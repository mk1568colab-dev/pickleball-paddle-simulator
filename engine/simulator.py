"""Core OM round engine for the classroom simulator."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from engine.config import (
    CAPACITY_PLAN_MULTIPLIERS,
    CAPACITY_STRESS_ADJUSTMENTS,
    EXPANSION_COSTS,
    FUTURE_CAPACITY_GAINS,
    HOLDING_COST_PER_UNIT,
    INVENTORY_POSTURE_MODIFIERS,
    MIN_ATTRACTIVENESS,
    PRICE_MAP,
    PRICE_SEGMENT_SCORES,
    QUALITY_COST_MULTIPLIERS,
    QUALITY_DEFECT_ADJUSTMENTS,
    QUALITY_SEGMENT_SCORES,
    REPUTATION_ATTRACTIVENESS_WEIGHT,
    REPUTATION_UPDATE_WEIGHTS,
    SEGMENT_FIT_WEIGHT,
    SUPPLY_RISK_DEFECT_ADJUSTMENTS,
    WARRANTY_COST_FACTOR,
)
from models.schemas import (
    MarketReport,
    PersistentTeamState,
    RoundResult,
    TeamArchetype,
    TeamDecision,
)
from utils.repository import load_team_archetypes


SEGMENTS = ("premium", "mid", "beginner")


@dataclass
class PreparedTeamRound:
    """Internal representation of a team's round inputs and derived OM values."""

    decision: TeamDecision
    archetype: TeamArchetype
    starting_state: PersistentTeamState
    available_capacity: int
    next_capacity: int
    expansion_cost: float
    effective_production: int
    defect_rate: float
    good_units_produced: int
    units_available_for_sale: int
    unit_cost: float
    notes: list[str] = field(default_factory=list)


def run_round(
    market_report: MarketReport,
    team_decisions: list[TeamDecision],
    existing_states: list[PersistentTeamState],
) -> tuple[list[RoundResult], list[PersistentTeamState]]:
    """Run one OM round and return the round results with updated team states."""
    archetype_lookup = {
        archetype.name: archetype for archetype in load_team_archetypes()
    }
    existing_state_lookup = {
        state.team_name.lower(): state for state in existing_states
    }

    prepared_teams: list[PreparedTeamRound] = []
    for decision in team_decisions:
        archetype = _resolve_archetype(decision, archetype_lookup)
        starting_state = _initialize_team_state(
            existing_state_lookup.get(decision.team_name.lower()),
            decision,
            archetype,
        )
        prepared_teams.append(
            _prepare_team_round(
                market_report=market_report,
                decision=decision,
                archetype=archetype,
                state=starting_state,
            )
        )

    demand_allocations = _allocate_demand(market_report, prepared_teams)

    results: list[RoundResult] = []
    updated_state_lookup = dict(existing_state_lookup)

    for prepared in prepared_teams:
        demand_allocated = demand_allocations.get(prepared.decision.team_name.lower(), 0.0)
        result = _finalize_round_result(
            market_report=market_report,
            prepared=prepared,
            demand_allocated=demand_allocated,
        )
        updated_state = _update_persistent_state(
            market_report=market_report,
            prepared=prepared,
            result=result,
        )
        results.append(result)
        updated_state_lookup[updated_state.team_name.lower()] = updated_state

    updated_states = sorted(
        updated_state_lookup.values(),
        key=lambda item: item.team_name.lower(),
    )
    return results, updated_states


def _resolve_archetype(
    decision: TeamDecision,
    archetype_lookup: dict[str, TeamArchetype],
) -> TeamArchetype:
    """Resolve a decision's archetype to a configured OM profile."""
    archetype = archetype_lookup.get(decision.archetype)
    if archetype is None:
        raise ValueError(f"Unknown archetype: {decision.archetype}")
    return archetype


