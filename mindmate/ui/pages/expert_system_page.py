"""Transparency page: knowledge base, live forward-chaining demo, crisis rules."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from ...config import MOOD_LABELS
from ...engine.inference_engine import InferenceEngine
from ...engine.working_memory import WorkingMemory
from ...knowledge_base import KnowledgeBase
from ...services import rewards
from .. import components


def render(user_id: int, kb: KnowledgeBase, prefs: dict[str, Any]) -> None:
    components.page_header(
        "🧠",
        "How MindMate reasons",
        "MindMate is a knowledge-based expert system. This page exposes the rules, the safety gate, and a live "
        "forward-chaining trace — the same engine used by the conversation.",
    )

    stats = st.columns(5)
    stats[0].markdown(components.stat_card("Production rules", str(len(kb.rules)), "IF–THEN, JSON-declared"), unsafe_allow_html=True)
    stats[1].markdown(components.stat_card("Concern categories", str(len(kb.concerns)), "Evidence vocabulary"), unsafe_allow_html=True)
    stats[2].markdown(components.stat_card("Recommendations", str(len(kb.recommendations)), "Optional activities"), unsafe_allow_html=True)
    stats[3].markdown(components.stat_card("Crisis signals", str(len(kb.crisis.get("signals", []))), "Safety gate patterns"), unsafe_allow_html=True)
    stats[4].markdown(components.stat_card("Max cycles", str(kb.engine_config.get("max_cycles", 60)), "Termination guard"), unsafe_allow_html=True)

    st.markdown("---")
    components.section_title("Architecture at a glance")
    st.markdown(
        """
        <div style="display:flex;gap:0.55rem;flex-wrap:wrap;align-items:stretch">
          <div class="mm-card" style="flex:1;min-width:135px"><div class="mm-label">1 · Input</div>
            Free text + structured answers</div>
          <div style="align-self:center;color:#8B7BC7;font-size:1.2rem">→</div>
          <div class="mm-card-alert" style="flex:1;min-width:135px"><div class="mm-label">2 · Safety gate</div>
            Crisis patterns run first and pre-empt everything</div>
          <div style="align-self:center;color:#8B7BC7;font-size:1.2rem">→</div>
          <div class="mm-card" style="flex:1;min-width:135px"><div class="mm-label">3 · NLU</div>
            Concern evidence, negation, duration, impact</div>
          <div style="align-self:center;color:#8B7BC7;font-size:1.2rem">→</div>
          <div class="mm-card" style="flex:1;min-width:135px"><div class="mm-label">4 · Working memory</div>
            Facts + attributes</div>
          <div style="align-self:center;color:#8B7BC7;font-size:1.2rem">→</div>
          <div class="mm-card" style="flex:1;min-width:135px"><div class="mm-label">5 · Inference</div>
            Forward chaining, salience order</div>
          <div style="align-self:center;color:#8B7BC7;font-size:1.2rem">→</div>
          <div class="mm-card" style="flex:1;min-width:135px"><div class="mm-label">6 · Output</div>
            Explanation + optional suggestions</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["📚 Knowledge base", "⚙️ Live inference demo", "🛟 Crisis rules", "🔎 Algorithm"])

    with tabs[0]:
        _knowledge_base_tab(kb)
    with tabs[1]:
        _demo_tab(kb)
    with tabs[2]:
        _crisis_tab(kb)
    with tabs[3]:
        _algorithm_tab(kb)


