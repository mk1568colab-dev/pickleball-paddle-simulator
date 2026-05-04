"""Stage C portfolio, lifecycle, forecasting, and finance round engine."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from engine.config import (
    ARCHETYPE_FIT_WEIGHT,
    BACKLOG_PENALTY_PER_UNIT,
    BASE_CANNIBALIZATION_RATE,
    BASE_CONVERSION_COST_SHARE,
    BASE_MATERIAL_COST_SHARE,
    CAPACITY_EXPANSION_CAPEX_PER_UNIT,
    DECLINE_PRICE_PRESSURE_PENALTY,
    DIFFERENT_SEGMENT_CANNIBALIZATION_FACTOR,
    EXPEDITED_LEAD_TIME_REDUCTION,
    EXPEDITED_ORDER_COST_UPLIFT,
    FORECAST_EXCESS_PRODUCTION_RATIO,
    FORECAST_LOW_COVERAGE_RATIO,
    FORECAST_MISMATCH_WARNING_RATIO,
    HOLDING_COST_PER_UNIT,
    LAUNCH_CANNIBALIZATION_BOOST,
    LAUNCH_DEFECT_PENALTY,
    LAUNCH_NOVELTY_BONUS,
    LAUNCH_READINESS_THRESHOLD,
    LIQUIDITY_LOW_CASH_THRESHOLD,
    LIQUIDITY_STRESS_REPUTATION_PENALTY,
    LIFECYCLE_AGE_THRESHOLDS,
    LIFECYCLE_DEMAND_MULTIPLIERS,
    LIFECYCLE_DEFECT_MODIFIERS,
    LIFECYCLE_GAP_CANNIBALIZATION_FACTOR,
    LIFECYCLE_PRICE_TOLERANCE_MULTIPLIERS,
    MAX_CANNIBALIZATION_TRANSFER_SHARE,
    MAX_LAUNCHES_PER_ROUND,
    MIN_ATTRACTIVENESS,
    NPD_MIN_DEVELOPMENT_ROUNDS_BY_TECH_GENERATION,
    NPD_EXPEDITE_EXTRA_PROGRESS_PER_ROUND,
    NPD_EXPEDITE_PROGRESS_THRESHOLD,
    NPD_EXPEDITE_TESTING_THRESHOLD,
    NPD_DEMAND_FIT_AMBITION_COST_RATE,
    NPD_DEFECT_IMPROVEMENT_COST_RATE,
    NPD_ESTIMATE_HIGH_MULTIPLIER_BY_TECH_GENERATION,
    NPD_ESTIMATE_LOW_MULTIPLIER_BY_TECH_GENERATION,
    NPD_MAX_EXPEDITE_ROUND_REDUCTION_BY_TECH_GENERATION,
    NPD_REQUIRED_INVESTMENT_BASE,
    NPD_SEGMENT_COST_MULTIPLIERS,
    NPD_TECH_GENERATION_COST_MULTIPLIERS,
    NPD_TESTING_ADEQUACY_GOOD_THRESHOLD,
    NPD_TESTING_ADEQUACY_LOW_THRESHOLD,
    OVERTIME_COST_MULTIPLIER,
    OVERTIME_DEFECT_PENALTY,
    PERIODIC_INTEREST_RATE,
    PRICE_ATTRACTIVENESS_WEIGHT,
    PRODUCT_DEMAND_FIT_WEIGHT,
    PRODUCT_SEGMENT_ALIGNMENT,
    PRODUCT_SEGMENT_ALIGNMENT_WEIGHT,
    PROJECT_SLOT_NAMES,
    QC_EFFECTIVENESS_RATE,
    QC_COST_REALIZATION_FACTOR,
    QC_MAX_DEFECT_REDUCTION,
    QUALITY_ATTRACTIVENESS_WEIGHT,
    RAW_MATERIAL_HOLDING_COST_PER_UNIT,
    READINESS_COMPLEXITY_PENALTY_PER_TECH,
    READINESS_INVESTMENT_RATE,
    READINESS_INVESTMENT_SCALE,
    READINESS_TESTING_BONUS_MAX,
    REPUTATION_ATTRACTIVENESS_WEIGHT,
    REPUTATION_UPDATE_WEIGHTS,
    RETIREMENT_LIQUIDATION_RECOVERY_RATE,
    SAME_GROUP_CANNIBALIZATION_FACTOR,
    SAME_SEGMENT_CANNIBALIZATION_FACTOR,
    SEGMENT_PRICE_TOLERANCE,
    SEGMENT_QUALITY_MULTIPLIERS,
    SEGMENT_REFERENCE_PRICES,
    SEGMENTS,
    SERVICE_READINESS_WEIGHT,
    STARTING_RAW_MATERIAL_COVERAGE,
    SUPPLIER_BASE_LEAD_TIMES,
    SUPPLIER_DEFECT_PRESSURE,
    SUPPLIER_MATERIAL_COST_MULTIPLIERS,
    SUPPLIER_NAMES,
    SUPPLIER_RISK_EXPOSURE,
    SUPPLY_RISK_INDEX,
    TECH_MAX_ATTRACTIVENESS_MODIFIER,
    TECH_MIN_ATTRACTIVENESS_MODIFIER,
    TECH_NEGATIVE_GAP_PENALTY,
    TECH_NEWER_THAN_MARKET_DEFECT_PENALTY,
    TECH_POSITIVE_GAP_BONUS,
    TECH_PREMIUM_SEGMENT_BONUS,
    TECH_ADVANTAGE_CANNIBALIZATION_FACTOR,
    UTILIZATION_STRESS_PENALTIES,
    UTILIZATION_STRESS_THRESHOLDS,
    WARRANTY_COST_FACTOR,
    WORKING_CAPITAL_TO_REVENUE_STRESS_THRESHOLD,
    DEBT_TO_REVENUE_STRESS_THRESHOLD,
)
from models.schemas import (
    ForecastAccuracyResult,
    MarketReport,
    OpenMaterialOrder,
    PersistentTeamState,
    ProductDecision,
    ProductDevelopmentProject,
    ProductLine,
    ProductRoundResult,
    RoundResult,
    TeamArchetype,
    TeamDecision,
    build_product_id,
    build_project_id,
)
from utils.repository import load_team_archetypes


@dataclass
class SupplierMetrics:
    """Weighted supplier metrics derived from the firm sourcing mix."""

    weighted_material_unit_cost: float
    weighted_lead_time: float
    weighted_supplier_defect_pressure: float
    weighted_supply_risk_exposure: float
    mix_total_pct: float
    mix_valid: bool
    normalized_mix: dict[str, float]


@dataclass
class PreparedProject:
    """Prepared development project state for the current round."""

    project: ProductDevelopmentProject
    required_investment: float
    readiness_pct: float
    min_launch_round: int
    launch_requested: bool
    cancel_requested: bool
    launched_this_round: bool = False
    launch_event: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class PreparedProductRound:
    """Prepared product data before demand is finalized."""

    product_line: ProductLine
    decision: ProductDecision
    beginning_inventory: int
    backlog_units_start: int
    actual_production_units: int
    defect_rate: float
    good_units_produced: int
    available_units_for_sale: int
    conversion_cost_per_unit: float
    contribution_margin_per_unit: float
    tech_gap_to_market: int
    tech_attractiveness_adjustment: float
    launched_this_round: bool = False
    launch_event: str = ""
    retired_this_round: bool = False
    retirement_liquidation_revenue: float = 0.0
    overtime_units_used: int = 0
    demand_allocated: float = 0.0
    actual_demand_units: float = 0.0
    service_demand_units: float = 0.0
    cannibalization_in_units: float = 0.0
    cannibalization_out_units: float = 0.0
    sales_units: int = 0
    unmet_units: int = 0
    backlog_units_end: int = 0
    lost_sales_units: int = 0
    ending_inventory: int = 0
    fill_rate: float = 1.0
    revenue: float = 0.0
    production_cost: float = 0.0
    fg_holding_cost: float = 0.0
    warranty_cost: float = 0.0
    allocated_procurement_cost: float = 0.0
    allocated_backlog_cost: float = 0.0
    allocated_expansion_cost: float = 0.0
    allocated_innovation_cost: float = 0.0
    allocated_raw_material_holding_cost: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def holding_cost(self) -> float:
        """Return the total holding cost assigned to the product."""
        return _round_currency(
            self.fg_holding_cost + self.allocated_raw_material_holding_cost
        )

    @property
    def profit_contribution(self) -> float:
        """Return the product's total profit contribution."""
        return _round_currency(
            self.revenue
            + self.retirement_liquidation_revenue
            - self.production_cost
            - self.holding_cost
            - self.warranty_cost
            - self.allocated_procurement_cost
            - self.allocated_backlog_cost
            - self.allocated_expansion_cost
            - self.allocated_innovation_cost
        )


@dataclass
class PreparedTeamRound:
    """Prepared firm-level round values before and after demand."""

    team_decision: TeamDecision
    archetype: TeamArchetype
    starting_state: PersistentTeamState
    supplier_metrics: SupplierMetrics
    installed_capacity_units: int
    effective_capacity_units: int
    beginning_raw_material_inventory: int
    raw_material_units_received: int
    raw_material_units_available: int
    requested_total_production_units: int
    feasible_total_production_units: int
    actual_total_production_units: int
    raw_material_inventory_end: int
    raw_material_holding_cost: float
    procurement_cost: float
    expansion_cost: float
    innovation_investment: float
    carryforward_material_orders: list[OpenMaterialOrder]
    placed_material_order: OpenMaterialOrder | None
    products: list[PreparedProductRound]
    projects: list[PreparedProject]
    active_product_count: int
    launch_ready_project_count: int
    launched_project_count: int
    retired_product_count: int
    cannibalized_demand_units: float
    launch_events: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class PortfolioDecisionPreview:
    """Live portfolio analytics preview for the team decision page."""

    installed_capacity_units: int
    overtime_capacity_units: int
    effective_capacity_units: int
    beginning_finished_goods_inventory: int
    beginning_raw_material_inventory: int
    raw_material_units_received: int
    raw_material_units_available: int
    total_forecast_units: int
    total_planned_production_units: int
    forecast_production_gap_units: int
    projected_max_feasible_production: int
    weighted_supplier_mix_text: str
    weighted_material_unit_cost: float
    weighted_lead_time: float
    projected_weighted_defect_rate: float
    projected_weighted_margin_per_unit: float
    projected_ending_finished_goods_inventory_if_forecast_hits: int
    projected_working_capital_requirement: float
    projected_ending_cash_before_borrowing: float
    projected_likely_borrowing_need: float
    projected_innovation_investment: float
    pipeline_project_count: int
    launch_ready_project_count: int
    average_portfolio_tech_generation: float
    tech_position_vs_market: float
    products_at_risk_count: int
    decline_product_count: int
    likely_cannibalization_exposure_units: float
    segment_mix_summary: str
    warnings: list[str]
    product_rows: list[dict[str, object]]
    project_rows: list[dict[str, object]]


@dataclass
class PlanningSnapshot:
    """Forecast-vs-plan preview metrics derived from prepared team state."""

    total_forecast_units: int
    forecast_production_gap_units: int
    projected_ending_finished_goods_inventory_if_forecast_hits: int
    projected_working_capital_requirement: float
    projected_ending_cash_before_borrowing: float
    projected_likely_borrowing_need: float
    warnings: list[str]


@dataclass
class CashFlowSummary:
    """Simple cash and debt roll-forward for the round."""

    starting_cash_balance: float
    starting_short_term_debt_balance: float
    planned_borrowing_amount: float
    automatic_borrowing_amount: float
    interest_expense: float
    ending_cash_before_borrowing: float
    ending_cash_balance: float
    ending_short_term_debt_balance: float
    working_capital_requirement: float
    liquidity_stress_score: float
    liquidity_stress_flag: bool


def run_round(
    market_report: MarketReport,
    team_decisions: list[TeamDecision],
    product_lines: list[ProductLine],
    product_decisions: list[ProductDecision],
    development_projects: list[ProductDevelopmentProject],
    existing_states: list[PersistentTeamState],
) -> tuple[
    list[RoundResult],
    list[ProductRoundResult],
    list[PersistentTeamState],
    list[ProductLine],
    list[ProductDevelopmentProject],
    list[ForecastAccuracyResult],
]:
    """Run one Stage C portfolio, planning, and finance round."""
    archetype_lookup = {item.name: item for item in load_team_archetypes()}
    state_lookup = {item.team_name.lower(): item for item in existing_states}
    product_lines_by_team = _group_product_lines(product_lines)
    product_decisions_by_team = _group_product_decisions(product_decisions)
    project_lookup_by_team = _group_projects(development_projects)

    prepared_teams: list[PreparedTeamRound] = []
    for team_decision in team_decisions:
        archetype = _resolve_archetype(team_decision, archetype_lookup)
        starting_state = _initialize_team_state(
            state_lookup.get(team_decision.team_name.lower()),
            team_decision,
            archetype,
        )
        team_product_lines = _ensure_team_product_lines(
            team_name=team_decision.team_name,
            archetype=archetype,
            existing_product_lines=product_lines_by_team.get(
                team_decision.team_name.lower(),
                [],
            ),
        )
        team_product_decisions = _resolve_product_decisions(
            team_name=team_decision.team_name,
            product_lines=team_product_lines,
            submitted_product_decisions=product_decisions_by_team.get(
                team_decision.team_name.lower(),
                [],
            ),
        )
        team_projects = _resolve_projects(
            team_name=team_decision.team_name,
            submitted_projects=project_lookup_by_team.get(
                team_decision.team_name.lower(),
                [],
            ),
        )
        prepared_teams.append(
            _prepare_team_round(
                market_report=market_report,
                team_decision=team_decision,
                archetype=archetype,
                starting_state=starting_state,
                product_lines=team_product_lines,
                product_decisions=team_product_decisions,
                development_projects=team_projects,
            )
        )

    _allocate_product_demand(market_report, prepared_teams)
    for prepared_team in prepared_teams:
        _apply_cannibalization(prepared_team)
        _finalize_product_sales(prepared_team)

    product_round_results: list[ProductRoundResult] = []
    round_results: list[RoundResult] = []
    updated_states: list[PersistentTeamState] = []
    updated_product_lines: list[ProductLine] = []
    updated_projects: list[ProductDevelopmentProject] = []
    forecast_accuracy_results: list[ForecastAccuracyResult] = []

    for prepared_team in prepared_teams:
        team_product_results = _finalize_team_product_results(
            prepared_team,
            market_report.round_number,
        )
        team_round_result = _aggregate_team_round_result(
            market_report=market_report,
            prepared_team=prepared_team,
            product_results=team_product_results,
        )
        updated_state = _update_persistent_team_state(
            market_report=market_report,
            prepared_team=prepared_team,
            team_round_result=team_round_result,
            product_results=team_product_results,
        )
        next_product_lines = _update_product_lines(
            product_lines=[item.product_line for item in prepared_team.products],
            prepared_products=prepared_team.products,
            market_report=market_report,
        )
        next_projects = _update_projects_after_round(
            prepared_team.projects,
            market_report.round_number,
        )

        product_round_results.extend(team_product_results)
        forecast_accuracy_results.extend(
            _build_forecast_accuracy_results(team_product_results)
        )
        round_results.append(team_round_result)
        updated_states.append(updated_state)
        updated_product_lines.extend(next_product_lines)
        updated_projects.extend(next_projects)

    return (
        round_results,
        product_round_results,
        sorted(updated_states, key=lambda item: item.team_name.lower()),
        sorted(
            updated_product_lines,
            key=lambda item: (item.team_name.lower(), item.slot_name),
        ),
        sorted(
            updated_projects,
            key=lambda item: (item.team_name.lower(), item.project_slot_name),
        ),
        forecast_accuracy_results,
    )


