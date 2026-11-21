"""Application-wide configuration and constants.

All paths can be overridden with environment variables, which keeps the app
easy to test and easy to demonstrate on another machine.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "MindMate"
APP_TAGLINE = "A gentle companion for difficult days"
VERSION = "1.1.0"

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
KB_DIR = PACKAGE_DIR / "knowledge_base"

DATA_DIR = Path(os.getenv("MINDMATE_DATA_DIR", PROJECT_DIR / "data"))
DB_PATH = Path(os.getenv("MINDMATE_DB", DATA_DIR / "mindmate.db"))

TIMEZONE = os.getenv("MINDMATE_TZ", "Asia/Kolkata")

# Safety: the assistant is deliberately conservative. If the classifier is
# unsure, the conversation switches to a gentle safety check instead of
# continuing with ordinary recommendations.
CRISIS_ESCALATION_ENABLED = True

# Reward rules. Points are for *effort*, never for mood scores.
POINTS = {
    "mood_checkin": 5,
    "habit_default": 10,
    "reflection": 5,
    "daily_summary_review": 0,  # viewing a summary is not an achievement
}

MAX_RECOMMENDATIONS = 3
MINUTES_PER_DAY = 24 * 60

MOOD_LABELS = {
    1: {"label": "Very low", "emoji": "🌧️", "color": "#B9A7D9"},
    2: {"label": "Low", "emoji": "🌫️", "color": "#A9C4DE"},
    3: {"label": "Okay", "emoji": "🌤️", "color": "#A8D5C7"},
    4: {"label": "Good", "emoji": "🌿", "color": "#94C9A9"},
    5: {"label": "Great", "emoji": "🌻", "color": "#F2C879"},
}

# Mood-specific follow-up prompts. The score (1–5) is a broad snapshot; the
# emotion words below let someone be more specific without being diagnosed.
MOOD_EMOTIONS = {
    "happy": {
        "label": "Happy",
        "emoji": "🌻",
        "color": "#F2C879",
        "question": "What made you feel happy today?",
        "prompts": ["Time with someone", "A small win", "Rest or a slow moment",
                    "Being outdoors", "Something kind happened", "Music or a book"],
        "message": "It is lovely that there was some light today. You do not have to hold on to it perfectly.",
        "scores": [4, 5],
    },
    "calm": {
        "label": "Calm",
        "emoji": "🌿",
        "color": "#A8D5C7",
        "question": "What helped you feel settled today?",
        "prompts": ["A quieter day", "Breathing or stretching", "Time away from screens",
                    "A routine that worked", "Being with someone safe"],
        "message": "Calm is worth noticing too. There is nothing you need to do to earn it.",
        "scores": [3, 4],
    },
    "anxious": {
        "label": "Anxious",
        "emoji": "🌫️",
        "color": "#A9C4DE",
        "question": "Is something making you feel worried or overwhelmed?",
        "prompts": ["Work or study pressure", "A decision I am avoiding", "Something uncertain",
                    "Money or practical worries", "A health concern", "Too many things at once"],
        "message": "Worry can take up a lot of room. You do not have to solve all of it right now.",
        "scores": [1, 2, 3],
    },
    "low": {
        "label": "Low",
        "emoji": "🌧️",
        "color": "#B9A7D9",
        "question": "Why is your mood low today?",
        "prompts": ["Feeling stressed", "Something upsetting happened", "Feeling lonely",
                    "Worrying about something", "Emotionally exhausted", "Poor sleep"],
        "message": "A low day is not a failure. Naming it is already a form of care.",
        "scores": [1, 2],
    },
    "sad": {
        "label": "Sad",
        "emoji": "💧",
        "color": "#A9C4DE",
        "question": "Would you like to talk about what's making you sad?",
        "prompts": ["A loss or goodbye", "A conflict with someone", "Feeling unseen",
                    "Disappointment", "Missing someone", "I am not sure yet"],
        "message": "You can be sad here without needing to explain it neatly. Take your time.",
        "scores": [1, 2],
    },
    "angry": {
        "label": "Angry",
        "emoji": "🔥",
        "color": "#E8B4A2",
        "question": "Would you like to share what frustrated you today?",
        "prompts": ["Being treated unfairly", "A boundary was crossed", "A plan fell through",
                    "Feeling ignored", "Too much pressure", "I am not sure yet"],
        "message": "Anger often points to something that mattered. It is okay to name it without judging it.",
        "scores": [1, 2, 3],
    },
    "tired": {
        "label": "Tired",
        "emoji": "😴",
        "color": "#C9B8A8",
        "question": "What has been draining your energy lately?",
        "prompts": ["Poor sleep", "A demanding week", "Emotional load", "Physical health",
                    "Too many responsibilities", "Not enough quiet time"],
        "message": "Tiredness is information, not laziness. Rest is allowed to be part of the plan.",
        "scores": [1, 2, 3],
    },
    "numb": {
        "label": "Numb",
        "emoji": "🫥",
        "color": "#CFC9DE",
        "question": "Is it hard to name what you are feeling right now?",
        "prompts": ["Everything feels flat", "I am overwhelmed", "I shut down",
                    "I do not know", "I am exhausted", "I would rather not say"],
        "message": "Not feeling much is also a valid way to arrive. You do not have to perform an emotion here.",
        "scores": [1, 2, 3],
    },
}

WEEKDAYS = [
    {"value": 0, "label": "Mon", "full": "Monday"},
    {"value": 1, "label": "Tue", "full": "Tuesday"},
    {"value": 2, "label": "Wed", "full": "Wednesday"},
    {"value": 3, "label": "Thu", "full": "Thursday"},
    {"value": 4, "label": "Fri", "full": "Friday"},
    {"value": 5, "label": "Sat", "full": "Saturday"},
    {"value": 6, "label": "Sun", "full": "Sunday"},
]

# Short, non-clinical quotes used on the landing page and dashboard. They are
# deliberately gentle: no productivity pressure and no "good vibes only".
QUOTES = [
    "Small steps every day lead to meaningful changes.",
    "You don't have to figure everything out today.",
    "Progress is still progress, even when it feels slow.",
    "You are allowed to do the minimum and call it enough.",
    "A difficult day is still a day you got through.",
    "There is no catch-up required for missed days.",
    "Noticing how you feel is already a skill.",
    "One kind thing toward yourself is a real action.",
    "You can start again at any hour of the day.",
    "Rest is part of the plan, not a reward for finishing it.",
    "Your worth is not measured by your streak or your points.",
    "You do not have to earn the right to ask for help.",
]

HABIT_CATEGORIES = {
    "movement": {"label": "Movement", "emoji": "🚶"},
    "mind": {"label": "Mind & calm", "emoji": "🧘"},
    "connection": {"label": "Connection", "emoji": "🫂"},
    "sleep": {"label": "Sleep", "emoji": "🌙"},
    "nutrition": {"label": "Food & water", "emoji": "🥗"},
    "creative": {"label": "Creative", "emoji": "🎨"},
    "study": {"label": "Study & work", "emoji": "📚"},
    "care": {"label": "Daily care", "emoji": "🪥"},
    "wellbeing": {"label": "Wellbeing", "emoji": "🌱"},
}

# Habit templates are *offers*, never prescriptions. Users can edit or ignore
# every field.
HABIT_TEMPLATES = [
    {"name": "Take a 10-minute walk", "category": "movement", "target_value": 10,
     "unit": "minutes", "target_days_per_week": 5, "points": 10},
    {"name": "Read for 10 minutes", "category": "mind", "target_value": 10,
     "unit": "minutes", "target_days_per_week": 5, "points": 10},
    {"name": "Drink enough water", "category": "nutrition", "target_value": 6,
     "unit": "glasses", "target_days_per_week": 7, "points": 5},
    {"name": "Wind down before bed", "category": "sleep", "target_value": 20,
     "unit": "minutes", "target_days_per_week": 5, "points": 10},
    {"name": "Write a short journal note", "category": "creative", "target_value": 1,
     "unit": "entry", "target_days_per_week": 5, "points": 10},
    {"name": "Message someone I trust", "category": "connection", "target_value": 1,
     "unit": "message", "target_days_per_week": 3, "points": 10},
    {"name": "Step outside for fresh air", "category": "movement", "target_value": 5,
     "unit": "minutes", "target_days_per_week": 5, "points": 5},
    {"name": "One screen-free break", "category": "mind", "target_value": 10,
     "unit": "minutes", "target_days_per_week": 5, "points": 5},
]
