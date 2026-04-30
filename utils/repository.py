"""SQLite-backed repository helpers for simulator records."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from data.defaults import DEFAULT_MARKET_REPORT
from models.schemas import (
    PROJECT_SLOT_NAMES,
    AppUser,
    ClassroomRoundStatus,
    ForecastAccuracyResult,
    MarketReport,
    OpenMaterialOrder,
    PersistentTeamState,
    ProductDecision,
    ProductDevelopmentProject,
    ProductForecast,
    ProductLine,
    ProductRoundResult,
    RoundResult,
    TeamArchetype,
    TeamDecision,
    build_product_id,
    build_project_id,
)
from utils.bootstrap import ensure_app_storage
from utils.database import get_connection


VALID_ROLES = {"admin", "team_leader"}


def _legacy_capacity_plan(
    overtime_capacity_units: int,
    capacity_expansion_units: int,
) -> str:
    """Map numeric capacity inputs to the legacy capacity-plan label."""
    if capacity_expansion_units >= 40:
        return "Expand"
    if capacity_expansion_units > 0 or overtime_capacity_units > 0:
        return "Selective Expansion"
    return "Maintain"


def _legacy_supplier_choice(decision: TeamDecision) -> str:
    """Return the dominant supplier label from the numeric supplier mix."""
    supplier_mix = {
        "Offshore Value": decision.supplier_mix_offshore_pct,
        "Balanced Source": decision.supplier_mix_balanced_pct,
        "Premium Reliable": decision.supplier_mix_premium_pct,
    }
    return max(supplier_mix, key=supplier_mix.get)


def _legacy_order_priority(expedited_order_share_pct: float) -> str:
    """Map expedited share to the legacy order-priority label."""
    if expedited_order_share_pct >= 50.0:
        return "Expedited"
    return "Standard"


def _legacy_service_policy(max_backorder_units: int) -> str:
    """Map numeric backlog allowance to the legacy service label."""
    if max_backorder_units > 0:
        return "Backorder"
    return "Lost Sales"


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
            event,
            current_market_generation,
            technology_shift_rate,
            premium_tech_adoption,
            mid_market_tech_adoption,
            beginner_price_pressure
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
                current_market_generation,
                technology_shift_rate,
                premium_tech_adoption,
                mid_market_tech_adoption,
                beginner_price_pressure,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(round_number) DO UPDATE SET
                total_demand = excluded.total_demand,
                premium_share = excluded.premium_share,
                mid_share = excluded.mid_share,
                beginner_share = excluded.beginner_share,
                material_cost_index = excluded.material_cost_index,
                supply_risk = excluded.supply_risk,
                quality_sensitivity = excluded.quality_sensitivity,
                event = excluded.event,
                current_market_generation = excluded.current_market_generation,
                technology_shift_rate = excluded.technology_shift_rate,
                premium_tech_adoption = excluded.premium_tech_adoption,
                mid_market_tech_adoption = excluded.mid_market_tech_adoption,
                beginner_price_pressure = excluded.beginner_price_pressure,
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
                report.current_market_generation,
                report.technology_shift_rate,
                report.premium_tech_adoption,
                report.mid_market_tech_adoption,
                report.beginner_price_pressure,
            ),
        )


def advance_market_report_to_next_round(report: MarketReport | None = None) -> MarketReport:
    """Copy the completed round's market settings into the next editable round."""
    completed_report = report or load_market_report()
    payload = completed_report.to_dict()
    payload["round_number"] = completed_report.round_number + 1
    next_report = MarketReport.from_dict(payload)
    save_market_report(next_report)
    return next_report


def load_round_status(round_number: int | None = None) -> ClassroomRoundStatus:
    """Load instructor-controlled submission status for a round."""
    ensure_app_storage()
    effective_round = (
        round_number if round_number is not None else load_market_report().round_number
    )
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT round_number, submissions_open, notes
            FROM classroom_rounds
            WHERE round_number = ?
            """,
            (effective_round,),
        ).fetchone()

    if row is None:
        return ClassroomRoundStatus(round_number=effective_round, submissions_open=True)
    return ClassroomRoundStatus.from_dict(dict(row))


def save_round_status(status: ClassroomRoundStatus) -> None:
    """Persist instructor-controlled submission status for a round."""
    ensure_app_storage()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO classroom_rounds (
                round_number,
                submissions_open,
                notes,
                updated_at
            )
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(round_number) DO UPDATE SET
                submissions_open = excluded.submissions_open,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                status.round_number,
                1 if status.submissions_open else 0,
                status.notes,
            ),
        )


def set_round_submissions_open(
    round_number: int,
    submissions_open: bool,
    notes: str = "",
) -> ClassroomRoundStatus:
    """Open or close team submissions for a round."""
    status = ClassroomRoundStatus(
        round_number=round_number,
        submissions_open=submissions_open,
        notes=notes,
    )
    save_round_status(status)
    return status


def is_round_submission_open(round_number: int | None = None) -> bool:
    """Return whether team leaders may submit decisions for a round."""
    return load_round_status(round_number).submissions_open


def load_team_archetypes() -> list[TeamArchetype]:
    """Load all team archetypes."""
    ensure_app_storage()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                name,
                description,
                base_cost,
                base_capacity,
                base_reputation,
                base_defect_rate,
                premium_fit,
                mid_fit,
                beginner_fit,
                suggested_overtime_capacity_units,
                suggested_capacity_expansion_units,
                suggested_max_backorder_units,
                suggested_raw_material_order_qty,
                suggested_supplier_mix_offshore_pct,
                suggested_supplier_mix_balanced_pct,
                suggested_supplier_mix_premium_pct,
                suggested_expedited_order_share_pct,
                suggested_product_templates_json
            FROM team_archetypes
            ORDER BY name
            """
        ).fetchall()

    return [TeamArchetype.from_dict(dict(row)) for row in rows]


def load_team_decisions(
    round_number: int | None = None,
    team_name: str | None = None,
) -> list[TeamDecision]:
    """Load team-level firm decisions for a round."""
    ensure_app_storage()
    effective_round = (
        round_number if round_number is not None else load_market_report().round_number
    )
    query = """
        SELECT
            team_name,
            archetype,
            overtime_capacity_units,
            capacity_expansion_units,
            raw_material_order_qty,
            supplier_mix_offshore_pct,
            supplier_mix_balanced_pct,
            supplier_mix_premium_pct,
            expedited_order_share_pct,
            max_backorder_units,
            planned_borrowing_amount,
            capacity_plan,
            supplier_choice,
            order_priority,
            service_policy
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
    """Load one team's firm decision for a specific round."""
    decisions = load_team_decisions(round_number=round_number, team_name=team_name)
    return decisions[0] if decisions else None


