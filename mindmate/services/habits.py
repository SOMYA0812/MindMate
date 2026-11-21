"""Healthy habit management.

Habits are user-owned and fully editable. The default starter pack is only an
offer. Completion is recorded once per habit per day, and points are awarded
idempotently by the rewards service.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from ..config import HABIT_CATEGORIES, HABIT_TEMPLATES
from ..database import get_conn, query_all, query_one, today_iso, utc_now
from . import rewards


ALL_DAYS = [0, 1, 2, 3, 4, 5, 6]


def _normalise_schedule(days: list[int] | tuple[int, ...] | None) -> list[int]:
    if not days:
        return list(ALL_DAYS)
    clean = sorted({int(day) for day in days if 0 <= int(day) <= 6})
    return clean or list(ALL_DAYS)


def _encode_schedule(days: list[int] | tuple[int, ...] | None) -> str:
    return json.dumps(_normalise_schedule(days))


def _decode_schedule(value: Any) -> list[int]:
    if isinstance(value, (list, tuple)):
        return _normalise_schedule(list(value))
    try:
        parsed = json.loads(value or "[]")
        return _normalise_schedule(parsed if isinstance(parsed, list) else None)
    except (TypeError, ValueError, json.JSONDecodeError):
        return list(ALL_DAYS)


def _hydrate(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if not isinstance(row, dict):
        row = dict(row)
    row["schedule_days"] = _decode_schedule(row.get("schedule_days"))
    row["description"] = row.get("description") or ""
    return row


def create_habit(
    user_id: int,
    name: str,
    category: str = "wellbeing",
    target_value: float = 1,
    unit: str = "time",
    points: int = 10,
    target_days_per_week: int = 7,
    description: str = "",
    schedule_days: list[int] | tuple[int, ...] | None = None,
) -> int:
    clean_name = (name or "").strip()[:100]
    if not clean_name:
        raise ValueError("A habit needs a name.")
    if category not in HABIT_CATEGORIES:
        category = "wellbeing"
    points = max(0, min(int(points), 50))
    target_days_per_week = max(1, min(int(target_days_per_week), 7))
    target_value = max(0.0, float(target_value or 1))
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO habits (user_id, name, description, category, schedule_days, "
            "target_value, unit, points, target_days_per_week, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
            (user_id, clean_name, (description or "").strip()[:300], category,
             _encode_schedule(schedule_days), target_value, unit.strip()[:30] or "time",
             points, target_days_per_week, utc_now()),
        )
        return int(cur.lastrowid)


def get_habit(user_id: int, habit_id: int) -> dict[str, Any] | None:
    return _hydrate(
        query_one("SELECT * FROM habits WHERE id = ? AND user_id = ?", (habit_id, user_id))
    )


def list_habits(user_id: int, active_only: bool = True) -> list[dict[str, Any]]:
    sql = "SELECT * FROM habits WHERE user_id = ?"
    params: list[Any] = [user_id]
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY is_active DESC, created_at, id"
    return [_hydrate(row) for row in query_all(sql, tuple(params))]  # type: ignore[misc]


def is_scheduled(habit: dict[str, Any], on_date: date | None = None) -> bool:
    day = on_date or date.today()
    schedule = habit.get("schedule_days", ALL_DAYS)
    if isinstance(schedule, str):
        schedule = _decode_schedule(schedule)
    return day.weekday() in (schedule or ALL_DAYS)


def update_habit(user_id: int, habit_id: int, **fields: Any) -> None:
    allowed = {
        "name", "description", "category", "schedule_days", "target_value", "unit",
        "points", "target_days_per_week", "is_active",
    }
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return
    if "name" in clean:
        clean["name"] = str(clean["name"]).strip()[:100]
        if not clean["name"]:
            raise ValueError("A habit needs a name.")
    if "description" in clean:
        clean["description"] = str(clean["description"] or "").strip()[:300]
    if "category" in clean and clean["category"] not in HABIT_CATEGORIES:
        clean["category"] = "wellbeing"
    if "schedule_days" in clean:
        clean["schedule_days"] = _encode_schedule(clean["schedule_days"])
    if "points" in clean:
        clean["points"] = max(0, min(int(clean["points"]), 50))
    if "target_days_per_week" in clean:
        clean["target_days_per_week"] = max(1, min(int(clean["target_days_per_week"]), 7))
    if "is_active" in clean:
        clean["is_active"] = int(bool(clean["is_active"]))
    assignments = ", ".join(f"{key} = ?" for key in clean)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE habits SET {assignments} WHERE id = ? AND user_id = ?",
            (*clean.values(), habit_id, user_id),
        )


def archive_habit(user_id: int, habit_id: int) -> None:
    update_habit(user_id, habit_id, is_active=0)


def restore_habit(user_id: int, habit_id: int) -> None:
    update_habit(user_id, habit_id, is_active=1)


def delete_habit(user_id: int, habit_id: int) -> None:
    """Delete a habit and its completions. Earned points are never clawed back."""
    with get_conn() as conn:
        conn.execute("DELETE FROM habits WHERE id = ? AND user_id = ?", (habit_id, user_id))


def add_starter_pack(user_id: int, keys: list[str] | None = None) -> int:
    """Add selected starter habits, skipping duplicates by name."""
    existing = {h["name"].lower() for h in list_habits(user_id, active_only=False)}
    created = 0
    for template in HABIT_TEMPLATES:
        if keys and template["name"] not in keys:
            continue
        if template["name"].lower() in existing:
            continue
        create_habit(
            user_id,
            name=template["name"],
            category=template["category"],
            target_value=template["target_value"],
            unit=template["unit"],
            points=template["points"],
            target_days_per_week=template["target_days_per_week"],
        )
        created += 1
    return created


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------

def mark_complete(user_id: int, habit_id: int, value: float | None = None,
                  note: str | None = None, on_date: str | None = None) -> dict[str, Any]:
    habit = get_habit(user_id, habit_id)
    if habit is None:
        raise ValueError("Habit not found.")
    day = on_date or today_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO habit_completions (habit_id, user_id, completed_on, value, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (habit_id, completed_on) DO NOTHING",
            (habit_id, user_id, day, value, (note or "")[:500] or None, utc_now()),
        )
        already = cur.rowcount == 0
    awarded = 0
    if not already:
        awarded = rewards.award_points(
            user_id, "habit", str(habit_id), int(habit["points"]), on_date=day
        )
    return {
        "completed": True,
        "already_completed": already,
        "points_awarded": awarded,
        "habit": habit,
        "date": day,
    }


def unmark_complete(user_id: int, habit_id: int, on_date: str | None = None) -> None:
    """Remove today's completion. Points already earned stay earned."""
    day = on_date or today_iso()
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM habit_completions WHERE habit_id = ? AND user_id = ? AND completed_on = ?",
            (habit_id, user_id, day),
        )


