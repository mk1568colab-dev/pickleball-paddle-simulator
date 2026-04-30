"""Instructor-facing market scenario presets.

These presets change only public market-report inputs. They are meant to help
instructors create different teaching environments without editing engine code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models.schemas import MarketReport


@dataclass(frozen=True)
class MarketScenarioPreset:
    """Reusable scenario configuration for one classroom round."""

    name: str
    description: str
    teaching_focus: str
    report_updates: dict[str, Any]


MARKET_SCENARIO_PRESETS: dict[str, MarketScenarioPreset] = {
    "Stable Market": MarketScenarioPreset(
        name="Stable Market",
        description="Balanced demand, normal input costs, and moderate technology pressure.",
        teaching_focus="Good baseline for introducing the simulator and comparing core strategies.",
        report_updates={
            "total_demand": 1200,
            "premium_share": 0.28,
            "mid_share": 0.46,
            "beginner_share": 0.26,
            "material_cost_index": 1.00,
            "supply_risk": "Moderate",
            "quality_sensitivity": 0.55,
            "current_market_generation": 2,
            "technology_shift_rate": 0.15,
            "premium_tech_adoption": 0.75,
            "mid_market_tech_adoption": 0.55,
            "beginner_price_pressure": 0.55,
            "event": "Stable market: balanced demand and moderate operating pressure.",
        },
    ),
    "Demand Boom": MarketScenarioPreset(
        name="Demand Boom",
        description="Higher total demand with only mild cost pressure.",
        teaching_focus="Capacity planning, service levels, and inventory readiness.",
        report_updates={
            "total_demand": 1550,
            "premium_share": 0.30,
            "mid_share": 0.44,
            "beginner_share": 0.26,
            "material_cost_index": 1.05,
            "supply_risk": "Moderate",
            "quality_sensitivity": 0.55,
            "current_market_generation": 2,
            "technology_shift_rate": 0.18,
            "premium_tech_adoption": 0.78,
            "mid_market_tech_adoption": 0.58,
            "beginner_price_pressure": 0.50,
            "event": "Demand boom: teams can grow, but shortages and overstretch are visible.",
        },
    ),
    "Supply Shock": MarketScenarioPreset(
        name="Supply Shock",
        description="Materials become expensive and unreliable.",
        teaching_focus="Supplier mix, raw-material planning, QC, and liquidity discipline.",
        report_updates={
            "total_demand": 1150,
            "premium_share": 0.30,
            "mid_share": 0.42,
            "beginner_share": 0.28,
            "material_cost_index": 1.30,
            "supply_risk": "High",
            "quality_sensitivity": 0.70,
            "current_market_generation": 2,
            "technology_shift_rate": 0.12,
            "premium_tech_adoption": 0.74,
            "mid_market_tech_adoption": 0.50,
            "beginner_price_pressure": 0.62,
            "event": "Supply shock: procurement and working-capital decisions become central.",
        },
    ),
    "Quality-Sensitive Market": MarketScenarioPreset(
        name="Quality-Sensitive Market",
        description="Customers punish defects and reward reliable products.",
        teaching_focus="QC investment, supplier quality, warranty cost, and reputation.",
        report_updates={
            "total_demand": 1200,
            "premium_share": 0.40,
            "mid_share": 0.40,
            "beginner_share": 0.20,
            "material_cost_index": 1.05,
            "supply_risk": "Moderate",
            "quality_sensitivity": 0.90,
            "current_market_generation": 2,
            "technology_shift_rate": 0.18,
            "premium_tech_adoption": 0.82,
            "mid_market_tech_adoption": 0.62,
            "beginner_price_pressure": 0.45,
            "event": "Quality-sensitive market: reliability affects demand, warranty cost, and reputation.",
        },
    ),
    "Technology Shift": MarketScenarioPreset(
        name="Technology Shift",
        description="The market moves toward a newer product generation.",
        teaching_focus="NPD investment, launch timing, retirement, and obsolescence risk.",
        report_updates={
            "total_demand": 1250,
            "premium_share": 0.45,
            "mid_share": 0.38,
            "beginner_share": 0.17,
            "material_cost_index": 1.10,
            "supply_risk": "Moderate",
            "quality_sensitivity": 0.68,
            "current_market_generation": 3,
            "technology_shift_rate": 0.35,
            "premium_tech_adoption": 0.92,
            "mid_market_tech_adoption": 0.72,
            "beginner_price_pressure": 0.55,
            "event": "Technology shift: newer generations gain appeal while older products lose edge.",
        },
    ),
    "Price War": MarketScenarioPreset(
        name="Price War",
        description="Beginner demand grows and customers become price sensitive.",
        teaching_focus="Margin discipline, low-cost sourcing, defects, and volume risk.",
        report_updates={
            "total_demand": 1300,
            "premium_share": 0.18,
            "mid_share": 0.35,
            "beginner_share": 0.47,
            "material_cost_index": 0.95,
            "supply_risk": "Moderate",
            "quality_sensitivity": 0.35,
            "current_market_generation": 2,
            "technology_shift_rate": 0.10,
            "premium_tech_adoption": 0.65,
            "mid_market_tech_adoption": 0.42,
            "beginner_price_pressure": 0.90,
            "event": "Price war: high volume is available, but weak margins can destroy profit.",
        },
    ),
    "Cash Crunch": MarketScenarioPreset(
        name="Cash Crunch",
        description="Demand softens while material cost and supply risk rise.",
        teaching_focus="Cash, borrowing, working capital, and cautious investment timing.",
        report_updates={
            "total_demand": 1050,
            "premium_share": 0.25,
            "mid_share": 0.43,
            "beginner_share": 0.32,
            "material_cost_index": 1.18,
            "supply_risk": "High",
            "quality_sensitivity": 0.60,
            "current_market_generation": 2,
            "technology_shift_rate": 0.16,
            "premium_tech_adoption": 0.72,
            "mid_market_tech_adoption": 0.54,
            "beginner_price_pressure": 0.72,
            "event": "Cash crunch: teams must protect liquidity while still serving demand.",
        },
    ),
}


def apply_market_scenario(report: MarketReport, preset_name: str) -> MarketReport:
    """Return a new market report with the selected preset applied."""
    preset = MARKET_SCENARIO_PRESETS[preset_name]
    payload = report.to_dict()
    payload.update(preset.report_updates)
    payload["round_number"] = report.round_number
    return MarketReport.from_dict(payload)
