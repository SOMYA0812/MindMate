"""Settings, privacy and data controls.

This page is deliberately plain and explicit. A mental-health support tool
should make it obvious what is stored, what is optional, and how to remove it.
Nothing here is hidden behind jargon, and no control asks the user to explain
themselves.
"""

from __future__ import annotations

import html
import json
from datetime import date
from typing import Any

import streamlit as st

from ...config import APP_NAME, VERSION
from ...database import (
    change_password,
    clear_chat_history,
    delete_user_data,
    export_user_data,
    get_user,
    query_one,
    update_preferences,
)
from ...knowledge_base import KnowledgeBase
from .. import components
from ..state import clear_chat, logout, reset_all_session_state
from ..theme import is_dark, set_theme


_TIME_OPTIONS = {
    "low": "A few minutes (up to 10)",
    "medium": "A little time (10–30 minutes)",
    "high": "More time available (30+ minutes)",
}

_PREFERENCE_OPTIONS = {
    "outdoors": "🌳 Being outdoors or moving",
    "social": "🫂 Talking with people",
    "quiet": "📖 Quiet, low-stimulation activities",
    "creative": "🎨 Creative expression",
}


def _count(table: str, user_id: int) -> int:
    row = query_one(f"SELECT COUNT(*) AS c FROM {table} WHERE user_id = ?", (user_id,))
    return int(row["c"]) if row else 0


def _consent_badge(given: bool) -> str:
    if given:
        return '<span class="mm-pill mint">✓ Consent recorded</span>'
    return '<span class="mm-pill">Consent not recorded</span>'