def _knowledge_base_tab(kb: KnowledgeBase) -> None:
    st.markdown("#### Production rules")
    st.caption(
        f"Strategy: {kb.engine_config.get('strategy', 'forward_chaining')} · "
        f"Conflict resolution: {kb.engine_config.get('conflict_resolution', 'salience')}."
    )
    categories = sorted({rule.category for rule in kb.rules})
    c1, c2 = st.columns([1, 1])
    category = c1.selectbox("Filter by layer", ["All"] + categories, key="kb_category")
    search = c2.text_input("Search rules", placeholder="ID, title, IF condition…", key="kb_search")

    rules = [rule for rule in kb.rules if category == "All" or rule.category == category]
    if search.strip():
        needle = search.strip().lower()
        rules = [
            rule for rule in rules
            if needle in rule.id.lower() or needle in rule.title.lower()
            or any(needle in c.get("label", "").lower() for c in rule.conditions)
        ]
    rows = [
        {
            "ID": rule.id,
            "Salience": rule.salience,
            "Layer": rule.category,
            "Rule": rule.title,
            "IF": " AND ".join(c.get("label", "") for c in rule.conditions),
            "THEN": "; ".join(_action_text(a) for a in rule.actions),
        }
        for rule in rules
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=430)

    st.markdown("#### Rule layers")
    counts = pd.Series([rule.category for rule in kb.rules]).value_counts()
    st.bar_chart(counts, height=220)

    st.markdown("#### Concern vocabulary")
    concerns = pd.DataFrame(kb.concerns_as_rows())
    concerns.columns = ["ID", "Concern", "Description", "Example evidence", "Follow-up questions"]
    st.dataframe(concerns, hide_index=True, use_container_width=True)

    st.markdown("#### Recommendation catalogue")
    rec_rows = [
        {
            "ID": rec.id,
            "Title": rec.title,
            "Kind": rec.kind,
            "Energy": rec.energy_level,
            "Minutes": rec.duration_minutes,
            "Why": rec.why,
        }
        for rec in kb.recommendations.values()
    ]
    st.dataframe(pd.DataFrame(rec_rows), hide_index=True, use_container_width=True, height=320)


def _action_text(action: dict[str, Any]) -> str:
    kind = action.get("type")
    if kind == "assert":
        return f"assert {action['fact']}"
    if kind == "recommend":
        return f"recommend {action['recommendation']} (w={action.get('weight', 1)})"
    if kind == "flag":
        return f"flag {action['value']}"
    if kind == "advice":
        return "offer a supportive note"
    return kind or "?"


def _demo_tab(kb: KnowledgeBase) -> None:
    st.markdown("#### Try the exact engine the chat uses")
    st.caption(
        "This does not call an LLM. Select facts, run forward chaining, and read the trace. "
        "The engine fires the highest-salience matching rule, adds its conclusions, then re-evaluates."
    )
    concern_labels = {cid: f"{kb.concerns[cid].emoji} {kb.concerns[cid].label}" for cid in kb.concern_order}
    selected = st.multiselect(
        "Concerns (working-memory facts)",
        options=list(concern_labels),
        default=["sadness"],
        format_func=lambda cid: concern_labels.get(cid, cid),
        key="demo_concerns",
    )
    c1, c2, c3, c4 = st.columns(4)
    duration = c1.selectbox("Duration", ["days", "weeks", "months", "long_term"], index=2, key="demo_duration")
    impact = c2.selectbox("Impact", ["mild", "moderate", "severe", "severe_plus"], index=2, key="demo_impact")
    sleep_hours = c3.number_input("Sleep hours", 0.0, 24.0, 5.5, 0.5, key="demo_sleep")
    support = c4.selectbox("Support", ["has_support", "limited", "isolated"], index=1, key="demo_support")

    c5, c6, c7 = st.columns(3)
    energy = c5.selectbox("Energy", ["low", "okay", "high"], index=0, key="demo_energy")
    time_available = c6.selectbox("Time available", ["low", "medium", "high"], index=1, key="demo_time")
    preferences = c7.multiselect(
        "Preferences", ["outdoors", "social", "quiet", "creative", "physical", "structured"], key="demo_prefs"
    )

    if st.button("▶ Run forward chaining", type="primary", key="demo_run"):
        wm = WorkingMemory()
        for cid in selected:
            wm.assert_fact(f"concern:{cid}", source="demo")
        wm.set_attribute("duration", duration, source="demo")
        wm.set_attribute("impact", impact, source="demo")
        wm.set_attribute("distress", "high" if impact in {"severe", "severe_plus"} else ("moderate" if impact == "moderate" else "low"), source="demo")
        wm.set_attribute("sleep_hours", sleep_hours, source="demo")
        wm.set_attribute("support", support, source="demo")
        wm.set_attribute("energy", energy, source="demo")
        wm.set_attribute("time_available", time_available, source="demo")
        if preferences:
            wm.set_attribute("preferences", preferences, source="demo")

        result = InferenceEngine(kb).run(wm)
        st.success(
            f"{len(result.fired_rules)} rules fired across {result.cycles} cycles. "
            f"Final facts: {len(wm.predicates)}; recommendations selected: {len(result.recommendations)}."
        )
        components.render_rule_trace(result)

        st.markdown("#### Recommendation ranking")
        rec_rows = [
            {
                "Recommendation": match.recommendation.title,
                "Score": match.score,
                "Kind": match.recommendation.kind,
                "Triggered by": ", ".join(match.rule_ids),
            }
            for match in result.recommendations + result.professional_matches + result.safety_matches
        ]
        if rec_rows:
            st.dataframe(pd.DataFrame(rec_rows), hide_index=True, use_container_width=True)
        st.markdown("#### Working memory after inference")
        st.markdown(
            "".join(f'<span class="mm-pill">{fact}</span>' for fact in wm.facts_snapshot()),
            unsafe_allow_html=True,
        )
        attrs = ", ".join(f"{key} = {value}" for key, value in wm.attributes.items())
        st.caption(f"Attributes: {attrs}")
        if result.advice:
            st.markdown("#### Advice attached by rules")
            for advice in result.advice:
                st.markdown(f"- {advice}")


