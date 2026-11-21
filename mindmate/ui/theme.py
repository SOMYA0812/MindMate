"""MindMate's visual design system.

The palette is warm and quiet: cream paper, peach light, terracotta accents and
a little sage. Headings use a serif display face, body copy stays in a clean
sans-serif, and every surface is driven by CSS custom properties so the same
components work in light and dark mode.

All fonts are system fonts, so the interface still works completely offline.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

LIGHT = {
    "ink": "#2F2A26",
    "muted": "#7C746B",
    "accent": "#B96B4B",
    "accent_deep": "#8E4F37",
    "peach": "#F6D9C7",
    "peach_soft": "#FBEAE0",
    "cream": "#FBF7F1",
    "paper": "#FFFDFA",
    "sage": "#A9C3B1",
    "sage_deep": "#5E836B",
    "rose": "#E8C3C1",
    "sky": "#C9D9E4",
    "line": "rgba(74, 58, 46, 0.12)",
    "line_strong": "rgba(74, 58, 46, 0.20)",
    "shadow": "0 18px 45px rgba(90, 63, 44, 0.09)",
    "shadow_soft": "0 8px 24px rgba(90, 63, 44, 0.06)",
    "card": "#FFFDFA",
    "card_soft": "#F9F3EC",
    "input": "#FFFDFA",
    "sidebar": "#F6EFE7",
    "sidebar_soft": "#FBF5EE",
    "hero": "linear-gradient(132deg, #FBEEE5 0%, #FBF7F1 45%, #EDF3ED 100%)",
    "app_bg": (
        "radial-gradient(1100px 620px at 10% -8%, #F9E4D5 0%, rgba(249,228,213,0) 62%),"
        "radial-gradient(900px 540px at 96% 2%, #E8F0E7 0%, rgba(232,240,231,0) 58%),"
        "linear-gradient(180deg, #FDFAF6 0%, #FBF7F1 48%, #F8F4ED 100%)"
    ),
    "dark": False,
}

DARK = {
    "ink": "#F3EADF",
    "muted": "#B8ADA1",
    "accent": "#E0A17F",
    "accent_deep": "#F2C2A6",
    "peach": "#3B2D26",
    "peach_soft": "#30251F",
    "cream": "#171310",
    "paper": "#211B17",
    "sage": "#6F907B",
    "sage_deep": "#A9CBB5",
    "rose": "#4B3232",
    "sky": "#334650",
    "line": "rgba(243, 234, 223, 0.14)",
    "line_strong": "rgba(243, 234, 223, 0.25)",
    "shadow": "0 18px 45px rgba(0, 0, 0, 0.34)",
    "shadow_soft": "0 8px 24px rgba(0, 0, 0, 0.24)",
    "card": "#241E19",
    "card_soft": "#2B231D",
    "input": "#2A231E",
    "sidebar": "#1C1713",
    "sidebar_soft": "#241E19",
    "hero": "linear-gradient(132deg, #342720 0%, #231C18 48%, #202A24 100%)",
    "app_bg": (
        "radial-gradient(1100px 620px at 8% -8%, #3A2A22 0%, rgba(58,42,34,0) 60%),"
        "radial-gradient(900px 540px at 96% 2%, #233129 0%, rgba(35,49,41,0) 58%),"
        "linear-gradient(180deg, #191411 0%, #171310 52%, #14110E 100%)"
    ),
    "dark": True,
}

PALETTE = LIGHT


def is_dark() -> bool:
    return st.session_state.get("theme", "light") == "dark"


def palette() -> dict[str, Any]:
    return DARK if is_dark() else LIGHT


def mood_tone(color: str) -> str:
    """Return a low-opacity tint usable on cards in either theme."""
    return f"{color}22" if not is_dark() else f"{color}33"


def _css_variables(tokens: dict[str, Any]) -> str:
    return f"""
  --mm-ink: {tokens['ink']};
  --mm-muted: {tokens['muted']};
  --mm-accent: {tokens['accent']};
  --mm-accent-deep: {tokens['accent_deep']};
  --mm-peach: {tokens['peach']};
  --mm-peach-soft: {tokens['peach_soft']};
  --mm-cream: {tokens['cream']};
  --mm-paper: {tokens['paper']};
  --mm-sage: {tokens['sage']};
  --mm-sage-deep: {tokens['sage_deep']};
  --mm-rose: {tokens['rose']};
  --mm-sky: {tokens['sky']};
  --mm-line: {tokens['line']};
  --mm-line-strong: {tokens['line_strong']};
  --mm-shadow: {tokens['shadow']};
  --mm-shadow-soft: {tokens['shadow_soft']};
  --mm-card: {tokens['card']};
  --mm-card-soft: {tokens['card_soft']};
  --mm-input: {tokens['input']};
  --mm-sidebar: {tokens['sidebar']};
  --mm-sidebar-soft: {tokens['sidebar_soft']};
  --mm-hero: {tokens['hero']};
  --mm-app-bg: {tokens['app_bg']};
  --mm-pill: {'rgba(224,161,127,0.16)' if tokens['dark'] else '#F8E9DD'};
  --mm-pill-ink: {'#F2C2A6' if tokens['dark'] else '#8E4F37'};
  --mm-mint: {'rgba(111,144,123,0.18)' if tokens['dark'] else '#E7F1EA'};
  --mm-mint-ink: {'#A9CBB5' if tokens['dark'] else '#4F7560'};
  --mm-alert: {'rgba(120,53,53,0.24)' if tokens['dark'] else '#FCEFEC'};
  --mm-alert-line: {'rgba(224,151,140,0.32)' if tokens['dark'] else 'rgba(185,107,75,0.28)'};
  --mm-alert-ink: {'#F3C3B7' if tokens['dark'] else '#8E4F3C'};
  --mm-safe: {'rgba(115,42,52,0.22)' if tokens['dark'] else '#FDF0F1'};
  --mm-safe-line: {'rgba(230,170,170,0.28)' if tokens['dark'] else 'rgba(170,82,94,0.22)'};
  --mm-safe-ink: {'#F0BFC4' if tokens['dark'] else '#8E3F4F'};
  --mm-nav-pill: {'rgba(255,253,250,0.06)' if tokens['dark'] else 'rgba(255,255,255,0.66)'};
  --mm-on-accent: {'#231A15' if tokens['dark'] else '#FFF9F4'};
