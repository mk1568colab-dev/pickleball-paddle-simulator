"""Configurable constants for the OM round engine."""

from __future__ import annotations


PRICE_MAP: dict[str, float] = {
    "Beginner": 90.0,
    "Mid": 130.0,
    "Premium": 180.0,
}

QUALITY_DEFECT_ADJUSTMENTS: dict[str, float] = {
    "Basic": 0.030,
    "Standard": 0.000,
    "High": -0.020,
}

QUALITY_COST_MULTIPLIERS: dict[str, float] = {
    "Basic": 0.94,
    "Standard": 1.00,
    "High": 1.08,
}

SUPPLY_RISK_DEFECT_ADJUSTMENTS: dict[str, float] = {
    "Low": -0.005,
    "Moderate": 0.000,
    "High": 0.020,
}

CAPACITY_PLAN_MULTIPLIERS: dict[str, float] = {
    "Reduce": 0.90,
    "Maintain": 1.00,
    "Expand": 1.00,
    "Selective Expansion": 1.05,
}

EXPANSION_COSTS: dict[str, float] = {
    "Reduce": 0.0,
    "Maintain": 0.0,
    "Expand": 6000.0,
    "Selective Expansion": 3000.0,
}

FUTURE_CAPACITY_GAINS: dict[str, int] = {
    "Reduce": 0,
    "Maintain": 0,
    "Expand": 80,
    "Selective Expansion": 40,
}

HOLDING_COST_PER_UNIT = 6.0
WARRANTY_COST_FACTOR = 45.0

PRICE_SEGMENT_SCORES: dict[str, dict[str, float]] = {
    "Premium": {"premium": 26.0, "mid": 12.0, "beginner": 4.0},
    "Mid": {"premium": 16.0, "mid": 24.0, "beginner": 14.0},
    "Beginner": {"premium": 6.0, "mid": 14.0, "beginner": 24.0},
}

QUALITY_SEGMENT_SCORES: dict[str, dict[str, float]] = {
    "High": {"premium": 24.0, "mid": 16.0, "beginner": 8.0},
    "Standard": {"premium": 14.0, "mid": 20.0, "beginner": 16.0},
    "Basic": {"premium": 6.0, "mid": 12.0, "beginner": 22.0},
}

INVENTORY_POSTURE_MODIFIERS: dict[str, float] = {
    "Lean": -1.0,
    "Balanced": 0.5,
    "Build": 1.5,
}

CAPACITY_STRESS_ADJUSTMENTS: dict[str, float] = {
    "moderate_threshold": 0.85,
    "moderate_increase": 0.010,
    "high_threshold": 0.95,
    "high_increase": 0.020,
}

REPUTATION_UPDATE_WEIGHTS: dict[str, float] = {
    "defect_target": 0.030,
    "defect_weight": 80.0,
    "fill_rate_baseline": 0.85,
    "fill_rate_weight": 12.0,
    "stockout_weight": 10.0,
    "quality_sensitivity_multiplier": 0.75,
}

SEGMENT_FIT_WEIGHT = 35.0
REPUTATION_ATTRACTIVENESS_WEIGHT = 0.20
MIN_ATTRACTIVENESS = 1.0
