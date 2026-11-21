"""End-of-day summaries.

A summary is descriptive, not evaluative. It lists what happened, names the
efforts that were made, and offers at most three gentle options for tomorrow.
It never says that the user 'should' have done more, never mentions a broken
streak, and never treats mood as a clinical outcome.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from ..database import get_conn, query_all, query_one, today_iso, utc_now
from . import habits, mood, reflection, rewards


def generate_daily_summary(user_id: int, target_date: str | None = None,
                           persist: bool = True) -> dict[str, Any]:
    day = target_date or today_iso()
    mood_entry = mood.get_mood_entry(user_id, day)
    reflection_entry = reflection.get_reflection(user_id, day)

    active_habits = habits.list_habits(user_id, active_only=True)
    completed_rows = habits.completions_for_date(user_id, day)
    completed_names = [row["name"] for row in completed_rows]
    habits_total = len(active_habits)
    habits_completed = len(completed_rows)
    points = rewards.points_today(user_id, day)
    badge_rows = query_all(
        "SELECT badge_key FROM badges WHERE user_id = ? AND awarded_on = ?", (user_id, day)
    )
    badges_earned = [
        rewards.BADGES.get(row["badge_key"], {"name": row["badge_key"], "emoji": "✨"})
        for row in badge_rows
    ]

    efforts: list[str] = []
    if mood_entry:
        efforts.append(f"Checked in with your mood ({mood.mood_label(mood_entry['mood_score'])['label'].lower()}).")
    if completed_names:
        efforts.append("Completed: " + ", ".join(completed_names) + ".")
    if reflection_entry:
        efforts.append("Wrote a reflection.")
    if not efforts:
        efforts.append(
            "You opened MindMate today. On a low-capacity day, showing up at all is still an effort."
        )

    suggestions: list[str] = []
    if mood_entry and int(mood_entry["mood_score"]) <= 2:
        suggestions.append(
            "Tomorrow, keep the bar very low: water, food, and one point of contact. Rest is allowed."
        )
    remaining = [h for h in active_habits if h["name"] not in completed_names]
    for habit in remaining[:2]:
        suggestions.append(
            f"If it feels possible, '{habit['name'].lower()}' could be a small option tomorrow. "
            "A partial version counts."
        )
    if mood_entry and mood_entry.get("sleep_hours") is not None and float(mood_entry["sleep_hours"]) < 6:
        suggestions.append(
            "A slightly earlier wind-down might be worth trying, without aiming for a perfect sleep."
        )
    if not active_habits:
        suggestions.append(
            "You could add one habit that feels almost too easy. It is an offer, not an assignment."
        )
    if not suggestions:
        suggestions.append("Keep tomorrow at a similar size. There is nothing to catch up on.")

    suggestions.append("No catch-up is required for today. Missing something does not erase what you did.")

    summary = {
        "date": day,
        "mood_score": int(mood_entry["mood_score"]) if mood_entry else None,
        "mood_label": mood.mood_label(int(mood_entry["mood_score"]))["label"] if mood_entry else "Not recorded",
        "habits_completed": habits_completed,
        "habits_total": habits_total,
        "points_earned": points,
        "efforts": efforts,
        "suggestions": suggestions[:4],
        "badges": badges_earned,
        "motivational_message": rewards.daily_message(date.fromisoformat(day)),
        "caveat": (
            "This summary describes actions you recorded. It is not a clinical assessment, and a day with fewer "
            "actions is not a worse day."
        ),
    }

    if persist:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO daily_summaries (user_id, summary_date, mood_score, habits_completed, habits_total, "
                "points_earned, efforts_json, suggestions_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (user_id, summary_date) DO UPDATE SET "
                "mood_score = excluded.mood_score, habits_completed = excluded.habits_completed, "
                "habits_total = excluded.habits_total, points_earned = excluded.points_earned, "
                "efforts_json = excluded.efforts_json, suggestions_json = excluded.suggestions_json",
                (
                    user_id, day, summary["mood_score"], habits_completed, habits_total, points,
                    json.dumps(efforts), json.dumps(suggestions[:4]), utc_now(),
                ),
            )
    return summary


def get_saved_summary(user_id: int, target_date: str | None = None) -> dict[str, Any] | None:
    day = target_date or today_iso()
    row = query_one(
        "SELECT * FROM daily_summaries WHERE user_id = ? AND summary_date = ?", (user_id, day)
    )
    if not row:
        return None
    try:
        row["efforts"] = json.loads(row.pop("efforts_json") or "[]")
        row["suggestions"] = json.loads(row.pop("suggestions_json") or "[]")
    except json.JSONDecodeError:
        row["efforts"], row["suggestions"] = [], []
    return row


def list_summaries(user_id: int, days: int = 14) -> list[dict[str, Any]]:
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    return query_all(
        "SELECT * FROM daily_summaries WHERE user_id = ? AND summary_date >= ? "
        "ORDER BY summary_date DESC",
        (user_id, start),
    )


def summary_markdown(summary: dict[str, Any]) -> str:
    lines = [f"### {summary['date']}", ""]
    lines.append(f"**Mood check-in:** {summary.get('mood_label', 'Not recorded')}")
    lines.append(
        f"**Habits:** {summary.get('habits_completed', 0)} of {summary.get('habits_total', 0)} recorded as complete"
    )
    lines.append(f"**Points earned today:** {summary.get('points_earned', 0)}")
    lines.append("")
    lines.append("**Positive efforts**")
    for effort in summary.get("efforts", []):
        lines.append(f"- {effort}")
    if summary.get("badges"):
        badge_text = ", ".join(f"{b.get('emoji', '✨')} {b.get('name', '')}" for b in summary["badges"])
        lines.append(f"\n**Badges:** {badge_text}")
    lines.append("")
    lines.append("**Gentle options for tomorrow**")
    for suggestion in summary.get("suggestions", []):
        lines.append(f"- {suggestion}")
    lines.append("")
    lines.append(f"_{summary.get('motivational_message', '')}_")
    lines.append("")
    lines.append(f"*{summary.get('caveat', '')}*")
    return "\n".join(lines)


def weekly_overview(user_id: int, reference_date: date | None = None) -> dict[str, Any]:
    ref = reference_date or date.today()
    start = ref - timedelta(days=6)
    mood_summary = mood.weekly_summary(user_id, ref)
    completions = habits.completion_range(user_id, days=7)
    days_active = len({row["completed_on"] for row in completions})
    distinct_habits = len({row["habit_id"] for row in completions})
    points = sum(item["points"] for item in rewards.weekly_points(user_id, 7))
    return {
        "mood": mood_summary,
        "habit_entries": len(completions),
        "days_with_habits": days_active,
        "distinct_habits": distinct_habits,
        "points": points,
        "start": start.isoformat(),
        "end": ref.isoformat(),
    }
