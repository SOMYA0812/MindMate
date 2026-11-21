"""Rewards dashboard: points, badges, plant growth and weekly chart."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ...knowledge_base import KnowledgeBase
from ...services import rewards
from .. import components


_EVENT_LABELS = {
    "mood_checkin": "Mood check-in",
    "habit": "Habit completion",
    "reflection": "Daily reflection",
}


def render(user_id: int, kb: KnowledgeBase, prefs: dict[str, Any]) -> None:
    components.page_header(
        "🏅",
        "My Rewards",
        "Points recognise effort, not mood. The plant grows from showing up, and it never wilts when you miss a day.",
    )

    plant = rewards.plant_state(user_id)
    badges = rewards.get_badges(user_id)
    stats = st.columns(4)
    stats[0].markdown(components.stat_card("Points today", str(rewards.points_today(user_id)), "For actions, not scores"), unsafe_allow_html=True)
    stats[1].markdown(components.stat_card("Total points", str(plant["total_points"]), "Accumulated effort"), unsafe_allow_html=True)
    stats[2].markdown(components.stat_card("Badges", str(len(badges)), f"of {len(rewards.BADGES)} available"), unsafe_allow_html=True)
    stats[3].markdown(components.stat_card("Gentle streak", f"{rewards.current_streak(user_id)} d", "Missing a day costs nothing"), unsafe_allow_html=True)

    st.markdown("")
    left, right = st.columns([0.9, 1.2], gap="large")
    with left:
        components.render_plant(plant)
    with right:
        components.section_title("Points this week")
        components.points_bar_chart(rewards.weekly_points(user_id, 7))
        st.markdown(
            f'<div class="mm-card-soft"><div class="mm-label">Today\'s reminder</div>'
            f'<div>{rewards.daily_message()}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    components.section_title("Badges", "Effort, consistency and returning after a break — never a mood outcome.")
    components.render_badges(rewards.all_badge_catalogue(user_id), columns=3)

    st.markdown("---")
    left2, right2 = st.columns([1, 1], gap="large")
    with left2:
        components.section_title("Where this week's points came from")
        breakdown = rewards.points_breakdown(user_id, days=7)
        if breakdown:
            frame = pd.DataFrame(breakdown)
            frame["event_type"] = frame["event_type"].map(lambda key: _EVENT_LABELS.get(key, key))
            frame.columns = ["Activity", "Points"]
            st.dataframe(frame, hide_index=True, use_container_width=True)
        else:
            st.caption("No points this week yet. The first check-in is worth 5.")
    with right2:
        components.section_title("How points work")
        st.markdown(
            """
            | Action | Points |
            |---|---:|
            | Daily mood check-in | 5 |
            | Daily reflection | 5 |
            | Habit completion | 5–10 (your choice) |
            | Reading / walking / journalling habit | 10 |
            | Connecting with someone habit | 10 |
            """
        )
        st.caption(
            "Mood scores never add or remove points. There is no penalty for a difficult day, a missed habit, "
            "or a long break. Points are a record of effort, not a measure of recovery."
        )

    with st.expander("What the plant stages mean"):
        st.markdown(
            "The plant has seven stages, from seed to orchard. It grows from total points. "
            "It does not shrink, and there is no deadline. If you take a break, it waits."
        )
        for stage in rewards.PLANT_STAGES:
            st.markdown(f"- **{stage['emoji']} {stage['name']}** at {stage['at']} points — {stage['note']}")
