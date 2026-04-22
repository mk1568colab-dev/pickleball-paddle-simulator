"""SQLite-backed repository helpers for simulator records."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from data.defaults import DEFAULT_MARKET_REPORT
from models.schemas import (
    AppUser,
    MarketReport,
    PersistentTeamState,
    RoundResult,
    TeamArchetype,
    TeamDecision,
)
from utils.bootstrap import ensure_app_storage
from utils.database import get_connection


VALID_ROLES = {"admin", "team_leader"}


def load_market_report(round_number: int | None = None) -> MarketReport:
    """Load the latest or a specific market report."""
    ensure_app_storage()
    query = """
        SELECT
            round_number,
            total_demand,
            premium_share,
            mid_share,
            beginner_share,
            material_cost_index,
            supply_risk,
            quality_sensitivity,
            event
        FROM market_reports
    """
    parameters: tuple[Any, ...] = ()

    if round_number is None:
        query += " ORDER BY round_number DESC LIMIT 1"
    else:
        query += " WHERE round_number = ?"
        parameters = (round_number,)

    with get_connection() as connection:
        row = connection.execute(query, parameters).fetchone()

    if row is None:
        return DEFAULT_MARKET_REPORT

    return MarketReport.from_dict(dict(row))


def save_market_report(report: MarketReport) -> None:
    """Persist a market report for its round."""
    ensure_app_storage()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO market_reports (
                round_number,
                total_demand,
                premium_share,
                mid_share,
                beginner_share,
                material_cost_index,
                supply_risk,
                quality_sensitivity,
                event,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(round_number) DO UPDATE SET
                total_demand = excluded.total_demand,
                premium_share = excluded.premium_share,
                mid_share = excluded.mid_share,
                beginner_share = excluded.beginner_share,
                material_cost_index = excluded.material_cost_index,
                supply_risk = excluded.supply_risk,
                quality_sensitivity = excluded.quality_sensitivity,
                event = excluded.event,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                report.round_number,
                report.total_demand,
                report.premium_share,
                report.mid_share,
                report.beginner_share,
                report.material_cost_index,
                report.supply_risk,
                report.quality_sensitivity,
                report.event,
            ),
        )


def load_team_archetypes() -> list[TeamArchetype]:
    """Load all team archetypes."""
    ensure_app_storage()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                name,
                description,
                default_price_level,
                default_capacity_plan,
                default_quality_level,
                default_inventory_posture,
                base_cost,
                base_capacity,
                base_reputation,
                base_defect_rate,
                premium_fit,
                mid_fit,
                beginner_fit
            FROM team_archetypes
            ORDER BY name
            """
        ).fetchall()

    return [TeamArchetype.from_dict(dict(row)) for row in rows]


def load_team_decisions(
    round_number: int | None = None,
    team_name: str | None = None,
) -> list[TeamDecision]:
    """Load team decisions for a round, optionally filtered to one team."""
    ensure_app_storage()
    effective_round = round_number if round_number is not None else load_market_report().round_number
    query = """
        SELECT
            team_name,
            archetype,
            price_level,
            production_quantity,
            capacity_plan,
            quality_level,
            inventory_posture
        FROM team_decisions
        WHERE round_number = ?
    """
    parameters: list[Any] = [effective_round]

    if team_name:
        query += " AND LOWER(team_name) = LOWER(?)"
        parameters.append(team_name)

    query += " ORDER BY team_name"

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [TeamDecision.from_dict(dict(row)) for row in rows]


def load_team_decision(round_number: int, team_name: str) -> TeamDecision | None:
    """Load one team's decision for a specific round."""
    decisions = load_team_decisions(round_number=round_number, team_name=team_name)
    return decisions[0] if decisions else None


