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
    base_cost REAL NOT NULL,
    base_capacity INTEGER NOT NULL,
    base_reputation REAL NOT NULL,
    base_defect_rate REAL NOT NULL,
    premium_fit REAL NOT NULL,
    mid_fit REAL NOT NULL,
    beginner_fit REAL NOT NULL,
    suggested_overtime_capacity_units INTEGER NOT NULL DEFAULT 0,
    suggested_capacity_expansion_units INTEGER NOT NULL DEFAULT 0,
    suggested_max_backorder_units INTEGER NOT NULL DEFAULT 100,
    suggested_raw_material_order_qty INTEGER NOT NULL DEFAULT 300,
    suggested_supplier_mix_offshore_pct REAL NOT NULL DEFAULT 0.0,
    suggested_supplier_mix_balanced_pct REAL NOT NULL DEFAULT 100.0,
    suggested_supplier_mix_premium_pct REAL NOT NULL DEFAULT 0.0,
    suggested_expedited_order_share_pct REAL NOT NULL DEFAULT 0.0,
    suggested_product_templates_json TEXT NOT NULL DEFAULT '[]',
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
    current_market_generation INTEGER NOT NULL DEFAULT 2,
    technology_shift_rate REAL NOT NULL DEFAULT 0.15,
    premium_tech_adoption REAL NOT NULL DEFAULT 0.75,
    mid_market_tech_adoption REAL NOT NULL DEFAULT 0.55,
    beginner_price_pressure REAL NOT NULL DEFAULT 0.60,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS classroom_rounds (
    round_number INTEGER PRIMARY KEY,
    submissions_open INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_decisions (
    round_number INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    archetype TEXT NOT NULL,
    overtime_capacity_units INTEGER NOT NULL DEFAULT 0,
    capacity_expansion_units INTEGER NOT NULL DEFAULT 0,
    raw_material_order_qty INTEGER NOT NULL DEFAULT 0,
    supplier_mix_offshore_pct REAL NOT NULL DEFAULT 0.0,
    supplier_mix_balanced_pct REAL NOT NULL DEFAULT 100.0,
    supplier_mix_premium_pct REAL NOT NULL DEFAULT 0.0,
    expedited_order_share_pct REAL NOT NULL DEFAULT 0.0,
    max_backorder_units INTEGER NOT NULL DEFAULT 0,
    planned_borrowing_amount REAL NOT NULL DEFAULT 0.0,
    selling_price_per_unit REAL NOT NULL DEFAULT 0.0,
    planned_production_units INTEGER NOT NULL DEFAULT 0,
    qc_budget_per_unit REAL NOT NULL DEFAULT 0.0,
    target_finished_goods_inventory INTEGER NOT NULL DEFAULT 0,
    price_level TEXT DEFAULT '',
    production_quantity INTEGER DEFAULT 0,
    capacity_plan TEXT DEFAULT '',
    quality_level TEXT DEFAULT '',
    inventory_posture TEXT DEFAULT '',
    supplier_choice TEXT DEFAULT '',
    order_priority TEXT DEFAULT '',
    service_policy TEXT DEFAULT '',
    submitted_by_user_id INTEGER,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (round_number, team_name),
    FOREIGN KEY (submitted_by_user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS product_lines (
    product_id TEXT PRIMARY KEY,
    team_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    slot_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    target_segment TEXT NOT NULL,
    lifecycle_stage TEXT NOT NULL,
    age_in_rounds INTEGER NOT NULL DEFAULT 0,
    base_defect_rate_modifier REAL NOT NULL DEFAULT 0.0,
    base_demand_fit_modifier REAL NOT NULL DEFAULT 1.0,
    tech_generation INTEGER NOT NULL DEFAULT 1,
    cannibalization_group TEXT NOT NULL DEFAULT '',
    launch_round INTEGER NOT NULL DEFAULT 0,
    retirement_flag INTEGER NOT NULL DEFAULT 0,
    retired_round INTEGER,
    replacement_project_id TEXT,
    inventory_units INTEGER NOT NULL DEFAULT 0,
    backlog_units INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (team_name, slot_name)
);

CREATE TABLE IF NOT EXISTS product_decisions (
    round_number INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    product_id TEXT NOT NULL,
    slot_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    target_segment TEXT NOT NULL,
    selling_price_per_unit REAL NOT NULL DEFAULT 0.0,
    forecast_units INTEGER NOT NULL DEFAULT 0,
    planned_production_units INTEGER NOT NULL DEFAULT 0,
    qc_budget_per_unit REAL NOT NULL DEFAULT 0.0,
    target_finished_goods_inventory INTEGER NOT NULL DEFAULT 0,
    retire_flag INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (round_number, team_name, slot_name)
);

CREATE TABLE IF NOT EXISTS product_development_projects (
    project_id TEXT PRIMARY KEY,
    team_name TEXT NOT NULL,
    project_slot_name TEXT NOT NULL,
    project_name TEXT NOT NULL DEFAULT '',
    target_segment TEXT NOT NULL DEFAULT 'mid',
    target_tech_generation INTEGER NOT NULL DEFAULT 1,
    intended_slot_name TEXT NOT NULL DEFAULT 'A',
    required_investment REAL NOT NULL DEFAULT 0.0,
    cumulative_investment REAL NOT NULL DEFAULT 0.0,
    investment_this_round REAL NOT NULL DEFAULT 0.0,
    testing_intensity REAL NOT NULL DEFAULT 0.0,
    launch_readiness_score REAL NOT NULL DEFAULT 0.0,
    planned_launch_round INTEGER NOT NULL DEFAULT 1,
    earliest_launch_round INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'concept',
    cannibalization_group TEXT NOT NULL DEFAULT '',
    projected_base_defect_modifier REAL NOT NULL DEFAULT 0.0,
    projected_demand_fit_modifier REAL NOT NULL DEFAULT 1.0,
    created_round INTEGER NOT NULL DEFAULT 1,
    launched_round INTEGER,
    canceled_round INTEGER,
    launch_now INTEGER NOT NULL DEFAULT 0,
    cancel_now INTEGER NOT NULL DEFAULT 0,
    replaced_product_name TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (team_name, project_slot_name)
);

CREATE TABLE IF NOT EXISTS product_forecasts (
    round_number INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    product_id TEXT NOT NULL,
    slot_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    forecast_units INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (round_number, team_name, slot_name)
);

CREATE TABLE IF NOT EXISTS forecast_accuracy_results (
    round_number INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    product_id TEXT NOT NULL,
    slot_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    forecast_units INTEGER NOT NULL DEFAULT 0,
    actual_demand_units REAL NOT NULL DEFAULT 0.0,
    actual_sales_units INTEGER NOT NULL DEFAULT 0,
    forecast_error_units REAL NOT NULL DEFAULT 0.0,
    absolute_error_units REAL NOT NULL DEFAULT 0.0,
    forecast_bias_pct REAL NOT NULL DEFAULT 0.0,
    mape_or_wape_value REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (round_number, team_name, slot_name)
);

CREATE TABLE IF NOT EXISTS team_states (
    team_name TEXT PRIMARY KEY,
    archetype TEXT NOT NULL,
    cash_balance REAL NOT NULL,
    inventory_units INTEGER NOT NULL,
    raw_material_inventory INTEGER NOT NULL,
    backlog_units INTEGER NOT NULL,
    capacity_units INTEGER NOT NULL,
    reputation_score REAL NOT NULL,
    completed_rounds_json TEXT NOT NULL,
    last_decision_json TEXT NOT NULL,
    open_material_orders_json TEXT NOT NULL,
    cumulative_profit REAL NOT NULL,
    short_term_debt_balance REAL NOT NULL DEFAULT 0.0,
    interest_expense_last_round REAL NOT NULL DEFAULT 0.0,
    liquidity_warning_flag INTEGER NOT NULL DEFAULT 0,
    working_capital_stress_score REAL NOT NULL DEFAULT 0.0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS round_results (
    round_number INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    archetype TEXT NOT NULL,
    active_product_count INTEGER NOT NULL DEFAULT 0,
    active_project_count INTEGER NOT NULL DEFAULT 0,
    launch_ready_project_count INTEGER NOT NULL DEFAULT 0,
    launched_project_count INTEGER NOT NULL DEFAULT 0,
    retired_product_count INTEGER NOT NULL DEFAULT 0,
    total_forecast_units INTEGER NOT NULL DEFAULT 0,
    total_actual_demand_units REAL NOT NULL DEFAULT 0.0,
    forecast_error_units REAL NOT NULL DEFAULT 0.0,
    absolute_forecast_error_units REAL NOT NULL DEFAULT 0.0,
    forecast_wape REAL NOT NULL DEFAULT 0.0,
    service_gap_units REAL NOT NULL DEFAULT 0.0,
    weighted_average_selling_price REAL NOT NULL DEFAULT 0.0,
    planned_production_units INTEGER NOT NULL DEFAULT 0,
    actual_production_units INTEGER NOT NULL DEFAULT 0,
    effective_capacity_units INTEGER NOT NULL DEFAULT 0,
    utilization_pct REAL NOT NULL DEFAULT 0.0,
    weighted_material_unit_cost REAL NOT NULL DEFAULT 0.0,
    defect_rate REAL NOT NULL DEFAULT 0.0,
    good_units_produced INTEGER NOT NULL DEFAULT 0,
    demand_allocated REAL NOT NULL DEFAULT 0.0,
    sales_units INTEGER NOT NULL DEFAULT 0,
    stockout_units INTEGER NOT NULL DEFAULT 0,
    lost_sales_units INTEGER NOT NULL DEFAULT 0,
    backlog_units_end INTEGER NOT NULL DEFAULT 0,
    ending_inventory INTEGER NOT NULL DEFAULT 0,
    ending_raw_material_inventory INTEGER NOT NULL DEFAULT 0,
    fill_rate REAL NOT NULL DEFAULT 1.0,
    unit_price REAL NOT NULL DEFAULT 0.0,
    revenue REAL NOT NULL DEFAULT 0.0,
    procurement_cost REAL NOT NULL DEFAULT 0.0,
    production_cost REAL NOT NULL DEFAULT 0.0,
    holding_cost REAL NOT NULL DEFAULT 0.0,
    warranty_cost REAL NOT NULL DEFAULT 0.0,
    backlog_cost REAL NOT NULL DEFAULT 0.0,
    expansion_cost REAL NOT NULL DEFAULT 0.0,
    innovation_investment REAL NOT NULL DEFAULT 0.0,
    interest_expense REAL NOT NULL DEFAULT 0.0,
    working_capital_requirement REAL NOT NULL DEFAULT 0.0,
    planned_borrowing_amount REAL NOT NULL DEFAULT 0.0,
    automatic_borrowing_amount REAL NOT NULL DEFAULT 0.0,
    ending_cash_balance REAL NOT NULL DEFAULT 0.0,
    short_term_debt_balance REAL NOT NULL DEFAULT 0.0,
    liquidity_stress_flag INTEGER NOT NULL DEFAULT 0,
    total_cost REAL NOT NULL DEFAULT 0.0,
    profit REAL NOT NULL DEFAULT 0.0,
    contribution_margin_per_unit REAL NOT NULL DEFAULT 0.0,
    reputation_after_round REAL NOT NULL DEFAULT 0.0,
    average_portfolio_tech_generation REAL NOT NULL DEFAULT 0.0,
    cannibalized_demand_units REAL NOT NULL DEFAULT 0.0,
    available_capacity INTEGER NOT NULL DEFAULT 0,
    beginning_finished_goods_inventory INTEGER NOT NULL DEFAULT 0,
    beginning_raw_material_inventory INTEGER NOT NULL DEFAULT 0,
    raw_material_units_received INTEGER NOT NULL DEFAULT 0,
    raw_material_units_consumed INTEGER NOT NULL DEFAULT 0,
    raw_material_order_qty INTEGER NOT NULL DEFAULT 0,
    starting_raw_material_inventory INTEGER NOT NULL DEFAULT 0,
    raw_material_ordered INTEGER NOT NULL DEFAULT 0,
    raw_material_inventory_end INTEGER NOT NULL DEFAULT 0,
    backlog_units_start INTEGER NOT NULL DEFAULT 0,
    supplier_choice TEXT NOT NULL DEFAULT '',
    order_priority TEXT NOT NULL DEFAULT '',
    service_policy TEXT NOT NULL DEFAULT '',
    launch_events_text TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (round_number, team_name)
);

CREATE TABLE IF NOT EXISTS product_round_results (
    round_number INTEGER NOT NULL,
    team_name TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    slot_name TEXT NOT NULL,
    target_segment TEXT NOT NULL,
    lifecycle_stage TEXT NOT NULL,
    age_in_rounds INTEGER NOT NULL DEFAULT 0,
    tech_generation INTEGER NOT NULL DEFAULT 1,
    cannibalization_group TEXT NOT NULL DEFAULT '',
    selling_price_per_unit REAL NOT NULL DEFAULT 0.0,
    forecast_units INTEGER NOT NULL DEFAULT 0,
    planned_production_units INTEGER NOT NULL DEFAULT 0,
    actual_production_units INTEGER NOT NULL DEFAULT 0,
    defect_rate REAL NOT NULL DEFAULT 0.0,
    good_units_produced INTEGER NOT NULL DEFAULT 0,
    demand_allocated REAL NOT NULL DEFAULT 0.0,
    actual_demand_units REAL NOT NULL DEFAULT 0.0,
    sales_units INTEGER NOT NULL DEFAULT 0,
    lost_sales_units INTEGER NOT NULL DEFAULT 0,
    ending_inventory INTEGER NOT NULL DEFAULT 0,
    fill_rate REAL NOT NULL DEFAULT 1.0,
    forecast_error_units REAL NOT NULL DEFAULT 0.0,
    absolute_error_units REAL NOT NULL DEFAULT 0.0,
    forecast_bias_pct REAL NOT NULL DEFAULT 0.0,
    mape_or_wape_value REAL NOT NULL DEFAULT 0.0,
    revenue REAL NOT NULL DEFAULT 0.0,
    production_cost REAL NOT NULL DEFAULT 0.0,
    holding_cost REAL NOT NULL DEFAULT 0.0,
    warranty_cost REAL NOT NULL DEFAULT 0.0,
    allocated_procurement_cost REAL NOT NULL DEFAULT 0.0,
    allocated_backlog_cost REAL NOT NULL DEFAULT 0.0,
    allocated_expansion_cost REAL NOT NULL DEFAULT 0.0,
    contribution_margin_per_unit REAL NOT NULL DEFAULT 0.0,
    profit_contribution REAL NOT NULL DEFAULT 0.0,
    beginning_inventory INTEGER NOT NULL DEFAULT 0,
    backlog_units_start INTEGER NOT NULL DEFAULT 0,
    backlog_units_end INTEGER NOT NULL DEFAULT 0,
    tech_gap_to_market INTEGER NOT NULL DEFAULT 0,
    tech_attractiveness_adjustment REAL NOT NULL DEFAULT 1.0,
    cannibalization_in_units REAL NOT NULL DEFAULT 0.0,
    cannibalization_out_units REAL NOT NULL DEFAULT 0.0,
    launched_this_round INTEGER NOT NULL DEFAULT 0,
    launch_event TEXT NOT NULL DEFAULT '',
    retired_this_round INTEGER NOT NULL DEFAULT 0,
    retirement_liquidation_revenue REAL NOT NULL DEFAULT 0.0,
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (round_number, team_name, slot_name)
);
"""


MARKET_REPORT_MIGRATIONS = (
    ("current_market_generation", "INTEGER NOT NULL DEFAULT 2"),
    ("technology_shift_rate", "REAL NOT NULL DEFAULT 0.15"),
    ("premium_tech_adoption", "REAL NOT NULL DEFAULT 0.75"),
    ("mid_market_tech_adoption", "REAL NOT NULL DEFAULT 0.55"),
    ("beginner_price_pressure", "REAL NOT NULL DEFAULT 0.60"),
)

TEAM_ARCHETYPE_MIGRATIONS = (
    ("suggested_overtime_capacity_units", "INTEGER NOT NULL DEFAULT 0"),
    ("suggested_capacity_expansion_units", "INTEGER NOT NULL DEFAULT 0"),
    ("suggested_max_backorder_units", "INTEGER NOT NULL DEFAULT 100"),
    ("suggested_raw_material_order_qty", "INTEGER NOT NULL DEFAULT 300"),
    ("suggested_supplier_mix_offshore_pct", "REAL NOT NULL DEFAULT 0.0"),
    ("suggested_supplier_mix_balanced_pct", "REAL NOT NULL DEFAULT 100.0"),
    ("suggested_supplier_mix_premium_pct", "REAL NOT NULL DEFAULT 0.0"),
    ("suggested_expedited_order_share_pct", "REAL NOT NULL DEFAULT 0.0"),
    ("suggested_product_templates_json", "TEXT NOT NULL DEFAULT '[]'"),
)

TEAM_DECISION_MIGRATIONS = (
    ("overtime_capacity_units", "INTEGER NOT NULL DEFAULT 0"),
    ("capacity_expansion_units", "INTEGER NOT NULL DEFAULT 0"),
    ("raw_material_order_qty", "INTEGER NOT NULL DEFAULT 0"),
    ("supplier_mix_offshore_pct", "REAL NOT NULL DEFAULT 0.0"),
    ("supplier_mix_balanced_pct", "REAL NOT NULL DEFAULT 100.0"),
    ("supplier_mix_premium_pct", "REAL NOT NULL DEFAULT 0.0"),
    ("expedited_order_share_pct", "REAL NOT NULL DEFAULT 0.0"),
    ("max_backorder_units", "INTEGER NOT NULL DEFAULT 0"),
    ("planned_borrowing_amount", "REAL NOT NULL DEFAULT 0.0"),
)

TEAM_STATE_MIGRATIONS = (
    ("raw_material_inventory", "INTEGER NOT NULL DEFAULT 0"),
    ("backlog_units", "INTEGER NOT NULL DEFAULT 0"),
    ("open_material_orders_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("short_term_debt_balance", "REAL NOT NULL DEFAULT 0.0"),
    ("interest_expense_last_round", "REAL NOT NULL DEFAULT 0.0"),
    ("liquidity_warning_flag", "INTEGER NOT NULL DEFAULT 0"),
    ("working_capital_stress_score", "REAL NOT NULL DEFAULT 0.0"),
)

ROUND_RESULT_MIGRATIONS = (
    ("active_product_count", "INTEGER NOT NULL DEFAULT 0"),
    ("active_project_count", "INTEGER NOT NULL DEFAULT 0"),
    ("launch_ready_project_count", "INTEGER NOT NULL DEFAULT 0"),
    ("launched_project_count", "INTEGER NOT NULL DEFAULT 0"),
    ("retired_product_count", "INTEGER NOT NULL DEFAULT 0"),
    ("weighted_average_selling_price", "REAL NOT NULL DEFAULT 0.0"),
    ("actual_production_units", "INTEGER NOT NULL DEFAULT 0"),
    ("innovation_investment", "REAL NOT NULL DEFAULT 0.0"),
    ("contribution_margin_per_unit", "REAL NOT NULL DEFAULT 0.0"),
    ("average_portfolio_tech_generation", "REAL NOT NULL DEFAULT 0.0"),
    ("cannibalized_demand_units", "REAL NOT NULL DEFAULT 0.0"),
    ("launch_events_text", "TEXT NOT NULL DEFAULT ''"),
    ("total_forecast_units", "INTEGER NOT NULL DEFAULT 0"),
    ("total_actual_demand_units", "REAL NOT NULL DEFAULT 0.0"),
    ("forecast_error_units", "REAL NOT NULL DEFAULT 0.0"),
    ("absolute_forecast_error_units", "REAL NOT NULL DEFAULT 0.0"),
    ("forecast_wape", "REAL NOT NULL DEFAULT 0.0"),
    ("service_gap_units", "REAL NOT NULL DEFAULT 0.0"),
    ("interest_expense", "REAL NOT NULL DEFAULT 0.0"),
    ("working_capital_requirement", "REAL NOT NULL DEFAULT 0.0"),
    ("planned_borrowing_amount", "REAL NOT NULL DEFAULT 0.0"),
    ("automatic_borrowing_amount", "REAL NOT NULL DEFAULT 0.0"),
    ("ending_cash_balance", "REAL NOT NULL DEFAULT 0.0"),
    ("short_term_debt_balance", "REAL NOT NULL DEFAULT 0.0"),
    ("liquidity_stress_flag", "INTEGER NOT NULL DEFAULT 0"),
)

PRODUCT_LINE_MIGRATIONS = (
    ("inventory_units", "INTEGER NOT NULL DEFAULT 0"),
    ("backlog_units", "INTEGER NOT NULL DEFAULT 0"),
    ("tech_generation", "INTEGER NOT NULL DEFAULT 1"),
    ("cannibalization_group", "TEXT NOT NULL DEFAULT ''"),
    ("launch_round", "INTEGER NOT NULL DEFAULT 0"),
    ("retirement_flag", "INTEGER NOT NULL DEFAULT 0"),
    ("retired_round", "INTEGER"),
    ("replacement_project_id", "TEXT"),
)

PRODUCT_DECISION_MIGRATIONS = (
    ("retire_flag", "INTEGER NOT NULL DEFAULT 0"),
    ("forecast_units", "INTEGER NOT NULL DEFAULT 0"),
)

PRODUCT_PROJECT_MIGRATIONS = ()

PRODUCT_ROUND_RESULT_MIGRATIONS = (
    ("tech_generation", "INTEGER NOT NULL DEFAULT 1"),
    ("cannibalization_group", "TEXT NOT NULL DEFAULT ''"),
    ("tech_gap_to_market", "INTEGER NOT NULL DEFAULT 0"),
    ("tech_attractiveness_adjustment", "REAL NOT NULL DEFAULT 1.0"),
    ("cannibalization_in_units", "REAL NOT NULL DEFAULT 0.0"),
    ("cannibalization_out_units", "REAL NOT NULL DEFAULT 0.0"),
    ("launched_this_round", "INTEGER NOT NULL DEFAULT 0"),
    ("launch_event", "TEXT NOT NULL DEFAULT ''"),
    ("retired_this_round", "INTEGER NOT NULL DEFAULT 0"),
    ("retirement_liquidation_revenue", "REAL NOT NULL DEFAULT 0.0"),
    ("forecast_units", "INTEGER NOT NULL DEFAULT 0"),
    ("actual_demand_units", "REAL NOT NULL DEFAULT 0.0"),
    ("forecast_error_units", "REAL NOT NULL DEFAULT 0.0"),
    ("absolute_error_units", "REAL NOT NULL DEFAULT 0.0"),
    ("forecast_bias_pct", "REAL NOT NULL DEFAULT 0.0"),
    ("mape_or_wape_value", "REAL NOT NULL DEFAULT 0.0"),
)


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
        _migrate_schema(connection)
    return database_path


def _migrate_schema(connection: sqlite3.Connection) -> None:
    """Apply additive migrations for older SQLite databases."""
    _ensure_columns(connection, "market_reports", MARKET_REPORT_MIGRATIONS)
    _ensure_columns(connection, "team_archetypes", TEAM_ARCHETYPE_MIGRATIONS)
    _ensure_columns(connection, "team_decisions", TEAM_DECISION_MIGRATIONS)
    _ensure_columns(connection, "team_states", TEAM_STATE_MIGRATIONS)
    _ensure_columns(connection, "round_results", ROUND_RESULT_MIGRATIONS)
    _ensure_columns(connection, "product_lines", PRODUCT_LINE_MIGRATIONS)
    _ensure_columns(connection, "product_decisions", PRODUCT_DECISION_MIGRATIONS)
    _ensure_columns(
        connection,
        "product_development_projects",
        PRODUCT_PROJECT_MIGRATIONS,
    )
    _ensure_columns(
        connection,
        "product_round_results",
        PRODUCT_ROUND_RESULT_MIGRATIONS,
    )


def _ensure_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: tuple[tuple[str, str], ...],
) -> None:
    """Add missing columns to a table without rebuilding it."""
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, column_sql in columns:
        if column_name in existing_columns:
            continue
        logger.info("Applying schema migration: add %s.%s", table_name, column_name)
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"
        )