def _crisis_tab(kb: KnowledgeBase) -> None:
    st.markdown("#### The safety gate runs before ordinary inference")
    st.markdown(
        "Crisis patterns live in `knowledge_base/crisis_patterns.json`. Any non-`none` result switches the dialogue "
        "into a safety flow, and ordinary recommendations are withheld until the safety questions are addressed. "
        "The classifier cannot assess risk, and a negative result never proves safety."
    )
    rows = []
    for signal in kb.crisis.get("signals", []):
        rows.append(
            {
                "ID": signal.get("id"),
                "Category": signal.get("category"),
                "Level": signal.get("level"),
                "Label": signal.get("label"),
                "Patterns": len(signal.get("patterns", [])),
                "Third party": bool(signal.get("third_party")),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.markdown("#### Safety questions")
    for question in kb.crisis.get("safety_questions", []):
        st.markdown(f"**{question['id']}** · {question['question']}")
        st.caption(" · ".join(opt["label"] for opt in question.get("options", [])))

    st.markdown("#### Escalation wording rules")
    for item in kb.crisis.get("do_not", []):
        st.markdown(f"- {item}")

    st.markdown("#### Resources are centralised")
    st.caption("The same list appears in the Resources page and in every crisis turn.")
    components.render_resources(kb.crisis.get("resources", []))


def _algorithm_tab(kb: KnowledgeBase) -> None:
    st.markdown(
        """
        #### Forward chaining, precisely

        1. **Seed working memory.** User evidence becomes predicates such as `concern:sadness`, plus attributes
           such as `duration = months`.
        2. **Match.** Evaluate every rule's conditions against current facts. Conditions are ANDed; a rule may use
           facts, negated facts, attribute comparisons, counts, or "any of" groups.
        3. **Conflict resolution.** Among all matching unfired rules, choose the highest salience. Ties go to the
           rule with more conditions (specificity), then to declaration order. This makes behaviour deterministic.
        4. **Fire once.** Assert the rule's conclusions (for example `state:low_mood`) and record which
           recommendations it supports.
        5. **Repeat.** Newly asserted facts can match rules that were not applicable before. That is the chaining.
        6. **Terminate.** Stop when no unfired rule matches, or at the cycle limit. Rules never fire twice, so the
           process is finite.

        #### Worked example

        ```
        concern:sadness, duration = months, impact = severe
          └─ A01 (salience 80) asserts state:low_mood
          └─ A02 (salience 85) asserts state:persistent_low_mood
          └─ B01 (salience 70) sees state:low_mood → need:behavioural_activation
          └─ C02 (salience 58) sees that need → recommends walk_10, journaling_5, values_reflection
          └─ E01 (salience 89) sees months + severe → need:professional_support
        ```

        The UI shows the real trace for each conversation, not a post-hoc story.

        #### What this is not

        - It is not a neural chatbot and does not call a language model.
        - It is not a diagnostic engine. Rules encode support-planning heuristics reviewed for this project,
          not clinical decision rules.
        - It cannot assess suicide risk. The crisis layer is a conservative prompt for human help.
        """
    )
    st.markdown("#### Engine configuration")
    st.json(kb.engine_config)