def save_team_decision(
    decision: TeamDecision,
    round_number: int,
    submitted_by_user_id: int | None = None,
) -> None:
    """Insert or update one team's firm-level decision for the round."""
    ensure_app_storage()
    payload = {
        "round_number": round_number,
        "team_name": decision.team_name,
        "archetype": decision.archetype,
        "overtime_capacity_units": decision.overtime_capacity_units,
        "capacity_expansion_units": decision.capacity_expansion_units,
        "raw_material_order_qty": decision.raw_material_order_qty,
        "supplier_mix_offshore_pct": decision.supplier_mix_offshore_pct,
        "supplier_mix_balanced_pct": decision.supplier_mix_balanced_pct,
        "supplier_mix_premium_pct": decision.supplier_mix_premium_pct,
        "expedited_order_share_pct": decision.expedited_order_share_pct,
        "max_backorder_units": decision.max_backorder_units,
        "planned_borrowing_amount": decision.planned_borrowing_amount,
        "selling_price_per_unit": 0.0,
        "planned_production_units": 0,
        "qc_budget_per_unit": 0.0,
        "target_finished_goods_inventory": 0,
        "price_level": "",
        "production_quantity": 0,
        "capacity_plan": _legacy_capacity_plan(
            decision.overtime_capacity_units,
            decision.capacity_expansion_units,
        ),
        "quality_level": "",
        "inventory_posture": "",
        "supplier_choice": _legacy_supplier_choice(decision),
        "order_priority": _legacy_order_priority(decision.expedited_order_share_pct),
        "service_policy": _legacy_service_policy(decision.max_backorder_units),
        "submitted_by_user_id": submitted_by_user_id,
    }

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO team_decisions (
                round_number,
                team_name,
                archetype,
                overtime_capacity_units,
                capacity_expansion_units,
                raw_material_order_qty,
                supplier_mix_offshore_pct,
                supplier_mix_balanced_pct,
                supplier_mix_premium_pct,
                expedited_order_share_pct,
                max_backorder_units,
                planned_borrowing_amount,
                selling_price_per_unit,
                planned_production_units,
                qc_budget_per_unit,
                target_finished_goods_inventory,
                price_level,
                production_quantity,
                capacity_plan,
                quality_level,
                inventory_posture,
                supplier_choice,
                order_priority,
                service_policy,
                submitted_by_user_id,
                updated_at
            )
            VALUES (
                :round_number,
                :team_name,
                :archetype,
                :overtime_capacity_units,
                :capacity_expansion_units,
                :raw_material_order_qty,
                :supplier_mix_offshore_pct,
                :supplier_mix_balanced_pct,
                :supplier_mix_premium_pct,
                :expedited_order_share_pct,
                :max_backorder_units,
                :planned_borrowing_amount,
                :selling_price_per_unit,
                :planned_production_units,
                :qc_budget_per_unit,
                :target_finished_goods_inventory,
                :price_level,
                :production_quantity,
                :capacity_plan,
                :quality_level,
                :inventory_posture,
                :supplier_choice,
                :order_priority,
                :service_policy,
                :submitted_by_user_id,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(round_number, team_name) DO UPDATE SET
                archetype = excluded.archetype,
                overtime_capacity_units = excluded.overtime_capacity_units,
                capacity_expansion_units = excluded.capacity_expansion_units,
                raw_material_order_qty = excluded.raw_material_order_qty,
                supplier_mix_offshore_pct = excluded.supplier_mix_offshore_pct,
                supplier_mix_balanced_pct = excluded.supplier_mix_balanced_pct,
                supplier_mix_premium_pct = excluded.supplier_mix_premium_pct,
                expedited_order_share_pct = excluded.expedited_order_share_pct,
                max_backorder_units = excluded.max_backorder_units,
                planned_borrowing_amount = excluded.planned_borrowing_amount,
                selling_price_per_unit = excluded.selling_price_per_unit,
                planned_production_units = excluded.planned_production_units,
                qc_budget_per_unit = excluded.qc_budget_per_unit,
                target_finished_goods_inventory = excluded.target_finished_goods_inventory,
                price_level = excluded.price_level,
                production_quantity = excluded.production_quantity,
                capacity_plan = excluded.capacity_plan,
                quality_level = excluded.quality_level,
                inventory_posture = excluded.inventory_posture,
                supplier_choice = excluded.supplier_choice,
                order_priority = excluded.order_priority,
                service_policy = excluded.service_policy,
                submitted_by_user_id = excluded.submitted_by_user_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            payload,
        )


def load_product_lines(team_name: str | None = None) -> list[ProductLine]:
    """Load persistent product lines, optionally filtered to one team."""
    ensure_app_storage()
    query = """
        SELECT
            product_id,
            team_name,
            product_name,
            slot_name,
            is_active,
            target_segment,
            lifecycle_stage,
            age_in_rounds,
            base_defect_rate_modifier,
            base_demand_fit_modifier,
            tech_generation,
            cannibalization_group,
            launch_round,
            retirement_flag,
            retired_round,
            replacement_project_id,
            inventory_units,
            backlog_units
        FROM product_lines
        WHERE 1 = 1
    """
    parameters: list[Any] = []

    if team_name:
        query += " AND LOWER(team_name) = LOWER(?)"
        parameters.append(team_name)

    query += " ORDER BY team_name, slot_name"

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [ProductLine.from_dict(dict(row)) for row in rows]


