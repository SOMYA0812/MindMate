"""Local account screens: sign-up, login, recovery and legacy claim.

Authentication is intentionally local. There is no email service, so recovery
uses a one-time code generated when credentials are created. The code is shown
once and stored only as a PBKDF2 hash.
"""

from __future__ import annotations

import html

import streamlit as st

from ...auth import (
    normalize_recovery_code,
    validate_password,
    validate_username,
)
from ...config import APP_NAME, APP_TAGLINE
from ...database import (
    create_account,
    get_legacy_users,
    get_preferences,
    reset_password_with_recovery,
    set_account_credentials,
    verify_login,
)
from ..theme import is_dark


def _topbar() -> None:
    dark = is_dark()
    theme_target = "light" if dark else "dark"
    theme_icon = "☀︎" if dark else "☾"
    st.markdown(
        f"""
        <nav class="mm-nav">
          <a class="mm-logo" href="?view=landing" aria-label="{APP_NAME} home">
            <span class="mm-logo-mark">✿</span>
            <span class="mm-logo-name">{APP_NAME}</span>
          </a>
          <div class="mm-nav-actions">
            <a class="mm-theme-link" href="?theme={theme_target}" aria-label="Switch theme">{theme_icon}</a>
            <a class="mm-nav-login" href="?view=landing">Back to home</a>
          </div>
        </nav>
        """,
        unsafe_allow_html=True,
    )


def _aside(kicker: str, title: str, copy: str, pills: list[str]) -> None:
    pill_html = "".join(f'<span class="mm-pill">{html.escape(pill)}</span>' for pill in pills)
    st.markdown(
        f"""
        <div class="mm-auth-aside">
          <div>
            <div class="mm-eyebrow">{html.escape(kicker)}</div>
            <h2>{title}</h2>
            <p>{copy}</p>
          </div>
          <div style="margin-top:1.4rem">{pill_html}</div>
          <div class="mm-small" style="margin-top:1rem">
            Local only · no external AI · export or delete any time
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _complete_login(user_id: int) -> None:
    prefs = get_preferences(int(user_id))
    st.session_state["user_id"] = int(user_id)
    st.session_state["theme"] = (
        prefs.get("theme") if prefs.get("theme") in {"light", "dark"}
        else st.session_state.get("theme", "light")
    )
    for key in ("auth_recovery", "auth_pending_user", "dialogue_state", "chat", "last_turn", "turn_seq"):
        st.session_state.pop(key, None)
    st.session_state["nav"] = "🏡 Home"
    st.query_params.clear()


def _go(view: str) -> None:
    st.query_params["view"] = view


# ---------------------------------------------------------------------------
# Sign up
# ---------------------------------------------------------------------------

def render_signup() -> None:
    _topbar()
    st.markdown('<div class="mm-auth-wrap">', unsafe_allow_html=True)
    left, right = st.columns([0.92, 1.08], gap="large")
    with left:
        _aside(
            "Create your space",
            "A private place to check in, at your pace.",
            "You will choose a local username and password. No email is required and nothing is sent "
            "to a server. Your recovery code is shown once at the end — keep it somewhere safe.",
            ["Stored on this device", "No streak pressure", "Password hashed"],
        )
    with right:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="mm-eyebrow">{APP_NAME} · first visit</div>
                <h1 style="margin:0.15rem 0 0.3rem">Create your account</h1>
                <div class="mm-muted" style="margin-bottom:0.9rem">
                  Takes less than a minute. Use a nickname if you prefer.
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.form("signup_form", clear_on_submit=False):
                display_name = st.text_input(
                    "What should MindMate call you?",
                    max_chars=60,
                    placeholder="A first name or nickname",
                )
                username = st.text_input(
                    "Username",
                    max_chars=32,
                    placeholder="letters, numbers, dots, dashes",
                    help="Used only to sign in on this device. It is not public.",
                )
                c1, c2 = st.columns(2)
                password = c1.text_input("Password", type="password", max_chars=200)
                confirm = c2.text_input("Confirm password", type="password", max_chars=200)
                st.caption("At least 8 characters, including a letter and a number.")
                consent = st.checkbox(
                    "I understand MindMate is an academic support tool, not a medical, diagnostic or crisis service."
                )
                storage = st.checkbox(
                    "I agree to the local storage of what I choose to enter on this device. I can export or delete it anytime."
                )
                submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)

            if submitted:
                problems = []
                if not display_name.strip():
                    problems.append("Please add a name or nickname.")
                username_error = validate_username(username)
                if username_error:
                    problems.append(username_error)
                password_error = validate_password(password)
                if password_error:
                    problems.append(password_error)
                if password != confirm:
                    problems.append("The two passwords do not match.")
                if not consent or not storage:
                    problems.append("Please confirm both statements before continuing.")
                if problems:
                    for problem in problems:
                        st.error(problem)
                else:
                    try:
                        user_id, code = create_account(
                            display_name, username, password, consent_given=True
                        )
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["auth_pending_user"] = user_id
                        st.session_state["auth_recovery"] = {
                            "username": username.strip(),
                            "code": code,
                        }
                        st.rerun()

            st.markdown(
                '<div class="mm-auth-links"><span class="mm-muted">Already have an account?</span>'
                '<a href="?view=login" style="font-weight:600">Log in</a></div>',
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def render_login() -> None:
    _topbar()
    notice = st.session_state.pop("auth_notice", None)
    legacy = get_legacy_users()
    st.markdown('<div class="mm-auth-wrap">', unsafe_allow_html=True)
    left, right = st.columns([0.92, 1.08], gap="large")
    with left:
        _aside(
            "Welcome back",
            "You do not have to catch up.",
            "Sign in to pick up wherever you left off. Missed days are not counted against you, "
            "and nothing you recorded has been removed.",
            ["Your progress is kept", "No missed-day penalty"],
        )
    with right:
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="mm-eyebrow">{APP_NAME} · welcome back</div>
                <h1 style="margin:0.15rem 0 0.3rem">Log in</h1>
                <div class="mm-muted" style="margin-bottom:0.9rem">
                  Your account stays on this device.
                </div>
                """,
                unsafe_allow_html=True,
            )
            if notice:
                st.success(notice)
            with st.form("login_form"):
                username = st.text_input("Username", max_chars=32, autocomplete="username")
                password = st.text_input("Password", type="password", max_chars=200, autocomplete="current-password")
                submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
            if submitted:
                user = verify_login(username, password)
                if user is None:
                    st.error("That username and password did not match. You can try again or use your recovery code.")
                else:
                    _complete_login(int(user["id"]))
                    st.rerun()

            st.markdown(
                '<div class="mm-auth-links">'
                '<a href="?view=reset">Forgot your password?</a>'
                '<a href="?view=signup">Create an account</a></div>',
                unsafe_allow_html=True,
            )
            if legacy:
                names = ", ".join(html.escape(str(row.get("display_name") or "Profile")) for row in legacy[:3])
                st.markdown(
                    f'<div class="mm-card-soft" style="margin-top:1rem">'
                    f'<div class="mm-label">An older local profile exists</div>'
                    f'<div style="margin-bottom:0.45rem">{names}</div>'
                    f'<a href="?view=claim">Secure this existing profile →</a></div>',
                    unsafe_allow_html=True,
                )
    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Password reset with recovery code