def preview_team_decision(
    market_report: MarketReport,
    candidate_team_decision: TeamDecision,
    candidate_product_decisions: list[ProductDecision],
    candidate_projects: list[ProductDevelopmentProject],
    product_lines: list[ProductLine],
    current_round_team_decisions: list[TeamDecision],
    current_round_product_decisions: list[ProductDecision],
    current_round_projects: list[ProductDevelopmentProject],
    existing_states: list[PersistentTeamState],
) -> PortfolioDecisionPreview:
    """Return a live Stage C preview for one team's portfolio and plans."""
    other_team_decisions = [
        item
        for item in current_round_team_decisions
        if item.team_name.lower() != candidate_team_decision.team_name.lower()
    ]
    other_product_decisions = [
        item
        for item in current_round_product_decisions
        if item.team_name.lower() != candidate_team_decision.team_name.lower()
    ]
    other_projects = [
        item
        for item in current_round_projects
        if item.team_name.lower() != candidate_team_decision.team_name.lower()
    ]

    archetype_lookup = {item.name: item for item in load_team_archetypes()}
    state_lookup = {item.team_name.lower(): item for item in existing_states}
    archetype = _resolve_archetype(candidate_team_decision, archetype_lookup)
    starting_state = state_lookup.get(candidate_team_decision.team_name.lower())
    team_product_lines = _ensure_team_product_lines(
        team_name=candidate_team_decision.team_name,
        archetype=archetype,
        existing_product_lines=[
            item
            for item in product_lines
            if item.team_name.lower() == candidate_team_decision.team_name.lower()
        ],
    )
    prepared_preview_team = _prepare_team_round(
        market_report=market_report,
        team_decision=candidate_team_decision,
        archetype=archetype,
        starting_state=_initialize_team_state(
            starting_state,
            candidate_team_decision,
            archetype,
        ),
        product_lines=team_product_lines,
        product_decisions=candidate_product_decisions,
        development_projects=candidate_projects,
    )
    planning_snapshot = _planning_snapshot_from_prepared(prepared_preview_team)

    (
        _,
        product_results,
        _,
        _,
        updated_projects,
        _,
    ) = run_round(
        market_report=market_report,
        team_decisions=other_team_decisions + [candidate_team_decision],
        product_lines=product_lines,
        product_decisions=other_product_decisions + candidate_product_decisions,
        development_projects=other_projects + candidate_projects,
        existing_states=existing_states,
    )

    team_product_results = [
        item
        for item in product_results
        if item.team_name.lower() == candidate_team_decision.team_name.lower()
    ]
    preview_projects = [
        item
        for item in updated_projects
        if item.team_name.lower() == candidate_team_decision.team_name.lower()
    ]
    supplier_metrics = _compute_supplier_metrics(
        candidate_team_decision,
        market_report,
        archetype,
    )
    inbound_orders, _ = _split_open_material_orders(
        market_report.round_number,
        starting_state.open_material_orders if starting_state else [],
    )
    beginning_finished_goods_inventory = sum(
        max(item.inventory_units, 0) for item in team_product_lines
    )
    beginning_raw_material_inventory = (
        max(starting_state.raw_material_inventory, 0) if starting_state else 0
    )
    if beginning_raw_material_inventory <= 0 and not (
        starting_state and starting_state.completed_rounds
    ):
        beginning_raw_material_inventory = int(
            round(archetype.base_capacity * STARTING_RAW_MATERIAL_COVERAGE)
        )
    raw_material_units_received = sum(order.quantity for order in inbound_orders)
    total_planned_production_units = sum(
        item.planned_production_units
        for item in candidate_product_decisions
        if item.is_active
    )

    warnings: list[str] = []
    if not candidate_team_decision.supplier_mix_valid():
        warnings.append(
            f"Supplier mix totals {candidate_team_decision.supplier_mix_total():.1f}% and will be normalized in the engine."
        )

    projected_max_feasible_production = sum(
        item.actual_production_units for item in team_product_results
    )
    if total_planned_production_units > projected_max_feasible_production:
        warnings.append(
            "Total planned product production exceeds shared capacity or raw-material availability."
        )

    if (
        candidate_team_decision.raw_material_order_qty < total_planned_production_units
        and beginning_raw_material_inventory < total_planned_production_units
    ):
        warnings.append(
            "Raw material ordering is low relative to the total portfolio production plan."
        )
    warnings.extend(planning_snapshot.warnings)

    for item in team_product_results:
        if item.contribution_margin_per_unit < 0:
            warnings.append(
                f"{item.product_name} is priced below its projected variable cost."
            )

    projected_innovation_investment = round(
        sum(
            max(project.investment_this_round, 0.0)
            for project in candidate_projects
            if project.is_defined() and project.status != "canceled"
        ),
        2,
    )
    weighted_defect_numerator = sum(
        item.defect_rate * max(item.actual_production_units, 1)
        for item in team_product_results
        if item.actual_production_units > 0
    )
    weighted_defect_denominator = (
        sum(item.actual_production_units for item in team_product_results) or 1
    )
    weighted_margin_numerator = sum(
        item.contribution_margin_per_unit * max(item.sales_units, 1)
        for item in team_product_results
        if item.sales_units > 0
    )
    weighted_margin_denominator = sum(item.sales_units for item in team_product_results) or 1
    active_tech_generations = [
        item.tech_generation
        for item in team_product_results
        if item.actual_production_units > 0 or item.demand_allocated > 0 or item.sales_units >= 0
    ]
    average_portfolio_tech_generation = round(
        sum(active_tech_generations) / len(active_tech_generations),
        2,
    ) if active_tech_generations else 0.0

    products_at_risk_count = sum(
        1
        for item in team_product_results
        if item.tech_gap_to_market < 0 or item.lifecycle_stage == "decline"
    )
    decline_product_count = sum(
        1 for item in team_product_results if item.lifecycle_stage == "decline"
    )
    likely_cannibalization_exposure_units = round(
        sum(item.cannibalization_out_units for item in team_product_results),
        1,
    )
    segment_mix_summary = _segment_mix_summary(candidate_product_decisions)

    product_rows = [
        {
            "slot_name": item.slot_name,
            "product_name": item.product_name,
            "target_segment": item.target_segment,
            "lifecycle_stage": item.lifecycle_stage,
            "age_in_rounds": item.age_in_rounds,
            "tech_generation": item.tech_generation,
            "forecast_units": item.forecast_units,
            "planned_production_units": item.planned_production_units,
            "actual_production_units": item.actual_production_units,
            "defect_rate": round(item.defect_rate, 4),
            "actual_demand_units": round(item.actual_demand_units, 2),
            "demand_allocated": round(item.demand_allocated, 2),
            "sales_units": item.sales_units,
            "ending_inventory": item.ending_inventory,
            "target_finished_goods_inventory": next(
                (
                    candidate.target_finished_goods_inventory
                    for candidate in candidate_product_decisions
                    if candidate.slot_name == item.slot_name
                ),
                0,
            ),
            "contribution_margin_per_unit": item.contribution_margin_per_unit,
            "launched_this_round": item.launched_this_round,
            "retire_flag": next(
                (
                    candidate.retire_flag
                    for candidate in candidate_product_decisions
                    if candidate.slot_name == item.slot_name
                ),
                False,
            ),
        }
        for item in team_product_results
    ]

    project_rows = []
    for item in preview_projects:
        if not item.is_defined():
            continue
        project_estimate = estimate_development_project(
            item,
            include_current_round_investment=False,
            current_round=market_report.round_number,
        )
        project_rows.append(
            {
                "project_slot_name": item.project_slot_name,
                "project_name": item.project_name,
                "status": item.status,
                "target_segment": item.target_segment,
                "target_tech_generation": item.target_tech_generation,
                "intended_slot_name": item.intended_slot_name,
                "required_investment": item.required_investment,
                "cumulative_investment": item.cumulative_investment,
                "investment_this_round": item.investment_this_round,
                "testing_intensity": item.testing_intensity,
                "launch_readiness_score": item.launch_readiness_score,
                "planned_launch_round": item.planned_launch_round,
                "earliest_launch_round": item.earliest_launch_round,
                "launch_now": item.launch_now,
                "estimated_cost_range": (
                    f"${project_estimate.get('estimated_low_cost', 0):,.0f}"
                    f" - ${project_estimate.get('estimated_high_cost', 0):,.0f}"
                ),
                "remaining_investment_after_this_round": project_estimate.get(
                    "remaining_investment_after_this_round",
                    0.0,
                ),
                "funding_progress_pct": project_estimate.get("funding_progress_pct", 0.0),
                "projected_readiness_after_this_round": project_estimate.get(
                    "projected_readiness_after_this_round",
                    0.0,
                ),
                "readiness_gap_points": project_estimate.get(
                    "readiness_gap_points",
                    0.0,
                ),
                "funding_gate_met": project_estimate.get("funding_gate_met", False),
                "readiness_gate_met": project_estimate.get("readiness_gate_met", False),
                "timing_gate_met": project_estimate.get("timing_gate_met", False),
                "launch_gate_met": project_estimate.get("launch_gate_met", False),
                "launch_blockers": project_estimate.get("launch_blockers", ""),
                "minimum_development_rounds": project_estimate.get(
                    "minimum_development_rounds",
                    0,
                ),
                "expected_launch_round": project_estimate.get("expected_launch_round", 0),
                "testing_adequacy": project_estimate.get("testing_adequacy", ""),
                "launch_risk": project_estimate.get("launch_risk", ""),
            }
        )

    installed_capacity_units = (
        starting_state.capacity_units
        if starting_state and starting_state.capacity_units > 0
        else archetype.base_capacity
    )
    effective_capacity_units = (
        installed_capacity_units + candidate_team_decision.overtime_capacity_units
    )

    return PortfolioDecisionPreview(
        installed_capacity_units=installed_capacity_units,
        overtime_capacity_units=candidate_team_decision.overtime_capacity_units,
        effective_capacity_units=effective_capacity_units,
        beginning_finished_goods_inventory=beginning_finished_goods_inventory,
        beginning_raw_material_inventory=beginning_raw_material_inventory,
        raw_material_units_received=raw_material_units_received,
        raw_material_units_available=(
            beginning_raw_material_inventory + raw_material_units_received
        ),
        total_forecast_units=planning_snapshot.total_forecast_units,
        total_planned_production_units=total_planned_production_units,
        forecast_production_gap_units=planning_snapshot.forecast_production_gap_units,
        projected_max_feasible_production=projected_max_feasible_production,
        weighted_supplier_mix_text=_supplier_mix_label(candidate_team_decision),
        weighted_material_unit_cost=supplier_metrics.weighted_material_unit_cost,
        weighted_lead_time=supplier_metrics.weighted_lead_time,
        projected_weighted_defect_rate=round(
            weighted_defect_numerator / weighted_defect_denominator,
            4,
        ),
        projected_weighted_margin_per_unit=round(
            weighted_margin_numerator / weighted_margin_denominator,
            2,
        ),
        projected_ending_finished_goods_inventory_if_forecast_hits=(
            planning_snapshot.projected_ending_finished_goods_inventory_if_forecast_hits
        ),
        projected_working_capital_requirement=(
            planning_snapshot.projected_working_capital_requirement
        ),
        projected_ending_cash_before_borrowing=(
            planning_snapshot.projected_ending_cash_before_borrowing
        ),
        projected_likely_borrowing_need=(
            planning_snapshot.projected_likely_borrowing_need
        ),
        projected_innovation_investment=projected_innovation_investment,
        pipeline_project_count=sum(
            1 for item in preview_projects if item.is_pipeline_active()
        ),
        launch_ready_project_count=sum(
            1
            for item in preview_projects
            if item.status == "launch_ready"
        ),
        average_portfolio_tech_generation=average_portfolio_tech_generation,
        tech_position_vs_market=round(
            average_portfolio_tech_generation - market_report.current_market_generation,
            2,
        ),
        products_at_risk_count=products_at_risk_count,
        decline_product_count=decline_product_count,
        likely_cannibalization_exposure_units=likely_cannibalization_exposure_units,
        segment_mix_summary=segment_mix_summary,
        warnings=warnings,
        product_rows=product_rows,
        project_rows=project_rows,
    )


