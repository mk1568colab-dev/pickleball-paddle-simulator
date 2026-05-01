"""Student-facing page for tracking one team's decisions and results over time."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd
import streamlit as st

from models.schemas import AppUser
from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import (
    load_forecast_accuracy_results,
    load_market_report,
    load_product_decisions,
    load_product_development_projects,
    load_product_lines,
    load_product_round_results,
    load_round_results,
    load_team_decisions,
    load_team_names,
    load_team_states,
)


FIRM_DECISION_COLUMNS = [
    "round_number",
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

PRODUCT_DECISION_COLUMNS = [
    "round_number",
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

ROUND_RESULT_COLUMNS = [
    "round_number",
    "profit",
    "revenue",
    "total_cost",
    "sales_units",
    "demand_allocated",
    "fill_rate",
    "forecast_wape",
    "ending_cash_balance",
    "short_term_debt_balance",
    "ending_inventory",
    "backlog_units_end",
    "actual_production_units",
    "utilization_pct",
    "defect_rate",
    "innovation_investment",
    "launched_project_count",
    "retired_product_count",
    "reputation_after_round",
    "launch_events_text",
    "notes",
]

PRODUCT_RESULT_COLUMNS = [
    "round_number",
    "slot_name",
    "product_name",
    "target_segment",
    "lifecycle_stage",
    "age_in_rounds",
    "tech_generation",
    "selling_price_per_unit",
    "forecast_units",
    "planned_production_units",
    "actual_production_units",
    "demand_allocated",
    "sales_units",
    "lost_sales_units",
    "ending_inventory",
    "backlog_units_end",
    "fill_rate",
    "forecast_error_units",
    "forecast_bias_pct",
    "defect_rate",
    "revenue",
    "production_cost",
    "holding_cost",
    "warranty_cost",
    "profit_contribution",
    "launched_this_round",
    "retired_this_round",
    "launch_event",
]

PROJECT_COLUMNS = [
    "project_slot_name",
    "project_name",
    "status",
    "target_segment",
    "target_tech_generation",
    "intended_slot_name",
    "required_investment",
    "cumulative_investment",
    "investment_this_round",
    "testing_intensity",
    "launch_readiness_score",
    "planned_launch_round",
    "earliest_launch_round",
    "launch_now",
    "cancel_now",
    "launched_round",
    "canceled_round",
    "replaced_product_name",
]


def _frame(records: Iterable[dict[str, object]]) -> pd.DataFrame:
    """Convert dictionaries into a DataFrame."""
    rows = list(records)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _object_frame(items: Iterable[object]) -> pd.DataFrame:
    """Convert dataclass-like objects with to_dict into a DataFrame."""
    return _frame(item.to_dict() for item in items if hasattr(item, "to_dict"))


def _select_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return only columns that exist in the frame, preserving desired order."""
    if frame.empty:
        return frame
    return frame[[column for column in columns if column in frame.columns]].copy()


def _download_frame(label: str, frame: pd.DataFrame, file_name: str) -> None:
    """Render a CSV download button for team history data."""
    if frame.empty:
        return
    st.download_button(
        label=label,
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
    )


def _money(value: float | int) -> str:
    """Format a value as dollars."""
    return f"${float(value):,.0f}"


def _pct(value: float | int) -> str:
    """Format a decimal value as a percentage."""
    return f"{float(value) * 100.0:.1f}%"


def _team_for_page(user: AppUser) -> str:
    """Return the team this page should display."""
    if user.role == "team_leader":
        if not user.team_name:
            st.error("Your account is not assigned to a team. Contact your instructor.")
            st.stop()
        return user.team_name

    team_names = load_team_names(include_inactive_users=True)
    if not team_names:
        st.info("No teams exist yet. Create team leader accounts first.")
        st.stop()
    return st.selectbox("Team to inspect", options=team_names)


def _round_numbers_for_history(team_name: str) -> list[int]:
    """Build a compact round range covering current round and completed results."""
    current_round = load_market_report().round_number
    completed_rounds = [
        result.round_number for result in load_round_results(team_name=team_name)
    ]
    max_round = max([current_round, *completed_rounds], default=current_round)
    return list(range(1, max_round + 1))


def _load_firm_decision_history(team_name: str) -> pd.DataFrame:
    """Load all saved firm-level decisions for one team."""
    rows: list[dict[str, object]] = []
    for round_number in _round_numbers_for_history(team_name):
        for decision in load_team_decisions(
            round_number=round_number,
            team_name=team_name,
        ):
            payload = decision.to_dict()
            payload["round_number"] = round_number
            rows.append(payload)
    return _select_columns(
        _frame(rows).sort_values("round_number") if rows else pd.DataFrame(),
        FIRM_DECISION_COLUMNS,
    )


