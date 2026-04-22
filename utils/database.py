"""SQLite connection and schema helpers for the simulator."""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_ENV_VAR = "SIMULATOR_DB_PATH"
DATA_DIR_ENV_VAR = "SIMULATOR_DATA_DIR"
HOSTED_DISK_ENV_VAR = "RENDER_DISK_PATH"
ENVIRONMENT_ENV_VAR = "SIMULATOR_ENV"
PRODUCTION_ENVIRONMENT = "prod"
DEVELOPMENT_ENVIRONMENT = "dev"
SQLITE_TIMEOUT_SECONDS = 30.0
SQLITE_BUSY_TIMEOUT_MS = 30_000

_logged_database_paths: set[str] = set()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'team_leader')),
    team_name TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_archetypes (
    name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    default_price_level TEXT NOT NULL,
    default_capacity_plan TEXT NOT NULL,
    default_quality_level TEXT NOT NULL,
    default_inventory_posture TEXT NOT NULL,
    base_cost REAL NOT NULL,
    base_capacity INTEGER NOT NULL,
    base_reputation REAL NOT NULL,
    base_defect_rate REAL NOT NULL,
    premium_fit REAL NOT NULL,
    mid_fit REAL NOT NULL,
    beginner_fit REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_reports (
    round_number INTEGER PRIMARY KEY,
    total_demand INTEGER NOT NULL,
    premium_share REAL NOT NULL,
    mid_share REAL NOT NULL,
    beginner_share REAL NOT NULL,
    material_cost_index REAL NOT NULL,
    supply_risk TEXT NOT NULL,
    quality_sensitivity REAL NOT NULL,
    event TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_decisions (
    round_number INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    archetype TEXT NOT NULL,
    price_level TEXT NOT NULL,
    production_quantity INTEGER NOT NULL,
    capacity_plan TEXT NOT NULL,
    quality_level TEXT NOT NULL,
    inventory_posture TEXT NOT NULL,
    submitted_by_user_id INTEGER,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (round_number, team_name),
    FOREIGN KEY (submitted_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS team_states (
    team_name TEXT PRIMARY KEY,
    archetype TEXT NOT NULL,
    cash_balance REAL NOT NULL,
    inventory_units INTEGER NOT NULL,
    capacity_units INTEGER NOT NULL,
    reputation_score REAL NOT NULL,
    completed_rounds_json TEXT NOT NULL,
    last_decision_json TEXT NOT NULL,
    cumulative_profit REAL NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS round_results (
    round_number INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    archetype TEXT NOT NULL,
    demand_allocated REAL NOT NULL,
    sales_units INTEGER NOT NULL,
    stockout_units INTEGER NOT NULL,
    ending_inventory INTEGER NOT NULL,
    fill_rate REAL NOT NULL,
    unit_price REAL NOT NULL,
    revenue REAL NOT NULL,
    production_cost REAL NOT NULL,
    holding_cost REAL NOT NULL,
    warranty_cost REAL NOT NULL,
    expansion_cost REAL NOT NULL,
    total_cost REAL NOT NULL,
    profit REAL NOT NULL,
    defect_rate REAL NOT NULL,
    available_capacity INTEGER NOT NULL,
    good_units_produced INTEGER NOT NULL,
    reputation_after_round REAL NOT NULL,
    notes TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (round_number, team_name)
);
"""


def get_simulator_env() -> str:
    """Return the configured simulator environment."""
    environment = os.getenv(ENVIRONMENT_ENV_VAR, PRODUCTION_ENVIRONMENT).strip().lower()
    if environment not in {PRODUCTION_ENVIRONMENT, DEVELOPMENT_ENVIRONMENT}:
        logger.warning(
            "Unsupported %s=%s; falling back to %s.",
            ENVIRONMENT_ENV_VAR,
            environment,
            PRODUCTION_ENVIRONMENT,
        )
        return PRODUCTION_ENVIRONMENT
    return environment


def get_database_path() -> Path:
    """Resolve the configured SQLite database path."""
    configured_path = os.getenv(DATABASE_ENV_VAR, "").strip()
    path_source = DATABASE_ENV_VAR
    if configured_path:
        path = Path(configured_path)
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
    else:
        data_dir, path_source = _get_data_dir()
        path = data_dir / "simulator.db"

    path.parent.mkdir(parents=True, exist_ok=True)
    _log_database_path_once(path, path_source)
    return path


def _get_data_dir() -> tuple[Path, str]:
    """Resolve the writable directory used for persistent simulator data."""
    configured_dir = os.getenv(DATA_DIR_ENV_VAR, "").strip()
    hosted_disk_dir = os.getenv(HOSTED_DISK_ENV_VAR, "").strip()

    if configured_dir:
        data_dir = Path(configured_dir)
        source = DATA_DIR_ENV_VAR
    elif hosted_disk_dir:
        data_dir = Path(hosted_disk_dir)
        source = HOSTED_DISK_ENV_VAR
    else:
        data_dir = BASE_DIR / "data"
        source = "local-data-fallback"

    if not data_dir.is_absolute():
        data_dir = (BASE_DIR / data_dir).resolve()

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir, source


def _log_database_path_once(path: Path, source: str) -> None:
    """Log database path details once per resolved path."""
    key = str(path)
    if key in _logged_database_paths:
        return

    _logged_database_paths.add(key)
    environment = get_simulator_env()
    logger.info("Simulator database path resolved to %s via %s.", path, source)
    if environment == PRODUCTION_ENVIRONMENT and source == "local-data-fallback":
        logger.warning(
            "Production mode is using the local fallback SQLite path. "
            "Configure %s or %s for a persistent hosted disk.",
            DATABASE_ENV_VAR,
            DATA_DIR_ENV_VAR,
        )


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection configured for the simulator."""
    connection = sqlite3.connect(
        get_database_path(),
        timeout=SQLITE_TIMEOUT_SECONDS,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS};")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database() -> Path:
    """Create the database file and schema if they do not exist yet."""
    database_path = get_database_path()
    with get_connection() as connection:
        connection.executescript(SCHEMA_SQL)
    return database_path
