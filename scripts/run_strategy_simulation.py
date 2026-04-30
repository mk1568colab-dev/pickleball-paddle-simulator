"""Run deterministic strategy scenarios against the real simulator engine.

This tool is intentionally separate from the Streamlit app. It lets an instructor
or researcher test "what if" team strategies without touching classroom SQLite
state or hosted app data.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import engine.simulator as simulator
from data.defaults import DEFAULT_MARKET_REPORT, DEFAULT_TEAM_ARCHETYPES
from engine.config import SEGMENT_REFERENCE_PRICES
from models.schemas import (
    MarketReport,
    PersistentTeamState,
    ProductDecision,
    ProductDevelopmentProject,
    ProductLine,
    RoundResult,
    TeamArchetype,
    TeamDecision,
    build_product_id,
    build_project_id,
)


STRATEGY_PRESETS: dict[str, dict[str, Any]] = {
    "premium_quality": {
        "label": "Premium quality",
        "price_multiplier": 1.08,
        "production_multiplier": 0.92,
        "forecast_multiplier": 0.98,
        "qc_delta": 2.2,
        "target_inventory_multiplier": 0.85,
        "overtime_pct_of_capacity": 0.04,
        "capacity_expansion_pct_of_capacity": 0.05,
        "raw_material_multiplier": 1.00,
        "supplier_mix": (0.0, 30.0, 70.0),
        "expedited_share_pct": 25.0,
        "max_backorder_pct_of_forecast": 0.08,
        "planned_borrowing": 0.0,
        "npd_investment": 3_000.0,
        "testing_intensity": 0.45,
    },
    "low_cost_volume": {
        "label": "Low-cost volume",
        "price_multiplier": 0.88,
        "production_multiplier": 1.22,
        "forecast_multiplier": 1.08,
        "qc_delta": -0.8,
        "target_inventory_multiplier": 1.25,
        "overtime_pct_of_capacity": 0.12,
        "capacity_expansion_pct_of_capacity": 0.09,
        "raw_material_multiplier": 1.24,
        "supplier_mix": (70.0, 25.0, 5.0),
        "expedited_share_pct": 5.0,
        "max_backorder_pct_of_forecast": 0.20,
        "planned_borrowing": 3_500.0,
        "npd_investment": 1_500.0,
        "testing_intensity": 0.20,
    },
    "balanced_sop": {
        "label": "Balanced S&OP",
        "price_multiplier": 1.00,
        "production_multiplier": 1.00,
        "forecast_multiplier": 1.00,
        "qc_delta": 0.8,
        "target_inventory_multiplier": 1.00,
        "overtime_pct_of_capacity": 0.06,
        "capacity_expansion_pct_of_capacity": 0.04,
        "raw_material_multiplier": 1.08,
        "supplier_mix": (20.0, 60.0, 20.0),
        "expedited_share_pct": 12.0,
        "max_backorder_pct_of_forecast": 0.12,
        "planned_borrowing": 1_000.0,
        "npd_investment": 2_500.0,
        "testing_intensity": 0.35,
    },
    "innovation_leap": {
        "label": "Innovation leap",
        "price_multiplier": 1.05,
        "production_multiplier": 0.88,
        "forecast_multiplier": 1.02,
        "qc_delta": 1.5,
        "target_inventory_multiplier": 0.95,
        "overtime_pct_of_capacity": 0.05,
        "capacity_expansion_pct_of_capacity": 0.03,
        "raw_material_multiplier": 0.95,
        "supplier_mix": (10.0, 45.0, 45.0),
        "expedited_share_pct": 18.0,
        "max_backorder_pct_of_forecast": 0.10,
        "planned_borrowing": 7_000.0,
        "npd_investment": 9_000.0,
        "testing_intensity": 0.75,
    },
    "cash_conservative": {
        "label": "Cash conservative",
        "price_multiplier": 1.02,
        "production_multiplier": 0.82,
        "forecast_multiplier": 0.92,
        "qc_delta": 0.4,
        "target_inventory_multiplier": 0.70,
        "overtime_pct_of_capacity": 0.01,
        "capacity_expansion_pct_of_capacity": 0.00,
        "raw_material_multiplier": 0.82,
        "supplier_mix": (10.0, 75.0, 15.0),
        "expedited_share_pct": 5.0,
        "max_backorder_pct_of_forecast": 0.06,
        "planned_borrowing": 0.0,
        "npd_investment": 750.0,
        "testing_intensity": 0.15,
    },
    "aggressive_growth": {
        "label": "Aggressive growth",
        "price_multiplier": 0.96,
        "production_multiplier": 1.18,
        "forecast_multiplier": 1.18,
        "qc_delta": 0.2,
        "target_inventory_multiplier": 1.15,
        "overtime_pct_of_capacity": 0.15,
        "capacity_expansion_pct_of_capacity": 0.12,
        "raw_material_multiplier": 1.30,
        "supplier_mix": (35.0, 50.0, 15.0),
        "expedited_share_pct": 20.0,
        "max_backorder_pct_of_forecast": 0.18,
        "planned_borrowing": 10_000.0,
        "npd_investment": 4_000.0,
        "testing_intensity": 0.40,
    },
}

DEFAULT_STRATEGY_ROTATION = tuple(STRATEGY_PRESETS)

MARKET_SCENARIO_PRESETS: dict[str, dict[str, Any]] = {
    "baseline": {
        "label": "Baseline market",
        "demand_multiplier": 1.00,
        "demand_growth_delta": 0.00,
        "premium_share_shift": 0.00,
        "mid_share_shift": 0.00,
        "beginner_share_shift": 0.00,
        "material_cost_index_delta": 0.00,
        "supply_risk_override": None,
        "quality_sensitivity_delta": 0.00,
        "technology_shift_delta": 0.00,
        "market_generation_offset": 0,
        "premium_tech_adoption_delta": 0.00,
        "mid_tech_adoption_delta": 0.00,
        "beginner_price_pressure_delta": 0.00,
    },
    "demand_boom": {
        "label": "Demand boom",
        "demand_multiplier": 1.45,
        "demand_growth_delta": 0.08,
        "premium_share_shift": -0.02,
        "mid_share_shift": 0.03,
        "beginner_share_shift": -0.01,
        "material_cost_index_delta": 0.02,
        "supply_risk_override": None,
        "quality_sensitivity_delta": 0.02,
        "technology_shift_delta": 0.02,
        "market_generation_offset": 0,
        "premium_tech_adoption_delta": 0.03,
        "mid_tech_adoption_delta": 0.02,
        "beginner_price_pressure_delta": -0.05,
    },
    "volume_surge": {
        "label": "Volume surge",
        "demand_multiplier": 1.65,
        "demand_growth_delta": 0.10,
        "premium_share_shift": -0.08,
        "mid_share_shift": 0.03,
        "beginner_share_shift": 0.05,
        "material_cost_index_delta": 0.00,
        "supply_risk_override": "Moderate",
        "quality_sensitivity_delta": -0.12,
        "technology_shift_delta": -0.02,
        "market_generation_offset": 0,
        "premium_tech_adoption_delta": -0.10,
        "mid_tech_adoption_delta": -0.04,
        "beginner_price_pressure_delta": 0.18,
    },
    "supply_shock": {
        "label": "Supply shock",
        "demand_multiplier": 0.98,
        "demand_growth_delta": -0.01,
        "premium_share_shift": 0.00,
        "mid_share_shift": -0.02,
        "beginner_share_shift": 0.02,
        "material_cost_index_delta": 0.18,
        "supply_risk_override": "High",
        "quality_sensitivity_delta": 0.08,
        "technology_shift_delta": 0.01,
        "market_generation_offset": 0,
        "premium_tech_adoption_delta": 0.00,
        "mid_tech_adoption_delta": 0.00,
        "beginner_price_pressure_delta": 0.08,
    },
    "tech_shift": {
        "label": "Fast tech shift",
        "demand_multiplier": 1.08,
        "demand_growth_delta": 0.03,
        "premium_share_shift": 0.08,
        "mid_share_shift": 0.03,
        "beginner_share_shift": -0.11,
        "material_cost_index_delta": 0.04,
        "supply_risk_override": None,
        "quality_sensitivity_delta": 0.06,
        "technology_shift_delta": 0.32,
        "market_generation_offset": 1,
        "premium_tech_adoption_delta": 0.22,
        "mid_tech_adoption_delta": 0.18,
        "beginner_price_pressure_delta": 0.00,
    },
    "price_recession": {
        "label": "Price-pressure recession",
        "demand_multiplier": 0.70,
        "demand_growth_delta": -0.06,
        "premium_share_shift": -0.12,
        "mid_share_shift": -0.03,
        "beginner_share_shift": 0.15,
        "material_cost_index_delta": 0.01,
        "supply_risk_override": "Moderate",
        "quality_sensitivity_delta": -0.06,
        "technology_shift_delta": -0.03,
        "market_generation_offset": 0,
        "premium_tech_adoption_delta": -0.08,
        "mid_tech_adoption_delta": -0.04,
        "beginner_price_pressure_delta": 0.32,
    },
    "quality_sensitive": {
        "label": "Quality-sensitive market",
        "demand_multiplier": 0.96,
        "demand_growth_delta": 0.01,
        "premium_share_shift": 0.06,
        "mid_share_shift": 0.02,
        "beginner_share_shift": -0.08,
        "material_cost_index_delta": 0.03,
        "supply_risk_override": None,
        "quality_sensitivity_delta": 0.26,
        "technology_shift_delta": 0.05,
        "market_generation_offset": 0,
        "premium_tech_adoption_delta": 0.09,
        "mid_tech_adoption_delta": 0.05,
        "beginner_price_pressure_delta": -0.04,
    },
}


def main() -> None:
    """Parse CLI arguments and run the requested strategy scenario."""
    parser = argparse.ArgumentParser(
        description="Run deterministic multi-team strategy simulations.",
    )
    parser.add_argument("--teams", type=int, default=6, help="Number of teams to simulate.")
    parser.add_argument("--rounds", type=int, default=4, help="Number of rounds to run.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "simulation_outputs",
        help="Directory where CSV and summary files will be written.",
    )
    parser.add_argument(
        "--strategies",
        nargs="*",
        default=list(DEFAULT_STRATEGY_ROTATION),
        choices=sorted(STRATEGY_PRESETS),
        help="Strategy presets to cycle across teams.",
    )
    parser.add_argument(
        "--market-scenario",
        default="baseline",
        choices=sorted(MARKET_SCENARIO_PRESETS),
        help="Named market scenario to run.",
    )
    parser.add_argument(
        "--compare-market-scenarios",
        action="store_true",
        help="Run the same team strategies through all market scenarios.",
    )
    parser.add_argument(
        "--batch-runs",
        type=int,
        default=0,
        help="Run many deterministic market/team-count experiments.",
    )
    parser.add_argument(
        "--min-teams",
        type=int,
        default=4,
        help="Minimum team count for batch experiments.",
    )
    parser.add_argument(
        "--max-teams",
        type=int,
        default=10,
        help="Maximum team count for batch experiments.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260425,
        help="Random seed for deterministic batch experiments.",
    )
    args = parser.parse_args()

    if args.teams <= 0:
        raise SystemExit("--teams must be greater than zero.")
    if args.rounds <= 0:
        raise SystemExit("--rounds must be greater than zero.")
    if args.min_teams <= 0 or args.max_teams < args.min_teams:
        raise SystemExit("--min-teams and --max-teams must define a valid positive range.")

    if args.batch_runs > 0:
        prefix = "batch_experiments"
    elif args.compare_market_scenarios:
        prefix = "market_compare"
    else:
        prefix = "strategy_run"
    run_dir = args.output_dir / datetime.now().strftime(f"{prefix}_%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.batch_runs > 0:
        batch_scenarios = run_batch_experiments(
            batch_runs=args.batch_runs,
            min_teams=args.min_teams,
            max_teams=args.max_teams,
            round_count=args.rounds,
            strategy_rotation=tuple(args.strategies),
            seed=args.seed,
        )
        write_batch_outputs(run_dir, batch_scenarios)
        print(f"Batch experiments complete: {run_dir}")
        robustness_rows = build_batch_strategy_robustness_rows(
            build_batch_final_team_rows(batch_scenarios)
        )
        for row in robustness_rows[:6]:
            print(
                f"{row['strategy_label']}: profit wins={row['profit_wins']}, "
                f"balanced wins={row['balanced_wins']}, "
                f"avg balanced rank={row['average_balanced_rank']}, "
                f"avg profit=${row['average_profit']:,.2f}"
            )
    elif args.compare_market_scenarios:
        scenarios = run_market_scenario_comparison(
            team_count=args.teams,
            round_count=args.rounds,
            strategy_rotation=tuple(args.strategies),
        )
        write_market_comparison_outputs(run_dir, scenarios)
        print(f"Market comparison complete: {run_dir}")
        comparison_rows = build_market_comparison_rows(scenarios)
        for row in comparison_rows:
            print(
                f"{row['market_scenario']}: profit winner={row['profit_winner']} "
                f"({row['profit_winner_strategy']}), balanced winner={row['balanced_winner']} "
                f"({row['balanced_winner_strategy']})"
            )
    else:
        scenario = run_strategy_scenario(
            team_count=args.teams,
            round_count=args.rounds,
            strategy_rotation=tuple(args.strategies),
            market_scenario_key=args.market_scenario,
        )
        write_outputs(run_dir, scenario)

        final_results = latest_round_results(scenario["team_results"])
        print(f"Simulation complete: {run_dir}")
        print("Final ranking by profit:")
        for rank, result in enumerate(
            sorted(final_results, key=lambda item: item.profit, reverse=True),
            start=1,
        ):
            print(
                f"{rank}. {result.team_name}: "
                f"profit=${result.profit:,.2f}, "
                f"cash=${result.ending_cash_balance:,.2f}, "
                f"debt=${result.short_term_debt_balance:,.2f}, "
                f"WAPE={result.forecast_wape:.1%}"
            )


def run_strategy_scenario(
    team_count: int,
    round_count: int,
    strategy_rotation: tuple[str, ...],
    market_scenario_key: str = "baseline",
    market_scenario_config: dict[str, Any] | None = None,
    run_id: int | None = None,
    strategy_offset: int = 0,
    archetype_offset: int = 0,
) -> dict[str, Any]:
    """Run a deterministic in-memory scenario across several rounds."""
    archetypes = DEFAULT_TEAM_ARCHETYPES
    market_scenario = market_scenario_config or MARKET_SCENARIO_PRESETS[market_scenario_key]

    # The production engine normally loads archetypes from SQLite. For this
    # offline runner, keep the scenario fully in memory and avoid app data side effects.
    simulator.load_team_archetypes = lambda: list(archetypes)

    teams = build_team_specs(
        team_count,
        strategy_rotation,
        archetypes,
        strategy_offset=strategy_offset,
        archetype_offset=archetype_offset,
    )
    states: list[PersistentTeamState] = []
    product_lines: list[ProductLine] = []
    projects: list[ProductDevelopmentProject] = []
    all_team_results: list[RoundResult] = []
    all_product_results: list[Any] = []
    all_forecast_results: list[Any] = []

    for round_number in range(1, round_count + 1):
        market_report = market_for_round(
            round_number,
            market_scenario_key,
            market_scenario,
        )
        team_decisions: list[TeamDecision] = []
        product_decisions: list[ProductDecision] = []
        round_projects: list[ProductDevelopmentProject] = []

        for team in teams:
            team_lines = lines_for_team(
                team_name=team["team_name"],
                archetype=team["archetype"],
                product_lines=product_lines,
            )
            product_decisions_for_team = build_product_decisions(
                team=team,
                product_lines=team_lines,
                round_number=round_number,
            )
            total_planned_units = sum(
                item.planned_production_units
                for item in product_decisions_for_team
                if item.is_active
            )
            total_forecast_units = sum(
                item.forecast_units
                for item in product_decisions_for_team
                if item.is_active
            )

            team_decisions.append(
                build_team_decision(
                    team=team,
                    total_planned_units=total_planned_units,
                    total_forecast_units=total_forecast_units,
                )
            )
            product_decisions.extend(product_decisions_for_team)
            round_projects.extend(
                build_project_decisions(
                    team=team,
                    existing_projects=[
                        item
                        for item in projects
                        if item.team_name.lower() == team["team_name"].lower()
                    ],
                    round_number=round_number,
                    market_report=market_report,
                )
            )

        (
            team_results,
            product_results,
            states,
            product_lines,
            projects,
            forecast_results,
        ) = simulator.run_round(
            market_report=market_report,
            team_decisions=team_decisions,
            product_lines=product_lines,
            product_decisions=product_decisions,
            development_projects=round_projects,
            existing_states=states,
        )

        all_team_results.extend(team_results)
        all_product_results.extend(product_results)
        all_forecast_results.extend(forecast_results)

    return {
        "run_id": run_id,
        "team_count": team_count,
        "round_count": round_count,
        "strategy_offset": strategy_offset,
        "archetype_offset": archetype_offset,
        "market_scenario_key": market_scenario_key,
        "market_scenario_label": market_scenario["label"],
        "market_scenario_config": market_scenario,
        "teams": teams,
        "team_results": all_team_results,
        "product_results": all_product_results,
        "forecast_results": all_forecast_results,
        "final_states": states,
        "final_product_lines": product_lines,
        "final_projects": projects,
    }


def run_market_scenario_comparison(
    team_count: int,
    round_count: int,
    strategy_rotation: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    """Run identical team strategies through each named market scenario."""
    scenarios: dict[str, dict[str, Any]] = {}
    for market_scenario_key in MARKET_SCENARIO_PRESETS:
        scenarios[market_scenario_key] = run_strategy_scenario(
            team_count=team_count,
            round_count=round_count,
            strategy_rotation=strategy_rotation,
            market_scenario_key=market_scenario_key,
        )
    return scenarios


def run_batch_experiments(
    batch_runs: int,
    min_teams: int,
    max_teams: int,
    round_count: int,
    strategy_rotation: tuple[str, ...],
    seed: int,
) -> list[dict[str, Any]]:
    """Run many deterministic market/team-count experiments."""
    rng = random.Random(seed)
    scenarios: list[dict[str, Any]] = []
    for run_id in range(1, batch_runs + 1):
        team_count = rng.randint(min_teams, max_teams)
        market_config = random_market_config(rng, run_id)
        scenarios.append(
            run_strategy_scenario(
                team_count=team_count,
                round_count=round_count,
                strategy_rotation=strategy_rotation,
                market_scenario_key=f"batch_{run_id:03d}",
                market_scenario_config=market_config,
                run_id=run_id,
                strategy_offset=rng.randrange(len(strategy_rotation)),
                archetype_offset=rng.randrange(len(DEFAULT_TEAM_ARCHETYPES)),
            )
        )
    return scenarios


def random_market_config(rng: random.Random, run_id: int) -> dict[str, Any]:
    """Create one deterministic but varied market environment."""
    premium_shift = rng.uniform(-0.14, 0.14)
    mid_shift = rng.uniform(-0.10, 0.10)
    beginner_shift = rng.uniform(-0.14, 0.14)
    risk_roll = rng.random()
    if risk_roll < 0.22:
        supply_risk = "Low"
    elif risk_roll < 0.68:
        supply_risk = "Moderate"
    else:
        supply_risk = "High"

    return {
        "label": f"Batch market {run_id:03d}",
        "demand_multiplier": rng.uniform(0.65, 1.75),
        "demand_growth_delta": rng.uniform(-0.07, 0.11),
        "premium_share_shift": premium_shift,
        "mid_share_shift": mid_shift,
        "beginner_share_shift": beginner_shift,
        "material_cost_index_delta": rng.uniform(-0.04, 0.24),
        "supply_risk_override": supply_risk,
        "quality_sensitivity_delta": rng.uniform(-0.22, 0.32),
        "technology_shift_delta": rng.uniform(-0.08, 0.38),
        "market_generation_offset": rng.choice([-1, 0, 0, 0, 1, 1]),
        "premium_tech_adoption_delta": rng.uniform(-0.14, 0.24),
        "mid_tech_adoption_delta": rng.uniform(-0.10, 0.20),
        "beginner_price_pressure_delta": rng.uniform(-0.12, 0.36),
    }


def build_team_specs(
    team_count: int,
    strategy_rotation: tuple[str, ...],
    archetypes: list[TeamArchetype],
    strategy_offset: int = 0,
    archetype_offset: int = 0,
) -> list[dict[str, Any]]:
    """Create deterministic team assignments for a scenario."""
    teams: list[dict[str, Any]] = []
    for index in range(team_count):
        archetype = archetypes[(index + archetype_offset) % len(archetypes)]
        strategy_key = strategy_rotation[(index + strategy_offset) % len(strategy_rotation)]
        teams.append(
            {
                "team_name": f"Team {index + 1:02d}",
                "archetype": archetype,
                "strategy_key": strategy_key,
                "strategy": STRATEGY_PRESETS[strategy_key],
            }
        )
    return teams


def market_for_round(
    round_number: int,
    market_scenario_key: str = "baseline",
    market_scenario_config: dict[str, Any] | None = None,
) -> MarketReport:
    """Create a simple deterministic market path for scenario analysis."""
    scenario = market_scenario_config or MARKET_SCENARIO_PRESETS[market_scenario_key]
    market_report = replace(DEFAULT_MARKET_REPORT)
    market_report.round_number = round_number
    growth_rate = 0.07 + scenario["demand_growth_delta"]
    market_report.total_demand = int(
        round(
            DEFAULT_MARKET_REPORT.total_demand
            * scenario["demand_multiplier"]
            * (1.0 + growth_rate * (round_number - 1))
        )
    )
    market_report.premium_share = max(
        DEFAULT_MARKET_REPORT.premium_share + scenario["premium_share_shift"],
        0.01,
    )
    market_report.mid_share = max(
        DEFAULT_MARKET_REPORT.mid_share + scenario["mid_share_shift"],
        0.01,
    )
    market_report.beginner_share = max(
        DEFAULT_MARKET_REPORT.beginner_share + scenario["beginner_share_shift"],
        0.01,
    )
    market_report.material_cost_index = round(
        1.0
        + 0.025 * max(round_number - 1, 0)
        + scenario["material_cost_index_delta"],
        3,
    )
    market_report.current_market_generation = min(
        4,
        max(
            1,
            2
            + max(round_number - 2, 0) // 2
            + scenario["market_generation_offset"],
        ),
    )
    market_report.technology_shift_rate = round(
        max(
            0.0,
            0.16
            + 0.03 * max(round_number - 1, 0)
            + scenario["technology_shift_delta"],
        ),
        3,
    )
    market_report.supply_risk = (
        scenario["supply_risk_override"]
        if scenario["supply_risk_override"] is not None
        else ("High" if round_number % 3 == 0 else "Moderate")
    )
    market_report.quality_sensitivity = min(
        max(
            DEFAULT_MARKET_REPORT.quality_sensitivity
            + scenario["quality_sensitivity_delta"],
            0.0,
        ),
        1.0,
    )
    market_report.premium_tech_adoption = min(
        max(
            DEFAULT_MARKET_REPORT.premium_tech_adoption
            + scenario["premium_tech_adoption_delta"],
            0.0,
        ),
        1.0,
    )
    market_report.mid_market_tech_adoption = min(
        max(
            DEFAULT_MARKET_REPORT.mid_market_tech_adoption
            + scenario["mid_tech_adoption_delta"],
            0.0,
        ),
        1.0,
    )
    market_report.beginner_price_pressure = min(
        max(
            DEFAULT_MARKET_REPORT.beginner_price_pressure
            + scenario["beginner_price_pressure_delta"],
            0.0,
        ),
        1.0,
    )
    market_report.event = (
        f"{scenario['label']} round {round_number}: deterministic market stress path."
    )
    return market_report


def lines_for_team(
    team_name: str,
    archetype: TeamArchetype,
    product_lines: list[ProductLine],
) -> list[ProductLine]:
    """Return current team product lines, seeding from archetype templates if needed."""
    existing_lines = [
        item
        for item in product_lines
        if item.team_name.lower() == team_name.lower()
    ]
    if existing_lines:
        return sorted(existing_lines, key=lambda item: item.slot_name)

    return [
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
        for template in sorted(archetype.suggested_product_templates, key=lambda item: item.slot_name)
    ]


def build_product_decisions(
    team: dict[str, Any],
    product_lines: list[ProductLine],
    round_number: int,
) -> list[ProductDecision]:
    """Build product decisions for one team from its strategy preset."""
    archetype: TeamArchetype = team["archetype"]
    strategy = team["strategy"]
    templates_by_slot = {
        item.slot_name: item for item in archetype.suggested_product_templates
    }
    decisions: list[ProductDecision] = []

    for line in sorted(product_lines, key=lambda item: item.slot_name):
        template = templates_by_slot.get(line.slot_name)
        base_price = (
            template.suggested_selling_price_per_unit
            if template is not None
            else SEGMENT_REFERENCE_PRICES.get(line.target_segment, 130.0)
        )
        base_planned_units = (
            template.suggested_planned_production_units
            if template is not None
            else max(line.inventory_units, 75)
        )
        base_qc_budget = (
            template.suggested_qc_budget_per_unit
            if template is not None
            else 3.0
        )
        base_target_inventory = (
            template.suggested_target_finished_goods_inventory
            if template is not None
            else 20
        )

        lifecycle_pressure = 0.92 if line.lifecycle_stage == "decline" else 1.0
        planned_units = int(
            round(
                base_planned_units
                * strategy["production_multiplier"]
                * lifecycle_pressure
            )
        )
        forecast_units = int(
            round(planned_units * strategy["forecast_multiplier"])
        )

        decisions.append(
            ProductDecision(
                product_id=line.product_id,
                team_name=team["team_name"],
                slot_name=line.slot_name,
                product_name=line.product_name,
                is_active=line.is_active,
                target_segment=line.target_segment,
                selling_price_per_unit=round(
                    base_price * strategy["price_multiplier"],
                    2,
                ),
                planned_production_units=max(planned_units, 0) if line.is_active else 0,
                qc_budget_per_unit=round(max(base_qc_budget + strategy["qc_delta"], 0.0), 2),
                target_finished_goods_inventory=max(
                    int(round(base_target_inventory * strategy["target_inventory_multiplier"])),
                    0,
                ),
                forecast_units=max(forecast_units, 0) if line.is_active else 0,
                retire_flag=bool(
                    line.lifecycle_stage == "decline"
                    and team["strategy_key"] in {"innovation_leap", "premium_quality"}
                    and round_number >= 3
                ),
            )
        )

    return decisions


def build_team_decision(
    team: dict[str, Any],
    total_planned_units: int,
    total_forecast_units: int,
) -> TeamDecision:
    """Build the firm-level decision for one team from its strategy preset."""
    archetype: TeamArchetype = team["archetype"]
    strategy = team["strategy"]
    offshore_pct, balanced_pct, premium_pct = strategy["supplier_mix"]

    return TeamDecision(
        team_name=team["team_name"],
        archetype=archetype.name,
        overtime_capacity_units=max(
            int(round(archetype.base_capacity * strategy["overtime_pct_of_capacity"])),
            0,
        ),
        capacity_expansion_units=max(
            int(round(archetype.base_capacity * strategy["capacity_expansion_pct_of_capacity"])),
            0,
        ),
        raw_material_order_qty=max(
            int(round(total_planned_units * strategy["raw_material_multiplier"])),
            0,
        ),
        supplier_mix_offshore_pct=offshore_pct,
        supplier_mix_balanced_pct=balanced_pct,
        supplier_mix_premium_pct=premium_pct,
        expedited_order_share_pct=strategy["expedited_share_pct"],
        max_backorder_units=max(
            int(round(total_forecast_units * strategy["max_backorder_pct_of_forecast"])),
            0,
        ),
        planned_borrowing_amount=max(strategy["planned_borrowing"], 0.0),
    )


def build_project_decisions(
    team: dict[str, Any],
    existing_projects: list[ProductDevelopmentProject],
    round_number: int,
    market_report: MarketReport,
) -> list[ProductDevelopmentProject]:
    """Build or update up to two NPD project slots for one team."""
    strategy = team["strategy"]
    project_by_slot = {item.project_slot_name: item for item in existing_projects}
    projects: list[ProductDevelopmentProject] = []

    for project_slot_name in ("P1", "P2"):
        existing = project_by_slot.get(project_slot_name)
        if existing is not None:
            project = replace(existing)
            project.investment_this_round = 0.0
            project.testing_intensity = 0.0
            project.launch_now = project.status == "launch_ready"
            project.cancel_now = False
            if (
                project_slot_name == "P1"
                and project.status not in {"launched", "canceled"}
                and project.project_name.strip()
            ):
                project.investment_this_round = max(strategy["npd_investment"], 0.0)
                project.testing_intensity = strategy["testing_intensity"]
            projects.append(project)
            continue

        if project_slot_name == "P1" and strategy["npd_investment"] > 0:
            target_segment = best_segment_for_archetype(team["archetype"])
            target_generation = min(market_report.current_market_generation + 1, 4)
            projects.append(
                ProductDevelopmentProject(
                    project_id=build_project_id(team["team_name"], project_slot_name),
                    team_name=team["team_name"],
                    project_slot_name=project_slot_name,
                    project_name=f"{team['team_name']} NextGen",
                    target_segment=target_segment,
                    target_tech_generation=target_generation,
                    intended_slot_name="C",
                    required_investment=0.0,
                    cumulative_investment=0.0,
                    investment_this_round=max(strategy["npd_investment"], 0.0),
                    testing_intensity=strategy["testing_intensity"],
                    launch_readiness_score=0.0,
                    planned_launch_round=round_number + 2,
                    earliest_launch_round=round_number + 2,
                    status="concept",
                    cannibalization_group=f"{target_segment}_nextgen",
                    projected_base_defect_modifier=0.002,
                    projected_demand_fit_modifier=1.08,
                    created_round=round_number,
                )
            )
            continue

        projects.append(
            ProductDevelopmentProject(
                project_id=build_project_id(team["team_name"], project_slot_name),
                team_name=team["team_name"],
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
                planned_launch_round=round_number,
                earliest_launch_round=round_number,
                status="concept",
                cannibalization_group="",
                projected_base_defect_modifier=0.0,
                projected_demand_fit_modifier=1.0,
                created_round=round_number,
            )
        )

    return projects


def best_segment_for_archetype(archetype: TeamArchetype) -> str:
    """Return the strongest demand segment for an archetype."""
    segment_scores = {
        "premium": archetype.premium_fit,
        "mid": archetype.mid_fit,
        "beginner": archetype.beginner_fit,
    }
    return max(segment_scores, key=segment_scores.get)


def write_outputs(run_dir: Path, scenario: dict[str, Any]) -> None:
    """Write scenario results as CSV and markdown summary files."""
    write_csv(run_dir / "team_results.csv", [asdict(item) for item in scenario["team_results"]])
    write_csv(run_dir / "product_results.csv", [asdict(item) for item in scenario["product_results"]])
    write_csv(run_dir / "forecast_accuracy.csv", [asdict(item) for item in scenario["forecast_results"]])
    write_csv(run_dir / "final_team_states.csv", [item.to_dict() for item in scenario["final_states"]])
    write_csv(run_dir / "final_product_lines.csv", [item.to_dict() for item in scenario["final_product_lines"]])
    write_csv(run_dir / "final_projects.csv", [item.to_dict() for item in scenario["final_projects"]])
    write_csv(
        run_dir / "team_strategy_assignments.csv",
        [
            {
                "team_name": item["team_name"],
                "archetype": item["archetype"].name,
                "strategy_key": item["strategy_key"],
                "strategy_label": item["strategy"]["label"],
            }
            for item in scenario["teams"]
        ],
    )
    (run_dir / "summary.md").write_text(build_summary_markdown(scenario), encoding="utf-8")


def write_market_comparison_outputs(
    run_dir: Path,
    scenarios: dict[str, dict[str, Any]],
) -> None:
    """Write one folder per market scenario plus cross-scenario comparison files."""
    for scenario_key, scenario in scenarios.items():
        scenario_dir = run_dir / scenario_key
        scenario_dir.mkdir(parents=True, exist_ok=True)
        write_outputs(scenario_dir, scenario)

    comparison_rows = build_market_comparison_rows(scenarios)
    final_team_rows = build_market_final_team_rows(scenarios)
    write_csv(run_dir / "market_scenario_comparison.csv", comparison_rows)
    write_csv(run_dir / "market_scenario_team_results.csv", final_team_rows)
    (run_dir / "market_scenario_summary.md").write_text(
        build_market_comparison_markdown(comparison_rows, final_team_rows),
        encoding="utf-8",
    )


def write_batch_outputs(run_dir: Path, scenarios: list[dict[str, Any]]) -> None:
    """Write aggregate CSV/Markdown outputs for many batch experiments."""
    run_summary_rows = build_batch_run_summary_rows(scenarios)
    final_team_rows = build_batch_final_team_rows(scenarios)
    robustness_rows = build_batch_strategy_robustness_rows(final_team_rows)
    write_csv(run_dir / "batch_run_summary.csv", run_summary_rows)
    write_csv(run_dir / "batch_final_team_results.csv", final_team_rows)
    write_csv(run_dir / "batch_strategy_robustness.csv", robustness_rows)
    write_csv(run_dir / "batch_team_round_results.csv", build_batch_round_rows(scenarios, "team_results"))
    write_csv(run_dir / "batch_product_round_results.csv", build_batch_round_rows(scenarios, "product_results"))
    write_csv(run_dir / "batch_forecast_accuracy.csv", build_batch_round_rows(scenarios, "forecast_results"))
    (run_dir / "batch_summary.md").write_text(
        build_batch_summary_markdown(run_summary_rows, robustness_rows),
        encoding="utf-8",
    )


def build_batch_run_summary_rows(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build one summary row per batch experiment."""
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        final_results = latest_round_results(scenario["team_results"])
        assignments = assignment_lookup(scenario)
        profit_winner = max(final_results, key=lambda item: item.profit)
        balanced_winner = balanced_score_rows(final_results, assignments)[0]
        service_winner = max(final_results, key=lambda item: item.fill_rate)
        forecast_winner = min(final_results, key=lambda item: item.forecast_wape)
        cash_winner = max(
            final_results,
            key=lambda item: item.ending_cash_balance - item.short_term_debt_balance,
        )
        market_config = scenario["market_scenario_config"]
        average_profit = sum(item.profit for item in final_results) / max(len(final_results), 1)
        rows.append(
            {
                "run_id": scenario["run_id"],
                "team_count": scenario["team_count"],
                "round_count": scenario["round_count"],
                "strategy_offset": scenario["strategy_offset"],
                "archetype_offset": scenario["archetype_offset"],
                "market_scenario": scenario["market_scenario_key"],
                "market_label": scenario["market_scenario_label"],
                "demand_multiplier": round(market_config["demand_multiplier"], 4),
                "demand_growth_delta": round(market_config["demand_growth_delta"], 4),
                "premium_share_shift": round(market_config["premium_share_shift"], 4),
                "mid_share_shift": round(market_config["mid_share_shift"], 4),
                "beginner_share_shift": round(market_config["beginner_share_shift"], 4),
                "material_cost_index_delta": round(market_config["material_cost_index_delta"], 4),
                "supply_risk": market_config["supply_risk_override"],
                "quality_sensitivity_delta": round(market_config["quality_sensitivity_delta"], 4),
                "technology_shift_delta": round(market_config["technology_shift_delta"], 4),
                "market_generation_offset": market_config["market_generation_offset"],
                "beginner_price_pressure_delta": round(market_config["beginner_price_pressure_delta"], 4),
                "profit_winner": profit_winner.team_name,
                "profit_winner_strategy": assignments[profit_winner.team_name]["strategy_label"],
                "profit_winner_profit": round(profit_winner.profit, 2),
                "balanced_winner": balanced_winner["team_name"],
                "balanced_winner_strategy": balanced_winner["strategy_label"],
                "balanced_winner_score": balanced_winner["balanced_score"],
                "service_winner": service_winner.team_name,
                "forecast_winner": forecast_winner.team_name,
                "cash_winner": cash_winner.team_name,
                "average_profit": round(average_profit, 2),
                "liquidity_stress_team_count": sum(
                    1 for item in final_results if item.liquidity_stress_flag
                ),
            }
        )
    return rows


