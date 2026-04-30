"""Application bootstrap helpers."""

from __future__ import annotations

import json
import logging
import os

from data.defaults import DEFAULT_MARKET_REPORT, DEFAULT_TEAM_ARCHETYPES, DEMO_USER_SEEDS
from utils.database import (
    DEVELOPMENT_ENVIRONMENT,
    get_connection,
    get_simulator_env,
    initialize_database,
)
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
            event,
            current_market_generation,
            technology_shift_rate,
            premium_tech_adoption,
            mid_market_tech_adoption,
            beginner_price_pressure
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            DEFAULT_MARKET_REPORT.current_market_generation,
            DEFAULT_MARKET_REPORT.technology_shift_rate,
            DEFAULT_MARKET_REPORT.premium_tech_adoption,
            DEFAULT_MARKET_REPORT.mid_market_tech_adoption,
            DEFAULT_MARKET_REPORT.beginner_price_pressure,
        ),
    )


def _seed_team_archetypes(connection) -> None:
    """Seed or refresh the archetype reference data."""
    existing_columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(team_archetypes)").fetchall()
    }

    def _active_templates(archetype):
        return [
            template
            for template in archetype.suggested_product_templates
            if template.is_active
        ] or list(archetype.suggested_product_templates)

    def _legacy_selling_price(archetype) -> float:
        templates = _active_templates(archetype)
        if not templates:
            return 130.0
        return round(
            sum(template.suggested_selling_price_per_unit for template in templates)
            / len(templates),
            2,
        )

    def _legacy_planned_production(archetype) -> int:
        return sum(
            template.suggested_planned_production_units
            for template in archetype.suggested_product_templates
            if template.is_active
        )

    def _legacy_qc_budget(archetype) -> float:
        templates = _active_templates(archetype)
        if not templates:
            return 3.0
        return round(
            sum(template.suggested_qc_budget_per_unit for template in templates)
            / len(templates),
            2,
        )

    def _legacy_target_inventory(archetype) -> int:
        return sum(
            template.suggested_target_finished_goods_inventory
            for template in archetype.suggested_product_templates
            if template.is_active
        )

    def _legacy_price_label(archetype) -> str:
        average_price = _legacy_selling_price(archetype)
        if average_price >= 165:
            return "Premium"
        if average_price <= 110:
            return "Beginner"
        return "Mid"

    def _legacy_capacity_plan(archetype) -> str:
        if archetype.suggested_capacity_expansion_units >= 40:
            return "Expand"
        if (
            archetype.suggested_capacity_expansion_units > 0
            or archetype.suggested_overtime_capacity_units > 0
        ):
            return "Selective Expansion"
        return "Maintain"

    def _legacy_quality_label(archetype) -> str:
        average_qc_budget = _legacy_qc_budget(archetype)
        if average_qc_budget >= 5.0:
            return "High"
        if average_qc_budget <= 2.0:
            return "Basic"
        return "Standard"

    def _legacy_inventory_posture(archetype) -> str:
        total_inventory = _legacy_target_inventory(archetype)
        if total_inventory >= 100:
            return "Build"
        if total_inventory <= 40:
            return "Lean"
        return "Balanced"

    def _legacy_supplier_choice(archetype) -> str:
        supplier_mix = {
            "Offshore Value": archetype.suggested_supplier_mix_offshore_pct,
            "Balanced Source": archetype.suggested_supplier_mix_balanced_pct,
            "Premium Reliable": archetype.suggested_supplier_mix_premium_pct,
        }
        return max(supplier_mix, key=supplier_mix.get)

    def _legacy_order_priority(archetype) -> str:
        if archetype.suggested_expedited_order_share_pct >= 50.0:
            return "Expedited"
        return "Standard"

    def _legacy_service_policy(archetype) -> str:
        if archetype.suggested_max_backorder_units > 0:
            return "Backorder"
        return "Lost Sales"

    all_columns = [
        "name",
        "description",
        "default_price_level",
        "default_capacity_plan",
        "default_quality_level",
        "default_inventory_posture",
        "base_cost",
        "base_capacity",
        "base_reputation",
        "base_defect_rate",
        "premium_fit",
        "mid_fit",
        "beginner_fit",
        "default_supplier_choice",
        "default_order_priority",
        "default_service_policy",
        "suggested_selling_price_per_unit",
        "suggested_planned_production_units",
        "suggested_qc_budget_per_unit",
        "suggested_target_finished_goods_inventory",
        "suggested_overtime_capacity_units",
        "suggested_capacity_expansion_units",
        "suggested_max_backorder_units",
        "suggested_raw_material_order_qty",
        "suggested_supplier_mix_offshore_pct",
        "suggested_supplier_mix_balanced_pct",
        "suggested_supplier_mix_premium_pct",
        "suggested_expedited_order_share_pct",
        "suggested_product_templates_json",
    ]
    insert_columns = [column for column in all_columns if column in existing_columns]
    placeholders = ", ".join("?" for _ in insert_columns)

    connection.execute("DELETE FROM team_archetypes")
    connection.executemany(
        f"""
        INSERT INTO team_archetypes ({", ".join(insert_columns)})
        VALUES ({placeholders})
        """,
        [
            tuple(
                {
                    "name": archetype.name,
                    "description": archetype.description,
                    "default_price_level": _legacy_price_label(archetype),
                    "default_capacity_plan": _legacy_capacity_plan(archetype),
                    "default_quality_level": _legacy_quality_label(archetype),
                    "default_inventory_posture": _legacy_inventory_posture(archetype),
                    "base_cost": archetype.base_cost,
                    "base_capacity": archetype.base_capacity,
                    "base_reputation": archetype.base_reputation,
                    "base_defect_rate": archetype.base_defect_rate,
                    "premium_fit": archetype.premium_fit,
                    "mid_fit": archetype.mid_fit,
                    "beginner_fit": archetype.beginner_fit,
                    "default_supplier_choice": _legacy_supplier_choice(archetype),
                    "default_order_priority": _legacy_order_priority(archetype),
                    "default_service_policy": _legacy_service_policy(archetype),
                    "suggested_selling_price_per_unit": _legacy_selling_price(archetype),
                    "suggested_planned_production_units": _legacy_planned_production(archetype),
                    "suggested_qc_budget_per_unit": _legacy_qc_budget(archetype),
                    "suggested_target_finished_goods_inventory": _legacy_target_inventory(archetype),
                    "suggested_overtime_capacity_units": archetype.suggested_overtime_capacity_units,
                    "suggested_capacity_expansion_units": archetype.suggested_capacity_expansion_units,
                    "suggested_max_backorder_units": archetype.suggested_max_backorder_units,
                    "suggested_raw_material_order_qty": archetype.suggested_raw_material_order_qty,
                    "suggested_supplier_mix_offshore_pct": archetype.suggested_supplier_mix_offshore_pct,
                    "suggested_supplier_mix_balanced_pct": archetype.suggested_supplier_mix_balanced_pct,
                    "suggested_supplier_mix_premium_pct": archetype.suggested_supplier_mix_premium_pct,
                    "suggested_expedited_order_share_pct": archetype.suggested_expedited_order_share_pct,
                    "suggested_product_templates_json": json.dumps(
                        [item.to_dict() for item in archetype.suggested_product_templates]
                    ),
                }[column]
                for column in insert_columns
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
