"""Daily reflection page."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from ...knowledge_base import KnowledgeBase
from ...services import reflection
from .. import components


def render(user_id: int, kb: KnowledgeBase, prefs: dict[str, Any]) -> None:
    components.page_header(
        "📝",
        "Daily Reflection",
        "A few optional lines to close the loop on the day. There are no right answers, and no one else sees this.",
    )

    existing = reflection.get_reflection(user_id)
    prompt = reflection.PROMPTS[date.today().toordinal() % len(reflection.PROMPTS)]

    st.markdown(
        f'<div class="mm-card-soft"><div class="mm-label">A prompt, if useful</div>'
        f'<div class="mm-quote">{prompt}</div></div>',
        unsafe_allow_html=True,
    )

    with st.form("reflection_form"):
        went_well = st.text_area(
            "One thing I got through or noticed today",
            value=(existing or {}).get("went_well") or "",
            height=100,
            max_chars=1000,
        )
        grateful_for = st.text_area(
            "Something small I am glad about (optional)",
            value=(existing or {}).get("grateful_for") or "",
            height=90,
            max_chars=1000,
        )
        tomorrow_step = st.text_area(
            "A gentle option for tomorrow (optional)",
            value=(existing or {}).get("tomorrow_step") or "",
            height=90,
            max_chars=1000,
        )
        submitted = st.form_submit_button("Save reflection", type="primary")

    if submitted:
        try:
            result = reflection.save_reflection(
                user_id,
                went_well=went_well,
                grateful_for=grateful_for,
                tomorrow_step=tomorrow_step,
            )
            if result["points_awarded"]:
                st.toast(f"Reflection saved. +{result['points_awarded']} points for taking the time.")
            else:
                st.toast("Reflection updated.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    st.caption(
        "Reflection points are for writing something — never for the content, and never for a particular mood."
    )

    st.markdown("---")
    components.section_title("Recent reflections", "Last 14 days.")
    recent = reflection.recent_reflections(user_id, days=14)
    if not recent:
        components.empty_state(
            "Nothing here yet",
            "You can leave this page and come back whenever you want. Reflection is optional.",
            emoji="🕯️",
        )
        return

    for entry in recent:
        with st.expander(f"{entry['reflection_date']}"):
            if entry.get("went_well"):
                st.markdown("**Got through / noticed**")
                st.write(entry["went_well"])
            if entry.get("grateful_for"):
                st.markdown("**Glad about**")
                st.write(entry["grateful_for"])
            if entry.get("tomorrow_step"):
                st.markdown("**Gentle option for tomorrow**")
                st.write(entry["tomorrow_step"])

    if existing:
        st.caption("You can edit today's reflection above; editing does not award extra points.")