def build_round_validation_rows(
    market_report: MarketReport,
    team_decisions: list[TeamDecision],
    product_lines: list[ProductLine],
    product_decisions: list[ProductDecision],
    development_projects: list[ProductDevelopmentProject],
    existing_states: list[PersistentTeamState],
) -> list[dict[str, object]]:
    """Build a pre-run validation summary for the instructor panel."""
    product_lines_by_team = _group_product_lines(product_lines)
    product_decisions_by_team = _group_product_decisions(product_decisions)
    projects_by_team = _group_projects(development_projects)
    archetype_lookup = {item.name: item for item in load_team_archetypes()}
    state_lookup = {item.team_name.lower(): item for item in existing_states}
    validation_rows: list[dict[str, object]] = []

    for team_decision in team_decisions:
        archetype = _resolve_archetype(team_decision, archetype_lookup)
        starting_state = _initialize_team_state(
            state_lookup.get(team_decision.team_name.lower()),
            team_decision,
            archetype,
        )
        prepared_team = _prepare_team_round(
            market_report=market_report,
            team_decision=team_decision,
            archetype=archetype,
            starting_state=starting_state,
            product_lines=_ensure_team_product_lines(
                team_name=team_decision.team_name,
                archetype=archetype,
                existing_product_lines=product_lines_by_team.get(
                    team_decision.team_name.lower(),
                    [],
                ),
            ),
            product_decisions=_resolve_product_decisions(
                team_name=team_decision.team_name,
                product_lines=product_lines_by_team.get(
                    team_decision.team_name.lower(),
                    [],
                )
                or _ensure_team_product_lines(
                    team_name=team_decision.team_name,
                    archetype=archetype,
                    existing_product_lines=[],
                ),
                submitted_product_decisions=product_decisions_by_team.get(
                    team_decision.team_name.lower(),
                    [],
                ),
            ),
            development_projects=_resolve_projects(
                team_name=team_decision.team_name,
                submitted_projects=projects_by_team.get(
                    team_decision.team_name.lower(),
                    [],
                ),
            ),
        )
        planning_snapshot = _planning_snapshot_from_prepared(prepared_team)
        active_product_count = sum(
            1 for item in prepared_team.products if item.decision.is_active
        )
        missing_forecasts = sum(
            1
            for item in prepared_team.products
            if item.decision.is_active and item.decision.forecast_units <= 0
        )
        validation_rows.append(
            {
                "team_name": team_decision.team_name,
                "active_products": prepared_team.active_product_count,
                "zero_active_products": prepared_team.active_product_count == 0,
                "missing_forecasts": missing_forecasts,
                "supplier_mix_total_pct": round(
                    prepared_team.supplier_metrics.mix_total_pct,
                    2,
                ),
                "supplier_mix_valid": prepared_team.supplier_metrics.mix_valid,
                "total_forecast_units": planning_snapshot.total_forecast_units,
                "total_planned_production_units": prepared_team.requested_total_production_units,
                "forecast_production_gap_units": planning_snapshot.forecast_production_gap_units,
                "effective_capacity_units": prepared_team.effective_capacity_units,
                "projected_max_feasible_production": prepared_team.feasible_total_production_units,
                "obviously_infeasible": (
                    prepared_team.requested_total_production_units
                    > prepared_team.feasible_total_production_units
                ),
                "forecast_plan_mismatch": (
                    active_product_count > 0
                    and abs(planning_snapshot.forecast_production_gap_units)
                    > max(planning_snapshot.total_forecast_units, 1)
                    * FORECAST_MISMATCH_WARNING_RATIO
                ),
                "likely_cash_shortfall": (
                    planning_snapshot.projected_ending_cash_before_borrowing < 0
                ),
                "pipeline_projects": sum(
                    1 for item in prepared_team.projects if item.project.is_pipeline_active()
                ),
                "launch_ready_projects": prepared_team.launch_ready_project_count,
                "launch_requests": sum(
                    1 for item in prepared_team.projects if item.launch_requested
                ),
                "multiple_launch_requests": sum(
                    1 for item in prepared_team.projects if item.launch_requested
                )
                > MAX_LAUNCHES_PER_ROUND,
            }
        )

    return validation_rows


def _resolve_archetype(
    team_decision: TeamDecision,
    archetype_lookup: dict[str, TeamArchetype],
) -> TeamArchetype:
    """Return the archetype for a team decision or fall back to the first entry."""
    if team_decision.archetype in archetype_lookup:
        return archetype_lookup[team_decision.archetype]
    return next(iter(archetype_lookup.values()))


def _initialize_team_state(
    existing_state: PersistentTeamState | None,
    team_decision: TeamDecision,
    archetype: TeamArchetype,
) -> PersistentTeamState:
    """Return an initialized persistent state for the team."""
    initial_cash_balance = _round_currency(archetype.base_capacity * archetype.base_cost * 1.2)

    if existing_state is not None:
        if not existing_state.completed_rounds:
            existing_state = replace(
                existing_state,
                archetype=team_decision.archetype,
                cash_balance=(
                    existing_state.cash_balance
                    if existing_state.cash_balance > 0
                    else initial_cash_balance
                ),
                raw_material_inventory=(
                    existing_state.raw_material_inventory
                    if existing_state.raw_material_inventory > 0
                    else int(
                        round(archetype.base_capacity * STARTING_RAW_MATERIAL_COVERAGE)
                    )
                ),
                capacity_units=(
                    existing_state.capacity_units
                    if existing_state.capacity_units > 0
                    else archetype.base_capacity
                ),
                reputation_score=(
                    existing_state.reputation_score
                    if existing_state.reputation_score > 0
                    else archetype.base_reputation
                ),
            )
        return existing_state

    return PersistentTeamState(
        team_name=team_decision.team_name,
        archetype=team_decision.archetype,
        cash_balance=initial_cash_balance,
        inventory_units=0,
        raw_material_inventory=int(round(archetype.base_capacity * STARTING_RAW_MATERIAL_COVERAGE)),
        backlog_units=0,
        capacity_units=archetype.base_capacity,
        reputation_score=archetype.base_reputation,
        completed_rounds=[],
        last_decision={},
        open_material_orders=[],
        cumulative_profit=0.0,
        short_term_debt_balance=0.0,
        interest_expense_last_round=0.0,
        liquidity_warning_flag=False,
        working_capital_stress_score=0.0,
    )


def _ensure_team_product_lines(
    team_name: str,
    archetype: TeamArchetype,
    existing_product_lines: list[ProductLine],
) -> list[ProductLine]:
    """Ensure that the team has all three product slots in memory."""
    line_by_slot = {item.slot_name: item for item in existing_product_lines}
    ensured_lines = list(existing_product_lines)

    for template in archetype.suggested_product_templates:
        if template.slot_name in line_by_slot:
            continue
        ensured_lines.append(
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

    return sorted(ensured_lines, key=lambda item: item.slot_name)


def _resolve_product_decisions(
    team_name: str,
    product_lines: list[ProductLine],
    submitted_product_decisions: list[ProductDecision],
) -> list[ProductDecision]:
    """Resolve one product decision for each slot."""
    decision_by_slot = {item.slot_name: item for item in submitted_product_decisions}
    resolved: list[ProductDecision] = []

    for product_line in sorted(product_lines, key=lambda item: item.slot_name):
        if product_line.slot_name in decision_by_slot:
            resolved.append(decision_by_slot[product_line.slot_name])
            continue
        resolved.append(
            ProductDecision(
                product_id=product_line.product_id,
                team_name=team_name,
                slot_name=product_line.slot_name,
                product_name=product_line.product_name,
                is_active=product_line.is_active,
                target_segment=product_line.target_segment,
                selling_price_per_unit=SEGMENT_REFERENCE_PRICES[product_line.target_segment],
                forecast_units=0,
                planned_production_units=0,
                qc_budget_per_unit=0.0,
                target_finished_goods_inventory=max(product_line.inventory_units, 0),
                retire_flag=False,
            )
        )

    return resolved


def _resolve_projects(
    team_name: str,
    submitted_projects: list[ProductDevelopmentProject],
) -> list[ProductDevelopmentProject]:
    """Resolve two persistent project slots for the team."""
    project_by_slot = {item.project_slot_name: item for item in submitted_projects}
    resolved: list[ProductDevelopmentProject] = []

    for project_slot_name in PROJECT_SLOT_NAMES:
        project = project_by_slot.get(project_slot_name)
        if project is None:
            resolved.append(
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
                    planned_launch_round=1,
                    earliest_launch_round=1,
                    status="concept",
                    cannibalization_group="",
                    projected_base_defect_modifier=0.0,
                    projected_demand_fit_modifier=1.0,
                    created_round=1,
                )
            )
            continue
        resolved.append(project)

    return resolved


def _prepare_team_round(
    market_report: MarketReport,
    team_decision: TeamDecision,
    archetype: TeamArchetype,
    starting_state: PersistentTeamState,
    product_lines: list[ProductLine],
    product_decisions: list[ProductDecision],
    development_projects: list[ProductDevelopmentProject],
) -> PreparedTeamRound:
    """Prepare one team's Stage B round before cross-team demand allocation."""
    supplier_metrics = _compute_supplier_metrics(team_decision, market_report, archetype)
    inbound_orders, carryforward_orders = _split_open_material_orders(
        market_report.round_number,
        starting_state.open_material_orders,
    )
    raw_material_units_received = sum(order.quantity for order in inbound_orders)
    beginning_raw_material_inventory = max(starting_state.raw_material_inventory, 0)
    if beginning_raw_material_inventory <= 0 and not starting_state.completed_rounds:
        beginning_raw_material_inventory = int(
            round(archetype.base_capacity * STARTING_RAW_MATERIAL_COVERAGE)
        )
    raw_material_units_available = beginning_raw_material_inventory + raw_material_units_received
    installed_capacity_units = max(
        starting_state.capacity_units or archetype.base_capacity,
        0,
    )
    effective_capacity_units = max(
        installed_capacity_units + max(team_decision.overtime_capacity_units, 0),
        0,
    )
    procurement_cost = _round_currency(
        max(team_decision.raw_material_order_qty, 0)
        * supplier_metrics.weighted_material_unit_cost
    )
    expansion_cost = _round_currency(
        max(team_decision.capacity_expansion_units, 0)
        * CAPACITY_EXPANSION_CAPEX_PER_UNIT
    )

    prepared_projects = _progress_projects(
        market_report=market_report,
        development_projects=development_projects,
    )
    (
        working_product_lines,
        working_product_decisions,
        prepared_projects,
        launch_events,
        pre_launch_liquidation_by_slot,
        pre_launch_retired_count,
        team_notes,
    ) = _apply_project_launches(
        market_report=market_report,
        product_lines=product_lines,
        product_decisions=product_decisions,
        prepared_projects=prepared_projects,
    )

    requested_units_by_slot = {
        decision.slot_name: max(decision.planned_production_units, 0)
        for decision in working_product_decisions
        if decision.is_active
    }
    requested_total_production_units = sum(requested_units_by_slot.values())
    feasible_total_production_units = min(
        requested_total_production_units,
        effective_capacity_units,
        raw_material_units_available,
    )
    actual_units_by_slot = _allocate_integer_proportionally(
        requested_units_by_slot,
        feasible_total_production_units,
    )
    used_raw_material_units = sum(actual_units_by_slot.values())
    raw_material_inventory_end = max(
        raw_material_units_available - used_raw_material_units,
        0,
    )
    raw_material_holding_cost = _round_currency(
        raw_material_inventory_end * RAW_MATERIAL_HOLDING_COST_PER_UNIT
    )
    placed_material_order = _build_material_order(
        market_report=market_report,
        team_decision=team_decision,
        supplier_metrics=supplier_metrics,
    )
    innovation_investment = _round_currency(
        sum(
            max(project.project.investment_this_round, 0.0)
            for project in prepared_projects
            if project.project.is_defined()
            and project.project.status not in {"canceled", "launched"}
        )
    )
    total_planned_units = sum(
        max(item.planned_production_units, 0)
        for item in working_product_decisions
        if item.is_active
    )
    utilization_ratio = (
        feasible_total_production_units / effective_capacity_units
        if effective_capacity_units > 0
        else 0.0
    )
    prepared_products: list[PreparedProductRound] = []

    decision_by_slot = {item.slot_name: item for item in working_product_decisions}
    line_by_slot = {item.slot_name: item for item in working_product_lines}
    for slot_name, product_line in sorted(line_by_slot.items()):
        decision = decision_by_slot[slot_name]
        beginning_inventory = max(product_line.inventory_units, 0)
        backlog_units_start = max(product_line.backlog_units, 0)
        actual_production_units = actual_units_by_slot.get(slot_name, 0)
        defect_rate = _compute_product_defect_rate(
            market_report=market_report,
            archetype=archetype,
            product_line=product_line,
            decision=decision,
            supplier_metrics=supplier_metrics,
            actual_production_units=actual_production_units,
            effective_capacity_units=effective_capacity_units,
            launched_this_round=product_line.launch_round == market_report.round_number,
        )
        good_units_produced = int(
            math.floor(actual_production_units * max(1.0 - defect_rate, 0.0))
        )
        available_units_for_sale = beginning_inventory + good_units_produced
        conversion_cost_per_unit = _conversion_cost_per_unit(
            archetype=archetype,
            market_report=market_report,
            actual_production_units=actual_production_units,
            overtime_capacity_units=max(team_decision.overtime_capacity_units, 0),
        )
        material_component_per_unit = (
            supplier_metrics.weighted_material_unit_cost
            if actual_production_units > 0
            else 0.0
        )
        qc_cost_per_unit = (
            max(decision.qc_budget_per_unit, 0.0) * QC_COST_REALIZATION_FACTOR
            if actual_production_units > 0
            else 0.0
        )
        contribution_margin_per_unit = _round_currency(
            max(decision.selling_price_per_unit, 0.0)
            - conversion_cost_per_unit
            - material_component_per_unit
            - qc_cost_per_unit
        )
        tech_gap = product_line.tech_generation - market_report.current_market_generation
        tech_adjustment = _technology_attractiveness_modifier(
            market_report=market_report,
            target_segment=decision.target_segment,
            tech_generation=product_line.tech_generation,
        )
        notes: list[str] = []
        if requested_total_production_units > feasible_total_production_units and decision.is_active:
            requested = requested_units_by_slot.get(slot_name, 0)
            actual = actual_units_by_slot.get(slot_name, 0)
            if actual < requested:
                notes.append(
                    f"Production capped from {requested} to {actual} by shared capacity or materials."
                )
        if product_line.launch_round == market_report.round_number:
            notes.append("Newly launched this round.")

        prepared_products.append(
            PreparedProductRound(
                product_line=product_line,
                decision=decision,
                beginning_inventory=beginning_inventory,
                backlog_units_start=backlog_units_start,
                actual_production_units=actual_production_units if decision.is_active else 0,
                defect_rate=defect_rate if decision.is_active else 0.0,
                good_units_produced=good_units_produced if decision.is_active else 0,
                available_units_for_sale=available_units_for_sale if decision.is_active else beginning_inventory,
                conversion_cost_per_unit=conversion_cost_per_unit,
                contribution_margin_per_unit=contribution_margin_per_unit,
                tech_gap_to_market=tech_gap,
                tech_attractiveness_adjustment=tech_adjustment,
                launched_this_round=product_line.launch_round == market_report.round_number,
                launch_event="; ".join(
                    event for event in launch_events if f"slot {slot_name}" in event.lower()
                ),
                retired_this_round=False,
                retirement_liquidation_revenue=pre_launch_liquidation_by_slot.get(
                    slot_name,
                    0.0,
                ),
                overtime_units_used=max(
                    actual_production_units - installed_capacity_units,
                    0,
                )
                if total_planned_units > 0
                else 0,
                notes=notes,
            )
        )

    launch_ready_project_count = sum(
        1
        for item in prepared_projects
        if item.project.status == "launch_ready"
    )
    return PreparedTeamRound(
        team_decision=team_decision,
        archetype=archetype,
        starting_state=starting_state,
        supplier_metrics=supplier_metrics,
        installed_capacity_units=installed_capacity_units,
        effective_capacity_units=effective_capacity_units,
        beginning_raw_material_inventory=beginning_raw_material_inventory,
        raw_material_units_received=raw_material_units_received,
        raw_material_units_available=raw_material_units_available,
        requested_total_production_units=requested_total_production_units,
        feasible_total_production_units=feasible_total_production_units,
        actual_total_production_units=used_raw_material_units,
        raw_material_inventory_end=raw_material_inventory_end,
        raw_material_holding_cost=raw_material_holding_cost,
        procurement_cost=procurement_cost,
        expansion_cost=expansion_cost,
        innovation_investment=innovation_investment,
        carryforward_material_orders=carryforward_orders,
        placed_material_order=placed_material_order,
        products=prepared_products,
        projects=prepared_projects,
        active_product_count=sum(1 for item in working_product_decisions if item.is_active),
        launch_ready_project_count=launch_ready_project_count,
        launched_project_count=sum(1 for item in prepared_projects if item.launched_this_round),
        retired_product_count=pre_launch_retired_count,
        cannibalized_demand_units=0.0,
        launch_events=launch_events,
        notes=team_notes,
    )