"""


def build_css(theme: str = "light") -> str:
    tokens = DARK if theme == "dark" else LIGHT
    variables = _css_variables(tokens)
    return f"""
<style>
:root {{{variables}}}

html {{ color-scheme: {'dark' if tokens['dark'] else 'light'}; }}
html, body, [class*="css"] {{
  font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  color: var(--mm-ink);
}}
body, .stApp {{ background: var(--mm-app-bg); color: var(--mm-ink); }}
.stApp {{ background: var(--mm-app-bg); }}

[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"] {{ right: 1rem; }}
[data-testid="stDecoration"] {{ display: none; }}
footer {{ visibility: hidden; }}
#MainMenu {{ visibility: hidden; }}

.block-container {{
  padding-top: 1.5rem;
  padding-bottom: 2.4rem;
  max-width: 1200px;
}}

h1, h2, h3, h4, h5 {{
  font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
  color: var(--mm-ink);
  letter-spacing: -0.025em;
  font-weight: 600;
}}
h1 {{ font-size: 2.35rem; line-height: 1.08; }}
h2 {{ font-size: 1.65rem; }}
h3 {{ font-size: 1.22rem; }}
p, li, label, .stMarkdown {{ color: var(--mm-ink); line-height: 1.68; }}
a {{ color: var(--mm-accent-deep); }}

/* ---------------- Sidebar ---------------- */
[data-testid="stSidebar"] {{
  background: var(--mm-sidebar);
  border-right: 1px solid var(--mm-line);
}}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.1rem; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
  color: var(--mm-ink);
}}
[data-testid="stSidebar"] .stRadio label {{
  padding: 0.34rem 0.42rem;
  border-radius: 12px;
  font-size: 0.95rem;
  transition: background 0.16s ease;
}}
[data-testid="stSidebar"] .stRadio label:hover {{ background: var(--mm-nav-pill); }}
[data-testid="stSidebar"] .stRadio label[data-selected="true"] {{
  background: var(--mm-peach-soft);
}}
[data-testid="stSidebar"] .stRadio label[data-selected="true"] p {{
  color: var(--mm-accent-deep); font-weight: 600;
}}

