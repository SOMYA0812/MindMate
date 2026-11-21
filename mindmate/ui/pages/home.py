"""Home dashboard: welcome, mood check-in, today's progress and quick actions."""

from __future__ import annotations

import html
from datetime import date, datetime
from typing import Any

import streamlit as st

from ...config import HABIT_TEMPLATES, QUOTES
from ...knowledge_base import KnowledgeBase
from ...services import habits, mood, rewards, summaries
from .. import components
from ..state import (
    NAV_CHAT,
    NAV_HABITS,
    NAV_REFLECTION,
    NAV_REWARDS,
    NAV_SUMMARY,
    go_to,
)


def _greeting() -> tuple[str, str]:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning", "🌸"
    if hour < 17:
        return "Good afternoon", "☀️"
    if hour < 21:
        return "Good evening", "🌙"
    return "A gentle late check-in", "✨"


def _quote() -> str:
    offset = int(st.session_state.get("quote_offset", 0))
    index = (date.today().toordinal() + offset) % len(QUOTES)
    return QUOTES[index]


def render(user_id: int, kb: KnowledgeBase, prefs: dict[str, Any]) -> None:
    name = prefs.get("preferred_name") or "Friend"
    today = datetime.now().strftime("%A, %d %B")
    greeting, emoji = _greeting()

    st.markdown(
        f"""
        <div class="mm-hero" style="margin-bottom:0.6rem">
          <div class="mm-eyebrow">{html.escape(today)}</div>
          <h1>{html.escape(greeting)}, {html.escape(str(name))} {emoji}</h1>
          <p>There is no perfect way to use this page. A check-in, a few lines, or one small
          habit is enough for today.</p>
          <div class="mm-quote" style="margin-top:1rem">{html.escape(_quote())}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    q1, q2 = st.columns([0.72, 0.28])
    with q1:
        st.caption("A quiet thought, changed each day. Nothing here needs to be earned.")
    with q2:
        if st.button("Another thought", key="home_new_quote", use_container_width=True):
            st.session_state["quote_offset"] = int(st.session_state.get("quote_offset", 0)) + 1
            st.rerun()

    left, right = st.columns([1.35, 1], gap="large")
    with left:
        with st.container(border=True):
            components.mood_selector(user_id, key_prefix="home")

    with right:
        progress = habits.daily_progress(user_id)
        with st.container(border=True):
            st.markdown("#### Today's small steps")
            if progress["total"]:
                st.progress(
                    progress["percent"] / 100,
                    text=f"{progress['completed']} of {progress['total']} habits recorded",
                )
            else:
                st.caption("No habits yet. You can add one whenever you want.")
            st.markdown(
                f'<div class="mm-small" style="margin-top:0.4rem">'
                f'⭐ <strong>{progress["points_today"]}</strong> points today · '
                f'🫶 <strong>{rewards.total_points(user_id)}</strong> total</div>',
                unsafe_allow_html=True,
            )
            if progress["remaining"]:
                names = ", ".join(h["name"] for h in progress["remaining"][:2])
                st.caption(f"Still open: {names}")
            elif progress["total"]:
                st.caption("Everything you planned is recorded. Rest is allowed.")
            if st.button("Open my habits", use_container_width=True, key="home_open_habits"):
                go_to(NAV_HABITS)
                st.rerun()

    st.markdown("")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("💬 Talk to MindMate", type="primary", use_container_width=True, key="home_talk"):
            go_to(NAV_CHAT)
            st.rerun()
    with c2:
        if st.button("📝 Write a reflection", use_container_width=True, key="home_reflect"):
            go_to(NAV_REFLECTION)
            st.rerun()
    with c3:
        if st.button("🏅 See my rewards", use_container_width=True, key="home_rewards"):
            go_to(NAV_REWARDS)
            st.rerun()

    st.markdown("---")
    components.section_title("This week at a glance", "A snapshot of what you recorded, not a score of how you are doing.")

    overview = summaries.weekly_overview(user_id)
    weekly = overview["mood"]
    metrics = st.columns(4)
    metrics[0].markdown(components.stat_card("Mood check-ins", f"{weekly['count']} / 7", "Self-reported snapshots"), unsafe_allow_html=True)
    metrics[1].markdown(components.stat_card("Habit entries", str(overview["habit_entries"]), f"{overview['days_with_habits']} day(s) with a habit"), unsafe_allow_html=True)
    metrics[2].markdown(components.stat_card("Points this week", str(overview["points"]), "For effort, never for mood"), unsafe_allow_html=True)
    metrics[3].markdown(components.stat_card("Gentle streak", f"{rewards.current_streak(user_id)} d", "No penalty for missed days"), unsafe_allow_html=True)

    st.markdown("")
    plant = rewards.plant_state(user_id)
    p1, p2 = st.columns([0.85, 1.15], gap="large")
    with p1:
        components.render_plant(plant)
    with p2:
        st.markdown("#### Your plant")
        st.write(
            "The plant grows from points earned by showing up — check-ins, habits and reflections. "
            "It never wilts when you miss a day. If you take a break, it waits for you."
        )
        st.markdown(
            f'<span class="mm-pill mint">{plant["name"]}</span>'
            f'<span class="mm-pill">{plant["total_points"]} points</span>',
            unsafe_allow_html=True,
        )
        if st.button("View badges and progress", key="home_plant_rewards"):
            go_to(NAV_REWARDS)
            st.rerun()

    if not habits.list_habits(user_id, active_only=False):
        st.markdown("---")
        with st.expander("Would you like a few starter habits?", expanded=True):
            st.write(
                "These are examples, not a prescription. Choose any you like — you can edit the name, "
                "target and days later."
            )
            options = [template["name"] for template in HABIT_TEMPLATES]
            chosen = st.multiselect(
                "Starter habits",
                options,
                default=options[:3],
                key="home_starter_habits",
            )
            if st.button("Add selected habits", type="primary", key="home_add_starter"):
                added = habits.add_starter_pack(user_id, chosen)
                if added:
                    st.toast(f"Added {added} habit(s). You can edit them in My Habits.")
                else:
                    st.toast("Those habits are already in your list.")
                st.rerun()

    hour = datetime.now().hour
    saved = summaries.get_saved_summary(user_id)
    if hour >= 19 and not saved:
        st.markdown("---")
        st.markdown(
            """
            <div class="mm-card-warm">
              <div class="mm-label">Close the day</div>
              <p>If you want, MindMate can gather what you recorded today into a short, non-judgemental summary.
              Nothing is required, and there is no catch-up list.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Create today's summary", type="primary", key="home_close_day"):
            summaries.generate_daily_summary(user_id)
            st.toast("Your summary is ready.")
            go_to(NAV_SUMMARY)
            st.rerun()

    if not mood.get_mood_entry(user_id):
        st.caption("You have not checked in today. That is okay — the option will be here when you want it.")
