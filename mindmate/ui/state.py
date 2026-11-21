"""Session-state helpers shared by the Streamlit pages.

The dialogue engine itself is recreated on each rerun from a plain state dict,
which keeps Streamlit hot-reloads from leaving stale objects behind.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from ..database import get_preferences, get_user, save_chat_message
from ..engine.dialogue import DialogueEngine, QuickReply, Turn, UserProfile
from ..knowledge_base import KnowledgeBase, load_knowledge_base

NAV_HOME = "🏡 Home"
NAV_CHAT = "💬 Talk to MindMate"
NAV_HABITS = "🌱 My Habits"
NAV_MOOD = "📈 Mood History"
NAV_REFLECTION = "📝 Daily Reflection"
NAV_REWARDS = "🏅 My Rewards"
NAV_SUMMARY = "🌙 Daily Summary"
NAV_RESOURCES = "🛟 Mental Health Resources"
NAV_SETTINGS = "⚙️ Settings"

NAV_OPTIONS = [
    NAV_HOME,
    NAV_CHAT,
    NAV_HABITS,
    NAV_MOOD,
    NAV_REFLECTION,
    NAV_REWARDS,
    NAV_SUMMARY,
    NAV_RESOURCES,
    NAV_SETTINGS,
]


@st.cache_resource(show_spinner=False)
def cached_kb() -> KnowledgeBase:
    return load_knowledge_base()


def user_profile(user_id: int) -> UserProfile:
    prefs = get_preferences(user_id)
    user = get_user(user_id)
    name = prefs.get("preferred_name") or (user["display_name"] if user else "Friend")
    return UserProfile(
        name=name or "Friend",
        time_available=prefs.get("time_available", "medium"),
        preferences=prefs.get("preferred_activities", []),
        mood_score=None,
    )


def get_engine(kb: KnowledgeBase, user_id: int) -> DialogueEngine:
    state = st.session_state.get("dialogue_state")
    return DialogueEngine(kb, user_profile(user_id), state)


def persist_engine(engine: DialogueEngine) -> None:
    st.session_state["dialogue_state"] = engine.state_dict()


def add_chat(role: str, content: str, user_id: int | None = None,
             persist: bool = False) -> None:
    st.session_state.setdefault("chat", []).append({"role": role, "content": content})
    if persist and user_id:
        try:
            save_chat_message(user_id, role, content)
        except Exception:  # chat persistence should never break support
            pass


def add_user_message(content: str, user_id: int | None = None, persist: bool = False) -> None:
    add_chat("user", content, user_id=user_id, persist=persist)


def apply_turn(engine: DialogueEngine, turn: Turn, user_id: int | None = None,
               persist_chat: bool = False) -> None:
    for message in turn.messages:
        if message and message.strip():
            add_chat("assistant", message, user_id=user_id, persist=persist_chat)
    st.session_state["last_turn"] = turn
    st.session_state["turn_seq"] = int(st.session_state.get("turn_seq", 0)) + 1
    persist_engine(engine)


def clear_chat() -> None:
    st.session_state["chat"] = []
    st.session_state["last_turn"] = None


def go_to(page_label: str) -> None:
    if page_label in NAV_OPTIONS:
        st.session_state["nav"] = page_label


def handle_quick_reply(
    engine: DialogueEngine,
    action: str,
    value: Any,
) -> Turn | None:
    """Apply a quick-reply action. Returns a new Turn, or None for UI-only actions."""
    if action == "text":
        return engine.submit_text(str(value))
    if action == "concern":
        return engine.submit_concern_choice([str(value)])
    if action == "answer":
        return engine.submit_answer(value["field"], value["value"])
    if action == "safety":
        return engine.submit_safety_answer(str(value))
    if action == "skip":
        return engine.skip_question()
    if action == "correct":
        return engine.correct_concerns()
    if action == "show_concerns":
        return engine.show_concern_picker()
    if action == "confirm":
        return engine.confirm()
    if action == "close":
        return engine.close()
    if action == "safety_resolved":
        return engine.submit_safety_resolved()
    if action == "reset":
        engine.reset()
        clear_chat()
        return None
    if action == "resources":
        go_to(NAV_RESOURCES)
        return None
    if action == "safety_steps":
        st.session_state["show_safety_steps"] = True
        return None
    if action == "habits":
        go_to(NAV_HABITS)
        return None
    return None


def load_saved_chat(user_id: int) -> None:
    """Load persisted transcript into the chat panel when the user opted in."""
    from ..database import get_chat_history

    if st.session_state.get("chat"):
        return
    history = get_chat_history(user_id, limit=40)
    st.session_state["chat"] = [
        {"role": row["role"], "content": row["content"]} for row in history
    ]


def reset_all_session_state() -> None:
    for key in (
        "user_id", "dialogue_state", "chat", "last_turn", "nav", "turn_seq",
        "show_safety_steps", "auth_view", "auth_notice", "theme",
    ):
        st.session_state.pop(key, None)


def logout() -> None:
    """End the local session without deleting any data."""
    for key in (
        "user_id", "dialogue_state", "chat", "last_turn", "turn_seq",
        "show_safety_steps", "auth_view",
    ):
        st.session_state.pop(key, None)
    st.session_state["nav"] = NAV_HOME