/* ---------------- Buttons ---------------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button,
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {{
  border-radius: 999px;
  border: 1px solid var(--mm-line-strong);
  background: var(--mm-paper);
  color: var(--mm-ink);
  font-weight: 550;
  padding: 0.46rem 1.05rem;
  transition: transform 0.16s ease, box-shadow 0.16s ease, background 0.16s ease, border-color 0.16s ease;
  box-shadow: none;
}}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{
  border-color: var(--mm-accent);
  color: var(--mm-accent-deep);
  background: var(--mm-peach-soft);
  transform: translateY(-1px);
  box-shadow: var(--mm-shadow-soft);
}}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"],
[data-testid="stBaseButton-primary"] {{
  background: var(--mm-accent);
  color: var(--mm-on-accent);
  border: 1px solid transparent;
}}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {{
  background: var(--mm-accent-deep);
  color: var(--mm-on-accent);
  filter: none;
}}

/* ---------------- Inputs ---------------- */
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div,
.stTextInput input, .stTextArea textarea, .stNumberInput input {{
  background: var(--mm-input) !important;
  color: var(--mm-ink) !important;
  border-color: var(--mm-line-strong) !important;
  border-radius: 12px !important;
}}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within {{
  border-color: var(--mm-accent) !important;
  box-shadow: 0 0 0 3px rgba(185,107,75,0.12) !important;
}}
[data-baseweb="menu"], [data-baseweb="popover"] {{
  background: var(--mm-card) !important; color: var(--mm-ink) !important;
}}
[data-testid="stChatInput"] {{
  border-radius: 20px;
  border: 1px solid var(--mm-line-strong);
  background: var(--mm-input);
  box-shadow: var(--mm-shadow-soft);
}}
[data-testid="stChatInput"] textarea {{ color: var(--mm-ink); }}

/* ---------------- Chat ---------------- */
[data-testid="stChatMessage"] {{
  background: var(--mm-card);
  border: 1px solid var(--mm-line);
  border-radius: 20px;
  padding: 0.85rem 1.05rem;
  box-shadow: var(--mm-shadow-soft);
  margin-bottom: 0.35rem;
}}
[data-testid="stChatMessage"] p {{ margin-bottom: 0.35rem; }}

/* ---------------- Metrics, expanders, tabs ---------------- */
[data-testid="stMetric"] {{
  background: var(--mm-card);
  border: 1px solid var(--mm-line);
  border-radius: 18px;
  padding: 1rem 1.1rem;
  box-shadow: var(--mm-shadow-soft);
}}
[data-testid="stMetricLabel"] {{ color: var(--mm-muted); }}
[data-testid="stMetricValue"] {{ color: var(--mm-ink); font-weight: 650; }}
[data-testid="stExpander"] {{
  border: 1px solid var(--mm-line);
  border-radius: 16px;
  background: var(--mm-card);
  overflow: hidden;
}}
[data-testid="stExpander"] summary {{ font-weight: 550; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 0.4rem; }}
.stTabs [data-baseweb="tab"] {{
  border-radius: 999px;
  padding: 0.35rem 0.9rem;
  background: var(--mm-nav-pill);
}}
.stTabs [aria-selected="true"] {{
  background: var(--mm-peach-soft) !important;
  color: var(--mm-accent-deep) !important;
}}
[data-testid="stDataFrame"] {{ background: var(--mm-card); }}
[data-testid="stAlert"] {{ border-radius: 14px; }}
[data-testid="stProgress"] [role="progressbar"] {{ background: var(--mm-line) !important; }}
[data-testid="stProgress"] [role="progressbar"] > div > div {{
  background-color: var(--mm-accent) !important;
}}
hr {{ border-color: var(--mm-line); }}

