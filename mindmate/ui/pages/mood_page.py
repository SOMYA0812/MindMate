"""Mood check-in, history and gentle pattern view.

Mood scores are self-reported snapshots, never clinical measurements. The page
shows named emotions, optional context tags and supportive messages so a low
day is not reduced to a number.
"""

from __future__ import annotations

import html
from datetime import date
from typing import Any

import streamlit as st

from ...knowledge_base import KnowledgeBase
from ...services import mood
from .. import components
from ..state import NAV_REFLECTION, go_to


def _pretty_date(value: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%A, %d %B %Y")
    except (TypeError, ValueError):
        return str(value)


def _mood_card(entry: dict[str, Any]) -> str:
    score = entry.get("mood_score")
    label = mood.mood_label(score)
    meta = mood.emotion_meta(entry.get("emotion"))
    color = meta.get("color") or label.get("color") or "#F6D9C7"
    title = (
        f'{meta.get("emoji", "")} {html.escape(meta.get("label", ""))}'
        if entry.get("emotion")
        else f'{label["emoji"]} {html.escape(label["label"])}'
    )
    tags = "".join(
        f'<span class="mm-tag">{html.escape(str(tag))}</span>'
        for tag in (entry.get("reason_tags") or [])
    )
    prompt = entry.get("mood_prompt") or meta.get("question") or ""
    note = (entry.get("note") or "").strip()
    message = meta.get("message") or ""
    context = []
    if entry.get("energy") is not None:
        context.append(f"Energy {int(entry['energy'])}/5")
    if entry.get("anxiety") is not None:
        context.append(f"Tension {int(entry['anxiety'])}/5")
    if entry.get("sleep_hours") is not None:
        context.append(f"Sleep {float(entry['sleep_hours']):g} h")

    return f"""
    <div class="mm-mood-entry" style="border-left:4px solid {color}">
      <div class="mm-mood-date">{html.escape(_pretty_date(entry.get("entry_date", "")))}</div>
      <div style="display:flex;justify-content:space-between;gap:0.6rem;flex-wrap:wrap;align-items:center;margin-top:0.2rem">
        <span class="mm-mood-title">{title}</span>
        <span class="mm-pill" style="background:{label["color"]}33">{label["emoji"]} {html.escape(label["label"])}</span>
      </div>
      {f'<div style="margin-top:0.4rem;font-family:Georgia,serif;font-size:1rem">{html.escape(prompt)}</div>' if prompt else ""}
      {f'<div style="margin-top:0.4rem">{tags}</div>' if tags else ""}
      {f'<div class="mm-card-soft" style="margin-top:0.55rem">{html.escape(note)}</div>' if note else ""}
      {f'<div class="mm-small" style="margin-top:0.5rem;font-style:italic">{html.escape(message)}</div>' if message else ""}
      {f'<div class="mm-small" style="margin-top:0.45rem">{" · ".join(context)}</div>' if context else ""}
    </div>
    """


def render(user_id: int, kb: KnowledgeBase, prefs: dict[str, Any]) -> None:
    components.page_header(
        "📈",
        "Mood History",
        "A place to notice patterns without turning them into a verdict. Mood scores are self-reported snapshots, "
        "not clinical measurements.",
    )

    with st.container(border=True):
        components.mood_selector(user_id, key_prefix="mood_page")

    st.markdown("---")
    summary = mood.weekly_summary(user_id)
    components.section_title("This week", "Seven days ending today. There is no target to reach.")

    metrics = st.columns(4)
    metrics[0].markdown(
        components.stat_card("Check-ins", f"{summary['count']} / 7", "No streak requirement"),
        unsafe_allow_html=True,
    )
    average = f"{summary['average']:.1f}" if summary["average"] is not None else "—"
    metrics[1].markdown(components.stat_card("Average self-report", average, "Not a clinical score"), unsafe_allow_html=True)
    metrics[2].markdown(components.stat_card("Compared with last week", summary["direction"], "A shift, not a recovery claim"), unsafe_allow_html=True)
    sleep_average = "—"
    sleep_values = [row["sleep_hours"] for row in summary["entries"] if row.get("sleep_hours") is not None]
    if sleep_values:
        sleep_average = f"{sum(sleep_values) / len(sleep_values):.1f} h"
    metrics[3].markdown(components.stat_card("Average sleep", sleep_average, "If recorded"), unsafe_allow_html=True)

    st.markdown(
        f'<div class="mm-card-soft" style="margin-top:0.6rem">{html.escape(summary["text"])}'
        f'<div class="mm-small" style="margin-top:0.4rem">{html.escape(summary["caveat"])}</div></div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        components.section_title("Mood over time (last 30 days)")
        components.mood_line_chart(mood.mood_history(user_id, days=30))
    with right:
        components.section_title("How the week was distributed")
        components.mood_distribution_chart(summary["distribution"])

    emotions = mood.emotion_counts(user_id, days=30)
    tags = mood.tag_counts(user_id, days=30)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        components.section_title("Named emotions (last 30 days)")
        components.mood_emotion_chart(emotions)
    with c2:
        components.section_title("What came up most")
        components.mood_tag_chart(tags)

    if emotions or tags:
        insight = []
        if emotions:
            top = emotions[0]
            insight.append(
                f'The feeling you named most often was **{top["emoji"]} {top["label"]}** '
                f'({top["total"]} time(s)).'
            )
        if tags:
            top_tag = tags[0]
            insight.append(
                f'A context that appeared often was **{top_tag["tag"]}** '
                f'({top_tag["total"]} time(s)).'
            )
        st.markdown(
            f'<div class="mm-card-soft" style="margin-top:0.2rem">{" ".join(insight)} '
            "These are patterns in what you chose to record, not conclusions about you.</div>",
            unsafe_allow_html=True,
        )

    history = mood.mood_history(user_id, days=60)
    st.markdown("---")
    components.section_title("Recent check-ins", "Newest first. Each entry keeps the mood and context you chose.")
    if history:
        for entry in reversed(history[-14:]):
            st.markdown(_mood_card(entry), unsafe_allow_html=True)
        if len(history) > 14:
            st.caption(f"Showing the 14 most recent of {len(history)} check-ins in the last 60 days.")
    else:
        components.empty_state(
            "No check-ins yet",
            "A single check-in is enough to begin. You can add context such as sleep or energy if you want.",
            emoji="🌤️",
        )

    st.caption(
        "A higher mood score is not proof of recovery, and a lower score is not a failure or a diagnosis. "
        "Scores are affected by sleep, events, health and many other things."
    )

    if st.button("Write a reflection", key="mood_to_reflection"):
        go_to(NAV_REFLECTION)
        st.rerun()
