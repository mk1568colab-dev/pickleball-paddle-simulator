"""Page for capturing Stage B firm, product, and development-project decisions."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from engine.config import STARTING_RAW_MATERIAL_COVERAGE
from engine.simulator import estimate_development_project, preview_team_decision
from models.schemas import (
    MAX_TECH_GENERATION,
    MIN_TECH_GENERATION,
    PRODUCT_SLOT_NAMES,
    PROJECT_SLOT_NAMES,
    TARGET_SEGMENTS,
    ProductDecision,
    ProductDevelopmentProject,
    ProductForecast,
    ProductLine,
    TeamArchetype,
    TeamDecision,
    build_project_id,
)
from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import (
    ensure_development_projects_for_team,
    ensure_product_lines_for_team,
    load_market_report,
    load_product_decisions,
    load_product_development_projects,
    load_product_lines,
    load_round_status,
    load_team_archetypes,
    load_team_decision,
    load_team_decisions,
    load_team_states,
    load_users,
    save_product_decisions,
    save_product_forecasts,
    save_product_development_projects,
    save_product_lines,
    save_team_decision,
)


SESSION_CONTEXT_KEY = "stage_b_decision_editor_context"
ARCHETYPE_KEY = "stage_b_archetype_name"

FIRM_WIDGET_KEYS = {
    "overtime_capacity_units": "stage_b_overtime_capacity_units",
    "capacity_expansion_units": "stage_b_capacity_expansion_units",
    "raw_material_order_qty": "stage_b_raw_material_order_qty",
    "supplier_mix_offshore_pct": "stage_b_supplier_mix_offshore_pct",
    "supplier_mix_balanced_pct": "stage_b_supplier_mix_balanced_pct",
    "supplier_mix_premium_pct": "stage_b_supplier_mix_premium_pct",
    "expedited_order_share_pct": "stage_b_expedited_order_share_pct",
    "max_backorder_units": "stage_b_max_backorder_units",
    "planned_borrowing_amount": "stage_b_planned_borrowing_amount",
}

PRODUCT_FIELDS = (
    "product_name",
    "is_active",
    "target_segment",
    "selling_price_per_unit",
    "forecast_units",
    "planned_production_units",
    "qc_budget_per_unit",
    "target_finished_goods_inventory",
    "retire_flag",
)

PROJECT_FIELDS = (
    "project_name",
    "target_segment",
    "target_tech_generation",
    "intended_slot_name",
    "planned_launch_round",
    "investment_this_round",
    "testing_intensity",
    "launch_now",
    "cancel_now",
    "cannibalization_group",
    "projected_base_defect_modifier",
    "projected_demand_fit_modifier",
)

PROJECT_FIXED_FIELDS = (
    "project_name",
    "target_segment",
    "target_tech_generation",
    "intended_slot_name",
    "planned_launch_round",
    "cannibalization_group",
    "projected_base_defect_modifier",
    "projected_demand_fit_modifier",
)


def _product_widget_key(slot_name: str, field_name: str) -> str:
    """Return the widget key for a product slot field."""
    return f"stage_b_product_{slot_name}_{field_name}"


def _project_widget_key(project_slot_name: str, field_name: str) -> str:
    """Return the widget key for a development-project field."""
    return f"stage_b_project_{project_slot_name}_{field_name}"


def _project_fixed_settings_locked(project: ProductDevelopmentProject) -> bool:
    """Return whether project-charter fields should be locked in the UI."""
    return (
        project.is_pipeline_active()
        and (
            project.cumulative_investment > 0
            or project.investment_this_round > 0
            or project.testing_intensity > 0
            or project.launch_readiness_score > 0
            or project.status in {"development", "pilot", "launch_ready"}
        )
    )


def _sync_locked_project_fields(project: ProductDevelopmentProject) -> None:
    """Keep disabled project-charter widgets aligned with persisted values."""
    for field_name in PROJECT_FIXED_FIELDS:
        st.session_state[_project_widget_key(project.project_slot_name, field_name)] = getattr(
            project,
            field_name,
        )


def _build_team_options(current_round: int) -> list[str]:
    """Collect known team names for admin selection."""
    team_names = {
        user.team_name
        for user in load_users(role="team_leader")
        if user.team_name
    }
    team_names.update(
        decision.team_name
        for decision in load_team_decisions(round_number=current_round)
        if decision.team_name
    )
    team_names.update(
        state.team_name
        for state in load_team_states()
        if state.team_name
    )
    team_names.update(
        line.team_name
        for line in load_product_lines()
        if line.team_name
    )
    return sorted(team_names)


def _suggested_firm_decision(team_name: str, archetype: TeamArchetype) -> TeamDecision:
    """Build the firm-level suggested decision from an archetype."""
    return TeamDecision(
        team_name=team_name,
        archetype=archetype.name,
        overtime_capacity_units=archetype.suggested_overtime_capacity_units,
        capacity_expansion_units=archetype.suggested_capacity_expansion_units,
        raw_material_order_qty=archetype.suggested_raw_material_order_qty,
        supplier_mix_offshore_pct=archetype.suggested_supplier_mix_offshore_pct,
        supplier_mix_balanced_pct=archetype.suggested_supplier_mix_balanced_pct,
        supplier_mix_premium_pct=archetype.suggested_supplier_mix_premium_pct,
        expedited_order_share_pct=archetype.suggested_expedited_order_share_pct,
        max_backorder_units=archetype.suggested_max_backorder_units,
        planned_borrowing_amount=0.0,
    )


def _suggested_product_decisions(
    team_name: str,
    archetype: TeamArchetype,
    product_lines: list[ProductLine],
) -> list[ProductDecision]:
    """Build suggested product decisions for the three portfolio slots."""
    line_by_slot = {line.slot_name: line for line in product_lines}
    template_by_slot = {
        template.slot_name: template
        for template in archetype.suggested_product_templates
    }
    product_decisions: list[ProductDecision] = []

    for slot_name in PRODUCT_SLOT_NAMES:
        product_line = line_by_slot[slot_name]
        template = template_by_slot.get(slot_name)
        is_retired_slot = product_line.retirement_flag and not product_line.is_active
        product_decisions.append(
            ProductDecision(
                product_id=product_line.product_id,
                team_name=team_name,
                slot_name=slot_name,
                product_name=product_line.product_name,
                is_active=False if is_retired_slot else product_line.is_active,
                target_segment=product_line.target_segment,
                selling_price_per_unit=(
                    0.0
                    if is_retired_slot
                    else template.suggested_selling_price_per_unit if template else 130.0
                ),
                forecast_units=(
                    0
                    if is_retired_slot
                    else template.suggested_planned_production_units if template else 0
                ),
                planned_production_units=(
                    0
                    if is_retired_slot
                    else template.suggested_planned_production_units if template else 0
                ),
                qc_budget_per_unit=(
                    0.0
                    if is_retired_slot
                    else template.suggested_qc_budget_per_unit if template else 0.0
                ),
                target_finished_goods_inventory=(
                    0
                    if is_retired_slot
                    else template.suggested_target_finished_goods_inventory
                    if template
                    else 0
                ),
                retire_flag=False,
            )
        )

    return product_decisions


def _seed_projects(
    team_name: str,
    market_round: int,
) -> list[ProductDevelopmentProject]:
    """Build blank Stage B project slots for the decision editor."""
    return [
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
            planned_launch_round=market_round + 1,
            earliest_launch_round=market_round + 1,
            status="concept",
            cannibalization_group="",
            projected_base_defect_modifier=0.0,
            projected_demand_fit_modifier=1.0,
            created_round=market_round,
        )
        for project_slot_name in PROJECT_SLOT_NAMES
    ]


def _load_decisions_into_session(
    firm_decision: TeamDecision,
    product_decisions: list[ProductDecision],
    projects: list[ProductDevelopmentProject],
) -> None:
    """Push non-archetype decision objects into Streamlit widget state."""
    for field_name, widget_key in FIRM_WIDGET_KEYS.items():
        st.session_state[widget_key] = getattr(firm_decision, field_name)

    decision_by_slot = {decision.slot_name: decision for decision in product_decisions}
    for slot_name in PRODUCT_SLOT_NAMES:
        decision = decision_by_slot[slot_name]
        for field_name in PRODUCT_FIELDS:
            st.session_state[_product_widget_key(slot_name, field_name)] = getattr(
                decision,
                field_name,
            )

    project_by_slot = {project.project_slot_name: project for project in projects}
    for project_slot_name in PROJECT_SLOT_NAMES:
        project = project_by_slot[project_slot_name]
        for field_name in PROJECT_FIELDS:
            st.session_state[_project_widget_key(project_slot_name, field_name)] = getattr(
                project,
                field_name,
            )


def _current_firm_decision(team_name: str, archetype_name: str) -> TeamDecision:
    """Read the firm-level decision from the current widget state."""
    return TeamDecision(
        team_name=team_name.strip(),
        archetype=archetype_name,
        overtime_capacity_units=int(st.session_state.get(FIRM_WIDGET_KEYS["overtime_capacity_units"], 0)),
        capacity_expansion_units=int(st.session_state.get(FIRM_WIDGET_KEYS["capacity_expansion_units"], 0)),
        raw_material_order_qty=int(st.session_state.get(FIRM_WIDGET_KEYS["raw_material_order_qty"], 0)),
        supplier_mix_offshore_pct=float(st.session_state.get(FIRM_WIDGET_KEYS["supplier_mix_offshore_pct"], 0.0)),
        supplier_mix_balanced_pct=float(st.session_state.get(FIRM_WIDGET_KEYS["supplier_mix_balanced_pct"], 0.0)),
        supplier_mix_premium_pct=float(st.session_state.get(FIRM_WIDGET_KEYS["supplier_mix_premium_pct"], 0.0)),
        expedited_order_share_pct=float(st.session_state.get(FIRM_WIDGET_KEYS["expedited_order_share_pct"], 0.0)),
        max_backorder_units=int(st.session_state.get(FIRM_WIDGET_KEYS["max_backorder_units"], 0)),
        planned_borrowing_amount=float(st.session_state.get(FIRM_WIDGET_KEYS["planned_borrowing_amount"], 0.0)),
    )


def _current_product_decisions(
    team_name: str,
    product_lines: list[ProductLine],
) -> list[ProductDecision]:
    """Read all product-slot decisions from the current widget state."""
    line_by_slot = {line.slot_name: line for line in product_lines}
    decisions: list[ProductDecision] = []

    for slot_name in PRODUCT_SLOT_NAMES:
        product_line = line_by_slot[slot_name]
        is_retired_slot = product_line.retirement_flag and not product_line.is_active
        product_name = str(
            st.session_state.get(_product_widget_key(slot_name, "product_name"), "")
        ).strip() or product_line.product_name
        is_active = (
            False
            if is_retired_slot
            else bool(
                st.session_state.get(_product_widget_key(slot_name, "is_active"), False)
            )
        )
        decisions.append(
            ProductDecision(
                product_id=product_line.product_id,
                team_name=team_name.strip(),
                slot_name=slot_name,
                product_name=product_name,
                is_active=is_active,
                target_segment=str(
                    st.session_state.get(
                        _product_widget_key(slot_name, "target_segment"),
                        product_line.target_segment,
                    )
                ).lower(),
                selling_price_per_unit=float(
                    st.session_state.get(
                        _product_widget_key(slot_name, "selling_price_per_unit"),
                        0.0,
                    )
                ),
                forecast_units=(
                    int(
                        st.session_state.get(
                            _product_widget_key(slot_name, "forecast_units"),
                            0,
                        )
                    )
                    if is_active
                    else 0
                ),
                planned_production_units=(
                    int(
                        st.session_state.get(
                            _product_widget_key(slot_name, "planned_production_units"),
                            0,
                        )
                    )
                    if is_active
                    else 0
                ),
                qc_budget_per_unit=float(
                    st.session_state.get(
                        _product_widget_key(slot_name, "qc_budget_per_unit"),
                        0.0,
                    )
                ),
                target_finished_goods_inventory=int(
                    st.session_state.get(
                        _product_widget_key(slot_name, "target_finished_goods_inventory"),
                        0,
                    )
                ),
                retire_flag=bool(
                    st.session_state.get(_product_widget_key(slot_name, "retire_flag"), False)
                )
                if not is_retired_slot
                else False,
            )
        )

    return decisions


def _build_product_forecasts(
    round_number: int,
    product_decisions: list[ProductDecision],
) -> list[ProductForecast]:
    """Convert current product decisions into persisted forecast rows."""
    return [
        ProductForecast(
            round_number=round_number,
            team_name=decision.team_name,
            product_id=decision.product_id,
            slot_name=decision.slot_name,
            product_name=decision.product_name,
            forecast_units=decision.forecast_units if decision.is_active else 0,
        )
        for decision in product_decisions
    ]


def _current_projects(
    team_name: str,
    current_round: int,
    existing_projects: list[ProductDevelopmentProject],
) -> list[ProductDevelopmentProject]:
    """Read the editable development-project slots from widget state."""
    existing_by_slot = {project.project_slot_name: project for project in existing_projects}
    projects: list[ProductDevelopmentProject] = []

    for project_slot_name in PROJECT_SLOT_NAMES:
        existing_project = existing_by_slot[project_slot_name]
        fixed_settings_locked = _project_fixed_settings_locked(existing_project)
        if fixed_settings_locked:
            project_name = existing_project.project_name
            target_segment = existing_project.target_segment
            target_tech_generation = existing_project.target_tech_generation
            intended_slot_name = existing_project.intended_slot_name
            planned_launch_round = existing_project.planned_launch_round
            cannibalization_group = existing_project.cannibalization_group
            projected_base_defect_modifier = existing_project.projected_base_defect_modifier
            projected_demand_fit_modifier = existing_project.projected_demand_fit_modifier
        else:
            project_name = str(
                st.session_state.get(_project_widget_key(project_slot_name, "project_name"), "")
            ).strip()
            target_segment = str(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "target_segment"),
                    existing_project.target_segment,
                )
            ).lower()
            target_tech_generation = int(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "target_tech_generation"),
                    existing_project.target_tech_generation,
                )
            )
            intended_slot_name = str(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "intended_slot_name"),
                    existing_project.intended_slot_name,
                )
            ).upper()
            planned_launch_round = int(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "planned_launch_round"),
                    existing_project.planned_launch_round,
                )
            )
            cannibalization_group = str(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "cannibalization_group"),
                    existing_project.cannibalization_group,
                )
            ).strip()
            projected_base_defect_modifier = float(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "projected_base_defect_modifier"),
                    existing_project.projected_base_defect_modifier,
                )
            )
            projected_demand_fit_modifier = float(
                st.session_state.get(
                    _project_widget_key(project_slot_name, "projected_demand_fit_modifier"),
                    existing_project.projected_demand_fit_modifier,
                )
            )
        investment_this_round = float(
            st.session_state.get(
                _project_widget_key(project_slot_name, "investment_this_round"),
                0.0,
            )
        )
        testing_intensity = float(
            st.session_state.get(
                _project_widget_key(project_slot_name, "testing_intensity"),
                0.0,
            )
        )
        reset_pipeline = (
            existing_project.status in {"launched", "canceled"}
            and (
                project_name != existing_project.project_name
                or target_segment != existing_project.target_segment
                or target_tech_generation != existing_project.target_tech_generation
                or intended_slot_name != existing_project.intended_slot_name
                or planned_launch_round != existing_project.planned_launch_round
                or cannibalization_group != existing_project.cannibalization_group
                or projected_base_defect_modifier != existing_project.projected_base_defect_modifier
                or projected_demand_fit_modifier != existing_project.projected_demand_fit_modifier
                or investment_this_round > 0
                or testing_intensity > 0
            )
            and project_name
        )
        created_round = current_round if reset_pipeline else existing_project.created_round
        cumulative_investment = 0.0 if reset_pipeline else existing_project.cumulative_investment
        launch_readiness_score = 0.0 if reset_pipeline else existing_project.launch_readiness_score
        status = "concept" if reset_pipeline else existing_project.status
        launched_round = None if reset_pipeline else existing_project.launched_round
        canceled_round = None if reset_pipeline else existing_project.canceled_round

        projects.append(
            ProductDevelopmentProject(
                project_id=existing_project.project_id,
                team_name=team_name.strip(),
                project_slot_name=project_slot_name,
                project_name=project_name,
                target_segment=target_segment,
                target_tech_generation=target_tech_generation,
                intended_slot_name=intended_slot_name,
                required_investment=existing_project.required_investment,
                cumulative_investment=cumulative_investment,
                investment_this_round=investment_this_round,
                testing_intensity=testing_intensity,
                launch_readiness_score=launch_readiness_score,
                planned_launch_round=planned_launch_round,
                earliest_launch_round=existing_project.earliest_launch_round,
                status=status,
                cannibalization_group=cannibalization_group,
                projected_base_defect_modifier=projected_base_defect_modifier,
                projected_demand_fit_modifier=projected_demand_fit_modifier,
                created_round=created_round,
                launched_round=launched_round,
                canceled_round=canceled_round,
                launch_now=bool(
                    st.session_state.get(_project_widget_key(project_slot_name, "launch_now"), False)
                ),
                cancel_now=bool(
                    st.session_state.get(_project_widget_key(project_slot_name, "cancel_now"), False)
                ),
                replaced_product_name=existing_project.replaced_product_name,
            )
        )

    return projects


def _merge_product_lines(
    existing_product_lines: list[ProductLine],
    product_decisions: list[ProductDecision],
) -> list[ProductLine]:
    """Update persistent product-line metadata from the submitted portfolio."""
    decision_by_slot = {decision.slot_name: decision for decision in product_decisions}
    merged_lines: list[ProductLine] = []

    for product_line in sorted(existing_product_lines, key=lambda item: item.slot_name):
        decision = decision_by_slot[product_line.slot_name]
        merged_lines.append(
            ProductLine(
                product_id=product_line.product_id,
                team_name=product_line.team_name,
                product_name=decision.product_name,
                slot_name=product_line.slot_name,
                is_active=decision.is_active,
                target_segment=decision.target_segment,
                lifecycle_stage=product_line.lifecycle_stage,
                age_in_rounds=product_line.age_in_rounds,
                base_defect_rate_modifier=product_line.base_defect_rate_modifier,
                base_demand_fit_modifier=product_line.base_demand_fit_modifier,
                tech_generation=product_line.tech_generation,
                cannibalization_group=product_line.cannibalization_group,
                launch_round=product_line.launch_round,
                retirement_flag=product_line.retirement_flag,
                retired_round=product_line.retired_round,
                replacement_project_id=product_line.replacement_project_id,
                inventory_units=product_line.inventory_units,
                backlog_units=product_line.backlog_units,
            )
        )

    return merged_lines


def _render_state_snapshot(
    product_lines: list[ProductLine],
    existing_state,
    market_report,
    selected_archetype: TeamArchetype,
) -> None:
    """Render the team's current persistent operating and technology position."""
    beginning_inventory = sum(max(line.inventory_units, 0) for line in product_lines)
    beginning_backlog = sum(max(line.backlog_units, 0) for line in product_lines)
    is_first_round_state = not existing_state or not existing_state.completed_rounds
    installed_capacity = (
        existing_state.capacity_units
        if existing_state and existing_state.capacity_units > 0
        else selected_archetype.base_capacity
        if is_first_round_state
        else 0
    )
    reputation = (
        existing_state.reputation_score
        if existing_state and existing_state.reputation_score > 0
        else selected_archetype.base_reputation
        if is_first_round_state
        else 0.0
    )
    raw_material_inventory = (
        existing_state.raw_material_inventory
        if existing_state and existing_state.raw_material_inventory > 0
        else int(round(selected_archetype.base_capacity * STARTING_RAW_MATERIAL_COVERAGE))
        if is_first_round_state
        else 0
    )
    cash_balance = existing_state.cash_balance if existing_state else 0.0
    short_term_debt = existing_state.short_term_debt_balance if existing_state else 0.0
    interest_last_round = (
        existing_state.interest_expense_last_round if existing_state else 0.0
    )
    liquidity_flag = existing_state.liquidity_warning_flag if existing_state else False
    average_tech = (
        sum(line.tech_generation for line in product_lines if line.is_active)
        / max(sum(1 for line in product_lines if line.is_active), 1)
    )

    snapshot_cols = st.columns(8)
    snapshot_cols[0].metric("Installed Capacity", f"{installed_capacity:,}")
    snapshot_cols[1].metric("Beginning FG Inventory", f"{beginning_inventory:,}")
    snapshot_cols[2].metric("Beginning RM Inventory", f"{raw_material_inventory:,}")
    snapshot_cols[3].metric("Beginning Backlog", f"{beginning_backlog:,}")
    snapshot_cols[4].metric("Reputation", f"{reputation:.1f}")
    snapshot_cols[5].metric("Cash Balance", f"${cash_balance:,.0f}")
    snapshot_cols[6].metric("Short-Term Debt", f"${short_term_debt:,.0f}")
    snapshot_cols[7].metric(
        "Tech vs Market",
        f"{average_tech - market_report.current_market_generation:+.1f}",
    )
    st.caption(
        f"Last-round interest expense: ${interest_last_round:,.0f} | "
        f"Liquidity warning flag: {'On' if liquidity_flag else 'Off'}"
    )