def build_batch_final_team_rows(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build final-round team rows for every batch experiment."""
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        assignments = assignment_lookup(scenario)
        final_results = latest_round_results(scenario["team_results"])
        profit_ranked = sorted(final_results, key=lambda item: item.profit, reverse=True)
        balanced_ranked = balanced_score_rows(final_results, assignments)
        balanced_rank_by_team = {
            row["team_name"]: index
            for index, row in enumerate(balanced_ranked, start=1)
        }
        balanced_score_by_team = {
            row["team_name"]: row["balanced_score"]
            for row in balanced_ranked
        }
        for profit_rank, result in enumerate(profit_ranked, start=1):
            assignment = assignments[result.team_name]
            rows.append(
                {
                    "run_id": scenario["run_id"],
                    "team_count": scenario["team_count"],
                    "round_count": scenario["round_count"],
                    "strategy_offset": scenario["strategy_offset"],
                    "archetype_offset": scenario["archetype_offset"],
                    "market_scenario": scenario["market_scenario_key"],
                    "team_name": result.team_name,
                    "archetype": assignment["archetype"],
                    "strategy_key": assignment["strategy_key"],
                    "strategy_label": assignment["strategy_label"],
                    "profit_rank": profit_rank,
                    "balanced_rank": balanced_rank_by_team[result.team_name],
                    "balanced_score": balanced_score_by_team[result.team_name],
                    "profit": result.profit,
                    "revenue": result.revenue,
                    "total_cost": result.total_cost,
                    "sales_units": result.sales_units,
                    "fill_rate": result.fill_rate,
                    "forecast_wape": result.forecast_wape,
                    "ending_cash_balance": result.ending_cash_balance,
                    "short_term_debt_balance": result.short_term_debt_balance,
                    "cash_minus_debt": (
                        result.ending_cash_balance - result.short_term_debt_balance
                    ),
                    "liquidity_stress_flag": result.liquidity_stress_flag,
                    "reputation_after_round": result.reputation_after_round,
                    "lost_sales_units": result.lost_sales_units,
                    "backlog_units_end": result.backlog_units_end,
                    "ending_inventory": result.ending_inventory,
                }
            )
    return rows


def build_batch_strategy_robustness_rows(
    final_team_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Aggregate final team rows into strategy robustness metrics."""
    grouped: dict[str, dict[str, Any]] = {}
    for row in final_team_rows:
        strategy_key = str(row["strategy_key"])
        summary = grouped.setdefault(
            strategy_key,
            {
                "strategy_key": strategy_key,
                "strategy_label": row["strategy_label"],
                "appearances": 0,
                "profit_wins": 0,
                "balanced_wins": 0,
                "profit_rank_total": 0.0,
                "balanced_rank_total": 0.0,
                "profit_total": 0.0,
                "balanced_score_total": 0.0,
                "fill_rate_total": 0.0,
                "forecast_wape_total": 0.0,
                "cash_minus_debt_total": 0.0,
                "liquidity_stress_count": 0,
            },
        )
        summary["appearances"] += 1
        summary["profit_wins"] += 1 if int(row["profit_rank"]) == 1 else 0
        summary["balanced_wins"] += 1 if int(row["balanced_rank"]) == 1 else 0
        summary["profit_rank_total"] += float(row["profit_rank"])
        summary["balanced_rank_total"] += float(row["balanced_rank"])
        summary["profit_total"] += float(row["profit"])
        summary["balanced_score_total"] += float(row["balanced_score"])
        summary["fill_rate_total"] += float(row["fill_rate"])
        summary["forecast_wape_total"] += float(row["forecast_wape"])
        summary["cash_minus_debt_total"] += float(row["cash_minus_debt"])
        summary["liquidity_stress_count"] += 1 if row["liquidity_stress_flag"] else 0

    rows: list[dict[str, Any]] = []
    for summary in grouped.values():
        appearances = max(summary["appearances"], 1)
        rows.append(
            {
                "strategy_key": summary["strategy_key"],
                "strategy_label": summary["strategy_label"],
                "appearances": summary["appearances"],
                "profit_wins": summary["profit_wins"],
                "balanced_wins": summary["balanced_wins"],
                "average_profit_rank": round(summary["profit_rank_total"] / appearances, 2),
                "average_balanced_rank": round(summary["balanced_rank_total"] / appearances, 2),
                "average_profit": round(summary["profit_total"] / appearances, 2),
                "average_balanced_score": round(summary["balanced_score_total"] / appearances, 1),
                "average_fill_rate": round(summary["fill_rate_total"] / appearances, 4),
                "average_forecast_wape": round(summary["forecast_wape_total"] / appearances, 4),
                "average_cash_minus_debt": round(summary["cash_minus_debt_total"] / appearances, 2),
                "liquidity_stress_rate": round(summary["liquidity_stress_count"] / appearances, 4),
            }
        )
    return sorted(
        rows,
        key=lambda item: (
            -item["balanced_wins"],
            -item["profit_wins"],
            item["average_balanced_rank"],
        ),
    )


def build_batch_round_rows(
    scenarios: list[dict[str, Any]],
    result_key: str,
) -> list[dict[str, Any]]:
    """Build all-round rows for one result collection across batch experiments."""
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        for result in scenario[result_key]:
            row = asdict(result)
            row.update(
                {
                    "run_id": scenario["run_id"],
                    "team_count": scenario["team_count"],
                    "market_scenario": scenario["market_scenario_key"],
                    "market_label": scenario["market_scenario_label"],
                }
            )
            rows.append(row)
    return rows


def build_batch_summary_markdown(
    run_summary_rows: list[dict[str, Any]],
    robustness_rows: list[dict[str, Any]],
) -> str:
    """Build a readable markdown summary for batch experiments."""
    profit_wins_by_strategy = count_by_key(run_summary_rows, "profit_winner_strategy")
    balanced_wins_by_strategy = count_by_key(run_summary_rows, "balanced_winner_strategy")
    top_runs = sorted(
        run_summary_rows,
        key=lambda row: float(row["profit_winner_profit"]),
        reverse=True,
    )[:10]
    return "\n".join(
        [
            "# Batch Experiment Summary",
            "",
            f"Total simulations: {len(run_summary_rows)}",
            "",
            "## Strategy Robustness",
            "",
            markdown_table(robustness_rows),
            "",
            "## Profit Wins By Strategy",
            "",
            markdown_table(profit_wins_by_strategy),
            "",
            "## Balanced Wins By Strategy",
            "",
            markdown_table(balanced_wins_by_strategy),
            "",
            "## Highest Profit Runs",
            "",
            markdown_table(top_runs),
            "",
            "Balanced score weights: 40% profit, 20% fill rate, 20% forecast accuracy, 20% cash-minus-debt, with a small liquidity-stress penalty.",
            "",
        ]
    )


def count_by_key(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Count rows by one dictionary key for summary tables."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row[key])] = counts.get(str(row[key]), 0) + 1
    return [
        {"value": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def build_market_comparison_rows(
    scenarios: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build one final winner row per market scenario."""
    rows: list[dict[str, Any]] = []
    for scenario_key, scenario in scenarios.items():
        final_results = latest_round_results(scenario["team_results"])
        assignments = assignment_lookup(scenario)
        winning_result = max(final_results, key=lambda item: item.profit)
        balanced_winner = balanced_score_rows(final_results, assignments)[0]
        service_winner = max(final_results, key=lambda item: item.fill_rate)
        forecast_winner = min(final_results, key=lambda item: item.forecast_wape)
        cash_winner = max(
            final_results,
            key=lambda item: item.ending_cash_balance - item.short_term_debt_balance,
        )
        stressed_count = sum(1 for item in final_results if item.liquidity_stress_flag)
        average_profit = sum(item.profit for item in final_results) / max(len(final_results), 1)
        average_wape = sum(item.forecast_wape for item in final_results) / max(len(final_results), 1)
        rows.append(
            {
                "market_scenario": scenario_key,
                "market_label": scenario["market_scenario_label"],
                "profit_winner": winning_result.team_name,
                "profit_winner_strategy": assignments[winning_result.team_name]["strategy_label"],
                "profit_winner_profit": f"${winning_result.profit:,.2f}",
                "balanced_winner": balanced_winner["team_name"],
                "balanced_winner_strategy": balanced_winner["strategy_label"],
                "balanced_score": balanced_winner["balanced_score"],
                "service_winner": service_winner.team_name,
                "forecast_winner": forecast_winner.team_name,
                "cash_winner": cash_winner.team_name,
                "average_profit": f"${average_profit:,.2f}",
                "average_forecast_wape": f"{average_wape:.1%}",
                "liquidity_stress_team_count": stressed_count,
            }
        )
    return rows


def build_market_final_team_rows(
    scenarios: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build final-round rows for every team under every market scenario."""
    rows: list[dict[str, Any]] = []
    for scenario_key, scenario in scenarios.items():
        assignments = assignment_lookup(scenario)
        final_results = latest_round_results(scenario["team_results"])
        ranked_results = sorted(final_results, key=lambda item: item.profit, reverse=True)
        for rank, result in enumerate(ranked_results, start=1):
            assignment = assignments[result.team_name]
            rows.append(
                {
                    "market_scenario": scenario_key,
                    "market_label": scenario["market_scenario_label"],
                    "rank": rank,
                    "team_name": result.team_name,
                    "archetype": assignment["archetype"],
                    "strategy_key": assignment["strategy_key"],
                    "strategy_label": assignment["strategy_label"],
                    "profit": result.profit,
                    "revenue": result.revenue,
                    "total_cost": result.total_cost,
                    "sales_units": result.sales_units,
                    "fill_rate": result.fill_rate,
                    "forecast_wape": result.forecast_wape,
                    "ending_cash_balance": result.ending_cash_balance,
                    "short_term_debt_balance": result.short_term_debt_balance,
                    "liquidity_stress_flag": result.liquidity_stress_flag,
                    "reputation_after_round": result.reputation_after_round,
                    "balanced_score": balanced_score_for_result(result, final_results),
                }
            )
    return rows


def balanced_score_rows(
    final_results: list[RoundResult],
    assignments: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Return final results ranked by a multi-objective teaching score."""
    rows = []
    for result in final_results:
        assignment = assignments[result.team_name]
        rows.append(
            {
                "team_name": result.team_name,
                "strategy_key": assignment["strategy_key"],
                "strategy_label": assignment["strategy_label"],
                "balanced_score": balanced_score_for_result(result, final_results),
                "profit": result.profit,
                "fill_rate": result.fill_rate,
                "forecast_wape": result.forecast_wape,
                "cash_minus_debt": (
                    result.ending_cash_balance - result.short_term_debt_balance
                ),
                "liquidity_stress_flag": result.liquidity_stress_flag,
            }
        )
    return sorted(rows, key=lambda item: item["balanced_score"], reverse=True)


def balanced_score_for_result(
    result: RoundResult,
    peer_results: list[RoundResult],
) -> float:
    """Score performance across profit, service, forecast discipline, and liquidity."""
    profit_score = percentile_score(
        result.profit,
        [item.profit for item in peer_results],
    )
    service_score = percentile_score(
        result.fill_rate,
        [item.fill_rate for item in peer_results],
    )
    forecast_score = 1.0 - percentile_score(
        result.forecast_wape,
        [item.forecast_wape for item in peer_results],
    )
    liquidity_score = percentile_score(
        result.ending_cash_balance - result.short_term_debt_balance,
        [
            item.ending_cash_balance - item.short_term_debt_balance
            for item in peer_results
        ],
    )
    stress_penalty = 0.08 if result.liquidity_stress_flag else 0.0
    return round(
        max(
            0.0,
            100.0
            * (
                0.40 * profit_score
                + 0.20 * service_score
                + 0.20 * forecast_score
                + 0.20 * liquidity_score
                - stress_penalty
            ),
        ),
        1,
    )


def percentile_score(value: float, values: list[float]) -> float:
    """Return a 0-1 rank score where higher values are better."""
    if not values:
        return 0.0
    if len(values) == 1:
        return 1.0
    sorted_values = sorted(values)
    better_or_equal_count = sum(1 for item in sorted_values if item <= value)
    return (better_or_equal_count - 1) / (len(sorted_values) - 1)


def build_market_comparison_markdown(
    comparison_rows: list[dict[str, Any]],
    final_team_rows: list[dict[str, Any]],
) -> str:
    """Build a readable cross-market comparison summary."""
    strategy_summary: dict[str, dict[str, Any]] = {}
    for row in final_team_rows:
        strategy_key = str(row["strategy_key"])
        summary = strategy_summary.setdefault(
            strategy_key,
            {
                "strategy": row["strategy_label"],
                "profit_wins": 0,
                "balanced_wins": 0,
                "average_rank_total": 0.0,
                "average_profit_total": 0.0,
                "balanced_score_total": 0.0,
                "liquidity_stress_count": 0,
                "scenario_count": 0,
            },
        )
        scenario_key = str(row["market_scenario"])
        scenario_comparison = next(
            item for item in comparison_rows if item["market_scenario"] == scenario_key
        )
        summary["profit_wins"] += 1 if int(row["rank"]) == 1 else 0
        summary["balanced_wins"] += (
            1 if row["team_name"] == scenario_comparison["balanced_winner"] else 0
        )
        summary["average_rank_total"] += float(row["rank"])
        summary["average_profit_total"] += float(row["profit"])
        summary["balanced_score_total"] += float(row["balanced_score"])
        summary["liquidity_stress_count"] += 1 if row["liquidity_stress_flag"] else 0
        summary["scenario_count"] += 1

    strategy_rows = []
    for summary in strategy_summary.values():
        scenario_count = max(summary["scenario_count"], 1)
        strategy_rows.append(
            {
                "strategy": summary["strategy"],
                "profit_wins": summary["profit_wins"],
                "balanced_wins": summary["balanced_wins"],
                "average_rank": round(summary["average_rank_total"] / scenario_count, 2),
                "average_profit": f"${summary['average_profit_total'] / scenario_count:,.2f}",
                "average_balanced_score": round(
                    summary["balanced_score_total"] / scenario_count,
                    1,
                ),
                "liquidity_stress_count": summary["liquidity_stress_count"],
            }
        )
    strategy_rows.sort(
        key=lambda item: (
            -item["balanced_wins"],
            -item["average_balanced_score"],
            item["average_rank"],
        )
    )

    return "\n".join(
        [
            "# Market Scenario Comparison",
            "",
            "The same team strategies were run through each named market condition.",
            "",
            "## Scenario Winners",
            "",
            markdown_table(comparison_rows),
            "",
            "## Multi-Objective Strategy Robustness",
            "",
            markdown_table(strategy_rows),
            "",
            "Balanced score weights: 40% profit, 20% fill rate, 20% forecast accuracy, 20% cash-minus-debt, with a small liquidity-stress penalty.",
            "",
            "## Output Files",
            "",
            "- `market_scenario_comparison.csv` summarizes one winner per market scenario.",
            "- `market_scenario_team_results.csv` compares every team under every market scenario.",
            "- Each scenario also has its own subfolder with full team, product, forecast, and state CSV files.",
            "",
        ]
    )


def assignment_lookup(scenario: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Return team strategy metadata by team name."""
    return {
        item["team_name"]: {
            "archetype": item["archetype"].name,
            "strategy_key": item["strategy_key"],
            "strategy_label": item["strategy"]["label"],
        }
        for item in scenario["teams"]
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows to CSV with a stable union of all row fields."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_summary_markdown(scenario: dict[str, Any]) -> str:
    """Build a readable scenario summary for instructors."""
    team_results = scenario["team_results"]
    final_results = latest_round_results(team_results)
    strategy_rows = [
        {
            "team_name": item["team_name"],
            "archetype": item["archetype"].name,
            "strategy": item["strategy"]["label"],
        }
        for item in scenario["teams"]
    ]
    profit_rank = sorted(final_results, key=lambda item: item.profit, reverse=True)
    service_rank = sorted(final_results, key=lambda item: item.fill_rate, reverse=True)
    forecast_rank = sorted(final_results, key=lambda item: item.forecast_wape)
    liquidity_flags = [
        item for item in final_results if item.liquidity_stress_flag
    ]

    lines = [
        "# Strategy Simulation Summary",
        "",
        "This scenario was generated by `scripts/run_strategy_simulation.py` using the real Stage C engine.",
        "",
        "## Team Strategy Assignments",
        "",
        markdown_table(strategy_rows),
        "",
        "## Final Profit Ranking",
        "",
        markdown_table(
            [
                {
                    "rank": index,
                    "team_name": item.team_name,
                    "profit": f"${item.profit:,.2f}",
                    "revenue": f"${item.revenue:,.2f}",
                    "cash": f"${item.ending_cash_balance:,.2f}",
                    "debt": f"${item.short_term_debt_balance:,.2f}",
                    "forecast_wape": f"{item.forecast_wape:.1%}",
                    "fill_rate": f"{item.fill_rate:.1%}",
                    "liquidity_stress": item.liquidity_stress_flag,
                }
                for index, item in enumerate(profit_rank, start=1)
            ]
        ),
        "",
        "## Final Service Ranking",
        "",
        markdown_table(
            [
                {
                    "rank": index,
                    "team_name": item.team_name,
                    "fill_rate": f"{item.fill_rate:.1%}",
                    "lost_sales_units": item.lost_sales_units,
                    "backlog_units_end": item.backlog_units_end,
                    "reputation": item.reputation_after_round,
                }
                for index, item in enumerate(service_rank, start=1)
            ]
        ),
        "",
        "## Forecast Accuracy Ranking",
        "",
        markdown_table(
            [
                {
                    "rank": index,
                    "team_name": item.team_name,
                    "forecast_wape": f"{item.forecast_wape:.1%}",
                    "forecast_error_units": item.forecast_error_units,
                    "actual_demand_units": item.total_actual_demand_units,
                }
                for index, item in enumerate(forecast_rank, start=1)
            ]
        ),
        "",
        "## Liquidity Notes",
        "",
    ]
    if liquidity_flags:
        lines.extend(
            [
                markdown_table(
                    [
                        {
                            "team_name": item.team_name,
                            "cash": f"${item.ending_cash_balance:,.2f}",
                            "debt": f"${item.short_term_debt_balance:,.2f}",
                            "interest": f"${item.interest_expense:,.2f}",
                            "working_capital": f"${item.working_capital_requirement:,.2f}",
                        }
                        for item in liquidity_flags
                    ]
                ),
                "",
            ]
        )
    else:
        lines.extend(["No teams ended the final round with liquidity stress.", ""])

    lines.extend(
        [
            "## Reading The Output",
            "",
            "- `team_results.csv` is the main firm-level round history.",
            "- `product_results.csv` shows product-slot sales, inventory, defects, lifecycle, tech, and cannibalization.",
            "- `forecast_accuracy.csv` shows product-level forecast versus actual demand.",
            "- `final_team_states.csv` shows final cash, debt, capacity, reputation, and carryover state.",
            "",
        ]
    )
    return "\n".join(lines)


def latest_round_results(results: list[RoundResult]) -> list[RoundResult]:
    """Return only the latest round's team results."""
    if not results:
        return []
    latest_round = max(item.round_number for item in results)
    return [item for item in results if item.round_number == latest_round]


def markdown_table(rows: list[dict[str, Any]]) -> str:
    """Render a small list of dictionaries as a markdown table."""
    if not rows:
        return "_No rows._"
    headers = list(rows[0])
    separator = {header: "---" for header in headers}
    table_rows = [dict(zip(headers, headers, strict=True)), separator, *rows]
    lines = []
    for row in table_rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
