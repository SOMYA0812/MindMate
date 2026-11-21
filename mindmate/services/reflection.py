"""Daily reflection.

Reflection is optional and short. Points are awarded for the act of reflecting,
not for the content, and never for reporting a particular mood.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..config import POINTS
from ..database import get_conn, query_all, query_one, today_iso, utc_now
from . import rewards

PROMPTS = [
    "What is one thing you got through today, even if it was small?",
    "Was there a moment that felt slightly easier? What was happening?",
    "What would you like to leave here for today?",
    "If tomorrow could be 5% gentler, what would that look like?",
]


def save_reflection(
    user_id: int,
    went_well: str | None = None,
    grateful_for: str | None = None,
    tomorrow_step: str | None = None,
    reflection_date: str | None = None,
) -> dict[str, Any]:
    day = reflection_date or today_iso()
    fields = {
        "went_well": (went_well or "").strip()[:1000] or None,
        "grateful_for": (grateful_for or "").strip()[:1000] or None,
        "tomorrow_step": (tomorrow_step or "").strip()[:1000] or None,
    }
    if not any(fields.values()):
        raise ValueError("Write at least a few words before saving.")

    existing = get_reflection(user_id, day)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reflections (user_id, reflection_date, went_well, grateful_for, tomorrow_step, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (user_id, reflection_date) DO UPDATE SET "
            "went_well = excluded.went_well, grateful_for = excluded.grateful_for, "
            "tomorrow_step = excluded.tomorrow_step",
            (user_id, day, fields["went_well"], fields["grateful_for"], fields["tomorrow_step"], utc_now()),
        )
    awarded = 0
    if existing is None:
        awarded = rewards.award_points(user_id, "reflection", day, POINTS["reflection"], on_date=day)
    return {"reflection": get_reflection(user_id, day), "points_awarded": awarded, "updated": existing is not None}


def get_reflection(user_id: int, reflection_date: str | None = None) -> dict[str, Any] | None:
    day = reflection_date or today_iso()
    return query_one(
        "SELECT * FROM reflections WHERE user_id = ? AND reflection_date = ?", (user_id, day)
    )


def recent_reflections(user_id: int, days: int = 14) -> list[dict[str, Any]]:
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    return query_all(
        "SELECT * FROM reflections WHERE user_id = ? AND reflection_date >= ? "
        "ORDER BY reflection_date DESC",
        (user_id, start),
    )


def delete_reflection(user_id: int, reflection_date: str | None = None) -> None:
    day = reflection_date or today_iso()
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM reflections WHERE user_id = ? AND reflection_date = ?", (user_id, day)
        )