def _render_preview(candidate_firm_decision: TeamDecision, preview) -> None:
    """Render the Stage C portfolio, forecast, and finance analytics preview."""
    total_planned = preview.total_planned_production_units
    total_forecast = preview.total_forecast_units
    planned_utilization = (
        (total_planned / preview.effective_capacity_units) * 100.0
        if preview.effective_capacity_units > 0
        else 0.0
    )
    raw_material_gap = preview.raw_material_units_available - total_planned

    row_one = st.columns(5)
    row_one[0].metric("Total Forecast Units", f"{total_forecast:,}")
    row_one[1].metric("Effective Firm Capacity", f"{preview.effective_capacity_units:,}")
    row_one[2].metric("Total Planned Production", f"{total_planned:,}")
    row_one[3].metric("Forecast-Production Gap", f"{preview.forecast_production_gap_units:+,}")
    row_one[4].metric("Planned Utilization %", f"{planned_utilization:.1f}%")

    row_two = st.columns(5)
    row_two[0].metric("Projected Feasible Output", f"{preview.projected_max_feasible_production:,}")
    row_two[1].metric("Beginning FG Inventory", f"{preview.beginning_finished_goods_inventory:,}")
    row_two[2].metric("Raw Material Available", f"{preview.raw_material_units_available:,}")
    row_two[3].metric("RM Sufficiency Gap", f"{raw_material_gap:+,}")
    row_two[4].metric(
        "Projected FG Ending Inventory",
        f"{preview.projected_ending_finished_goods_inventory_if_forecast_hits:,}",
    )

    row_three = st.columns(5)
    row_three[0].metric("Weighted Lead Time", f"{preview.weighted_lead_time:.2f} rounds")
    row_three[1].metric("Weighted Material Cost", f"${preview.weighted_material_unit_cost:,.2f}")
    row_three[2].metric("Projected Weighted Defect Rate", f"{preview.projected_weighted_defect_rate:.2%}")
    row_three[3].metric("Projected Margin / Unit", f"${preview.projected_weighted_margin_per_unit:,.2f}")
    row_three[4].metric("Projected Innovation Spend", f"${preview.projected_innovation_investment:,.0f}")

    row_four = st.columns(5)
    row_four[0].metric("Projected Working Capital", f"${preview.projected_working_capital_requirement:,.0f}")
    row_four[1].metric("Projected Cash Before Borrowing", f"${preview.projected_ending_cash_before_borrowing:,.0f}")
    row_four[2].metric("Likely Borrowing Need", f"${preview.projected_likely_borrowing_need:,.0f}")
    row_four[3].metric("Planned Borrowing", f"${candidate_firm_decision.planned_borrowing_amount:,.0f}")
    row_four[4].metric("Max Backorder Units", f"{candidate_firm_decision.max_backorder_units:,}")

    row_five = st.columns(5)
    row_five[0].metric("Pipeline Projects", f"{preview.pipeline_project_count}")
    row_five[1].metric("Launch-Ready Projects", f"{preview.launch_ready_project_count}")
    row_five[2].metric("Tech Position vs Market", f"{preview.tech_position_vs_market:+.2f}")
    row_five[3].metric("Products in Decline", f"{preview.decline_product_count}")
    row_five[4].metric("Likely Cannibalization", f"{preview.likely_cannibalization_exposure_units:,.1f}")

    st.caption(
        f"Weighted supplier mix: {preview.weighted_supplier_mix_text} | "
        f"Projected portfolio segment mix: {preview.segment_mix_summary}"
    )

    for warning_message in preview.warnings:
        st.warning(warning_message)

    product_preview_frame = pd.DataFrame(preview.product_rows)
    if not product_preview_frame.empty:
        st.markdown("#### Portfolio Scenario Preview")
        st.dataframe(product_preview_frame, use_container_width=True, hide_index=True)

    project_preview_frame = pd.DataFrame(preview.project_rows)
    if not project_preview_frame.empty:
        st.markdown("#### Development Pipeline Estimate Preview")
        st.caption(
            "Use this table before saving: it shows estimated project cost, remaining funding, "
            "readiness after this round's investment/testing, earliest launch timing, and launch risk."
        )
        preferred_columns = [
            "project_slot_name",
            "project_name",
            "status",
            "target_segment",
            "target_tech_generation",
            "intended_slot_name",
            "estimated_cost_range",
            "remaining_investment_after_this_round",
            "funding_progress_pct",
            "projected_readiness_after_this_round",
            "readiness_gap_points",
            "funding_gate_met",
            "readiness_gate_met",
            "timing_gate_met",
            "launch_gate_met",
            "testing_adequacy",
            "launch_risk",
            "launch_blockers",
            "minimum_development_rounds",
            "expected_launch_round",
            "planned_launch_round",
            "launch_now",
        ]
        visible_columns = [
            column for column in preferred_columns if column in project_preview_frame.columns
        ]
        st.dataframe(
            project_preview_frame[visible_columns],
            use_container_width=True,
            hide_index=True,
        )


