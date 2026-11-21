"""Reusable Streamlit components for MindMate."""

from __future__ import annotations

import html
from datetime import date
from typing import Any, Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ..config import HABIT_CATEGORIES, MOOD_EMOTIONS, MOOD_LABELS
from ..engine.inference_engine import InferenceResult, RecommendationMatch
from ..services import habits, mood
from .theme import palette


# ---------------------------------------------------------------------------
# Basic layout
# ---------------------------------------------------------------------------

def page_header(emoji: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="mm-hero">
          <div class="mm-eyebrow">{html.escape(emoji)} MindMate</div>
          <h1>{html.escape(title)}</h1>
          <p>{html.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, caption: str = "") -> None:
    st.markdown(f"### {html.escape(title)}")
    if caption:
        st.markdown(f'<div class="mm-muted">{html.escape(caption)}</div>', unsafe_allow_html=True)


def footer() -> None:
    st.markdown(
        """
        <div class="mm-footer">
          <strong>MindMate is an academic project.</strong> It is not a medical device, diagnostic tool,
          therapist, or emergency service. It cannot diagnose or treat depression or any other condition.
          If you are in immediate danger in India, call <strong>112</strong>. For mental health support,
          call Tele-MANAS on <strong>14416</strong>. Helpline details can change; verify them before relying on them.
        </div>
        """,
        unsafe_allow_html=True,
    )


def info_card(text: str, tone: str = "") -> None:
    cls = {"warm": "mm-card-warm", "alert": "mm-card-alert", "soft": "mm-card-soft"}.get(tone, "mm-card")
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def stat_card(label: str, value: str, sub: str = "") -> str:
    return f"""
    <div class="mm-card">
      <div class="mm-label">{html.escape(label)}</div>
      <div class="mm-number">{html.escape(str(value))}</div>
      <div class="mm-small">{html.escape(sub)}</div>
    </div>
    """


def mood_chip(score: int | None) -> str:
    data = MOOD_LABELS.get(score or 0, {"label": "Not recorded", "emoji": "○", "color": "#CFC9DE"})
    ink = palette()["ink"]
    return f'<span class="mm-pill" style="background:{data["color"]}33;color:{ink}">{data["emoji"]} {data["label"]}</span>'


# ---------------------------------------------------------------------------
# Mood check-in
# ---------------------------------------------------------------------------

def _emotion_options() -> list[str]:
    return list(MOOD_EMOTIONS)


def _emotion_label(key: str) -> str:
    meta = MOOD_EMOTIONS.get(key, {})
    return f"{meta.get('emoji', '○')} {meta.get('label', key)}"


def _save_score(user_id: int, score: int, entry: dict[str, Any] | None) -> dict[str, Any]:
    """Save a quick score while preserving context already entered today."""
    if entry:
        same_score = int(entry.get("mood_score") or 0) == int(score)
        emotion = entry.get("emotion") if same_score else None
        emotion = emotion or mood.default_emotion_for_score(score)
        meta = mood.emotion_meta(emotion)
        return mood.save_mood_entry(
            user_id,
            score,
            energy=entry.get("energy"),
            anxiety=entry.get("anxiety"),
            sleep_hours=entry.get("sleep_hours"),
            note=entry.get("note"),
            entry_date=entry.get("entry_date"),
            emotion=emotion,
            mood_prompt=(entry.get("mood_prompt") if same_score else meta.get("question", "")),
            reason_tags=(entry.get("reason_tags") or []) if same_score else [],
        )
    emotion = mood.default_emotion_for_score(score)
    meta = mood.emotion_meta(emotion)
    return mood.save_mood_entry(
        user_id,
        score,
        emotion=emotion,
        mood_prompt=meta.get("question", ""),
    )


def mood_selector(user_id: int, key_prefix: str = "mood") -> None:
    entry = mood.get_mood_entry(user_id)
    st.markdown("#### How are you feeling right now?")
    st.markdown(
        '<div class="mm-muted" style="margin-bottom:0.6rem">A check-in takes ten seconds. '
        "There is no right answer, and a low score is not a failure.</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    for index, score in enumerate([1, 2, 3, 4, 5]):
        data = MOOD_LABELS[score]
        selected = entry is not None and int(entry["mood_score"]) == score
        with cols[index]:
            if st.button(
                f"{data['emoji']}\n\n{data['label']}",
                key=f"{key_prefix}_mood_{score}",
                use_container_width=True,
                type="primary" if selected else "secondary",
            ):
                result = _save_score(user_id, score, entry)
                if result["points_awarded"]:
                    st.toast(f"Check-in saved. +{result['points_awarded']} points for noticing how you feel.")
                else:
                    st.toast("Check-in updated.")
                st.rerun()

    if entry is None:
        st.markdown(
            '<div class="mm-small" style="margin-top:0.4rem">Your mood score never affects your points. '
            "Points are for the check-in itself.</div>",
            unsafe_allow_html=True,
        )
        return

    data = MOOD_LABELS[int(entry["mood_score"])]
    current_emotion = entry.get("emotion") or mood.default_emotion_for_score(entry["mood_score"])
    meta = mood.emotion_meta(current_emotion)
    tint = f"{meta.get('color', '#F6D9C7')}2A" if not meta.get("color") else f"{meta['color']}2A"
    st.markdown(
        f'<div class="mm-mood-panel" style="margin-top:0.8rem;background:{tint}">'
        f'<div style="display:flex;justify-content:space-between;gap:0.8rem;flex-wrap:wrap;align-items:center">'
        f'<span class="mm-mood-title">{meta.get("emoji", data["emoji"])} {html.escape(meta.get("label", data["label"]))}</span>'
        f'<span class="mm-pill">{data["emoji"]} {data["label"]}</span></div>'
        f'<div style="margin-top:0.35rem">{html.escape(meta.get("message") or "Thank you for checking in.")}</div>'
        f'<div class="mm-small" style="margin-top:0.35rem">Saved for {entry["entry_date"]}. '
        "Mood is self-reported, not a clinical measurement.</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown("##### A little more, only if you want")
    st.caption("This helps MindMate understand the context. You can skip every part of it.")
    pill_key = f"{key_prefix}_emotion_{entry['entry_date']}_{entry['mood_score']}"
    picker_default = st.session_state.get(pill_key, current_emotion)
    if picker_default not in MOOD_EMOTIONS:
        picker_default = current_emotion
    chosen_emotion = st.pills(
        "Which word fits best?",
        options=_emotion_options(),
        default=picker_default,
        format_func=_emotion_label,
        key=pill_key,
    ) or picker_default
    chosen_meta = mood.emotion_meta(chosen_emotion)
    prompt = chosen_meta.get("question") or "What is on your mind today?"

    st.markdown(
        f'<div class="mm-card-warm" style="margin:0.5rem 0 0.7rem">'
        f'<div class="mm-label">A question for this mood</div>'
        f'<div style="font-family:Georgia, serif;font-size:1.18rem">{html.escape(prompt)}</div></div>',
        unsafe_allow_html=True,
    )

    with st.form(f"{key_prefix}_mood_followup_{entry['entry_date']}"):
        existing_tags = entry.get("reason_tags") or []
        valid_defaults = [tag for tag in existing_tags if tag in chosen_meta.get("prompts", [])]
        tags = st.multiselect(
            "Anything that fits? (optional)",
            options=chosen_meta.get("prompts", []),
            default=valid_defaults,
            key=f"{key_prefix}_tags_{chosen_emotion}_{entry['mood_score']}",
        )
        note = st.text_area(
            "Anything you want to add? (optional)",
            value=entry.get("note") or "",
            max_chars=1000,
            height=90,
            placeholder="A sentence is enough. You can also leave this empty.",
        )
        with st.expander("Also track energy, tension and sleep"):
            c1, c2, c3 = st.columns(3)
            energy = c1.slider("Energy", 1, 5, int(entry.get("energy") or 3))
            anxiety = c2.slider("Tension / worry", 0, 5, int(entry.get("anxiety") or 0))
            sleep_hours = c3.number_input(
                "Sleep last night (hours)", 0.0, 24.0, float(entry.get("sleep_hours") or 7.0), 0.5
            )
        if st.form_submit_button("Save check-in details", type="primary"):
            mood.save_mood_entry(
                user_id,
                int(entry["mood_score"]),
                energy=energy,
                anxiety=anxiety,
                sleep_hours=sleep_hours,
                note=note,
                entry_date=entry["entry_date"],
                emotion=chosen_emotion,
                mood_prompt=prompt,
                reason_tags=tags,
            )
            st.toast("Saved. Your check-in is still worth the same points, whatever you chose.")
            st.rerun()

    st.markdown(
        '<div class="mm-small" style="margin-top:0.4rem">Your mood score never affects your points. '
        "Points are for the check-in itself.</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def _base_figure(height: int = 280) -> go.Figure:
    tokens = palette()
    fig = go.Figure()
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=tokens["ink"], family="Avenir Next, Segoe UI, sans-serif", size=12),
        hoverlabel=dict(bgcolor=tokens["card"], font_color=tokens["ink"],
                        bordercolor=tokens["line_strong"]),
    )
    return fig


def mood_line_chart(history: list[dict[str, Any]]) -> None:
    if not history:
        st.info("No mood check-ins yet. One check-in will start the chart — no streak required.")
        return
    tokens = palette()
    frame = pd.DataFrame(history)
    frame["entry_date"] = pd.to_datetime(frame["entry_date"])
    fig = _base_figure(300)
    fig.add_trace(
        go.Scatter(
            x=frame["entry_date"],
            y=frame["mood_score"],
            mode="lines+markers",
            line=dict(color=tokens["accent"], width=3, shape="spline"),
            marker=dict(size=11, color=tokens["accent_deep"],
                        line=dict(color=tokens["card"], width=2)),
            fill="tozeroy",
            fillcolor=f"{tokens['accent']}1F",
            customdata=frame["label"],
            hovertemplate="%{x|%d %b}<br>%{customdata}<extra></extra>",
        )
    )
    fig.update_yaxes(
        range=[0.5, 5.5],
        tickvals=[1, 2, 3, 4, 5],
        ticktext=["Very low", "Low", "Okay", "Good", "Great"],
        gridcolor=tokens["line"],
    )
    fig.update_xaxes(gridcolor=tokens["line"])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def mood_distribution_chart(distribution: dict[str, int]) -> None:
    if not distribution:
        return
    order = ["Very low", "Low", "Okay", "Good", "Great"]
    labels = [label for label in order if label in distribution]
    values = [distribution[label] for label in labels]
    colors = ["#B9A7D9", "#A9C4DE", "#A8D5C7", "#94C9A9", "#F2C879"]
    fig = _base_figure(230)
    fig.add_trace(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=colors[: len(labels)], line=dict(width=0)),
            text=values,
            textposition="outside",
            hovertemplate="%{y}: %{x} day(s)<extra></extra>",
        )
    )
    fig.update_layout(showlegend=False, xaxis_title="Days", bargap=0.35)
    fig.update_xaxes(showgrid=False, dtick=1)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def mood_emotion_chart(distribution: list[dict[str, Any]]) -> None:
    if not distribution:
        st.caption("Name an emotion in a check-in to see this pattern.")
        return
    fig = _base_figure(230)
    fig.add_trace(
        go.Bar(
            x=[row["total"] for row in distribution],
            y=[f'{row["emoji"]} {row["label"]}' for row in distribution],
            orientation="h",
            marker=dict(color=[row["color"] for row in distribution], line=dict(width=0)),
            text=[row["total"] for row in distribution],
            textposition="outside",
            hovertemplate="%{y}: %{x} check-in(s)<extra></extra>",
        )
    )
    fig.update_layout(showlegend=False, bargap=0.4, xaxis_title="Check-ins")
    fig.update_xaxes(showgrid=False, dtick=1)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def mood_tag_chart(tags: list[dict[str, Any]]) -> None:
    if not tags:
        st.caption("Add an optional context tag to see what comes up most often.")
        return
    fig = _base_figure(230)
    fig.add_trace(
        go.Bar(
            x=[row["total"] for row in tags[:8]],
            y=[row["tag"] for row in tags[:8]],
            orientation="h",
            marker=dict(color=palette()["sage"], line=dict(width=0)),
            text=[row["total"] for row in tags[:8]],
            textposition="outside",
            hovertemplate="%{y}: %{x} time(s)<extra></extra>",
        )
    )
    fig.update_layout(showlegend=False, bargap=0.4, xaxis_title="Times mentioned")
    fig.update_xaxes(showgrid=False, dtick=1)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def points_bar_chart(weekly: list[dict[str, Any]]) -> None:
    tokens = palette()
    fig = _base_figure(240)
    fig.add_trace(
        go.Bar(
            x=[row["label"] for row in weekly],
            y=[row["points"] for row in weekly],
            marker=dict(color=tokens["sage"], line=dict(width=0)),
            text=[row["points"] if row["points"] else "" for row in weekly],
            textposition="outside",
            hovertemplate="%{x}: %{y} points<extra></extra>",
        )
    )
    fig.update_layout(showlegend=False, yaxis_title="Points", bargap=0.45)
    fig.update_yaxes(gridcolor=tokens["line"], rangemode="tozero")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def habit_heatmap(grid: list[dict[str, Any]]) -> None:
    if not grid:
        st.info("Add a habit to see your week.")
        return
    tokens = palette()

    def _value(cell: dict[str, Any]) -> int:
        if cell["done"]:
            return 2
        return 1 if cell.get("scheduled", True) else 0

    def _text(cell: dict[str, Any]) -> str:
        if cell["done"]:
            return "recorded"
        return "not recorded" if cell.get("scheduled", True) else "rest day"

    z = [[_value(cell) for cell in row["days"]] for row in grid]
    text = [[_text(cell) for cell in row["days"]] for row in grid]
    y = [row["habit"]["name"] for row in grid]
    x = [cell["label"] for cell in grid[0]["days"]]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=x,
            y=y,
            text=text,
            zmin=0,
            zmax=2,
            colorscale=[
                [0.0, tokens["line"]],
                [0.49, tokens["line"]],
                [0.5, tokens["card_soft"]],
                [0.99, tokens["card_soft"]],
                [1.0, tokens["accent"]],
            ],
            showscale=False,
            xgap=6,
            ygap=6,
            hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(200, 44 * len(grid) + 80),
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=tokens["ink"], size=12),
    )
    fig.update_xaxes(side="top", showgrid=False)
    fig.update_yaxes(showgrid=False, autorange="reversed")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Plant and badges