def _initialize_team_state(
    existing_state: PersistentTeamState | None,
    decision: TeamDecision,
    archetype: TeamArchetype,
) -> PersistentTeamState:
    """Build the starting state for a team before the round is processed."""
    if existing_state is None:
        return PersistentTeamState(
            team_name=decision.team_name,
            archetype=decision.archetype,
            cash_balance=0.0,
            inventory_units=0,
            capacity_units=archetype.base_capacity,
            reputation_score=archetype.base_reputation,
            completed_rounds=[],
            last_decision={},
            cumulative_profit=0.0,
        )

    return PersistentTeamState(
        team_name=decision.team_name,
        archetype=decision.archetype,
        cash_balance=existing_state.cash_balance,
        inventory_units=max(existing_state.inventory_units, 0),
        capacity_units=(
            existing_state.capacity_units
            if existing_state.capacity_units > 0
            else archetype.base_capacity
        ),
        reputation_score=existing_state.reputation_score,
        completed_rounds=list(existing_state.completed_rounds),
        last_decision=dict(existing_state.last_decision),
        cumulative_profit=existing_state.cumulative_profit,
    )


def _prepare_team_round(
    market_report: MarketReport,
    decision: TeamDecision,
    archetype: TeamArchetype,
    state: PersistentTeamState,
) -> PreparedTeamRound:
    """Calculate pre-demand operating values for a team."""
    notes: list[str] = []
    current_capacity = state.capacity_units if state.capacity_units > 0 else archetype.base_capacity
    available_capacity, next_capacity, expansion_cost = _apply_capacity_plan(
        current_capacity,
        decision.capacity_plan,
    )

    requested_production = max(decision.production_quantity, 0)
    effective_production = min(requested_production, available_capacity)
    if requested_production > available_capacity:
        notes.append(
            f"Production capped from {requested_production} to {available_capacity} units."
        )

    utilization = (
        effective_production / available_capacity if available_capacity > 0 else 0.0
    )
    defect_rate = _calculate_defect_rate(
        archetype=archetype,
        decision=decision,
        market_report=market_report,
        utilization=utilization,
    )
    good_units_produced = int(
        math.floor(effective_production * max(1.0 - defect_rate, 0.0))
    )
    inventory_units = max(state.inventory_units, 0)
    units_available_for_sale = inventory_units + good_units_produced
    unit_cost = _round_currency(
        archetype.base_cost
        * QUALITY_COST_MULTIPLIERS.get(decision.quality_level, 1.0)
        * market_report.material_cost_index
    )

    return PreparedTeamRound(
        decision=decision,
        archetype=archetype,
        starting_state=state,
        available_capacity=available_capacity,
        next_capacity=next_capacity,
        expansion_cost=expansion_cost,
        effective_production=effective_production,
        defect_rate=defect_rate,
        good_units_produced=good_units_produced,
        units_available_for_sale=units_available_for_sale,
        unit_cost=unit_cost,
        notes=notes,
    )


def _apply_capacity_plan(current_capacity: int, capacity_plan: str) -> tuple[int, int, float]:
    """Apply the chosen capacity plan for current and future capacity."""
    multiplier = CAPACITY_PLAN_MULTIPLIERS.get(capacity_plan, 1.0)
    expansion_cost = EXPANSION_COSTS.get(capacity_plan, 0.0)
    future_gain = FUTURE_CAPACITY_GAINS.get(capacity_plan, 0)

    available_capacity = max(int(math.floor(current_capacity * multiplier)), 1)
    next_capacity = max(current_capacity + future_gain, 1)
    return available_capacity, next_capacity, expansion_cost


