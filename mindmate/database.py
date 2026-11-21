"""SQLite persistence for MindMate.

Design choices that matter for the project report:

* One short-lived connection per operation. Streamlit reruns the script often,
  so a global connection is a source of surprising bugs.
* Foreign keys with ON DELETE CASCADE make the "delete my data" control truly
  delete everything.
* ``points_ledger`` is append-only and idempotent (unique index). Rewards can
  therefore never be awarded twice for the same action on the same day.
* Free-text notes are optional; the app never requires a user to disclose
  anything. Chat transcripts are opt-in (stored only when the user enables it).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from .config import DATA_DIR, DB_PATH

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    consent_given INTEGER NOT NULL DEFAULT 0,
    consent_at TEXT,
    onboarding_complete INTEGER NOT NULL DEFAULT 0,
    username TEXT,
    password_hash TEXT,
    password_salt TEXT,
    password_iterations INTEGER NOT NULL DEFAULT 600000,
    recovery_hash TEXT,
    recovery_salt TEXT,
    recovery_iterations INTEGER NOT NULL DEFAULT 250000,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferred_name TEXT,
    time_available TEXT NOT NULL DEFAULT 'medium',
    preferred_activities TEXT NOT NULL DEFAULT '[]',
    contact_name TEXT,
    contact_phone TEXT,
    save_chat_history INTEGER NOT NULL DEFAULT 0,
    theme TEXT NOT NULL DEFAULT 'light',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mood_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entry_date TEXT NOT NULL,
    mood_score INTEGER NOT NULL CHECK (mood_score BETWEEN 1 AND 5),
    energy INTEGER CHECK (energy BETWEEN 1 AND 5),
    anxiety INTEGER CHECK (anxiety BETWEEN 0 AND 5),
    sleep_hours REAL CHECK (sleep_hours IS NULL OR (sleep_hours >= 0 AND sleep_hours <= 24)),
    emotion TEXT,
    mood_prompt TEXT,
    reason_tags TEXT NOT NULL DEFAULT '[]',
    note TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, entry_date)
);

CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'wellbeing',
    schedule_days TEXT NOT NULL DEFAULT '[0,1,2,3,4,5,6]',
    target_value REAL NOT NULL DEFAULT 1,
    unit TEXT NOT NULL DEFAULT 'time',
    points INTEGER NOT NULL DEFAULT 10 CHECK (points BETWEEN 0 AND 50),
    target_days_per_week INTEGER NOT NULL DEFAULT 7 CHECK (target_days_per_week BETWEEN 1 AND 7),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS habit_completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    completed_on TEXT NOT NULL,
    value REAL,
    note TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (habit_id, completed_on)
);

CREATE TABLE IF NOT EXISTS points_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    reference_id TEXT NOT NULL,
    points INTEGER NOT NULL,
    awarded_on TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, event_type, reference_id, awarded_on)
);

CREATE TABLE IF NOT EXISTS badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    badge_key TEXT NOT NULL,
    awarded_on TEXT NOT NULL,
    UNIQUE (user_id, badge_key)
);

CREATE TABLE IF NOT EXISTS daily_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    summary_date TEXT NOT NULL,
    mood_score INTEGER,
    habits_completed INTEGER NOT NULL DEFAULT 0,
    habits_total INTEGER NOT NULL DEFAULT 0,
    points_earned INTEGER NOT NULL DEFAULT 0,
    efforts_json TEXT NOT NULL DEFAULT '[]',
    suggestions_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    UNIQUE (user_id, summary_date)
);

CREATE TABLE IF NOT EXISTS reflections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reflection_date TEXT NOT NULL,
    went_well TEXT,
    grateful_for TEXT,
    tomorrow_step TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, reflection_date)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crisis_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    detected_at TEXT NOT NULL,
    level TEXT NOT NULL,
    signal_categories TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

TABLES_FOR_EXPORT = (
    "users",
    "user_preferences",
    "mood_entries",
    "habits",
    "habit_completions",
    "points_ledger",
    "badges",
    "daily_summaries",
    "reflections",
    "chat_messages",
    "crisis_events",
)


class DatabaseError(RuntimeError):
    """Raised for expected, user-facing database problems."""


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def get_db_path() -> Path:
    return Path(DB_PATH)


def _db_path_for(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else get_db_path()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = _db_path_for(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_conn(path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: str | Path | None = None) -> Path:
    db_path = _db_path_for(path)
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)
        _migrate_schema(conn)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return db_path


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """Add a column to an existing table without touching its data.

    SQLite has no ``ADD COLUMN IF NOT EXISTS``; this small helper keeps the
    upgrade path safe for databases created by earlier MindMate versions.
    """
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _migrate_schema(conn: sqlite3.Connection) -> None:
    # Accounts (added in the 1.1 release).
    _ensure_column(conn, "users", "username", "TEXT")
    _ensure_column(conn, "users", "password_hash", "TEXT")
    _ensure_column(conn, "users", "password_salt", "TEXT")
    _ensure_column(conn, "users", "password_iterations", "INTEGER NOT NULL DEFAULT 600000")
    _ensure_column(conn, "users", "recovery_hash", "TEXT")
    _ensure_column(conn, "users", "recovery_salt", "TEXT")
    _ensure_column(conn, "users", "recovery_iterations", "INTEGER NOT NULL DEFAULT 250000")
    _ensure_column(conn, "users", "last_login_at", "TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username "
        "ON users(username) WHERE username IS NOT NULL"
    )

    # Theme preference and richer habit/mood context.
    _ensure_column(conn, "user_preferences", "theme", "TEXT NOT NULL DEFAULT 'light'")
    _ensure_column(conn, "habits", "description", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(conn, "habits", "schedule_days", "TEXT NOT NULL DEFAULT '[0,1,2,3,4,5,6]'")
    _ensure_column(conn, "mood_entries", "emotion", "TEXT")
    _ensure_column(conn, "mood_entries", "mood_prompt", "TEXT")
    _ensure_column(conn, "mood_entries", "reason_tags", "TEXT NOT NULL DEFAULT '[]'")


# ---------------------------------------------------------------------------
# Users and preferences
# ---------------------------------------------------------------------------

def create_user(display_name: str, consent_given: bool = True,
                path: str | Path | None = None) -> int:
    name = (display_name or "").strip()[:60] or "Friend"
    with get_conn(path) as conn:
        cur = conn.execute(
            "INSERT INTO users (display_name, created_at, consent_given, consent_at) "
            "VALUES (?, ?, ?, ?)",
            (name, utc_now(), int(consent_given), utc_now() if consent_given else None),
        )
        user_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO user_preferences (user_id, preferred_name, updated_at) "
            "VALUES (?, ?, ?)",
            (user_id, name, utc_now()),
        )
    return user_id


def get_user(user_id: int, path: str | Path | None = None) -> sqlite3.Row | None:
    with get_conn(path) as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_first_user(path: str | Path | None = None) -> sqlite3.Row | None:
    with get_conn(path) as conn:
        return conn.execute("SELECT * FROM users ORDER BY id LIMIT 1").fetchone()


# ---------------------------------------------------------------------------
# Local accounts (password authentication)
# ---------------------------------------------------------------------------

def get_user_by_username(username: str, path: str | Path | None = None) -> dict[str, Any] | None:
    clean = (username or "").strip()
    if not clean:
        return None
    return query_one(
        "SELECT * FROM users WHERE lower(username) = lower(?)", (clean,), path
    )


def username_taken(username: str, exclude_user_id: int | None = None,
                   path: str | Path | None = None) -> bool:
    row = get_user_by_username(username, path)
    if row is None:
        return False
    return exclude_user_id is None or int(row["id"]) != int(exclude_user_id)


def get_legacy_users(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Profiles created before passwords existed, still needing credentials."""
    return query_all(
        "SELECT * FROM users WHERE onboarding_complete = 1 "
        "AND (username IS NULL OR username = '' OR password_hash IS NULL) ORDER BY id",
        (),
        path,
    )


