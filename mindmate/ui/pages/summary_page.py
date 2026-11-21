"""End-of-day summary page."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from ...knowledge_base import KnowledgeBase
from ...services import summaries
from .. import components


def render(user_id: int, kb: KnowledgeBase, prefs: dict[str, Any]) -> None:
    components.page_header(
        "🌙",
        "Daily Summary",
        "A short, non-judgemental record of what you did today and a few gentle options for tomorrow. "
        "There is no catch-up list.",
    )

    summary = summaries.get_saved_summary(user_id)
    if summary is None:
        st.markdown(
            """
            <div class="mm-card-warm">
              <div class="mm-label">Ready when you are</div>
              <p>MindMate will gather today's check-in, completed habits, points and reflection into one summary.
              You can create it now, or come back later.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Create today's summary", type="primary", key="summary_create"):
            summaries.generate_daily_summary(user_id)
            st.toast("Today's summary is ready.")
            st.rerun()
    else:
        _render_summary(summary)
        if st.button("Refresh today's summary", key="summary_refresh"):
            summaries.generate_daily_summary(user_id)
            st.toast("Summary refreshed.")
            st.rerun()

    st.markdown("---")
    components.section_title("This week", "Seven days ending today.")
    overview = summaries.weekly_overview(user_id)
    weekly = overview["mood"]
    metrics = st.columns(4)
    metrics[0].markdown(components.stat_card("Mood check-ins", str(weekly["count"]), "Self-reported"), unsafe_allow_html=True)
    metrics[1].markdown(components.stat_card("Habit entries", str(overview["habit_entries"]), "Across all habits"), unsafe_allow_html=True)
    metrics[2].markdown(components.stat_card("Points", str(overview["points"]), "Effort, not mood"), unsafe_allow_html=True)
    metrics[3].markdown(components.stat_card("Days with a habit", str(overview["days_with_habits"]), "Out of 7"), unsafe_allow_html=True)
    st.markdown(
        f'<div class="mm-card-soft" style="margin-top:0.6rem">{weekly["text"]}'
        f'<div class="mm-small" style="margin-top:0.35rem">{weekly["caveat"]}</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    components.section_title("Earlier summaries", "Last 14 days.")
    earlier = [s for s in summaries.list_summaries(user_id, days=14) if s["summary_date"] != date.today().isoformat()]
    if not earlier:
        st.caption("No earlier summaries yet.")
    for saved in earlier:
        with st.expander(saved["summary_date"]):
            st.markdown(
                f"**Mood:** {saved.get('mood_score') or 'not recorded'} · "
                f"**Habits:** {saved['habits_completed']}/{saved['habits_total']} · "
                f"**Points:** {saved['points_earned']}"
            )
            for suggestion in saved.get("suggestions", []):
                st.markdown(f"- {suggestion}")


def _render_summary(summary: dict[str, Any]) -> None:
    st.markdown(f"## {summary['date']}")
    metrics = st.columns(4)
    metrics[0].markdown(components.stat_card("Mood check-in", summary.get("mood_label", "Not recorded"), "Self-reported"), unsafe_allow_html=True)
    metrics[1].markdown(
        components.stat_card(
            "Habits",
            f"{summary.get('habits_completed', 0)} / {summary.get('habits_total', 0)}",
            "Recorded today",
        ),
        unsafe_allow_html=True,
    )
    metrics[2].markdown(components.stat_card("Points earned", str(summary.get("points_earned", 0)), "For effort"), unsafe_allow_html=True)
    metrics[3].markdown(
        components.stat_card("Badges", str(len(summary.get("badges", []))), "Earned today"),
        unsafe_allow_html=True,
    )

    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("#### Positive efforts")
        st.markdown(
            '<div class="mm-card">'
            + "".join(f"<p>✓ {effort}</p>" for effort in summary.get("efforts", []))
            + "</div>",
            unsafe_allow_html=True,
        )
        if summary.get("badges"):
            pills = "".join(
                f'<span class="mm-pill peach">{b.get("emoji", "✨")} {b.get("name", "")}</span>'
                for b in summary["badges"]
            )
            st.markdown(pills, unsafe_allow_html=True)
    with right:
        st.markdown("#### Gentle options for tomorrow")
        st.markdown(
            '<div class="mm-card-warm">'
            + "".join(f"<p>{suggestion}</p>" for suggestion in summary.get("suggestions", []))
            + "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f'<div class="mm-quote">{summary.get("motivational_message", "")}</div>', unsafe_allow_html=True)

    st.caption(summary.get("caveat", ""))