/* ---------------- Shared custom classes ---------------- */
.mm-hero {{
  background: var(--mm-hero);
  border: 1px solid var(--mm-line);
  border-radius: 28px;
  padding: 1.7rem 1.9rem;
  box-shadow: var(--mm-shadow-soft);
  margin-bottom: 1.1rem;
}}
.mm-hero h1 {{ margin: 0.1rem 0 0.45rem 0; font-size: 2.15rem; }}
.mm-hero p {{ margin: 0; color: var(--mm-muted); max-width: 64ch; }}
.mm-eyebrow {{
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.70rem;
  font-weight: 700;
  color: var(--mm-accent-deep);
  margin-bottom: 0.25rem;
}}
.mm-card {{
  background: var(--mm-card);
  border: 1px solid var(--mm-line);
  border-radius: 22px;
  padding: 1.15rem 1.25rem;
  box-shadow: var(--mm-shadow-soft);
  height: 100%;
}}
.mm-card-soft {{
  background: var(--mm-card-soft);
  border: 1px solid var(--mm-line);
  border-radius: 18px;
  padding: 1rem 1.15rem;
}}
.mm-card-warm {{
  background: var(--mm-peach-soft);
  border: 1px solid var(--mm-line);
  border-radius: 22px;
  padding: 1.15rem 1.25rem;
}}
.mm-card-alert {{
  background: var(--mm-alert);
  border: 1px solid var(--mm-alert-line);
  border-radius: 20px;
  padding: 1.05rem 1.2rem;
  color: var(--mm-ink);
}}
.mm-safe {{
  background: var(--mm-safe);
  border: 1px solid var(--mm-safe-line);
  border-radius: 20px;
  padding: 1.1rem 1.2rem;
  margin: 0.6rem 0 1rem 0;
}}
.mm-safe .title {{ font-weight: 700; color: var(--mm-safe-ink); margin-bottom: 0.3rem; }}
.mm-pill {{
  display: inline-block;
  padding: 0.18rem 0.66rem;
  border-radius: 999px;
  background: var(--mm-pill);
  color: var(--mm-pill-ink);
  font-size: 0.76rem;
  font-weight: 600;
  margin: 0.15rem 0.25rem 0.15rem 0;
}}
.mm-pill.mint {{ background: var(--mm-mint); color: var(--mm-mint-ink); }}
.mm-pill.peach {{ background: var(--mm-pill); color: var(--mm-pill-ink); }}
.mm-pill.rose {{ background: var(--mm-alert); color: var(--mm-alert-ink); }}
.mm-muted {{ color: var(--mm-muted); font-size: 0.9rem; }}
.mm-small {{ font-size: 0.82rem; color: var(--mm-muted); }}
.mm-label {{
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.69rem;
  font-weight: 700;
  color: var(--mm-muted);
  margin-bottom: 0.35rem;
}}
.mm-number {{
  font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  font-size: 1.9rem;
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1.1;
  color: var(--mm-ink);
}}
.mm-divider {{ height: 1px; background: var(--mm-line); margin: 0.9rem 0; }}
.mm-badge {{
  display: flex; gap: 0.6rem; align-items: flex-start;
  background: var(--mm-card);
  border: 1px solid var(--mm-line);
  border-radius: 16px; padding: 0.7rem 0.8rem; margin-bottom: 0.55rem;
}}
.mm-badge.locked {{ opacity: 0.5; filter: grayscale(0.35); }}
.mm-badge .emoji {{ font-size: 1.35rem; line-height: 1.1; }}
.mm-badge .name {{ font-weight: 600; font-size: 0.9rem; }}
.mm-badge .desc {{ font-size: 0.76rem; color: var(--mm-muted); }}
.mm-resource {{
  background: var(--mm-card);
  border: 1px solid var(--mm-line);
  border-radius: 18px; padding: 0.9rem 1rem; margin-bottom: 0.6rem;
}}
.mm-resource .number {{ font-size: 1.25rem; font-weight: 700; color: var(--mm-accent-deep); }}
.mm-resource a {{ color: var(--mm-accent-deep); text-decoration: none; }}
.mm-plant {{
  display: flex; align-items: center; justify-content: center;
  background: var(--mm-mint);
  border: 1px solid var(--mm-line);
  border-radius: 22px; padding: 0.6rem;
}}
.mm-mood-row {{ display: flex; gap: 0.5rem; flex-wrap: wrap; }}
.mm-check {{ display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.85rem; color: var(--mm-mint-ink); font-weight: 600; }}
.mm-quote {{
  border-left: 3px solid var(--mm-accent);
  padding: 0.15rem 0 0.15rem 0.9rem;
  color: var(--mm-muted);
  font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  font-size: 1.06rem;
  font-style: italic;
  line-height: 1.55;
}}
.mm-footer {{
  margin-top: 2.4rem; padding-top: 1rem;
  border-top: 1px solid var(--mm-line);
  color: var(--mm-muted); font-size: 0.78rem; line-height: 1.6;
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 20px; }}

