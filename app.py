"""MindMate — entry point.

Run with:
    streamlit run app.py

The file handles security, theme bootstrap, navigation and the sidebar. Each
page lives in ``mindmate/ui/pages``. Public views (landing, sign-up, login,
legal) are selected with ``?view=...`` so the landing page links work like a
normal website.
"""

from __future__ import annotations

import streamlit as st

from mindmate.config import APP_NAME, APP_TAGLINE, VERSION
from mindmate.database import get_preferences, get_user, init_db, update_preferences
from mindmate.services import habits, rewards
from mindmate.ui import state as ui_state
from mindmate.ui.pages import (
    auth_page,
    chat,
    habits_page,
    home,
    landing_page,
    mood_page,
    reflection_page,
    resources_page,
    rewards_page,
    settings_page,
    summary_page,
)
from mindmate.ui.theme import inject_css, is_dark, set_theme

st.set_page_config(
    page_title=f"{APP_NAME} · Mental health support",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="auto",
)

init_db()

# A theme link from the landing page arrives as ?theme=dark. Apply it once,
# then remove it so later navigation does not keep overriding the preference.
_theme_param = st.query_params.get("theme")
if isinstance(_theme_param, list):
    _theme_param = _theme_param[0] if _theme_param else None
_theme_from_url = _theme_param in {"light", "dark"}
if _theme_from_url:
    st.session_state["theme"] = _theme_param
    del st.query_params["theme"]

st.session_state.setdefault("theme", "light")
inject_css()
kb = ui_state.cached_kb()

_view = st.query_params.get("view", "landing")
if isinstance(_view, list):
    _view = _view[0] if _view else "landing"


