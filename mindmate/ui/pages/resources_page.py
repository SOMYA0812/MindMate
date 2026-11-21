"""Mental health resources, crisis guidance and safety information."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ...knowledge_base import KnowledgeBase
from .. import components


def render(user_id: int, kb: KnowledgeBase, prefs: dict[str, Any]) -> None:
    components.page_header(
        "🛟",
        "Mental Health Resources",
        "If you are in immediate danger, call 112. For mental health support in India, Tele-MANAS (14416) is free "
        "and available 24/7. You do not need the right words.",
    )

    components.crisis_banner()

    st.markdown("### Helplines")
    st.caption(
        "These are public services and NGOs in India. Numbers can change; verify them before a live demonstration. "
        "If you are outside India, see the note further down."
    )
    components.render_resources(kb.crisis.get("resources", []))

    st.markdown("---")
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        components.section_title("When to contact someone")
        rows = [
            ("You are thinking about ending your life or hurting yourself", "Call 112 or Tele-MANAS 14416 now. Do not stay alone."),
            ("You have a plan, means, or have already taken something", "Call 112 or go to the nearest emergency department now."),
            ("Someone you know may be in immediate danger", "Stay with them if you can and call 112. Ask directly about suicide."),
            ("You feel unable to function day to day", "Contact a doctor, counsellor or Tele-MANAS and ask how to access care."),
            ("Low mood, anxiety or sleep problems persist for weeks", "Arrange a professional conversation. This app cannot diagnose."),
            ("You are not sure whether it is 'serious enough'", "You do not have to wait for a threshold. Asking for help early is reasonable."),
        ]
        st.dataframe(
            pd.DataFrame(rows, columns=["Situation", "Suggested step"]),
            hide_index=True,
            use_container_width=True,
        )
    with right:
        components.section_title("A simple safety plan")
        st.markdown(
            "When things feel unsafe, a concrete plan reduces the number of decisions you have to make."
        )
        for step in kb.crisis.get("safety_steps", []):
            st.markdown(f"- {step}")
        st.markdown(
            '<div class="mm-card-soft"><div class="mm-label">Keep it visible</div>'
            "Write 112 and 14416 somewhere you can see them, and save one trusted person's number "
            "on your home screen.</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    components.section_title("A grounding exercise you can try now")
    st.markdown(
        "This is a self-help exercise, not a treatment. Sit somewhere safe. If you feel dizzy, stop and breathe normally."
    )
    grounding = st.columns(5)
    prompts = [
        ("5", "things you can see"),
        ("4", "things you can touch"),
        ("3", "things you can hear"),
        ("2", "things you can smell"),
        ("1", "thing you can taste"),
    ]
    for column, (number, text) in zip(grounding, prompts):
        with column:
            st.markdown(
                f'<div class="mm-card" style="text-align:center"><div class="mm-number">{number}</div>'
                f'<div class="mm-small">{text}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")
    left2, right2 = st.columns([1, 1], gap="large")
    with left2:
        components.section_title("Talking to a professional")
        st.markdown(
            """
            - A college counsellor, family doctor, or licensed therapist are all reasonable first contacts.
            - You can write down two or three things you want help with before the appointment.
            - You can ask a trusted person to help you make the first call.
            - Tele-MANAS (14416) can also advise on how to access care.
            - Needing support is not a failure of self-help, and it is not a diagnosis.
            """
        )
    with right2:
        components.section_title("Supporting someone else")
        st.markdown(
            """
            - Ask directly: "Are you thinking about suicide?" Asking does not plant the idea.
            - Listen without debating or offering quick fixes.
            - If they are in immediate danger, stay with them and call 112.
            - Encourage them to call Tele-MANAS on 14416, and help them contact someone they trust.
            - Do not promise secrecy if someone is at risk. Tell another trusted adult or professional.
            - Look after yourself too; supporting someone is heavy.
            """
        )

    st.markdown("---")
    out_of_india = kb.crisis.get(
        "out_of_india_note",
        "If you are outside India, contact your local emergency number or a local crisis line.",
    )
    st.markdown(f'<div class="mm-card-warm"><div class="mm-label">Outside India</div>{out_of_india}</div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="mm-card-alert" style="margin-top:1rem">
          <div class="mm-label">Important limits</div>
          <p style="margin-bottom:0.3rem">MindMate is a student academic project. It does not provide diagnosis,
          treatment, medical advice, or crisis intervention. Its classifier is based on language patterns and
          cannot assess risk. A low result does not mean someone is safe.</p>
          <p style="margin-bottom:0">If you are in immediate danger, call <strong>112</strong>. For mental health
          support, call <strong>Tele-MANAS 14416</strong>.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