/* ---------------- Mood-specific surfaces ---------------- */
.mm-mood-panel {{
  border-radius: 22px;
  border: 1px solid var(--mm-line);
  padding: 1.1rem 1.2rem;
  background: var(--mm-card);
}}
.mm-mood-banner {{ border-radius: 20px; padding: 1rem 1.15rem; border: 1px solid var(--mm-line); }}
.mm-mood-entry {{
  background: var(--mm-card);
  border: 1px solid var(--mm-line);
  border-radius: 18px;
  padding: 0.9rem 1rem;
  margin-bottom: 0.6rem;
}}
.mm-mood-date {{ font-size: 0.75rem; color: var(--mm-muted); letter-spacing: 0.04em; }}
.mm-mood-title {{ font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif; font-size: 1.15rem; font-weight: 600; }}
.mm-tag {{ display:inline-block; padding:0.14rem 0.55rem; border-radius:999px; background:var(--mm-card-soft); border:1px solid var(--mm-line); font-size:0.74rem; margin:0.15rem 0.2rem 0.15rem 0; }}

/* ---------------- Landing page ---------------- */
.mm-landing {{ margin-top: -0.4rem; }}
.mm-nav {{
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  padding: 0.55rem 0.65rem 0.55rem 1rem;
  border: 1px solid var(--mm-line);
  background: color-mix(in srgb, var(--mm-paper) 82%, transparent);
  border-radius: 999px;
  box-shadow: var(--mm-shadow-soft);
  margin-bottom: 2.2rem;
  position: relative; z-index: 3;
}}
.mm-logo {{ display:flex; align-items:center; gap:0.55rem; text-decoration:none !important; color:var(--mm-ink) !important; }}
.mm-logo-mark {{
  width: 34px; height: 34px; border-radius: 50%;
  background: var(--mm-accent);
  display:inline-flex; align-items:center; justify-content:center;
  color: var(--mm-on-accent); font-size: 1rem;
  box-shadow: inset 0 -4px 8px rgba(0,0,0,0.10);
}}
.mm-logo-name {{ font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif; font-size: 1.22rem; font-weight: 600; letter-spacing:-0.02em; }}
.mm-navlinks {{ display:flex; align-items:center; gap:1.25rem; }}
.mm-navlinks a {{ color:var(--mm-muted) !important; text-decoration:none !important; font-size:0.84rem; }}
.mm-navlinks a:hover {{ color:var(--mm-accent-deep) !important; }}
.mm-nav-actions {{ display:flex; align-items:center; gap:0.55rem; }}
.mm-nav-login {{ color:var(--mm-ink) !important; text-decoration:none !important; font-size:0.84rem; padding:0.45rem 0.8rem; }}
.mm-nav-cta {{
  display:inline-block; padding:0.58rem 1.15rem; border-radius:999px;
  background:var(--mm-accent); color:var(--mm-on-accent) !important;
  text-decoration:none !important; font-size:0.84rem; font-weight:600;
  transition:background 0.16s ease, transform 0.16s ease;
}}
.mm-nav-cta:hover {{ background:var(--mm-accent-deep); transform:translateY(-1px); }}
.mm-theme-link {{ text-decoration:none !important; font-size:1rem; color:var(--mm-muted) !important; padding:0.35rem 0.5rem; }}