def _calculate_defect_rate(
    archetype: TeamArchetype,
    decision: TeamDecision,
    market_report: MarketReport,
    utilization: float,
) -> float:
    """Calculate the realized defect rate using quality, supply, and stress effects."""
    defect_rate = archetype.base_defect_rate
    defect_rate += QUALITY_DEFECT_ADJUSTMENTS.get(decision.quality_level, 0.0)
    defect_rate += SUPPLY_RISK_DEFECT_ADJUSTMENTS.get(
        market_report.supply_risk,
        SUPPLY_RISK_DEFECT_ADJUSTMENTS["Moderate"],
    )

    if utilization >= CAPACITY_STRESS_ADJUSTMENTS["high_threshold"]:
        defect_rate += CAPACITY_STRESS_ADJUSTMENTS["high_increase"]
    elif utilization >= CAPACITY_STRESS_ADJUSTMENTS["moderate_threshold"]:
        defect_rate += CAPACITY_STRESS_ADJUSTMENTS["moderate_increase"]

    return max(0.005, min(defect_rate, 0.25))


def _allocate_demand(
    market_report: MarketReport,
    prepared_teams: list[PreparedTeamRound],
) -> dict[str, float]:
    """Allocate shared market demand across teams by segment attractiveness."""
    if not prepared_teams:
        return {}

    demand_by_team = {
        prepared.decision.team_name.lower(): 0.0 for prepared in prepared_teams
    }
    normalized_shares = market_report.normalized_shares()

    for segment in SEGMENTS:
        segment_demand = market_report.total_demand * normalized_shares[segment]
        attractiveness_by_team = {
            prepared.decision.team_name.lower(): _segment_attractiveness(
                prepared,
                segment,
            )
            for prepared in prepared_teams
        }
        total_attractiveness = sum(attractiveness_by_team.values())
        if total_attractiveness <= 0:
            even_allocation = segment_demand / len(prepared_teams)
            for team_key in demand_by_team:
                demand_by_team[team_key] += even_allocation
            continue

        for team_key, attractiveness in attractiveness_by_team.items():
            demand_by_team[team_key] += segment_demand * (
                attractiveness / total_attractiveness
            )

    return demand_by_team


def _segment_attractiveness(prepared: PreparedTeamRound, segment: str) -> float:
    """Score how attractive one team is to a specific demand segment."""
    price_score = PRICE_SEGMENT_SCORES.get(prepared.decision.price_level, {}).get(
        segment,
        0.0,
    )
    quality_score = QUALITY_SEGMENT_SCORES.get(prepared.decision.quality_level, {}).get(
        segment,
        0.0,
    )
    fit_score = prepared.archetype.fit_for_segment(segment) * SEGMENT_FIT_WEIGHT
    reputation_score = (
        prepared.starting_state.reputation_score * REPUTATION_ATTRACTIVENESS_WEIGHT
    )
    inventory_modifier = INVENTORY_POSTURE_MODIFIERS.get(
        prepared.decision.inventory_posture,
        0.0,
    )

    return max(
        price_score + quality_score + fit_score + reputation_score + inventory_modifier,
        MIN_ATTRACTIVENESS,
    )