def save_product_lines(product_lines: list[ProductLine]) -> None:
    """Persist product line state for one or more teams."""
    if not product_lines:
        return

    ensure_app_storage()
    payloads = []
    for product_line in product_lines:
        payload = product_line.to_dict()
        payload["is_active"] = 1 if product_line.is_active else 0
        payload["retirement_flag"] = 1 if product_line.retirement_flag else 0
        payloads.append(payload)

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO product_lines (
                product_id,
                team_name,
                product_name,
                slot_name,
                is_active,
                target_segment,
                lifecycle_stage,
                age_in_rounds,
                base_defect_rate_modifier,
                base_demand_fit_modifier,
                tech_generation,
                cannibalization_group,
                launch_round,
                retirement_flag,
                retired_round,
                replacement_project_id,
                inventory_units,
                backlog_units,
                updated_at
            )
            VALUES (
                :product_id,
                :team_name,
                :product_name,
                :slot_name,
                :is_active,
                :target_segment,
                :lifecycle_stage,
                :age_in_rounds,
                :base_defect_rate_modifier,
                :base_demand_fit_modifier,
                :tech_generation,
                :cannibalization_group,
                :launch_round,
                :retirement_flag,
                :retired_round,
                :replacement_project_id,
                :inventory_units,
                :backlog_units,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(product_id) DO UPDATE SET
                team_name = excluded.team_name,
                product_name = excluded.product_name,
                slot_name = excluded.slot_name,
                is_active = excluded.is_active,
                target_segment = excluded.target_segment,
                lifecycle_stage = excluded.lifecycle_stage,
                age_in_rounds = excluded.age_in_rounds,
                base_defect_rate_modifier = excluded.base_defect_rate_modifier,
                base_demand_fit_modifier = excluded.base_demand_fit_modifier,
                tech_generation = excluded.tech_generation,
                cannibalization_group = excluded.cannibalization_group,
                launch_round = excluded.launch_round,
                retirement_flag = excluded.retirement_flag,
                retired_round = excluded.retired_round,
                replacement_project_id = excluded.replacement_project_id,
                inventory_units = excluded.inventory_units,
                backlog_units = excluded.backlog_units,
                updated_at = CURRENT_TIMESTAMP
            """,
            payloads,
        )


def ensure_product_lines_for_team(
    team_name: str,
    archetype_name: str,
) -> list[ProductLine]:
    """Ensure that a team has the default three product slots."""
    ensure_app_storage()
    existing_lines = load_product_lines(team_name=team_name)
    existing_by_slot = {item.slot_name: item for item in existing_lines}
    if len(existing_by_slot) == 3:
        return sorted(existing_lines, key=lambda item: item.slot_name)

    archetype_lookup = {item.name: item for item in load_team_archetypes()}
    archetype = archetype_lookup.get(archetype_name)
    if archetype is None:
        raise ValueError(f"Unknown archetype: {archetype_name}")

    created_lines: list[ProductLine] = list(existing_lines)
    for template in archetype.suggested_product_templates:
        if template.slot_name in existing_by_slot:
            continue
        created_lines.append(
            ProductLine(
                product_id=build_product_id(team_name, template.slot_name),
                team_name=team_name,
                product_name=template.product_name,
                slot_name=template.slot_name,
                is_active=template.is_active,
                target_segment=template.target_segment,
                lifecycle_stage=template.lifecycle_stage,
                age_in_rounds=template.age_in_rounds,
                base_defect_rate_modifier=template.base_defect_rate_modifier,
                base_demand_fit_modifier=template.base_demand_fit_modifier,
                tech_generation=template.tech_generation,
                cannibalization_group=template.cannibalization_group,
                launch_round=template.launch_round,
                retirement_flag=template.retirement_flag,
                retired_round=template.retired_round,
                replacement_project_id=template.replacement_project_id,
                inventory_units=0,
                backlog_units=0,
            )
        )

    save_product_lines(created_lines)
    return sorted(created_lines, key=lambda item: item.slot_name)


def load_product_decisions(
    round_number: int | None = None,
    team_name: str | None = None,
) -> list[ProductDecision]:
    """Load product-level decisions for a round."""
    ensure_app_storage()
    effective_round = (
        round_number if round_number is not None else load_market_report().round_number
    )
    query = """
        SELECT
            product_id,
            team_name,
            slot_name,
            product_name,
            is_active,
            target_segment,
            selling_price_per_unit,
            forecast_units,
            planned_production_units,
            qc_budget_per_unit,
            target_finished_goods_inventory,
            retire_flag
        FROM product_decisions
        WHERE round_number = ?
    """
    parameters: list[Any] = [effective_round]

    if team_name:
        query += " AND LOWER(team_name) = LOWER(?)"
        parameters.append(team_name)

    query += " ORDER BY team_name, slot_name"

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [ProductDecision.from_dict(dict(row)) for row in rows]


def save_product_decisions(
    product_decisions: list[ProductDecision],
    round_number: int,
) -> None:
    """Persist product-level decisions for the round."""
    if not product_decisions:
        return

    ensure_app_storage()
    payloads = []
    for decision in product_decisions:
        payload = decision.to_dict()
        payload["round_number"] = round_number
        payload["is_active"] = 1 if decision.is_active else 0
        payload["retire_flag"] = 1 if decision.retire_flag else 0
        payloads.append(payload)

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO product_decisions (
                round_number,
                team_name,
                product_id,
                slot_name,
                product_name,
                is_active,
                target_segment,
                selling_price_per_unit,
                forecast_units,
                planned_production_units,
                qc_budget_per_unit,
                target_finished_goods_inventory,
                retire_flag,
                updated_at
            )
            VALUES (
                :round_number,
                :team_name,
                :product_id,
                :slot_name,
                :product_name,
                :is_active,
                :target_segment,
                :selling_price_per_unit,
                :forecast_units,
                :planned_production_units,
                :qc_budget_per_unit,
                :target_finished_goods_inventory,
                :retire_flag,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(round_number, team_name, slot_name) DO UPDATE SET
                product_id = excluded.product_id,
                product_name = excluded.product_name,
                is_active = excluded.is_active,
                target_segment = excluded.target_segment,
                selling_price_per_unit = excluded.selling_price_per_unit,
                forecast_units = excluded.forecast_units,
                planned_production_units = excluded.planned_production_units,
                qc_budget_per_unit = excluded.qc_budget_per_unit,
                target_finished_goods_inventory = excluded.target_finished_goods_inventory,
                retire_flag = excluded.retire_flag,
                updated_at = CURRENT_TIMESTAMP
            """,
            payloads,
        )


def load_product_forecasts(
    round_number: int | None = None,
    team_name: str | None = None,
) -> list[ProductForecast]:
    """Load per-product forecasts for a round."""
    ensure_app_storage()
    effective_round = (
        round_number if round_number is not None else load_market_report().round_number
    )
    query = """
        SELECT
            round_number,
            team_name,
            product_id,
            slot_name,
            product_name,
            forecast_units
        FROM product_forecasts
        WHERE round_number = ?
    """
    parameters: list[Any] = [effective_round]

    if team_name:
        query += " AND LOWER(team_name) = LOWER(?)"
        parameters.append(team_name)

    query += " ORDER BY team_name, slot_name"

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [ProductForecast.from_dict(dict(row)) for row in rows]