.mm-hero-grid {{ display:grid; grid-template-columns: 1.02fr 0.98fr; gap: 3rem; align-items:center; padding: 1rem 0 3.2rem; }}
.mm-display {{
  font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
  font-size: clamp(2.6rem, 5.4vw, 4.55rem);
  line-height: 0.98;
  letter-spacing: -0.045em;
  font-weight: 500;
  margin: 0.55rem 0 1.15rem;
  color: var(--mm-ink);
}}
.mm-display em {{ font-style: italic; color: var(--mm-accent-deep); }}
.mm-lede {{ font-size: 1.04rem; line-height: 1.75; color: var(--mm-muted); max-width: 48ch; margin-bottom: 1.4rem; }}
.mm-cta-row {{ display:flex; gap:0.7rem; flex-wrap:wrap; align-items:center; }}
.mm-cta-primary {{
  display:inline-block; padding:0.82rem 1.4rem; border-radius:999px;
  background:var(--mm-accent); color:var(--mm-on-accent) !important;
  text-decoration:none !important; font-weight:600; font-size:0.92rem;
  box-shadow:0 10px 24px rgba(185,107,75,0.18);
  transition:transform 0.16s ease, background 0.16s ease;
}}
.mm-cta-primary:hover {{ transform:translateY(-2px); background:var(--mm-accent-deep); }}
.mm-cta-secondary {{
  display:inline-block; padding:0.78rem 1.3rem; border-radius:999px;
  border:1px solid var(--mm-line-strong); color:var(--mm-ink) !important;
  text-decoration:none !important; font-weight:550; font-size:0.92rem; background:var(--mm-nav-pill);
}}
.mm-cta-secondary:hover {{ border-color:var(--mm-accent); color:var(--mm-accent-deep) !important; }}
.mm-trust {{ display:flex; gap:1rem; flex-wrap:wrap; margin-top:1.6rem; color:var(--mm-muted); font-size:0.76rem; }}
.mm-trust span::before {{ content:"·"; color:var(--mm-accent); margin-right:0.45rem; }}
.mm-trust span:first-child::before {{ content:""; margin:0; }}

.mm-visual {{ position:relative; min-height:440px; display:flex; align-items:center; justify-content:center; }}
.mm-orb {{
  position:absolute; border-radius:50%; filter:blur(2px);
  background:radial-gradient(circle at 30% 30%, var(--mm-peach), rgba(246,217,199,0));
}}
.mm-orb.one {{ width:360px; height:360px; right:8%; top:2%; opacity:0.85; }}
.mm-orb.two {{ width:250px; height:250px; left:0; bottom:2%; background:radial-gradient(circle at 40% 40%, var(--mm-sage), rgba(169,195,177,0)); }}
.mm-phone {{
  position:relative; z-index:2; width:min(300px, 82%); border-radius:36px;
  background:var(--mm-card); border:1px solid var(--mm-line);
  box-shadow:0 30px 70px rgba(90,63,44,0.16);
  padding:1.15rem 1.05rem 1.3rem;
  transform:rotate(-2.5deg);
}}
.mm-phone-top {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:1.15rem; }}
.mm-phone-dot {{ width:8px; height:8px; border-radius:50%; background:var(--mm-sage); }}
.mm-phone-kicker {{ font-size:0.66rem; text-transform:uppercase; letter-spacing:0.12em; color:var(--mm-muted); }}
.mm-phone-title {{ font-family:"Iowan Old Style", Georgia, serif; font-size:1.35rem; line-height:1.2; margin:0.25rem 0 0.9rem; }}
.mm-mood-dots {{ display:flex; gap:0.35rem; margin:0.6rem 0 1rem; }}
.mm-mood-dot {{ flex:1; text-align:center; padding:0.42rem 0; border-radius:12px; border:1px solid var(--mm-line); font-size:0.9rem; }}
.mm-mood-dot.active {{ background:var(--mm-peach); border-color:var(--mm-accent); }}
.mm-phone-quote {{ background:var(--mm-card-soft); border-radius:14px; padding:0.8rem 0.85rem; font-family:"Iowan Old Style", Georgia, serif; font-style:italic; font-size:0.95rem; color:var(--mm-muted); line-height:1.5; }}
.mm-float-card {{
  position:absolute; z-index:3; right:0; bottom:10%; width:190px;
  background:var(--mm-card); border:1px solid var(--mm-line); border-radius:18px;
  padding:0.75rem 0.85rem; box-shadow:var(--mm-shadow); font-size:0.78rem;
  transform:rotate(3deg);
}}
.mm-float-card .mm-label {{ margin-bottom:0.2rem; }}

