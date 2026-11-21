"""Crisis-signal detection and safe escalation.

This module is intentionally conservative and deliberately modest about what
it can do. It detects *language patterns* that warrant a direct safety check.
It does not estimate suicide risk, and it never tells a person that they are
safe. Every escalation keeps human helplines and trusted people in view.

Priority rule for the whole application: if this module returns anything other
than ``level="none"``, the dialogue manager stops ordinary recommendation
selection and switches to the safety flow. Safety always outranks support.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..knowledge_base import KnowledgeBase

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def normalise(text: str) -> str:
    text = (text or "").translate(_APOSTROPHES).lower()
    text = re.sub(r"\bcan not\b", "cannot", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass(frozen=True)
class CrisisSignal:
    id: str
    category: str
    level: str
    label: str
    evidence: tuple[str, ...]
    needs_medical_check: bool = False
    third_party: bool = False

    def as_dict(self) -> dict[str, Any]:
        # Evidence is deliberately kept short and is not persisted by default.
        return {
            "id": self.id,
            "category": self.category,
            "level": self.level,
            "label": self.label,
            "needs_medical_check": self.needs_medical_check,
        }


@dataclass
class CrisisAssessment:
    level: str = "none"
    signals: list[CrisisSignal] = field(default_factory=list)
    needs_safety_check: bool = False
    third_party: bool = False
    protective_signal: bool = False
    explicit_denial: bool = False
    ambiguous: bool = False
    matched_text: tuple[str, ...] = ()

    @property
    def rank(self) -> int:
        return {"none": 0, "elevated": 2, "high": 3, "imminent": 4}.get(self.level, 0)

    @property
    def categories(self) -> list[str]:
        seen: list[str] = []
        for signal in self.signals:
            if signal.category not in seen:
                seen.append(signal.category)
        return seen

    @property
    def is_crisis(self) -> bool:
        return self.level != "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "categories": self.categories,
            "needs_safety_check": self.needs_safety_check,
            "third_party": self.third_party,
            "protective_signal": self.protective_signal,
            "explicit_denial": self.explicit_denial,
            "ambiguous": self.ambiguous,
        }


class CrisisDetector:
    """Pattern-based triage with explicit limitations."""

    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.kb = knowledge_base
        self._signals = knowledge_base.crisis.get("signals", [])
        self._protective = [
            re.compile(p, re.IGNORECASE)
            for p in knowledge_base.crisis.get("protective_signals", [])
        ]
        self._denials = [
            re.compile(p, re.IGNORECASE)
            for p in knowledge_base.crisis.get("denial_signals", [])
        ]
        self._level_rank = {
            name: data.get("rank", 0)
            for name, data in knowledge_base.crisis.get("levels", {}).items()
        }

    # ------------------------------------------------------------------
    def detect(self, text: str) -> CrisisAssessment:
        normalised = normalise(text)
        if not normalised:
            return CrisisAssessment()

        matched: list[CrisisSignal] = []
        evidence: list[str] = []
        for signal_def in self._signals:
            hits: list[str] = []
            for pattern in signal_def.get("patterns", []):
                for match in re.finditer(pattern, normalised, re.IGNORECASE):
                    if self._is_negated(normalised, match.start()):
                        continue
                    hits.append(match.group(0))
            if hits:
                matched.append(
                    CrisisSignal(
                        id=signal_def["id"],
                        category=signal_def["category"],
                        level=signal_def["level"],
                        label=signal_def.get("label", signal_def["category"]),
                        evidence=tuple(dict.fromkeys(hits)),
                        needs_medical_check=bool(signal_def.get("needs_medical_check")),
                        third_party=bool(signal_def.get("third_party")),
                    )
                )
                evidence.extend(hits)

        protective = any(p.search(normalised) for p in self._protective)
        denial = any(p.search(normalised) for p in self._denials)
        third_party = any(s.third_party for s in matched)

        if not matched:
            return CrisisAssessment(
                level="none",
                protective_signal=protective,
                explicit_denial=denial,
            )

        level = max((s.level for s in matched), key=lambda lv: self._level_rank.get(lv, 0))

        # An explicit denial ("I would never hurt myself") in a message whose
        # only signal is general active ideation is not dismissed. It is
        # downgraded one step and still followed by a safety check, because
        # ambivalence is common.
        strong_categories = {s.category for s in matched if s.level in {"high", "imminent"}}
        only_active_ideation = strong_categories <= {"active_ideation"}
        if denial and only_active_ideation and not any(
            s.category in {"planning", "access_to_means", "recent_attempt", "self_harm", "immediate_danger", "third_party_risk"}
            for s in matched
        ):
            level = "elevated"

        ambiguous = all(
            s.category in {"ambiguous_distress", "hopelessness"} for s in matched
        )
        return CrisisAssessment(
            level=level,
            signals=matched,
            needs_safety_check=level in {"elevated", "high", "imminent"},
            third_party=third_party,
            protective_signal=protective,
            explicit_denial=denial,
            ambiguous=ambiguous,
            matched_text=tuple(dict.fromkeys(evidence))[:8],
        )

    # ------------------------------------------------------------------
    def _is_negated(self, text: str, start: int) -> bool:
        """Detect a negation immediately before a match.

        This is deliberately a narrow window. A denial such as
        "I would never kill myself" is also handled by explicit denial
        patterns and still results in a gentle safety check.
        """
        window = text[max(0, start - 32):start]
        return bool(
            re.search(
                r"\b(not|never|no|don't|dont|doesn't|didn't|won't|wouldn't|isn't|aren't|hardly|barely)\b[^.!?,;]{0,20}$",
                window,
                re.IGNORECASE,
            )
        )

    # ------------------------------------------------------------------
    # Presentation helpers (kept here so safety wording is centralised)
    # ------------------------------------------------------------------
    def questions(self) -> list[dict[str, Any]]:
        return list(self.kb.crisis.get("safety_questions", []))

    def resources(self) -> list[dict[str, Any]]:
        return list(self.kb.crisis.get("resources", []))

    def safety_steps(self) -> list[str]:
        return list(self.kb.crisis.get("safety_steps", []))

    def opener(self, assessment: CrisisAssessment) -> str:
        if assessment.third_party:
            key = "third_party"
        elif assessment.level == "imminent":
            key = "imminent"
        elif assessment.level == "high":
            key = "high"
        elif assessment.ambiguous:
            key = "ambiguous"
        else:
            key = "elevated"
        return self.kb.crisis.get("response_openers", {}).get(key, "")

    def build_messages(self, assessment: CrisisAssessment) -> list[str]:
        """Return short paragraphs for the chat/safety panel.

        Wording is intentionally non-clinical, direct and non-judgemental.
        """
        if not assessment.is_crisis:
            return []

        messages: list[str] = []
        opener = self.opener(assessment)
        if opener:
            messages.append(opener)

        if assessment.third_party:
            messages.append(
                "You do not have to manage this alone, and you do not need to be a professional to help. "
                "Ask your friend directly whether they are thinking about suicide; asking does not plant the idea. "
                "If they are in immediate danger, stay with them if you can and call 112. Encourage them to call "
                "Tele-MANAS on 14416, and help them contact someone they trust."
            )
            messages.append(
                "Look after yourself too. Supporting someone at risk is heavy, and you are allowed to ask for help with it."
            )
        elif assessment.level in {"high", "imminent"}:
            messages.append(
                "Please do not stay alone with this. If you might act on these thoughts, call 112 now or go to the "
                "nearest emergency department. Tele-MANAS (14416) is a free 24/7 mental health helpline in India, "
                "and you can call them even if you are not sure what to say."
            )
            messages.append(
                "If you can, tell one person you trust that you are not safe right now and ask them to stay with you. "
                "Move away from anything you could use to hurt yourself, and ask someone to hold it for now."
            )
            if any(s.needs_medical_check for s in assessment.signals):
                messages.append(
                    "You mentioned something that may have already caused injury. Please contact emergency services "
                    "or go to an emergency department now, even if you feel embarrassed. Medical staff are there for this."
                )
            if assessment.protective_signal:
                messages.append(
                    "Part of you also mentioned wanting to stay safe. That part matters. Please let someone else help "
                    "you protect it right now."
                )
            if assessment.ambiguous:
                messages.append(
                    "I may have misread how serious this is, and I would rather ask than assume. "
                    "Are you having thoughts of ending your life or hurting yourself right now?"
                )
        else:
            messages.append(
                "I am going to ask you a few short, direct questions. There is no wrong answer, and you can stop at any time."
            )

        messages.append(
            "I am an academic support tool, not a crisis service or a therapist. I cannot assess your risk, "
            "and nothing here replaces a real person who can help."
        )
        return messages


def crisis_disclaimer() -> str:
    return (
        "MindMate is not a medical device, crisis service, or substitute for a qualified professional. "
        "If you are in immediate danger, call 112 (India). For mental health support, call Tele-MANAS on 14416."
    )