def is_completed(user_id: int, habit_id: int, on_date: str | None = None) -> bool:
    day = on_date or today_iso()
    row = query_one(
        "SELECT id FROM habit_completions WHERE habit_id = ? AND user_id = ? AND completed_on = ?",
        (habit_id, user_id, day),
    )
    return row is not None


def completions_for_date(user_id: int, on_date: str | None = None) -> list[dict[str, Any]]:
    day = on_date or today_iso()
    return query_all(
        "SELECT c.*, h.name, h.category, h.points FROM habit_completions c "
        "JOIN habits h ON h.id = c.habit_id "
        "WHERE c.user_id = ? AND c.completed_on = ? ORDER BY c.created_at",
        (user_id, day),
    )


def completion_ids(user_id: int, on_date: str | None = None) -> set[int]:
    return {int(row["habit_id"]) for row in completions_for_date(user_id, on_date)}


def daily_progress(user_id: int, on_date: str | None = None) -> dict[str, Any]:
    """Today's progress, counting only habits scheduled for that weekday.

    An off-schedule habit can still be ticked as a bonus, but it does not make
    the day look incomplete. Missed days are never subtracted from anything.
    """
    day = on_date or today_iso()
    day_date = date.fromisoformat(day)
    habits_today = list_habits(user_id)
    scheduled = [h for h in habits_today if is_scheduled(h, day_date)]
    not_scheduled = [h for h in habits_today if not is_scheduled(h, day_date)]
    completed = completion_ids(user_id, day)
    done = [h for h in scheduled if int(h["id"]) in completed]
    return {
        "date": day,
        "total": len(scheduled),
        "completed": len(done),
        "remaining": [h for h in scheduled if int(h["id"]) not in completed],
        "completed_habits": done,
        "scheduled": scheduled,
        "not_scheduled": not_scheduled,
        "points_today": rewards.points_today(user_id, day),
        "percent": round(100 * len(done) / len(scheduled)) if scheduled else 0,
    }