.mm-band {{ border-top:1px solid var(--mm-line); padding:1.25rem 0; display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; align-items:center; }}
.mm-band-item {{ display:flex; align-items:center; gap:0.55rem; color:var(--mm-muted); font-size:0.82rem; }}
.mm-band-item strong {{ color:var(--mm-ink); font-weight:600; }}

.mm-section {{ padding:4.2rem 0 0; }}
.mm-section-head {{ max-width: 55ch; margin-bottom: 1.9rem; }}
.mm-section-head h2 {{ font-size: clamp(1.8rem, 3.2vw, 2.6rem); line-height:1.08; margin:0.35rem 0 0.7rem; }}
.mm-section-head p {{ color:var(--mm-muted); margin:0; }}
.mm-feature-grid {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:1rem; }}
.mm-feature {{
  background:var(--mm-card); border:1px solid var(--mm-line); border-radius:24px;
  padding:1.25rem 1.2rem 1.35rem; box-shadow:var(--mm-shadow-soft);
}}
.mm-feature-art {{ height:86px; border-radius:16px; margin-bottom:1rem; position:relative; overflow:hidden; background:var(--mm-card-soft); }}
.mm-feature-art.mood {{ background:linear-gradient(135deg, var(--mm-peach-soft), var(--mm-card)); }}
.mm-feature-art.habit {{ background:linear-gradient(135deg, var(--mm-mint), var(--mm-card)); }}
.mm-feature-art.expert {{ background:linear-gradient(135deg, var(--mm-card-soft), var(--mm-peach-soft)); }}
.mm-art-bubble {{ position:absolute; border-radius:50%; background:var(--mm-accent); opacity:0.22; }}
.mm-feature h3 {{ margin:0 0 0.45rem; font-size:1.18rem; }}
.mm-feature p {{ color:var(--mm-muted); font-size:0.9rem; margin:0 0 0.75rem; }}
.mm-feature ul {{ margin:0; padding-left:1.05rem; color:var(--mm-muted); font-size:0.86rem; }}
.mm-feature li {{ margin-bottom:0.28rem; }}

.mm-split {{ display:grid; grid-template-columns:1fr 1fr; gap:2.8rem; align-items:center; }}
.mm-quote-card {{
  background:var(--mm-card); border:1px solid var(--mm-line); border-radius:28px;
  padding:2rem 2rem 1.8rem; box-shadow:var(--mm-shadow);
}}
.mm-quote-card .mark {{ font-family:Georgia, serif; font-size:3rem; line-height:0.8; color:var(--mm-accent); }}
.mm-quote-card blockquote {{ font-family:"Iowan Old Style", Georgia, serif; font-size:1.4rem; line-height:1.42; margin:0.6rem 0 1rem; }}
.mm-quote-card cite {{ color:var(--mm-muted); font-style:normal; font-size:0.8rem; }}

.mm-rule-flow {{ display:grid; grid-template-columns:repeat(3,1fr); gap:0.8rem; margin-top:1.3rem; }}
.mm-rule-step {{ border:1px solid var(--mm-line); background:var(--mm-card-soft); border-radius:18px; padding:0.95rem 1rem; }}
.mm-rule-step .num {{ font-family:"Iowan Old Style", Georgia, serif; font-size:1.3rem; color:var(--mm-accent-deep); }}
.mm-rule-step strong {{ display:block; margin:0.15rem 0 0.3rem; }}
.mm-rule-step span {{ color:var(--mm-muted); font-size:0.84rem; line-height:1.55; }}

.mm-safety-band {{
  margin-top:3.6rem; border-radius:26px; padding:1.4rem 1.6rem;
  background:var(--mm-safe); border:1px solid var(--mm-safe-line);
  display:flex; justify-content:space-between; gap:1.2rem; align-items:center; flex-wrap:wrap;
}}
.mm-safety-band h3 {{ margin:0 0 0.25rem; color:var(--mm-safe-ink); }}
.mm-safety-band p {{ margin:0; color:var(--mm-muted); font-size:0.88rem; }}

