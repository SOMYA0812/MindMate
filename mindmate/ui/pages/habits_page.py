"""Habit tracker page.

Every habit is fully editable: name, description, area, daily goal, schedule,
weekly target, points, archive and delete (with confirmation). Missing a day
never removes points or resets progress.
"""

from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st

from ...config import HABIT_CATEGORIES, HABIT_TEMPLATES, WEEKDAYS
from ...knowledge_base import KnowledgeBase
from ...services import habits, rewards
from .. import components


def _schedule_text(days: list[int] | None) -> str:
    values = sorted(int(day) for day in (days or []))
    if values == [0, 1, 2, 3, 4, 5, 6]:
        return "Every day"
    if values == [0, 1, 2, 3, 4]:
        return "Weekdays"
    if values == [5, 6]:
        return "Weekends"
    lookup = {item["value"]: item["label"] for item in WEEKDAYS}
    return ", ".join(lookup.get(day, str(day)) for day in values) or "No days chosen"


def _toggle_habit(user_id: int, habit_id: int) -> None:
    checked = bool(st.session_state.get(f"habit_done_{habit_id}"))
    try:
        if checked:
            result = habits.mark_complete(user_id, habit_id)
            if result["points_awarded"]:
                st.session_state["habit_flash"] = (
                    f"Recorded. +{result['points_awarded']} points for the effort — not for the outcome."
                )
            else:
                st.session_state["habit_flash"] = "Already recorded for today. One entry a day is enough."
        else:
            habits.unmark_complete(user_id, habit_id)
            st.session_state["habit_flash"] = "Unmarked. Points already earned are not taken away."
    except ValueError as exc:
        st.session_state["habit_flash"] = str(exc)


def _day_options() -> list[int]:
    return [item["value"] for item in WEEKDAYS]


def _day_label(value: int) -> str:
    for item in WEEKDAYS:
        if item["value"] == value:
            return item["label"]
    return str(value)


def _habit_row(user_id: int, habit: dict[str, Any], done: bool, scheduled: bool = True) -> None:
    habit_id = int(habit["id"])
    cat = HABIT_CATEGORIES.get(habit["category"], HABIT_CATEGORIES["wellbeing"])
    streak = habits.habit_streak(user_id, habit_id)
    cols = st.columns([0.07, 0.5, 0.25, 0.18])
    with cols[0]:
        st.checkbox(
            f"Done: {habit['name']}",
            value=done,
            key=f"habit_done_{habit_id}",
            on_change=_toggle_habit,
            args=(user_id, habit_id),
            label_visibility="collapsed",
        )
    with cols[1]:
        st.markdown(f"**{html.escape(habit['name'])}**")
        if habit.get("description"):
            st.caption(html.escape(habit["description"]))
        st.caption(
            f"{cat['emoji']} {cat['label']} · {habit['target_value']:g} {html.escape(habit['unit'])}"
            + ("" if scheduled else " · not scheduled today")
        )
    with cols[2]:
        st.markdown(
            f'<span class="mm-pill peach">🗓 {html.escape(_schedule_text(habit.get("schedule_days")))}</span>',
            unsafe_allow_html=True,
        )
    with cols[3]:
        st.caption(f"⭐ {habit['points']} pts · 🔥 {streak} d")