# ---------------------------------------------------------------------------

def plant_svg(stage_index: int, height: int = 210) -> str:
    """A small inline SVG plant that grows with accumulated effort."""
    stage = max(0, min(int(stage_index), 6))
    stem_height = [2, 24, 48, 68, 78, 86, 92][stage]
    leaves = ""
    for frac, side in [(0.35, -1), (0.55, 1), (0.72, -1)]:
        if stage >= 2:
            y = 168 - stem_height * frac
            x = 110 + side * 17
            leaves += (
                f'<ellipse cx="{x}" cy="{y}" rx="17" ry="8" fill="#8FBF9F" '
                f'transform="rotate({-25 * side} {x} {y})" opacity="0.95"/>'
            )
    flower = ""
    if stage >= 4:
        cy = 168 - stem_height - 4
        for dx, dy, color in [(-11, 0, "#F2B8C6"), (11, 0, "#F2B8C6"), (0, -11, "#F6CF8D"), (0, 11, "#F6CF8D"), (-8, -8, "#E9A7BC"), (8, -8, "#E9A7BC"), (-8, 8, "#E9A7BC"), (8, 8, "#E9A7BC")]:
            flower += f'<circle cx="{110 + dx}" cy="{cy + dy}" r="9" fill="{color}"/>'
        flower += f'<circle cx="110" cy="{cy}" r="7" fill="#F6E3A8"/>'
    if stage >= 5:
        flower += (
            f'<circle cx="72" cy="105" r="26" fill="#6FA98D" opacity="0.75"/>'
            f'<circle cx="148" cy="105" r="26" fill="#6FA98D" opacity="0.75"/>'
            f'<circle cx="110" cy="78" r="34" fill="#79B397" opacity="0.85"/>'
        )
    if stage == 6:
        flower += (
            f'<circle cx="52" cy="138" r="8" fill="#F2C879"/>'
            f'<circle cx="168" cy="138" r="8" fill="#F2C879"/>'
            f'<circle cx="42" cy="118" r="6" fill="#F2B8C6"/>'
            f'<circle cx="178" cy="118" r="6" fill="#F2B8C6"/>'
        )
    seed = "" if stage > 0 else '<ellipse cx="110" cy="168" rx="8" ry="5" fill="#9C7C63"/>'
    svg = f"""
    <svg viewBox="0 0 220 215" width="100%" height="{height}" xmlns="http://www.w3.org/2000/svg" role="img"
         aria-label="A plant at growth stage {stage}">
      <defs>
        <linearGradient id="pot" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#E8CDBD"/><stop offset="100%" stop-color="#D8B7A3"/>
        </linearGradient>
      </defs>
      <circle cx="110" cy="110" r="96" fill="#F5FAF7"/>
      <ellipse cx="110" cy="178" rx="72" ry="12" fill="#DDEBE3"/>
      {flower}
      <path d="M110 168 L110 {168 - stem_height}" stroke="#6FA98D" stroke-width="4" stroke-linecap="round"/>
      {leaves}
      {seed}
      <path d="M72 168 L148 168 L138 198 Q110 204 82 198 Z" fill="url(#pot)"/>
      <ellipse cx="110" cy="168" rx="38" ry="7" fill="#B99179"/>
    </svg>
    """
    # Streamlit renders HTML through Markdown; newlines inside the SVG can be
    # parsed as a code block, so collapse it to a single line.
    return " ".join(line.strip() for line in svg.strip().splitlines())


