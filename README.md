# MindMate

A local-first mental-wellness companion built with Streamlit. MindMate combines a
rule-based expert system (with a transparent reasoning trace), gentle habit
tracking, mood check-ins and reflections, all stored in a SQLite database on your
own device.

> MindMate is an academic support tool. It cannot diagnose, treat or assess risk,
> and it is not an emergency service. If you are in immediate danger in India,
> call **112**. For mental-health support, call **Tele-MANAS 14416** (24/7, free).

## Highlights

- **InMind-inspired landing page** — warm cream/peach palette, serif headings,
  soft gradients, responsive layout, dark-mode aware, with a public footer for
  privacy, terms and helplines.
- **Local accounts** — username + password with PBKDF2-HMAC-SHA256 hashing
  (600,000 iterations, per-user salt). Nothing is stored in plain text and no
  email is required.
- **One-time recovery code** — shown once at sign-up and stored only as a hash.
  Used to reset a forgotten password.
- **Existing-profile claim** — an older profile created before accounts existed
  can be secured in one step without losing moods, habits or points.
- **Persistent dark/light theme** — applies to every page, chart, card, form and
  button, and is saved per profile. The landing page also accepts
  `?theme=light` / `?theme=dark`.
- **Editable habits** — name, description, area, daily goal, weekday schedule,
  weekly target and points. Add, edit, archive/restore, and delete with a
  confirmation step. Off-schedule days are treated as rest days.
- **No guilt mechanics** — missed days never subtract points or reset progress.
  Unmarking or deleting a habit keeps every point already earned.
- **Mood check-ins with context** — score plus optional named emotion,
  mood-specific follow-up question, context tags, note, energy, tension and
  sleep. Each mood has its own supportive message and visual treatment.
- **Mood history** — entry cards, line/distribution charts, named-emotion and
  context-tag charts, plus a gentle pattern insight.
- **Personal home** — time-aware greeting, rotating comforting quote and a
  short path to the next small action.
- **Existing expert system preserved** — chat, inference rules, recommendations,
  reflections, rewards and daily summaries all keep working and persisting.

## Requirements

- Python 3.10+
- The packages in `requirements.txt` (Streamlit, pandas, Plotly)

## Setup

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

Then open <http://localhost:8501>.

On first launch the database is created (or migrated) at
`data/mindmate.db`. Set `MINDMATE_DATA_DIR` or `MINDMATE_DB` to use a
different location.

## First run

1. The landing page opens. Choose **Get started** to create a local account.
2. Pick a display name, username and password (8+ characters, a letter and a
   number), then save the recovery code shown on the next screen — it is not
   shown again.
3. If an older unsecured profile exists, log in and use **Secure this existing
   profile** to attach credentials without losing its history.

## Project layout

```
app.py                         entry point, routing, auth gate, sidebar
.streamlit/config.toml         Streamlit theme (warm terracotta/cream)
mindmate/
  auth.py                      password + recovery-code hashing helpers
  database.py                  schema, migrations, accounts, storage
  config.py                    app constants, mood metadata, quotes
  engine/                      expert system: NLU, rules, dialogue, crisis
  knowledge_base/              rules, recommendations, categories (JSON)
  services/                    habits, mood, rewards, summaries
  ui/theme.py                  light/dark design tokens and CSS
  ui/components.py             shared cards, charts, mood selector
  ui/pages/                    landing, auth, home, chat, habits, mood, ...
tests/smoke_test.py            end-to-end UI smoke test (temp database)
```

## Tests

The smoke test runs the real Streamlit app with `AppTest` against a temporary
database, so it never touches your profile:

```powershell
.venv\Scripts\python.exe tests\smoke_test.py
```

It covers the landing page, public legal/helpline views, sign-up and recovery
code, in-page navigation, habit creation, point preservation on unmark, mood
questions and history, dark/light mode, password change, logout/login and every
signed-in page.

## Data and privacy

- Everything is stored locally in `data/mindmate.db`.
- Settings offers a full JSON export and a permanent delete of all data.
- Chat history can be cleared separately.
- Passwords and recovery codes are only ever stored as salted PBKDF2 hashes.
- Helpline numbers are included for convenience; verify them before relying on
  them.
