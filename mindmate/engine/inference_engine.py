"""Forward-chaining inference engine.

Algorithm
---------
1.  Seed working memory with facts extracted from the user's message and
    structured answers (concerns and attributes).
2.  Evaluate every rule whose conditions all match the current facts.
3.  Conflict resolution: choose the matching rule with the highest salience;
    ties are broken by specificity (more conditions first), then declaration
    order. Fire exactly one rule, record its trace, and assert its conclusions.
4.  Repeat from step 2 until no unfired rule matches or the cycle limit is
    reached.

Because new facts are asserted between cycles, later rules can match on facts
that earlier rules produced. That is the defining behaviour of forward
chaining, and it is visible in :attr:`InferenceResult.fired_rules`.

The engine never mutates the knowledge base and never awards points. It only
produces an explainable conclusion set; services and the UI decide what to do
with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..knowledge_base import KnowledgeBase, Recommendation, Rule
from .working_memory import WorkingMemory


@dataclass(frozen=True)
class FiredRule:
    rule_id: str
    title: str
    category: str
    salience: int
    cycle: int
    matched_conditions: tuple[str, ...]
    added_facts: tuple[str, ...]
    recommended: tuple[str, ...]
    flags: tuple[str, ...]
    advice: tuple[str, ...]
    why: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "category": self.category,
            "salience": self.salience,
            "cycle": self.cycle,
            "matched_conditions": list(self.matched_conditions),
            "added_facts": list(self.added_facts),
            "recommended": list(self.recommended),
            "flags": list(self.flags),
            "advice": list(self.advice),
            "why": self.why,
        }


@dataclass(frozen=True)
class RecommendationMatch:
    recommendation: Recommendation
    score: float
    rule_ids: tuple[str, ...]
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.recommendation.id,
            "title": self.recommendation.title,
            "score": self.score,
            "rule_ids": list(self.rule_ids),
        }


@dataclass
class InferenceResult:
    fired_rules: list[FiredRule] = field(default_factory=list)
    recommendations: list[RecommendationMatch] = field(default_factory=list)
    professional_matches: list[RecommendationMatch] = field(default_factory=list)
    safety_matches: list[RecommendationMatch] = field(default_factory=list)
    flags: set[str] = field(default_factory=set)
    advice: list[str] = field(default_factory=list)
    working_memory: WorkingMemory = field(default_factory=WorkingMemory)
    cycles: int = 0
    cycle_limit_reached: bool = False

    @property
    def derived_facts(self) -> list[str]:
        return self.working_memory.derived_facts()

    @property
    def states(self) -> list[str]:
        return [f.split(":", 1)[1] for f in self.derived_facts if f.startswith("state:")]

    @property
    def needs(self) -> list[str]:
        return [f.split(":", 1)[1] for f in self.derived_facts if f.startswith("need:")]

    def explanation_lines(self) -> list[str]:
        """Plain-language trace suitable for the UI's 'Why these suggestions?' panel."""
        lines: list[str] = []
        for fired in self.fired_rules:
            conditions = "; ".join(fired.matched_conditions)
            produced = ", ".join(fired.added_facts) or "no new facts"
            recs = f" -> suggested {', '.join(fired.recommended)}" if fired.recommended else ""
            lines.append(
                f"Step {fired.cycle}: {fired.title} "
                f"(rule {fired.rule_id}, salience {fired.salience}) "
                f"because {conditions}. It added {produced}.{recs}"
            )
        return lines

    def as_dict(self) -> dict[str, Any]:
        return {
            "fired_rules": [r.as_dict() for r in self.fired_rules],
            "recommendations": [r.as_dict() for r in self.recommendations],
            "professional_matches": [r.as_dict() for r in self.professional_matches],
            "flags": sorted(self.flags),
            "advice": list(self.advice),
            "states": self.states,
            "needs": self.needs,
            "cycles": self.cycles,
            "cycle_limit_reached": self.cycle_limit_reached,
            "working_memory": self.working_memory.snapshot(),
        }