def _render_project_launch_gate_guidance(
    candidate_projects: list[ProductDevelopmentProject],
    current_round: int,
) -> None:
    """Show a plain-language launch checklist for active development projects."""
    rows: list[dict[str, object]] = []
    for project in candidate_projects:
        if not project.is_defined() or project.status in {"launched", "canceled"}:
            continue
        estimate = estimate_development_project(
            project,
            include_current_round_investment=True,
            current_round=current_round,
        )
        rows.append(
            {
                "project": f"{project.project_slot_name}: {project.project_name}",
                "funding_gate": "Pass" if estimate.get("funding_gate_met") else "Not yet",
                "readiness_gate": "Pass" if estimate.get("readiness_gate_met") else "Not yet",
                "timing_gate": "Pass" if estimate.get("timing_gate_met") else "Not yet",
                "can_launch_now": "Yes" if estimate.get("launch_gate_met") else "No",
                "funding_progress_pct": estimate.get("funding_progress_pct", 0.0),
                "readiness_after_this_round": estimate.get(
                    "projected_readiness_after_this_round",
                    0.0,
                ),
                "readiness_needed": estimate.get("readiness_threshold", 0.0),
                "what_to_do_next": estimate.get("launch_blockers", ""),
            }
        )

    if not rows:
        return

    st.markdown("#### Launch Gate Checklist")
    st.caption(
        "A project can launch only when all three gates pass: funding, readiness, and timing. "
        "If the table says Can Launch Now = Yes, check Launch Now If Ready before saving."
    )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _validation_messages(
    candidate_firm_decision: TeamDecision,
    candidate_product_decisions: list[ProductDecision],
    candidate_projects: list[ProductDevelopmentProject],
    current_round: int,
) -> list[str]:
    """Build save-time validation messages."""
    messages: list[str] = []
    if not candidate_firm_decision.team_name:
        messages.append("Team name is required before you can save.")
    if not candidate_firm_decision.supplier_mix_valid():
        messages.append("Supplier mix percentages must sum to 100 before saving.")
    if not 0.0 <= candidate_firm_decision.expedited_order_share_pct <= 100.0:
        messages.append("Expedited order share must stay between 0 and 100.")
    if not any(item.is_active for item in candidate_product_decisions) and not any(
        item.launch_now for item in candidate_projects if item.is_defined()
    ):
        messages.append("Keep at least one active product or request at least one project launch.")

    for decision in candidate_product_decisions:
        if not decision.product_name.strip():
            messages.append(f"Product {decision.slot_name} must have a name.")
        if decision.target_segment not in TARGET_SEGMENTS:
            messages.append(f"Product {decision.slot_name} has an invalid target segment.")
        if decision.is_active and decision.selling_price_per_unit <= 0:
            messages.append(f"Product {decision.slot_name} needs a positive selling price.")
        if decision.is_active and decision.forecast_units <= 0:
            messages.append(f"Product {decision.slot_name} needs a demand forecast before saving.")

    launch_requests = 0
    for project in candidate_projects:
        project_controls_used = (
            project.investment_this_round > 0
            or project.testing_intensity > 0
            or project.launch_now
            or project.cancel_now
        )
        if not project.project_name.strip():
            if project_controls_used:
                messages.append(
                    f"Project {project.project_slot_name} needs a project name before investment, testing, launch, or cancellation controls can be used."
                )
            continue
        if project.target_segment not in TARGET_SEGMENTS:
            messages.append(f"Project {project.project_slot_name} has an invalid target segment.")
        if project.planned_launch_round < project.created_round:
            messages.append(
                f"Project {project.project_slot_name} cannot have a planned launch round earlier than the project creation round."
            )
        if not 0.0 <= project.testing_intensity <= 1.0:
            messages.append(f"Project {project.project_slot_name} testing intensity must stay between 0.0 and 1.0.")
        if project.target_tech_generation < MIN_TECH_GENERATION or project.target_tech_generation > MAX_TECH_GENERATION:
            messages.append(f"Project {project.project_slot_name} tech generation must stay between {MIN_TECH_GENERATION} and {MAX_TECH_GENERATION}.")
        if project.projected_demand_fit_modifier <= 0:
            messages.append(f"Project {project.project_slot_name} demand-fit modifier must be positive.")
        if project.launch_now:
            launch_requests += 1

    if launch_requests > 1:
        messages.append("Only one launch request per team is allowed per round.")

    return messages


