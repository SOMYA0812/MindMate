"""Conversational dialogue manager.

The dialogue manager is a deterministic state machine, not an open-ended
chatbot. It has four jobs:

1.  Run crisis detection on every user message *before* anything else.
2.  Extract evidence with the NLU detector, then ask up to two structured
    questions so the user can confirm or correct the interpretation.
3.  Run the forward-chaining engine over working memory.
4.  Return an explainable turn for the UI: messages, quick replies,
    recommendations, the rule trace, and safety resources.

The manager is UI-independent and can be unit-tested without Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..knowledge_base import KnowledgeBase
from .crisis import CrisisAssessment, CrisisDetector
from .inference_engine import FiredRule, InferenceEngine, InferenceResult, RecommendationMatch
from .nlu import DetectedConcern, DetectionResult, NLUDetector
from .working_memory import WorkingMemory

MAX_QUESTIONS = 2

_DURATION_LABELS = {
    "days": "for a few days",
    "weeks": "for a few weeks",
    "months": "for a month or more",
    "long_term": "for a long time",
}
_IMPACT_LABELS = {
    "mild": "affecting you a little",
    "moderate": "making some days harder",
    "severe": "making most days hard",
    "severe_plus": "making daily life very hard",
}
_SUPPORT_LABELS = {
    "has_support": "with someone you can talk to",
    "limited": "with only a little support",
    "isolated": "without much support around you",
}
_DISTRESS_RANK = {"low": 1, "moderate": 2, "high": 3}
_DURATION_RANK = {"days": 1, "weeks": 2, "months": 3, "long_term": 4}
_IMPACT_RANK = {"mild": 1, "moderate": 2, "severe": 3, "severe_plus": 4}
_SUPPORT_RANK = {"has_support": 1, "limited": 2, "isolated": 3}


@dataclass(frozen=True)
class QuickReply:
    label: str
    action: str
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {"label": self.label, "action": self.action, "value": self.value}


@dataclass
class UserProfile:
    name: str = "Friend"
    time_available: str = "medium"
    preferences: list[str] = field(default_factory=list)
    mood_score: int | None = None


@dataclass
class Turn:
    messages: list[str] = field(default_factory=list)
    quick_replies: list[QuickReply] = field(default_factory=list)
    stage: str = "new"
    concerns: list[DetectedConcern] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    crisis: CrisisAssessment | None = None
    inference: InferenceResult | None = None
    recommendations: list[RecommendationMatch] = field(default_factory=list)
    professional: list[RecommendationMatch] = field(default_factory=list)
    safety_recommendations: list[RecommendationMatch] = field(default_factory=list)
    advice: list[str] = field(default_factory=list)
    understanding: str | None = None
    safety_question: dict[str, Any] | None = None
    safety_step: int = 0
    resources: list[dict[str, Any]] = field(default_factory=list)
    safety_steps: list[str] = field(default_factory=list)
    all_concerns: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class DialogueEngine:
    """A small, testable conversation state machine."""

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        profile: UserProfile | None = None,
        state: dict[str, Any] | None = None,
    ) -> None:
        self.kb = knowledge_base
        self.profile = profile or UserProfile()
        self.nlu = NLUDetector(knowledge_base)
        self.crisis_detector = CrisisDetector(knowledge_base)
        self.inference = InferenceEngine(knowledge_base)
        self.state = self._default_state()
        if state:
            self.state.update(state)
            self.state["concerns"] = list(self.state.get("concerns", []))
            self.state["asked"] = list(self.state.get("asked", []))
            self.state["attributes"] = dict(self.state.get("attributes", {}))

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "stage": "new",
            "concerns": [],
            "concern_evidence": {},
            "concern_confidence": {},
            "attributes": {},
            "asked": [],
            "pending_field": None,
            "crisis_active": False,
            "crisis_level": "none",
            "crisis_categories": [],
            "crisis_ambiguous": False,
            "crisis_third_party": False,
            "crisis_history": False,
            "safety_step": 0,
            "safety_answers": {},
            "safety_confirmed": False,
            "empathy_given": [],
            "turn_count": 0,
        }

    def state_dict(self) -> dict[str, Any]:
        return {
            key: (list(value) if isinstance(value, list) else dict(value) if isinstance(value, dict) else value)
            for key, value in self.state.items()
        }

    @property
    def stage(self) -> str:
        return self.state["stage"]

    def reset(self) -> Turn:
        self.state = self._default_state()
        return self.start()

    # ------------------------------------------------------------------
    # Opening
    # ------------------------------------------------------------------
    def start(self) -> Turn:
        self.state["stage"] = "awaiting_text"
        name = self.profile.name.strip() or "Friend"
        messages = [
            f"Hi {name}. I'm MindMate. I'm here to listen, help you make sense of what is going on, "
            "and suggest small things that might make today a little more manageable.",
            "I'm a supportive academic tool, not a therapist, doctor or emergency service. "
            "You can write in your own words, and you can correct me at any point.",
            "What has been on your mind today?",
        ]
        replies = [
            QuickReply("I'm not sure how to explain it", "text", "I'm not sure how to explain it"),
            QuickReply("I'd rather pick from a list", "show_concerns"),
            QuickReply("Show crisis resources", "resources"),
        ]
        return Turn(
            messages=messages,
            quick_replies=replies,
            stage=self.state["stage"],
            concerns=self._detected_objects(),
            attributes=self.state["attributes"],
            all_concerns=self._all_concerns(),
        )

    # ------------------------------------------------------------------
    # Main text entry point
    # ------------------------------------------------------------------
    def submit_text(self, text: str) -> Turn:
        text = (text or "").strip()
        if not text:
            return Turn(
                messages=["I didn't catch that. You can write as little or as much as you like."],
                stage=self.stage,
                concerns=self._detected_objects(),
                all_concerns=self._all_concerns(),
                error="empty_message",
            )
        self.state["turn_count"] += 1

        # Safety always runs first, in every stage.
        assessment = self.crisis_detector.detect(text)
        if assessment.is_crisis:
            return self._begin_safety(assessment)

        if self.state["crisis_active"]:
            routed = self._route_safety_text(text)
            if routed is not None:
                return routed
            return Turn(
                messages=[
                    "I want to stay with your safety for a moment before we talk about anything else. "
                    "Please choose one of the options below — there is no wrong answer."
                ],
                quick_replies=self._safety_replies(),
                stage=self.stage,
                crisis=self._current_crisis(),
                safety_question=self._current_safety_question(),
                safety_step=self.state["safety_step"],
                resources=self.crisis_detector.resources(),
                all_concerns=self._all_concerns(),
            )

        if self.state["stage"] in {"awaiting_safety", "crisis_support"}:
            # Safety was resolved in a previous turn but the stage lagged.
            self.state["crisis_active"] = False

        if _is_closing(text):
            return self._closing_turn()

        if _is_acknowledgement(text) and self.state["concerns"]:
            return Turn(
                messages=[
                    "You're welcome. I'm here if you want to sit with the suggestions or tell me more. "
                    "You can also come back later — there is no deadline."
                ],
                quick_replies=self._supporting_replies(),
                stage="supporting",
                concerns=self._detected_objects(),
                attributes=self.state["attributes"],
                all_concerns=self._all_concerns(),
            )

        detection = self.nlu.detect(text)
        new_concerns = self._merge_detection(detection)
        self._merge_attributes(detection.attributes, explicit=False)

        if not self.state["concerns"]:
            return self._clarify_turn(detection)

        return self._after_evidence(new_concerns=new_concerns)

    # ------------------------------------------------------------------
    # Structured answers
    # ------------------------------------------------------------------
    def submit_concern_choice(self, concern_ids: Iterable[str], *, replace: bool = False) -> Turn:
        ids = [cid for cid in dict.fromkeys(concern_ids) if cid in self.kb.concerns]
        if not ids:
            return Turn(
                messages=["I didn't receive a concern to work with. You can pick one below, or describe it in your own words."],
                quick_replies=self._concern_replies(),
                stage="awaiting_concern",
                concerns=self._detected_objects(),
                all_concerns=self._all_concerns(),
                error="no_concern_selected",
            )

        if replace:
            self.state["concerns"] = ids
            self.state["concern_evidence"] = {cid: [] for cid in ids}
            self.state["concern_confidence"] = {cid: 100 for cid in ids}
        else:
            for cid in ids:
                if cid not in self.state["concerns"]:
                    self.state["concerns"].append(cid)
                self.state["concern_confidence"][cid] = 100
                self.state["concern_evidence"].setdefault(cid, [])

        # A concern chosen explicitly starts a fresh question budget.
        if replace:
            self.state["asked"] = []
            self.state["pending_field"] = None

        message = (
            "Thank you — I've updated my understanding. Let me ask something that will help me choose better."
            if replace
            else "Thank you. I've added that to what I understood."
        )
        return self._after_evidence(prefix=[message], new_concerns=ids)

    def submit_answer(self, field: str, value: Any) -> Turn:
        followup = self.kb.get_followup(field)
        attribute = followup.attribute if followup else field
        coerced = _coerce_value(attribute, value)
        self.state["attributes"][attribute] = coerced
        if followup is None or field not in self.state["asked"]:
            self.state["asked"].append(field)
        self.state["pending_field"] = None

        if attribute == "impact":
            mapped = "high" if coerced in {"severe", "severe_plus"} else (
                "moderate" if coerced == "moderate" else "low"
            )
            self.state["attributes"]["distress"] = mapped

        return self._after_evidence(prefix=["Thank you — that helps me choose something that fits."])

    def skip_question(self) -> Turn:
        if self.state["pending_field"]:
            self.state["asked"].append(self.state["pending_field"])
            self.state["pending_field"] = None
        return self._after_evidence(prefix=["That's completely okay — we can leave that blank."])

    def correct_concerns(self) -> Turn:
        self.state["stage"] = "awaiting_concern_correction"
        return Turn(
            messages=[
                "No problem — I would rather get this right. Which of these fits better? "
                "You can pick more than one."
            ],
            quick_replies=self._concern_replies(),
            stage=self.state["stage"],
            concerns=self._detected_objects(),
            attributes=self.state["attributes"],
            all_concerns=self._all_concerns(),
        )

    def show_concern_picker(self) -> Turn:
        self.state["stage"] = "awaiting_concern"
        return Turn(
            messages=["Of course. Which of these feels closest? You can pick more than one."],
            quick_replies=self._concern_replies(),
            stage=self.state["stage"],
            concerns=self._detected_objects(),
            attributes=self.state["attributes"],
            all_concerns=self._all_concerns(),
        )

    # ------------------------------------------------------------------
    # Safety flow
    # ------------------------------------------------------------------
    def _begin_safety(self, assessment: CrisisAssessment) -> Turn:
        self.state.update(
            {
                "stage": "awaiting_safety",
                "crisis_active": True,
                "crisis_level": assessment.level,
                "crisis_categories": assessment.categories,
                "crisis_ambiguous": assessment.ambiguous,
                "crisis_third_party": assessment.third_party,
                "crisis_history": True,
                "safety_step": 0,
                "safety_answers": {},
                "safety_confirmed": False,
            }
        )
        messages = self.crisis_detector.build_messages(assessment)
        replies: list[QuickReply] = []
        question = None

        if assessment.third_party:
            replies = [
                QuickReply("Show helplines", "resources"),
                QuickReply("I'm okay for now", "close"),
            ]
        else:
            question = self._current_safety_question()
            if question:
                messages.append(question["question"])
                replies = self._safety_replies()

        return Turn(
            messages=messages,
            quick_replies=replies,
            stage=self.state["stage"],
            crisis=assessment,
            safety_question=question,
            safety_step=self.state["safety_step"],
            resources=self.crisis_detector.resources(),
            safety_steps=self.crisis_detector.safety_steps(),
            concerns=self._detected_objects(),
            all_concerns=self._all_concerns(),
        )

    def submit_safety_answer(self, value: str) -> Turn:
        step = int(self.state.get("safety_step", 0))
        self.state["safety_answers"][f"step_{step}"] = value

        if self.state.get("crisis_third_party"):
            return self._third_party_turn()

        messages: list[str] = []
        if step == 0:
            if value == "help_now":
                return self._urgent_safety_turn(
                    "Thank you for being honest. This is the moment to involve another person. "
                    "Please call 112 now if you are in immediate danger, or Tele-MANAS on 14416. "
                    "If you can, stay on the line and do not stay alone."
                )
            if value == "unsure":
                messages.append(
                    "Thank you for being honest. I am not going to assume either way. "
                    "Please call Tele-MANAS on 14416 now and tell them exactly what you told me. "
                    "You do not need to have the right words."
                )
                messages.append("One more question, so I understand the situation:")
                self.state["safety_step"] = 1
                return self._safety_question_turn(messages)
            # safe_now → still ask about plan/access
            messages.append(
                "Thank you for telling me. I am glad you are safe right now. "
                "I would still like to ask two short questions, because safety can change quickly."
            )
            self.state["safety_step"] = 1
            return self._safety_question_turn(messages)

        if step == 1:
            if value == "has_plan":
                return self._urgent_safety_turn(
                    "Thank you for telling me. Having a plan or access to something you could use is serious. "
                    "Please move away from it if you can, ask someone to hold it, and call 112 or Tele-MANAS 14416 now. "
                    "If you can, tell a trusted person to come and stay with you."
                )
            if value == "unsure":
                messages.append(
                    "Thank you for being honest. When something is unclear, the safest step is to involve a person "
                    "who can help. Please call Tele-MANAS on 14416 now, and stay with someone if you can."
                )
            else:
                messages.append("Thank you. I am glad there is no plan or access right now.")
            messages.append("Last question:")
            self.state["safety_step"] = 2
            return self._safety_question_turn(messages)

        # step 2: someone available or alone
        self.state["safety_confirmed"] = True
        self.state["crisis_active"] = False
        if value == "someone_available":
            messages.append(
                "I'm glad someone is available. Please ask them to stay with you, even if you do not want to explain everything. "
                "Keep the helpline numbers visible for later."
            )
        else:
            messages.append(
                "Thank you for answering. Not having someone physically with you right now is hard. "
                "Please consider calling Tele-MANAS on 14416 and staying on the line; you do not have to be alone with this."
            )
        messages.append(
            "I am going to keep the safety resources visible. If anything changes and you feel unsafe, call 112 or 14416 immediately."
        )
        self.state["stage"] = "supporting"
        self.state["safety_step"] = 3
        return self._after_evidence(prefix=messages, allow_crisis_support=True)

    def submit_safety_resolved(self) -> Turn:
        self.state["safety_confirmed"] = True
        self.state["crisis_active"] = False
        self.state["stage"] = "supporting"
        self.state["safety_step"] = 3
        return self._after_evidence(
            prefix=[
                "I'm really glad you reached out to someone. That took courage. "
                "Please keep the helpline numbers somewhere visible, and come back here whenever you need."
            ],
            allow_crisis_support=True,
        )

    def _urgent_safety_turn(self, message: str) -> Turn:
        self.state["stage"] = "crisis_support"
        self.state["crisis_active"] = True
        self.state["safety_step"] = 3
        return Turn(
            messages=[message, "You do not have to solve this alone, and you do not have to explain it perfectly."],
            quick_replies=[
                QuickReply("I've contacted someone", "safety_resolved"),
                QuickReply("Show helplines again", "resources"),
                QuickReply("I'm with someone now", "safety_resolved"),
            ],
            stage=self.state["stage"],
            crisis=self._current_crisis(),
            safety_question=None,
            safety_step=3,
            resources=self.crisis_detector.resources(),
            safety_steps=self.crisis_detector.safety_steps(),
            concerns=self._detected_objects(),
            all_concerns=self._all_concerns(),
        )

    def _safety_question_turn(self, messages: list[str]) -> Turn:
        self.state["stage"] = "awaiting_safety"
        question = self._current_safety_question()
        if question:
            messages.append(question["question"])
            if question.get("help"):
                messages.append(question["help"])
        return Turn(
            messages=messages,
            quick_replies=self._safety_replies(),
            stage=self.state["stage"],
            crisis=self._current_crisis(),
            safety_question=question,
            safety_step=self.state["safety_step"],
            resources=self.crisis_detector.resources(),
            safety_steps=self.crisis_detector.safety_steps(),
            concerns=self._detected_objects(),
            all_concerns=self._all_concerns(),
        )

    def _third_party_turn(self) -> Turn:
        self.state["stage"] = "crisis_support"
        self.state["crisis_active"] = True
        return Turn(
            messages=[
                "Your friend's safety matters, and so does yours. Stay with them if you can, ask directly whether they are "
                "thinking about suicide, and help them call Tele-MANAS on 14416.",
                "If they are in immediate danger, call 112. Do not leave them alone if you can avoid it, and do not promise "
                "to keep it secret from everyone who could help.",
                "You do not have to carry this by yourself. Tell another trusted adult or a counsellor what is happening.",
            ],
            quick_replies=[
                QuickReply("Show helplines", "resources"),
                QuickReply("I'm okay for now", "close"),
            ],
            stage=self.state["stage"],
            crisis=self._current_crisis(),
            resources=self.crisis_detector.resources(),
            safety_steps=self.crisis_detector.safety_steps(),
            all_concerns=self._all_concerns(),
        )

    def _route_safety_text(self, text: str) -> Turn | None:
        lowered = text.lower()
        if any(phrase in lowered for phrase in ("i called", "i have called", "spoke to someone", "talked to someone", "with someone now", "someone is with me")):
            return self.submit_safety_resolved()

        step = int(self.state.get("safety_step", 0))
        if "not sure" in lowered or "don't know" in lowered or "dont know" in lowered:
            return self.submit_safety_answer("unsure")
        if step == 0:
            if any(phrase in lowered for phrase in ("yes", "need help", "not safe", "help now")):
                return self.submit_safety_answer("help_now")
            if any(phrase in lowered for phrase in ("safe", "no", "okay", "ok")):
                return self.submit_safety_answer("safe_now")
        elif step == 1:
            if any(phrase in lowered for phrase in ("yes", "plan", "have access")):
                return self.submit_safety_answer("has_plan")
            if any(phrase in lowered for phrase in ("no", "none", "don't have", "dont have")):
                return self.submit_safety_answer("no_plan")
        elif step == 2:
            if any(phrase in lowered for phrase in ("alone", "nobody", "no one")):
                return self.submit_safety_answer("alone")
            if any(phrase in lowered for phrase in ("yes", "someone", "friend", "family")):
                return self.submit_safety_answer("someone_available")
        return None

    def _current_safety_question(self) -> dict[str, Any] | None:
        questions = self.crisis_detector.questions()
        step = int(self.state.get("safety_step", 0))
        if 0 <= step < len(questions):
            return questions[step]
        return None

    def _safety_replies(self) -> list[QuickReply]:
        question = self._current_safety_question()
        replies: list[QuickReply] = []
        if question:
            replies = [QuickReply(opt["label"], "safety", opt["value"]) for opt in question.get("options", [])]
        replies.append(QuickReply("Show helplines", "resources"))
        return replies

    def _current_crisis(self) -> CrisisAssessment | None:
        if not self.state.get("crisis_history") and not self.state.get("crisis_active"):
            return None
        return CrisisAssessment(
            level=self.state.get("crisis_level", "none"),
            needs_safety_check=True,
            third_party=bool(self.state.get("crisis_third_party")),
            ambiguous=bool(self.state.get("crisis_ambiguous")),
        )

    # ------------------------------------------------------------------
    # Evidence handling
    # ------------------------------------------------------------------
    def _merge_detection(self, detection: DetectionResult) -> list[str]:
        new_ids: list[str] = []
        for concern in detection.concerns:
            if concern.id not in self.state["concerns"]:
                self.state["concerns"].append(concern.id)
                new_ids.append(concern.id)
            self.state["concern_confidence"][concern.id] = max(
                int(self.state["concern_confidence"].get(concern.id, 0)),
                concern.confidence,
            )
            existing = self.state["concern_evidence"].get(concern.id, [])
            merged = list(dict.fromkeys([*existing, *concern.matched_phrases]))[:6]
            self.state["concern_evidence"][concern.id] = merged
        return new_ids

    def _merge_attributes(self, attributes: dict[str, Any], *, explicit: bool) -> None:
        current = self.state["attributes"]
        for key, value in attributes.items():
            if value is None:
                continue
            if key == "preferences":
                merged = list(dict.fromkeys([*current.get("preferences", []), *list(value)]))
                current["preferences"] = merged
                continue
            if key in {"duration", "impact", "distress", "support"} and not explicit and key in current:
                ranks = {
                    "duration": _DURATION_RANK,
                    "impact": _IMPACT_RANK,
                    "distress": _DISTRESS_RANK,
                    "support": _SUPPORT_RANK,
                }[key]
                if ranks.get(str(value), 0) < ranks.get(str(current[key]), 0):
                    continue
            current[key] = value

    def _detected_objects(self) -> list[DetectedConcern]:
        result: list[DetectedConcern] = []
        for cid in self.state["concerns"]:
            concern = self.kb.get_concern(cid)
            if not concern:
                continue
            result.append(
                DetectedConcern(
                    id=cid,
                    label=concern.label,
                    emoji=concern.emoji,
                    confidence=int(self.state["concern_confidence"].get(cid, 60)),
                    matched_phrases=tuple(self.state["concern_evidence"].get(cid, [])),
                    strong_match=bool(self.state["concern_evidence"].get(cid)),
                )
            )
        return result

    # ------------------------------------------------------------------
    # Turn builders
    # ------------------------------------------------------------------
    def _clarify_turn(self, detection: DetectionResult) -> Turn:
        self.state["stage"] = "awaiting_concern"
        messages: list[str] = []
        if detection.generic_distress:
            messages.append(
                "It sounds like something is off, even if the words are hard to find. That is okay. "
                "Sometimes it is easier to start with a rough direction."
            )
        else:
            messages.append(
                "I want to make sure I understand rather than guess. I did not pick up a clear concern from that."
            )
        messages.append(
            "Which of these feels closest? You can pick more than one. If none fit, tell me in your own words and I will try again."
        )
        return Turn(
            messages=messages,
            quick_replies=self._concern_replies(),
            stage=self.state["stage"],
            concerns=self._detected_objects(),
            attributes=self.state["attributes"],
            all_concerns=self._all_concerns(),
        )

    def _after_evidence(self, *, prefix: list[str] | None = None,
                        new_concerns: list[str] | None = None,
                        allow_crisis_support: bool = False) -> Turn:
        messages = list(prefix or [])
        if not self.state["concerns"]:
            if self.state.get("safety_confirmed") and allow_crisis_support:
                messages.append(
                    "You do not have to explain what happened. If you want, we can stay with what is here now — "
                    "and the helpline numbers will remain visible."
                )
                return self._support_turn(messages, new_concerns=[])
            self.state["stage"] = "awaiting_concern"
            messages.append("Which of these feels closest? You can pick more than one.")
            return Turn(
                messages=messages,
                quick_replies=self._concern_replies(),
                stage=self.state["stage"],
                concerns=self._detected_objects(),
                attributes=self.state["attributes"],
                all_concerns=self._all_concerns(),
            )

        question_key = None if self.state.get("safety_confirmed") else self._next_question_key()
        if question_key and not allow_crisis_support:
            return self._ask_question(question_key, messages)

        return self._support_turn(messages, new_concerns=new_concerns or [])

    def _next_question_key(self) -> str | None:
        if len(self.state["asked"]) >= MAX_QUESTIONS:
            return None
        primary = self.state["concerns"][0]
        concern = self.kb.get_concern(primary)
        if not concern:
            return None
        for key in concern.followups:
            followup = self.kb.get_followup(key)
            if not followup:
                continue
            if key in self.state["asked"]:
                continue
            if followup.attribute in self.state["attributes"]:
                continue
            return key
        return None

    def _ask_question(self, key: str, prefix: list[str]) -> Turn:
        followup = self.kb.get_followup(key)
        self.state["stage"] = "awaiting_detail"
        self.state["pending_field"] = key
        concern = self.kb.get_concern(self.state["concerns"][0])
        messages = list(prefix)
        if concern and concern.empathy:
            messages.append(concern.empathy[0])
        if followup:
            messages.append(followup.question)
            if followup.help:
                messages.append(followup.help)
        replies = [
            QuickReply(opt["label"], "answer", {"field": key, "value": opt["value"]})
            for opt in (followup.options if followup else [])
        ]
        replies.append(QuickReply("Skip this", "skip"))
        return Turn(
            messages=messages,
            quick_replies=replies,
            stage=self.state["stage"],
            concerns=self._detected_objects(),
            attributes=self.state["attributes"],
            understanding=self._understanding_text(),
            all_concerns=self._all_concerns(),
        )

    def _support_turn(self, prefix: list[str] | None = None,
                      new_concerns: list[str] | None = None) -> Turn:
        self.state["stage"] = "supporting"
        self.state["pending_field"] = None
        messages = list(prefix or [])
        new_ids = new_concerns or []

        empathy_message = self._empathy_message(new_ids)
        if empathy_message:
            messages.append(empathy_message)

        if self.state.get("crisis_history") and self.state.get("safety_confirmed") and not self.state.get("crisis_active"):
            messages.append(
                "I have not forgotten what you told me earlier. Safety is still the first thing here, "
                "so I will keep the helpline information visible."
            )

        messages.append(
            "Here is my best understanding — please correct me if it is off: "
            + self._understanding_text(include_intro=False)
        )

        if self.state.get("crisis_active"):
            return Turn(
                messages=messages,
                quick_replies=self._safety_replies(),
                stage=self.state["stage"],
                crisis=self._current_crisis(),
                safety_question=self._current_safety_question(),
                resources=self.crisis_detector.resources(),
                concerns=self._detected_objects(),
                attributes=self.state["attributes"],
                understanding=self._understanding_text(),
                all_concerns=self._all_concerns(),
            )

        inference = self.current_inference()
        if inference is None:
            self.state["stage"] = "awaiting_concern"
            messages.append("Which of these feels closest? You can pick more than one.")
            return Turn(
                messages=messages,
                quick_replies=self._concern_replies(),
                stage=self.state["stage"],
                concerns=self._detected_objects(),
                attributes=self.state["attributes"],
                all_concerns=self._all_concerns(),
            )

        if inference.recommendations:
            messages.append(
                "Based on that, here are a few small options. They are suggestions, not instructions — "
                "use one, adapt it, or ignore them all."
            )
        else:
            messages.append(
                "I do not have an activity suggestion for this moment. That is not a failure; "
                "sometimes the most useful thing is to stay with the feeling and keep support around you."
            )

        for advice in inference.advice[:2]:
            messages.append(advice)

        if inference.professional_matches:
            messages.append(
                "It may also be worth talking to a counsellor or doctor. Not because you have failed at self-help, "
                "but because heavier or longer-lasting difficulties deserve a real conversation with a qualified person. "
                "This app cannot diagnose anything."
            )

        top = self.kb.get_concern(self.state["concerns"][0]) if self.state["concerns"] else None
        if top and top.risk_note:
            messages.append(top.risk_note)

        return Turn(
            messages=messages,
            quick_replies=self._supporting_replies(),
            stage=self.state["stage"],
            concerns=self._detected_objects(),
            attributes=self.state["attributes"],
            crisis=self._current_crisis() if self.state.get("crisis_history") else None,
            inference=inference,
            recommendations=inference.recommendations,
            professional=inference.professional_matches,
            safety_recommendations=inference.safety_matches,
            advice=inference.advice,
            understanding=self._understanding_text(),
            resources=self.crisis_detector.resources() if self.state.get("crisis_history") else [],
            all_concerns=self._all_concerns(),
        )

    def _empathy_message(self, new_ids: list[str]) -> str | None:
        given = self.state.get("empathy_given", [])
        candidate = None
        for cid in new_ids or self.state["concerns"]:
            if cid not in given:
                candidate = cid
                break
        if not candidate:
            return "Thank you for telling me more. I'm still with you." if self.state["turn_count"] > 1 else None
        concern = self.kb.get_concern(candidate)
        if not concern:
            return None
        self.state["empathy_given"].append(candidate)
        lines = list(concern.empathy[:1])
        if concern.normalise:
            lines.append(concern.normalise)
        return " ".join(lines)

    def _understanding_text(self, include_intro: bool = True) -> str:
        parts: list[str] = []
        for cid in self.state["concerns"][:3]:
            concern = self.kb.get_concern(cid)
            if not concern:
                continue
            evidence = self.state["concern_evidence"].get(cid, [])
            label = concern.label.lower()
            if evidence:
                quoted = ", ".join(f"'{p}'" for p in evidence[:3])
                parts.append(f"{label} (you mentioned {quoted})")
            else:
                parts.append(label)

        context: list[str] = []
        attrs = self.state["attributes"]
        if "duration" in attrs:
            context.append(_DURATION_LABELS.get(str(attrs["duration"]), str(attrs["duration"])))
        if "impact" in attrs:
            context.append(_IMPACT_LABELS.get(str(attrs["impact"]), str(attrs["impact"])))
        if "sleep_hours" in attrs:
            context.append(f"around {attrs['sleep_hours']} hours of sleep")
        if "support" in attrs:
            context.append(_SUPPORT_LABELS.get(str(attrs["support"]), str(attrs["support"])))

        text = "; ".join(parts) if parts else "something you are still finding words for"
        if context:
            text += ". You also mentioned: " + "; ".join(context)
        return ("Here is what I heard: " if include_intro else "") + text + "."

    def _supporting_replies(self) -> list[QuickReply]:
        replies = [
            QuickReply("That's right", "confirm"),
            QuickReply("Let me correct that", "correct"),
            QuickReply("Show helplines", "resources"),
            QuickReply("I'm done for now", "close"),
        ]
        if self.state.get("crisis_history"):
            replies.insert(2, QuickReply("Show safety steps", "safety_steps"))
        return replies

    def _concern_replies(self) -> list[QuickReply]:
        common = [
            "sadness", "anxiety", "stress", "loneliness", "low_motivation",
            "sleep_difficulty", "overwhelm", "negative_thinking",
        ]
        replies = []
        for cid in common:
            concern = self.kb.get_concern(cid)
            if concern:
                replies.append(QuickReply(f"{concern.emoji} {concern.short}", "concern", cid))
        replies.append(QuickReply("Something else", "show_concerns"))
        return replies

    def _all_concerns(self) -> list[dict[str, Any]]:
        return [
            {
                "id": cid,
                "label": self.kb.concerns[cid].label,
                "short": self.kb.concerns[cid].short,
                "emoji": self.kb.concerns[cid].emoji,
                "description": self.kb.concerns[cid].description,
            }
            for cid in self.kb.concern_order
        ]

    def _closing_turn(self) -> Turn:
        self.state["stage"] = "closing"
        messages = [
            "Thank you for spending this time with me. Whatever you managed today — even opening this page — counts.",
            "You can come back whenever you want. If things feel unsafe, please use the helplines; you do not have to wait for the next conversation.",
        ]
        return Turn(
            messages=messages,
            quick_replies=[
                QuickReply("Start a new conversation", "reset"),
                QuickReply("Show helplines", "resources"),
            ],
            stage=self.state["stage"],
            concerns=self._detected_objects(),
            attributes=self.state["attributes"],
            resources=self.crisis_detector.resources() if self.state.get("crisis_history") else [],
            all_concerns=self._all_concerns(),
        )

    def close(self) -> Turn:
        """Public closing response for the UI."""
        return self._closing_turn()

    def confirm(self) -> Turn:
        """User confirmed the interpretation; keep suggestions available."""
        result = self.current_inference()
        return Turn(
            messages=[
                "Thank you for confirming. I'll keep the suggestions below. "
                "You can use one, adapt it, or close the page — none of it is an assignment.",
                "If something changes, or the suggestions do not fit, you can tell me and we will adjust.",
            ],
            quick_replies=self._supporting_replies(),
            stage="supporting",
            concerns=self._detected_objects(),
            attributes=self.state["attributes"],
            inference=result,
            recommendations=result.recommendations if result else [],
            professional=result.professional_matches if result else [],
            safety_recommendations=result.safety_matches if result else [],
            understanding=self._understanding_text(),
            resources=self.crisis_detector.resources() if self.state.get("crisis_history") else [],
            all_concerns=self._all_concerns(),
        )

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def _build_working_memory(self) -> WorkingMemory:
        wm = WorkingMemory()
        for cid in self.state["concerns"]:
            wm.assert_fact(f"concern:{cid}", source="user")
        for key, value in self.state["attributes"].items():
            wm.set_attribute(key, value, source="user")
        if self.profile.time_available and "time_available" not in wm.attributes:
            wm.set_attribute("time_available", self.profile.time_available, source="profile")
        if self.profile.preferences and "preferences" not in wm.attributes:
            wm.set_attribute("preferences", list(self.profile.preferences), source="profile")
        if self.state.get("safety_confirmed"):
            wm.assert_fact("safety:confirmed", source="user")
        if self.state.get("crisis_history"):
            wm.assert_fact("history:crisis_signal", source="conversation")
        return wm

    def current_inference(self) -> InferenceResult | None:
        if not self.state["concerns"] and not self.state.get("safety_confirmed"):
            return None
        if self.state.get("crisis_active"):
            return None
        return self.inference.run(self._build_working_memory())

    def explanation(self) -> list[str]:
        result = self.current_inference()
        return result.explanation_lines() if result else []

    def trace_rows(self) -> list[dict[str, Any]]:
        result = self.current_inference()
        if not result:
            return []
        return [fired.as_dict() for fired in result.fired_rules]

    def resources(self) -> list[dict[str, Any]]:
        return self.crisis_detector.resources()

    def safety_steps(self) -> list[str]:
        return self.crisis_detector.safety_steps()

    # ------------------------------------------------------------------
    # Helpers used by UI
    # ------------------------------------------------------------------
    def summary_facts(self) -> dict[str, Any]:
        return {
            "concerns": list(self.state["concerns"]),
            "attributes": dict(self.state["attributes"]),
            "crisis_history": bool(self.state.get("crisis_history")),
            "safety_confirmed": bool(self.state.get("safety_confirmed")),
            "stage": self.state["stage"],
        }


def _coerce_value(attribute: str, value: Any) -> Any:
    if attribute == "sleep_hours":
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


def _is_closing(text: str) -> bool:
    lowered = text.lower().strip()
    phrases = ("i'm done", "im done", "goodbye", "bye", "that's all", "thats all", "thank you, bye", "see you")
    return any(phrase in lowered for phrase in phrases)


def _is_acknowledgement(text: str) -> bool:
    lowered = text.lower().strip().strip(".!")
    return lowered in {"thanks", "thank you", "ok", "okay", "got it", "sure", "yes", "no", "hmm", "alright"}