def save_product_forecasts(forecasts: list[ProductForecast]) -> None:
    """Persist per-product forecasts for a round."""
    if not forecasts:
        return

    ensure_app_storage()
    payloads = [forecast.to_dict() for forecast in forecasts]
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO product_forecasts (
                round_number,
                team_name,
                product_id,
                slot_name,
                product_name,
                forecast_units,
                updated_at
            )
            VALUES (
                :round_number,
                :team_name,
                :product_id,
                :slot_name,
                :product_name,
                :forecast_units,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(round_number, team_name, slot_name) DO UPDATE SET
                product_id = excluded.product_id,
                product_name = excluded.product_name,
                forecast_units = excluded.forecast_units,
                updated_at = CURRENT_TIMESTAMP
            """,
            payloads,
        )


def load_product_development_projects(
    team_name: str | None = None,
) -> list[ProductDevelopmentProject]:
    """Load development-project slots for one or all teams."""
    ensure_app_storage()
    query = """
        SELECT
            project_id,
            team_name,
            project_slot_name,
            project_name,
            target_segment,
            target_tech_generation,
            intended_slot_name,
            required_investment,
            cumulative_investment,
            investment_this_round,
            testing_intensity,
            launch_readiness_score,
            planned_launch_round,
            earliest_launch_round,
            status,
            cannibalization_group,
            projected_base_defect_modifier,
            projected_demand_fit_modifier,
            created_round,
            launched_round,
            canceled_round,
            launch_now,
            cancel_now,
            replaced_product_name
        FROM product_development_projects
        WHERE 1 = 1
    """
    parameters: list[Any] = []

    if team_name:
        query += " AND LOWER(team_name) = LOWER(?)"
        parameters.append(team_name)

    query += " ORDER BY team_name, project_slot_name"

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [ProductDevelopmentProject.from_dict(dict(row)) for row in rows]


def save_product_development_projects(
    projects: list[ProductDevelopmentProject],
) -> None:
    """Persist development project slots."""
    if not projects:
        return

    ensure_app_storage()
    payloads = []
    for project in projects:
        payload = project.to_dict()
        payload["launch_now"] = 1 if project.launch_now else 0
        payload["cancel_now"] = 1 if project.cancel_now else 0
        payloads.append(payload)

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO product_development_projects (
                project_id,
                team_name,
                project_slot_name,
                project_name,
                target_segment,
                target_tech_generation,
                intended_slot_name,
                required_investment,
                cumulative_investment,
                investment_this_round,
                testing_intensity,
                launch_readiness_score,
                planned_launch_round,
                earliest_launch_round,
                status,
                cannibalization_group,
                projected_base_defect_modifier,
                projected_demand_fit_modifier,
                created_round,
                launched_round,
                canceled_round,
                launch_now,
                cancel_now,
                replaced_product_name,
                updated_at
            )
            VALUES (
                :project_id,
                :team_name,
                :project_slot_name,
                :project_name,
                :target_segment,
                :target_tech_generation,
                :intended_slot_name,
                :required_investment,
                :cumulative_investment,
                :investment_this_round,
                :testing_intensity,
                :launch_readiness_score,
                :planned_launch_round,
                :earliest_launch_round,
                :status,
                :cannibalization_group,
                :projected_base_defect_modifier,
                :projected_demand_fit_modifier,
                :created_round,
                :launched_round,
                :canceled_round,
                :launch_now,
                :cancel_now,
                :replaced_product_name,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(project_id) DO UPDATE SET
                team_name = excluded.team_name,
                project_slot_name = excluded.project_slot_name,
                project_name = excluded.project_name,
                target_segment = excluded.target_segment,
                target_tech_generation = excluded.target_tech_generation,
                intended_slot_name = excluded.intended_slot_name,
                required_investment = excluded.required_investment,
                cumulative_investment = excluded.cumulative_investment,
                investment_this_round = excluded.investment_this_round,
                testing_intensity = excluded.testing_intensity,
                launch_readiness_score = excluded.launch_readiness_score,
                planned_launch_round = excluded.planned_launch_round,
                earliest_launch_round = excluded.earliest_launch_round,
                status = excluded.status,
                cannibalization_group = excluded.cannibalization_group,
                projected_base_defect_modifier = excluded.projected_base_defect_modifier,
                projected_demand_fit_modifier = excluded.projected_demand_fit_modifier,
                created_round = excluded.created_round,
                launched_round = excluded.launched_round,
                canceled_round = excluded.canceled_round,
                launch_now = excluded.launch_now,
                cancel_now = excluded.cancel_now,
                replaced_product_name = excluded.replaced_product_name,
                updated_at = CURRENT_TIMESTAMP
            """,
            payloads,
        )


def ensure_development_projects_for_team(team_name: str) -> list[ProductDevelopmentProject]:
    """Ensure a team has two editable development-project slots."""
    ensure_app_storage()
    existing_projects = load_product_development_projects(team_name=team_name)
    existing_by_slot = {
        item.project_slot_name: item for item in existing_projects
    }
    if len(existing_by_slot) == len(PROJECT_SLOT_NAMES):
        return sorted(existing_projects, key=lambda item: item.project_slot_name)

    current_round = load_market_report().round_number
    created_projects: list[ProductDevelopmentProject] = list(existing_projects)
    for project_slot_name in PROJECT_SLOT_NAMES:
        if project_slot_name in existing_by_slot:
            continue
        created_projects.append(
            ProductDevelopmentProject(
                project_id=build_project_id(team_name, project_slot_name),
                team_name=team_name,
                project_slot_name=project_slot_name,
                project_name="",
                target_segment="mid",
                target_tech_generation=2,
                intended_slot_name="C",
                required_investment=0.0,
                cumulative_investment=0.0,
                investment_this_round=0.0,
                testing_intensity=0.0,
                launch_readiness_score=0.0,
                planned_launch_round=current_round + 1,
                earliest_launch_round=current_round + 1,
                status="concept",
                cannibalization_group="",
                projected_base_defect_modifier=0.0,
                projected_demand_fit_modifier=1.0,
                created_round=current_round,
            )
        )

    save_product_development_projects(created_projects)
    return sorted(created_projects, key=lambda item: item.project_slot_name)