def _progress_projects(
    market_report: MarketReport,
    development_projects: list[ProductDevelopmentProject],
) -> list[PreparedProject]:
    """Advance project investment and readiness for the current round."""
    prepared_projects: list[PreparedProject] = []
    for project in development_projects:
        normalized_project = replace(project)
        if normalized_project.created_round <= 0:
            normalized_project.created_round = market_report.round_number

        if (
            normalized_project.status in {"launched", "canceled"}
            and normalized_project.project_name.strip()
        ):
            if normalized_project.investment_this_round > 0 or normalized_project.testing_intensity > 0:
                normalized_project.status = "concept"
                normalized_project.cumulative_investment = 0.0
                normalized_project.launch_readiness_score = 0.0
                normalized_project.launched_round = None
                normalized_project.canceled_round = None
                normalized_project.launch_now = False
                normalized_project.cancel_now = False
                normalized_project.created_round = market_report.round_number

        required_investment = _required_investment_for_project(normalized_project)
        min_launch_round = _minimum_launch_round_for_project(
            normalized_project,
            required_investment,
        )
        normalized_project.required_investment = required_investment
        normalized_project.earliest_launch_round = min_launch_round

        if not normalized_project.is_defined():
            normalized_project.status = "concept"
            normalized_project.required_investment = 0.0
            normalized_project.cumulative_investment = 0.0
            normalized_project.launch_readiness_score = 0.0
            normalized_project.launch_now = False
            normalized_project.cancel_now = False
            prepared_projects.append(
                PreparedProject(
                    project=normalized_project,
                    required_investment=0.0,
                    readiness_pct=0.0,
                    min_launch_round=min_launch_round,
                    launch_requested=False,
                    cancel_requested=False,
                )
            )
            continue

        cancel_requested = normalized_project.cancel_now
        if cancel_requested and normalized_project.status != "launched":
            normalized_project.status = "canceled"
            normalized_project.canceled_round = market_report.round_number
            normalized_project.launch_now = False
            normalized_project.launch_readiness_score = 0.0
            prepared_projects.append(
                PreparedProject(
                    project=normalized_project,
                    required_investment=required_investment,
                    readiness_pct=0.0,
                    min_launch_round=min_launch_round,
                    launch_requested=False,
                    cancel_requested=True,
                    notes=["Project canceled this round."],
                )
            )
            continue

        normalized_project.cumulative_investment = max(
            normalized_project.cumulative_investment + normalized_project.investment_this_round,
            0.0,
        )
        normalized_project.launch_readiness_score = _project_readiness_score(
            project=normalized_project,
            required_investment=required_investment,
        )
        min_launch_round = _minimum_launch_round_for_project(
            normalized_project,
            required_investment,
        )
        normalized_project.earliest_launch_round = min_launch_round
        progress_ratio = (
            normalized_project.cumulative_investment / required_investment
            if required_investment > 0
            else 0.0
        )
        if (
            normalized_project.cumulative_investment >= required_investment
            and normalized_project.launch_readiness_score >= LAUNCH_READINESS_THRESHOLD
            and market_report.round_number >= min_launch_round
        ):
            normalized_project.status = "launch_ready"
        elif progress_ratio >= 0.65:
            normalized_project.status = "pilot"
        elif progress_ratio > 0.0 or normalized_project.testing_intensity > 0:
            normalized_project.status = "development"
        else:
            normalized_project.status = "concept"

        prepared_projects.append(
            PreparedProject(
                project=normalized_project,
                required_investment=required_investment,
                readiness_pct=round(normalized_project.launch_readiness_score, 2),
                min_launch_round=min_launch_round,
                launch_requested=normalized_project.launch_now,
                cancel_requested=False,
            )
        )

    return sorted(prepared_projects, key=lambda item: item.project.project_slot_name)


def _apply_project_launches(
    market_report: MarketReport,
    product_lines: list[ProductLine],
    product_decisions: list[ProductDecision],
    prepared_projects: list[PreparedProject],
) -> tuple[
    list[ProductLine],
    list[ProductDecision],
    list[PreparedProject],
    list[str],
    dict[str, float],
    int,
    list[str],
]:
    """Apply launch-now decisions and replace slots when eligible."""
    line_by_slot = {item.slot_name: replace(item) for item in product_lines}
    decision_by_slot = {item.slot_name: replace(item) for item in product_decisions}
    launchable_projects = [
        item
        for item in prepared_projects
        if item.launch_requested
        and item.project.status == "launch_ready"
        and market_report.round_number >= item.min_launch_round
    ]
    launchable_projects.sort(
        key=lambda item: (
            -item.project.launch_readiness_score,
            item.project.project_slot_name,
        )
    )
    launch_events: list[str] = []
    liquidation_by_slot: dict[str, float] = {}
    retired_product_count = 0
    notes: list[str] = []

    for skipped_project in launchable_projects[MAX_LAUNCHES_PER_ROUND:]:
        skipped_project.project.launch_now = False
        skipped_project.notes.append(
            "Deferred because only one launch per team is allowed each round."
        )
        notes.append(
            f"{skipped_project.project.project_name} stayed in the pipeline because only one launch per round is allowed."
        )

    for project_wrapper in launchable_projects[:MAX_LAUNCHES_PER_ROUND]:
        project = project_wrapper.project
        target_slot = project.intended_slot_name
        existing_line = line_by_slot[target_slot]
        existing_decision = decision_by_slot[target_slot]
        replacement_name = existing_line.product_name if existing_line.is_active else None
        liquidation_revenue = 0.0
        if existing_line.is_active and existing_line.inventory_units > 0:
            liquidation_revenue = _round_currency(
                existing_line.inventory_units
                * max(existing_decision.selling_price_per_unit, 0.0)
                * RETIREMENT_LIQUIDATION_RECOVERY_RATE
            )
            liquidation_by_slot[target_slot] = liquidation_revenue
        if existing_line.is_active:
            retired_product_count += 1

        project.replaced_product_name = replacement_name
        project.status = "launched"
        project.launched_round = market_report.round_number
        project.launch_now = False
        project_wrapper.launched_this_round = True
        project_wrapper.launch_event = (
            f"Launched {project.project_name} into slot {target_slot}"
            + (
                f", replacing {replacement_name}" if replacement_name else ""
            )
        )
        launch_events.append(project_wrapper.launch_event)

        line_by_slot[target_slot] = ProductLine(
            product_id=build_product_id(project.team_name, target_slot),
            team_name=project.team_name,
            product_name=project.project_name,
            slot_name=target_slot,
            is_active=True,
            target_segment=project.target_segment,
            lifecycle_stage="launch",
            age_in_rounds=0,
            base_defect_rate_modifier=project.projected_base_defect_modifier,
            base_demand_fit_modifier=project.projected_demand_fit_modifier,
            tech_generation=project.target_tech_generation,
            cannibalization_group=project.cannibalization_group,
            launch_round=market_report.round_number,
            retirement_flag=False,
            retired_round=None,
            replacement_project_id=project.project_id,
            inventory_units=0,
            backlog_units=0,
        )
        decision_by_slot[target_slot] = ProductDecision(
            product_id=build_product_id(project.team_name, target_slot),
            team_name=project.team_name,
            slot_name=target_slot,
            product_name=project.project_name,
            is_active=True,
            target_segment=project.target_segment,
            selling_price_per_unit=max(existing_decision.selling_price_per_unit, 0.0),
            forecast_units=max(existing_decision.forecast_units, 0),
            planned_production_units=max(existing_decision.planned_production_units, 0),
            qc_budget_per_unit=max(existing_decision.qc_budget_per_unit, 0.0),
            target_finished_goods_inventory=max(
                existing_decision.target_finished_goods_inventory,
                0,
            ),
            retire_flag=False,
        )
        notes.append(project_wrapper.launch_event)

    return (
        [line_by_slot[slot] for slot in sorted(line_by_slot)],
        [decision_by_slot[slot] for slot in sorted(decision_by_slot)],
        prepared_projects,
        launch_events,
        liquidation_by_slot,
        retired_product_count,
        notes,
    )


def _compute_supplier_metrics(
    team_decision: TeamDecision,
    market_report: MarketReport,
    archetype: TeamArchetype,
) -> SupplierMetrics:
    """Compute weighted supplier metrics from the numeric sourcing mix."""
    normalized_mix = _normalized_supplier_mix(team_decision)
    weighted_material_multiplier = sum(
        normalized_mix[name] * SUPPLIER_MATERIAL_COST_MULTIPLIERS[name]
        for name in SUPPLIER_NAMES
    )
    weighted_lead_time = sum(
        normalized_mix[name] * SUPPLIER_BASE_LEAD_TIMES[name]
        for name in SUPPLIER_NAMES
    )
    weighted_defect_pressure = sum(
        normalized_mix[name] * SUPPLIER_DEFECT_PRESSURE[name]
        for name in SUPPLIER_NAMES
    )
    weighted_supply_risk_exposure = sum(
        normalized_mix[name] * SUPPLIER_RISK_EXPOSURE[name]
        for name in SUPPLIER_NAMES
    )
    expedited_share = max(team_decision.expedited_order_share_pct, 0.0) / 100.0
    weighted_material_unit_cost = (
        archetype.base_cost
        * BASE_MATERIAL_COST_SHARE
        * weighted_material_multiplier
        * market_report.material_cost_index
        * (1.0 + expedited_share * EXPEDITED_ORDER_COST_UPLIFT)
    )
    adjusted_lead_time = max(
        weighted_lead_time
        * SUPPLY_RISK_INDEX[market_report.supply_risk]
        - expedited_share * EXPEDITED_LEAD_TIME_REDUCTION,
        1.0,
    )
    return SupplierMetrics(
        weighted_material_unit_cost=_round_currency(weighted_material_unit_cost),
        weighted_lead_time=round(adjusted_lead_time, 2),
        weighted_supplier_defect_pressure=round(weighted_defect_pressure, 4),
        weighted_supply_risk_exposure=round(weighted_supply_risk_exposure, 4),
        mix_total_pct=team_decision.supplier_mix_total(),
        mix_valid=team_decision.supplier_mix_valid(),
        normalized_mix=normalized_mix,
    )


def _allocate_product_demand(
    market_report: MarketReport,
    prepared_teams: list[PreparedTeamRound],
) -> None:
    """Allocate shared market demand across all active products."""
    segment_demand = {
        segment: market_report.total_demand * share
        for segment, share in market_report.normalized_shares().items()
    }
    attractiveness_by_segment: dict[str, list[tuple[PreparedProductRound, float]]] = {
        segment: [] for segment in SEGMENTS
    }

    for prepared_team in prepared_teams:
        for product in prepared_team.products:
            if not product.decision.is_active:
                continue
            for segment in SEGMENTS:
                attractiveness = _segment_attractiveness(
                    market_report=market_report,
                    prepared_team=prepared_team,
                    product=product,
                    segment=segment,
                )
                attractiveness_by_segment[segment].append((product, attractiveness))

    for segment, segment_rows in attractiveness_by_segment.items():
        total_attractiveness = sum(score for _, score in segment_rows)
        if total_attractiveness <= 0:
            continue
        for product, score in segment_rows:
            product.demand_allocated += (
                segment_demand[segment] * score / total_attractiveness
            )


def _apply_cannibalization(prepared_team: PreparedTeamRound) -> None:
    """Transfer some demand from older products to stronger new products in-team."""
    active_products = [
        item for item in prepared_team.products if item.decision.is_active
    ]
    for receiver in active_products:
        for donor in active_products:
            if donor.decision.slot_name == receiver.decision.slot_name:
                continue
            if donor.demand_allocated <= 0:
                continue
            if receiver.product_line.age_in_rounds > donor.product_line.age_in_rounds:
                continue
            receiver_newer = (
                receiver.product_line.tech_generation > donor.product_line.tech_generation
                or receiver.product_line.age_in_rounds < donor.product_line.age_in_rounds
                or receiver.product_line.lifecycle_stage in {"launch", "growth"}
            )
            donor_older = donor.product_line.lifecycle_stage in {"maturity", "decline"}
            if not (receiver_newer and donor_older):
                continue

            same_group_factor = (
                SAME_GROUP_CANNIBALIZATION_FACTOR
                if receiver.product_line.cannibalization_group
                and receiver.product_line.cannibalization_group
                == donor.product_line.cannibalization_group
                else 0.65
            )
            segment_factor = (
                SAME_SEGMENT_CANNIBALIZATION_FACTOR
                if receiver.decision.target_segment == donor.decision.target_segment
                else DIFFERENT_SEGMENT_CANNIBALIZATION_FACTOR
            )
            lifecycle_factor = (
                LIFECYCLE_GAP_CANNIBALIZATION_FACTOR
                if receiver.product_line.lifecycle_stage in {"launch", "growth"}
                and donor.product_line.lifecycle_stage in {"maturity", "decline"}
                else 0.75
            )
            tech_advantage = max(
                receiver.product_line.tech_generation - donor.product_line.tech_generation,
                0,
            )
            transfer_share = min(
                BASE_CANNIBALIZATION_RATE
                * same_group_factor
                * segment_factor
                * lifecycle_factor
                * (1.0 + tech_advantage * TECH_ADVANTAGE_CANNIBALIZATION_FACTOR)
                * (
                    LAUNCH_CANNIBALIZATION_BOOST
                    if receiver.launched_this_round
                    else 1.0
                ),
                MAX_CANNIBALIZATION_TRANSFER_SHARE,
            )
            transfer_units = donor.demand_allocated * transfer_share
            if transfer_units <= 0:
                continue
            donor.demand_allocated -= transfer_units
            receiver.demand_allocated += transfer_units
            donor.cannibalization_out_units += transfer_units
            receiver.cannibalization_in_units += transfer_units
            prepared_team.cannibalized_demand_units += transfer_units