def _load_product_decision_history(team_name: str) -> pd.DataFrame:
    """Load all saved product-level decisions for one team."""
    rows: list[dict[str, object]] = []
    for round_number in _round_numbers_for_history(team_name):
        for decision in load_product_decisions(
            round_number=round_number,
            team_name=team_name,
        ):
            payload = decision.to_dict()
            payload["round_number"] = round_number
            rows.append(payload)
    frame = _frame(rows)
    if not frame.empty:
        frame = frame.sort_values(["round_number", "slot_name"])
    return _select_columns(frame, PRODUCT_DECISION_COLUMNS)


def _round_results_frame(team_name: str) -> pd.DataFrame:
    """Return team-level results sorted oldest to newest with derived metrics."""
    frame = _object_frame(load_round_results(team_name=team_name))
    if frame.empty:
        return frame

    frame = frame.sort_values("round_number").reset_index(drop=True)
    frame["cumulative_profit"] = frame["profit"].cumsum()
    frame["service_level_pct"] = frame["fill_rate"] * 100.0
    frame["forecast_accuracy_pct"] = (1.0 - frame["forecast_wape"]).clip(0, 1) * 100.0
    return frame


def _product_results_frame(team_name: str) -> pd.DataFrame:
    """Return product-level results sorted oldest to newest."""
    frame = _object_frame(load_product_round_results(team_name=team_name))
    if not frame.empty:
        frame = frame.sort_values(["round_number", "slot_name"]).reset_index(drop=True)
    return frame


def _forecast_results_frame(team_name: str) -> pd.DataFrame:
    """Return product forecast accuracy rows sorted oldest to newest."""
    frame = _object_frame(load_forecast_accuracy_results(team_name=team_name))
    if not frame.empty:
        frame = frame.sort_values(["round_number", "slot_name"]).reset_index(drop=True)
    return frame