def main() -> None:
    """Render the Stage B team decision editor."""
    ensure_app_storage()
    user = require_authenticated_user()

    st.title("Team Decisions")
    st.caption(
        "Set firm-level operations and finance, submit product-level forecasts, manage the active three-slot portfolio, and invest in up to two future development projects."
    )

    market_report = load_market_report()
    current_round = market_report.round_number
    round_status = load_round_status(current_round)
    team_states = load_team_states()
    state_lookup = {item.team_name.lower(): item for item in team_states}
    current_round_firm_decisions = load_team_decisions(round_number=current_round)
    current_round_product_decisions = load_product_decisions(round_number=current_round)
    current_round_projects = load_product_development_projects()
    archetypes = load_team_archetypes()
    archetype_lookup = {item.name: item for item in archetypes}
    archetype_names = list(archetype_lookup)

    st.caption(
        "The preview uses the current market report, your persistent portfolio state, saved round submissions, and your current forecast-vs-plan inputs."
    )
    if round_status.submissions_open:
        st.success(f"Round {current_round} submissions are open.")
    else:
        st.warning(
            f"Round {current_round} submissions are closed. Team leaders can review their plan, but cannot save changes unless the instructor reopens the round."
        )

    st.markdown("### 1. Team Identity")
    if user.role == "team_leader":
        if not user.team_name:
            st.error("Your account does not have a team assignment yet.")
            st.stop()
        team_name = user.team_name
        st.text_input("Team Name", value=team_name, disabled=True)
    else:
        team_options = _build_team_options(current_round)
        if team_options:
            team_name = st.selectbox("Team", options=team_options)
        else:
            team_name = st.text_input("Team Name", placeholder="Team Alpha")

    team_name_key = team_name.strip().lower()
    if not team_name_key:
        st.info("Select or enter a team to start editing the portfolio.")
        st.stop()

    existing_state = state_lookup.get(team_name_key)
    existing_firm_decision = load_team_decision(current_round, team_name)
    default_archetype_name = (
        existing_firm_decision.archetype
        if existing_firm_decision
        else (
            existing_state.archetype
            if existing_state and existing_state.archetype in archetype_lookup
            else archetype_names[0]
        )
    )

    product_lines = ensure_product_lines_for_team(team_name, default_archetype_name)
    saved_product_decisions = load_product_decisions(round_number=current_round, team_name=team_name)
    saved_projects = ensure_development_projects_for_team(team_name)

    current_context = f"{current_round}:{team_name_key}"
    if st.session_state.get(SESSION_CONTEXT_KEY) != current_context:
        seed_firm_decision = (
            existing_firm_decision
            if existing_firm_decision is not None
            else _suggested_firm_decision(team_name, archetype_lookup[default_archetype_name])
        )
        seed_product_decisions = (
            saved_product_decisions
            if saved_product_decisions
            else _suggested_product_decisions(team_name, archetype_lookup[default_archetype_name], product_lines)
        )
        seed_projects = saved_projects if saved_projects else _seed_projects(team_name, current_round)
        # This is safe here because the archetype widget has not been created
        # yet in this page run. Button callbacks below must not mutate it.
        st.session_state[ARCHETYPE_KEY] = seed_firm_decision.archetype
        _load_decisions_into_session(seed_firm_decision, seed_product_decisions, seed_projects)
        st.session_state[SESSION_CONTEXT_KEY] = current_context

    archetype_locked = (
        user.role == "team_leader"
        and (
            existing_firm_decision is not None
            or bool(existing_state and existing_state.completed_rounds)
        )
    )
    selected_archetype_name = st.selectbox(
        "Archetype",
        options=archetype_names,
        index=archetype_names.index(st.session_state.get(ARCHETYPE_KEY, default_archetype_name)),
        key=ARCHETYPE_KEY,
        disabled=archetype_locked,
    )
    selected_archetype = archetype_lookup[selected_archetype_name]

    identity_actions = st.columns(2)
    if identity_actions[0].button("Apply Archetype Suggestions"):
        _load_decisions_into_session(
            _suggested_firm_decision(team_name, selected_archetype),
            _suggested_product_decisions(team_name, selected_archetype, product_lines),
            saved_projects,
        )
        st.rerun()
    if saved_product_decisions and existing_firm_decision and identity_actions[1].button("Load Saved Round Submission"):
        _load_decisions_into_session(
            existing_firm_decision,
            saved_product_decisions,
            saved_projects,
        )
        st.rerun()

    st.markdown("### 2. Current Team State")
    _render_state_snapshot(product_lines, existing_state, market_report, selected_archetype)
    st.caption(
        f"Market generation is currently Gen {market_report.current_market_generation}. "
        f"Premium tech adoption is {market_report.premium_tech_adoption:.0%} and mid-market tech adoption is {market_report.mid_market_tech_adoption:.0%}."
    )

    st.markdown("### 3. Firm-Level Operations and Finance")
    firm_row_one = st.columns(3)
    firm_row_one[0].number_input("Overtime Capacity Units", min_value=0, step=10, key=FIRM_WIDGET_KEYS["overtime_capacity_units"])
    firm_row_one[1].number_input("Capacity Expansion Units", min_value=0, step=10, key=FIRM_WIDGET_KEYS["capacity_expansion_units"])
    firm_row_one[2].number_input("Max Backorder Units", min_value=0, step=10, key=FIRM_WIDGET_KEYS["max_backorder_units"])

    firm_row_two = st.columns(3)
    firm_row_two[0].number_input("Raw Material Order Quantity", min_value=0, step=10, key=FIRM_WIDGET_KEYS["raw_material_order_qty"])
    firm_row_two[1].slider("Expedited Order Share %", min_value=0.0, max_value=100.0, step=1.0, key=FIRM_WIDGET_KEYS["expedited_order_share_pct"])
    firm_row_two[2].number_input("Planned Borrowing Amount", min_value=0.0, step=500.0, key=FIRM_WIDGET_KEYS["planned_borrowing_amount"])

    st.caption("Supplier mix must sum to 100% across the whole firm.")
    supplier_cols = st.columns(3)
    supplier_cols[0].number_input("Offshore Mix %", min_value=0.0, max_value=100.0, step=1.0, key=FIRM_WIDGET_KEYS["supplier_mix_offshore_pct"])
    supplier_cols[1].number_input("Balanced Mix %", min_value=0.0, max_value=100.0, step=1.0, key=FIRM_WIDGET_KEYS["supplier_mix_balanced_pct"])
    supplier_cols[2].number_input("Premium Mix %", min_value=0.0, max_value=100.0, step=1.0, key=FIRM_WIDGET_KEYS["supplier_mix_premium_pct"])

    st.markdown("### 4. Active Product Portfolio and Forecasts")
    line_by_slot = {line.slot_name: line for line in product_lines}
    for slot_name in PRODUCT_SLOT_NAMES:
        product_line = line_by_slot[slot_name]
        is_retired_slot = product_line.retirement_flag and not product_line.is_active
        with st.container(border=True):
            heading_suffix = " - Retired / Empty Slot" if is_retired_slot else ""
            st.markdown(f"#### Product {slot_name}{heading_suffix}")
            if is_retired_slot:
                st.info(
                    f"This product was retired after round {product_line.retired_round}. "
                    "It no longer receives demand, production, backlog, or inventory. "
                    "Launch a development project into this slot to replace it."
                )
            meta_cols = st.columns(5)
            meta_cols[0].metric("Lifecycle", product_line.lifecycle_stage.title())
            meta_cols[1].metric("Age (Rounds)", f"{product_line.age_in_rounds}")
            meta_cols[2].metric("Tech Gen", f"Gen {product_line.tech_generation}")
            meta_cols[3].metric("FG Inventory", f"{product_line.inventory_units:,}")
            meta_cols[4].metric("Backlog", f"{product_line.backlog_units:,}")

            top_row = st.columns([2, 1, 1, 1])
            top_row[0].text_input(
                "Product Name",
                key=_product_widget_key(slot_name, "product_name"),
                disabled=is_retired_slot,
            )
            active_value = bool(st.session_state.get(_product_widget_key(slot_name, "is_active"), product_line.is_active))
            top_row[1].checkbox(
                "Active",
                key=_product_widget_key(slot_name, "is_active"),
                value=False if is_retired_slot else active_value,
                disabled=is_retired_slot,
                help=(
                    "Retired slots stay inactive until a development project launches into this slot."
                    if is_retired_slot
                    else None
                ),
            )
            current_segment = str(st.session_state.get(_product_widget_key(slot_name, "target_segment"), product_line.target_segment))
            top_row[2].selectbox(
                "Target Segment",
                options=list(TARGET_SEGMENTS),
                index=list(TARGET_SEGMENTS).index(current_segment),
                key=_product_widget_key(slot_name, "target_segment"),
                disabled=is_retired_slot,
            )
            top_row[3].checkbox(
                "Retire After Round",
                key=_product_widget_key(slot_name, "retire_flag"),
                disabled=is_retired_slot,
                help=(
                    "This slot has already been retired."
                    if is_retired_slot
                    else "If checked, the product sells through this round, then any remaining inventory is liquidated and the slot becomes inactive."
                ),
            )

            numeric_row = st.columns(5)
            numeric_row[0].number_input("Selling Price / Unit", min_value=0.0, step=1.0, key=_product_widget_key(slot_name, "selling_price_per_unit"), disabled=is_retired_slot)
            numeric_row[1].number_input("Forecast Units", min_value=0, step=10, key=_product_widget_key(slot_name, "forecast_units"), disabled=is_retired_slot)
            numeric_row[2].number_input("Planned Production Units", min_value=0, step=10, key=_product_widget_key(slot_name, "planned_production_units"), disabled=is_retired_slot)
            numeric_row[3].number_input("QC Budget / Unit", min_value=0.0, step=0.25, key=_product_widget_key(slot_name, "qc_budget_per_unit"), disabled=is_retired_slot)
            numeric_row[4].number_input("Target FG Inventory", min_value=0, step=5, key=_product_widget_key(slot_name, "target_finished_goods_inventory"), disabled=is_retired_slot)

    st.markdown("### 5. Development Pipeline")
    st.caption(
        "Use up to two project slots to invest ahead of launch. Project charter settings become fixed once work starts; investment and testing remain controllable each round."
    )
    st.info(
        "How to think about NPD: choose the product concept once, then manage the project. "
        "More investment improves funding progress, higher testing intensity improves launch readiness, "
        "and newer technology generations usually require more money and development time. "
        "The planned launch round is a target date; if a project is late, it can still launch later once funding, readiness, and timing gates pass. "
        "See the Model Formula Guide page for the exact readiness and cost-estimate formulas."
    )
    existing_projects = load_product_development_projects(team_name=team_name)
    existing_project_by_slot = {project.project_slot_name: project for project in existing_projects}
    for project_slot_name in PROJECT_SLOT_NAMES:
        project = existing_project_by_slot[project_slot_name]
        fixed_settings_locked = _project_fixed_settings_locked(project)
        if fixed_settings_locked:
            _sync_locked_project_fields(project)
        with st.container(border=True):
            st.markdown(f"#### Project {project_slot_name}")
            project_meta = st.columns(5)
            project_meta[0].metric("Status", project.status.replace("_", " ").title())
            project_meta[1].metric("Cumulative Investment", f"${project.cumulative_investment:,.0f}")
            project_meta[2].metric("Saved Readiness", f"{project.launch_readiness_score:.1f}%")
            project_meta[3].metric("Earliest Launch", f"Round {project.earliest_launch_round}")
            project_meta[4].metric("Last Launch", f"{project.launched_round or '-'}")
            st.caption(
                "Top metrics show the saved project state entering this round. "
                "Your new investment/testing choices are reflected in the Launch Gate Checklist below."
            )

            st.caption(
                "Fixed project settings are locked after investment/testing begins. "
                "Round decisions remain adjustable so teams can speed up or stabilize the project."
                if fixed_settings_locked
                else "Set the fixed project charter before starting investment/testing."
            )
            st.caption(
                "Fixed charter: name, segment, tech generation, target slot, planned launch round, "
                "cannibalization group, defect goal, and demand-fit goal. "
                "Round controls: investment this round, testing intensity, launch now if ready, or cancel."
            )
            project_top = st.columns([2, 1, 1, 1])
            project_top[0].text_input(
                "Project Name",
                key=_project_widget_key(project_slot_name, "project_name"),
                disabled=fixed_settings_locked,
            )
            current_segment = str(st.session_state.get(_project_widget_key(project_slot_name, "target_segment"), project.target_segment))
            project_top[1].selectbox(
                "Target Segment",
                options=list(TARGET_SEGMENTS),
                index=list(TARGET_SEGMENTS).index(current_segment),
                key=_project_widget_key(project_slot_name, "target_segment"),
                disabled=fixed_settings_locked,
            )
            project_top[2].number_input(
                "Target Tech Generation",
                min_value=MIN_TECH_GENERATION,
                max_value=MAX_TECH_GENERATION,
                step=1,
                key=_project_widget_key(project_slot_name, "target_tech_generation"),
                disabled=fixed_settings_locked,
            )
            current_slot = str(st.session_state.get(_project_widget_key(project_slot_name, "intended_slot_name"), project.intended_slot_name))
            project_top[3].selectbox(
                "Intended Product Slot",
                options=list(PRODUCT_SLOT_NAMES),
                index=list(PRODUCT_SLOT_NAMES).index(current_slot),
                key=_project_widget_key(project_slot_name, "intended_slot_name"),
                disabled=fixed_settings_locked,
            )

            project_mid = st.columns(4)
            project_mid[0].number_input(
                "Planned Launch Round",
                min_value=min(current_round, int(project.planned_launch_round)),
                step=1,
                key=_project_widget_key(project_slot_name, "planned_launch_round"),
                disabled=fixed_settings_locked,
            )
            project_mid[1].number_input("Investment This Round", min_value=0.0, step=250.0, key=_project_widget_key(project_slot_name, "investment_this_round"))
            project_mid[2].slider("Testing Intensity", min_value=0.0, max_value=1.0, step=0.05, key=_project_widget_key(project_slot_name, "testing_intensity"))
            project_mid[3].text_input(
                "Cannibalization Group",
                key=_project_widget_key(project_slot_name, "cannibalization_group"),
                disabled=fixed_settings_locked,
            )

            project_bottom = st.columns(4)
            project_bottom[0].number_input(
                "Projected Defect Modifier",
                step=0.002,
                key=_project_widget_key(project_slot_name, "projected_base_defect_modifier"),
                disabled=fixed_settings_locked,
            )
            project_bottom[1].number_input(
                "Projected Demand-Fit Modifier",
                min_value=0.1,
                step=0.05,
                key=_project_widget_key(project_slot_name, "projected_demand_fit_modifier"),
                disabled=fixed_settings_locked,
            )
            project_bottom[2].checkbox("Launch Now If Ready", key=_project_widget_key(project_slot_name, "launch_now"))
            project_bottom[3].checkbox("Cancel Project", key=_project_widget_key(project_slot_name, "cancel_now"))

    candidate_firm_decision = _current_firm_decision(team_name, selected_archetype_name)
    candidate_product_decisions = _current_product_decisions(team_name, product_lines)
    candidate_projects = _current_projects(team_name, current_round, saved_projects)
    _render_project_launch_gate_guidance(candidate_projects, current_round)
    preview = preview_team_decision(
        market_report=market_report,
        candidate_team_decision=candidate_firm_decision,
        candidate_product_decisions=candidate_product_decisions,
        candidate_projects=candidate_projects,
        product_lines=load_product_lines(),
        current_round_team_decisions=current_round_firm_decisions,
        current_round_product_decisions=current_round_product_decisions,
        current_round_projects=current_round_projects,
        existing_states=team_states,
    )

    st.markdown("### 6. Planning Analytics Preview")
    _render_preview(candidate_firm_decision, preview)

    save_col, note_col = st.columns([1, 2])
    save_disabled = user.role == "team_leader" and not round_status.submissions_open
    if save_col.button(
        "Save Portfolio and Pipeline Decision",
        type="primary",
        disabled=save_disabled,
    ):
        if user.role == "team_leader" and not round_status.submissions_open:
            st.error("Submissions are closed for this round.")
            st.stop()
        errors = _validation_messages(
            candidate_firm_decision,
            candidate_product_decisions,
            candidate_projects,
            current_round,
        )
        if errors:
            for error_message in errors:
                st.error(error_message)
        else:
            save_team_decision(
                decision=candidate_firm_decision,
                round_number=current_round,
                submitted_by_user_id=user.user_id,
            )
            save_product_decisions(product_decisions=candidate_product_decisions, round_number=current_round)
            save_product_forecasts(_build_product_forecasts(current_round, candidate_product_decisions))
            save_product_development_projects(candidate_projects)
            save_product_lines(_merge_product_lines(product_lines, candidate_product_decisions))
            st.success(
                f"Saved the Stage C portfolio, forecast, and pipeline submission for `{candidate_firm_decision.team_name}` in round `{current_round}`."
            )

    note_col.caption(
        "Firm-level decisions remain shared across the business, while product-slot forecasts, portfolio decisions, and development projects let teams balance S&OP discipline, cash pressure, and future launches."
    )


main()
