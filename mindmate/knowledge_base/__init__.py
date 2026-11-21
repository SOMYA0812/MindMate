"""Knowledge-base loading and validation.

The knowledge base is stored as JSON so that rules can be inspected, edited and
demonstrated without touching Python code. This module turns the JSON into
read-only objects and fails loudly if the knowledge is malformed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import KB_DIR

VALID_CONDITION_KINDS = {"fact", "any", "all", "absent", "attr", "fact_count"}
VALID_ATTRIBUTE_OPS = {
    "eq", "ne", "in", "not_in", "lt", "lte", "gt", "gte", "exists", "contains",
}
VALID_ACTION_TYPES = {"assert", "recommend", "flag", "advice"}


class KnowledgeBaseError(ValueError):
    """Raised when the rule files are inconsistent or incomplete."""


@dataclass(frozen=True)
class Recommendation:
    id: str
    title: str
    category: str
    kind: str
    summary: str
    why: str
    steps: tuple[str, ...]
    duration_minutes: int
    time_needed: str
    energy_level: str
    tags: tuple[str, ...]
    caution: str | None
    habit_template: dict[str, Any] | None


@dataclass(frozen=True)
class Concern:
    id: str
    label: str
    short: str
    emoji: str
    description: str
    empathy: tuple[str, ...]
    normalise: str
    followups: tuple[str, ...]
    keywords: tuple[str, ...]
    strong_keywords: tuple[str, ...]
    risk_note: str | None


@dataclass(frozen=True)
class FollowUp:
    attribute: str
    question: str
    help: str
    options: tuple[dict[str, Any], ...]
    severity_map: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    category: str
    salience: int
    conditions: tuple[dict[str, Any], ...]
    actions: tuple[dict[str, Any], ...]
    why: str
    order: int

    @property
    def specificity(self) -> int:
        return len(self.conditions)

    def as_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "salience": self.salience,
            "category": self.category,
            "conditions": " AND ".join(c.get("label", c.get("fact", c.get("kind", ""))) for c in self.conditions),
            "actions": "; ".join(_describe_action(a) for a in self.actions),
            "why": self.why,
        }


def _describe_action(action: dict[str, Any]) -> str:
    kind = action["type"]
    if kind == "assert":
        return f"assert {action['fact']}"
    if kind == "recommend":
        return f"recommend {action['recommendation']} (w={action.get('weight', 1)})"
    if kind == "flag":
        return f"flag {action['value']}"
    if kind == "advice":
        return "offer advice"
    return kind


@dataclass(frozen=True)
class KnowledgeBase:
    concerns: dict[str, Concern]
    concern_order: tuple[str, ...]
    followups: dict[str, FollowUp]
    rules: tuple[Rule, ...]
    recommendations: dict[str, Recommendation]
    crisis: dict[str, Any]
    severity_phrases: dict[str, tuple[str, ...]]
    impact_phrases: dict[str, tuple[str, ...]]
    support_phrases: dict[str, tuple[str, ...]]
    preference_phrases: dict[str, tuple[str, ...]]
    engine_config: dict[str, Any]

    # -- lookups ---------------------------------------------------------
    def get_concern(self, concern_id: str) -> Concern | None:
        return self.concerns.get(concern_id)

    def get_recommendation(self, rec_id: str) -> Recommendation | None:
        return self.recommendations.get(rec_id)

    def get_followup(self, key: str) -> FollowUp | None:
        return self.followups.get(key)

    def rules_as_rows(self) -> list[dict[str, Any]]:
        return [rule.as_row() for rule in self.rules]

    def concerns_as_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "id": c.id,
                "label": c.label,
                "description": c.description,
                "example_phrases": ", ".join(c.strong_keywords + c.keywords[:5]),
                "follow_up_questions": ", ".join(c.followups),
            }
            for c in (self.concerns[cid] for cid in self.concern_order)
        ]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise KnowledgeBaseError(f"Knowledge-base file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise KnowledgeBaseError(f"Invalid JSON in {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise KnowledgeBaseError(f"{path.name} must contain a JSON object")
    return data


def _validate_rule(rule: dict[str, Any], rec_ids: set[str], seen: set[str]) -> None:
    required = {"id", "title", "salience", "conditions", "then", "why"}
    missing = required - set(rule)
    if missing:
        raise KnowledgeBaseError(f"Rule {rule.get('id', '?')} is missing {sorted(missing)}")
    rid = rule["id"]
    if rid in seen:
        raise KnowledgeBaseError(f"Duplicate rule id: {rid}")
    seen.add(rid)
    if not isinstance(rule["salience"], int):
        raise KnowledgeBaseError(f"Rule {rid}: salience must be an integer")
    if not rule["conditions"]:
        raise KnowledgeBaseError(f"Rule {rid}: at least one condition is required")

    for cond in rule["conditions"]:
        kind = cond.get("kind")
        if kind not in VALID_CONDITION_KINDS:
            raise KnowledgeBaseError(f"Rule {rid}: unknown condition kind {kind!r}")
        if not cond.get("label"):
            raise KnowledgeBaseError(f"Rule {rid}: every condition needs a human-readable label")
        if kind in {"fact", "absent"}:
            fact = cond.get("fact", "")
            if ":" not in fact:
                raise KnowledgeBaseError(f"Rule {rid}: fact {fact!r} must look like 'namespace:value'")
        elif kind in {"any", "all"}:
            facts = cond.get("facts", [])
            if not facts or any(":" not in f for f in facts):
                raise KnowledgeBaseError(f"Rule {rid}: {kind} needs a list of namespaced facts")
        elif kind == "attr":
            if cond.get("op") not in VALID_ATTRIBUTE_OPS:
                raise KnowledgeBaseError(f"Rule {rid}: unknown attribute operator {cond.get('op')!r}")
            if not cond.get("key"):
                raise KnowledgeBaseError(f"Rule {rid}: attribute condition needs a key")
        elif kind == "fact_count":
            if cond.get("op") not in {"gte", "gt", "lte", "lt", "eq"}:
                raise KnowledgeBaseError(f"Rule {rid}: invalid fact_count operator")
            if not cond.get("prefix"):
                raise KnowledgeBaseError(f"Rule {rid}: fact_count needs a prefix")

    for action in rule["then"]:
        kind = action.get("type")
        if kind not in VALID_ACTION_TYPES:
            raise KnowledgeBaseError(f"Rule {rid}: unknown action type {kind!r}")
        if kind == "assert" and ":" not in action.get("fact", ""):
            raise KnowledgeBaseError(f"Rule {rid}: asserted fact must be namespaced")
        if kind == "recommend":
            rec_id = action.get("recommendation")
            if rec_id not in rec_ids:
                raise KnowledgeBaseError(f"Rule {rid}: unknown recommendation {rec_id!r}")
            if not isinstance(action.get("weight", 1), (int, float)):
                raise KnowledgeBaseError(f"Rule {rid}: recommendation weight must be numeric")


@lru_cache(maxsize=4)
def load_knowledge_base(kb_dir: str | Path | None = None) -> KnowledgeBase:
    """Load and validate all knowledge files.

    Results are cached because the files are static at runtime.
    """
    base = Path(kb_dir) if kb_dir else KB_DIR
    categories = _read_json(base / "categories.json")
    rule_data = _read_json(base / "rules.json")
    rec_data = _read_json(base / "recommendations.json")
    crisis_data = _read_json(base / "crisis_patterns.json")

    # -- recommendations ------------------------------------------------
    recommendations: dict[str, Recommendation] = {}
    for item in rec_data.get("recommendations", []):
        try:
            rec = Recommendation(
                id=item["id"],
                title=item["title"],
                category=item["category"],
                kind=item.get("kind", "activity"),
                summary=item["summary"],
                why=item["why"],
                steps=tuple(item.get("steps", [])),
                duration_minutes=int(item.get("duration_minutes", 5)),
                time_needed=item.get("time_needed", "low"),
                energy_level=item.get("energy_level", "any"),
                tags=tuple(item.get("tags", [])),
                caution=item.get("caution"),
                habit_template=item.get("habit_template"),
            )
        except KeyError as exc:
            raise KnowledgeBaseError(f"Recommendation missing field {exc}: {item!r}") from exc
        if rec.id in recommendations:
            raise KnowledgeBaseError(f"Duplicate recommendation id: {rec.id}")
        if rec.kind not in {"activity", "professional", "safety"}:
            raise KnowledgeBaseError(f"Recommendation {rec.id}: invalid kind {rec.kind!r}")
        if rec.time_needed not in {"low", "medium", "high"}:
            raise KnowledgeBaseError(f"Recommendation {rec.id}: invalid time_needed")
        if rec.energy_level not in {"low", "medium", "high", "any"}:
            raise KnowledgeBaseError(f"Recommendation {rec.id}: invalid energy_level")
        recommendations[rec.id] = rec
    if not recommendations:
        raise KnowledgeBaseError("No recommendations found")

    # -- concerns -------------------------------------------------------
    concerns: dict[str, Concern] = {}
    order: list[str] = []
    for item in categories.get("concerns", []):
        try:
            concern = Concern(
                id=item["id"],
                label=item["label"],
                short=item.get("short", item["label"]),
                emoji=item.get("emoji", "💬"),
                description=item.get("description", ""),
                empathy=tuple(item.get("empathy", [])),
                normalise=item.get("normalise", ""),
                followups=tuple(item.get("followups", ["duration", "impact"])),
                keywords=tuple(item.get("keywords", [])),
                strong_keywords=tuple(item.get("strong_keywords", [])),
                risk_note=item.get("risk_note"),
            )
        except KeyError as exc:
            raise KnowledgeBaseError(f"Concern missing field {exc}: {item!r}") from exc
        if concern.id in concerns:
            raise KnowledgeBaseError(f"Duplicate concern id: {concern.id}")
        concerns[concern.id] = concern
        order.append(concern.id)

    followups: dict[str, FollowUp] = {}
    for key, item in categories.get("followup_questions", {}).items():
        followups[key] = FollowUp(
            attribute=item["attribute"],
            question=item["question"],
            help=item.get("help", ""),
            options=tuple(item.get("options", [])),
            severity_map=item.get("severity_map", {}),
        )
    if not followups:
        raise KnowledgeBaseError("No follow-up questions found")

    # -- rules ----------------------------------------------------------
    seen: set[str] = set()
    rec_ids = set(recommendations)
    rules: list[Rule] = []
    for index, item in enumerate(rule_data.get("rules", [])):
        _validate_rule(item, rec_ids, seen)
        rules.append(
            Rule(
                id=item["id"],
                title=item["title"],
                category=item.get("category", "general"),
                salience=int(item["salience"]),
                conditions=tuple(item["conditions"]),
                actions=tuple(item["then"]),
                why=item["why"],
                order=index,
            )
        )
    if not rules:
        raise KnowledgeBaseError("No rules found")

    # -- crisis patterns -------------------------------------------------
    for signal in crisis_data.get("signals", []):
        if signal.get("level") not in {"elevated", "high", "imminent"}:
            raise KnowledgeBaseError(f"Crisis signal {signal.get('id')}: invalid level")
        for pattern in signal.get("patterns", []):
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error as exc:
                raise KnowledgeBaseError(
                    f"Crisis signal {signal.get('id')}: invalid regex {pattern!r}: {exc}"
                ) from exc
    for pattern in crisis_data.get("protective_signals", []) + crisis_data.get("denial_signals", []):
        try:
            re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            raise KnowledgeBaseError(f"Invalid crisis regex {pattern!r}: {exc}") from exc
    if not crisis_data.get("resources"):
        raise KnowledgeBaseError("Crisis resources are required")

    return KnowledgeBase(
        concerns=concerns,
        concern_order=tuple(order),
        followups=followups,
        rules=tuple(rules),
        recommendations=recommendations,
        crisis=crisis_data,
        severity_phrases={k: tuple(v) for k, v in categories.get("severity_phrases", {}).items()},
        impact_phrases={k: tuple(v) for k, v in categories.get("impact_phrases", {}).items()},
        support_phrases={k: tuple(v) for k, v in categories.get("support_phrases", {}).items()},
        preference_phrases={k: tuple(v) for k, v in categories.get("preference_phrases", {}).items()},
        engine_config=rule_data.get("engine", {}),
    )
