"""Public landing page and legal pages.

The landing page is intentionally product-like rather than dashboard-like: a
soft editorial hero, generous whitespace, a quiet nav bar, and three concrete
explanations of what MindMate actually does. It uses only local CSS and inline
SVG, so the page works offline.
"""

from __future__ import annotations

import html

import streamlit as st

from ...config import APP_NAME, APP_TAGLINE, QUOTES, VERSION
from ...knowledge_base import KnowledgeBase
from ..theme import is_dark


def _quote() -> str:
    from datetime import date

    return QUOTES[date.today().toordinal() % len(QUOTES)]


def _nav() -> None:
    dark = is_dark()
    theme_target = "light" if dark else "dark"
    theme_icon = "☀︎" if dark else "☾"
    st.markdown(
        f"""
        <div class="mm-landing">
          <nav class="mm-nav">
            <a class="mm-logo" href="?view=landing" aria-label="{APP_NAME} home">
              <span class="mm-logo-mark">✿</span>
              <span class="mm-logo-name">{APP_NAME}</span>
            </a>
            <div class="mm-navlinks">
              <a href="#approach">Our approach</a>
              <a href="#mood">Mood &amp; habits</a>
              <a href="#expert">The expert system</a>
            </div>
            <div class="mm-nav-actions">
              <a class="mm-theme-link" href="?theme={theme_target}" aria-label="Switch theme">{theme_icon}</a>
              <a class="mm-nav-login" href="?view=login">Log in</a>
              <a class="mm-nav-cta" href="?view=signup">Get started</a>
            </div>
          </nav>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _hero() -> None:
    st.markdown(
        f"""
        <section class="mm-hero-grid">
          <div>
            <div class="mm-eyebrow">A gentler kind of mental wellness tool</div>
            <h1 class="mm-display">A softer place to land on <em>hard days.</em></h1>
            <p class="mm-lede">
              MindMate helps you notice how you feel, build small habits that fit your real life,
              and find a next step without judgement. No score to chase. No streak to protect.
            </p>
            <div class="mm-cta-row">
              <a class="mm-cta-primary" href="?view=signup">Create your private space</a>
              <a class="mm-cta-secondary" href="?view=login">I already have an account</a>
            </div>
            <div class="mm-trust">
              <span>Stored on this device</span>
              <span>No external AI</span>
              <span>No diagnosis</span>
            </div>
          </div>
          <div class="mm-visual" aria-hidden="true">
            <div class="mm-orb one"></div>
            <div class="mm-orb two"></div>
            <div class="mm-phone">
              <div class="mm-phone-top">
                <span class="mm-phone-kicker">Today · a small check-in</span>
                <span class="mm-phone-dot"></span>
              </div>
              <div class="mm-phone-title">How are you,<br>really?</div>
              <div class="mm-mood-dots">
                <div class="mm-mood-dot">🌧️</div>
                <div class="mm-mood-dot">🌫️</div>
                <div class="mm-mood-dot active">🌤️</div>
                <div class="mm-mood-dot">🌿</div>
                <div class="mm-mood-dot">🌻</div>
              </div>
              <div class="mm-phone-quote">“You don't have to figure everything out today.”</div>
            </div>
            <div class="mm-float-card">
              <div class="mm-label">A gentle next step</div>
              <div style="font-weight:600;margin-bottom:0.15rem">10-minute walk</div>
              <div class="mm-small">Optional · +10 effort points</div>
            </div>
          </div>
        </section>
        <div class="mm-band">
          <div class="mm-band-item"><strong>Private by design</strong> local SQLite, export or delete anytime</div>
          <div class="mm-band-item"><strong>Human-paced</strong> no streak penalties, no guilt copy</div>
          <div class="mm-band-item"><strong>Clear reasoning</strong> IF–THEN rules, not a black box</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _approach() -> None:
    st.markdown(
        """
        <section class="mm-section" id="approach">
          <div class="mm-section-head">
            <div class="mm-eyebrow">What MindMate is for</div>
            <h2>Support that meets you where you are.</h2>
            <p>Three quiet tools, designed to be useful on a good day and possible on a difficult one.</p>
          </div>
          <div class="mm-feature-grid">
            <article class="mm-feature">
              <div class="mm-feature-art mood">
                <div class="mm-art-bubble" style="width:52px;height:52px;left:20px;top:16px"></div>
                <div class="mm-art-bubble" style="width:26px;height:26px;right:34px;top:38px;background:var(--mm-sage);opacity:0.35"></div>
              </div>
              <h3>Notice, without judging</h3>
              <p>A ten-second mood check-in, then a question that fits the feeling — not a generic form.</p>
              <ul>
                <li>Mood-specific prompts for low, sad, anxious, angry and happy days</li>
                <li>Optional context: sleep, energy, what contributed</li>
                <li>Patterns shown as snapshots, never as a verdict</li>
              </ul>
            </article>
            <article class="mm-feature">
              <div class="mm-feature-art habit">
                <div class="mm-art-bubble" style="width:44px;height:44px;left:30px;top:22px;background:var(--mm-sage);opacity:0.4"></div>
                <div class="mm-art-bubble" style="width:18px;height:18px;right:38px;top:24px"></div>
              </div>
              <h3>Small habits, fully yours</h3>
              <p>Create a habit that is almost too easy. Edit the name, goal, schedule or points whenever life changes.</p>
              <ul>
                <li>Daily completion with one entry per habit</li>
                <li>Editable schedules and weekly targets</li>
                <li>Missing a day never removes earned points</li>
              </ul>
            </article>
            <article class="mm-feature">
              <div class="mm-feature-art expert">
                <div class="mm-art-bubble" style="width:60px;height:60px;right:18px;top:14px;background:var(--mm-accent);opacity:0.18"></div>
                <div class="mm-art-bubble" style="width:22px;height:22px;left:34px;bottom:16px;background:var(--mm-sage);opacity:0.4"></div>
              </div>
              <h3>A transparent expert system</h3>
              <p>An explicit knowledge base turns what you share into a few optional, explainable suggestions.</p>
              <ul>
                <li>IF–THEN rules with salience and conflict resolution</li>
                <li>Safety gate before ordinary recommendations</li>
                <li>No large language model and no paid API</li>
              </ul>
            </article>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _mood_section() -> None:
    st.markdown(
        f"""
        <section class="mm-section" id="mood">
          <div class="mm-split">
            <div>
              <div class="mm-eyebrow">Mood &amp; habits</div>
              <h2 style="font-size:clamp(1.8rem,3.2vw,2.6rem);line-height:1.08;margin:0.35rem 0 0.8rem">
                A record of care,<br>not a performance.
              </h2>
              <p style="color:var(--mm-muted);max-width:48ch">
                Your mood history is a set of self-reported snapshots. A low day is not a failure,
                and a high day is not proof of recovery. The same is true of habits: the plant grows
                from effort, waits through breaks, and never wilts when you miss a day.
              </p>
              <div class="mm-cta-row" style="margin-top:1.2rem">
                <a class="mm-cta-secondary" href="?view=signup">Start a gentle routine</a>
              </div>
            </div>
            <div class="mm-quote-card">
              <div class="mark">“</div>
              <blockquote>{html.escape(_quote())}</blockquote>
              <cite>Today's note from MindMate</cite>
              <div style="margin-top:1.2rem;display:flex;gap:0.4rem;flex-wrap:wrap">
                <span class="mm-pill mint">🌱 Seed → Sprout</span>
                <span class="mm-pill">+10 for a walk</span>
                <span class="mm-pill peach">No missed-day penalty</span>
              </div>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _expert_section(kb: KnowledgeBase) -> None:
    st.markdown(
        f"""
        <section class="mm-section" id="expert">
          <div class="mm-section-head">
            <div class="mm-eyebrow">How the support is chosen</div>
            <h2>An expert system you can actually follow.</h2>
            <p>
              MindMate is not a chatbot guessing at a reply. It evaluates a JSON knowledge base of
              {len(kb.rules)} IF–THEN rules, fires the most specific matching rule, and repeats.
              A safety gate always runs first.
            </p>
          </div>
          <div class="mm-rule-flow">
            <div class="mm-rule-step">
              <div class="num">01</div>
              <strong>Notice</strong>
              <span>Free text and structured answers become facts: a concern, a duration, an impact, a preference.</span>
            </div>
            <div class="mm-rule-step">
              <div class="num">02</div>
              <strong>Check safety first</strong>
              <span>Crisis language pauses ordinary suggestions and offers direct, compassionate human support.</span>
            </div>
            <div class="mm-rule-step">
              <div class="num">03</div>
              <strong>Offer a small next step</strong>
              <span>Rules chain to optional activities, with the reasoning available if you want to see it.</span>
            </div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _safety_band() -> None:
    st.markdown(
        """
        <div class="mm-safety-band">
          <div>
            <h3>If today feels unsafe, please do not wait for an app.</h3>
            <p>In India, call <strong>112</strong> for immediate danger, or <strong>Tele-MANAS 14416</strong>
            for free 24/7 mental health support. MindMate cannot assess risk or provide crisis care.</p>
          </div>
          <div><span class="mm-pill rose">Not a crisis service</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _footer() -> None:
    st.markdown(
        f"""
        <footer class="mm-landing-footer">
          <div class="mm-footer-grid">
            <div class="mm-footer-brand">
              <div class="mm-logo" style="margin-bottom:0.6rem">
                <span class="mm-logo-mark">✿</span>
                <span class="mm-logo-name">{APP_NAME}</span>
              </div>
              <p>{APP_TAGLINE}. A student-built expert system for emotional support and healthy habits.
              It is not a medical device, diagnosis, treatment, or emergency service.</p>
              <div class="mm-small">v{VERSION} · academic project</div>
            </div>
            <div class="mm-footer-col">
              <h4>MindMate</h4>
              <a href="?view=signup">Create an account</a>
              <a href="?view=login">Log in</a>
              <a href="#approach">Our approach</a>
              <a href="#mood">Mood &amp; habits</a>
            </div>
            <div class="mm-footer-col">
              <h4>Support</h4>
              <a href="?view=resources">Helplines &amp; safety</a>
              <a href="tel:112">Emergency · 112</a>
              <a href="tel:14416">Tele-MANAS · 14416</a>
              <a href="?view=privacy#data">Privacy at a glance</a>
            </div>
            <div class="mm-footer-col">
              <h4>Legal</h4>
              <a href="?view=privacy">Privacy policy</a>
              <a href="?view=terms">Terms of use</a>
              <a href="?view=privacy#limits">Important limits</a>
            </div>
          </div>
          <div class="mm-footer-bottom">
            <span>© 2026 {APP_NAME}. Made for a calmer relationship with your own mind.</span>
            <span>Helpline numbers can change; verify them before relying on them.</span>
          </div>
        </footer>
        """,
        unsafe_allow_html=True,
    )


def render(kb: KnowledgeBase) -> None:
    _nav()
    _hero()
    _approach()
    _mood_section()
    _expert_section(kb)
    _safety_band()
    _footer()


def render_public_resources() -> None:
    """A public helpline page reachable from the landing footer."""
    _nav()
    st.markdown(
        """
        <section class="mm-section" style="padding-top:1.4rem">
          <div class="mm-section-head">
            <div class="mm-eyebrow">Support outside the app</div>
            <h2>If today feels unsafe, please do not wait for an app.</h2>
            <p>MindMate cannot assess risk or provide crisis care. These numbers are for India and are
            listed for convenience. Details can change, so verify them before relying on them.</p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    resources = [
        ("112", "Emergency services", "Immediate danger, medical emergency or police", "tel:112"),
        ("14416", "Tele-MANAS", "Free, 24/7 mental health support in multiple languages", "tel:14416"),
        ("1-800-891-4416", "Tele-MANAS toll-free", "Alternative national mental health helpline", "tel:18008914416"),
        ("1800-599-0019", "KIRAN", "24/7 national mental health rehabilitation helpline", "tel:18005990019"),
        ("+91-9820466726", "AASRA", "Confidential support for emotional distress", "tel:+919820466726"),
        ("+91-9999666555", "Vandrevala Foundation", "24/7 counselling support", "tel:+919999666555"),
        ("1098", "CHILDLINE", "Support for children and young people in distress", "tel:1098"),
    ]
    for number, name, description, link in resources:
        st.markdown(
            f'<div class="mm-resource"><div style="display:flex;justify-content:space-between;gap:0.8rem;flex-wrap:wrap">'
            f'<div><strong>{html.escape(name)}</strong>'
            f'<div class="mm-small">{html.escape(description)}</div></div>'
            f'<a class="number" href="{link}">{html.escape(number)}</a></div></div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="mm-card-warm" style="margin-top:1rem">If you are with someone who may be in danger, '
        "stay with them if it is safe to do so, remove access to means, and contact emergency services. "
        "MindMate is not a monitoring or emergency service.</div>",
        unsafe_allow_html=True,
    )
    _footer()


def render_legal(kind: str) -> None:
    """Render a readable privacy or terms page from the landing footer."""
    back = '<a class="mm-nav-login" href="?view=landing" style="padding-left:0">← Back to MindMate</a>'
    st.markdown(f'<div class="mm-landing">{back}</div>', unsafe_allow_html=True)
    if kind == "terms":
        title = "Terms of use"
        body = """
        <p><strong>MindMate is an academic project, not a clinical product.</strong> It does not diagnose
        depression, anxiety or any other condition, does not provide treatment or medical advice, and
        cannot assess whether you are safe. It is not a substitute for a qualified professional or an
        emergency service.</p>
        <p>You are responsible for the information you choose to enter. Use the app only on a device you
        trust, and use the export and delete controls if you share that device. The app is provided for
        educational demonstration and personal reflection, without warranties of any kind.</p>
        <p>If you are in immediate danger in India, call <strong>112</strong>. For mental health support,
        call <strong>Tele-MANAS 14416</strong> (24/7, free). Helpline details can change; verify them before
        relying on them.</p>
        """
    else:
        title = "Privacy policy"
        body = """
        <p><strong>Your data stays on this device.</strong> MindMate stores your profile, mood check-ins,
        habits, reflections, points, badges and optional saved transcripts in a local SQLite file. It does
        not call an external AI service, analytics provider or advertising network.</p>
        <p id="data">Passwords are derived with PBKDF2-HMAC-SHA256 and a per-user random salt. Plain-text
        passwords are never stored. A one-time recovery code is also stored only as a hash. You can export
        everything as JSON or delete the profile and every related record from Settings.</p>
        <p id="limits"><strong>Important limits.</strong> Chat transcripts are kept only in the browser
        session unless you explicitly turn on local saving. No app can guarantee privacy on a shared or
        compromised computer. MindMate is not a crisis service and does not monitor you in real time.</p>
        <p>The knowledge base and application code contain no other user's data. Helpline numbers are
        provided for convenience and may change.</p>
        """
    st.markdown(
        f"""
        <div class="mm-auth-wrap">
          <div class="mm-auth-card" style="margin-top:1.5rem;max-width:780px">
            <div class="mm-eyebrow">{APP_NAME} · legal</div>
            <h1>{title}</h1>
            <div style="color:var(--mm-muted);line-height:1.75">{body}</div>
            <div class="mm-auth-links"><a href="?view=landing">← Return to the landing page</a>
            <a href="?view=privacy">Privacy</a><a href="?view=terms">Terms</a></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
