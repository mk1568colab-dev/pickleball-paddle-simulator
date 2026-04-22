"""Application bootstrap helpers."""

from __future__ import annotations

import logging
import os

from data.defaults import DEFAULT_MARKET_REPORT, DEFAULT_TEAM_ARCHETYPES, DEMO_USER_SEEDS
from utils.database import DEVELOPMENT_ENVIRONMENT, get_connection, get_simulator_env, initialize_database
from utils.security import hash_password


logger = logging.getLogger(__name__)

DEMO_ACCOUNTS_ENV_VAR = "SIMULATOR_ENABLE_DEMO_ACCOUNTS"


def ensure_app_storage() -> str:
    """Create the SQLite database, schema, and seed reference data."""
    database_path = initialize_database()

    with get_connection() as connection:
        _seed_market_report(connection)
        _seed_team_archetypes(connection)
        if _should_seed_demo_accounts():
            _seed_demo_users(connection)

    return str(database_path)


def _seed_market_report(connection) -> None:
    """Insert the default market report if none exists yet."""
    existing_count = connection.execute(
        "SELECT COUNT(*) AS count FROM market_reports"
    ).fetchone()["count"]
    if existing_count:
        return

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
            event
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            DEFAULT_MARKET_REPORT.round_number,
            DEFAULT_MARKET_REPORT.total_demand,
            DEFAULT_MARKET_REPORT.premium_share,
            DEFAULT_MARKET_REPORT.mid_share,
            DEFAULT_MARKET_REPORT.beginner_share,
            DEFAULT_MARKET_REPORT.material_cost_index,
            DEFAULT_MARKET_REPORT.supply_risk,
            DEFAULT_MARKET_REPORT.quality_sensitivity,
            DEFAULT_MARKET_REPORT.event,
        ),
    )


def _seed_team_archetypes(connection) -> None:
    """Seed or refresh the archetype reference data."""
    rows = connection.execute(
        "SELECT name FROM team_archetypes ORDER BY name"
    ).fetchall()
    existing_names = {row["name"] for row in rows}
    default_names = {item.name for item in DEFAULT_TEAM_ARCHETYPES}

    if existing_names and existing_names == default_names:
        return

    connection.execute("DELETE FROM team_archetypes")
    connection.executemany(
        """
        INSERT INTO team_archetypes (
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
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                archetype.name,
                archetype.description,
                archetype.default_price_level,
                archetype.default_capacity_plan,
                archetype.default_quality_level,
                archetype.default_inventory_posture,
                archetype.base_cost,
                archetype.base_capacity,
                archetype.base_reputation,
                archetype.base_defect_rate,
                archetype.premium_fit,
                archetype.mid_fit,
                archetype.beginner_fit,
            )
            for archetype in DEFAULT_TEAM_ARCHETYPES
        ],
    )


def _should_seed_demo_accounts() -> bool:
    """Return whether demo accounts should be inserted for development use."""
    flag_value = os.getenv(DEMO_ACCOUNTS_ENV_VAR, "").strip().lower()
    if flag_value not in {"1", "true", "yes", "on"}:
        return False

    if get_simulator_env() != DEVELOPMENT_ENVIRONMENT:
        logger.warning(
            "%s was enabled outside %s mode; demo accounts will not be seeded.",
            DEMO_ACCOUNTS_ENV_VAR,
            DEVELOPMENT_ENVIRONMENT,
        )
        return False

    return True


def _seed_demo_users(connection) -> None:
    """Insert demo accounts only when explicit development mode is enabled."""
    logger.info("Seeding demo user accounts because demo mode is enabled.")
    for seed in DEMO_USER_SEEDS:
        existing_user = connection.execute(
            "SELECT user_id FROM users WHERE username = ? COLLATE NOCASE",
            (seed["username"],),
        ).fetchone()
        if existing_user:
            continue

        connection.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                role,
                team_name,
                is_active
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                seed["username"],
                hash_password(seed["password"]),
                seed["role"],
                seed["team_name"],
                1 if seed["is_active"] else 0,
            ),
        )