def load_round_results(
    round_number: int | None = None,
    team_name: str | None = None,
) -> list[RoundResult]:
    """Load aggregate team-level round results."""
    ensure_app_storage()
    query = """
        SELECT
            round_number,
            team_name,
            archetype,
            active_product_count,
            active_project_count,
            launch_ready_project_count,
            launched_project_count,
            retired_product_count,
            total_forecast_units,
            total_actual_demand_units,
            forecast_error_units,
            absolute_forecast_error_units,
            forecast_wape,
            service_gap_units,
            weighted_average_selling_price,
            planned_production_units,
            actual_production_units,
            effective_capacity_units,
            utilization_pct,
            weighted_material_unit_cost,
            defect_rate,
            good_units_produced,
            demand_allocated,
            sales_units,
            lost_sales_units,
            backlog_units_end,
            ending_inventory,
            ending_raw_material_inventory,
            fill_rate,
            revenue,
            procurement_cost,
            production_cost,
            holding_cost,
            warranty_cost,
            backlog_cost,
            expansion_cost,
            innovation_investment,
            interest_expense,
            working_capital_requirement,
            planned_borrowing_amount,
            automatic_borrowing_amount,
            ending_cash_balance,
            short_term_debt_balance,
            liquidity_stress_flag,
            total_cost,
            profit,
            contribution_margin_per_unit,
            reputation_after_round,
            average_portfolio_tech_generation,
            cannibalized_demand_units,
            beginning_finished_goods_inventory,
            beginning_raw_material_inventory,
            raw_material_units_received,
            raw_material_units_consumed,
            raw_material_order_qty,
            backlog_units_start,
            launch_events_text,
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
    """Persist aggregate team-level round results."""
    if not results:
        return

    ensure_app_storage()
    payloads = []
    for result in results:
        payload = result.to_dict()
        payload["liquidity_stress_flag"] = 1 if result.liquidity_stress_flag else 0
        payload["stockout_units"] = result.lost_sales_units + result.backlog_units_end
        payload["unit_price"] = result.weighted_average_selling_price
        payload["available_capacity"] = result.effective_capacity_units
        payload["starting_raw_material_inventory"] = result.beginning_raw_material_inventory
        payload["raw_material_ordered"] = result.raw_material_order_qty
        payload["raw_material_inventory_end"] = result.ending_raw_material_inventory
        payload["supplier_choice"] = ""
        payload["order_priority"] = ""
        payload["service_policy"] = ""
        payloads.append(payload)

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO round_results (
                round_number,
                team_name,
                archetype,
                active_product_count,
                active_project_count,
                launch_ready_project_count,
                launched_project_count,
                retired_product_count,
                total_forecast_units,
                total_actual_demand_units,
                forecast_error_units,
                absolute_forecast_error_units,
                forecast_wape,
                service_gap_units,
                weighted_average_selling_price,
                planned_production_units,
                actual_production_units,
                effective_capacity_units,
                utilization_pct,
                weighted_material_unit_cost,
                defect_rate,
                good_units_produced,
                demand_allocated,
                sales_units,
                stockout_units,
                lost_sales_units,
                backlog_units_end,
                ending_inventory,
                ending_raw_material_inventory,
                fill_rate,
                unit_price,
                revenue,
                procurement_cost,
                production_cost,
                holding_cost,
                warranty_cost,
                backlog_cost,
                expansion_cost,
                innovation_investment,
                interest_expense,
                working_capital_requirement,
                planned_borrowing_amount,
                automatic_borrowing_amount,
                ending_cash_balance,
                short_term_debt_balance,
                liquidity_stress_flag,
                total_cost,
                profit,
                contribution_margin_per_unit,
                reputation_after_round,
                average_portfolio_tech_generation,
                cannibalized_demand_units,
                available_capacity,
                beginning_finished_goods_inventory,
                beginning_raw_material_inventory,
                raw_material_units_received,
                raw_material_units_consumed,
                raw_material_order_qty,
                starting_raw_material_inventory,
                raw_material_ordered,
                raw_material_inventory_end,
                backlog_units_start,
                supplier_choice,
                order_priority,
                service_policy,
                launch_events_text,
                notes,
                updated_at
            )
            VALUES (
                :round_number,
                :team_name,
                :archetype,
                :active_product_count,
                :active_project_count,
                :launch_ready_project_count,
                :launched_project_count,
                :retired_product_count,
                :total_forecast_units,
                :total_actual_demand_units,
                :forecast_error_units,
                :absolute_forecast_error_units,
                :forecast_wape,
                :service_gap_units,
                :weighted_average_selling_price,
                :planned_production_units,
                :actual_production_units,
                :effective_capacity_units,
                :utilization_pct,
                :weighted_material_unit_cost,
                :defect_rate,
                :good_units_produced,
                :demand_allocated,
                :sales_units,
                :stockout_units,
                :lost_sales_units,
                :backlog_units_end,
                :ending_inventory,
                :ending_raw_material_inventory,
                :fill_rate,
                :unit_price,
                :revenue,
                :procurement_cost,
                :production_cost,
                :holding_cost,
                :warranty_cost,
                :backlog_cost,
                :expansion_cost,
                :innovation_investment,
                :interest_expense,
                :working_capital_requirement,
                :planned_borrowing_amount,
                :automatic_borrowing_amount,
                :ending_cash_balance,
                :short_term_debt_balance,
                :liquidity_stress_flag,
                :total_cost,
                :profit,
                :contribution_margin_per_unit,
                :reputation_after_round,
                :average_portfolio_tech_generation,
                :cannibalized_demand_units,
                :available_capacity,
                :beginning_finished_goods_inventory,
                :beginning_raw_material_inventory,
                :raw_material_units_received,
                :raw_material_units_consumed,
                :raw_material_order_qty,
                :starting_raw_material_inventory,
                :raw_material_ordered,
                :raw_material_inventory_end,
                :backlog_units_start,
                :supplier_choice,
                :order_priority,
                :service_policy,
                :launch_events_text,
                :notes,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(round_number, team_name) DO UPDATE SET
                archetype = excluded.archetype,
                active_product_count = excluded.active_product_count,
                active_project_count = excluded.active_project_count,
                launch_ready_project_count = excluded.launch_ready_project_count,
                launched_project_count = excluded.launched_project_count,
                retired_product_count = excluded.retired_product_count,
                total_forecast_units = excluded.total_forecast_units,
                total_actual_demand_units = excluded.total_actual_demand_units,
                forecast_error_units = excluded.forecast_error_units,
                absolute_forecast_error_units = excluded.absolute_forecast_error_units,
                forecast_wape = excluded.forecast_wape,
                service_gap_units = excluded.service_gap_units,
                weighted_average_selling_price = excluded.weighted_average_selling_price,
                planned_production_units = excluded.planned_production_units,
                actual_production_units = excluded.actual_production_units,
                effective_capacity_units = excluded.effective_capacity_units,
                utilization_pct = excluded.utilization_pct,
                weighted_material_unit_cost = excluded.weighted_material_unit_cost,
                defect_rate = excluded.defect_rate,
                good_units_produced = excluded.good_units_produced,
                demand_allocated = excluded.demand_allocated,
                sales_units = excluded.sales_units,
                stockout_units = excluded.stockout_units,
                lost_sales_units = excluded.lost_sales_units,
                backlog_units_end = excluded.backlog_units_end,
                ending_inventory = excluded.ending_inventory,
                ending_raw_material_inventory = excluded.ending_raw_material_inventory,
                fill_rate = excluded.fill_rate,
                unit_price = excluded.unit_price,
                revenue = excluded.revenue,
                procurement_cost = excluded.procurement_cost,
                production_cost = excluded.production_cost,
                holding_cost = excluded.holding_cost,
                warranty_cost = excluded.warranty_cost,
                backlog_cost = excluded.backlog_cost,
                expansion_cost = excluded.expansion_cost,
                innovation_investment = excluded.innovation_investment,
                interest_expense = excluded.interest_expense,
                working_capital_requirement = excluded.working_capital_requirement,
                planned_borrowing_amount = excluded.planned_borrowing_amount,
                automatic_borrowing_amount = excluded.automatic_borrowing_amount,
                ending_cash_balance = excluded.ending_cash_balance,
                short_term_debt_balance = excluded.short_term_debt_balance,
                liquidity_stress_flag = excluded.liquidity_stress_flag,
                total_cost = excluded.total_cost,
                profit = excluded.profit,
                contribution_margin_per_unit = excluded.contribution_margin_per_unit,
                reputation_after_round = excluded.reputation_after_round,
                average_portfolio_tech_generation = excluded.average_portfolio_tech_generation,
                cannibalized_demand_units = excluded.cannibalized_demand_units,
                available_capacity = excluded.available_capacity,
                beginning_finished_goods_inventory = excluded.beginning_finished_goods_inventory,
                beginning_raw_material_inventory = excluded.beginning_raw_material_inventory,
                raw_material_units_received = excluded.raw_material_units_received,
                raw_material_units_consumed = excluded.raw_material_units_consumed,
                raw_material_order_qty = excluded.raw_material_order_qty,
                starting_raw_material_inventory = excluded.starting_raw_material_inventory,
                raw_material_ordered = excluded.raw_material_ordered,
                raw_material_inventory_end = excluded.raw_material_inventory_end,
                backlog_units_start = excluded.backlog_units_start,
                supplier_choice = excluded.supplier_choice,
                order_priority = excluded.order_priority,
                service_policy = excluded.service_policy,
                launch_events_text = excluded.launch_events_text,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            payloads,
        )


def load_product_round_results(
    round_number: int | None = None,
    team_name: str | None = None,
) -> list[ProductRoundResult]:
    """Load product-level round results."""
    ensure_app_storage()
    query = """
        SELECT
            round_number,
            team_name,
            product_id,
            product_name,
            slot_name,
            target_segment,
            lifecycle_stage,
            age_in_rounds,
            tech_generation,
            cannibalization_group,
            selling_price_per_unit,
            forecast_units,
            planned_production_units,
            actual_production_units,
            defect_rate,
            good_units_produced,
            demand_allocated,
            actual_demand_units,
            sales_units,
            lost_sales_units,
            ending_inventory,
            fill_rate,
            forecast_error_units,
            absolute_error_units,
            forecast_bias_pct,
            mape_or_wape_value,
            revenue,
            production_cost,
            holding_cost,
            warranty_cost,
            allocated_procurement_cost,
            allocated_backlog_cost,
            allocated_expansion_cost,
            contribution_margin_per_unit,
            profit_contribution,
            beginning_inventory,
            backlog_units_start,
            backlog_units_end,
            tech_gap_to_market,
            tech_attractiveness_adjustment,
            cannibalization_in_units,
            cannibalization_out_units,
            launched_this_round,
            launch_event,
            retired_this_round,
            retirement_liquidation_revenue,
            notes
        FROM product_round_results
        WHERE 1 = 1
    """
    parameters: list[Any] = []

    if round_number is not None:
        query += " AND round_number = ?"
        parameters.append(round_number)

    if team_name:
        query += " AND LOWER(team_name) = LOWER(?)"
        parameters.append(team_name)

    query += " ORDER BY round_number DESC, team_name, slot_name"

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [ProductRoundResult.from_dict(dict(row)) for row in rows]


def save_product_round_results(results: list[ProductRoundResult]) -> None:
    """Persist product-level round results."""
    if not results:
        return

    ensure_app_storage()
    payloads = []
    for result in results:
        payload = result.to_dict()
        payload["launched_this_round"] = 1 if result.launched_this_round else 0
        payload["retired_this_round"] = 1 if result.retired_this_round else 0
        payloads.append(payload)

    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO product_round_results (
                round_number,
                team_name,
                product_id,
                product_name,
                slot_name,
                target_segment,
                lifecycle_stage,
                age_in_rounds,
                tech_generation,
                cannibalization_group,
                selling_price_per_unit,
                forecast_units,
                planned_production_units,
                actual_production_units,
                defect_rate,
                good_units_produced,
                demand_allocated,
                actual_demand_units,
                sales_units,
                lost_sales_units,
                ending_inventory,
                fill_rate,
                forecast_error_units,
                absolute_error_units,
                forecast_bias_pct,
                mape_or_wape_value,
                revenue,
                production_cost,
                holding_cost,
                warranty_cost,
                allocated_procurement_cost,
                allocated_backlog_cost,
                allocated_expansion_cost,
                contribution_margin_per_unit,
                profit_contribution,
                beginning_inventory,
                backlog_units_start,
                backlog_units_end,
                tech_gap_to_market,
                tech_attractiveness_adjustment,
                cannibalization_in_units,
                cannibalization_out_units,
                launched_this_round,
                launch_event,
                retired_this_round,
                retirement_liquidation_revenue,
                notes,
                updated_at
            )
            VALUES (
                :round_number,
                :team_name,
                :product_id,
                :product_name,
                :slot_name,
                :target_segment,
                :lifecycle_stage,
                :age_in_rounds,
                :tech_generation,
                :cannibalization_group,
                :selling_price_per_unit,
                :forecast_units,
                :planned_production_units,
                :actual_production_units,
                :defect_rate,
                :good_units_produced,
                :demand_allocated,
                :actual_demand_units,
                :sales_units,
                :lost_sales_units,
                :ending_inventory,
                :fill_rate,
                :forecast_error_units,
                :absolute_error_units,
                :forecast_bias_pct,
                :mape_or_wape_value,
                :revenue,
                :production_cost,
                :holding_cost,
                :warranty_cost,
                :allocated_procurement_cost,
                :allocated_backlog_cost,
                :allocated_expansion_cost,
                :contribution_margin_per_unit,
                :profit_contribution,
                :beginning_inventory,
                :backlog_units_start,
                :backlog_units_end,
                :tech_gap_to_market,
                :tech_attractiveness_adjustment,
                :cannibalization_in_units,
                :cannibalization_out_units,
                :launched_this_round,
                :launch_event,
                :retired_this_round,
                :retirement_liquidation_revenue,
                :notes,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(round_number, team_name, slot_name) DO UPDATE SET
                product_id = excluded.product_id,
                product_name = excluded.product_name,
                target_segment = excluded.target_segment,
                lifecycle_stage = excluded.lifecycle_stage,
                age_in_rounds = excluded.age_in_rounds,
                tech_generation = excluded.tech_generation,
                cannibalization_group = excluded.cannibalization_group,
                selling_price_per_unit = excluded.selling_price_per_unit,
                forecast_units = excluded.forecast_units,
                planned_production_units = excluded.planned_production_units,
                actual_production_units = excluded.actual_production_units,
                defect_rate = excluded.defect_rate,
                good_units_produced = excluded.good_units_produced,
                demand_allocated = excluded.demand_allocated,
                actual_demand_units = excluded.actual_demand_units,
                sales_units = excluded.sales_units,
                lost_sales_units = excluded.lost_sales_units,
                ending_inventory = excluded.ending_inventory,
                fill_rate = excluded.fill_rate,
                forecast_error_units = excluded.forecast_error_units,
                absolute_error_units = excluded.absolute_error_units,
                forecast_bias_pct = excluded.forecast_bias_pct,
                mape_or_wape_value = excluded.mape_or_wape_value,
                revenue = excluded.revenue,
                production_cost = excluded.production_cost,
                holding_cost = excluded.holding_cost,
                warranty_cost = excluded.warranty_cost,
                allocated_procurement_cost = excluded.allocated_procurement_cost,
                allocated_backlog_cost = excluded.allocated_backlog_cost,
                allocated_expansion_cost = excluded.allocated_expansion_cost,
                contribution_margin_per_unit = excluded.contribution_margin_per_unit,
                profit_contribution = excluded.profit_contribution,
                beginning_inventory = excluded.beginning_inventory,
                backlog_units_start = excluded.backlog_units_start,
                backlog_units_end = excluded.backlog_units_end,
                tech_gap_to_market = excluded.tech_gap_to_market,
                tech_attractiveness_adjustment = excluded.tech_attractiveness_adjustment,
                cannibalization_in_units = excluded.cannibalization_in_units,
                cannibalization_out_units = excluded.cannibalization_out_units,
                launched_this_round = excluded.launched_this_round,
                launch_event = excluded.launch_event,
                retired_this_round = excluded.retired_this_round,
                retirement_liquidation_revenue = excluded.retirement_liquidation_revenue,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            payloads,
        )


def load_forecast_accuracy_results(
    round_number: int | None = None,
    team_name: str | None = None,
) -> list[ForecastAccuracyResult]:
    """Load per-product forecast-accuracy results."""
    ensure_app_storage()
    query = """
        SELECT
            round_number,
            team_name,
            product_id,
            slot_name,
            product_name,
            forecast_units,
            actual_demand_units,
            actual_sales_units,
            forecast_error_units,
            absolute_error_units,
            forecast_bias_pct,
            mape_or_wape_value
        FROM forecast_accuracy_results
        WHERE 1 = 1
    """
    parameters: list[Any] = []

    if round_number is not None:
        query += " AND round_number = ?"
        parameters.append(round_number)

    if team_name:
        query += " AND LOWER(team_name) = LOWER(?)"
        parameters.append(team_name)

    query += " ORDER BY round_number DESC, team_name, slot_name"

    with get_connection() as connection:
        rows = connection.execute(query, tuple(parameters)).fetchall()

    return [ForecastAccuracyResult.from_dict(dict(row)) for row in rows]


def save_forecast_accuracy_results(
    results: list[ForecastAccuracyResult],
) -> None:
    """Persist per-product forecast-accuracy results."""
    if not results:
        return

    ensure_app_storage()
    payloads = [result.to_dict() for result in results]
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO forecast_accuracy_results (
                round_number,
                team_name,
                product_id,
                slot_name,
                product_name,
                forecast_units,
                actual_demand_units,
                actual_sales_units,
                forecast_error_units,
                absolute_error_units,
                forecast_bias_pct,
                mape_or_wape_value,
                updated_at
            )
            VALUES (
                :round_number,
                :team_name,
                :product_id,
                :slot_name,
                :product_name,
                :forecast_units,
                :actual_demand_units,
                :actual_sales_units,
                :forecast_error_units,
                :absolute_error_units,
                :forecast_bias_pct,
                :mape_or_wape_value,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(round_number, team_name, slot_name) DO UPDATE SET
                product_id = excluded.product_id,
                product_name = excluded.product_name,
                forecast_units = excluded.forecast_units,
                actual_demand_units = excluded.actual_demand_units,
                actual_sales_units = excluded.actual_sales_units,
                forecast_error_units = excluded.forecast_error_units,
                absolute_error_units = excluded.absolute_error_units,
                forecast_bias_pct = excluded.forecast_bias_pct,
                mape_or_wape_value = excluded.mape_or_wape_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            payloads,
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
            raw_material_inventory,
            backlog_units,
            capacity_units,
            reputation_score,
            completed_rounds_json,
            last_decision_json,
            open_material_orders_json,
            cumulative_profit,
            short_term_debt_balance,
            interest_expense_last_round,
            liquidity_warning_flag,
            working_capital_stress_score
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
    if not states:
        return

    ensure_app_storage()
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO team_states (
                team_name,
                archetype,
                cash_balance,
                inventory_units,
                raw_material_inventory,
                backlog_units,
                capacity_units,
                reputation_score,
                completed_rounds_json,
                last_decision_json,
                open_material_orders_json,
                cumulative_profit,
                short_term_debt_balance,
                interest_expense_last_round,
                liquidity_warning_flag,
                working_capital_stress_score,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(team_name) DO UPDATE SET
                archetype = excluded.archetype,
                cash_balance = excluded.cash_balance,
                inventory_units = excluded.inventory_units,
                raw_material_inventory = excluded.raw_material_inventory,
                backlog_units = excluded.backlog_units,
                capacity_units = excluded.capacity_units,
                reputation_score = excluded.reputation_score,
                completed_rounds_json = excluded.completed_rounds_json,
                last_decision_json = excluded.last_decision_json,
                open_material_orders_json = excluded.open_material_orders_json,
                cumulative_profit = excluded.cumulative_profit,
                short_term_debt_balance = excluded.short_term_debt_balance,
                interest_expense_last_round = excluded.interest_expense_last_round,
                liquidity_warning_flag = excluded.liquidity_warning_flag,
                working_capital_stress_score = excluded.working_capital_stress_score,
                updated_at = CURRENT_TIMESTAMP
            """,
            [
                (
                    state.team_name,
                    state.archetype,
                    state.cash_balance,
                    state.inventory_units,
                    state.raw_material_inventory,
                    state.backlog_units,
                    state.capacity_units,
                    state.reputation_score,
                    json.dumps(state.completed_rounds),
                    json.dumps(state.last_decision),
                    json.dumps(
                        [order.to_dict() for order in state.open_material_orders]
                    ),
                    state.cumulative_profit,
                    state.short_term_debt_balance,
                    state.interest_expense_last_round,
                    1 if state.liquidity_warning_flag else 0,
                    state.working_capital_stress_score,
                )
                for state in states
            ],
        )


