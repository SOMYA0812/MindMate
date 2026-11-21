"""Reward, badge and plant-growth logic.

Rules that are intentionally enforced here:

* Points are awarded for *actions*, never for reporting a better mood.
* Missing a day never removes points, breaks the plant, or triggers a penalty.
* Ledger writes are idempotent per (user, event, reference, date).
* Badges describe effort and consistency, not clinical improvement.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from ..config import POINTS
from ..database import query_all, query_one, today_iso, utc_now, get_conn

BADGES: dict[str, dict[str, str]] = {
    "first_checkin": {
        "name": "First check-in",
        "emoji": "🌱",
        "description": "You checked in with yourself for the first time.",
    },
    "first_habit": {
        "name": "First small step",
        "emoji": "👣",
        "description": "You completed your first habit.",
    },
    "checkin_3": {
        "name": "Three check-ins",
        "emoji": "🌤️",
        "description": "You checked in on three different days.",
    },
    "checkin_7": {
        "name": "A week of noticing",
        "emoji": "🗓️",
        "description": "You checked in on seven different days.",
    },
    "habit_10": {
        "name": "Ten efforts",
        "emoji": "🌿",
        "description": "You completed ten habit entries.",
    },
    "habit_25": {
        "name": "Twenty-five efforts",
        "emoji": "🌳",
        "description": "You completed twenty-five habit entries.",
    },
    "streak_3": {
        "name": "Three days of showing up",
        "emoji": "✨",
        "description": "You did something supportive on three days in a row.",
    },
    "streak_7": {
        "name": "A gentle week",
        "emoji": "🌈",
        "description": "You did something supportive on seven days in a row.",
    },
    "reflection_5": {
        "name": "Five reflections",
        "emoji": "📝",
        "description": "You wrote five daily reflections.",
    },
    "week_balanced": {
        "name": "A mixed week",
        "emoji": "🧺",
        "description": "You practised habits from three different areas in one week.",
    },
    "gentle_return": {
        "name": "You came back",
        "emoji": "🫶",
        "description": "You returned after a gap. Coming back counts.",
    },
    "plant_bloom": {
        "name": "Plant in bloom",
        "emoji": "🌻",
        "description": "Your plant reached 300 points of accumulated effort.",
    },
}

PLANT_STAGES = [
    {"key": "seed", "name": "Seed", "emoji": "🌰", "at": 0,
     "note": "A beginning. Nothing has to be visible yet."},
    {"key": "sprout", "name": "Sprout", "emoji": "🌱", "at": 25,
     "note": "Something small is growing."},
    {"key": "seedling", "name": "Seedling", "emoji": "🌿", "at": 60,
     "note": "A few leaves. Keep going at your own pace."},
    {"key": "bud", "name": "Bud", "emoji": "🌷", "at": 120,
     "note": "There is a bud. It does not need to hurry."},
    {"key": "bloom", "name": "Bloom", "emoji": "🌸", "at": 200,
     "note": "Your plant has bloomed from repeated small efforts."},
    {"key": "tree", "name": "Little tree", "emoji": "🌳", "at": 300,
     "note": "Steady care has made something lasting."},
    {"key": "orchard", "name": "Orchard", "emoji": "🌻", "at": 450,
     "note": "A whole garden of small efforts."},
]

MOTIVATIONAL_MESSAGES = [
    "Showing up today counts, even if nothing else got done.",
    "You do not have to earn rest. It is part of the plan.",
    "Small and repeatable beats big and perfect.",
    "A difficult day is still a day you got through.",
    "You are allowed to do the minimum and call it enough.",
    "Progress can look like resting, asking for help, or trying once.",
    "Your worth is not measured by your streak or your points.",
    "One kind thing toward yourself is a real action.",
    "There is no catch-up required for missed days.",
    "You can start again at any hour of the day.",
    "The goal is support, not a perfect record.",
    "Noticing how you feel is already a skill.",
]


def award_points(user_id: int, event_type: str, reference_id: str,
                 points: int, on_date: str | None = None) -> int:
    """Award points idempotently. Returns the number actually awarded (0 or points)."""
    if points <= 0:
        return 0
    day = on_date or today_iso()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO points_ledger (user_id, event_type, reference_id, points, awarded_on, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id, event_type, reference_id, awarded_on) DO NOTHING",
            (user_id, event_type, str(reference_id), int(points), day, utc_now()),
        )
        inserted = cur.rowcount > 0
    if inserted:
        check_and_award_badges(user_id)
        return int(points)
    return 0


def points_today(user_id: int, on_date: str | None = None) -> int:
    day = on_date or today_iso()
    row = query_one(
        "SELECT COALESCE(SUM(points), 0) AS total FROM points_ledger WHERE user_id = ? AND awarded_on = ?",
        (user_id, day),
    )
    return int(row["total"]) if row else 0


def total_points(user_id: int) -> int:
    row = query_one(
        "SELECT COALESCE(SUM(points), 0) AS total FROM points_ledger WHERE user_id = ?",
        (user_id,),
    )
    return int(row["total"]) if row else 0


def points_breakdown(user_id: int, days: int = 7) -> list[dict[str, Any]]:
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    return query_all(
        "SELECT event_type, COALESCE(SUM(points), 0) AS points FROM points_ledger "
        "WHERE user_id = ? AND awarded_on >= ? GROUP BY event_type ORDER BY points DESC",
        (user_id, start),
    )


def weekly_points(user_id: int, days: int = 7) -> list[dict[str, Any]]:
    start = date.today() - timedelta(days=days - 1)
    rows = query_all(
        "SELECT awarded_on, COALESCE(SUM(points), 0) AS points FROM points_ledger "
        "WHERE user_id = ? AND awarded_on >= ? GROUP BY awarded_on",
        (user_id, start.isoformat()),
    )
    by_day = {row["awarded_on"]: int(row["points"]) for row in rows}
    result = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        result.append(
            {
                "date": day.isoformat(),
                "label": day.strftime("%a"),
                "points": by_day.get(day.isoformat(), 0),
            }
        )
    return result


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------

def _activity_dates(user_id: int) -> list[date]:
    rows = query_all(
        "SELECT entry_date AS d FROM mood_entries WHERE user_id = ? "
        "UNION SELECT completed_on AS d FROM habit_completions WHERE user_id = ? "
        "UNION SELECT reflection_date AS d FROM reflections WHERE user_id = ? "
        "ORDER BY d",
        (user_id, user_id, user_id),
    )
    result: list[date] = []
    for row in rows:
        try:
            result.append(date.fromisoformat(str(row["d"])[:10]))
        except (TypeError, ValueError):
            continue
    return result


def current_streak(user_id: int) -> int:
    """Consecutive days with any supportive action.

    A day is not counted as 'missed' until it is over, so not having done
    something yet today does not break the streak.
    """
    days = set(_activity_dates(user_id))
    if not days:
        return 0
    today = date.today()
    anchor = today if today in days else today - timedelta(days=1)
    if anchor not in days:
        return 0
    streak = 0
    cursor = anchor
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _has_gentle_return(user_id: int) -> bool:
    days = sorted(set(_activity_dates(user_id)))
    if len(days) < 2:
        return False
    today = date.today()
    if days[-1] < today - timedelta(days=2):
        return False
    return any((days[i] - days[i - 1]).days >= 3 for i in range(1, len(days)))


def check_and_award_badges(user_id: int) -> list[dict[str, Any]]:
    """Evaluate badge conditions and insert any newly earned badges."""
    counts = {
        "checkins": query_one("SELECT COUNT(*) AS c FROM mood_entries WHERE user_id = ?", (user_id,))["c"],
        "habits": query_one("SELECT COUNT(*) AS c FROM habit_completions WHERE user_id = ?", (user_id,))["c"],
        "reflections": query_one("SELECT COUNT(*) AS c FROM reflections WHERE user_id = ?", (user_id,))["c"],
    }
    streak = current_streak(user_id)
    total = total_points(user_id)

    week_start = (date.today() - timedelta(days=6)).isoformat()
    category_rows = query_all(
        "SELECT DISTINCT h.category FROM habit_completions c "
        "JOIN habits h ON h.id = c.habit_id "
        "WHERE c.user_id = ? AND c.completed_on >= ?",
        (user_id, week_start),
    )

    earned: list[str] = []
    if counts["checkins"] >= 1:
        earned.append("first_checkin")
    if counts["checkins"] >= 3:
        earned.append("checkin_3")
    if counts["checkins"] >= 7:
        earned.append("checkin_7")
    if counts["habits"] >= 1:
        earned.append("first_habit")
    if counts["habits"] >= 10:
        earned.append("habit_10")
    if counts["habits"] >= 25:
        earned.append("habit_25")
    if counts["reflections"] >= 5:
        earned.append("reflection_5")
    if streak >= 3:
        earned.append("streak_3")
    if streak >= 7:
        earned.append("streak_7")
    if len(category_rows) >= 3:
        earned.append("week_balanced")
    if _has_gentle_return(user_id):
        earned.append("gentle_return")
    if total >= 300:
        earned.append("plant_bloom")

    newly: list[dict[str, Any]] = []
    with get_conn() as conn:
        for key in earned:
            cur = conn.execute(
                "INSERT INTO badges (user_id, badge_key, awarded_on) VALUES (?, ?, ?) "
                "ON CONFLICT (user_id, badge_key) DO NOTHING",
                (user_id, key, today_iso()),
            )
            if cur.rowcount > 0:
                newly.append({"key": key, **BADGES.get(key, {"name": key, "emoji": "✨", "description": ""})})
    return newly


def get_badges(user_id: int) -> list[dict[str, Any]]:
    rows = query_all(
        "SELECT badge_key, awarded_on FROM badges WHERE user_id = ? ORDER BY awarded_on, id",
        (user_id,),
    )
    result = []
    for row in rows:
        meta = BADGES.get(row["badge_key"], {"name": row["badge_key"], "emoji": "✨", "description": ""})
        result.append({"key": row["badge_key"], "earned_on": row["awarded_on"], **meta})
    return result


def all_badge_catalogue(user_id: int) -> list[dict[str, Any]]:
    earned = {b["key"]: b for b in get_badges(user_id)}
    catalogue = []
    for key, meta in BADGES.items():
        item = {"key": key, **meta, "earned": key in earned, "earned_on": earned.get(key, {}).get("earned_on")}
        catalogue.append(item)
    return catalogue


# ---------------------------------------------------------------------------
# Plant and messages
# ---------------------------------------------------------------------------

def plant_state(user_id: int) -> dict[str, Any]:
    total = total_points(user_id)
    stage = PLANT_STAGES[0]
    for candidate in PLANT_STAGES:
        if total >= candidate["at"]:
            stage = candidate
    index = PLANT_STAGES.index(stage)
    next_stage = PLANT_STAGES[index + 1] if index + 1 < len(PLANT_STAGES) else None
    if next_stage:
        span = max(1, next_stage["at"] - stage["at"])
        progress = min(1.0, max(0.0, (total - stage["at"]) / span))
    else:
        progress = 1.0
    return {
        **stage,
        "total_points": total,
        "next_at": next_stage["at"] if next_stage else None,
        "next_name": next_stage["name"] if next_stage else None,
        "progress": round(progress, 3),
        "stage_index": index,
    }


def daily_message(on_date: date | None = None) -> str:
    day = on_date or date.today()
    return MOTIVATIONAL_MESSAGES[day.toordinal() % len(MOTIVATIONAL_MESSAGES)]