def _render_current_snapshot(team_name: str) -> None:
    """Render current persistent team state, portfolio, and pipeline."""
    states = load_team_states(team_name=team_name)
    state = states[0] if states else None
    if state is None:
        st.info("No persistent team state exists yet. Save decisions or run a round first.")
    else:
        row_one = st.columns(5)
        row_one[0].metric("Cash", _money(state.cash_balance))
        row_one[1].metric("Debt", _money(state.short_term_debt_balance))
        row_one[2].metric("Cumulative Profit", _money(state.cumulative_profit))
        row_one[3].metric("Capacity", f"{state.capacity_units:,}")
        row_one[4].metric("Reputation", f"{state.reputation_score:.1f}")

        row_two = st.columns(5)
        row_two[0].metric("FG Inventory", f"{state.inventory_units:,}")
        row_two[1].metric("Raw Materials", f"{state.raw_material_inventory:,}")
        row_two[2].metric("Backlog", f"{state.backlog_units:,}")
        row_two[3].metric("Completed Rounds", ", ".join(map(str, state.completed_rounds)) or "-")
        row_two[4].metric("Liquidity Warning", "On" if state.liquidity_warning_flag else "Off")

    st.markdown("#### Current Product Portfolio")
    portfolio_frame = _object_frame(load_product_lines(team_name=team_name))
    if portfolio_frame.empty:
        st.info("No product portfolio has been initialized yet.")
    else:
        st.dataframe(
            _select_columns(
                portfolio_frame,
                [
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
                    "retired_round",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("#### Current Development Pipeline")
    project_frame = _object_frame(load_product_development_projects(team_name=team_name))
    if project_frame.empty:
        st.info("No development project slots exist yet.")
    else:
        st.dataframe(
            _select_columns(project_frame, PROJECT_COLUMNS),
            use_container_width=True,
            hide_index=True,
        )


def _render_decision_history(team_name: str) -> None:
    """Render saved round decisions."""
    firm_frame = _load_firm_decision_history(team_name)
    product_frame = _load_product_decision_history(team_name)

    st.markdown("#### Firm-Level Decision History")
    if firm_frame.empty:
        st.info("No firm-level decisions have been saved yet.")
    else:
        st.dataframe(firm_frame, use_container_width=True, hide_index=True)
        _download_frame(
            "Download Firm Decision History CSV",
            firm_frame,
            f"{team_name}_firm_decisions.csv",
        )

    st.markdown("#### Product-Level Decision History")
    if product_frame.empty:
        st.info("No product-level decisions have been saved yet.")
    else:
        st.dataframe(product_frame, use_container_width=True, hide_index=True)
        _download_frame(
            "Download Product Decision History CSV",
            product_frame,
            f"{team_name}_product_decisions.csv",
        )


def _render_performance_trends(team_name: str) -> None:
    """Render round-by-round team result trends."""
    results = _round_results_frame(team_name)
    if results.empty:
        st.info("No round results yet. The instructor needs to run at least one round.")
        return

    latest = results.iloc[-1]
    row = st.columns(6)
    row[0].metric("Latest Profit", _money(latest["profit"]))
    row[1].metric("Cumulative Profit", _money(latest["cumulative_profit"]))
    row[2].metric("Revenue", _money(latest["revenue"]))
    row[3].metric("Service Level", _pct(latest["fill_rate"]))
    row[4].metric("Forecast Accuracy", f"{latest['forecast_accuracy_pct']:.1f}%")
    row[5].metric("Cash / Debt", f"{_money(latest['ending_cash_balance'])} / {_money(latest['short_term_debt_balance'])}")

    chart_columns = {
        "Profit": "profit",
        "Cumulative Profit": "cumulative_profit",
        "Revenue": "revenue",
        "Total Cost": "total_cost",
        "Service Level %": "service_level_pct",
        "Forecast Accuracy %": "forecast_accuracy_pct",
        "Ending Cash": "ending_cash_balance",
        "Short-Term Debt": "short_term_debt_balance",
        "Ending Inventory": "ending_inventory",
        "Backlog": "backlog_units_end",
        "Innovation Investment": "innovation_investment",
        "Reputation": "reputation_after_round",
    }
    selected_metrics = st.multiselect(
        "Trend metrics",
        options=list(chart_columns),
        default=["Profit", "Cumulative Profit", "Ending Cash", "Short-Term Debt"],
    )
    if selected_metrics:
        chart_frame = results[["round_number"] + [chart_columns[item] for item in selected_metrics]]
        chart_frame = chart_frame.rename(
            columns={chart_columns[item]: item for item in selected_metrics}
        )
        st.line_chart(chart_frame.set_index("round_number"))

    st.markdown("#### Round-by-Round Team Results")
    st.dataframe(
        _select_columns(
            results,
            [
                "round_number",
                "profit",
                "cumulative_profit",
                "revenue",
                "total_cost",
                "sales_units",
                "demand_allocated",
                "fill_rate",
                "forecast_wape",
                "ending_cash_balance",
                "short_term_debt_balance",
                "ending_inventory",
                "backlog_units_end",
                "innovation_investment",
                "launch_events_text",
                "notes",
            ],
        ),
        use_container_width=True,
        hide_index=True,
    )
    _download_frame(
        "Download Team Results CSV",
        _select_columns(results, ROUND_RESULT_COLUMNS + ["cumulative_profit"]),
        f"{team_name}_round_results.csv",
    )


def _render_product_results(team_name: str) -> None:
    """Render product-level results and product trend chart."""
    products = _product_results_frame(team_name)
    if products.empty:
        st.info("No product-level results yet.")
        return

    latest_round = int(products["round_number"].max())
    st.markdown(f"#### Latest Product Results: Round {latest_round}")
    st.dataframe(
        _select_columns(
            products[products["round_number"] == latest_round],
            PRODUCT_RESULT_COLUMNS,
        ),
        use_container_width=True,
        hide_index=True,
    )

    product_options = sorted(products["product_name"].dropna().unique())
    selected_product = st.selectbox("Product trend", options=product_options)
    metric_options = {
        "Sales Units": "sales_units",
        "Demand Allocated": "demand_allocated",
        "Profit Contribution": "profit_contribution",
        "Ending Inventory": "ending_inventory",
        "Backlog": "backlog_units_end",
        "Forecast Error": "forecast_error_units",
        "Defect Rate": "defect_rate",
    }
    selected_metric = st.selectbox("Product metric", options=list(metric_options))
    product_trend = products[products["product_name"] == selected_product][
        ["round_number", metric_options[selected_metric]]
    ].rename(columns={metric_options[selected_metric]: selected_metric})
    st.line_chart(product_trend.set_index("round_number"))

    st.markdown("#### All Product Results")
    product_results_display = _select_columns(products, PRODUCT_RESULT_COLUMNS)
    st.dataframe(product_results_display, use_container_width=True, hide_index=True)
    _download_frame(
        "Download Product Results CSV",
        product_results_display,
        f"{team_name}_product_results.csv",
    )


def _render_forecast_and_planning(team_name: str) -> None:
    """Render forecast accuracy and plan-vs-actual diagnostics."""
    forecasts = _forecast_results_frame(team_name)
    results = _round_results_frame(team_name)

    if forecasts.empty:
        st.info("No forecast accuracy results yet.")
    else:
        latest_round = int(forecasts["round_number"].max())
        latest_forecasts = forecasts[forecasts["round_number"] == latest_round]
        total_abs_error = float(latest_forecasts["absolute_error_units"].sum())
        total_actual = max(float(latest_forecasts["actual_demand_units"].sum()), 1.0)
        st.metric("Latest Product-Forecast WAPE", f"{(total_abs_error / total_actual) * 100.0:.1f}%")
        st.dataframe(
            _select_columns(
                forecasts,
                [
                    "round_number",
                    "slot_name",
                    "product_name",
                    "forecast_units",
                    "actual_demand_units",
                    "actual_sales_units",
                    "forecast_error_units",
                    "absolute_error_units",
                    "forecast_bias_pct",
                    "mape_or_wape_value",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )

    if not results.empty:
        st.markdown("#### Planning Discipline by Round")
        planning_frame = results[
            [
                "round_number",
                "total_forecast_units",
                "planned_production_units",
                "actual_production_units",
                "total_actual_demand_units",
                "forecast_error_units",
                "service_gap_units",
                "forecast_wape",
                "fill_rate",
                "utilization_pct",
                "ending_inventory",
                "backlog_units_end",
            ]
        ].copy()
        planning_frame["forecast_minus_production"] = (
            planning_frame["total_forecast_units"]
            - planning_frame["planned_production_units"]
        )
        st.dataframe(planning_frame, use_container_width=True, hide_index=True)


def _render_pipeline_history(team_name: str) -> None:
    """Render current pipeline plus round-level innovation outcomes."""
    projects = _object_frame(load_product_development_projects(team_name=team_name))
    results = _round_results_frame(team_name)
    product_results = _product_results_frame(team_name)

    st.markdown("#### Current Pipeline State")
    if projects.empty:
        st.info("No active or historical project slots yet.")
    else:
        st.dataframe(_select_columns(projects, PROJECT_COLUMNS), use_container_width=True, hide_index=True)

    st.markdown("#### Round Innovation and Launch History")
    if results.empty:
        st.info("No round-level launch history yet.")
    else:
        innovation_frame = _select_columns(
            results,
            [
                "round_number",
                "innovation_investment",
                "active_project_count",
                "launch_ready_project_count",
                "launched_project_count",
                "retired_product_count",
                "average_portfolio_tech_generation",
                "cannibalized_demand_units",
                "launch_events_text",
                "notes",
            ],
        )
        st.dataframe(innovation_frame, use_container_width=True, hide_index=True)

    if not product_results.empty:
        st.markdown("#### Product Launch / Retirement Events")
        event_frame = product_results[
            (product_results["launched_this_round"] == True)
            | (product_results["retired_this_round"] == True)
            | (product_results["launch_event"].fillna("") != "")
        ].copy()
        if event_frame.empty:
            st.info("No product launch or retirement events have been recorded yet.")
        else:
            st.dataframe(
                _select_columns(
                    event_frame,
                    [
                        "round_number",
                        "slot_name",
                        "product_name",
                        "launched_this_round",
                        "retired_this_round",
                        "launch_event",
                        "retirement_liquidation_revenue",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
            )


def main() -> None:
    """Render the My Team Tracker page."""
    ensure_app_storage()
    user = require_authenticated_user()

    st.title("My Team Tracker")
    st.caption(
        "Review your saved decisions, product portfolio, development pipeline, and round-by-round outcomes in one place."
    )

    team_name = _team_for_page(user)
    st.info(
        f"Showing tracker for **{team_name}**. Team leaders only see their own team; admin users can inspect any team."
    )

    tabs = st.tabs(
        [
            "Current Snapshot",
            "Decision History",
            "Performance Trends",
            "Product Results",
            "Forecast & Planning",
            "Pipeline & Launches",
        ]
    )

    with tabs[0]:
        _render_current_snapshot(team_name)
    with tabs[1]:
        _render_decision_history(team_name)
    with tabs[2]:
        _render_performance_trends(team_name)
    with tabs[3]:
        _render_product_results(team_name)
    with tabs[4]:
        _render_forecast_and_planning(team_name)
    with tabs[5]:
        _render_pipeline_history(team_name)


main()