def reset_runtime_data() -> None:
    """Clear decisions, results, and persistent runtime state."""
    ensure_app_storage()
    with get_connection() as connection:
        connection.execute("DELETE FROM classroom_rounds")
        connection.execute("DELETE FROM product_decisions")
        connection.execute("DELETE FROM product_forecasts")
        connection.execute("DELETE FROM product_development_projects")
        connection.execute("DELETE FROM forecast_accuracy_results")
        connection.execute("DELETE FROM product_round_results")
        connection.execute("DELETE FROM team_decisions")
        connection.execute("DELETE FROM round_results")
        connection.execute("DELETE FROM team_states")
        connection.execute("DELETE FROM product_lines")


def factory_reset_game_data() -> MarketReport:
    """Reset all gameplay data to a fresh Round 1 state while preserving accounts."""
    ensure_app_storage()
    with get_connection() as connection:
        connection.execute("DELETE FROM classroom_rounds")
        connection.execute("DELETE FROM market_reports")
        connection.execute("DELETE FROM product_decisions")
        connection.execute("DELETE FROM product_forecasts")
        connection.execute("DELETE FROM product_development_projects")
        connection.execute("DELETE FROM forecast_accuracy_results")
        connection.execute("DELETE FROM product_round_results")
        connection.execute("DELETE FROM team_decisions")
        connection.execute("DELETE FROM round_results")
        connection.execute("DELETE FROM team_states")
        connection.execute("DELETE FROM product_lines")

    save_market_report(DEFAULT_MARKET_REPORT)
    set_round_submissions_open(
        DEFAULT_MARKET_REPORT.round_number,
        True,
        "Factory reset created a fresh Round 1.",
    )
    return DEFAULT_MARKET_REPORT


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


