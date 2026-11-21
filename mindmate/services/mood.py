"""Mood check-ins and weekly self-report summaries.

Mood scores are **self-reported snapshots**, not clinical measurements. The
service never rewards a higher score, never labels a score as an improvement in
a clinical sense, and never treats a lower score as failure.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from ..config import MOOD_EMOTIONS, MOOD_LABELS, POINTS
from ..database import get_conn, query_all, query_one, today_iso, utc_now
from . import rewards


def mood_label(score: int | None) -> dict[str, Any]:
    if score is None:
        return {"label": "Not recorded", "emoji": "○", "color": "#CFC9DE"}
    return MOOD_LABELS.get(int(score), {"label": "Unknown", "emoji": "○", "color": "#CFC9DE"})


def emotion_meta(emotion: str | None) -> dict[str, Any]:
    """Return display metadata for a mood word, with a safe fallback."""
    if emotion and emotion in MOOD_EMOTIONS:
        return {"id": emotion, **MOOD_EMOTIONS[emotion]}
    return {
        "id": None,
        "label": "Not named",
        "emoji": "○",
        "color": "#CFC9DE",
        "question": "",
        "prompts": [],
        "message": "",
        "scores": [],
    }


def default_emotion_for_score(score: int | None) -> str | None:
    if score is None:
        return None
    if int(score) <= 1:
        return "sad"
    if int(score) == 2:
        return "low"
    if int(score) == 3:
        return "calm"
    if int(score) == 4:
        return "happy"
    return "happy"


def _decode_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item)[:80] for item in value]
    try:
        parsed = json.loads(value or "[]")
        return [str(item)[:80] for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _hydrate(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if not isinstance(row, dict):
        row = dict(row)
    row["reason_tags"] = _decode_tags(row.get("reason_tags"))
    meta = emotion_meta(row.get("emotion"))
    row["emotion_label"] = meta["label"]
    row["emotion_emoji"] = meta["emoji"]
    row["emotion_color"] = meta["color"]
    row["supportive_message"] = meta["message"]
    row["mood_prompt"] = row.get("mood_prompt") or meta["question"]
    return row


def save_mood_entry(
    user_id: int,
    mood_score: int,
    energy: int | None = None,
    anxiety: int | None = None,
    sleep_hours: float | None = None,
    note: str | None = None,
    entry_date: str | None = None,
    emotion: str | None = None,
    mood_prompt: str | None = None,
    reason_tags: list[str] | None = None,
) -> dict[str, Any]:
    if not 1 <= int(mood_score) <= 5:
        raise ValueError("Mood must be between 1 and 5.")
    day = entry_date or today_iso()
    if energy is not None and not 1 <= int(energy) <= 5:
        raise ValueError("Energy must be between 1 and 5.")
    if anxiety is not None and not 0 <= int(anxiety) <= 5:
        raise ValueError("Anxiety must be between 0 and 5.")
    if sleep_hours is not None and not 0 <= float(sleep_hours) <= 24:
        raise ValueError("Sleep hours must be between 0 and 24.")
    clean_note = (note or "").strip()[:1000] or None
    clean_emotion = emotion if emotion in MOOD_EMOTIONS else None
    clean_prompt = (mood_prompt or "").strip()[:300] or None
    tags = [str(tag).strip()[:80] for tag in (reason_tags or []) if str(tag).strip()][:12]

    existing = get_mood_entry(user_id, day)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO mood_entries (user_id, entry_date, mood_score, energy, anxiety, sleep_hours, "
            "emotion, mood_prompt, reason_tags, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (user_id, entry_date) DO UPDATE SET "
            "mood_score = excluded.mood_score, energy = excluded.energy, anxiety = excluded.anxiety, "
            "sleep_hours = excluded.sleep_hours, emotion = excluded.emotion, "
            "mood_prompt = excluded.mood_prompt, reason_tags = excluded.reason_tags, note = excluded.note",
            (user_id, day, int(mood_score), energy, anxiety, sleep_hours, clean_emotion,
             clean_prompt, json.dumps(tags), clean_note, utc_now()),
        )
    awarded = 0
    if existing is None:
        awarded = rewards.award_points(user_id, "mood_checkin", day, POINTS["mood_checkin"], on_date=day)
    return {"entry": get_mood_entry(user_id, day), "points_awarded": awarded, "updated": existing is not None}


def get_mood_entry(user_id: int, entry_date: str | None = None) -> dict[str, Any] | None:
    day = entry_date or today_iso()
    return _hydrate(
        query_one("SELECT * FROM mood_entries WHERE user_id = ? AND entry_date = ?", (user_id, day))
    )


def delete_mood_entry(user_id: int, entry_date: str | None = None) -> None:
    day = entry_date or today_iso()
    with get_conn() as conn:
        conn.execute("DELETE FROM mood_entries WHERE user_id = ? AND entry_date = ?", (user_id, day))


def mood_history(user_id: int, days: int = 30) -> list[dict[str, Any]]:
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = query_all(
        "SELECT * FROM mood_entries WHERE user_id = ? AND entry_date >= ? ORDER BY entry_date",
        (user_id, start),
    )
    hydrated = []
    for row in rows:
        item = _hydrate(row) or row
        item["label"] = mood_label(item["mood_score"])["label"]
        item["emoji"] = mood_label(item["mood_score"])["emoji"]
        hydrated.append(item)
    return hydrated


def emotion_counts(user_id: int, days: int = 30) -> list[dict[str, Any]]:
    """Count named emotions in the window, most common first."""
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = query_all(
        "SELECT emotion, COUNT(*) AS total FROM mood_entries "
        "WHERE user_id = ? AND entry_date >= ? AND emotion IS NOT NULL AND emotion != '' "
        "GROUP BY emotion ORDER BY total DESC",
        (user_id, start),
    )
    result = []
    for row in rows:
        meta = emotion_meta(row["emotion"])
        result.append({
            "emotion": row["emotion"],
            "label": meta["label"],
            "emoji": meta["emoji"],
            "color": meta["color"],
            "total": int(row["total"]),
        })
    return result


def tag_counts(user_id: int, days: int = 30) -> list[dict[str, Any]]:
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = query_all(
        "SELECT reason_tags FROM mood_entries WHERE user_id = ? AND entry_date >= ?",
        (user_id, start),
    )
    counts: dict[str, int] = {}
    for row in rows:
        for tag in _decode_tags(row.get("reason_tags")):
            counts[tag] = counts.get(tag, 0) + 1
    return [
        {"tag": tag, "total": total}
        for tag, total in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def mood_frame(user_id: int, days: int = 30) -> Any:
    """Return a pandas DataFrame for charts (imported lazily)."""
    import pandas as pd

    rows = mood_history(user_id, days)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["entry_date", "mood_score", "label", "energy", "anxiety", "sleep_hours"])
    frame["entry_date"] = pd.to_datetime(frame["entry_date"])
    return frame.sort_values("entry_date")


def weekly_summary(user_id: int, reference_date: date | None = None) -> dict[str, Any]:
    ref = reference_date or date.today()
    start = ref - timedelta(days=6)
    previous_start = start - timedelta(days=7)
    previous_end = start - timedelta(days=1)

    current = query_all(
        "SELECT * FROM mood_entries WHERE user_id = ? AND entry_date BETWEEN ? AND ? ORDER BY entry_date",
        (user_id, start.isoformat(), ref.isoformat()),
    )
    previous = query_all(
        "SELECT * FROM mood_entries WHERE user_id = ? AND entry_date BETWEEN ? AND ?",
        (user_id, previous_start.isoformat(), previous_end.isoformat()),
    )

    scores = [int(row["mood_score"]) for row in current]
    previous_scores = [int(row["mood_score"]) for row in previous]
    average = round(sum(scores) / len(scores), 2) if scores else None
    previous_average = round(sum(previous_scores) / len(previous_scores), 2) if previous_scores else None

    direction = "not enough data"
    if average is not None and previous_average is not None:
        delta = average - previous_average
        if delta >= 0.4:
            direction = "a little higher than last week"
        elif delta <= -0.4:
            direction = "a little lower than last week"
        else:
            direction = "similar to last week"

    distribution: dict[str, int] = {}
    for score in scores:
        label = mood_label(score)["label"]
        distribution[label] = distribution.get(label, 0) + 1

    best = max(current, key=lambda r: r["mood_score"]) if current else None
    lowest = min(current, key=lambda r: r["mood_score"]) if current else None

    if not current:
        text = (
            "No mood check-ins in this window. That is okay — this is a tool, not an obligation. "
            "If you want to start, one check-in is enough."
        )
    else:
        most_common = max(distribution, key=distribution.get)
        text = (
            f"You checked in on {len(current)} day(s) this week. Your self-reported mood was most often "
            f"'{most_common}'. This is a personal snapshot, not a clinical measurement, and there is no target score."
        )

    return {
        "start": start.isoformat(),
        "end": ref.isoformat(),
        "entries": current,
        "count": len(current),
        "average": average,
        "previous_average": previous_average,
        "direction": direction,
        "distribution": distribution,
        "best_day": best,
        "lowest_day": lowest,
        "text": text,
        "checked_in_today": any(row["entry_date"] == ref.isoformat() for row in current),
        "caveat": (
            "Mood scores are self-reported and affected by many things. A higher score is not proof of recovery, "
            "and a lower score is not a failure or a diagnosis."
        ),
    }
