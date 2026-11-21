"""The support conversation page."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ...knowledge_base import KnowledgeBase
from ...services import mood, rewards
from .. import components
from ..state import (
    NAV_HABITS,
    NAV_RESOURCES,
    add_user_message,
    apply_turn,
    clear_chat,
    get_engine,
    go_to,
    handle_quick_reply,
    load_saved_chat,
    persist_engine,
)


def render(user_id: int, kb: KnowledgeBase, prefs: dict[str, Any]) -> None:
    components.page_header(
        "💬",
        "Talk to MindMate",
        "Write in your own words. MindMate will reflect what it hears, ask a couple of questions, "
        "and offer small optional suggestions. You can correct it at any time.",
    )

    if prefs.get("save_chat_history"):
        load_saved_chat(user_id)

    persist_chat = bool(prefs.get("save_chat_history"))
    engine = get_engine(kb, user_id)

    if not st.session_state.get("chat"):
        turn = engine.start()
        apply_turn(engine, turn, user_id=user_id, persist_chat=persist_chat)

    top_left, top_right, top_mid = st.columns([1, 1, 1])
    with top_left:
        if st.button("🔄 New conversation", use_container_width=True, key="chat_reset"):
            clear_chat()
            turn = engine.reset()
            apply_turn(engine, turn, user_id=user_id, persist_chat=persist_chat)
            st.rerun()
    with top_mid:
        if st.button("🛟 Helplines", use_container_width=True, key="chat_helplines"):
            go_to(NAV_RESOURCES)
            st.rerun()
    with top_right:
        today = mood.get_mood_entry(user_id)
        if today:
            st.markdown(
                f'<div style="text-align:right;padding-top:0.35rem">'
                f'<span class="mm-pill mint">Today: {mood.mood_label(today["mood_score"])["emoji"]} '
                f'{mood.mood_label(today["mood_score"])["label"]}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("No mood check-in today")

    if not persist_chat:
        st.caption("🔒 This conversation is kept only in this browser session and is not saved to the database.")

    if engine.state.get("crisis_history"):
        components.crisis_banner()

    if st.session_state.pop("show_safety_steps", False):
        with st.expander("Safety steps you can use right now", expanded=True):
            for step in engine.safety_steps():
                st.markdown(f"- {step}")

    chat_history = st.session_state.get("chat", [])
    for message in chat_history:
        role = message.get("role", "assistant")
        avatar = "🌿" if role == "assistant" else "🧑"
        with st.chat_message(role, avatar=avatar):
            st.markdown(message.get("content", ""))

    turn = st.session_state.get("last_turn")
    if turn is not None:
        if turn.understanding:
            components.render_understanding(turn.concerns, turn.attributes)

        if turn.recommendations:
            st.markdown("#### A few small options")
            st.caption("Optional. Use one, adapt it, or ignore them all — there is no assignment here.")
            components.render_recommendations(
                turn.recommendations, user_id, key_prefix=f"chat_{st.session_state.get('turn_seq', 0)}"
            )

        if turn.professional:
            components.render_professional(turn.professional)

        if turn.safety_recommendations:
            components.render_safety_plan(turn.safety_recommendations)

        if turn.inference:
            with st.expander("🧠 Why did MindMate suggest this? (rule trace)"):
                components.render_rule_trace(turn.inference)

        if turn.resources:
            with st.expander("🛟 Helplines and safety steps"):
                if turn.safety_steps:
                    st.markdown("**Safety steps**")
                    for step in turn.safety_steps:
                        st.markdown(f"- {step}")
                components.render_resources(turn.resources)

        _render_quick_replies(engine, turn, user_id, persist_chat)

    prompt = st.chat_input("Write what's on your mind…")
    if prompt:
        cleaned = prompt.strip()
        if cleaned:
            add_user_message(cleaned, user_id=user_id, persist=persist_chat)
            new_turn = engine.submit_text(cleaned)
            apply_turn(engine, new_turn, user_id=user_id, persist_chat=persist_chat)
            st.rerun()

    st.caption(
        "MindMate is not a therapist or emergency service. If you are in immediate danger, call 112 (India) "
        "or Tele-MANAS on 14416."
    )


def _render_quick_replies(engine, turn, user_id: int, persist_chat: bool) -> None:
    seq = st.session_state.get("turn_seq", 0)

    if turn.stage in {"awaiting_concern", "awaiting_concern_correction"}:
        options = [item["id"] for item in turn.all_concerns]
        labels = {item["id"]: f"{item['emoji']} {item['label']}" for item in turn.all_concerns}
        current = [c.id for c in turn.concerns]
        st.markdown("#### Or choose from the full list")
        chosen = st.multiselect(
            "What feels closest? You can choose more than one.",
            options=options,
            default=[cid for cid in current if cid in options],
            format_func=lambda cid: labels.get(cid, cid),
            key=f"concern_pick_{seq}",
        )
        if st.button("Use these concerns", type="primary", key=f"concern_apply_{seq}"):
            if not chosen:
                st.toast("Choose at least one option, or type in your own words below.")
            else:
                add_user_message(
                    "I'd choose: " + ", ".join(labels.get(cid, cid) for cid in chosen),
                    user_id=user_id,
                    persist=persist_chat,
                )
                new_turn = engine.submit_concern_choice(
                    chosen, replace=turn.stage == "awaiting_concern_correction"
                )
                apply_turn(engine, new_turn, user_id=user_id, persist_chat=persist_chat)
                st.rerun()

    replies = list(turn.quick_replies)
    if not replies:
        return

    st.markdown('<div class="mm-label" style="margin-top:0.7rem">Quick replies</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for index, reply in enumerate(replies):
        with cols[index % 3]:
            is_primary = reply.action == "safety" and reply.value == "help_now"
            if st.button(
                reply.label,
                key=f"qr_{seq}_{index}",
                use_container_width=True,
                type="primary" if is_primary else "secondary",
            ):
                if reply.action not in {"resources", "safety_steps"}:
                    add_user_message(reply.label, user_id=user_id, persist=persist_chat)
                new_turn = handle_quick_reply(engine, reply.action, reply.value)
                if new_turn is not None:
                    apply_turn(engine, new_turn, user_id=user_id, persist_chat=persist_chat)
                st.rerun()
