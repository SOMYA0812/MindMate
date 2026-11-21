"""End-to-end smoke test for the MindMate UI.

Run from the project folder:

    .venv\\Scripts\\python.exe tests\\smoke_test.py

The test writes to a temporary SQLite database, so it never touches the real
profile in ``data/mindmate.db``.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

TEST_DIR = Path(tempfile.mkdtemp(prefix="mindmate-smoke-"))
os.environ["MINDMATE_DATA_DIR"] = str(TEST_DIR)
os.environ["MINDMATE_DB"] = str(TEST_DIR / "mindmate.db")

from streamlit.testing.v1 import AppTest  # noqa: E402


def no_exc(at: AppTest, label: str) -> None:
    assert not at.exception, (label, [e.value for e in at.exception])


def text(at: AppTest) -> str:
    return "\n".join(block.value for block in at.markdown)


def main() -> None:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)

    # Landing page and public pages.
    at.run()
    no_exc(at, "landing")
    assert "A softer place to land" in text(at)
    for view in ("privacy", "terms", "resources"):
        at.query_params["view"] = view
        at.run()
        no_exc(at, f"public {view}")
    print("landing and public pages ok")

    # First-time signup and one-time recovery code.
    at.query_params["view"] = "signup"
    at.run()
    no_exc(at, "signup")
    at.text_input[0].set_value("Smoke Person")
    at.text_input[1].set_value("smoke_user")
    at.text_input[2].set_value("smokepass123")
    at.text_input[3].set_value("smokepass123")
    for checkbox in at.checkbox:
        checkbox.set_value(True)
    next(button for button in at.button if button.label == "Create account").click().run()
    no_exc(at, "signup submit")
    assert "Save your recovery code" in text(at)
    at.checkbox[0].set_value(True).run()
    next(button for button in at.button if button.label == "Continue to MindMate").click().run()
    no_exc(at, "recovery continue")
    assert "mm-hero" in text(at)
    print("signup and recovery code ok")

    # Logical navigation from an in-page button (not the sidebar radio).
    next(button for button in at.button if button.label == "Open my habits").click().run()
    no_exc(at, "go_to habits")
    assert at.radio[0].value == at.radio[0].options[2]
    print("in-page navigation ok")

    # Add and edit a habit with a description and weekday schedule.
    at.text_input[0].set_value("Morning water")
    at.text_area[0].set_value("One glass is enough.")
    at.multiselect[0].set_value([0, 1, 2, 3, 4, 5, 6])
    next(button for button in at.button if button.label == "Add habit").click().run()
    no_exc(at, "add habit")
    assert "Morning water" in text(at)
    assert any("One glass is enough." in caption.value for caption in at.caption)
    print("habit add ok")

    # Completing awards points; unmarking must not take them away.
    from mindmate.services import rewards

    done = next(box for box in at.checkbox if box.label.startswith("Done: Morning water"))
    done.set_value(True).run()
    no_exc(at, "complete habit")
    points_after = rewards.total_points(1)
    assert points_after > 0
    done = next(box for box in at.checkbox if box.label.startswith("Done: Morning water"))
    done.set_value(False).run()
    no_exc(at, "unmark habit")
    assert rewards.total_points(1) == points_after
    print(f"points preserved on unmark ok ({points_after})")

    # Mood check-in with a mood-specific question and supportive message.
    at.radio[0].set_value(at.radio[0].options[0]).run()
    low = next(button for button in at.button if "Low" in button.label and "Very low" not in button.label)
    low.click().run()
    no_exc(at, "mood check-in")
    assert "Why is your mood low today?" in text(at)
    assert "A low day is not a failure" in text(at)
    at.radio[0].set_value(at.radio[0].options[3]).run()
    no_exc(at, "mood history")
    assert "Recent check-ins" in text(at)
    assert "Named emotions" in text(at)
    print("mood questions and history ok")

    # Dark mode applies the dark token set and persists to preferences.
    at.toggle[0].set_value(True).run()
    no_exc(at, "dark mode")
    styles = "\n".join(block.value for block in at.markdown if "<style>" in block.value)
    assert "--mm-ink: #F3EADF" in styles
    at.toggle[0].set_value(False).run()
    no_exc(at, "light mode")
    styles = "\n".join(block.value for block in at.markdown if "<style>" in block.value)
    assert "--mm-ink: #2F2A26" in styles
    print("dark and light mode ok")

    # Settings: password change, then logout and login with the new password.
    at.radio[0].set_value(at.radio[0].options[8]).run()
    no_exc(at, "settings")
    labels = [field.label for field in at.text_input]
    index = labels.index("Current password")
    at.text_input[index].set_value("smokepass123")
    at.text_input[index + 1].set_value("smokepass456")
    at.text_input[index + 2].set_value("smokepass456")
    next(button for button in at.button if button.label == "Update password").click().run()
    no_exc(at, "change password")

    from mindmate.database import verify_login

    assert verify_login("smoke_user", "smokepass456") is not None
    next(button for button in at.button if button.label == "Log out").click().run()
    no_exc(at, "logout")
    assert "A softer place to land" in text(at)

    at.query_params["view"] = "login"
    at.run()
    no_exc(at, "login view")
    at.text_input[0].set_value("smoke_user")
    at.text_input[1].set_value("smokepass456")
    next(button for button in at.button if button.label == "Log in").click().run()
    no_exc(at, "login")
    assert "mm-hero" in text(at)
    print("password change, logout and login ok")

    # Every signed-in page should render without an exception.
    for index in range(9):
        at.radio[0].set_value(at.radio[0].options[index]).run()
        no_exc(at, f"page {index}")
    print("all signed-in pages ok")
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(TEST_DIR, ignore_errors=True)