# ---------------------------------------------------------------------------

def render_reset() -> None:
    _topbar()
    st.markdown('<div class="mm-auth-wrap">', unsafe_allow_html=True)
    left, right = st.columns([0.92, 1.08], gap="large")
    with left:
        _aside(
            "Account recovery",
            "Use the recovery code you saved.",
            "The code looks like MM-XXXX-XXXX-XXXX. It was shown once when the account was created. "
            "There is no email reset because MindMate does not connect to a mail service.",
            ["One-time recovery code", "Stored as a hash", "No email needed"],
        )
    with right:
        with st.container(border=True):
            st.markdown(
                """
                <div class="mm-eyebrow">Reset your password</div>
                <h1 style="margin:0.15rem 0 0.3rem">Forgot password</h1>
                <div class="mm-muted" style="margin-bottom:0.9rem">
                  Enter your username and recovery code, then choose a new password.
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.form("reset_form"):
                username = st.text_input("Username", max_chars=32, autocomplete="username")
                code = st.text_input(
                    "Recovery code",
                    max_chars=40,
                    placeholder="MM-XXXX-XXXX-XXXX",
                    autocomplete="off",
                )
                c1, c2 = st.columns(2)
                new_password = c1.text_input("New password", type="password", max_chars=200)
                confirm = c2.text_input("Confirm new password", type="password", max_chars=200)
                submitted = st.form_submit_button("Reset password", type="primary", use_container_width=True)
            if submitted:
                password_error = validate_password(new_password)
                if password_error:
                    st.error(password_error)
                elif new_password != confirm:
                    st.error("The two passwords do not match.")
                elif not username.strip() or not normalize_recovery_code(code):
                    st.error("Enter your username and the full recovery code.")
                else:
                    try:
                        ok = reset_password_with_recovery(username, code, new_password)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        if ok:
                            st.session_state["auth_notice"] = (
                                "Password updated. You can log in with your new password."
                            )
                            _go("login")
                            st.rerun()
                        else:
                            st.error(
                                "That username and recovery code did not match. Check capital letters and dashes."
                            )
            st.markdown(
                '<div class="mm-auth-links"><a href="?view=login">← Back to log in</a>'
                '<span class="mm-muted">No recovery code? You can create a new local account.</span></div>',
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Existing local profile without credentials
# ---------------------------------------------------------------------------

def render_claim() -> None:
    _topbar()
    legacy = get_legacy_users()
    st.markdown('<div class="mm-auth-wrap">', unsafe_allow_html=True)
    left, right = st.columns([0.92, 1.08], gap="large")
    with left:
        _aside(
            "One-time setup",
            "Keep the history you already have.",
            "This device already has a MindMate profile from before accounts were added. "
            "Add a username and password without losing any moods, habits or points.",
            ["Existing data preserved", "One-time setup", "No previous password needed"],
        )
    with right:
        with st.container(border=True):
            st.markdown(
                """
                <div class="mm-eyebrow">Secure an existing profile</div>
                <h1 style="margin:0.15rem 0 0.3rem">Add a password</h1>
                <div class="mm-muted" style="margin-bottom:0.9rem">
                  Choose the profile you want to keep, then set credentials for it.
                </div>
                """,
                unsafe_allow_html=True,
            )
            if not legacy:
                st.info(
                    "There is no unsecured profile on this device. You can log in or create a new account."
                )
                st.markdown(
                    '<div class="mm-auth-links"><a href="?view=login">Log in</a>'
                    '<a href="?view=signup">Create an account</a></div>',
                    unsafe_allow_html=True,
                )
            else:
                labels = {
                    int(row["id"]): f'{row.get("display_name") or "Profile"} · created {str(row.get("created_at") or "")[:10]}'
                    for row in legacy
                }
                with st.form("claim_form"):
                    selected = st.selectbox(
                        "Profile",
                        options=list(labels),
                        format_func=lambda uid: labels.get(uid, str(uid)),
                    )
                    username = st.text_input(
                        "Choose a username",
                        max_chars=32,
                        placeholder="letters, numbers, dots, dashes",
                    )
                    c1, c2 = st.columns(2)
                    password = c1.text_input("Choose a password", type="password", max_chars=200)
                    confirm = c2.text_input("Confirm password", type="password", max_chars=200)
                    st.caption("At least 8 characters, including a letter and a number.")
                    submitted = st.form_submit_button(
                        "Secure this profile", type="primary", use_container_width=True
                    )
                if submitted:
                    problems = []
                    username_error = validate_username(username)
                    if username_error:
                        problems.append(username_error)
                    password_error = validate_password(password)
                    if password_error:
                        problems.append(password_error)
                    if password != confirm:
                        problems.append("The two passwords do not match.")
                    if problems:
                        for problem in problems:
                            st.error(problem)
                    else:
                        try:
                            code = set_account_credentials(
                                int(selected), username, password
                            )
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.session_state["auth_pending_user"] = int(selected)
                            st.session_state["auth_recovery"] = {
                                "username": username.strip(),
                                "code": code,
                            }
                            st.rerun()
            st.markdown(
                '<div class="mm-auth-links"><a href="?view=login">← Back to log in</a>'
                '<a href="?view=signup">Create a new account</a></div>',
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# One-time recovery code
# ---------------------------------------------------------------------------

def has_pending_recovery() -> bool:
    return bool(st.session_state.get("auth_recovery") and st.session_state.get("auth_pending_user"))


def render_recovery() -> None:
    payload = st.session_state.get("auth_recovery") or {}
    user_id = int(st.session_state.get("auth_pending_user") or 0)
    code = str(payload.get("code") or "")
    username = str(payload.get("username") or "")
    _topbar()
    st.markdown('<div class="mm-auth-wrap" style="max-width:720px">', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            f"""
            <div class="mm-eyebrow">{APP_NAME} · one important step</div>
            <h1 style="margin:0.15rem 0 0.3rem">Save your recovery code</h1>
            <p class="mm-muted">This is the only way to reset your password, because MindMate has no email
            service. It will not be shown again.</p>
            <div class="mm-recovery">{html.escape(code)}</div>
            <div class="mm-small" style="margin-top:0.5rem">Username: <strong>{html.escape(username)}</strong></div>
            """,
            unsafe_allow_html=True,
        )
        st.download_button(
            "⬇️ Download the code as a text file",
            data=(
                f"MindMate recovery code\n"
                f"Username: {username}\n"
                f"Recovery code: {code}\n\n"
                "Keep this somewhere private. It can reset your local password.\n"
            ),
            file_name="mindmate-recovery-code.txt",
            mime="text/plain",
            use_container_width=True,
        )
        saved = st.checkbox(
            "I have saved this code somewhere private. I understand it will not be shown again."
        )
        if st.button(
            "Continue to MindMate",
            type="primary",
            use_container_width=True,
            disabled=not saved,
        ) and user_id:
            _complete_login(user_id)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