def render(user_id: int, kb: KnowledgeBase, prefs: dict[str, Any]) -> None:
    components.page_header(
        "🌱",
        "My Habits",
        "Build a routine that fits your real life. Every habit is editable, and missing a day never removes points.",
    )

    flash = st.session_state.pop("habit_flash", None)
    if flash:
        st.toast(flash)

    progress = habits.daily_progress(user_id)
    metrics = st.columns(4)
    metrics[0].markdown(
        components.stat_card("Today", f"{progress['completed']} / {progress['total']}", "Habits scheduled today"),
        unsafe_allow_html=True,
    )
    metrics[1].markdown(components.stat_card("Points today", str(progress["points_today"]), "Effort only"), unsafe_allow_html=True)
    metrics[2].markdown(components.stat_card("Gentle streak", f"{rewards.current_streak(user_id)} d", "No penalty for breaks"), unsafe_allow_html=True)
    metrics[3].markdown(components.stat_card("Active habits", str(len(habits.list_habits(user_id))), "Your own choices"), unsafe_allow_html=True)

    st.markdown(
        '<div class="mm-card-soft">Points are awarded once when you record a habit. '
        "Missing a day does not subtract anything, and unmarking a habit keeps points already earned.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("")
    with st.expander("➕ Add a habit", expanded=progress["total"] == 0):
        _add_habit_form(user_id, key_prefix="add")

    all_habits = habits.list_habits(user_id, active_only=False)
    if not all_habits:
        components.empty_state(
            "No habits yet",
            "Add one that feels almost too easy, or choose a starter habit below.",
            emoji="🌰",
        )
        _starter_pack(user_id)
        return

    st.markdown("---")
    components.section_title("Today", "Tick what happened. A partial version still counts.")
    active = habits.list_habits(user_id)
    done_ids = habits.completion_ids(user_id)

    if not active:
        st.info("All your habits are archived. You can restore one below, or add a new one.")
    elif not progress["scheduled"]:
        st.info("Nothing is scheduled for today. You can rest, or use an off-schedule habit below.")
    for habit in progress["scheduled"]:
        _habit_row(user_id, habit, int(habit["id"]) in done_ids)

    if progress["not_scheduled"]:
        with st.expander("Not scheduled today · optional", expanded=False):
            st.caption(
                "These are off today. Ticking one is a bonus and does not change whether today's plan "
                "looks complete."
            )
            for habit in progress["not_scheduled"]:
                _habit_row(user_id, habit, int(habit["id"]) in done_ids, scheduled=False)

    st.markdown("")
    grid = habits.weekly_grid(user_id, days=7)
    left, right = st.columns([1.25, 1], gap="large")
    with left:
        components.section_title("Last seven days")
        components.habit_heatmap(grid)
    with right:
        components.section_title("Weekly targets")
        weekly = habits.weekly_progress(user_id)
        for item in weekly:
            habit = item["habit"]
            st.markdown(f"**{html.escape(habit['name'])}**")
            st.progress(
                min(1.0, item["percent"] / 100),
                text=f"{item['days_completed']} of {item['target_days']} target days",
            )
        st.caption("Targets are a direction, not a contract. You can change them any time.")

    st.markdown("---")
    with st.expander("✏️ Manage habits", expanded=False):
        _manage_habits(user_id, all_habits)

    with st.expander("🗂 Habit history (last 28 days)"):
        history = habits.habit_history(user_id, days=28)
        if history:
            frame = pd.DataFrame(history)[["completed_on", "name", "category", "value", "note"]]
            frame.columns = ["Date", "Habit", "Category", "Value", "Note"]
            st.dataframe(frame, hide_index=True, use_container_width=True)
        else:
            st.caption("Nothing recorded yet. The history will appear after your first habit.")

    st.caption(
        "Points are awarded once per habit per day. Unmarking a habit does not remove points already earned. "
        "There is no penalty for missed days."
    )


def _schedule_picker(habit: dict[str, Any] | None, key: str) -> list[int]:
    default = list(habit.get("schedule_days") or _day_options()) if habit else _day_options()
    return st.multiselect(
        "Which days?",
        options=_day_options(),
        default=[day for day in default if day in _day_options()],
        format_func=_day_label,
        key=key,
        help="Today's page only counts habits scheduled for that weekday. Off days are never penalised.",
    )


def _add_habit_form(user_id: int, key_prefix: str) -> None:
    with st.form(f"{key_prefix}_habit_form"):
        st.markdown("#### Create your own habit")
        st.caption("Nothing here is prescribed. Make it small enough to be possible on a difficult day.")
        name = st.text_input("Habit name", placeholder="e.g. Take a 10-minute walk", max_chars=100)
        description = st.text_area(
            "Description (optional)",
            placeholder="Why it matters, or the smallest version that still counts.",
            max_chars=300,
            height=70,
        )
        c1, c2, c3 = st.columns(3)
        category = c1.selectbox(
            "Area",
            options=list(HABIT_CATEGORIES),
            format_func=lambda key: f"{HABIT_CATEGORIES[key]['emoji']} {HABIT_CATEGORIES[key]['label']}",
        )
        target_value = c2.number_input("Daily goal", min_value=0.0, max_value=1000.0, value=10.0, step=1.0)
        unit = c3.text_input("Unit", value="minutes", max_chars=30)
        schedule_days = _schedule_picker(None, f"{key_prefix}_days")
        c4, c5 = st.columns(2)
        days = c4.slider("Target days per week", 1, 7, 5)
        points = c5.slider("Points per completion", 0, 25, 10, help="Effort points. Keep it kind.")
        submitted = st.form_submit_button("Add habit", type="primary")
    if submitted:
        if not name.strip():
            st.error("Give the habit a name first.")
        else:
            habits.create_habit(
                user_id,
                name=name,
                description=description,
                category=category,
                target_value=target_value,
                unit=unit or "time",
                points=points,
                target_days_per_week=days,
                schedule_days=schedule_days,
            )
            st.toast("Habit added. You can edit it whenever you like.")
            st.rerun()

    with st.expander("Or start from an example"):
        options = [template["name"] for template in HABIT_TEMPLATES]
        chosen = st.multiselect("Example habits", options, key=f"{key_prefix}_template_choice")
        if st.button("Add chosen examples", key=f"{key_prefix}_template_add"):
            if not chosen:
                st.toast("Choose at least one example.")
            else:
                added = habits.add_starter_pack(user_id, chosen)
                st.toast(f"Added {added} habit(s).")
                st.rerun()


def _starter_pack(user_id: int) -> None:
    st.markdown("#### Or choose from a few examples")
    options = [template["name"] for template in HABIT_TEMPLATES]
    chosen = st.multiselect("Starter habits", options, default=options[:3], key="habits_starter_choice")
    if st.button("Add selected habits", type="primary", key="habits_starter_add"):
        added = habits.add_starter_pack(user_id, chosen)
        if added:
            st.toast(f"Added {added} habit(s).")
        else:
            st.toast("Those are already in your list.")
        st.rerun()


def _manage_habits(user_id: int, all_habits: list[dict[str, Any]]) -> None:
    labels = {int(h["id"]): h["name"] for h in all_habits}
    selected = st.selectbox(
        "Choose a habit",
        options=list(labels),
        format_func=lambda hid: labels.get(hid, str(hid)),
        key="manage_habit_select",
    )
    habit = next((h for h in all_habits if int(h["id"]) == selected), None)
    if not habit:
        return
    habit_id = int(habit["id"])
    with st.form(f"edit_habit_{habit_id}"):
        name = st.text_input("Name", value=habit["name"], max_chars=100)
        description = st.text_area(
            "Description (optional)",
            value=habit.get("description") or "",
            max_chars=300,
            height=70,
        )
        c1, c2, c3 = st.columns(3)
        category = c1.selectbox(
            "Area",
            options=list(HABIT_CATEGORIES),
            index=list(HABIT_CATEGORIES).index(habit["category"]) if habit["category"] in HABIT_CATEGORIES else 0,
            format_func=lambda key: f"{HABIT_CATEGORIES[key]['emoji']} {HABIT_CATEGORIES[key]['label']}",
        )
        target_value = c2.number_input("Daily goal", 0.0, 1000.0, float(habit["target_value"]), 1.0)
        unit = c3.text_input("Unit", value=habit["unit"], max_chars=30)
        schedule_days = _schedule_picker(habit, f"edit_days_{habit_id}")
        c4, c5 = st.columns(2)
        days = c4.slider("Target days per week", 1, 7, int(habit["target_days_per_week"]))
        points = c5.slider("Points per completion", 0, 25, int(habit["points"]))
        if st.form_submit_button("Save changes", type="primary"):
            if not name.strip():
                st.error("Keep a name for this habit.")
            else:
                habits.update_habit(
                    user_id,
                    habit_id,
                    name=name,
                    description=description,
                    category=category,
                    schedule_days=schedule_days,
                    target_value=target_value,
                    unit=unit,
                    points=points,
                    target_days_per_week=days,
                )
                st.toast("Habit updated. Past completions and points are unchanged.")
                st.rerun()

    b1, b2 = st.columns(2)
    with b1:
        if habit["is_active"]:
            if st.button("Archive habit", key=f"archive_{habit_id}"):
                habits.archive_habit(user_id, habit_id)
                st.toast("Habit archived. You can restore it later.")
                st.rerun()
        else:
            if st.button("Restore habit", key=f"restore_{habit_id}"):
                habits.restore_habit(user_id, habit_id)
                st.toast("Habit restored.")
                st.rerun()
    with b2:
        confirm = st.checkbox("I understand deleting removes its history", key=f"confirm_delete_{habit_id}")
        if st.button("Delete habit", key=f"delete_{habit_id}", disabled=not confirm):
            habits.delete_habit(user_id, habit_id)
            st.toast("Habit deleted. Points already earned stay in your total.")
            st.rerun()