def save_team_decision(
    decision: TeamDecision,
    round_number: int,
    submitted_by_user_id: int | None = None,
) -> None:
    """Insert or update one team's decision for the round."""
    ensure_app_storage()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO team_decisions (
                round_number,
                team_name,
                archetype,
                price_level,
                production_quantity,
                capacity_plan,
                quality_level,
                inventory_posture,
                submitted_by_user_id,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(round_number, team_name) DO UPDATE SET
                archetype = excluded.archetype,
                price_level = excluded.price_level,
                production_quantity = excluded.production_quantity,
                capacity_plan = excluded.capacity_plan,
                quality_level = excluded.quality_level,
                inventory_posture = excluded.inventory_posture,
                submitted_by_user_id = excluded.submitted_by_user_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                round_number,
                decision.team_name,
                decision.archetype,
                decision.price_level,
                decision.production_quantity,
                decision.capacity_plan,
                decision.quality_level,
                decision.inventory_posture,
                submitted_by_user_id,
            ),
        )


def load_round_results(
    round_number: int | None = None,
    team_name: str | None = None,
) -> list[RoundResult]:
    """Load round results, optionally filtered by round or team."""
    ensure_app_storage()
    query = """
        SELECT
            round_number,
            team_name,
            archetype,
            demand_allocated,
            sales_units,
            stockout_units,
            ending_inventory,
            fill_rate,
            unit_price,
            revenue,
            production_cost,
            holding_cost,
            warranty_cost,
            expansion_cost,
            total_cost,
            profit,
            defect_rate,
            available_capacity,
            good_units_produced,
            reputation_after_round,
            notes
        FROM round_results
        WHERE 1 = 1
    """
    parameters: list[Any] = []

    if round_number is not None:
        query += " AND round_number = ?"
        parameters.append(round_number)

    if team_name:
        query += " AND LOWER(team_name) = LOWER(?)"
        parameters.append(team_name)

    query += " ORDER BY round_number DESC, team_name"

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [RoundResult.from_dict(dict(row)) for row in rows]


def save_round_results(results: list[RoundResult]) -> None:
    """Persist one round's results."""
    ensure_app_storage()
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO round_results (
                round_number,
                team_name,
                archetype,
                demand_allocated,
                sales_units,
                stockout_units,
                ending_inventory,
                fill_rate,
                unit_price,
                revenue,
                production_cost,
                holding_cost,
                warranty_cost,
                expansion_cost,
                total_cost,
                profit,
                defect_rate,
                available_capacity,
                good_units_produced,
                reputation_after_round,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(round_number, team_name) DO UPDATE SET
                archetype = excluded.archetype,
                demand_allocated = excluded.demand_allocated,
                sales_units = excluded.sales_units,
                stockout_units = excluded.stockout_units,
                ending_inventory = excluded.ending_inventory,
                fill_rate = excluded.fill_rate,
                unit_price = excluded.unit_price,
                revenue = excluded.revenue,
                production_cost = excluded.production_cost,
                holding_cost = excluded.holding_cost,
                warranty_cost = excluded.warranty_cost,
                expansion_cost = excluded.expansion_cost,
                total_cost = excluded.total_cost,
                profit = excluded.profit,
                defect_rate = excluded.defect_rate,
                available_capacity = excluded.available_capacity,
                good_units_produced = excluded.good_units_produced,
                reputation_after_round = excluded.reputation_after_round,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            [
                (
                    result.round_number,
                    result.team_name,
                    result.archetype,
                    result.demand_allocated,
                    result.sales_units,
                    result.stockout_units,
                    result.ending_inventory,
                    result.fill_rate,
                    result.unit_price,
                    result.revenue,
                    result.production_cost,
                    result.holding_cost,
                    result.warranty_cost,
                    result.expansion_cost,
                    result.total_cost,
                    result.profit,
                    result.defect_rate,
                    result.available_capacity,
                    result.good_units_produced,
                    result.reputation_after_round,
                    result.notes,
                )
                for result in results
            ],
        )


