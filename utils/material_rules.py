"""Classroom-scoped material rules, committed when submissions first open."""

from engine.materials import LEGACY_REQUIREMENTS, validate_requirements
from utils.bootstrap import ensure_app_storage
from utils.database import get_connection


def rules_from_connection(connection, round_number):
    row = connection.execute(
        "SELECT beginner, mid, premium FROM material_rules WHERE round_number<=? "
        "ORDER BY round_number DESC LIMIT 1", (round_number,)
    ).fetchone()
    return dict(row) if row else dict(LEGACY_REQUIREMENTS)


def load_material_requirements(round_number):
    ensure_app_storage()
    with get_connection() as connection:
        return rules_from_connection(connection, round_number)


def snapshot_material_requirements(connection, round_number):
    rates = rules_from_connection(connection, round_number)
    connection.execute(
        "INSERT OR IGNORE INTO material_rules(round_number, beginner, mid, premium) VALUES (?,?,?,?)",
        (round_number, rates['beginner'], rates['mid'], rates['premium']),
    )


def save_material_requirements(round_number, values):
    from utils.auth import get_current_user
    user = get_current_user()
    if user is None or user.role != 'admin' or not user.is_active:
        raise PermissionError("Only an authenticated classroom administrator can change material requirements.")
    rates = validate_requirements(values)
    ensure_app_storage()
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        admin = connection.execute(
            "SELECT 1 FROM users WHERE user_id=? AND username=? AND role='admin' AND is_active=1",
            (user.user_id, user.username),
        ).fetchone()
        if not admin:
            raise PermissionError("Active administrator access is required in this classroom.")
        current = connection.execute("SELECT MAX(round_number) FROM market_reports").fetchone()[0]
        locked = connection.execute(
            "SELECT 1 FROM demand_commitments WHERE round_number=? AND locked_at IS NOT NULL",
            (round_number,),
        ).fetchone()
        submitted = connection.execute(
            "SELECT 1 FROM team_decisions WHERE round_number=? LIMIT 1", (round_number,)
        ).fetchone()
        completed = connection.execute(
            "SELECT 1 FROM round_results WHERE round_number=? LIMIT 1", (round_number,)
        ).fetchone()
        if round_number != current or locked or submitted or completed:
            raise ValueError("Material requirements are locked after submissions open or decisions exist. Set the next round before opening submissions.")
        connection.execute(
            "INSERT INTO material_rules(round_number, beginner, mid, premium) VALUES (?,?,?,?) "
            "ON CONFLICT(round_number) DO UPDATE SET beginner=excluded.beginner, mid=excluded.mid, premium=excluded.premium",
            (round_number, rates['beginner'], rates['mid'], rates['premium']),
        )