def load_team_names(include_inactive_users: bool = True) -> list[str]:
    """Return every team name known through accounts or simulator records."""
    ensure_app_storage()
    active_clause = "" if include_inactive_users else "AND is_active = 1"
    queries = [
        f"""
        SELECT team_name
        FROM users
        WHERE role = 'team_leader'
          AND team_name IS NOT NULL
          AND TRIM(team_name) <> ''
          {active_clause}
        """,
        "SELECT team_name FROM team_states",
        "SELECT team_name FROM product_lines",
        "SELECT team_name FROM team_decisions",
        "SELECT team_name FROM product_decisions",
        "SELECT team_name FROM product_forecasts",
        "SELECT team_name FROM product_development_projects",
        "SELECT team_name FROM round_results",
        "SELECT team_name FROM product_round_results",
        "SELECT team_name FROM forecast_accuracy_results",
    ]

    team_names: set[str] = set()
    with get_connection() as connection:
        for query in queries:
            rows = connection.execute(query).fetchall()
            for row in rows:
                team_name = str(row["team_name"] or "").strip()
                if team_name:
                    team_names.add(team_name)

    return sorted(team_names, key=str.lower)


def remove_team_data(
    team_name: str,
    *,
    deactivate_team_leaders: bool = True,
    delete_team_leader_accounts: bool = False,
) -> dict[str, int]:
    """Remove one team's simulator records and optionally deactivate its accounts."""
    ensure_app_storage()
    normalized_team_name = team_name.strip()
    if not normalized_team_name:
        raise ValueError("Team name is required.")

    team_tables = [
        "product_decisions",
        "product_forecasts",
        "product_development_projects",
        "forecast_accuracy_results",
        "product_round_results",
        "team_decisions",
        "round_results",
        "team_states",
        "product_lines",
    ]
    deleted_counts: dict[str, int] = {}

    with get_connection() as connection:
        for table_name in team_tables:
            cursor = connection.execute(
                f"DELETE FROM {table_name} WHERE LOWER(team_name) = LOWER(?)",
                (normalized_team_name,),
            )
            deleted_counts[table_name] = max(cursor.rowcount, 0)

        if delete_team_leader_accounts:
            cursor = connection.execute(
                """
                DELETE FROM users
                WHERE role = 'team_leader'
                  AND LOWER(team_name) = LOWER(?)
                """,
                (normalized_team_name,),
            )
            deleted_counts["deleted_team_leader_accounts"] = max(cursor.rowcount, 0)
            deleted_counts["deactivated_team_leader_accounts"] = 0
        elif deactivate_team_leaders:
            cursor = connection.execute(
                """
                UPDATE users
                SET is_active = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE role = 'team_leader'
                  AND LOWER(team_name) = LOWER(?)
                  AND is_active = 1
                """,
                (normalized_team_name,),
            )
            deleted_counts["deactivated_team_leader_accounts"] = max(cursor.rowcount, 0)
            deleted_counts["deleted_team_leader_accounts"] = 0
        else:
            deleted_counts["deactivated_team_leader_accounts"] = 0
            deleted_counts["deleted_team_leader_accounts"] = 0

    return deleted_counts


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
    payload["open_material_orders"] = [
        OpenMaterialOrder.from_dict(item)
        for item in json.loads(payload.pop("open_material_orders_json", "[]"))
    ]
    return PersistentTeamState.from_dict(payload)