def _finalize_product_sales(prepared_team: PreparedTeamRound) -> None:
    """Finalize product-level service outcomes after demand and cannibalization."""
    total_unmet_units = 0.0
    for product in prepared_team.products:
        product.actual_demand_units = max(product.demand_allocated, 0.0)
        if not product.decision.is_active:
            product.service_demand_units = float(product.backlog_units_start)
            product.sales_units = min(product.available_units_for_sale, product.backlog_units_start)
            product.ending_inventory = max(
                product.available_units_for_sale - product.sales_units,
                0,
            )
            product.fill_rate = 1.0
            product.unmet_units = max(
                product.backlog_units_start - product.sales_units,
                0,
            )
            total_unmet_units += product.unmet_units
            continue

        product.service_demand_units = max(
            product.demand_allocated + product.backlog_units_start,
            0.0,
        )
        product.sales_units = min(
            int(math.floor(product.service_demand_units)),
            product.available_units_for_sale,
        )
        product.unmet_units = max(product.service_demand_units - product.sales_units, 0.0)
        total_unmet_units += product.unmet_units
        product.ending_inventory = max(
            product.available_units_for_sale - product.sales_units,
            0,
        )

    backlog_allocation = _allocate_backlog_across_products(
        products=prepared_team.products,
        max_team_backorder_units=max(prepared_team.team_decision.max_backorder_units, 0),
    )
    for product in prepared_team.products:
        product.backlog_units_end = backlog_allocation.get(product.decision.slot_name, 0)
        product.lost_sales_units = max(
            int(math.floor(product.unmet_units)) - product.backlog_units_end,
            0,
        )
        if product.decision.retire_flag and product.decision.is_active:
            if product.backlog_units_end > 0:
                product.lost_sales_units += product.backlog_units_end
                product.backlog_units_end = 0
            if product.ending_inventory > 0:
                product.retirement_liquidation_revenue += _round_currency(
                    product.ending_inventory
                    * max(product.decision.selling_price_per_unit, 0.0)
                    * RETIREMENT_LIQUIDATION_RECOVERY_RATE
                )
            product.ending_inventory = 0
            product.retired_this_round = True
            product.notes.append("Retired at the end of the round.")
        denominator = product.service_demand_units
        product.fill_rate = (
            min(product.sales_units / denominator, 1.0)
            if denominator > 0
            else 1.0
        )
        product.revenue = _round_currency(
            product.sales_units * max(product.decision.selling_price_per_unit, 0.0)
        )
        product.production_cost = _round_currency(
            product.actual_production_units
            * (
                product.conversion_cost_per_unit
                + max(product.decision.qc_budget_per_unit, 0.0)
                * QC_COST_REALIZATION_FACTOR
            )
        )
        product.fg_holding_cost = _round_currency(
            product.ending_inventory * HOLDING_COST_PER_UNIT
        )
        product.warranty_cost = _round_currency(
            product.sales_units * product.defect_rate * WARRANTY_COST_FACTOR
        )
        if product.lost_sales_units > 0:
            product.notes.append(f"Lost {product.lost_sales_units} sales units.")
        if product.backlog_units_end > 0:
            product.notes.append(f"Carried {product.backlog_units_end} backlog units.")

    production_share = _allocation_share_map(
        {
            item.decision.slot_name: item.actual_production_units
            for item in prepared_team.products
        }
    )
    backlog_share = _allocation_share_map(
        {
            item.decision.slot_name: item.backlog_units_end
            for item in prepared_team.products
        }
    )
    innovation_share = _allocation_share_map(
        {
            item.decision.slot_name: max(item.demand_allocated, 1.0)
            for item in prepared_team.products
            if item.decision.is_active
        }
    )
    total_backlog_end = sum(item.backlog_units_end for item in prepared_team.products)

    for product in prepared_team.products:
        slot_name = product.decision.slot_name
        product.allocated_procurement_cost = _round_currency(
            prepared_team.procurement_cost * production_share.get(slot_name, 0.0)
        )
        product.allocated_backlog_cost = _round_currency(
            total_backlog_end
            * BACKLOG_PENALTY_PER_UNIT
            * backlog_share.get(slot_name, 0.0)
        )
        product.allocated_expansion_cost = _round_currency(
            prepared_team.expansion_cost * production_share.get(slot_name, 0.0)
        )
        product.allocated_innovation_cost = _round_currency(
            prepared_team.innovation_investment * innovation_share.get(slot_name, 0.0)
        )
        product.allocated_raw_material_holding_cost = _round_currency(
            prepared_team.raw_material_holding_cost
            * production_share.get(slot_name, 0.0)
        )


def _planning_snapshot_from_prepared(
    prepared_team: PreparedTeamRound,
) -> PlanningSnapshot:
    """Build forecast-vs-plan and liquidity preview metrics before save/run."""
    active_products = [item for item in prepared_team.products if item.decision.is_active]
    total_forecast_units = sum(item.decision.forecast_units for item in active_products)
    forecast_production_gap_units = (
        prepared_team.requested_total_production_units - total_forecast_units
    )
    target_inventory_units = sum(
        item.decision.target_finished_goods_inventory for item in active_products
    )

    projected_fg_inventory = 0
    projected_revenue = 0.0
    projected_warranty_cost = 0.0
    projected_production_cost = 0.0
    unmet_forecast_by_slot: dict[str, int] = {}
    variable_cost_sum = 0.0
    variable_cost_units = 0

    for product in active_products:
        forecast_service_units = max(
            product.decision.forecast_units + product.backlog_units_start,
            0,
        )
        projected_sales_units = min(
            int(math.floor(forecast_service_units)),
            product.available_units_for_sale,
        )
        projected_unmet_units = max(
            int(math.floor(forecast_service_units)) - projected_sales_units,
            0,
        )
        unmet_forecast_by_slot[product.decision.slot_name] = projected_unmet_units
        projected_fg_inventory += max(
            product.available_units_for_sale - projected_sales_units,
            0,
        )
        projected_revenue += projected_sales_units * max(
            product.decision.selling_price_per_unit,
            0.0,
        )
        projected_warranty_cost += (
            projected_sales_units * product.defect_rate * WARRANTY_COST_FACTOR
        )
        projected_production_cost += (
            product.actual_production_units
            * (
                product.conversion_cost_per_unit
                + max(product.decision.qc_budget_per_unit, 0.0)
                * QC_COST_REALIZATION_FACTOR
            )
        )
        if product.actual_production_units > 0:
            variable_cost_sum += (
                product.actual_production_units
                * (
                    product.conversion_cost_per_unit
                    + max(product.decision.qc_budget_per_unit, 0.0)
                    * QC_COST_REALIZATION_FACTOR
                    + prepared_team.supplier_metrics.weighted_material_unit_cost
                )
            )
            variable_cost_units += product.actual_production_units

    projected_total_unmet_units = sum(unmet_forecast_by_slot.values())
    backlog_cap = min(
        projected_total_unmet_units,
        max(prepared_team.team_decision.max_backorder_units, 0),
    )
    backlog_share = _allocate_integer_proportionally(
        unmet_forecast_by_slot,
        backlog_cap,
    )
    projected_backlog_cost = _round_currency(
        sum(backlog_share.values()) * BACKLOG_PENALTY_PER_UNIT
    )
    projected_holding_cost = _round_currency(
        projected_fg_inventory * HOLDING_COST_PER_UNIT + prepared_team.raw_material_holding_cost
    )
    projected_interest_expense = _round_currency(
        (
            prepared_team.starting_state.short_term_debt_balance
            + max(prepared_team.team_decision.planned_borrowing_amount, 0.0)
        )
        * PERIODIC_INTEREST_RATE
    )
    projected_ending_cash_before_borrowing = _round_currency(
        prepared_team.starting_state.cash_balance
        + max(prepared_team.team_decision.planned_borrowing_amount, 0.0)
        + projected_revenue
        - prepared_team.procurement_cost
        - _round_currency(projected_production_cost)
        - projected_holding_cost
        - _round_currency(projected_warranty_cost)
        - projected_backlog_cost
        - prepared_team.expansion_cost
        - prepared_team.innovation_investment
        - projected_interest_expense
    )
    projected_likely_borrowing_need = max(
        -projected_ending_cash_before_borrowing,
        0.0,
    )
    projected_average_unit_cost = (
        variable_cost_sum / variable_cost_units if variable_cost_units > 0 else 0.0
    )
    projected_working_capital_requirement = _working_capital_requirement(
        finished_goods_inventory_units=projected_fg_inventory,
        fg_unit_cost=projected_average_unit_cost,
        raw_material_inventory_units=prepared_team.raw_material_inventory_end,
        raw_material_unit_cost=prepared_team.supplier_metrics.weighted_material_unit_cost,
        short_term_debt_balance=(
            prepared_team.starting_state.short_term_debt_balance
            + max(prepared_team.team_decision.planned_borrowing_amount, 0.0)
            + projected_likely_borrowing_need
        ),
    )

    warnings: list[str] = []
    if total_forecast_units > 0 and prepared_team.requested_total_production_units < (
        total_forecast_units * FORECAST_LOW_COVERAGE_RATIO
    ):
        warnings.append(
            "Production plan covers less than the expected forecast demand."
        )
    if total_forecast_units > 0 and prepared_team.requested_total_production_units > (
        total_forecast_units * FORECAST_EXCESS_PRODUCTION_RATIO
    ):
        warnings.append(
            "Production plan materially exceeds the submitted demand forecast."
        )
    if (
        total_forecast_units > 0
        and abs(forecast_production_gap_units)
        > total_forecast_units * FORECAST_MISMATCH_WARNING_RATIO
    ):
        warnings.append(
            "Forecast and production are misaligned enough to create S&OP risk."
        )
    if (
        target_inventory_units > 0
        and total_forecast_units > 0
        and target_inventory_units > total_forecast_units * 0.55
    ):
        warnings.append(
            "Target finished-goods inventory is high relative to the submitted forecast."
        )
    if projected_ending_cash_before_borrowing < 0:
        warnings.append(
            "Projected cash will likely go negative without additional borrowing."
        )

    return PlanningSnapshot(
        total_forecast_units=total_forecast_units,
        forecast_production_gap_units=forecast_production_gap_units,
        projected_ending_finished_goods_inventory_if_forecast_hits=projected_fg_inventory,
        projected_working_capital_requirement=projected_working_capital_requirement,
        projected_ending_cash_before_borrowing=projected_ending_cash_before_borrowing,
        projected_likely_borrowing_need=_round_currency(projected_likely_borrowing_need),
        warnings=warnings,
    )


def _working_capital_requirement(
    finished_goods_inventory_units: int,
    fg_unit_cost: float,
    raw_material_inventory_units: int,
    raw_material_unit_cost: float,
    short_term_debt_balance: float,
) -> float:
    """Return a simple working-capital burden metric."""
    fg_inventory_value = max(finished_goods_inventory_units, 0) * max(fg_unit_cost, 0.0)
    raw_material_value = max(raw_material_inventory_units, 0) * max(raw_material_unit_cost, 0.0)
    debt_burden = max(short_term_debt_balance, 0.0) * 0.15
    return _round_currency(fg_inventory_value + raw_material_value + debt_burden)


def _build_cash_flow_summary(
    prepared_team: PreparedTeamRound,
    revenue: float,
    core_costs_ex_interest: float,
    finished_goods_inventory_units: int,
    fg_unit_cost: float,
) -> CashFlowSummary:
    """Roll forward cash and short-term debt with simple borrowing rules."""
    starting_cash_balance = prepared_team.starting_state.cash_balance
    starting_short_term_debt_balance = (
        prepared_team.starting_state.short_term_debt_balance
    )
    planned_borrowing_amount = max(
        prepared_team.team_decision.planned_borrowing_amount,
        0.0,
    )
    interest_expense = _round_currency(
        (starting_short_term_debt_balance + planned_borrowing_amount)
        * PERIODIC_INTEREST_RATE
    )
    ending_cash_before_borrowing = _round_currency(
        starting_cash_balance
        + planned_borrowing_amount
        + revenue
        - core_costs_ex_interest
        - interest_expense
    )
    automatic_borrowing_amount = _round_currency(
        max(-ending_cash_before_borrowing, 0.0)
    )
    ending_cash_balance = _round_currency(
        ending_cash_before_borrowing + automatic_borrowing_amount
    )
    ending_short_term_debt_balance = _round_currency(
        starting_short_term_debt_balance
        + planned_borrowing_amount
        + automatic_borrowing_amount
    )
    working_capital_requirement = _working_capital_requirement(
        finished_goods_inventory_units=finished_goods_inventory_units,
        fg_unit_cost=fg_unit_cost,
        raw_material_inventory_units=prepared_team.raw_material_inventory_end,
        raw_material_unit_cost=prepared_team.supplier_metrics.weighted_material_unit_cost,
        short_term_debt_balance=ending_short_term_debt_balance,
    )
    revenue_base = max(revenue, 1.0)
    stress_points = 0
    if ending_cash_balance <= LIQUIDITY_LOW_CASH_THRESHOLD:
        stress_points += 1
    if ending_short_term_debt_balance / revenue_base > DEBT_TO_REVENUE_STRESS_THRESHOLD:
        stress_points += 1
    if working_capital_requirement / revenue_base > WORKING_CAPITAL_TO_REVENUE_STRESS_THRESHOLD:
        stress_points += 1
    if starting_short_term_debt_balance > 0 and (
        planned_borrowing_amount > 0 or automatic_borrowing_amount > 0
    ):
        stress_points += 1
    liquidity_stress_score = round((stress_points / 4.0) * 100.0, 1)
    liquidity_stress_flag = (
        stress_points >= 2
        or automatic_borrowing_amount > 0
        or ending_cash_balance <= 0
    )
    return CashFlowSummary(
        starting_cash_balance=_round_currency(starting_cash_balance),
        starting_short_term_debt_balance=_round_currency(
            starting_short_term_debt_balance
        ),
        planned_borrowing_amount=_round_currency(planned_borrowing_amount),
        automatic_borrowing_amount=automatic_borrowing_amount,
        interest_expense=interest_expense,
        ending_cash_before_borrowing=ending_cash_before_borrowing,
        ending_cash_balance=max(ending_cash_balance, 0.0),
        ending_short_term_debt_balance=ending_short_term_debt_balance,
        working_capital_requirement=working_capital_requirement,
        liquidity_stress_score=liquidity_stress_score,
        liquidity_stress_flag=liquidity_stress_flag,
    )