def create_account(display_name: str, username: str, password: str,
                   consent_given: bool = True, recovery_code: str | None = None,
                   path: str | Path | None = None) -> tuple[int, str]:
    """Create a profile with hashed credentials. Returns ``(user_id, recovery_code)``."""
    from .auth import generate_recovery_code, hash_secret, validate_password, validate_username

    name = (display_name or "").strip()[:60] or "Friend"
    user_name = (username or "").strip()
    errors = [e for e in (validate_username(user_name), validate_password(password)) if e]
    if errors:
        raise ValueError(errors[0])
    if username_taken(user_name, path=path):
        raise ValueError("That username is already in use. Try another one.")

    code = recovery_code or generate_recovery_code()
    password_salt, password_hash, password_iterations = hash_secret(password)
    recovery_salt, recovery_hash, recovery_iterations = hash_secret(
        _normalize_recovery(code), iterations=250_000
    )
    with get_conn(path) as conn:
        cur = conn.execute(
            "INSERT INTO users (display_name, created_at, consent_given, consent_at, "
            "onboarding_complete, username, password_hash, password_salt, password_iterations, "
            "recovery_hash, recovery_salt, recovery_iterations) "
            "VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)",
            (name, utc_now(), int(consent_given), utc_now() if consent_given else None,
             user_name, password_hash, password_salt, password_iterations,
             recovery_hash, recovery_salt, recovery_iterations),
        )
        user_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO user_preferences (user_id, preferred_name, updated_at) VALUES (?, ?, ?)",
            (user_id, name, utc_now()),
        )
    return user_id, code


