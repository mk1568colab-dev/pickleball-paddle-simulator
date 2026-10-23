"""Read-only UI checks against the isolated classroom lab."""
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LAB = ROOT / ".preview" / "demand_lab_20261022_v1" / "lab.db"
assert LAB.is_file()
os.environ["SIMULATOR_DB_PATH"] = str(LAB)
os.environ["SIMULATOR_ENV"] = "dev"
os.environ["SIMULATOR_ENABLE_DEMO_ACCOUNTS"] = "false"
from streamlit.testing.v1 import AppTest
from utils.student_guide import big_picture_download


def check(path, user):
    with patch("streamlit.page_link") as links:
        app = AppTest.from_file(str(ROOT / path), default_timeout=30)
        app.session_state["authenticated_username"] = user
        app.run()
        assert not app.exception, str(app.exception)
        labels = [call.kwargs["label"] for call in links.call_args_list]
    return app, labels


student, labels = check("app.py", "lab_team1")
assert labels[:3] == ["Home", "Game Big Picture", "My Account"], labels
assert "Model Formula Guide" not in labels
for phrase in ["What This Version Supports", "Deployment Note", "SQLite database path"]:
    assert phrase not in str(student)
assert not student.get("download_button")
blocked, _ = check("pages/7_Model_Formula_Guide.py", "lab_team1")
assert any("admin users only" in error.value for error in blocked.error)
assert not blocked.title
admin, labels = check("pages/7_Model_Formula_Guide.py", "lab_admin")
assert "Model Formula Guide" in labels
assert any(item.value == "Model Formula Guide" for item in admin.title)
guide = big_picture_download().decode("utf-8")
assert "four product slots" in guide and "PowerPoint" not in guide
print("PASS: student navigation, download, clean home, direct-URL denial, admin access.")