def _build_forecast_accuracy_results(
    product_results: list[ProductRoundResult],
) -> list[ForecastAccuracyResult]:
    """Build persisted forecast-vs-actual diagnostics from product results."""
    return [
        ForecastAccuracyResult(
            round_number=result.round_number,
            team_name=result.team_name,
            product_id=result.product_id,
            slot_name=result.slot_name,
            product_name=result.product_name,
            forecast_units=result.forecast_units,
            actual_demand_units=result.actual_demand_units,
            actual_sales_units=result.sales_units,
            forecast_error_units=result.forecast_error_units,
            absolute_error_units=result.absolute_error_units,
            forecast_bias_pct=result.forecast_bias_pct,
            mape_or_wape_value=result.mape_or_wape_value,
        )
        for result in product_results
    ]


def _finalize_team_product_results(
    prepared_team: PreparedTeamRound,
    round_number: int,
) -> list[ProductRoundResult]:
    """Convert prepared product state into persisted result objects."""
    product_results: list[ProductRoundResult] = []
    for product in prepared_team.products:
        product_results.append(
            ProductRoundResult(
                round_number=round_number,
                team_name=prepared_team.team_decision.team_name,
                product_id=product.product_line.product_id,
                product_name=product.decision.product_name,
                slot_name=product.decision.slot_name,
                target_segment=product.decision.target_segment,
                lifecycle_stage=product.product_line.lifecycle_stage,
                age_in_rounds=product.product_line.age_in_rounds,
                tech_generation=product.product_line.tech_generation,
                cannibalization_group=product.product_line.cannibalization_group,
                selling_price_per_unit=_round_currency(product.decision.selling_price_per_unit),
                forecast_units=product.decision.forecast_units,
                planned_production_units=product.decision.planned_production_units,
                actual_production_units=product.actual_production_units,
                defect_rate=round(product.defect_rate, 4),
                good_units_produced=product.good_units_produced,
                demand_allocated=round(product.demand_allocated, 2),
                actual_demand_units=round(product.actual_demand_units, 2),
                sales_units=product.sales_units,
                lost_sales_units=product.lost_sales_units,
                ending_inventory=product.ending_inventory,
                fill_rate=round(product.fill_rate, 4),
                forecast_error_units=round(
                    product.actual_demand_units - product.decision.forecast_units,
                    2,
                ),
                absolute_error_units=round(
                    abs(product.actual_demand_units - product.decision.forecast_units),
                    2,
                ),
                forecast_bias_pct=round(
                    (product.actual_demand_units - product.decision.forecast_units)
                    / max(product.decision.forecast_units, 1),
                    4,
                ),
                mape_or_wape_value=round(
                    abs(product.actual_demand_units - product.decision.forecast_units)
                    / max(product.actual_demand_units, 1.0),
                    4,
                ),
                revenue=product.revenue,
                production_cost=product.production_cost,
                holding_cost=product.holding_cost,
                warranty_cost=product.warranty_cost,
                allocated_procurement_cost=product.allocated_procurement_cost,
                allocated_backlog_cost=product.allocated_backlog_cost,
                allocated_expansion_cost=product.allocated_expansion_cost,
                contribution_margin_per_unit=product.contribution_margin_per_unit,
                profit_contribution=product.profit_contribution,
                beginning_inventory=product.beginning_inventory,
                backlog_units_start=product.backlog_units_start,
                backlog_units_end=product.backlog_units_end,
                tech_gap_to_market=product.tech_gap_to_market,
                tech_attractiveness_adjustment=round(
                    product.tech_attractiveness_adjustment,
                    3,
                ),
                cannibalization_in_units=round(product.cannibalization_in_units, 2),
                cannibalization_out_units=round(product.cannibalization_out_units, 2),
                launched_this_round=product.launched_this_round,
                launch_event=product.launch_event,
                retired_this_round=product.retired_this_round,
                retirement_liquidation_revenue=product.retirement_liquidation_revenue,
                notes=" ".join(product.notes).strip(),
            )
        )
    return product_results


def _aggregate_team_round_result(
    market_report: MarketReport,
    prepared_team: PreparedTeamRound,
    product_results: list[ProductRoundResult],
) -> RoundResult:
    """Aggregate product-level outputs back into the firm summary."""
    total_forecast_units = sum(item.forecast_units for item in product_results)
    total_actual_demand_units = round(
        sum(item.actual_demand_units for item in product_results),
        2,
    )
    total_forecast_error_units = round(
        total_actual_demand_units - total_forecast_units,
        2,
    )
    total_absolute_forecast_error_units = round(
        sum(item.absolute_error_units for item in product_results),
        2,
    )
    forecast_wape = round(
        total_absolute_forecast_error_units / max(total_actual_demand_units, 1.0),
        4,
    )
    total_sales = sum(item.sales_units for item in product_results)
    total_revenue = _round_currency(sum(item.revenue for item in product_results))
    total_production_cost = _round_currency(sum(item.production_cost for item in product_results))
    total_holding_cost = _round_currency(sum(item.holding_cost for item in product_results))
    total_warranty_cost = _round_currency(sum(item.warranty_cost for item in product_results))
    total_backlog_cost = _round_currency(sum(item.allocated_backlog_cost for item in product_results))
    total_innovation_cost = prepared_team.innovation_investment
    total_ending_inventory = sum(item.ending_inventory for item in product_results)
    total_lost_sales = sum(item.lost_sales_units for item in product_results)
    total_backlog_end = sum(item.backlog_units_end for item in product_results)
    total_beginning_inventory = sum(item.beginning_inventory for item in product_results)
    total_backlog_start = sum(item.backlog_units_start for item in product_results)
    total_demand_allocated = round(sum(item.demand_allocated for item in product_results), 2)
    total_good_units = sum(item.good_units_produced for item in product_results)
    service_gap_units = round(total_lost_sales + total_backlog_end, 2)
    total_liquidation_revenue = _round_currency(
        sum(item.retirement_liquidation_revenue for item in product_results)
    )
    core_costs_ex_interest = _round_currency(
        prepared_team.procurement_cost
        + total_production_cost
        + total_holding_cost
        + total_warranty_cost
        + total_backlog_cost
        + prepared_team.expansion_cost
        + total_innovation_cost
    )
    weighted_fg_unit_cost = (
        sum(
            item.actual_production_units
            * (
                (
                    item.production_cost / max(item.actual_production_units, 1)
                    if item.actual_production_units > 0
                    else 0.0
                )
                + prepared_team.supplier_metrics.weighted_material_unit_cost
            )
            for item in product_results
            if item.actual_production_units > 0
        )
        / max(sum(item.actual_production_units for item in product_results), 1)
    )
    cash_flow_summary = _build_cash_flow_summary(
        prepared_team=prepared_team,
        revenue=_round_currency(total_revenue + total_liquidation_revenue),
        core_costs_ex_interest=core_costs_ex_interest,
        finished_goods_inventory_units=total_ending_inventory,
        fg_unit_cost=weighted_fg_unit_cost,
    )
    total_cost = _round_currency(
        core_costs_ex_interest + cash_flow_summary.interest_expense
    )
    profit = _round_currency(
        total_revenue + total_liquidation_revenue - total_cost
    )
    weighted_average_selling_price = _round_currency(
        total_revenue / total_sales if total_sales > 0 else 0.0
    )
    contribution_margin_per_unit = _round_currency(
        (
            total_revenue
            - prepared_team.procurement_cost
            - total_production_cost
            - total_warranty_cost
        )
        / total_sales
        if total_sales > 0
        else 0.0
    )
    weighted_defect_rate = (
        sum(item.defect_rate * max(item.actual_production_units, 1) for item in product_results)
        / max(sum(item.actual_production_units for item in product_results), 1)
    )
    total_service_demand = total_demand_allocated + total_backlog_start
    fill_rate = (
        min(total_sales / total_service_demand, 1.0)
        if total_service_demand > 0
        else 1.0
    )
    reputation_after_round = _update_reputation(
        current_reputation=prepared_team.starting_state.reputation_score,
        defect_rate=weighted_defect_rate,
        fill_rate=fill_rate,
        lost_sales_units=total_lost_sales,
        backlog_units_end=total_backlog_end,
        demand_allocated=total_service_demand,
        quality_sensitivity=market_report.quality_sensitivity,
    )
    if cash_flow_summary.liquidity_stress_flag:
        reputation_after_round = max(
            reputation_after_round - LIQUIDITY_STRESS_REPUTATION_PENALTY,
            0.0,
        )
    active_tech_generations = [
        item.tech_generation for item in product_results if item.sales_units >= 0
    ]
    average_portfolio_tech_generation = round(
        sum(active_tech_generations) / len(active_tech_generations),
        2,
    ) if active_tech_generations else 0.0
    notes = list(prepared_team.notes)
    notes.append(
        f"Portfolio forecast WAPE was {forecast_wape:.2%} against realized demand."
    )
    if total_lost_sales > 0:
        notes.append(f"Lost {total_lost_sales} sales units across the portfolio.")
    if total_backlog_end > 0:
        notes.append(f"Carried {total_backlog_end} backlog units into next round.")
    if total_liquidation_revenue > 0:
        notes.append(f"Generated ${total_liquidation_revenue:,.2f} from retirement liquidation.")
    if cash_flow_summary.planned_borrowing_amount > 0:
        notes.append(
            f"Used ${cash_flow_summary.planned_borrowing_amount:,.2f} of planned borrowing."
        )
    if cash_flow_summary.automatic_borrowing_amount > 0:
        notes.append(
            f"Auto-borrowed ${cash_flow_summary.automatic_borrowing_amount:,.2f} to cover a cash shortfall."
        )
    if cash_flow_summary.liquidity_stress_flag:
        notes.append("Liquidity stress flagged this round.")

    return RoundResult(
        round_number=market_report.round_number,
        team_name=prepared_team.team_decision.team_name,
        archetype=prepared_team.team_decision.archetype,
        active_product_count=prepared_team.active_product_count,
        active_project_count=sum(
            1 for item in prepared_team.projects if item.project.is_pipeline_active()
        ),
        launch_ready_project_count=prepared_team.launch_ready_project_count,
        launched_project_count=prepared_team.launched_project_count,
        retired_product_count=sum(
            1 for item in product_results if item.retired_this_round
        ) + max(prepared_team.retired_product_count, 0),
        total_forecast_units=total_forecast_units,
        total_actual_demand_units=total_actual_demand_units,
        forecast_error_units=total_forecast_error_units,
        absolute_forecast_error_units=total_absolute_forecast_error_units,
        forecast_wape=forecast_wape,
        service_gap_units=service_gap_units,
        weighted_average_selling_price=weighted_average_selling_price,
        planned_production_units=prepared_team.requested_total_production_units,
        actual_production_units=prepared_team.actual_total_production_units,
        effective_capacity_units=prepared_team.effective_capacity_units,
        utilization_pct=round(
            _safe_pct(
                prepared_team.actual_total_production_units,
                prepared_team.effective_capacity_units,
            ),
            2,
        ),
        weighted_material_unit_cost=prepared_team.supplier_metrics.weighted_material_unit_cost,
        defect_rate=round(weighted_defect_rate, 4),
        good_units_produced=total_good_units,
        demand_allocated=total_demand_allocated,
        sales_units=total_sales,
        lost_sales_units=total_lost_sales,
        backlog_units_end=total_backlog_end,
        ending_inventory=total_ending_inventory,
        ending_raw_material_inventory=prepared_team.raw_material_inventory_end,
        fill_rate=round(fill_rate, 4),
        revenue=_round_currency(total_revenue + total_liquidation_revenue),
        procurement_cost=prepared_team.procurement_cost,
        production_cost=total_production_cost,
        holding_cost=total_holding_cost,
        warranty_cost=total_warranty_cost,
        backlog_cost=total_backlog_cost,
        expansion_cost=prepared_team.expansion_cost,
        innovation_investment=total_innovation_cost,
        interest_expense=cash_flow_summary.interest_expense,
        working_capital_requirement=cash_flow_summary.working_capital_requirement,
        planned_borrowing_amount=cash_flow_summary.planned_borrowing_amount,
        automatic_borrowing_amount=cash_flow_summary.automatic_borrowing_amount,
        ending_cash_balance=cash_flow_summary.ending_cash_balance,
        short_term_debt_balance=cash_flow_summary.ending_short_term_debt_balance,
        liquidity_stress_flag=cash_flow_summary.liquidity_stress_flag,
        total_cost=total_cost,
        profit=profit,
        contribution_margin_per_unit=contribution_margin_per_unit,
        reputation_after_round=round(reputation_after_round, 2),
        average_portfolio_tech_generation=average_portfolio_tech_generation,
        cannibalized_demand_units=round(prepared_team.cannibalized_demand_units, 2),
        beginning_finished_goods_inventory=total_beginning_inventory,
        beginning_raw_material_inventory=prepared_team.beginning_raw_material_inventory,
        raw_material_units_received=prepared_team.raw_material_units_received,
        raw_material_units_consumed=prepared_team.actual_total_production_units,
        raw_material_order_qty=max(prepared_team.team_decision.raw_material_order_qty, 0),
        backlog_units_start=total_backlog_start,
        launch_events_text=" | ".join(prepared_team.launch_events),
        notes=" ".join(notes).strip(),
    )


def _update_persistent_team_state(
    market_report: MarketReport,
    prepared_team: PreparedTeamRound,
    team_round_result: RoundResult,
    product_results: list[ProductRoundResult],
) -> PersistentTeamState:
    """Update the persistent firm state after the round."""
    completed_rounds = list(prepared_team.starting_state.completed_rounds)
    if market_report.round_number not in completed_rounds:
        completed_rounds.append(market_report.round_number)

    open_material_orders = list(prepared_team.carryforward_material_orders)
    if prepared_team.placed_material_order is not None:
        open_material_orders.append(prepared_team.placed_material_order)

    next_installed_capacity = max(
        prepared_team.installed_capacity_units
        + max(prepared_team.team_decision.capacity_expansion_units, 0),
        0,
    )

    return PersistentTeamState(
        team_name=prepared_team.team_decision.team_name,
        archetype=prepared_team.team_decision.archetype,
        cash_balance=team_round_result.ending_cash_balance,
        inventory_units=sum(item.ending_inventory for item in product_results),
        raw_material_inventory=prepared_team.raw_material_inventory_end,
        backlog_units=sum(item.backlog_units_end for item in product_results),
        capacity_units=next_installed_capacity,
        reputation_score=team_round_result.reputation_after_round,
        completed_rounds=completed_rounds,
        last_decision={
            "firm_decision": prepared_team.team_decision.to_dict(),
            "product_decisions": [item.decision.to_dict() for item in prepared_team.products],
            "projects": [item.project.to_dict() for item in prepared_team.projects],
        },
        open_material_orders=open_material_orders,
        cumulative_profit=_round_currency(
            prepared_team.starting_state.cumulative_profit + team_round_result.profit
        ),
        short_term_debt_balance=team_round_result.short_term_debt_balance,
        interest_expense_last_round=team_round_result.interest_expense,
        liquidity_warning_flag=team_round_result.liquidity_stress_flag,
        working_capital_stress_score=round(
            (
                team_round_result.working_capital_requirement
                / max(team_round_result.revenue, 1.0)
            )
            * 100.0,
            2,
        ),
    )


