"""Instructor tools for running the Stage C portfolio engine."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from engine.simulator import build_round_validation_rows, run_round
from utils.auth import require_admin, require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.demand_protocol import committed_report, complete_demand_round, demand_status
from utils.submission_fallback import complete_round_inputs, save_fallback_decisions
from utils.repository import (
    advance_market_report_to_next_round,
    factory_reset_game_data,
    load_market_report,
    load_product_decisions,
    load_product_development_projects,
    load_product_lines,
    load_round_status,
    load_team_decisions,
    load_team_states,
    load_users,
    save_forecast_accuracy_results,
    save_product_development_projects,
    save_product_lines,
    save_product_round_results,
    save_round_results,
    save_team_states,
    set_round_submissions_open,
)


def _frame(records: list[dict[str, object]]) -> pd.DataFrame:
    """Convert dictionaries into a display DataFrame."""
    return pd.DataFrame(records) if records else pd.DataFrame()


def _clear_game_editor_session_state() -> None:
    """Clear cached decision-editor values after a full game reset."""
    for key in list(st.session_state):
        if key.startswith("stage_b_"):
            del st.session_state[key]


def _inject_instructor_cockpit_css() -> None:
    """Apply compact instructor styling without changing execution logic."""
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            min-width: 12rem !important;
            width: 12rem !important;
        }
        section[data-testid="stSidebar"] img {
            max-width: 80px !important;
        }
        div[data-testid="stSidebarContent"] {
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }
        div[data-testid="stSidebarContent"] p,
        div[data-testid="stSidebarContent"] a,
        div[data-testid="stSidebarContent"] span {
            font-size: 0.82rem;
        }
        .block-container {
            max-width: 96rem;
            padding-top: 1.7rem;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #d7e0ec;
            border-radius: 0.45rem;
            padding: 0.55rem 0.65rem;
            min-height: 4.0rem;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.76rem;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.04rem;
        }
        div[data-testid="stVerticalBlock"] {
            gap: 0.58rem;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 0.55rem;
        }
        .kiki-panel-note {
            color: #5a667a;
            font-size: 0.82rem;
            margin-top: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def _status_label(condition: bool, good: str = "OK", bad: str = "Needs Review") -> str:
    """Return compact classroom status text."""
    return good if condition else bad


def _readiness_rows(
    submission_status_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    team_decisions,
) -> list[dict[str, object]]:
    """Build an instructor-facing team readiness board."""
    validation_by_team = (
        {
            str(row["team_name"]).lower(): row
            for row in validation_frame.to_dict("records")
        }
        if not validation_frame.empty
        else {}
    )
    decision_by_team = {decision.team_name.lower(): decision for decision in team_decisions}
    rows: list[dict[str, object]] = []
    status_records = (
        submission_status_frame.to_dict("records")
        if not submission_status_frame.empty
        else []
    )

    known_status_names = {str(row["team_name"]).lower() for row in status_records}
    for team_key in validation_by_team:
        if team_key not in known_status_names:
            status_records.append(
                {
                    "round_number": "",
                    "username": "",
                    "team_name": validation_by_team[team_key]["team_name"],
                    "firm_submission_saved": True,
                    "product_slots_saved": "",
                    "active_product_forecasts_saved": "",
                }
            )

    for status_row in sorted(status_records, key=lambda item: str(item["team_name"]).lower()):
        team_name = str(status_row["team_name"])
        team_key = team_name.lower()
        validation = validation_by_team.get(team_key)
        firm_saved = bool(status_row.get("firm_submission_saved", False))
        decision = decision_by_team.get(team_key)

        if validation is None:
            rows.append(
                {
                    "team_name": team_name,
                    "archetype": decision.archetype if decision else "-",
                    "firm_saved": "No",
                    "product_slots": status_row.get("product_slots_saved", 0),
                    "forecasts": status_row.get("active_product_forecasts_saved", 0),
                    "supplier": "-",
                    "feasibility": "-",
                    "cash": "-",
                    "launch": "-",
                    "status": "Auto-carry pending",
                }
            )
            continue

        launch_requests = int(validation.get("launch_requests", 0))
        launch_ready = int(validation.get("launch_ready_projects", 0))
        if bool(validation.get("multiple_launch_requests", False)):
            launch_status = "Multiple requests"
        elif launch_requests and launch_ready:
            launch_status = f"{launch_ready} ready"
        elif launch_requests:
            launch_status = "Requested, not ready"
        elif launch_ready:
            launch_status = f"{launch_ready} ready, not requested"
        else:
            launch_status = "None"

        issue_count = sum(
            [
                not firm_saved,
                not bool(validation.get("supplier_mix_valid", False)),
                bool(validation.get("obviously_infeasible", False)),
                int(validation.get("missing_forecasts", 0)) > 0,
                bool(validation.get("forecast_plan_mismatch", False)),
                bool(validation.get("likely_cash_shortfall", False)),
                bool(validation.get("zero_active_products", False)),
                bool(validation.get("multiple_launch_requests", False)),
            ]
        )
        rows.append(
            {
                "team_name": team_name,
                "archetype": decision.archetype if decision else "-",
                "firm_saved": "Yes" if firm_saved else "No",
                "product_slots": status_row.get("product_slots_saved", 0),
                "forecasts": status_row.get("active_product_forecasts_saved", 0),
                "supplier": (
                    "OK"
                    if bool(validation.get("supplier_mix_valid", False))
                    else f"{float(validation.get('supplier_mix_total_pct', 0.0)):.0f}%"
                ),
                "feasibility": (
                    "Over plan"
                    if bool(validation.get("obviously_infeasible", False))
                    else "OK"
                ),
                "cash": (
                    "Shortfall"
                    if bool(validation.get("likely_cash_shortfall", False))
                    else "OK"
                ),
                "launch": launch_status,
                "status": "Ready" if issue_count == 0 else f"{issue_count} issue(s)",
            }
        )

    return rows


def _validation_exception_rows(
    submission_status_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
) -> list[dict[str, object]]:
    """Return only teams requiring instructor attention."""
    rows: list[dict[str, object]] = []
    if not submission_status_frame.empty:
        for status_row in submission_status_frame.to_dict("records"):
            if not bool(status_row.get("firm_submission_saved", False)):
                rows.append(
                    {
                        "team_name": status_row["team_name"],
                        "area": "Submission",
                        "issue": "No firm-level decision saved for the current round.",
                        "suggested_action": "Run with the previous plan (starting defaults if none), without development spending or launch/cancel actions.",
                    }
                )

    if validation_frame.empty:
        return rows

    for row in validation_frame.to_dict("records"):
        team_name = row["team_name"]
        if not bool(row.get("supplier_mix_valid", False)):
            rows.append(
                {
                    "team_name": team_name,
                    "area": "Supplier mix",
                    "issue": f"Supplier mix totals {float(row.get('supplier_mix_total_pct', 0.0)):.0f}%.",
                    "suggested_action": "Ask the team to rebalance to 100%.",
                }
            )
        if bool(row.get("obviously_infeasible", False)):
            rows.append(
                {
                    "team_name": team_name,
                    "area": "Feasibility",
                    "issue": "Planned production exceeds feasible capacity or materials.",
                    "suggested_action": "Confirm whether the team expects output to be capped.",
                }
            )
        if int(row.get("missing_forecasts", 0)) > 0:
            rows.append(
                {
                    "team_name": team_name,
                    "area": "Forecast",
                    "issue": f"{int(row.get('missing_forecasts', 0))} active product(s) have zero forecast.",
                    "suggested_action": "Ask the team to enter product forecasts.",
                }
            )
        if bool(row.get("forecast_plan_mismatch", False)):
            rows.append(
                {
                    "team_name": team_name,
                    "area": "S&OP",
                    "issue": "Forecast and production plan are materially mismatched.",
                    "suggested_action": "Ask whether the gap is intentional.",
                }
            )
        if bool(row.get("likely_cash_shortfall", False)):
            rows.append(
                {
                    "team_name": team_name,
                    "area": "Cash",
                    "issue": "Plan is likely to need borrowing.",
                    "suggested_action": "Discuss liquidity before running.",
                }
            )
        if bool(row.get("zero_active_products", False)):
            rows.append(
                {
                    "team_name": team_name,
                    "area": "Portfolio",
                    "issue": "No active product will compete unless a launch occurs.",
                    "suggested_action": "Check active products and launch request.",
                }
            )
        if bool(row.get("multiple_launch_requests", False)):
            rows.append(
                {
                    "team_name": team_name,
                    "area": "Launch",
                    "issue": "Multiple launch requests are selected.",
                    "suggested_action": "Only one launch is allowed per team per round.",
                }
            )
    return rows


def _run_round_and_advance(
    market_report,
    team_decisions,
    product_decisions,
    development_projects,
    product_lines,
    team_states,
) -> None:
    """Run the deterministic engine and advance the classroom round."""
    if load_round_status(market_report.round_number).submissions_open:
        st.error("Close submissions before running the round.")
        return
    try:
        market_report = committed_report(market_report)
    except ValueError as exc:
        st.error(str(exc))
        return
    team_decisions, product_decisions, development_projects, product_lines, fallback = complete_round_inputs(
        market_report.round_number, team_decisions, product_decisions,
        development_projects, product_lines, team_states,
    )
    if not team_decisions:
        st.error("Create at least one active team before running the round.")
        return
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
    save_fallback_decisions(market_report.round_number, team_decisions, product_decisions, fallback)
    save_round_results(round_results)
    save_product_round_results(product_results)
    save_forecast_accuracy_results(forecast_accuracy_results)
    save_team_states(updated_states)
    save_product_lines(updated_product_lines)
    save_product_development_projects(updated_projects)
    complete_demand_round(market_report.round_number)
    next_market_report = advance_market_report_to_next_round(market_report)
    set_round_submissions_open(
        market_report.round_number,
        False,
        "Round completed by instructor." + (
            " Auto-carried (no submission): " + ", ".join(fallback) if fallback else ""
        ),
    )
    set_round_submissions_open(
        next_market_report.round_number,
        False,
        "Prepare the next outlook and actual demand before opening submissions.",
    )
    _clear_game_editor_session_state()
    st.session_state["instructor_panel_notice"] = (
        f"Round {market_report.round_number} completed for {len(round_results)} teams, "
        f"{len(product_results)} product slots, and {len(forecast_accuracy_results)} forecast rows. "
        f"Public Market Report is now ready for Round {next_market_report.round_number}."
        + (" Auto-carried (no development spending): " + ", ".join(fallback) + "." if fallback else "")
    )
    st.rerun()


def main() -> None:
    """Render the instructor control page."""
    ensure_app_storage()
    user = require_authenticated_user()
    require_admin(user)
    _inject_instructor_cockpit_css()

    st.title("Instructor Cockpit")
    st.caption(
        "Admin-only round control, pre-run validation, team readiness, launch checks, and debrief preparation."
    )
    if notice := st.session_state.pop("instructor_panel_notice", None):
        st.success(notice)
    if warning := st.session_state.pop("instructor_panel_warning", None):
        st.warning(warning)

    market_report = load_market_report()
    current_round = market_report.round_number
    round_status = load_round_status(current_round)
    team_decisions = load_team_decisions(round_number=current_round)
    product_decisions = load_product_decisions(round_number=current_round)
    development_projects = load_product_development_projects()
    product_lines = load_product_lines()
    team_states = load_team_states()
    active_team_accounts = load_users(role="team_leader", is_active=True)

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

    submission_status_frame = _frame(
        _submission_status_rows(current_round, team_decisions, product_decisions)
    )
    missing_submission_count = (
        int((~submission_status_frame["firm_submission_saved"]).sum())
        if not submission_status_frame.empty
        else 0
    )
    pipeline_project_count = len(
        [item for item in development_projects if item.is_pipeline_active()]
    )
    launch_request_count = (
        int(validation_frame["launch_requests"].sum())
        if not validation_frame.empty
        else 0
    )

    st.subheader("Pre-Run Cockpit")
    summary_cols = st.columns(9)
    summary_cols[0].metric("Round", current_round)
    summary_cols[1].metric("Submitted", f"{len(team_decisions)} / {len(active_team_accounts)}")
    summary_cols[2].metric("Missing Teams", missing_submission_count)
    summary_cols[3].metric("Invalid Mix", invalid_mix_count)
    summary_cols[4].metric("Infeasible", infeasible_count)
    summary_cols[5].metric("Missing Forecast", missing_forecasts_count)
    summary_cols[6].metric("Cash Shortfall", likely_cash_shortfall_count)
    summary_cols[7].metric("Launch Requests", launch_request_count)
    summary_cols[8].metric("Ready Launches", ready_projects_total)

    control_sections = st.columns([1.15, 1.55, 1.05])
    with control_sections[0]:
        with st.container(border=True):
            st.markdown("#### Market Snapshot")
            market_cols = st.columns(2)
            market_cols[0].metric("Demand", f"{market_report.total_demand:,}")
            market_cols[1].metric(
                "Segment Mix",
                f"{market_report.premium_share:.0%} / {market_report.mid_share:.0%} / {market_report.beginner_share:.0%}",
            )
            market_cols = st.columns(2)
            market_cols[0].metric("Material Cost", f"{market_report.material_cost_index:+.2f}")
            market_cols[1].metric("Supply Risk", str(market_report.supply_risk))
            market_cols = st.columns(2)
            market_cols[0].metric("Quality Sens.", f"{market_report.quality_sensitivity:+.2f}")
            market_cols[1].metric("Market Gen", f"Gen {market_report.current_market_generation}")

    with control_sections[1]:
        with st.container(border=True):
            st.markdown("#### Classroom Controls")
            status_cols = st.columns(4)
            status_cols[0].metric(
                "Window",
                "Open" if round_status.submissions_open else "Closed",
            )
            status_cols[1].metric("Accounts", len(active_team_accounts))
            status_cols[2].metric("Saved Firms", len(team_decisions))
            status_cols[3].metric(
                "Gate",
                "Ready" if not _validation_exception_rows(submission_status_frame, validation_frame) else "Needs Review",
            )

            button_cols = st.columns([1, 1, 1])
            if button_cols[0].button("Open Team Submissions", disabled=not demand_status(current_round)):
                set_round_submissions_open(
                    current_round,
                    True,
                    "Instructor reopened submissions.",
                )
                st.success(f"Round {current_round} submissions are open.")
                st.rerun()
            if button_cols[1].button("Close Team Submissions"):
                set_round_submissions_open(
                    current_round,
                    False,
                    "Instructor closed submissions before running the round.",
                )
                st.warning(f"Round {current_round} submissions are closed.")
                st.rerun()
            if button_cols[2].button("Run Round", type="primary", key="instructor_run_round"):
                if not team_decisions and not active_team_accounts:
                    st.error("Create at least one active team before running the round.")
                else:
                    _run_round_and_advance(
                        market_report,
                        team_decisions,
                        product_decisions,
                        development_projects,
                        product_lines,
                        team_states,
                    )
            missing_names = sorted({u.team_name for u in active_team_accounts if u.team_name}
                                   - {d.team_name for d in team_decisions})
            if missing_names:
                st.info("Auto-carry at Run Round: " + ", ".join(missing_names)
                        + ". Previous operating/product plan (starting defaults if none); "
                        "no development investment, testing, launch or cancellation.")
            if round_status.submissions_open:
                st.info(
                    "Submissions are open. Actual demand and market settings are locked. Close submissions before running."
                )

    with control_sections[2]:
        with st.container(border=True):
            st.markdown("#### Run Gate")
            missing_team_names = (
                submission_status_frame.loc[
                    ~submission_status_frame["firm_submission_saved"],
                    "team_name",
                ].astype(str).tolist()
                if not submission_status_frame.empty
                else []
            )
            exception_rows = _validation_exception_rows(submission_status_frame, validation_frame)
            gate_cols = st.columns(2)
            gate_cols[0].metric(
                "Missing Team",
                missing_team_names[0] if missing_team_names else "None",
            )
            gate_cols[1].metric(
                "Exception Count",
                len(exception_rows),
            )
            gate_cols = st.columns(2)
            gate_cols[0].metric("Highest Risk", exception_rows[0]["area"] if exception_rows else "None")
            gate_cols[1].metric("Pipeline Projects", pipeline_project_count)
            st.caption("Factory reset is in the Danger Zone tab below.")

    readiness_frame = _frame(
        _readiness_rows(submission_status_frame, validation_frame, team_decisions)
    )
    st.subheader("Team Readiness Board")
    if readiness_frame.empty:
        st.info("Create team leader accounts to see a team readiness board.")
    else:
        readiness_display_frame = readiness_frame.rename(
            columns={
                "team_name": "Team",
                "archetype": "Archetype",
                "firm_saved": "Saved",
                "product_slots": "Product Slots",
                "forecasts": "Forecasts",
                "supplier": "Supplier",
                "feasibility": "Feasibility",
                "cash": "Cash",
                "launch": "Launch",
                "status": "Status",
            }
        )
        st.dataframe(readiness_display_frame, use_container_width=True, hide_index=True)

    lower_cols = st.columns([1.7, 1.0])
    with lower_cols[0]:
        st.subheader("Validation Exceptions")
        exception_frame = _frame(_validation_exception_rows(submission_status_frame, validation_frame))
        if exception_frame.empty:
            st.success("No pre-run validation exceptions detected.")
        else:
            exception_display_frame = exception_frame.rename(
                columns={
                    "team_name": "Team",
                    "area": "Area",
                    "issue": "Issue",
                    "suggested_action": "Suggested Action",
                }
            )
            st.dataframe(exception_display_frame, use_container_width=True, hide_index=True)
    with lower_cols[1]:
        st.subheader("Debrief Shortcuts")
        st.caption("After Run Round, use these pages to discuss results from different angles.")
        link_cols = st.columns(2)
        try:
            link_cols[0].page_link("pages/4_Results_Dashboard.py", label="Results Dashboard")
            link_cols[1].page_link("pages/8_Finance_Detail.py", label="Finance Detail")
            link_cols[0].page_link("pages/9_My_Team_Tracker.py", label="Team Tracker")
            link_cols[1].page_link("pages/1_Public_Market_Report.py", label="Next Market Report")
        except KeyError:
            st.caption("Results Dashboard | Finance Detail | Team Tracker | Public Market Report")
        st.info(
            "Debrief prompt: Why did profit, service, cash, forecast discipline, and launch timing rank different teams?"
        )

    st.subheader("Detail Tables")
    (
        validation_tab,
        submission_tab,
        firm_tab,
        product_tab,
        project_tab,
        portfolio_tab,
        danger_tab,
    ) = st.tabs(
        [
            "Validation Detail",
            "Submission Checklist",
            "Firm Decisions",
            "Product Decisions",
            "Development Projects",
            "Portfolio Snapshot",
            "Danger Zone",
        ]
    )

    with validation_tab:
        if validation_frame.empty:
            st.info("No team submissions are saved for the current round yet.")
        else:
            st.dataframe(validation_frame, use_container_width=True, hide_index=True)

    with submission_tab:
        if submission_status_frame.empty:
            st.info("Create team leader accounts to see a submission checklist.")
        else:
            st.dataframe(submission_status_frame, use_container_width=True, hide_index=True)

    firm_decision_frame = _frame([item.to_dict() for item in team_decisions])
    with firm_tab:
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

    product_decision_frame = _frame([item.to_dict() for item in product_decisions])
    with product_tab:
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

    project_frame = _frame([item.to_dict() for item in development_projects if item.is_defined()])
    with project_tab:
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

    product_line_frame = _frame([item.to_dict() for item in product_lines])
    with portfolio_tab:
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

    with danger_tab:
        st.warning(
            "Factory reset erases all game progress, market report history, decisions, product portfolios, pipelines, results, and team states. It keeps admin/team-leader accounts."
        )
        confirm_factory_reset = st.checkbox(
            "I understand this will restart the simulation at Round 1.",
            key="confirm_factory_reset_game",
        )
        if st.button(
            "Factory Reset Game",
            disabled=not confirm_factory_reset,
            help="Keeps user accounts, but resets the simulation itself to a fresh Round 1.",
        ):
            reset_report = factory_reset_game_data()
            _clear_game_editor_session_state()
            st.session_state["instructor_panel_warning"] = (
                f"Factory reset complete. The game is back to Round {reset_report.round_number}; accounts were kept."
            )
            st.rerun()


main()
