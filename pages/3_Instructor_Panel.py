"""Instructor tools for running the Stage C portfolio engine."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from engine.simulator import build_round_validation_rows, run_round
from utils.auth import require_admin, require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import (
    load_market_report,
    load_product_decisions,
    load_product_development_projects,
    load_product_lines,
    load_round_status,
    load_team_decisions,
    load_team_states,
    load_users,
    reset_runtime_data,
    save_forecast_accuracy_results,
    save_product_development_projects,
    save_product_lines,
    save_product_round_results,
    save_round_results,
    set_round_submissions_open,
    save_team_states,
)


def _frame(records: list[dict[str, object]]) -> pd.DataFrame:
    """Convert dictionaries into a display DataFrame."""
    return pd.DataFrame(records) if records else pd.DataFrame()


def _submission_status_rows(
    current_round: int,
    team_decisions,
    product_decisions,
) -> list[dict[str, object]]:
    """Build a classroom submission status table from team accounts."""
    decision_team_names = {item.team_name.lower() for item in team_decisions}
    product_decision_counts: dict[str, int] = {}
    forecast_counts: dict[str, int] = {}
    for decision in product_decisions:
        key = decision.team_name.lower()
        product_decision_counts[key] = product_decision_counts.get(key, 0) + 1
        if decision.is_active and decision.forecast_units > 0:
            forecast_counts[key] = forecast_counts.get(key, 0) + 1

    rows: list[dict[str, object]] = []
    for user in load_users(role="team_leader", is_active=True):
        if not user.team_name:
            continue
        key = user.team_name.lower()
        rows.append(
            {
                "round_number": current_round,
                "username": user.username,
                "team_name": user.team_name,
                "firm_submission_saved": key in decision_team_names,
                "product_slots_saved": product_decision_counts.get(key, 0),
                "active_product_forecasts_saved": forecast_counts.get(key, 0),
            }
        )
    return rows


def main() -> None:
    """Render the instructor control page."""
    ensure_app_storage()
    user = require_authenticated_user()
    require_admin(user)

    st.title("Instructor Panel")
    st.caption(
        "Admin-only controls for reviewing Stage C submissions, validating planning discipline and liquidity risk, and running the round engine."
    )

    market_report = load_market_report()
    current_round = market_report.round_number
    round_status = load_round_status(current_round)
    team_decisions = load_team_decisions(round_number=current_round)
    product_decisions = load_product_decisions(round_number=current_round)
    development_projects = load_product_development_projects()
    product_lines = load_product_lines()
    team_states = load_team_states()

    validation_rows = build_round_validation_rows(
        market_report=market_report,
        team_decisions=team_decisions,
        product_lines=product_lines,
        product_decisions=product_decisions,
        development_projects=development_projects,
        existing_states=team_states,
    )
    validation_frame = _frame(validation_rows)
    invalid_mix_count = int((~validation_frame["supplier_mix_valid"]).sum()) if not validation_frame.empty else 0
    infeasible_count = int(validation_frame["obviously_infeasible"].sum()) if not validation_frame.empty else 0
    zero_active_count = int(validation_frame["zero_active_products"].sum()) if not validation_frame.empty else 0
    multi_launch_count = int(validation_frame["multiple_launch_requests"].sum()) if not validation_frame.empty else 0
    ready_projects_total = int(validation_frame["launch_ready_projects"].sum()) if not validation_frame.empty else 0
    missing_forecasts_count = int(validation_frame["missing_forecasts"].sum()) if not validation_frame.empty else 0
    forecast_mismatch_count = int(validation_frame["forecast_plan_mismatch"].sum()) if not validation_frame.empty else 0
    likely_cash_shortfall_count = int(validation_frame["likely_cash_shortfall"].sum()) if not validation_frame.empty else 0

    st.subheader("Pre-Run Validation Summary")
    summary_row_one = st.columns(5)
    summary_row_one[0].metric("Current Round", current_round)
    summary_row_one[1].metric("Teams Submitted", len(team_decisions))
    summary_row_one[2].metric("Invalid Supplier Mix", invalid_mix_count)
    summary_row_one[3].metric("Infeasible Plans", infeasible_count)
    summary_row_one[4].metric("Missing Forecasts", missing_forecasts_count)

    summary_row_two = st.columns(4)
    summary_row_two[0].metric("Forecast Mismatches", forecast_mismatch_count)
    summary_row_two[1].metric("Likely Cash Shortfalls", likely_cash_shortfall_count)
    summary_row_two[2].metric("Pipeline Projects", len([item for item in development_projects if item.is_pipeline_active()]))
    summary_row_two[3].metric("Launch-Ready Projects", ready_projects_total)

    if invalid_mix_count:
        st.warning(
            "One or more teams have supplier-mix percentages that do not sum to 100. The engine will normalize them, but they should revise these rows."
        )
    if infeasible_count:
        st.warning(
            "One or more teams planned more total production than their shared capacity or raw-material position supports."
        )
    if missing_forecasts_count:
        st.warning(
            "One or more active product slots still have a zero or missing forecast."
        )
    if forecast_mismatch_count:
        st.warning(
            "One or more teams have a material mismatch between submitted forecast and production plan."
        )
    if likely_cash_shortfall_count:
        st.warning(
            "One or more teams are likely to require borrowing based on their current submission."
        )
    if zero_active_count:
        st.warning(
            "One or more teams have no active products selected. They will not compete for demand unless a launch occurs this round."
        )
    if multi_launch_count:
        st.warning(
            "One or more teams requested multiple launches. The engine will only allow one launch per team per round."
        )

    st.subheader("Submission Controls")
    status_cols = st.columns(4)
    status_cols[0].metric("Round", current_round)
    status_cols[1].metric(
        "Submission Status",
        "Open" if round_status.submissions_open else "Closed",
    )
    status_cols[2].metric("Active Team Accounts", len(load_users(role="team_leader", is_active=True)))
    status_cols[3].metric("Firm Submissions", len(team_decisions))

    control_cols = st.columns(2)
    if control_cols[0].button("Open Team Submissions"):
        set_round_submissions_open(
            current_round,
            True,
            "Instructor reopened submissions.",
        )
        st.success(f"Round {current_round} submissions are open.")
        st.rerun()
    if control_cols[1].button("Close Team Submissions"):
        set_round_submissions_open(
            current_round,
            False,
            "Instructor closed submissions before running the round.",
        )
        st.warning(f"Round {current_round} submissions are closed.")
        st.rerun()

    submission_status_frame = _frame(
        _submission_status_rows(current_round, team_decisions, product_decisions)
    )
    if submission_status_frame.empty:
        st.info("Create team leader accounts to see a submission checklist.")
    else:
        st.dataframe(submission_status_frame, use_container_width=True, hide_index=True)

    st.subheader("Round Controls")
    if round_status.submissions_open:
        st.info(
            "Submissions are still open. You can run the round now, but closing submissions first is cleaner for classroom use."
        )
    if st.button("Run Round", type="primary"):
        if not team_decisions:
            st.error("Save at least one team submission before running the round.")
        else:
            (
                round_results,
                product_results,
                updated_states,
                updated_product_lines,
                updated_projects,
                forecast_accuracy_results,
            ) = run_round(
                market_report=market_report,
                team_decisions=team_decisions,
                product_lines=product_lines,
                product_decisions=product_decisions,
                development_projects=development_projects,
                existing_states=team_states,
            )
            save_round_results(round_results)
            save_product_round_results(product_results)
            save_forecast_accuracy_results(forecast_accuracy_results)
            save_team_states(updated_states)
            save_product_lines(updated_product_lines)
            save_product_development_projects(updated_projects)
            st.success(
                f"Round completed for {len(round_results)} teams, {len(product_results)} product slots, {len(forecast_accuracy_results)} forecast rows, and {len(updated_projects)} project slots."
            )

    if st.button("Reset Decisions, Pipeline, Results, and Team State"):
        reset_runtime_data()
        st.warning(
            "Runtime decisions, development projects, product slots, results, and team states have been reset."
        )

    st.subheader("Validation Detail")
    if validation_frame.empty:
        st.info("No team submissions are saved for the current round yet.")
    else:
        st.dataframe(validation_frame, use_container_width=True, hide_index=True)

    st.subheader("Saved Firm-Level Decisions")
    firm_decision_frame = _frame([item.to_dict() for item in team_decisions])
    if firm_decision_frame.empty:
        st.info("No firm-level decisions are saved for the current round yet.")
    else:
        st.dataframe(
            firm_decision_frame[
                [
                    "team_name",
                    "archetype",
                    "overtime_capacity_units",
                    "capacity_expansion_units",
                    "raw_material_order_qty",
                    "supplier_mix_offshore_pct",
                    "supplier_mix_balanced_pct",
                    "supplier_mix_premium_pct",
                    "expedited_order_share_pct",
                    "max_backorder_units",
                    "planned_borrowing_amount",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Saved Product-Level Decisions")
    product_decision_frame = _frame([item.to_dict() for item in product_decisions])
    if product_decision_frame.empty:
        st.info("No product-slot decisions are saved for the current round yet.")
    else:
        st.dataframe(
            product_decision_frame[
                [
                    "team_name",
                    "slot_name",
                    "product_name",
                    "is_active",
                    "target_segment",
                    "selling_price_per_unit",
                    "forecast_units",
                    "planned_production_units",
                    "qc_budget_per_unit",
                    "target_finished_goods_inventory",
                    "retire_flag",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Saved Development Projects")
    project_frame = _frame([item.to_dict() for item in development_projects if item.is_defined()])
    if project_frame.empty:
        st.info("No development projects are saved yet.")
    else:
        st.dataframe(
            project_frame[
                [
                    "team_name",
                    "project_slot_name",
                    "project_name",
                    "status",
                    "target_segment",
                    "target_tech_generation",
                    "intended_slot_name",
                    "cumulative_investment",
                    "investment_this_round",
                    "launch_readiness_score",
                    "planned_launch_round",
                    "earliest_launch_round",
                    "launch_now",
                    "cancel_now",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Current Portfolio Snapshot")
    product_line_frame = _frame([item.to_dict() for item in product_lines])
    if product_line_frame.empty:
        st.info("Product slots will appear after a team opens the decision page or after the first round runs.")
    else:
        st.dataframe(
            product_line_frame[
                [
                    "team_name",
                    "slot_name",
                    "product_name",
                    "is_active",
                    "target_segment",
                    "lifecycle_stage",
                    "age_in_rounds",
                    "tech_generation",
                    "inventory_units",
                    "backlog_units",
                    "retirement_flag",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Notes")
    st.info(
        "Use `Admin User Management` to create accounts and reset passwords. This page focuses on validating Stage C portfolio, forecast, and liquidity submissions before the round is executed."
    )


main()
