"""Configurable constants for the Stage B portfolio, lifecycle, and NPD engine."""

from __future__ import annotations


PRODUCT_SLOT_NAMES = ("A", "B", "C")
PROJECT_SLOT_NAMES = ("P1", "P2")
SEGMENTS = ("premium", "mid", "beginner")
LIFECYCLE_STAGES = ("launch", "growth", "maturity", "decline")
TECH_GENERATIONS = (1, 2, 3, 4)

SUPPLIER_NAMES = (
    "Offshore Value",
    "Balanced Source",
    "Premium Reliable",
)

SEGMENT_REFERENCE_PRICES: dict[str, float] = {
    "premium": 190.0,
    "mid": 132.0,
    "beginner": 92.0,
}

SEGMENT_PRICE_TOLERANCE: dict[str, float] = {
    "premium": 48.0,
    "mid": 28.0,
    "beginner": 18.0,
}

SEGMENT_QUALITY_MULTIPLIERS: dict[str, float] = {
    "premium": 1.35,
    "mid": 1.00,
    "beginner": 0.72,
}

PRODUCT_SEGMENT_ALIGNMENT: dict[str, dict[str, float]] = {
    "premium": {"premium": 1.15, "mid": 0.74, "beginner": 0.34},
    "mid": {"premium": 0.76, "mid": 1.10, "beginner": 0.74},
    "beginner": {"premium": 0.34, "mid": 0.76, "beginner": 1.18},
}

LIFECYCLE_AGE_THRESHOLDS: dict[str, tuple[int, int | None]] = {
    "launch": (0, 1),
    "growth": (2, 3),
    "maturity": (4, 6),
    "decline": (7, None),
}

LIFECYCLE_DEMAND_MULTIPLIERS: dict[str, float] = {
    "launch": 1.06,
    "growth": 1.14,
    "maturity": 1.00,
    "decline": 0.82,
}

LIFECYCLE_PRICE_TOLERANCE_MULTIPLIERS: dict[str, float] = {
    "launch": 1.04,
    "growth": 1.08,
    "maturity": 1.00,
    "decline": 0.90,
}

LIFECYCLE_DEFECT_MODIFIERS: dict[str, float] = {
    "launch": 0.006,
    "growth": 0.002,
    "maturity": 0.000,
    "decline": 0.003,
}

SUPPLIER_MATERIAL_COST_MULTIPLIERS: dict[str, float] = {
    "Offshore Value": 0.86,
    "Balanced Source": 1.00,
    "Premium Reliable": 1.15,
}

SUPPLIER_BASE_LEAD_TIMES: dict[str, float] = {
    "Offshore Value": 2.4,
    "Balanced Source": 1.3,
    "Premium Reliable": 0.9,
}

SUPPLIER_DEFECT_PRESSURE: dict[str, float] = {
    "Offshore Value": 0.012,
    "Balanced Source": 0.003,
    "Premium Reliable": -0.004,
}

SUPPLIER_RISK_EXPOSURE: dict[str, float] = {
    "Offshore Value": 1.30,
    "Balanced Source": 1.00,
    "Premium Reliable": 0.75,
}

SUPPLY_RISK_INDEX: dict[str, float] = {
    "Low": 0.85,
    "Moderate": 1.00,
    "High": 1.25,
}

EXPEDITED_ORDER_COST_UPLIFT = 0.18
EXPEDITED_LEAD_TIME_REDUCTION = 0.80

BASE_MATERIAL_COST_SHARE = 0.45
BASE_CONVERSION_COST_SHARE = 0.55

OVERTIME_COST_MULTIPLIER = 1.35
OVERTIME_DEFECT_PENALTY = 0.012
CAPACITY_EXPANSION_CAPEX_PER_UNIT = 72.0

QC_MAX_DEFECT_REDUCTION = 0.038
QC_EFFECTIVENESS_RATE = 0.30
QC_COST_REALIZATION_FACTOR = 1.00

HOLDING_COST_PER_UNIT = 6.0
RAW_MATERIAL_HOLDING_COST_PER_UNIT = 2.0
WARRANTY_COST_FACTOR = 45.0
BACKLOG_PENALTY_PER_UNIT = 10.0
PERIODIC_INTEREST_RATE = 0.022
LIQUIDITY_LOW_CASH_THRESHOLD = 5_000.0
DEBT_TO_REVENUE_STRESS_THRESHOLD = 0.40
WORKING_CAPITAL_TO_REVENUE_STRESS_THRESHOLD = 0.32
LIQUIDITY_STRESS_REPUTATION_PENALTY = 0.75

