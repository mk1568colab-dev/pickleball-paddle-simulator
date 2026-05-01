"""Readable guide to the simulator's core formulas."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from engine import config
from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage


def _constant_frame(rows: list[tuple[str, object, str]]) -> pd.DataFrame:
    """Convert formula constants into a readable DataFrame."""
    return pd.DataFrame(rows, columns=["constant", "value", "meaning"])


def main() -> None:
    """Render a transparent formula guide for students and instructors."""
    ensure_app_storage()
    require_authenticated_user()

    st.title("Model Formula Guide")
    st.caption(
        "This page makes the simulator logic visible. The model is deterministic and rule-based, not an AI black box."
    )

    st.subheader("1. Market Demand Allocation")
    st.markdown(
        """
        The market report creates total segment demand:

        ```text
        premium_demand = total_demand * premium_share
        mid_demand = total_demand * mid_share
        beginner_demand = total_demand * beginner_share
        ```

        Each product receives a share of each segment based on its attractiveness:

        ```text
        product_segment_demand =
            segment_demand
            * product_attractiveness
            / total_attractiveness_of_all_products_in_segment
        ```
        """
    )

    st.subheader("2. Product Attractiveness")
    st.markdown(
        """
        The engine uses a weighted multi-attribute attraction model:

        ```text
        base_score =
            price_weight * price_competitiveness
          + quality_weight * quality_index * segment_quality_multiplier
          + archetype_fit_weight * archetype_segment_fit
          + product_alignment_weight * product_segment_alignment
          + product_fit_weight * product_demand_fit_modifier
          + reputation_weight * team_reputation
          + service_weight * service_readiness

        attractiveness =
            max(base_score, minimum_attractiveness)
          * lifecycle_multiplier
          * technology_modifier
          * launch_novelty_bonus_if_applicable
        ```
        """
    )
    st.dataframe(
        _constant_frame(
            [
                ("PRICE_ATTRACTIVENESS_WEIGHT", config.PRICE_ATTRACTIVENESS_WEIGHT, "How strongly segment customers respond to price."),
                ("QUALITY_ATTRACTIVENESS_WEIGHT", config.QUALITY_ATTRACTIVENESS_WEIGHT, "How strongly customers reward low defects and QC investment."),
                ("ARCHETYPE_FIT_WEIGHT", config.ARCHETYPE_FIT_WEIGHT, "How much the team's operating archetype fits a segment."),
                ("PRODUCT_SEGMENT_ALIGNMENT_WEIGHT", config.PRODUCT_SEGMENT_ALIGNMENT_WEIGHT, "How much a product benefits from targeting the segment it competes in."),
                ("PRODUCT_DEMAND_FIT_WEIGHT", config.PRODUCT_DEMAND_FIT_WEIGHT, "How much product-specific fit affects demand."),
                ("REPUTATION_ATTRACTIVENESS_WEIGHT", config.REPUTATION_ATTRACTIVENESS_WEIGHT, "How much team reputation affects demand."),
                ("SERVICE_READINESS_WEIGHT", config.SERVICE_READINESS_WEIGHT, "How much availability/readiness helps demand conversion."),
                ("MIN_ATTRACTIVENESS", config.MIN_ATTRACTIVENESS, "Lower bound so products do not fully disappear from allocation."),
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("3. Forecast Accuracy")
    st.markdown(
        """
        Product forecasts are compared against actual allocated demand:

        ```text
        forecast_error_units = actual_demand_units - forecast_units
        absolute_error_units = abs(actual_demand_units - forecast_units)
        forecast_bias_pct = forecast_error_units / max(forecast_units, 1)
        team_wape = sum(absolute_error_units) / max(sum(actual_demand_units), 1)
        ```
        """
    )

    st.subheader("4. Production, Quality, and Defects")
    st.markdown(
        """
        Shared firm constraints cap total production:

        ```text
        effective_capacity = installed_capacity + overtime_capacity
        feasible_production = min(total_planned_production, effective_capacity, available_raw_materials)
        ```

        Product defects depend on archetype, lifecycle, supplier pressure, utilization stress, technology risk, and QC spend:

        ```text
        qc_effect = qc_max_reduction * (1 - exp(-qc_rate * qc_budget_per_unit))

        defect_rate =
            base_defect_rate
          + product_defect_modifier
          + lifecycle_defect_modifier
          + supplier_defect_pressure
          + utilization_stress_penalty
          + technology_launch_penalty
          - qc_effect
        ```
        """
    )
    st.dataframe(
        _constant_frame(
            [
                ("QC_MAX_DEFECT_REDUCTION", config.QC_MAX_DEFECT_REDUCTION, "Maximum possible defect reduction from QC spend."),
                ("QC_EFFECTIVENESS_RATE", config.QC_EFFECTIVENESS_RATE, "How quickly QC spend creates diminishing-return benefits."),
                ("QC_COST_REALIZATION_FACTOR", config.QC_COST_REALIZATION_FACTOR, "Portion of QC spend charged as real production cost."),
                ("OVERTIME_COST_MULTIPLIER", config.OVERTIME_COST_MULTIPLIER, "Cost premium for overtime production."),
                ("OVERTIME_DEFECT_PENALTY", config.OVERTIME_DEFECT_PENALTY, "Defect penalty from operational stress caused by overtime."),
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("5. Cash, Debt, and Liquidity")
    st.markdown(
        """
        Cash is updated from the round economics:

        ```text
        ending_cash_before_borrowing =
            starting_cash
          + planned_borrowing
          + revenue
          - procurement_cost
          - production_cost
          - holding_cost
          - warranty_cost
          - backlog_cost
          - expansion_cost
          - innovation_investment
          - interest_expense

        if ending_cash_before_borrowing < 0:
            automatic_borrowing = abs(ending_cash_before_borrowing)
            ending_cash = 0
        ```

        Liquidity stress is triggered when cash/debt/working-capital pressure becomes high enough to matter for future management decisions.
        """
    )
    st.dataframe(
        _constant_frame(
            [
                ("PERIODIC_INTEREST_RATE", config.PERIODIC_INTEREST_RATE, "Interest charged on short-term debt each round."),
                ("LIQUIDITY_LOW_CASH_THRESHOLD", config.LIQUIDITY_LOW_CASH_THRESHOLD, "Low-cash warning threshold."),
                ("DEBT_TO_REVENUE_STRESS_THRESHOLD", config.DEBT_TO_REVENUE_STRESS_THRESHOLD, "Debt-to-revenue ratio that can trigger stress."),
                ("WORKING_CAPITAL_TO_REVENUE_STRESS_THRESHOLD", config.WORKING_CAPITAL_TO_REVENUE_STRESS_THRESHOLD, "Working-capital burden threshold."),
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("6. Product Development and Launch Readiness")
    st.markdown(
        """
        Development projects behave like a simple stage-gate process. A team first defines a project charter, then manages investment and testing over time.

        Fixed project charter fields include project name, target segment, target technology generation, intended product slot, planned launch round, cannibalization group, defect target, and demand-fit target. Once investment or testing begins, those settings are locked so teams cannot keep redesigning the project every round.

        Controllable project decisions include investment this round, testing intensity, launch-now-if-ready, and cancel project.

        Estimated required investment is based on project ambition:

        ```text
        required_investment =
            base_required_investment
          * segment_cost_multiplier
          * technology_generation_cost_multiplier
          * demand_fit_ambition_multiplier
          * defect_improvement_multiplier

        estimated_cost_range =
            required_investment
          * low/high uncertainty multiplier for the target technology generation
        ```

        Funding progress and readiness are then updated from investment and testing:

        ```text
        funding_progress =
            cumulative_investment / required_investment

        readiness_from_investment =
            readiness_scale * (1 - exp(-readiness_rate * funding_progress))

        readiness_score =
            readiness_from_funding_progress
          + testing_intensity_bonus
          - technology_complexity_penalty

        launch_ready if:
            cumulative_investment >= required_investment
            and readiness_score >= launch_readiness_threshold
            and current_round >= earliest_launch_round
        ```

        The Team Decisions page now shows these as three visible launch gates:

        ```text
        funding_gate = cumulative_investment >= required_investment
        readiness_gate = readiness_score >= launch_readiness_threshold
        timing_gate = current_round >= earliest_launch_round

        can_launch_now = funding_gate and readiness_gate and timing_gate
        ```

        The planned launch round is treated as a target date, not a permanent deadline. If a team misses the target date, the project can still launch in a later round after the funding, readiness, and timing gates are all satisfied.

        Strong funding plus strong testing can earn bounded expedite credit:

        ```text
        if funding_progress >= expedite_progress_threshold
           and testing_intensity >= expedite_testing_threshold:
               earliest_launch_round can move earlier
        ```

        This keeps the teaching tradeoff clear: teams can accelerate innovation, but only by spending cash and maintaining engineering discipline. High-tech products can be more attractive after launch, but they require more funding, more time, and more testing discipline.
        """
    )
    st.dataframe(
        _constant_frame(
            [
                ("NPD_REQUIRED_INVESTMENT_BASE", config.NPD_REQUIRED_INVESTMENT_BASE, "Base development cost before segment and technology adjustments."),
                ("NPD_SEGMENT_COST_MULTIPLIERS", config.NPD_SEGMENT_COST_MULTIPLIERS, "Development-cost multiplier by target customer segment."),
                ("NPD_TECH_GENERATION_COST_MULTIPLIERS", config.NPD_TECH_GENERATION_COST_MULTIPLIERS, "Development-cost multiplier by target technology generation."),
                ("NPD_DEMAND_FIT_AMBITION_COST_RATE", config.NPD_DEMAND_FIT_AMBITION_COST_RATE, "Cost pressure from targeting stronger demand fit."),
                ("NPD_DEFECT_IMPROVEMENT_COST_RATE", config.NPD_DEFECT_IMPROVEMENT_COST_RATE, "Cost pressure from targeting a lower defect baseline."),
                ("LAUNCH_READINESS_THRESHOLD", config.LAUNCH_READINESS_THRESHOLD, "Readiness score required before a project can launch."),
                ("READINESS_TESTING_BONUS_MAX", config.READINESS_TESTING_BONUS_MAX, "Maximum readiness benefit from testing intensity."),
                ("READINESS_COMPLEXITY_PENALTY_PER_TECH", config.READINESS_COMPLEXITY_PENALTY_PER_TECH, "Readiness penalty for higher technology generations."),
                ("NPD_TESTING_ADEQUACY_LOW_THRESHOLD", config.NPD_TESTING_ADEQUACY_LOW_THRESHOLD, "Below this testing level, students should expect readiness to stall."),
                ("NPD_TESTING_ADEQUACY_GOOD_THRESHOLD", config.NPD_TESTING_ADEQUACY_GOOD_THRESHOLD, "Testing level treated as good engineering discipline."),
                ("NPD_EXPEDITE_PROGRESS_THRESHOLD", config.NPD_EXPEDITE_PROGRESS_THRESHOLD, "Funding-progress threshold for launch-timing expedite credit."),
                ("NPD_EXPEDITE_TESTING_THRESHOLD", config.NPD_EXPEDITE_TESTING_THRESHOLD, "Testing-intensity threshold for launch-timing expedite credit."),
                ("NPD_MAX_EXPEDITE_ROUND_REDUCTION_BY_TECH_GENERATION", config.NPD_MAX_EXPEDITE_ROUND_REDUCTION_BY_TECH_GENERATION, "Maximum rounds that expediting can pull forward by tech generation."),
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("7. Optional Balanced Teaching Score")
    st.markdown(
        """
        The dashboard includes an optional classroom score to prevent pure profit-chasing:

        ```text
        balanced_score =
            100 * (
                0.40 * profit_percentile
              + 0.20 * fill_rate_percentile
              + 0.20 * forecast_accuracy_percentile
              + 0.20 * liquidity_health_percentile
              - liquidity_stress_penalty
            )
        ```

        This is a teaching score, not a fixed rule of the world. Instructors can use it when they want students to value profit, service, planning, and cash discipline together.
        """
    )


main()