def _public_shell() -> None:
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
          [data-testid="stHeader"] { background: transparent; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Public views
# ---------------------------------------------------------------------------

_session_user = None
if "user_id" in st.session_state:
    _session_user = get_user(int(st.session_state["user_id"]))
    if _session_user is None:
        st.session_state.pop("user_id", None)

if _session_user is None:
    _public_shell()
    if auth_page.has_pending_recovery():
        auth_page.render_recovery()
        st.stop()
    if _view == "signup":
        auth_page.render_signup()
    elif _view == "login":
        auth_page.render_login()
    elif _view == "reset":
        auth_page.render_reset()
    elif _view == "claim":
        auth_page.render_claim()
    elif _view == "privacy":
        landing_page.render_legal("privacy")
    elif _view == "terms":
        landing_page.render_legal("terms")
    elif _view == "resources":
        landing_page.render_public_resources()
    else:
        landing_page.render(kb)
    st.stop()


# ---------------------------------------------------------------------------
# Signed-in application
# ---------------------------------------------------------------------------

user_id = int(st.session_state["user_id"])
user = _session_user

# Legal pages stay reachable while signed in, without leaving the account.
if _view in {"privacy", "terms"}:
    _public_shell()
    landing_page.render_legal(_view)
    st.stop()
if _view == "resources":
    st.session_state["nav"] = ui_state.NAV_RESOURCES

prefs = get_preferences(user_id)

# Load the saved theme once per signed-in user (login already does this, but a
# hard refresh needs it too).
if st.session_state.get("theme_user_id") != user_id and not _theme_from_url:
    saved_theme = prefs.get("theme")
    if saved_theme in {"light", "dark"}:
        st.session_state["theme"] = saved_theme
    st.session_state["theme_user_id"] = user_id
elif _theme_from_url and prefs.get("theme") != st.session_state.get("theme"):
    update_preferences(user_id, theme=st.session_state["theme"])
    st.session_state["theme_user_id"] = user_id

st.session_state.setdefault("nav", ui_state.NAV_HOME)
display_name = prefs.get("preferred_name") or user["display_name"] or "Friend"
username = user["username"] if "username" in user.keys() else ""
if _view != "landing":
    # A signed-in visit to a public URL should not show marketing screens again.
    st.query_params.pop("view", None)

with st.sidebar:
    st.markdown(
        f"""
        <div style="padding:0.2rem 0.15rem 0.6rem">
          <div style="font-family:'Iowan Old Style',Georgia,serif;font-size:1.55rem;
                      font-weight:600;letter-spacing:-0.03em;color:var(--mm-ink)">
            <span style="color:var(--mm-accent)">✿</span> {APP_NAME}
          </div>
          <div style="font-size:0.8rem;color:var(--mm-muted)">{APP_TAGLINE}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="mm-card-soft" style="padding:0.7rem 0.85rem;margin-bottom:0.7rem">'
        f'<div class="mm-label">Signed in locally</div>'
        f'<div style="font-weight:600">{display_name}</div>'
        f'<div class="mm-small">@{username}</div></div>'
        if username else
        f'<div class="mm-card-soft" style="padding:0.7rem 0.85rem;margin-bottom:0.7rem">'
        f'<div class="mm-label">Signed in locally</div>'
        f'<div style="font-weight:600">{display_name}</div></div>',
        unsafe_allow_html=True,
    )

    progress = habits.daily_progress(user_id)
    total_points = rewards.total_points(user_id)
    streak = rewards.current_streak(user_id)
    st.markdown(
        f"""
        <div class="mm-card-soft" style="padding:0.75rem 0.9rem;margin-bottom:0.8rem">
          <div style="display:flex;justify-content:space-between;font-size:0.84rem">
            <span>🌱 Habits today</span><strong>{progress['completed']}/{progress['total']}</strong>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:0.84rem;margin-top:0.25rem">
            <span>⭐ Points today</span><strong>{progress['points_today']}</strong>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:0.84rem;margin-top:0.25rem">
            <span>🫶 Total points</span><strong>{total_points}</strong>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:0.84rem;margin-top:0.25rem">
            <span>✨ Gentle streak</span><strong>{streak} day(s)</strong>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # The radio has its own widget key so page-level ``go_to`` calls can change
    # the logical page without mutating an already-instantiated widget key.
    current_nav = st.session_state.get("nav", ui_state.NAV_HOME)
    if current_nav not in ui_state.NAV_OPTIONS:
        current_nav = ui_state.NAV_HOME
    st.session_state["nav_radio"] = current_nav

    def _sync_nav() -> None:
        st.session_state["nav"] = st.session_state.get("nav_radio", ui_state.NAV_HOME)

    st.radio(
        "Navigate",
        ui_state.NAV_OPTIONS,
        key="nav_radio",
        on_change=_sync_nav,
        label_visibility="collapsed",
    )

    st.markdown(
        '<div class="mm-divider"></div>',
        unsafe_allow_html=True,
    )
    _current_dark = is_dark()
    _dark_toggle = st.toggle(
        "🌙 Dark mode",
        value=_current_dark,
        key=f"sidebar_dark_{st.session_state.get('theme', 'light')}",
        help="Applies to every page, chart and form. Your choice is saved with your profile.",
    )
    if _dark_toggle != _current_dark:
        set_theme("dark" if _dark_toggle else "light")
        update_preferences(user_id, theme=st.session_state["theme"])
        st.rerun()

    if st.button("Log out", use_container_width=True, key="sidebar_logout"):
        ui_state.logout()
        st.query_params["view"] = "landing"
        st.rerun()

    st.markdown(
        """
        <div class="mm-safe" style="padding:0.8rem 0.9rem;margin-top:0.8rem">
          <div class="title" style="font-size:0.86rem">Need urgent help?</div>
          <div style="font-size:0.8rem">Call <strong>112</strong> for immediate danger.</div>
          <div style="font-size:0.8rem">Tele-MANAS: <strong>14416</strong></div>
          <div style="font-size:0.72rem;opacity:0.8;margin-top:0.25rem">24/7 · free · India</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"v{VERSION} · academic project")


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

page = st.session_state.get("nav", ui_state.NAV_HOME)

if page == ui_state.NAV_HOME:
    home.render(user_id, kb, prefs)
elif page == ui_state.NAV_CHAT:
    chat.render(user_id, kb, prefs)
elif page == ui_state.NAV_HABITS:
    habits_page.render(user_id, kb, prefs)
elif page == ui_state.NAV_MOOD:
    mood_page.render(user_id, kb, prefs)
elif page == ui_state.NAV_REFLECTION:
    reflection_page.render(user_id, kb, prefs)
elif page == ui_state.NAV_REWARDS:
    rewards_page.render(user_id, kb, prefs)
elif page == ui_state.NAV_SUMMARY:
    summary_page.render(user_id, kb, prefs)
elif page == ui_state.NAV_RESOURCES:
    resources_page.render(user_id, kb, prefs)
elif page == ui_state.NAV_SETTINGS:
    settings_page.render(user_id, kb, prefs)
else:
    home.render(user_id, kb, prefs)