def _normalize_recovery(code: str) -> str:
    from .auth import normalize_recovery_code

    return normalize_recovery_code(code)


def set_account_credentials(user_id: int, username: str, password: str,
                            recovery_code: str | None = None,
                            path: str | Path | None = None) -> str:
    """Attach credentials to an existing local profile. Returns the recovery code."""
    from .auth import generate_recovery_code, hash_secret, validate_password, validate_username

    user_name = (username or "").strip()
    errors = [e for e in (validate_username(user_name), validate_password(password)) if e]
    if errors:
        raise ValueError(errors[0])
    if username_taken(user_name, exclude_user_id=user_id, path=path):
        raise ValueError("That username is already in use. Try another one.")
    row = get_user(user_id, path)
    if row is None:
        raise ValueError("Profile not found.")

    code = recovery_code or generate_recovery_code()
    password_salt, password_hash, password_iterations = hash_secret(password)
    recovery_salt, recovery_hash, recovery_iterations = hash_secret(
        _normalize_recovery(code), iterations=250_000
    )
    with get_conn(path) as conn:
        conn.execute(
            "UPDATE users SET username = ?, password_hash = ?, password_salt = ?, "
            "password_iterations = ?, recovery_hash = ?, recovery_salt = ?, "
            "recovery_iterations = ?, onboarding_complete = 1 WHERE id = ?",
            (user_name, password_hash, password_salt, password_iterations,
             recovery_hash, recovery_salt, recovery_iterations, user_id),
        )
    return code


def verify_login(username: str, password: str, path: str | Path | None = None) -> dict[str, Any] | None:
    """Return the user row on success, otherwise ``None``. Never reveals which part failed."""
    from .auth import verify_secret

    row = get_user_by_username(username, path)
    if row is None or not row.get("password_hash") or not row.get("password_salt"):
        return None
    if not verify_secret(
        password or "",
        row["password_salt"],
        row["password_hash"],
        int(row.get("password_iterations") or 600_000),
    ):
        return None
    with get_conn(path) as conn:
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (utc_now(), int(row["id"])))
    refreshed = get_user(int(row["id"]), path)
    return dict(refreshed) if refreshed else None


def reset_password_with_recovery(username: str, recovery_code: str, new_password: str,
                                 path: str | Path | None = None) -> bool:
    """Reset a password if the recovery code matches. Returns success."""
    from .auth import hash_secret, recovery_matches, validate_password

    error = validate_password(new_password)
    if error:
        raise ValueError(error)
    row = get_user_by_username(username, path)
    if row is None or not row.get("recovery_hash") or not row.get("recovery_salt"):
        return False
    if not recovery_matches(
        recovery_code,
        row["recovery_salt"],
        row["recovery_hash"],
        int(row.get("recovery_iterations") or 250_000),
    ):
        return False
    password_salt, password_hash, iterations = hash_secret(new_password)
    with get_conn(path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, password_salt = ?, password_iterations = ? "
            "WHERE id = ?",
            (password_hash, password_salt, iterations, int(row["id"])),
        )
    return True


def change_password(user_id: int, current_password: str, new_password: str,
                    path: str | Path | None = None) -> bool:
    """Change a password after verifying the current one."""
    from .auth import hash_secret, validate_password, verify_secret

    error = validate_password(new_password)
    if error:
        raise ValueError(error)
    row = get_user(user_id, path)
    row = dict(row) if row is not None else None
    if row is None or not row.get("password_hash"):
        return False
    if not verify_secret(
        current_password or "",
        row["password_salt"],
        row["password_hash"],
        int(row.get("password_iterations") or 600_000),
    ):
        return False
    salt, derived, iterations = hash_secret(new_password)
    with get_conn(path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, password_salt = ?, password_iterations = ? "
            "WHERE id = ?",
            (derived, salt, iterations, int(user_id)),
        )
    return True