def _finalize_round_result(
    market_report: MarketReport,
    prepared: PreparedTeamRound,
    demand_allocated: float,
) -> RoundResult:
    """Convert pre-demand metrics and demand allocation into a final round result."""
    realized_demand_units = int(math.floor(max(demand_allocated, 0.0) + 0.5))
    sales_units = min(realized_demand_units, prepared.units_available_for_sale)
    stockout_units = max(realized_demand_units - sales_units, 0)
    ending_inventory = max(prepared.units_available_for_sale - sales_units, 0)
    fill_rate = (
        min(sales_units / demand_allocated, 1.0) if demand_allocated > 0 else 1.0
    )

    unit_price = PRICE_MAP.get(prepared.decision.price_level, PRICE_MAP["Mid"])
    revenue = sales_units * unit_price
    production_cost = prepared.effective_production * prepared.unit_cost
    holding_cost = ending_inventory * HOLDING_COST_PER_UNIT
    warranty_cost = sales_units * prepared.defect_rate * WARRANTY_COST_FACTOR
    total_cost = (
        production_cost
        + holding_cost
        + warranty_cost
        + prepared.expansion_cost
    )
    profit = revenue - total_cost
    reputation_after_round = _update_reputation(
        current_reputation=prepared.starting_state.reputation_score,
        defect_rate=prepared.defect_rate,
        fill_rate=fill_rate,
        stockout_units=stockout_units,
        demand_allocated=demand_allocated,
        quality_sensitivity=market_report.quality_sensitivity,
    )

    notes = list(prepared.notes)
    if stockout_units > 0:
        notes.append(f"Stockout of {stockout_units} units against allocated demand.")
    if prepared.expansion_cost > 0:
        notes.append(
            f"Capacity plan {prepared.decision.capacity_plan} adds future capacity."
        )

    return RoundResult(
        round_number=market_report.round_number,
        team_name=prepared.decision.team_name,
        archetype=prepared.decision.archetype,
        demand_allocated=round(demand_allocated, 2),
        sales_units=sales_units,
        stockout_units=stockout_units,
        ending_inventory=ending_inventory,
        fill_rate=round(fill_rate, 4),
        unit_price=unit_price,
        revenue=_round_currency(revenue),
        production_cost=_round_currency(production_cost),
        holding_cost=_round_currency(holding_cost),
        warranty_cost=_round_currency(warranty_cost),
        expansion_cost=_round_currency(prepared.expansion_cost),
        total_cost=_round_currency(total_cost),
        profit=_round_currency(profit),
        defect_rate=round(prepared.defect_rate, 4),
        available_capacity=prepared.available_capacity,
        good_units_produced=prepared.good_units_produced,
        reputation_after_round=round(reputation_after_round, 2),
        notes=" ".join(notes).strip(),
    )


def _update_reputation(
    current_reputation: float,
    defect_rate: float,
    fill_rate: float,
    stockout_units: int,
    demand_allocated: float,
    quality_sensitivity: float,
) -> float:
    """Update next-round reputation based on quality and service performance."""
    quality_multiplier = 1.0 + (
        quality_sensitivity
        * REPUTATION_UPDATE_WEIGHTS["quality_sensitivity_multiplier"]
    )
    stockout_ratio = stockout_units / demand_allocated if demand_allocated > 0 else 0.0

    defect_component = (
        REPUTATION_UPDATE_WEIGHTS["defect_target"] - defect_rate
    ) * REPUTATION_UPDATE_WEIGHTS["defect_weight"] * quality_multiplier
    fill_component = (
        fill_rate - REPUTATION_UPDATE_WEIGHTS["fill_rate_baseline"]
    ) * REPUTATION_UPDATE_WEIGHTS["fill_rate_weight"]
    stockout_component = (
        stockout_ratio
        * REPUTATION_UPDATE_WEIGHTS["stockout_weight"]
        * quality_multiplier
    )

    updated_reputation = current_reputation + defect_component + fill_component - stockout_component
    return max(0.0, min(updated_reputation, 100.0))


def _update_persistent_state(
    market_report: MarketReport,
    prepared: PreparedTeamRound,
    result: RoundResult,
) -> PersistentTeamState:
    """Apply the round results back into persistent team state."""
    completed_rounds = list(prepared.starting_state.completed_rounds)
    if market_report.round_number not in completed_rounds:
        completed_rounds.append(market_report.round_number)

    return PersistentTeamState(
        team_name=prepared.decision.team_name,
        archetype=prepared.decision.archetype,
        cash_balance=_round_currency(
            prepared.starting_state.cash_balance + result.profit
        ),
        inventory_units=result.ending_inventory,
        capacity_units=prepared.next_capacity,
        reputation_score=result.reputation_after_round,
        completed_rounds=completed_rounds,
        last_decision=prepared.decision.to_dict(),
        cumulative_profit=_round_currency(
            prepared.starting_state.cumulative_profit + result.profit
        ),
    )


def _round_currency(value: float) -> float:
    """Round a numeric value to currency-style precision."""
    return round(value, 2)