def load_team_states(team_name: str | None = None) -> list[PersistentTeamState]:
    """Load current persistent team states."""
    ensure_app_storage()
    query = """
        SELECT
            team_name,
            archetype,
            cash_balance,
            inventory_units,
            capacity_units,
            reputation_score,
            completed_rounds_json,
            last_decision_json,
            cumulative_profit
        FROM team_states
        WHERE 1 = 1
    """
    parameters: list[Any] = []

    if team_name:
        query += " AND LOWER(team_name) = LOWER(?)"
        parameters.append(team_name)

    query += " ORDER BY team_name"

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [_row_to_team_state(row) for row in rows]


def save_team_state(state: PersistentTeamState) -> None:
    """Insert or update one team state."""
    save_team_states([state])


def save_team_states(states: list[PersistentTeamState]) -> None:
    """Persist a snapshot of team states."""
    ensure_app_storage()
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO team_states (
                team_name,
                archetype,
                cash_balance,
                inventory_units,
                capacity_units,
                reputation_score,
                completed_rounds_json,
                last_decision_json,
                cumulative_profit,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(team_name) DO UPDATE SET
                archetype = excluded.archetype,
                cash_balance = excluded.cash_balance,
                inventory_units = excluded.inventory_units,
                capacity_units = excluded.capacity_units,
                reputation_score = excluded.reputation_score,
                completed_rounds_json = excluded.completed_rounds_json,
                last_decision_json = excluded.last_decision_json,
                cumulative_profit = excluded.cumulative_profit,
                updated_at = CURRENT_TIMESTAMP
            """,
            [
                (
                    state.team_name,
                    state.archetype,
                    state.cash_balance,
                    state.inventory_units,
                    state.capacity_units,
                    state.reputation_score,
                    json.dumps(state.completed_rounds),
                    json.dumps(state.last_decision),
                    state.cumulative_profit,
                )
                for state in states
            ],
        )


def reset_runtime_data() -> None:
    """Clear decisions, results, and team states."""
    ensure_app_storage()
    with get_connection() as connection:
        connection.execute("DELETE FROM team_decisions")
        connection.execute("DELETE FROM round_results")
        connection.execute("DELETE FROM team_states")


def count_active_admins() -> int:
    """Return the number of active admin accounts."""
    ensure_app_storage()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM users
            WHERE role = 'admin' AND is_active = 1
            """
        ).fetchone()
    return int(row["count"]) if row else 0


def has_active_admin() -> bool:
    """Return whether the system has at least one active admin account."""
    return count_active_admins() > 0


def load_users(
    role: str | None = None,
    is_active: bool | None = None,
) -> list[AppUser]:
    """Load application users with optional filters."""
    ensure_app_storage()
    query = """
        SELECT
            user_id,
            username,
            password_hash,
            role,
            team_name,
            is_active
        FROM users
        WHERE 1 = 1
    """
    parameters: list[Any] = []

    if role:
        query += " AND role = ?"
        parameters.append(role)

    if is_active is not None:
        query += " AND is_active = ?"
        parameters.append(1 if is_active else 0)

    query += " ORDER BY role, username"

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [AppUser.from_dict(dict(row)) for row in rows]


