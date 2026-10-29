"""Independent classroom databases with session-bound authentication."""

from contextlib import closing, contextmanager
from contextvars import ContextVar
from pathlib import Path
import sqlite3
import uuid

DEFAULT_CLASSROOM = "default"
ACTIVE_CLASSROOM_KEY = "active_classroom_id"
AUTH_CLASSROOM_KEY = "authenticated_classroom_id"
_database_override = ContextVar("classroom_database_override", default=None)


def _session():
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is None:
        return None
    import streamlit as st
    return st.session_state


def active_classroom_id() -> str:
    session = _session()
    if session is None:
        return DEFAULT_CLASSROOM
    if session.get("authenticated_username"):
        # Sessions created before this feature belong to the original classroom.
        return session.get(AUTH_CLASSROOM_KEY, DEFAULT_CLASSROOM)
    return session.get(ACTIVE_CLASSROOM_KEY, DEFAULT_CLASSROOM)


@contextmanager
def _registry(base_path=None):
    from utils.database import get_base_database_path
    base_path = base_path or get_base_database_path()
    path = base_path.parent / (base_path.stem + "_classrooms.db")
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("""CREATE TABLE IF NOT EXISTS classrooms (
            classroom_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            filename TEXT NOT NULL UNIQUE, ready INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        connection.execute("""INSERT OR IGNORE INTO classrooms
            (classroom_id, name, filename, ready) VALUES (?, ?, ?, 1)""",
            (DEFAULT_CLASSROOM, "Class 1", base_path.name))
        connection.commit()
        yield connection
        connection.commit()
    finally:
        connection.close()


def list_classrooms() -> list[dict]:
    with _registry() as connection:
        return [dict(row) for row in connection.execute(
            "SELECT classroom_id, name FROM classrooms WHERE ready=1 ORDER BY created_at, rowid")]


def classroom_name() -> str:
    selected = active_classroom_id()
    return next((row['name'] for row in list_classrooms() if row['classroom_id'] == selected), "Unknown classroom")


def classroom_database_path(base_path: Path) -> Path:
    override = _database_override.get()
    if override is not None:
        return override
    classroom_id = active_classroom_id()
    if classroom_id == DEFAULT_CLASSROOM:
        return base_path
    with _registry(base_path) as connection:
        row = connection.execute("SELECT filename FROM classrooms WHERE classroom_id=? AND ready=1",
                                 (classroom_id,)).fetchone()
    if row is None:
        raise ValueError("Classroom unavailable. Sign out and select an available classroom.")
    path = base_path.parent / "classrooms" / row['filename']
    if path.parent.resolve() != (base_path.parent / "classrooms").resolve() or not path.is_file():
        raise ValueError("Classroom storage unavailable. Contact the instructor.")
    return path


@contextmanager
def database_scope(path: Path):
    """Internal provisioning/tests only. Never changes environment variables."""
    token = _database_override.set(path)
    try:
        yield
    finally:
        _database_override.reset(token)


def create_classroom(name: str, admin_username: str, owner_username: str) -> str:
    """Provision a new isolated game; inherit the requesting admin's password hash."""
    from utils.database import get_base_database_path
    from utils.bootstrap import ensure_app_storage
    from utils.repository import create_user
    if active_classroom_id() != DEFAULT_CLASSROOM:
        raise ValueError("Only an administrator in Class 1 can create classrooms.")
    session = _session()
    if session is not None and session.get('authenticated_username') != owner_username:
        raise ValueError("Administrator authentication required.")
    name, admin_username = name.strip(), admin_username.strip()
    if not name or len(name) > 80 or not admin_username or len(admin_username) > 80:
        raise ValueError("Enter a classroom name and admin username (maximum 80 characters each).")
    if any(ord(c) < 32 for c in name + admin_username):
        raise ValueError("Names cannot contain control characters.")
    base_path = get_base_database_path()
    with closing(sqlite3.connect(f"file:{base_path.as_posix()}?mode=ro", uri=True)) as source:
        owner = source.execute("SELECT password_hash FROM users WHERE username=? AND role='admin' AND is_active=1",
                               (owner_username,)).fetchone()
    if owner is None:
        raise ValueError("An active Class 1 administrator is required.")
    classroom_id = uuid.uuid4().hex
    folder = base_path.parent / "classrooms"
    folder.mkdir(exist_ok=True)
    path = folder / f"{classroom_id}.db"
    # Keep the class undiscoverable until schema, market and administrator exist.
    with _registry() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM classrooms WHERE name=?", (name,)).fetchone():
            raise ValueError("A classroom with that name already exists.")
        connection.execute("INSERT INTO classrooms (classroom_id,name,filename) VALUES (?,?,?)",
                           (classroom_id, name, path.name))
        with database_scope(path):
            ensure_app_storage()
            create_user(admin_username, owner[0], "admin", None, True)
        connection.execute("UPDATE classrooms SET ready=1 WHERE classroom_id=?", (classroom_id,))
    return classroom_id


def select_classroom(classroom_id: str) -> None:
    import streamlit as st
    if classroom_id not in {row['classroom_id'] for row in list_classrooms()}:
        raise ValueError("Unknown classroom.")
    # Drop all previous game widgets, drafts and credential notices on switching.
    st.session_state.clear()
    st.session_state[ACTIVE_CLASSROOM_KEY] = classroom_id


def render_classroom_picker() -> None:
    import streamlit as st
    choices = list_classrooms()
    identifiers = [row['classroom_id'] for row in choices]
    names = {row['classroom_id']: row['name'] for row in choices}
    selected = active_classroom_id()
    choice = st.selectbox("Classroom", identifiers, index=identifiers.index(selected),
                          format_func=names.get, key="login_classroom_picker")
    if choice != selected:
        select_classroom(choice)
        st.rerun()