def render(user_id: int, kb: KnowledgeBase, prefs: dict[str, Any]) -> None:
    components.page_header(
        "⚙️",
        "Settings",
        "Your account, appearance and privacy in one place. Everything is stored in a local SQLite file "
        "on this device, and you can export or delete it at any time.",
    )

    user = get_user(user_id)
    if user is None:
        st.error("This profile no longer exists. Reload the app to start again.")
        return
    user = dict(user)

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    components.section_title("Your profile")
    st.caption(
        "A nickname is enough. The trusted contact is optional, stored locally, and MindMate never "
        "contacts anyone automatically."
    )

    with st.form("profile_form"):
        c1, c2 = st.columns(2)
        preferred_name = c1.text_input(
            "What should MindMate call you?",
            value=prefs.get("preferred_name") or user.get("display_name") or "",
            max_chars=60,
        )
        time_available = c2.selectbox(
            "How much time do you usually have for an activity?",
            options=list(_TIME_OPTIONS),
            index=list(_TIME_OPTIONS).index(prefs.get("time_available", "medium"))
            if prefs.get("time_available", "medium") in _TIME_OPTIONS
            else 1,
            format_func=lambda key: _TIME_OPTIONS[key],
            help="Used only to keep suggestions realistic. You can change it any time.",
        )

        chosen_preferences = st.multiselect(
            "Anything you tend to find easier or more enjoyable? (optional)",
            options=list(_PREFERENCE_OPTIONS),
            default=[p for p in prefs.get("preferred_activities", []) if p in _PREFERENCE_OPTIONS],
            format_func=lambda key: _PREFERENCE_OPTIONS[key],
            help="These only influence which optional suggestions appear first.",
        )

        c3, c4 = st.columns(2)
        contact_name = c3.text_input(
            "Trusted contact name (optional)",
            value=prefs.get("contact_name") or "",
            max_chars=80,
        )
        contact_phone = c4.text_input(
            "Trusted contact phone (optional)",
            value=prefs.get("contact_phone") or "",
            max_chars=40,
        )

        if st.form_submit_button("Save profile", type="primary"):
            if not preferred_name.strip():
                st.error("Please keep a name or nickname.")
            else:
                update_preferences(
                    user_id,
                    preferred_name=preferred_name.strip()[:60],
                    time_available=time_available,
                    preferred_activities=chosen_preferences,
                    contact_name=contact_name.strip()[:80],
                    contact_phone=contact_phone.strip()[:40],
                )
                st.toast("Profile saved.")
                st.rerun()

    # ------------------------------------------------------------------
    # Account and security
    # ------------------------------------------------------------------
    st.markdown("---")
    components.section_title("Account & security")
    username = user.get("username") or ""
    st.markdown(
        f'<div class="mm-card-soft"><div class="mm-label">Username</div>'
        f'<div style="font-weight:600">@{html.escape(username)}</div>'
        f'<div class="mm-small" style="margin-top:0.35rem">Last sign-in: '
        f'{html.escape(str(user.get("last_login_at") or "not recorded"))}</div></div>',
        unsafe_allow_html=True,
    )
    with st.form("change_password_form"):
        st.markdown("#### Change password")
        c1, c2, c3 = st.columns(3)
        current_password = c1.text_input("Current password", type="password", max_chars=200)
        new_password = c2.text_input("New password", type="password", max_chars=200)
        confirm_password = c3.text_input("Confirm new password", type="password", max_chars=200)
        changed = st.form_submit_button("Update password", type="primary")
    if changed:
        if new_password != confirm_password:
            st.error("The two new passwords do not match.")
        else:
            try:
                ok = change_password(user_id, current_password, new_password)
            except ValueError as exc:
                st.error(str(exc))
            else:
                if ok:
                    st.success("Password updated. Use the new password next time you sign in.")
                else:
                    st.error("Your current password did not match.")
    st.caption(
        "If you forget this password, use the one-time recovery code you saved at sign-up. "
        "MindMate cannot reset it without that code and does not send email."
    )

    # ------------------------------------------------------------------
    # Appearance
    # ------------------------------------------------------------------
    st.markdown("---")
    components.section_title("Appearance")
    st.caption("The same choice applies to every page, chart, card and form.")
    current_theme = "dark" if is_dark() else "light"
    chosen_theme = st.radio(
        "Theme",
        options=["light", "dark"],
        index=0 if current_theme == "light" else 1,
        format_func=lambda value: "☀︎ Light" if value == "light" else "☾ Dark",
        horizontal=True,
        key=f"settings_theme_{current_theme}",
        label_visibility="collapsed",
    )
    if chosen_theme != current_theme:
        set_theme(chosen_theme)
        update_preferences(user_id, theme=chosen_theme)
        st.rerun()

    st.markdown(
        '<div class="mm-small" style="margin-top:0.6rem">'
        '<a href="?view=privacy">Privacy policy</a> · <a href="?view=terms">Terms of use</a> · '
        '<a href="?view=resources">Helplines &amp; safety</a></div>',
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------
    st.markdown("---")
    components.section_title("Consent and limits")
    consent_col, limits_col = st.columns([1, 1.35], gap="large")
    with consent_col:
        st.markdown(
            f"""
            <div class="mm-card">
              <div class="mm-label">Consent status</div>
              {_consent_badge(bool(user.get("consent_given")))}
              <div class="mm-small" style="margin-top:0.5rem">
                Recorded: {html.escape(str(user.get("consent_at") or "not recorded"))}<br>
                Profile created: {html.escape(str(user.get("created_at") or "unknown"))}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with limits_col:
        st.markdown(
            """
            <div class="mm-card-warm">
              <div class="mm-label">What this consent covers</div>
              <p style="margin-bottom:0.35rem">You agreed to use a local academic support tool that
              does not diagnose, treat, or provide emergency care.</p>
              <p style="margin-bottom:0">Consent is not a contract and does not remove your rights.
              You can stop using MindMate, export your data, or delete it at any time.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # Chat history preference
    # ------------------------------------------------------------------
    st.markdown("---")
    components.section_title("Conversation privacy")
    st.caption(
        "By default, the conversation lives only in this browser session. It disappears when the "
        "session ends and is never written to the database."
    )

    saved = bool(prefs.get("save_chat_history"))
    save_chat = st.toggle(
        "Save conversation transcripts locally",
        value=saved,
        key="save_chat_history_toggle",
        help="When on, new messages are written to the local database so they can reappear next time. "
        "You can clear them below.",
    )
    if save_chat != saved:
        update_preferences(user_id, save_chat_history=save_chat)
        st.toast(
            "Transcripts will be saved locally from now on."
            if save_chat
            else "Transcripts will no longer be saved. Already-saved messages remain until you clear them."
        )
        st.rerun()

    if saved:
        st.markdown(
            '<div class="mm-small">Saved transcripts are included in the JSON export and removed when '
            "you delete all data.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="mm-small">🔒 Transcript saving is off. Nothing from the chat is stored in the '
            "database.</div>",
            unsafe_allow_html=True,
        )

    chat_col, session_col = st.columns(2, gap="large")
    with chat_col:
        if st.button("Clear saved transcripts", use_container_width=True):
            clear_chat_history(user_id)
            st.toast("Saved transcripts deleted from this device.")
            st.rerun()
        st.caption("This does not affect your mood entries, habits, points or reflections.")
    with session_col:
        if st.button("Clear this browser session", use_container_width=True):
            clear_chat()
            st.session_state.pop("dialogue_state", None)
            st.session_state.pop("show_safety_steps", None)
            st.toast("Session conversation cleared. A new conversation will start next time.")
            st.rerun()
        st.caption("Useful on a shared computer. Database records are untouched.")

    # ------------------------------------------------------------------
    # Data overview and export
    # ------------------------------------------------------------------
    st.markdown("---")
    components.section_title("What is stored on this device")
    st.caption("These counts describe only this local profile. Nothing is sent to a server.")

    counts = [
        ("Mood check-ins", _count("mood_entries", user_id), "📈"),
        ("Active habits", int(query_one(
            "SELECT COUNT(*) AS c FROM habits WHERE user_id = ? AND is_active = 1", (user_id,)
        )["c"]), "🌱"),
        ("Habit completions", _count("habit_completions", user_id), "✓"),
        ("Daily reflections", _count("reflections", user_id), "📝"),
        ("Saved chat messages", _count("chat_messages", user_id), "💬"),
        ("Safety check records", _count("crisis_events", user_id), "🛟"),
    ]
    columns = st.columns(3)
    for index, (label, value, emoji) in enumerate(counts):
        with columns[index % 3]:
            st.markdown(
                components.stat_card(f"{emoji} {label}", str(value), "stored locally"),
                unsafe_allow_html=True,
            )

    export = export_user_data(user_id)
    export["app"] = {"name": APP_NAME, "version": VERSION, "exported_on": date.today().isoformat()}
    payload = json.dumps(export, indent=2, ensure_ascii=False)
    st.markdown("")
    st.download_button(
        "⬇️ Download my data as JSON",
        data=payload,
        file_name=f"mindmate-export-{date.today().isoformat()}.json",
        mime="application/json",
        use_container_width=False,
    )
    with st.expander("What the export contains"):
        st.markdown(
            "- Your profile and preferences\n"
            "- Mood check-ins and optional context\n"
            "- Habits and habit completions\n"
            "- Points ledger and badges\n"
            "- Daily summaries and reflections\n"
            "- Saved chat transcripts (only if you enabled saving)\n"
            "- Safety check events recorded by the app\n\n"
            "The export does not include the knowledge base or any other user's data."
        )

    # ------------------------------------------------------------------
    # Delete everything
    # ------------------------------------------------------------------
    st.markdown("---")
    components.section_title("Delete all my data")
    st.markdown(
        '<div class="mm-card-alert">'
        "<strong>This cannot be undone.</strong> The profile and every related record — mood entries, "
        "habits, completions, points, badges, summaries, reflections, saved transcripts and safety "
        "records — are deleted from the local database. The app will return to the welcome screen."
        "</div>",
        unsafe_allow_html=True,
    )

    with st.form("delete_all_form"):
        confirmation = st.text_input(
            'Type DELETE (in capitals) to confirm',
            placeholder="DELETE",
            autocomplete="off",
        )
        understood = st.checkbox("I understand that this permanently removes my MindMate data.")
        deleted = st.form_submit_button("Delete all my data", type="primary")
        if deleted:
            if confirmation.strip() != "DELETE":
                st.error('Type DELETE exactly, in capitals, to confirm.')
            elif not understood:
                st.error("Please tick the confirmation box as well.")
            else:
                delete_user_data(user_id)
                reset_all_session_state()
                st.toast("All local MindMate data for this profile has been deleted.")
                st.rerun()

    # ------------------------------------------------------------------
    # About
    # ------------------------------------------------------------------
    st.markdown("---")
    components.section_title("About this build")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown(
            f"""
            - **App:** {APP_NAME} v{VERSION}
            - **Type:** student academic project
            - **Reasoning:** explicit IF–THEN rules, forward chaining in Python
            - **Storage:** SQLite on this device
            - **External services:** none — no LLM or paid API is called
            - **Knowledge base:** {len(kb.rules)} rules, {len(kb.recommendations)} optional activities,
              {len(kb.concerns)} concern categories
            """
        )
    with right:
        st.markdown(
            """
            MindMate cannot diagnose or treat any condition, cannot assess risk, and is not an
            emergency service. If you are in immediate danger in India, call **112**.
            For mental health support, call **Tele-MANAS 14416** (24/7, free).
            """
        )
        st.caption("Helpline numbers can change. Verify them before relying on them.")

    st.markdown("---")
    components.section_title("Session")
    st.caption("Logging out ends this browser session. Your moods, habits and points stay saved on this device.")
    if st.button("Log out", key="settings_logout"):
        logout()
        st.query_params["view"] = "landing"
        st.rerun()