def get_user_by_username(username: str) -> AppUser | None:
    """Load one user by username."""
    ensure_app_storage()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                user_id,
                username,
                password_hash,
                role,
                team_name,
                is_active
            FROM users
            WHERE username = ? COLLATE NOCASE
            """,
            (username.strip(),),
        ).fetchone()

    return AppUser.from_dict(dict(row)) if row else None


def get_user_by_id(user_id: int) -> AppUser | None:
    """Load one user by primary key."""
    ensure_app_storage()
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                user_id,
                username,
                password_hash,
                role,
                team_name,
                is_active
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    return AppUser.from_dict(dict(row)) if row else None


def create_initial_admin(username: str, password_hash: str) -> AppUser:
    """Create the first admin account when none exists yet."""
    if has_active_admin():
        raise ValueError("Initial setup is already complete.")

    return create_user(
        username=username,
        password_hash=password_hash,
        role="admin",
        team_name=None,
        is_active=True,
    )


def create_user(
    username: str,
    password_hash: str,
    role: str,
    team_name: str | None,
    is_active: bool,
) -> AppUser:
    """Create a new user account."""
    ensure_app_storage()
    normalized_username = _normalize_username(username)
    normalized_role = _normalize_role(role)
    normalized_team_name = _normalize_team_name(normalized_role, team_name)

    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (
                    username,
                    password_hash,
                    role,
                    team_name,
                    is_active,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    normalized_username,
                    password_hash,
                    normalized_role,
                    normalized_team_name,
                    1 if is_active else 0,
                ),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError("That username is already in use.") from error

    created_user = get_user_by_id(int(cursor.lastrowid))
    if created_user is None:
        raise ValueError("The user could not be loaded after creation.")
    return created_user


def update_user(
    user_id: int,
    username: str,
    role: str,
    team_name: str | None,
    is_active: bool,
    password_hash: str | None = None,
) -> AppUser:
    """Update one existing user account."""
    ensure_app_storage()
    existing_user = get_user_by_id(user_id)
    if existing_user is None:
        raise ValueError("That user no longer exists.")

    normalized_username = _normalize_username(username)
    normalized_role = _normalize_role(role)
    normalized_team_name = _normalize_team_name(normalized_role, team_name)

    if (
        existing_user.role == "admin"
        and existing_user.is_active
        and count_active_admins() == 1
        and (normalized_role != "admin" or not is_active)
    ):
        raise ValueError("You cannot deactivate or remove the last active admin.")

    resolved_password_hash = password_hash or existing_user.password_hash

    try:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE users
                SET
                    username = ?,
                    password_hash = ?,
                    role = ?,
                    team_name = ?,
                    is_active = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (
                    normalized_username,
                    resolved_password_hash,
                    normalized_role,
                    normalized_team_name,
                    1 if is_active else 0,
                    user_id,
                ),
            )
    except sqlite3.IntegrityError as error:
        raise ValueError("That username is already in use.") from error

    updated_user = get_user_by_id(user_id)
    if updated_user is None:
        raise ValueError("The user could not be loaded after update.")
    return updated_user


def update_user_password(user_id: int, password_hash: str) -> AppUser:
    """Update only a user's password hash."""
    existing_user = get_user_by_id(user_id)
    if existing_user is None:
        raise ValueError("That user no longer exists.")

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE users
            SET
                password_hash = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                password_hash,
                user_id,
            ),
        )

    updated_user = get_user_by_id(user_id)
    if updated_user is None:
        raise ValueError("The user could not be loaded after password update.")
    return updated_user


def _normalize_username(username: str) -> str:
    """Normalize and validate a username."""
    normalized_username = username.strip()
    if not normalized_username:
        raise ValueError("Username is required.")
    return normalized_username


def _normalize_role(role: str) -> str:
    """Normalize and validate a user role."""
    normalized_role = role.strip()
    if normalized_role not in VALID_ROLES:
        raise ValueError("Invalid role.")
    return normalized_role


def _normalize_team_name(role: str, team_name: str | None) -> str | None:
    """Normalize the team assignment for a user role."""
    normalized_team_name = team_name.strip() if team_name else None
    if role == "team_leader" and not normalized_team_name:
        raise ValueError("Team name is required for team leaders.")
    if role == "admin":
        return None
    return normalized_team_name


def _row_to_team_state(row: Any) -> PersistentTeamState:
    """Convert a SQLite row into persistent team state."""
    payload = dict(row)
    payload["completed_rounds"] = json.loads(payload.pop("completed_rounds_json", "[]"))
    payload["last_decision"] = json.loads(payload.pop("last_decision_json", "{}"))
    return PersistentTeamState.from_dict(payload)
