"""Hybrid natural-language understanding for the support conversation.

The detector is deliberately *not* the whole expert system. It extracts
evidence from free text:

* concern phrases, with negation and overlap handling;
* duration, impact, sleep hours, support, energy, time and preferences;
* strong language that suggests higher distress.

The dialogue manager then asks structured follow-up questions so that the user
can confirm or correct what was understood. Nothing is inferred as a diagnosis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..knowledge_base import Concern, KnowledgeBase

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})

_INTENSIFIERS = (
    "very", "really", "so", "extremely", "completely", "totally", "constantly",
    "always", "terribly", "incredibly", "awfully", "super",
)

_GENERIC_DISTRESS = (
    "not okay", "not ok", "struggling", "feel weird", "feeling weird",
    "feel off", "feeling off", "don't feel good", "do not feel good",
    "rough day", "bad day", "hard day", "not myself",
)


@dataclass(frozen=True)
class DetectedConcern:
    id: str
    label: str
    emoji: str
    confidence: int
    matched_phrases: tuple[str, ...]
    strong_match: bool = False

    @property
    def evidence_text(self) -> str:
        return ", ".join(self.matched_phrases[:4])

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "confidence": self.confidence,
            "phrases": list(self.matched_phrases),
        }


@dataclass
class DetectionResult:
    concerns: list[DetectedConcern] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    matched_text: tuple[str, ...] = ()
    generic_distress: bool = False
    raw_text: str = ""

    @property
    def concern_ids(self) -> list[str]:
        return [c.id for c in self.concerns]

    @property
    def top_concern(self) -> DetectedConcern | None:
        return self.concerns[0] if self.concerns else None

    @property
    def unknown(self) -> bool:
        return not self.concerns

    def by_id(self, concern_id: str) -> DetectedConcern | None:
        return next((c for c in self.concerns if c.id == concern_id), None)

    def summary(self) -> str:
        if not self.concerns:
            return "No clear concern phrase detected"
        labels = ", ".join(f"{c.label} ({c.confidence}%)" for c in self.concerns[:3])
        if self.attributes:
            context = ", ".join(f"{k}={v}" for k, v in self.attributes.items())
            return f"{labels}; context: {context}"
        return labels


class NLUDetector:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.kb = knowledge_base
        self._concern_patterns = self._compile_concern_patterns()
        self._impact = self._compile_phrase_map(knowledge_base.impact_phrases)
        self._distress = self._compile_phrase_map(knowledge_base.severity_phrases)
        self._support = self._compile_phrase_map(knowledge_base.support_phrases)
        self._preferences = self._compile_phrase_map(knowledge_base.preference_phrases)

    # ------------------------------------------------------------------
    # Compilation
    # ------------------------------------------------------------------
    @staticmethod
    def _phrase_regex(phrase: str) -> re.Pattern[str]:
        wildcard = phrase.endswith("*")
        body = phrase[:-1] if wildcard else phrase
        suffix = r"[a-z]*" if wildcard else ""
        return re.compile(r"\b" + re.escape(body) + suffix + r"\b", re.IGNORECASE)

    def _compile_concern_patterns(self) -> dict[str, list[tuple[str, bool, re.Pattern[str]]]]:
        compiled: dict[str, list[tuple[str, bool, re.Pattern[str]]]] = {}
        for cid in self.kb.concern_order:
            concern = self.kb.concerns[cid]
            entries: list[tuple[str, bool, re.Pattern[str]]] = []
            seen: set[str] = set()
            for phrase in concern.strong_keywords:
                if phrase not in seen:
                    entries.append((phrase, True, self._phrase_regex(phrase)))
                    seen.add(phrase)
            for phrase in concern.keywords:
                if phrase not in seen:
                    entries.append((phrase, False, self._phrase_regex(phrase)))
                    seen.add(phrase)
            entries.sort(key=lambda item: len(item[0]), reverse=True)
            compiled[cid] = entries
        return compiled

    @staticmethod
    def _compile_phrase_map(
        mapping: dict[str, tuple[str, ...]]
    ) -> dict[str, list[tuple[str, re.Pattern[str]]]]:
        result: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
        for key, phrases in mapping.items():
            items = [(p, re.compile(r"\b" + re.escape(p) + r"\b", re.IGNORECASE)) for p in phrases]
            items.sort(key=lambda x: len(x[0]), reverse=True)
            result[key] = items
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, text: str, *, max_concerns: int = 3) -> DetectionResult:
        normalised = self._normalise(text)
        result = DetectionResult(raw_text=text)
        if not normalised:
            return result

        matched_all: list[str] = []
        for cid in self.kb.concern_order:
            concern = self.kb.concerns[cid]
            matched = self._match_concern(normalised, self._concern_patterns[cid])
            if not matched:
                continue
            phrases, strong = matched
            confidence = self._score(phrases, strong, normalised)
            if confidence < 40:
                continue
            result.concerns.append(
                DetectedConcern(
                    id=cid,
                    label=concern.label,
                    emoji=concern.emoji,
                    confidence=confidence,
                    matched_phrases=tuple(phrases),
                    strong_match=strong,
                )
            )
            matched_all.extend(phrases)

        result.concerns.sort(key=lambda c: (-c.confidence, self.kb.concern_order.index(c.id)))
        result.concerns = result.concerns[:max_concerns]
        result.matched_text = tuple(dict.fromkeys(matched_all))[:8]
        result.attributes = self._extract_attributes(normalised)
        result.generic_distress = any(p in normalised for p in _GENERIC_DISTRESS)
        return result

    # ------------------------------------------------------------------
    # Concern matching
    # ------------------------------------------------------------------
    def _match_concern(
        self,
        text: str,
        patterns: Iterable[tuple[str, bool, re.Pattern[str]]],
    ) -> tuple[list[str], bool] | None:
        """Match longer phrases first and skip overlapping shorter ones.

        This prevents "can't sleep" being suppressed by a negation in front of
        the shorter word "sleep", and stops double-counting "panic attack" and
        "panic".
        """
        spans: list[tuple[int, int]] = []
        phrases: list[str] = []
        strong = False
        for phrase, is_strong, pattern in patterns:
            for match in pattern.finditer(text):
                start, end = match.span()
                if any(start < e and end > s for s, e in spans):
                    continue
                if self._negated(text, start):
                    continue
                spans.append((start, end))
                phrases.append(phrase.replace("*", ""))
                strong = strong or is_strong
        if not phrases:
            return None
        return list(dict.fromkeys(phrases)), strong

    @staticmethod
    def _negated(text: str, start: int) -> bool:
        window = text[max(0, start - 30):start]
        return bool(
            re.search(
                r"\b(not|never|no|don't|dont|doesn't|didn't|won't|wouldn't|isn't|aren't|hardly|barely)\b"
                r"[^.!?,;]{0,18}$",
                window,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _score(phrases: list[str], strong: bool, text: str) -> int:
        score = 35
        score += 12 * len(phrases)
        if strong:
            score += 20
            score = max(score, 68)
        first = phrases[0].replace("*", "")
        index = text.find(first)
        window = text[max(0, index - 24):index] if index >= 0 else ""
        if any(re.search(r"\b" + re.escape(word) + r"\b", window) for word in _INTENSIFIERS):
            score += 8
        return min(score, 92)

    # ------------------------------------------------------------------
    # Attribute extraction
    # ------------------------------------------------------------------
    def _extract_attributes(self, text: str) -> dict[str, Any]:
        attrs: dict[str, Any] = {}

        duration = self._extract_duration(text)
        if duration:
            attrs["duration"] = duration

        impact = self._first_level(text, self._impact, priority=["severe_plus", "severe", "moderate", "mild"])
        if impact:
            attrs["impact"] = impact

        distress = self._first_level(text, self._distress, priority=["high", "moderate", "low"])
        if distress:
            attrs["distress"] = distress

        sleep_hours = self._extract_sleep_hours(text)
        if sleep_hours is not None:
            attrs["sleep_hours"] = sleep_hours

        support = self._extract_support(text)
        if support:
            attrs["support"] = support

        prefs = [
            key for key, items in self._preferences.items()
            if any(pattern.search(text) for _, pattern in items)
        ]
        if prefs:
            attrs["preferences"] = prefs

        time_available = self._extract_time(text)
        if time_available:
            attrs["time_available"] = time_available

        energy = self._extract_energy(text)
        if energy:
            attrs["energy"] = energy

        return attrs

    @staticmethod
    def _first_level(
        text: str,
        mapping: dict[str, list[tuple[str, re.Pattern[str]]]],
        priority: list[str],
    ) -> str | None:
        for level in priority:
            for _, pattern in mapping.get(level, []):
                if pattern.search(text):
                    return level
        return None

    @staticmethod
    def _extract_duration(text: str) -> str | None:
        candidates: list[tuple[int, str]] = []
        rules = {
            "long_term": [
                r"\ball my life\b", r"\bmy whole life\b", r"\bas long as i can remember\b",
                r"\bfor years\b", r"\bfor (a )?very long\b", r"\bsince childhood\b",
            ],
            "months": [
                r"\bfor (a |a few |several )?months?\b", r"\bfor \d+ months?\b",
                r"\bsince (last|a few) months?\b", r"\blast month\b",
            ],
            "weeks": [
                r"\bfor (a |a few |several )?weeks?\b", r"\bfor \d+ weeks?\b",
                r"\bfor (the )?(past|last) (few )?weeks?\b", r"\bthis week\b",
            ],
            "days": [
                r"\bfor (a |a few |several )?days?\b", r"\bfor \d+ days?\b",
                r"\b(past|last) (few )?days?\b", r"\bsince yesterday\b", r"\btoday\b",
            ],
        }
        rank = {"days": 1, "weeks": 2, "months": 3, "long_term": 4}
        for level, patterns in rules.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    candidates.append((rank[level], level))
                    break
        if not candidates:
            return None
        return max(candidates)[1]

    @staticmethod
    def _extract_sleep_hours(text: str) -> float | None:
        if re.search(r"\b(haven'?t|have not) slept\b|\bawake all night\b|\bno sleep\b", text):
            return 2.0
        range_match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", text
        )
        if range_match:
            low, high = float(range_match.group(1)), float(range_match.group(2))
            if 0 < low <= high <= 24:
                return round((low + high) / 2, 1)
        less = re.search(r"\b(?:less than|under|only)\s*(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", text)
        if less:
            value = float(less.group(1))
            if 0 < value <= 24:
                return max(0.5, value - 0.5)
        # Require sleep context near the number to avoid "I study 5 hours".
        for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", text):
            window = text[max(0, match.start() - 30):match.start()]
            if re.search(r"\b(sleep|slept|sleeping|night|bed|rest)\b", window):
                value = float(match.group(1))
                if 0 < value <= 24:
                    return value
        shorthand = re.search(r"\bslept\s*(?:only\s*)?(\d+(?:\.\d+)?)\b", text)
        if shorthand:
            value = float(shorthand.group(1))
            if 0 < value <= 24:
                return value
        return None

    def _extract_support(self, text: str) -> str | None:
        isolated = any(p.search(text) for _, p in self._support.get("isolated", []))
        has_support = any(p.search(text) for _, p in self._support.get("has_support", []))
        if isolated:
            return "isolated"
        if has_support:
            return "has_support"
        if re.search(r"\bnot really\b.*\b(talk|anyone|someone)\b", text):
            return "limited"
        return None

    @staticmethod
    def _extract_time(text: str) -> str | None:
        if re.search(r"\b(no time|not much time|hardly any time|very busy|swamped|overloaded)\b", text):
            return "low"
        if re.search(r"\b(have time|free time|flexible|not busy|plenty of time)\b", text):
            return "high"
        return None

    @staticmethod
    def _extract_energy(text: str) -> str | None:
        if re.search(r"\b(no energy|exhausted|drained|depleted|running on empty|so tired|completely tired)\b", text):
            return "low"
        if re.search(r"\b(some energy|a bit of energy|okay energy|moderate energy)\b", text):
            return "okay"
        if re.search(r"\b(energetic|full of energy|rested|good energy)\b", text):
            return "high"
        return None

    @staticmethod
    def _normalise(text: str) -> str:
        text = (text or "").translate(_APOSTROPHES).lower()
        text = re.sub(r"\bcan not\b", "cannot", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