FORECAST_LOW_COVERAGE_RATIO = 0.80
FORECAST_EXCESS_PRODUCTION_RATIO = 1.20
FORECAST_MISMATCH_WARNING_RATIO = 0.35

STARTING_RAW_MATERIAL_COVERAGE = 1.0

UTILIZATION_STRESS_THRESHOLDS: dict[str, float] = {
    "moderate": 0.85,
    "high": 0.95,
}

UTILIZATION_STRESS_PENALTIES: dict[str, float] = {
    "moderate": 0.008,
    "high": 0.020,
}

PRICE_ATTRACTIVENESS_WEIGHT = 28.0
QUALITY_ATTRACTIVENESS_WEIGHT = 18.0
ARCHETYPE_FIT_WEIGHT = 18.0
PRODUCT_SEGMENT_ALIGNMENT_WEIGHT = 16.0
PRODUCT_DEMAND_FIT_WEIGHT = 14.0
REPUTATION_ATTRACTIVENESS_WEIGHT = 0.18
SERVICE_READINESS_WEIGHT = 8.0
MIN_ATTRACTIVENESS = 1.0

TECH_POSITIVE_GAP_BONUS = 0.08
TECH_NEGATIVE_GAP_PENALTY = 0.13
TECH_MIN_ATTRACTIVENESS_MODIFIER = 0.72
TECH_MAX_ATTRACTIVENESS_MODIFIER = 1.20
TECH_NEWER_THAN_MARKET_DEFECT_PENALTY = 0.004
TECH_PREMIUM_SEGMENT_BONUS = 0.02

LAUNCH_NOVELTY_BONUS = 1.08
DECLINE_PRICE_PRESSURE_PENALTY = 0.08
RETIREMENT_LIQUIDATION_RECOVERY_RATE = 0.45

NPD_REQUIRED_INVESTMENT_BASE = 7_500.0
NPD_REQUIRED_INVESTMENT_BY_SEGMENT: dict[str, float] = {
    "premium": 3_500.0,
    "mid": 2_200.0,
    "beginner": 1_500.0,
}
NPD_REQUIRED_INVESTMENT_BY_TECH_GENERATION: dict[int, float] = {
    1: 0.0,
    2: 2_500.0,
    3: 5_000.0,
    4: 8_500.0,
}

NPD_MIN_DEVELOPMENT_ROUNDS_BY_TECH_GENERATION: dict[int, int] = {
    1: 1,
    2: 1,
    3: 2,
    4: 3,
}

READINESS_INVESTMENT_SCALE = 86.0
READINESS_INVESTMENT_RATE = 1.8
READINESS_TESTING_BONUS_MAX = 18.0
READINESS_COMPLEXITY_PENALTY_PER_TECH = 3.5
LAUNCH_READINESS_THRESHOLD = 84.0

LAUNCH_DEFECT_PENALTY = 0.010
LAUNCH_SUPPLY_STABILIZATION_PENALTY = 0.003
MAX_LAUNCHES_PER_ROUND = 1

BASE_CANNIBALIZATION_RATE = 0.05
SAME_GROUP_CANNIBALIZATION_FACTOR = 1.60
SAME_SEGMENT_CANNIBALIZATION_FACTOR = 1.25
DIFFERENT_SEGMENT_CANNIBALIZATION_FACTOR = 0.70
LIFECYCLE_GAP_CANNIBALIZATION_FACTOR = 1.25
TECH_ADVANTAGE_CANNIBALIZATION_FACTOR = 0.22
LAUNCH_CANNIBALIZATION_BOOST = 1.15
MAX_CANNIBALIZATION_TRANSFER_SHARE = 0.18

REPUTATION_UPDATE_WEIGHTS: dict[str, float] = {
    "defect_target": 0.030,
    "defect_weight": 85.0,
    "fill_rate_baseline": 0.88,
    "fill_rate_weight": 14.0,
    "lost_sales_weight": 14.0,
    "backlog_weight": 8.0,
    "quality_sensitivity_multiplier": 0.80,
}