class InferenceEngine:
    """A deterministic, data-driven forward-chaining engine."""

    def __init__(self, knowledge_base: KnowledgeBase, max_cycles: int | None = None) -> None:
        self.kb = knowledge_base
        configured = knowledge_base.engine_config.get("max_cycles", 60)
        self.max_cycles = int(max_cycles or configured)

    # ------------------------------------------------------------------
    # Condition evaluation
    # ------------------------------------------------------------------
    def _attribute_matches(self, cond: dict[str, Any], wm: WorkingMemory) -> bool:
        key = cond["key"]
        op = cond["op"]
        expected = cond.get("value")
        if op == "exists":
            return key in wm.attributes
        if key not in wm.attributes:
            return False
        actual = wm.attributes[key]
        if op == "eq":
            return _loose_equal(actual, expected)
        if op == "ne":
            return not _loose_equal(actual, expected)
        if op == "in":
            return any(_loose_equal(actual, item) for item in _as_list(expected))
        if op == "not_in":
            return not any(_loose_equal(actual, item) for item in _as_list(expected))
        if op in {"lt", "lte", "gt", "gte"}:
            try:
                a, b = float(actual), float(expected)
            except (TypeError, ValueError):
                return False
            return {"lt": a < b, "lte": a <= b, "gt": a > b, "gte": a >= b}[op]
        if op == "contains":
            if isinstance(actual, (list, tuple, set)):
                return any(_loose_equal(item, expected) for item in actual)
            return str(expected).lower() in str(actual).lower()
        return False

    def _count_matches(self, cond: dict[str, Any], wm: WorkingMemory) -> bool:
        count = wm.count_prefix(cond["prefix"])
        expected = int(cond.get("value", 1))
        op = cond["op"]
        return {
            "gte": count >= expected,
            "gt": count > expected,
            "lte": count <= expected,
            "lt": count < expected,
            "eq": count == expected,
        }[op]

    def evaluate_condition(self, cond: dict[str, Any], wm: WorkingMemory) -> bool:
        kind = cond["kind"]
        if kind == "fact":
            return wm.has(cond["fact"])
        if kind == "absent":
            return not wm.has(cond["fact"])
        if kind == "any":
            return wm.has_any(cond.get("facts", []))
        if kind == "all":
            return wm.has_all(cond.get("facts", []))
        if kind == "attr":
            return self._attribute_matches(cond, wm)
        if kind == "fact_count":
            return self._count_matches(cond, wm)
        return False

    def rule_matches(self, rule: Rule, wm: WorkingMemory) -> bool:
        return all(self.evaluate_condition(c, wm) for c in rule.conditions)

    def matching_rules(self, wm: WorkingMemory, exclude: Iterable[str] = ()) -> list[Rule]:
        excluded = set(exclude)
        return [r for r in self.kb.rules if r.id not in excluded and self.rule_matches(r, wm)]

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self, wm: WorkingMemory) -> InferenceResult:
        result = InferenceResult(working_memory=wm)
        fired_ids: set[str] = set()
        rec_scores: dict[str, dict[str, Any]] = {}
        advice_seen: set[str] = set()

        for cycle in range(1, self.max_cycles + 1):
            candidates = self.matching_rules(wm, exclude=fired_ids)
            if not candidates:
                break
            # Conflict resolution: salience → specificity → declaration order.
            chosen = max(candidates, key=lambda r: (r.salience, r.specificity, -r.order))
            result.cycles = cycle
            fired_ids.add(chosen.id)

            added: list[str] = []
            recommended: list[str] = []
            flags: list[str] = []
            advice: list[str] = []

            for action in chosen.actions:
                kind = action["type"]
                if kind == "assert":
                    fact = action["fact"]
                    if wm.assert_fact(fact, source="inference", cycle=cycle,
                                      evidence=[f"rule {chosen.id}"]):
                        added.append(fact)
                elif kind == "recommend":
                    rec_id = action["recommendation"]
                    weight = float(action.get("weight", 1))
                    entry = rec_scores.setdefault(
                        rec_id, {"score": 0.0, "rule_ids": [], "reasons": []}
                    )
                    entry["score"] += weight
                    if chosen.id not in entry["rule_ids"]:
                        entry["rule_ids"].append(chosen.id)
                    if chosen.why not in entry["reasons"]:
                        entry["reasons"].append(chosen.why)
                    recommended.append(rec_id)
                elif kind == "flag":
                    flags.append(action["value"])
                    result.flags.add(action["value"])
                elif kind == "advice":
                    text = action["value"]
                    if text not in advice_seen:
                        advice_seen.add(text)
                        result.advice.append(text)
                        advice.append(text)

            result.fired_rules.append(
                FiredRule(
                    rule_id=chosen.id,
                    title=chosen.title,
                    category=chosen.category,
                    salience=chosen.salience,
                    cycle=cycle,
                    matched_conditions=tuple(c["label"] for c in chosen.conditions),
                    added_facts=tuple(added),
                    recommended=tuple(recommended),
                    flags=tuple(flags),
                    advice=tuple(advice),
                    why=chosen.why,
                )
            )
        else:
            result.cycle_limit_reached = True

        result.recommendations, result.professional_matches, result.safety_matches = (
            self._rank_recommendations(rec_scores, wm)
        )
        return result

    # ------------------------------------------------------------------
    # Recommendation ranking and filtering
    # ------------------------------------------------------------------
    def _rank_recommendations(
        self,
        rec_scores: dict[str, dict[str, Any]],
        wm: WorkingMemory,
        limit: int | None = None,
    ) -> tuple[list[RecommendationMatch], list[RecommendationMatch], list[RecommendationMatch]]:
        built: list[RecommendationMatch] = []
        for rec_id, data in rec_scores.items():
            rec = self.kb.get_recommendation(rec_id)
            if rec is None:  # validated at load time, defensive only
                continue
            built.append(
                RecommendationMatch(
                    recommendation=rec,
                    score=round(float(data["score"]), 2),
                    rule_ids=tuple(data["rule_ids"]),
                    reasons=tuple(data["reasons"]),
                )
            )

        built.sort(key=lambda m: (-m.score, m.recommendation.title))
        professional = [m for m in built if m.recommendation.kind == "professional"]
        safety = [m for m in built if m.recommendation.kind == "safety"]
        activities = [m for m in built if m.recommendation.kind == "activity"]

        activities = self._filter_by_capacity(activities, wm)
        activities = _diversify(activities, limit if limit is not None else 3)
        return activities, professional, safety

    @staticmethod
    def _filter_by_capacity(
        matches: list[RecommendationMatch], wm: WorkingMemory
    ) -> list[RecommendationMatch]:
        """Remove suggestions that do not fit the person's stated capacity.

        Filtering is done only when enough alternatives remain, so the engine
        never returns an empty list just because someone is exhausted.
        """
        time_available = str(wm.get_attribute("time_available", "")).lower()
        energy = str(wm.get_attribute("energy", "")).lower()

        def too_long(match: RecommendationMatch) -> bool:
            return time_available == "low" and match.recommendation.time_needed == "medium"

        def too_demanding(match: RecommendationMatch) -> bool:
            return energy == "low" and match.recommendation.energy_level in {"medium", "high"}

        filtered = [m for m in matches if not too_long(m) and not too_demanding(m)]
        if len(filtered) >= 2:
            return filtered
        return matches


def _diversify(matches: list[RecommendationMatch], limit: int) -> list[RecommendationMatch]:
    """Prefer variety across categories, then fill remaining slots by score."""
    chosen: list[RecommendationMatch] = []
    seen_categories: set[str] = set()
    for match in matches:
        category = match.recommendation.category
        if category in seen_categories:
            continue
        chosen.append(match)
        seen_categories.add(category)
        if len(chosen) >= limit:
            return chosen
    for match in matches:
        if match in chosen:
            continue
        chosen.append(match)
        if len(chosen) >= limit:
            break
    return chosen


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _loose_equal(left: Any, right: Any) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return left.strip().lower() == right.strip().lower()
    try:
        return float(left) == float(right)
    except (TypeError, ValueError):
        return left == right