# ---------------------------------------------------------------------------
# History and weekly views
# ---------------------------------------------------------------------------

def completion_range(user_id: int, days: int = 7) -> list[dict[str, Any]]:
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    return query_all(
        "SELECT c.*, h.name, h.category FROM habit_completions c "
        "JOIN habits h ON h.id = c.habit_id "
        "WHERE c.user_id = ? AND c.completed_on >= ? ORDER BY c.completed_on",
        (user_id, start),
    )


def weekly_progress(user_id: int) -> list[dict[str, Any]]:
    habits = list_habits(user_id)
    rows = completion_range(user_id, days=7)
    by_habit: dict[int, set[str]] = {}
    for row in rows:
        by_habit.setdefault(int(row["habit_id"]), set()).add(row["completed_on"])
    today = today_iso()
    result = []
    for habit in habits:
        days_done = by_habit.get(int(habit["id"]), set())
        target = int(habit["target_days_per_week"])
        result.append(
            {
                "habit": habit,
                "days_completed": len(days_done),
                "target_days": target,
                "percent": min(100, round(100 * len(days_done) / max(1, target))),
                "completed_today": today in days_done,
                "dates": sorted(days_done),
            }
        )
    return result


def weekly_grid(user_id: int, days: int = 7) -> list[dict[str, Any]]:
    """Rows of habit × day completion flags, newest day last."""
    habits = list_habits(user_id)
    start = date.today() - timedelta(days=days - 1)
    day_list = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    rows = completion_range(user_id, days=days)
    completed = {(int(r["habit_id"]), r["completed_on"]) for r in rows}
    grid = []
    for habit in habits:
        grid.append(
            {
                "habit": habit,
                "days": [
                    {
                        "date": d,
                        "label": date.fromisoformat(d).strftime("%a"),
                        "done": (int(habit["id"]), d) in completed,
                        "scheduled": is_scheduled(habit, date.fromisoformat(d)),
                    }
                    for d in day_list
                ],
            }
        )
    return grid


def habit_streak(user_id: int, habit_id: int) -> int:
    """Consecutive scheduled completions. Rest days never break the streak."""
    habit = get_habit(user_id, habit_id)
    if habit is None:
        return 0
    rows = query_all(
        "SELECT completed_on FROM habit_completions WHERE habit_id = ? AND user_id = ? ORDER BY completed_on DESC",
        (habit_id, user_id),
    )
    days = {date.fromisoformat(str(r["completed_on"])[:10]) for r in rows}
    if not days:
        return 0
    today = date.today()
    cursor = today
    # Today only breaks the streak once it is actually a scheduled day that
    # has not been marked yet; a rest day is skipped entirely.
    if is_scheduled(habit, today) and today not in days:
        cursor = today - timedelta(days=1)
    streak = 0
    for _ in range(3660):
        if is_scheduled(habit, cursor):
            if cursor in days:
                streak += 1
            else:
                break
        cursor -= timedelta(days=1)
    return streak


def habit_history(user_id: int, days: int = 28) -> list[dict[str, Any]]:
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    return query_all(
        "SELECT c.completed_on, c.value, c.note, h.name, h.category, h.unit "
        "FROM habit_completions c JOIN habits h ON h.id = c.habit_id "
        "WHERE c.user_id = ? AND c.completed_on >= ? ORDER BY c.completed_on DESC, c.id DESC",
        (user_id, start),
    )