def _update_product_lines(
    product_lines: list[ProductLine],
    prepared_products: list[PreparedProductRound],
    market_report: MarketReport,
) -> list[ProductLine]:
    """Update persistent product-line age, lifecycle, inventory, and retirement state."""
    updated_lines: list[ProductLine] = []
    for product in sorted(prepared_products, key=lambda item: item.decision.slot_name):
        product_line = product.product_line
        next_is_active = product.decision.is_active and not product.retired_this_round
        next_age = (
            product_line.age_in_rounds + 1 if next_is_active else product_line.age_in_rounds
        )
        next_lifecycle_stage = (
            _lifecycle_stage_for_age(next_age)
            if next_is_active
            else product_line.lifecycle_stage
        )
        next_inventory = 0 if product.retired_this_round else product.ending_inventory
        next_backlog = 0 if product.retired_this_round else product.backlog_units_end
        updated_lines.append(
            ProductLine(
                product_id=product_line.product_id,
                team_name=product_line.team_name,
                product_name=product.decision.product_name,
                slot_name=product_line.slot_name,
                is_active=next_is_active,
                target_segment=product.decision.target_segment,
                lifecycle_stage=next_lifecycle_stage,
                age_in_rounds=next_age,
                base_defect_rate_modifier=product_line.base_defect_rate_modifier,
                base_demand_fit_modifier=product_line.base_demand_fit_modifier,
                tech_generation=product_line.tech_generation,
                cannibalization_group=product_line.cannibalization_group,
                launch_round=product_line.launch_round,
                retirement_flag=product.retired_this_round,
                retired_round=(
                    market_report.round_number if product.retired_this_round else product_line.retired_round
                ),
                replacement_project_id=product_line.replacement_project_id,
                inventory_units=next_inventory,
                backlog_units=next_backlog,
            )
        )
    return updated_lines


def _update_projects_after_round(
    prepared_projects: list[PreparedProject],
    round_number: int,
) -> list[ProductDevelopmentProject]:
    """Persist next-round project state and clear round-specific toggles."""
    updated_projects: list[ProductDevelopmentProject] = []
    for prepared_project in prepared_projects:
        project = replace(prepared_project.project)
        if project.status == "launched":
            updated_projects.append(
                _empty_project_slot_for_next_round(
                    launched_project=project,
                    next_round=round_number + 1,
                )
            )
            continue

        project.launch_now = False
        project.cancel_now = False
        project.investment_this_round = 0.0
        if project.status == "canceled":
            project.canceled_round = project.canceled_round or round_number
        updated_projects.append(project)
    return updated_projects


def _empty_project_slot_for_next_round(
    launched_project: ProductDevelopmentProject,
    next_round: int,
) -> ProductDevelopmentProject:
    """Return a fresh editable pipeline slot after a project has launched.

    The launched product is now represented by ProductLine, ProductRoundResult, and
    launch-event history. The development slot itself becomes available again so
    students do not keep editing a finished project.
    """
    return ProductDevelopmentProject(
        project_id=launched_project.project_id,
        team_name=launched_project.team_name,
        project_slot_name=launched_project.project_slot_name,
        project_name="",
        target_segment="mid",
        target_tech_generation=2,
        intended_slot_name="C",
        required_investment=0.0,
        cumulative_investment=0.0,
        investment_this_round=0.0,
        testing_intensity=0.0,
        launch_readiness_score=0.0,
        planned_launch_round=next_round + 1,
        earliest_launch_round=next_round + 1,
        status="concept",
        cannibalization_group="",
        projected_base_defect_modifier=0.0,
        projected_demand_fit_modifier=1.0,
        created_round=next_round,
        launched_round=None,
        canceled_round=None,
        launch_now=False,
        cancel_now=False,
        replaced_product_name=None,
    )


def _segment_attractiveness(
    market_report: MarketReport,
    prepared_team: PreparedTeamRound,
    product: PreparedProductRound,
    segment: str,
) -> float:
    """Return one product's attractiveness in a demand segment."""
    reference_price = SEGMENT_REFERENCE_PRICES[segment]
    lifecycle_stage = product.product_line.lifecycle_stage
    tolerance = (
        SEGMENT_PRICE_TOLERANCE[segment]
        * LIFECYCLE_PRICE_TOLERANCE_MULTIPLIERS[lifecycle_stage]
    )
    if segment == "beginner":
        tolerance *= 1.0 + market_report.beginner_price_pressure * 0.30
    if product.tech_gap_to_market > 0:
        tolerance *= 1.0 + min(product.tech_gap_to_market, 2) * TECH_PREMIUM_SEGMENT_BONUS
    price_gap = abs(product.decision.selling_price_per_unit - reference_price)
    price_pressure_penalty = (
        DECLINE_PRICE_PRESSURE_PENALTY if lifecycle_stage == "decline" else 0.0
    )
    price_score = PRICE_ATTRACTIVENESS_WEIGHT * max(
        0.05,
        1.20 - price_gap / max(tolerance, 1.0) - price_pressure_penalty,
    )

    quality_index = max(
        0.30,
        1.0
        + _qc_effect(product.decision.qc_budget_per_unit) * 10.0
        - product.defect_rate * 6.0,
    )
    quality_score = (
        QUALITY_ATTRACTIVENESS_WEIGHT
        * quality_index
        * SEGMENT_QUALITY_MULTIPLIERS[segment]
    )
    archetype_fit_score = (
        prepared_team.archetype.fit_for_segment(segment) * ARCHETYPE_FIT_WEIGHT
    )
    segment_alignment_score = (
        PRODUCT_SEGMENT_ALIGNMENT[product.decision.target_segment][segment]
        * PRODUCT_SEGMENT_ALIGNMENT_WEIGHT
    )
    product_demand_fit_score = (
        product.product_line.base_demand_fit_modifier
        * PRODUCT_DEMAND_FIT_WEIGHT
    )
    reputation_score = (
        prepared_team.starting_state.reputation_score * REPUTATION_ATTRACTIVENESS_WEIGHT
    )
    service_buffer = (
        product.available_units_for_sale
        / max(product.decision.target_finished_goods_inventory, 1)
        if product.decision.target_finished_goods_inventory > 0
        else 1.0
    )
    service_score = SERVICE_READINESS_WEIGHT * min(service_buffer, 1.25)
    lifecycle_multiplier = LIFECYCLE_DEMAND_MULTIPLIERS[lifecycle_stage]
    launch_novelty = LAUNCH_NOVELTY_BONUS if product.launched_this_round else 1.0

    base_score = (
        price_score
        + quality_score
        + archetype_fit_score
        + segment_alignment_score
        + product_demand_fit_score
        + reputation_score
        + service_score
    )
    attractiveness = (
        max(base_score, MIN_ATTRACTIVENESS)
        * lifecycle_multiplier
        * product.tech_attractiveness_adjustment
        * launch_novelty
    )
    return max(attractiveness, MIN_ATTRACTIVENESS)


def _compute_product_defect_rate(
    market_report: MarketReport,
    archetype: TeamArchetype,
    product_line: ProductLine,
    decision: ProductDecision,
    supplier_metrics: SupplierMetrics,
    actual_production_units: int,
    effective_capacity_units: int,
    launched_this_round: bool,
) -> float:
    """Return the product defect rate from process, quality, and technology effects."""
    utilization_ratio = (
        actual_production_units / effective_capacity_units
        if effective_capacity_units > 0
        else 0.0
    )
    utilization_penalty = 0.0
    if utilization_ratio >= UTILIZATION_STRESS_THRESHOLDS["high"]:
        utilization_penalty = UTILIZATION_STRESS_PENALTIES["high"]
    elif utilization_ratio >= UTILIZATION_STRESS_THRESHOLDS["moderate"]:
        utilization_penalty = UTILIZATION_STRESS_PENALTIES["moderate"]

    tech_gap = max(product_line.tech_generation - market_report.current_market_generation, 0)
    defect_rate = (
        archetype.base_defect_rate
        + product_line.base_defect_rate_modifier
        + supplier_metrics.weighted_supplier_defect_pressure
        + (
            supplier_metrics.weighted_supply_risk_exposure
            * (SUPPLY_RISK_INDEX[market_report.supply_risk] - 1.0)
            * 0.018
        )
        + utilization_penalty
        + (
            OVERTIME_DEFECT_PENALTY
            if actual_production_units > effective_capacity_units * 0.9
            and effective_capacity_units > 0
            else 0.0
        )
        + LIFECYCLE_DEFECT_MODIFIERS[product_line.lifecycle_stage]
        + tech_gap * TECH_NEWER_THAN_MARKET_DEFECT_PENALTY
        + (LAUNCH_DEFECT_PENALTY if launched_this_round else 0.0)
        - _qc_effect(decision.qc_budget_per_unit)
    )
    return max(0.005, min(defect_rate, 0.25))


def _technology_attractiveness_modifier(
    market_report: MarketReport,
    target_segment: str,
    tech_generation: int,
) -> float:
    """Return a bounded technology-fit modifier relative to the market."""
    tech_gap = tech_generation - market_report.current_market_generation
    segment_weight = {
        "premium": market_report.premium_tech_adoption,
        "mid": market_report.mid_market_tech_adoption,
        "beginner": max(0.15, 0.35 - market_report.beginner_price_pressure * 0.20),
    }[target_segment]
    obsolescence_multiplier = 1.0 + market_report.technology_shift_rate
    if tech_gap >= 0:
        modifier = 1.0 + min(tech_gap, 2) * TECH_POSITIVE_GAP_BONUS * segment_weight
    else:
        modifier = 1.0 - min(abs(tech_gap), 3) * TECH_NEGATIVE_GAP_PENALTY * segment_weight * obsolescence_multiplier
    return max(
        TECH_MIN_ATTRACTIVENESS_MODIFIER,
        min(modifier, TECH_MAX_ATTRACTIVENESS_MODIFIER),
    )


def estimate_development_project(
    project: ProductDevelopmentProject,
    include_current_round_investment: bool = True,
    current_round: int | None = None,
) -> dict[str, object]:
    """Return transparent planning estimates for a development project.

    The estimates are deterministic teaching aids: ambitious segments, newer
    technology, stronger demand fit, and better defect targets cost more, while
    investment and testing improve readiness over time.
    """
    if not project.is_defined():
        return {}

    required_investment = _required_investment_for_project(project)
    projected_cumulative_investment = max(project.cumulative_investment, 0.0)
    if include_current_round_investment:
        projected_cumulative_investment += max(project.investment_this_round, 0.0)

    projected_project = replace(
        project,
        required_investment=required_investment,
        cumulative_investment=projected_cumulative_investment,
    )
    funding_progress = (
        projected_cumulative_investment / required_investment
        if required_investment > 0
        else 0.0
    )
    projected_readiness = _project_readiness_score(
        projected_project,
        required_investment,
    )
    earliest_launch_round = _minimum_launch_round_for_project(
        projected_project,
        required_investment,
    )
    expected_launch_round = max(
        earliest_launch_round,
        project.planned_launch_round,
        current_round or 1,
    )
    low_estimate = _round_currency(
        required_investment
        * NPD_ESTIMATE_LOW_MULTIPLIER_BY_TECH_GENERATION[
            project.target_tech_generation
        ]
    )
    high_estimate = _round_currency(
        required_investment
        * NPD_ESTIMATE_HIGH_MULTIPLIER_BY_TECH_GENERATION[
            project.target_tech_generation
        ]
    )
    remaining_investment = _round_currency(
        max(required_investment - projected_cumulative_investment, 0.0)
    )
    readiness_gap = round(
        max(LAUNCH_READINESS_THRESHOLD - projected_readiness, 0.0),
        1,
    )
    funding_gate_met = remaining_investment <= 0
    readiness_gate_met = projected_readiness >= LAUNCH_READINESS_THRESHOLD
    timing_gate_met = (
        current_round >= earliest_launch_round
        if current_round is not None
        else None
    )
    launch_gate_met = (
        funding_gate_met
        and readiness_gate_met
        and (timing_gate_met is not False)
    )
    launch_blockers = _launch_blocker_text(
        remaining_investment=remaining_investment,
        readiness_gap=readiness_gap,
        testing_intensity=project.testing_intensity,
        current_round=current_round,
        earliest_launch_round=earliest_launch_round,
    )

    return {
        "required_investment": required_investment,
        "estimated_low_cost": low_estimate,
        "estimated_high_cost": high_estimate,
        "remaining_investment_after_this_round": remaining_investment,
        "funding_progress_pct": round(min(funding_progress, 2.0) * 100.0, 1),
        "projected_readiness_after_this_round": round(projected_readiness, 1),
        "readiness_threshold": LAUNCH_READINESS_THRESHOLD,
        "readiness_gap_points": readiness_gap,
        "testing_adequacy": _testing_adequacy_label(project.testing_intensity),
        "launch_risk": _launch_risk_label(projected_project, projected_readiness),
        "funding_gate_met": funding_gate_met,
        "readiness_gate_met": readiness_gate_met,
        "timing_gate_met": timing_gate_met,
        "launch_gate_met": launch_gate_met,
        "launch_blockers": launch_blockers,
        "minimum_development_rounds": NPD_MIN_DEVELOPMENT_ROUNDS_BY_TECH_GENERATION[
            project.target_tech_generation
        ],
        "estimated_earliest_launch_round": earliest_launch_round,
        "expected_launch_round": expected_launch_round,
        "estimate_note": (
            "Investment improves funding progress; testing improves readiness; "
            "newer technology and stronger performance targets require more money and time."
        ),
    }