def render_plant(plant: dict[str, Any]) -> None:
    st.markdown(f'<div class="mm-plant">{plant_svg(plant["stage_index"])}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:center;margin-top:0.4rem"><strong>{plant["emoji"]} {plant["name"]}</strong>'
        f'<div class="mm-small">{plant["note"]}</div></div>',
        unsafe_allow_html=True,
    )
    if plant.get("next_at"):
        st.progress(plant["progress"], text=f'{plant["total_points"]} points · next: {plant["next_name"]} at {plant["next_at"]}')
    else:
        st.progress(1.0, text=f'{plant["total_points"]} points · fully grown')


def render_badges(catalogue: list[dict[str, Any]], columns: int = 3) -> None:
    cols = st.columns(columns)
    for index, badge in enumerate(catalogue):
        with cols[index % columns]:
            locked = "locked" if not badge["earned"] else ""
            st.markdown(
                f'<div class="mm-badge {locked}">'
                f'<div class="emoji">{badge["emoji"]}</div>'
                f'<div><div class="name">{html.escape(badge["name"])}</div>'
                f'<div class="desc">{html.escape(badge["description"])}</div></div></div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Recommendations and explainability
# ---------------------------------------------------------------------------

def render_recommendations(
    matches: Iterable[RecommendationMatch],
    user_id: int,
    key_prefix: str,
) -> None:
    matches = list(matches)
    if not matches:
        return
    existing = {h["name"].lower() for h in habits.list_habits(user_id, active_only=False)}
    for match in matches:
        rec = match.recommendation
        with st.container(border=True):
            top = st.columns([0.78, 0.22])
            with top[0]:
                st.markdown(f"#### {html.escape(rec.title)}")
                st.markdown(f'<span class="mm-pill mint">{html.escape(rec.category)}</span> '
                            f'<span class="mm-pill">{rec.duration_minutes} min</span> '
                            f'<span class="mm-pill peach">{html.escape(rec.energy_level)} energy</span>',
                            unsafe_allow_html=True)
                st.write(rec.summary)
            with top[1]:
                st.markdown(f'<div class="mm-small">Score {match.score:g}</div>', unsafe_allow_html=True)

            with st.expander("How to do it"):
                st.markdown(f"**Why this may help:** {rec.why}")
                for step in rec.steps:
                    st.markdown(f"- {step}")
                if rec.caution:
                    st.caption(f"Take care: {rec.caution}")

            template = rec.habit_template
            if template:
                already = template["name"].lower() in existing
                if already:
                    st.caption("Already in your habits.")
                elif st.button(
                    "Add this as a habit",
                    key=f"add_{key_prefix}_{rec.id}",
                    help="Optional. You can edit or remove it later.",
                ):
                    habits.create_habit(
                        user_id,
                        name=template["name"],
                        category=template.get("category", "wellbeing"),
                        target_value=template.get("target_value", 1),
                        unit=template.get("unit", "time"),
                        points=template.get("points", 10),
                        target_days_per_week=template.get("target_days_per_week", 5),
                    )
                    st.toast("Added to your habits. You can edit it there.")
                    st.rerun()
            st.caption(
                "This is an optional self-help suggestion, not a prescription or a diagnosis."
            )


def render_professional(matches: Iterable[RecommendationMatch]) -> None:
    matches = list(matches)
    if not matches:
        return
    st.markdown(
        '<div class="mm-card-warm">'
        '<div class="mm-label">A note about extra support</div>'
        "<p style='margin-bottom:0.4rem'>A counsellor, doctor or mental health professional can offer "
        "assessment and options that this app cannot. Reaching out is not a sign that self-help failed.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    rec = matches[0].recommendation
    with st.expander("What talking to a professional could look like"):
        st.write(rec.summary)
        for step in rec.steps:
            st.markdown(f"- {step}")
        st.caption(rec.caution or "MindMate cannot diagnose or treat any condition.")


def render_safety_plan(matches: Iterable[RecommendationMatch]) -> None:
    matches = list(matches)
    if not matches:
        return
    rec = matches[0].recommendation
    st.markdown(
        f"""
        <div class="mm-safe">
          <div class="title">🛟 {html.escape(rec.title)}</div>
          <p style="margin-bottom:0.4rem">{html.escape(rec.summary)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Open the safety plan steps"):
        for step in rec.steps:
            st.markdown(f"- {step}")
        st.caption(rec.caution or "")


def render_rule_trace(result: InferenceResult | None) -> None:
    if result is None or not result.fired_rules:
        st.info("No rule trace is available for this turn yet.")
        return
    st.markdown("#### The reasoning, step by step")
    st.caption(
        "Forward chaining: the engine evaluates every rule against working memory, fires the highest-salience "
        "matching rule, adds its conclusions, then repeats. Each rule fires at most once."
    )
    rows = []
    for fired in result.fired_rules:
        rows.append(
            {
                "Step": fired.cycle,
                "Rule": fired.rule_id,
                "If": "; ".join(fired.matched_conditions),
                "Salience": fired.salience,
                "Then added": ", ".join(fired.added_facts) or "—",
                "Suggested": ", ".join(fired.recommended) or "—",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=min(420, 42 * len(rows) + 40))
    if result.derived_facts:
        st.markdown(
            "".join(f'<span class="mm-pill mint">{html.escape(f)}</span>' for f in result.derived_facts),
            unsafe_allow_html=True,
        )
    with st.expander("Why did the engine choose this path?"):
        for line in result.explanation_lines():
            st.markdown(f"- {line}")
    st.caption(
        "Rules are declarative IF-THEN productions stored in JSON. The reasoning is deterministic and does not use an LLM."
    )


def render_understanding(concerns: list[Any], attributes: dict[str, Any]) -> None:
    if not concerns:
        return
    pills = "".join(
        f'<span class="mm-pill">{c.emoji} {html.escape(c.label)}</span>' for c in concerns
    )
    context = []
    if attributes.get("duration"):
        context.append(f"duration: {attributes['duration']}")
    if attributes.get("impact"):
        context.append(f"impact: {attributes['impact']}")
    if attributes.get("sleep_hours"):
        context.append(f"sleep: {attributes['sleep_hours']} h")
    if attributes.get("support"):
        context.append(f"support: {attributes['support']}")
    context_html = f'<div class="mm-small">{html.escape(" · ".join(context))}</div>' if context else ""
    st.markdown(
        f'<div class="mm-card-soft"><div class="mm-label">What MindMate understood</div>{pills}{context_html}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Crisis resources
# ---------------------------------------------------------------------------

def crisis_banner(compact: bool = False) -> None:
    st.markdown(
        """
        <div class="mm-safe">
          <div class="title">If you are in immediate danger, call 112 (India).</div>
          <div>For mental health support, call <strong>Tele-MANAS on 14416</strong> (24/7, free).
          You do not need the right words, and you do not have to be alone.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_resources(resources: list[dict[str, Any]], columns: int = 2) -> None:
    cols = st.columns(columns)
    for index, resource in enumerate(resources):
        with cols[index % columns]:
            number = html.escape(str(resource.get("number", "")))
            alt = resource.get("alternate")
            alt_html = f'<div class="mm-small">Also: {html.escape(alt)}</div>' if alt else ""
            st.markdown(
                f"""
                <div class="mm-resource">
                  <div class="name" style="font-weight:650">{html.escape(resource.get("name", ""))}</div>
                  <a class="number" href="tel:{number}">{number}</a>
                  {alt_html}
                  <div class="mm-small" style="margin-top:0.25rem">{html.escape(resource.get("availability", ""))}</div>
                  <div class="mm-small" style="margin-top:0.35rem">{html.escape(resource.get("when", ""))}</div>
                  <div class="mm-small" style="margin-top:0.25rem;opacity:0.75">Source: {html.escape(resource.get("source", ""))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def empty_state(title: str, text: str, emoji: str = "🌱") -> None:
    st.markdown(
        f'<div class="mm-card" style="text-align:center;padding:2rem">'
        f'<div style="font-size:2rem">{emoji}</div>'
        f'<h3 style="margin:0.4rem 0">{html.escape(title)}</h3>'
        f'<div class="mm-muted">{html.escape(text)}</div></div>',
        unsafe_allow_html=True,
    )