def complete_onboarding(user_id: int, preferred_name: str | None = None,
                        path: str | Path | None = None) -> None:
    with get_conn(path) as conn:
        conn.execute("UPDATE users SET onboarding_complete = 1 WHERE id = ?", (user_id,))
        if preferred_name:
            conn.execute(
                "UPDATE user_preferences SET preferred_name = ?, updated_at = ? WHERE user_id = ?",
                (preferred_name.strip()[:60], utc_now(), user_id),
            )


def get_preferences(user_id: int, path: str | Path | None = None) -> dict[str, Any]:
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)
        ).fetchone()
    if row is None:
        return {}
    data = dict(row)
    try:
        data["preferred_activities"] = json.loads(data.get("preferred_activities") or "[]")
    except json.JSONDecodeError:
        data["preferred_activities"] = []
    return data


def update_preferences(user_id: int, **fields: Any) -> None:
    allowed = {
        "preferred_name", "time_available", "preferred_activities",
        "contact_name", "contact_phone", "save_chat_history", "theme",
    }
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return
    if "preferred_activities" in clean and not isinstance(clean["preferred_activities"], str):
        clean["preferred_activities"] = json.dumps(clean["preferred_activities"])
    if "save_chat_history" in clean:
        clean["save_chat_history"] = int(bool(clean["save_chat_history"]))
    assignments = ", ".join(f"{key} = ?" for key in clean)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE user_preferences SET {assignments}, updated_at = ? WHERE user_id = ?",
            (*clean.values(), utc_now(), user_id),
        )


# ---------------------------------------------------------------------------
# Generic helpers used by services
# ---------------------------------------------------------------------------

def execute(sql: str, params: tuple = (), path: str | Path | None = None) -> int:
    with get_conn(path) as conn:
        cur = conn.execute(sql, params)
        return int(cur.lastrowid or 0)


def query_all(sql: str, params: tuple = (), path: str | Path | None = None) -> list[dict[str, Any]]:
    with get_conn(path) as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def query_one(sql: str, params: tuple = (), path: str | Path | None = None) -> dict[str, Any] | None:
    with get_conn(path) as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def table_exists(name: str, path: str | Path | None = None) -> bool:
    row = query_one(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (name,), path
    )
    return row is not None


# ---------------------------------------------------------------------------
# Privacy controls
# ---------------------------------------------------------------------------

def export_user_data(user_id: int, path: str | Path | None = None) -> dict[str, Any]:
    """Return everything stored about one user as plain JSON-safe data."""
    export: dict[str, Any] = {"exported_at": utc_now(), "user_id": user_id}
    with get_conn(path) as conn:
        for table in TABLES_FOR_EXPORT:
            if table == "users":
                rows = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchall()
            else:
                rows = conn.execute(f"SELECT * FROM {table} WHERE user_id = ?", (user_id,)).fetchall()
            export[table] = [dict(r) for r in rows]
    return export


def delete_user_data(user_id: int, path: str | Path | None = None) -> None:
    """Delete the user; ON DELETE CASCADE removes every related record."""
    with get_conn(path) as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def clear_chat_history(user_id: int, path: str | Path | None = None) -> None:
    with get_conn(path) as conn:
        conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))


def save_chat_message(user_id: int, role: str, content: str,
                      meta: dict | None = None) -> None:
    with get_conn(path) as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, meta_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, role, content, json.dumps(meta or {}), utc_now()),
        )


def get_chat_history(user_id: int, limit: int = 40) -> list[dict[str, Any]]:
    rows = query_all(
        "SELECT role, content, meta_json, created_at FROM chat_messages "
        "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    for row in rows:
        try:
            row["meta"] = json.loads(row.pop("meta_json") or "{}")
        except json.JSONDecodeError:
            row["meta"] = {}
    return list(reversed(rows))


def record_crisis_event(user_id: int, level: str, categories: list[str],
                        action_taken: str, notes: str | None = None) -> None:
    with get_conn(path=None) as conn:
        conn.execute(
            "INSERT INTO crisis_events (user_id, detected_at, level, signal_categories, "
            "action_taken, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, utc_now(), level, json.dumps(categories), action_taken, notes),
        )


def get_setting(key: str, default: str | None = None) -> str | None:
    row = query_one("SELECT value FROM app_meta WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


# ---------------------------------------------------------------------------
# Small date helpers shared by services
# ---------------------------------------------------------------------------

def today_iso() -> str:
    return date.today().isoformat()


def days_ago_iso(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