def _project_readiness_score(
    project: ProductDevelopmentProject,
    required_investment: float,
) -> float:
    """Return a bounded readiness score based on investment and testing."""
    investment_progress = (
        project.cumulative_investment / required_investment
        if required_investment > 0
        else 0.0
    )
    readiness_from_investment = READINESS_INVESTMENT_SCALE * (
        1.0 - math.exp(-READINESS_INVESTMENT_RATE * investment_progress)
    )
    testing_bonus = min(max(project.testing_intensity, 0.0), 1.0) * READINESS_TESTING_BONUS_MAX
    complexity_penalty = (
        max(project.target_tech_generation - 1, 0)
        * READINESS_COMPLEXITY_PENALTY_PER_TECH
    )
    return max(
        0.0,
        min(
            readiness_from_investment + testing_bonus - complexity_penalty,
            100.0,
        ),
    )


def _minimum_launch_round_for_project(
    project: ProductDevelopmentProject,
    required_investment: float,
) -> int:
    """Return the earliest launch round after tech timing and expedite credit."""
    tech_development_floor = (
        project.created_round
        + NPD_MIN_DEVELOPMENT_ROUNDS_BY_TECH_GENERATION[project.target_tech_generation]
    )
    expedite_credit = _project_expedite_round_credit(project, required_investment)

    return max(
        project.created_round + 1,
        tech_development_floor - expedite_credit,
        project.planned_launch_round - expedite_credit,
        1,
    )


def _project_expedite_round_credit(
    project: ProductDevelopmentProject,
    required_investment: float,
) -> int:
    """Return bounded launch-timing credit from high funding plus high testing."""
    max_credit = NPD_MAX_EXPEDITE_ROUND_REDUCTION_BY_TECH_GENERATION[
        project.target_tech_generation
    ]
    if max_credit <= 0 or required_investment <= 0 or not project.is_defined():
        return 0

    funding_progress = project.cumulative_investment / required_investment
    testing_intensity = min(max(project.testing_intensity, 0.0), 1.0)
    if (
        funding_progress < NPD_EXPEDITE_PROGRESS_THRESHOLD
        or testing_intensity < NPD_EXPEDITE_TESTING_THRESHOLD
    ):
        return 0

    extra_progress = max(funding_progress - NPD_EXPEDITE_PROGRESS_THRESHOLD, 0.0)
    earned_credit = 1 + int(
        extra_progress // NPD_EXPEDITE_EXTRA_PROGRESS_PER_ROUND
    )
    return min(max_credit, earned_credit)


def _required_investment_for_project(project: ProductDevelopmentProject) -> float:
    """Return estimated required investment from project ambition and complexity."""
    segment_multiplier = NPD_SEGMENT_COST_MULTIPLIERS.get(
        project.target_segment,
        NPD_SEGMENT_COST_MULTIPLIERS["mid"],
    )
    tech_multiplier = NPD_TECH_GENERATION_COST_MULTIPLIERS.get(
        project.target_tech_generation,
        NPD_TECH_GENERATION_COST_MULTIPLIERS[2],
    )
    demand_fit_multiplier = 1.0 + max(
        project.projected_demand_fit_modifier - 1.0,
        0.0,
    ) * NPD_DEMAND_FIT_AMBITION_COST_RATE
    defect_improvement_multiplier = 1.0 + max(
        -project.projected_base_defect_modifier,
        0.0,
    ) * NPD_DEFECT_IMPROVEMENT_COST_RATE

    return _round_currency(
        NPD_REQUIRED_INVESTMENT_BASE
        * segment_multiplier
        * tech_multiplier
        * demand_fit_multiplier
        * defect_improvement_multiplier
    )


def _launch_blocker_text(
    remaining_investment: float,
    readiness_gap: float,
    testing_intensity: float,
    current_round: int | None,
    earliest_launch_round: int,
) -> str:
    """Explain what prevents launch in plain language."""
    blockers: list[str] = []
    if remaining_investment > 0:
        blockers.append(f"Needs ${remaining_investment:,.0f} more investment")
    if readiness_gap > 0:
        if testing_intensity < NPD_TESTING_ADEQUACY_LOW_THRESHOLD:
            blockers.append(
                f"Readiness is {readiness_gap:.1f} points short; testing is low"
            )
        elif testing_intensity < NPD_TESTING_ADEQUACY_GOOD_THRESHOLD:
            blockers.append(
                f"Readiness is {readiness_gap:.1f} points short; more testing helps"
            )
        else:
            blockers.append(
                f"Readiness is {readiness_gap:.1f} points short; add investment or keep testing"
            )
    if current_round is not None and current_round < earliest_launch_round:
        blockers.append(f"Cannot launch before round {earliest_launch_round}")
    if not blockers:
        return "All launch gates are met. Check Launch Now If Ready to launch this round."
    return "; ".join(blockers) + "."


def _testing_adequacy_label(testing_intensity: float) -> str:
    """Return a student-friendly label for the current testing intensity."""
    bounded_testing = min(max(testing_intensity, 0.0), 1.0)
    if bounded_testing >= NPD_TESTING_ADEQUACY_GOOD_THRESHOLD:
        return "Good"
    if bounded_testing >= NPD_TESTING_ADEQUACY_LOW_THRESHOLD:
        return "Moderate"
    return "Low"


def _launch_risk_label(
    project: ProductDevelopmentProject,
    readiness_score: float,
) -> str:
    """Return a simple launch-risk label from readiness, testing, and tech complexity."""
    testing_label = _testing_adequacy_label(project.testing_intensity)
    if (
        readiness_score >= LAUNCH_READINESS_THRESHOLD
        and testing_label == "Good"
        and project.target_tech_generation <= 3
    ):
        return "Low"
    if readiness_score >= LAUNCH_READINESS_THRESHOLD and testing_label != "Low":
        return "Moderate"
    if readiness_score >= 60.0 or testing_label == "Good":
        return "Elevated"
    return "High"


def _conversion_cost_per_unit(
    archetype: TeamArchetype,
    market_report: MarketReport,
    actual_production_units: int,
    overtime_capacity_units: int,
) -> float:
    """Return per-unit conversion cost excluding material input cost."""
    base_conversion_cost = (
        archetype.base_cost * BASE_CONVERSION_COST_SHARE * market_report.material_cost_index
    )
    overtime_ratio = (
        min(actual_production_units, overtime_capacity_units) / actual_production_units
        if actual_production_units > 0 and overtime_capacity_units > 0
        else 0.0
    )
    return _round_currency(
        base_conversion_cost
        * (1.0 + overtime_ratio * (OVERTIME_COST_MULTIPLIER - 1.0))
    )


def _allocate_backlog_across_products(
    products: list[PreparedProductRound],
    max_team_backorder_units: int,
) -> dict[str, int]:
    """Allocate the team backorder cap across products proportionally to unmet demand."""
    unmet_by_slot = {
        item.decision.slot_name: max(int(math.floor(item.unmet_units)), 0)
        for item in products
        if item.unmet_units > 0
    }
    return _allocate_integer_proportionally(unmet_by_slot, max_team_backorder_units)


def _build_material_order(
    market_report: MarketReport,
    team_decision: TeamDecision,
    supplier_metrics: SupplierMetrics,
) -> OpenMaterialOrder | None:
    """Create a future raw-material order for the current round."""
    quantity = max(team_decision.raw_material_order_qty, 0)
    if quantity <= 0:
        return None

    lead_time_rounds = max(int(round(supplier_metrics.weighted_lead_time)), 1)
    return OpenMaterialOrder(
        quantity=quantity,
        arrival_round=market_report.round_number + lead_time_rounds,
        placed_round=market_report.round_number,
        weighted_material_unit_cost=supplier_metrics.weighted_material_unit_cost,
        weighted_lead_time=supplier_metrics.weighted_lead_time,
    )


def _split_open_material_orders(
    round_number: int,
    open_orders: list[OpenMaterialOrder],
) -> tuple[list[OpenMaterialOrder], list[OpenMaterialOrder]]:
    """Split inbound raw-material orders into arriving-now versus future orders."""
    inbound_orders: list[OpenMaterialOrder] = []
    carryforward_orders: list[OpenMaterialOrder] = []
    for order in open_orders:
        if order.arrival_round <= round_number:
            inbound_orders.append(order)
        else:
            carryforward_orders.append(order)
    return inbound_orders, carryforward_orders


def _normalized_supplier_mix(team_decision: TeamDecision) -> dict[str, float]:
    """Return normalized supplier shares using canonical supplier labels."""
    raw_total = max(team_decision.supplier_mix_total(), 0.0)
    if raw_total <= 0:
        return {
            "Offshore Value": 0.0,
            "Balanced Source": 1.0,
            "Premium Reliable": 0.0,
        }

    return {
        "Offshore Value": team_decision.supplier_mix_offshore_pct / raw_total,
        "Balanced Source": team_decision.supplier_mix_balanced_pct / raw_total,
        "Premium Reliable": team_decision.supplier_mix_premium_pct / raw_total,
    }


def _lifecycle_stage_for_age(age_in_rounds: int) -> str:
    """Resolve the lifecycle stage from age thresholds."""
    for stage_name, (min_age, max_age) in LIFECYCLE_AGE_THRESHOLDS.items():
        if age_in_rounds < min_age:
            continue
        if max_age is None or age_in_rounds <= max_age:
            return stage_name
    return "decline"


def _group_product_lines(product_lines: list[ProductLine]) -> dict[str, list[ProductLine]]:
    """Group product lines by team."""
    grouped: dict[str, list[ProductLine]] = {}
    for item in product_lines:
        grouped.setdefault(item.team_name.lower(), []).append(item)
    return grouped


def _group_product_decisions(
    product_decisions: list[ProductDecision],
) -> dict[str, list[ProductDecision]]:
    """Group product decisions by team."""
    grouped: dict[str, list[ProductDecision]] = {}
    for item in product_decisions:
        grouped.setdefault(item.team_name.lower(), []).append(item)
    return grouped


def _group_projects(
    projects: list[ProductDevelopmentProject],
) -> dict[str, list[ProductDevelopmentProject]]:
    """Group development projects by team."""
    grouped: dict[str, list[ProductDevelopmentProject]] = {}
    for item in projects:
        grouped.setdefault(item.team_name.lower(), []).append(item)
    return grouped


def _allocate_integer_proportionally(
    requested_units_by_key: dict[str, int],
    capped_total_units: int,
) -> dict[str, int]:
    """Allocate a capped total proportionally using largest-remainder rounding."""
    positive_requests = {
        key: max(value, 0)
        for key, value in requested_units_by_key.items()
        if value > 0
    }
    if not positive_requests or capped_total_units <= 0:
        return {key: 0 for key in requested_units_by_key}

    requested_total = sum(positive_requests.values())
    if capped_total_units >= requested_total:
        return {
            key: positive_requests.get(key, 0)
            for key in requested_units_by_key
        }

    raw_allocations = {
        key: capped_total_units * (value / requested_total)
        for key, value in positive_requests.items()
    }
    allocated_units = {
        key: int(math.floor(value)) for key, value in raw_allocations.items()
    }
    remaining_units = capped_total_units - sum(allocated_units.values())
    ranked_remainders = sorted(
        raw_allocations.items(),
        key=lambda item: (item[1] - math.floor(item[1]), positive_requests[item[0]], item[0]),
        reverse=True,
    )
    for key, _ in ranked_remainders[:remaining_units]:
        allocated_units[key] += 1

    return {
        key: allocated_units.get(key, 0)
        for key in requested_units_by_key
    }


def _allocation_share_map(weights_by_key: dict[str, float]) -> dict[str, float]:
    """Return normalized shares from a positive-weight mapping."""
    positive_weights = {
        key: max(value, 0.0)
        for key, value in weights_by_key.items()
        if value > 0
    }
    total = sum(positive_weights.values())
    if total <= 0:
        return {key: 0.0 for key in weights_by_key}
    return {key: positive_weights.get(key, 0.0) / total for key in weights_by_key}


def _qc_effect(qc_budget_per_unit: float) -> float:
    """Return the defect-rate reduction from QC spend with diminishing returns."""
    qc_budget = max(qc_budget_per_unit, 0.0)
    return QC_MAX_DEFECT_REDUCTION * (1.0 - math.exp(-QC_EFFECTIVENESS_RATE * qc_budget))


def _update_reputation(
    current_reputation: float,
    defect_rate: float,
    fill_rate: float,
    lost_sales_units: int,
    backlog_units_end: int,
    demand_allocated: float,
    quality_sensitivity: float,
) -> float:
    """Update next-round reputation based on quality and service performance."""
    demand_base = demand_allocated if demand_allocated > 0 else 1.0
    quality_multiplier = 1.0 + (
        quality_sensitivity
        * REPUTATION_UPDATE_WEIGHTS["quality_sensitivity_multiplier"]
    )

    defect_component = (
        REPUTATION_UPDATE_WEIGHTS["defect_target"] - defect_rate
    ) * REPUTATION_UPDATE_WEIGHTS["defect_weight"] * quality_multiplier
    fill_component = (
        fill_rate - REPUTATION_UPDATE_WEIGHTS["fill_rate_baseline"]
    ) * REPUTATION_UPDATE_WEIGHTS["fill_rate_weight"]
    lost_sales_component = (
        (lost_sales_units / demand_base)
        * REPUTATION_UPDATE_WEIGHTS["lost_sales_weight"]
        * quality_multiplier
    )
    backlog_component = (
        (backlog_units_end / demand_base)
        * REPUTATION_UPDATE_WEIGHTS["backlog_weight"]
    )

    updated_reputation = (
        current_reputation
        + defect_component
        + fill_component
        - lost_sales_component
        - backlog_component
    )
    return max(0.0, min(updated_reputation, 100.0))


def _supplier_mix_label(team_decision: TeamDecision) -> str:
    """Build a readable supplier mix label for preview UI."""
    return (
        f"Offshore {team_decision.supplier_mix_offshore_pct:.0f}% / "
        f"Balanced {team_decision.supplier_mix_balanced_pct:.0f}% / "
        f"Premium {team_decision.supplier_mix_premium_pct:.0f}%"
    )


def _segment_mix_summary(product_decisions: list[ProductDecision]) -> str:
    """Return a readable planned portfolio mix by segment."""
    segment_units = {segment: 0 for segment in SEGMENTS}
    for item in product_decisions:
        if not item.is_active:
            continue
        segment_units[item.target_segment] += max(item.planned_production_units, 0)

    total_units = sum(segment_units.values()) or 1
    return (
        f"Premium {segment_units['premium'] / total_units:.0%} | "
        f"Mid {segment_units['mid'] / total_units:.0%} | "
        f"Beginner {segment_units['beginner'] / total_units:.0%}"
    )


def _safe_pct(numerator: float, denominator: float) -> float:
    """Return a percentage ratio safely."""
    if denominator <= 0:
        return 0.0
    return 100.0 * numerator / denominator


def _round_currency(value: float) -> float:
    """Round a numeric value to currency-style precision."""
    return round(value, 2)