.mm-landing-footer {{ margin-top:3.8rem; border-top:1px solid var(--mm-line); padding:2rem 0 1.2rem; }}
.mm-footer-grid {{ display:grid; grid-template-columns:1.4fr 1fr 1fr 1fr; gap:1.5rem; }}
.mm-footer-brand p {{ color:var(--mm-muted); font-size:0.84rem; max-width:34ch; line-height:1.65; }}
.mm-footer-col h4 {{ font-family:inherit; font-size:0.74rem; text-transform:uppercase; letter-spacing:0.12em; color:var(--mm-muted); margin:0 0 0.6rem; }}
.mm-footer-col a {{ display:block; color:var(--mm-ink) !important; text-decoration:none !important; font-size:0.86rem; margin-bottom:0.42rem; }}
.mm-footer-col a:hover {{ color:var(--mm-accent-deep) !important; }}
.mm-footer-bottom {{ border-top:1px solid var(--mm-line); margin-top:1.6rem; padding-top:1rem; display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; color:var(--mm-muted); font-size:0.74rem; }}

/* ---------------- Authentication ---------------- */
.mm-auth-wrap {{ max-width: 1040px; margin: 0 auto; }}
.mm-auth-grid {{ display:grid; grid-template-columns: 0.92fr 1.08fr; gap:2.5rem; align-items:stretch; margin-top:1.6rem; }}
.mm-auth-aside {{
  background:var(--mm-hero); border:1px solid var(--mm-line); border-radius:28px;
  padding:2rem 1.9rem; box-shadow:var(--mm-shadow-soft); display:flex; flex-direction:column; justify-content:space-between;
}}
.mm-auth-aside h2 {{ font-size:2rem; line-height:1.12; margin:0.6rem 0 0.75rem; }}
.mm-auth-aside p {{ color:var(--mm-muted); font-size:0.92rem; }}
.mm-auth-card {{
  background:var(--mm-card); border:1px solid var(--mm-line); border-radius:28px;
  padding:1.7rem 1.8rem; box-shadow:var(--mm-shadow);
}}
.mm-auth-card h1 {{ font-size:2rem; margin:0.2rem 0 0.35rem; }}
.mm-auth-links {{ display:flex; justify-content:space-between; gap:0.8rem; flex-wrap:wrap; font-size:0.84rem; margin-top:0.6rem; }}
.mm-recovery {{
  background:var(--mm-card-soft); border:1px dashed var(--mm-accent);
  border-radius:16px; padding:1rem; font-family:Consolas, monospace;
  font-size:1.15rem; letter-spacing:0.08em; text-align:center; color:var(--mm-accent-deep);
  user-select:all;
}}

/* ---------------- Mobile ---------------- */
@media (max-width: 900px) {{
  .mm-hero-grid {{ grid-template-columns:1fr; gap:1.6rem; padding-bottom:1.6rem; }}
  .mm-visual {{ min-height:360px; }}
  .mm-feature-grid {{ grid-template-columns:1fr; }}
  .mm-split {{ grid-template-columns:1fr; gap:1.4rem; }}
  .mm-rule-flow {{ grid-template-columns:1fr; }}
  .mm-footer-grid {{ grid-template-columns:1fr 1fr; }}
  .mm-auth-grid {{ grid-template-columns:1fr; }}
  .mm-auth-aside {{ display:none; }}
  .mm-navlinks {{ display:none; }}
}}
@media (max-width: 720px) {{
  .block-container {{ padding-top:0.8rem; padding-left:0.85rem; padding-right:0.85rem; }}
  .mm-hero {{ padding:1.2rem 1.15rem; border-radius:20px; }}
  .mm-hero h1 {{ font-size:1.65rem; }}
  h1 {{ font-size:1.8rem; }}
  .mm-number {{ font-size:1.55rem; }}
  .mm-display {{ font-size:2.65rem; }}
  .mm-nav {{ padding:0.45rem 0.55rem 0.45rem 0.8rem; }}
  .mm-nav-login {{ display:none; }}
  .mm-phone {{ transform:none; }}
  .mm-float-card {{ display:none; }}
  .mm-footer-grid {{ grid-template-columns:1fr; }}
  .mm-cta-primary, .mm-cta-secondary {{ width:100%; text-align:center; }}
}}
</style>
"""


def inject_css() -> None:
    theme = st.session_state.get("theme", "light")
    st.markdown(build_css(theme), unsafe_allow_html=True)


def set_theme(theme: str) -> None:
    st.session_state["theme"] = "dark" if theme == "dark" else "light"
