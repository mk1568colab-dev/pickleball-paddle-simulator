"""Dashboard page for reviewing Stage C portfolio, forecast, and finance outputs."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from engine.teaching import (
    build_balanced_score_rows,
    build_debrief_rows,
    build_forecast_learning_rows,
)
from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import (
    load_forecast_accuracy_results,
    load_market_report,
    load_product_development_projects,
    load_product_lines,
    load_product_round_results,
    load_round_results,
    load_team_states,
)


TEAM_RESULT_COLUMNS = [
    "round_number",
    "team_name",
    "archetype",
    "active_product_count",
    "active_project_count",
    "launch_ready_project_count",
    "launched_project_count",
    "retired_product_count",
    "total_forecast_units",
    "total_actual_demand_units",
    "forecast_error_units",
    "absolute_forecast_error_units",
    "forecast_wape",
    "service_gap_units",
    "weighted_average_selling_price",
    "planned_production_units",
    "actual_production_units",
    "effective_capacity_units",
    "utilization_pct",
    "weighted_material_unit_cost",
    "defect_rate",
    "good_units_produced",
    "demand_allocated",
    "sales_units",
    "lost_sales_units",
    "backlog_units_end",
    "ending_inventory",
    "ending_raw_material_inventory",
    "fill_rate",
    "revenue",
    "procurement_cost",
    "production_cost",
    "holding_cost",
    "warranty_cost",
    "backlog_cost",
    "expansion_cost",
    "innovation_investment",
    "interest_expense",
    "working_capital_requirement",
    "planned_borrowing_amount",
    "automatic_borrowing_amount",
    "ending_cash_balance",
    "short_term_debt_balance",
    "liquidity_stress_flag",
    "total_cost",
    "profit",
    "contribution_margin_per_unit",
    "reputation_after_round",
    "average_portfolio_tech_generation",
    "cannibalized_demand_units",
    "launch_events_text",
]

PRODUCT_RESULT_COLUMNS = [
    "round_number",
    "team_name",
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
    "defect_rate",
    "good_units_produced",
    "demand_allocated",
    "actual_demand_units",
    "sales_units",
    "lost_sales_units",
    "backlog_units_end",
    "ending_inventory",
    "fill_rate",
    "forecast_error_units",
    "absolute_error_units",
    "forecast_bias_pct",
    "mape_or_wape_value",
    "revenue",
    "production_cost",
    "holding_cost",
    "warranty_cost",
    "allocated_procurement_cost",
    "allocated_backlog_cost",
    "allocated_expansion_cost",
    "profit_contribution",
    "tech_gap_to_market",
    "tech_attractiveness_adjustment",
    "cannibalization_in_units",
    "cannibalization_out_units",
    "launched_this_round",
    "launch_event",
    "retired_this_round",
    "retirement_liquidation_revenue",
]

FORECAST_ACCURACY_COLUMNS = [
    "round_number",
    "team_name",
    "slot_name",
    "product_name",
    "forecast_units",
    "actual_demand_units",
    "actual_sales_units",
    "forecast_error_units",
    "absolute_error_units",
    "forecast_bias_pct",
    "mape_or_wape_value",
]

ROUND_TREND_METRICS = {
    "Round profit": "profit",
    "Cumulative profit": "cumulative_profit",
    "Revenue": "revenue",
    "Total cost": "total_cost",
    "Demand allocated": "demand_allocated",
    "Sales units": "sales_units",
    "Service level %": "service_level_pct",
    "Forecast accuracy %": "forecast_accuracy_pct",
    "Ending cash": "ending_cash_balance",
    "Short-term debt": "short_term_debt_balance",
    "Ending inventory": "ending_inventory",
    "Ending backlog": "backlog_units_end",
    "Reputation": "reputation_after_round",
    "Capacity utilization %": "utilization_pct",
    "Innovation investment": "innovation_investment",
}

ROUND_TREND_TABLE_COLUMNS = [
    "round_number",
    "team_name",
    "archetype",
    "profit",
    "cumulative_profit",
    "revenue",
    "total_cost",
    "demand_allocated",
    "sales_units",
    "service_level_pct",
    "forecast_accuracy_pct",
    "ending_cash_balance",
    "short_term_debt_balance",
    "ending_inventory",
    "backlog_units_end",
    "reputation_after_round",
    "utilization_pct",
    "innovation_investment",
]


def _frame(records: list[dict[str, object]]) -> pd.DataFrame:
    """Convert a list of dictionaries into a DataFrame."""
    return pd.DataFrame(records) if records else pd.DataFrame()


def _download_frame(label: str, frame: pd.DataFrame, file_name: str) -> None:
    """Render a CSV download button for a DataFrame."""
    if frame.empty:
        return
    st.download_button(
        label=label,
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
    )


def _latest_round_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return only the latest round in a result frame."""
    latest_round = int(frame["round_number"].max())
    return frame[frame["round_number"] == latest_round].copy()


def _state_rows(states) -> list[dict[str, object]]:
    """Flatten persistent team state into dashboard-friendly rows."""
    rows: list[dict[str, object]] = []
    for state in states:
        next_inbound_round = min(
            (order.arrival_round for order in state.open_material_orders),
            default=None,
        )
        rows.append(
            {
                "team_name": state.team_name,
                "archetype": state.archetype,
                "cash_balance": state.cash_balance,
                "short_term_debt_balance": state.short_term_debt_balance,
                "interest_expense_last_round": state.interest_expense_last_round,
                "liquidity_warning_flag": state.liquidity_warning_flag,
                "working_capital_stress_score": state.working_capital_stress_score,
                "finished_goods_inventory": state.inventory_units,
                "raw_material_inventory": state.raw_material_inventory,
                "backlog_units": state.backlog_units,
                "installed_capacity_units": state.capacity_units,
                "reputation_score": state.reputation_score,
                "open_material_orders_count": len(state.open_material_orders),
                "next_inbound_round": next_inbound_round,
                "completed_rounds": ", ".join(str(item) for item in state.completed_rounds),
                "cumulative_profit": state.cumulative_profit,
            }
        )
    return rows


def _team_rankings(
    latest_team_frame: pd.DataFrame,
    total_demand: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build Stage B team-level ranking tables."""
    ranking_base = latest_team_frame.copy()
    ranking_base["market_share_pct"] = (ranking_base["demand_allocated"] / max(total_demand, 1)) * 100.0

    profit_ranking = ranking_base.sort_values(by="profit", ascending=False)[
        ["team_name", "profit", "revenue", "total_cost", "innovation_investment", "reputation_after_round"]
    ]
    market_share_ranking = ranking_base.sort_values(by=["demand_allocated", "sales_units"], ascending=[False, False])[
        ["team_name", "demand_allocated", "market_share_pct", "sales_units", "average_portfolio_tech_generation"]
    ]
    service_ranking = ranking_base.sort_values(by=["fill_rate", "lost_sales_units", "backlog_units_end"], ascending=[False, True, True])[
        ["team_name", "fill_rate", "lost_sales_units", "backlog_units_end", "ending_inventory"]
    ]
    defect_ranking = ranking_base.sort_values(by=["defect_rate", "warranty_cost"], ascending=[True, True])[
        ["team_name", "defect_rate", "warranty_cost", "good_units_produced", "reputation_after_round"]
    ]
    utilization_ranking = ranking_base.sort_values(by=["utilization_pct", "effective_capacity_units"], ascending=[False, False])[
        ["team_name", "utilization_pct", "effective_capacity_units", "planned_production_units", "actual_production_units"]
    ]
    forecast_accuracy_ranking = ranking_base.sort_values(
        by=["forecast_wape", "absolute_forecast_error_units"],
        ascending=[True, True],
    )[
        [
            "team_name",
            "forecast_wape",
            "total_forecast_units",
            "total_actual_demand_units",
            "absolute_forecast_error_units",
        ]
    ]
    return (
        profit_ranking,
        market_share_ranking,
        service_ranking,
        defect_ranking,
        utilization_ranking,
        forecast_accuracy_ranking,
    )


def _round_trend_frame(team_results_frame: pd.DataFrame) -> pd.DataFrame:
    """Add derived metrics that make round-by-round charts easier to read."""
    if team_results_frame.empty:
        return team_results_frame

    trend_frame = team_results_frame.copy()
    trend_frame = trend_frame.sort_values(by=["team_name", "round_number"])
    trend_frame["cumulative_profit"] = trend_frame.groupby("team_name")["profit"].cumsum()
    trend_frame["service_level_pct"] = trend_frame["fill_rate"] * 100.0
    trend_frame["forecast_accuracy_pct"] = (
        (1.0 - trend_frame["forecast_wape"]).clip(lower=0.0, upper=1.0) * 100.0
    )
    return trend_frame


def _render_metric_trend_chart(
    trend_frame: pd.DataFrame,
    metric_label: str,
    metric_column: str,
) -> None:
    """Render one round-by-round line chart with teams as separate lines."""
    chart_data = (
        trend_frame.pivot_table(
            index="round_number",
            columns="team_name",
            values=metric_column,
            aggfunc="sum",
        )
        .sort_index()
        .apply(pd.to_numeric, errors="coerce")
    )
    st.markdown(f"#### {metric_label}")
    st.line_chart(chart_data, use_container_width=True)


def _render_round_trends(
    team_results_frame: pd.DataFrame,
    *,
    key_prefix: str,
    team_selector_enabled: bool,
) -> None:
    """Render multi-round performance charts and an exportable trend table."""
    if team_results_frame.empty:
        st.info("Round trends will appear after at least one round has been run.")
        return

    trend_frame = _round_trend_frame(team_results_frame)
    available_teams = sorted(trend_frame["team_name"].dropna().unique().tolist())
    if team_selector_enabled:
        selected_teams = st.multiselect(
            "Teams to show",
            options=available_teams,
            default=available_teams,
            key=f"{key_prefix}_teams",
        )
    else:
        selected_teams = available_teams

    if not selected_teams:
        st.info("Select at least one team to show round trends.")
        return

    trend_frame = trend_frame[trend_frame["team_name"].isin(selected_teams)].copy()
    latest_round = int(trend_frame["round_number"].max())
    latest_frame = trend_frame[trend_frame["round_number"] == latest_round].copy()
    cumulative_leader = (
        latest_frame.sort_values(by="cumulative_profit", ascending=False)["team_name"].iloc[0]
        if not latest_frame.empty
        else "-"
    )

    metric_row = st.columns(4)
    metric_row[0].metric("Rounds Tracked", int(trend_frame["round_number"].nunique()))
    metric_row[1].metric("Teams Tracked", int(trend_frame["team_name"].nunique()))
    metric_row[2].metric("Latest Round", latest_round)
    metric_row[3].metric("Cumulative Profit Leader", cumulative_leader)

    st.caption(
        "Use these charts to discuss whether teams are improving, burning cash, "
        "building inventory, missing forecasts, or changing competitive position over time."
    )

    metric_labels = list(ROUND_TREND_METRICS.keys())
    default_metrics = [
        "Round profit",
        "Cumulative profit",
        "Service level %",
        "Ending cash",
    ]
    selected_metrics = st.multiselect(
        "Performance metrics to chart",
        options=metric_labels,
        default=default_metrics,
        key=f"{key_prefix}_metrics",
    )

    for metric_label in selected_metrics:
        metric_column = ROUND_TREND_METRICS[metric_label]
        _render_metric_trend_chart(trend_frame, metric_label, metric_column)

    st.markdown("#### Round-by-Round Performance Table")
    available_columns = [
        column for column in ROUND_TREND_TABLE_COLUMNS if column in trend_frame.columns
    ]
    table_frame = trend_frame[available_columns].sort_values(
        by=["round_number", "team_name"],
        ascending=[True, True],
    )
    st.dataframe(table_frame, use_container_width=True, hide_index=True)
    _download_frame(
        "Download Round Trend CSV",
        table_frame,
        f"{key_prefix}_round_trends.csv",
    )


def _portfolio_snapshot_frame(product_lines_frame: pd.DataFrame) -> pd.DataFrame:
    """Return a tidy active-portfolio snapshot frame."""
    if product_lines_frame.empty:
        return product_lines_frame
    return product_lines_frame[
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
            "retired_round",
        ]
    ].copy()


def _pipeline_snapshot_frame(project_frame: pd.DataFrame) -> pd.DataFrame:
    """Return a tidy development-pipeline frame."""
    if project_frame.empty:
        return project_frame
    return project_frame[
        [
            "team_name",
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
            "launched_round",
            "canceled_round",
            "replaced_product_name",
        ]
    ].copy()


def _lifecycle_distribution(product_lines_frame: pd.DataFrame) -> pd.DataFrame:
    """Build lifecycle-stage counts."""
    if product_lines_frame.empty:
        return pd.DataFrame()
    return (
        product_lines_frame.groupby(["lifecycle_stage", "target_segment", "tech_generation"])
        .size()
        .reset_index(name="product_count")
        .sort_values(by=["lifecycle_stage", "target_segment", "tech_generation"])
    )


def _product_profitability_frame(product_results_frame: pd.DataFrame) -> pd.DataFrame:
    """Build a product profitability view for admins."""
    if product_results_frame.empty:
        return product_results_frame
    return product_results_frame.sort_values(by=["profit_contribution", "sales_units"], ascending=[False, False])[
        [
            "team_name",
            "slot_name",
            "product_name",
            "target_segment",
            "lifecycle_stage",
            "tech_generation",
            "profit_contribution",
            "revenue",
            "sales_units",
            "fill_rate",
            "defect_rate",
            "cannibalization_in_units",
            "cannibalization_out_units",
        ]
    ]


def _launch_log_frame(product_results_frame: pd.DataFrame) -> pd.DataFrame:
    """Return launch and retirement events from product results."""
    if product_results_frame.empty:
        return product_results_frame
    event_rows = product_results_frame[
        (product_results_frame["launched_this_round"]) | (product_results_frame["retired_this_round"])
    ].copy()
    if event_rows.empty:
        return event_rows
    return event_rows[
        [
            "round_number",
            "team_name",
            "slot_name",
            "product_name",
            "launched_this_round",
            "launch_event",
            "retired_this_round",
            "retirement_liquidation_revenue",
        ]
    ].sort_values(by=["round_number", "team_name", "slot_name"], ascending=[False, True, True])


def main() -> None:
    """Render Stage C saved inputs and outputs."""
    ensure_app_storage()
    user = require_authenticated_user()

    st.title("Results Dashboard")
    st.caption(
        "Review Stage C portfolio performance with forecast accuracy, planning diagnostics, cash pressure, product detail, and development-pipeline progress."
    )

    market_report = load_market_report()
    team_results = load_round_results()
    team_results_frame = _frame([item.to_dict() for item in team_results])
    forecast_accuracy_frame = _frame(
        [item.to_dict() for item in load_forecast_accuracy_results()]
    )
    product_results = load_product_round_results()
    product_results_frame = _frame([item.to_dict() for item in product_results])
    product_lines = load_product_lines()
    product_lines_frame = _frame([item.to_dict() for item in product_lines])
    development_projects = load_product_development_projects()
    project_frame = _frame([item.to_dict() for item in development_projects if item.is_defined()])

    st.subheader("Current Market Report")
    st.table(_frame([market_report.to_dict()]))

    if user.role == "admin":
        (
            team_summary_tab,
            round_trends_tab,
            teaching_debrief_tab,
            forecast_accuracy_tab,
            product_detail_tab,
            liquidity_tab,
            portfolio_snapshot_tab,
            pipeline_tab,
            event_log_tab,
        ) = st.tabs(
            [
                "Team Summary",
                "Round Trends",
                "Teaching Debrief",
                "Forecast Accuracy",
                "Product Detail",
                "Liquidity / Debt",
                "Portfolio Snapshot",
                "Development Pipeline",
                "Launch / Retirement Log",
            ]
        )

        with team_summary_tab:
            if team_results_frame.empty:
                st.info("Run a round from the Instructor Panel to generate team-level results.")
            else:
                latest_team_frame = _latest_round_frame(team_results_frame)
                latest_round = int(latest_team_frame["round_number"].iloc[0])
                st.subheader(f"Latest Team Summary - Round {latest_round}")
                st.dataframe(latest_team_frame[TEAM_RESULT_COLUMNS], use_container_width=True, hide_index=True)
                _download_frame(
                    "Download Latest Team Summary CSV",
                    latest_team_frame[TEAM_RESULT_COLUMNS],
                    f"round_{latest_round}_team_summary.csv",
                )

                rankings = _team_rankings(latest_team_frame, market_report.total_demand)
                st.markdown("#### Profit Ranking")
                st.dataframe(rankings[0], use_container_width=True, hide_index=True)
                st.markdown("#### Market Share / Demand Ranking")
                st.dataframe(rankings[1], use_container_width=True, hide_index=True)
                st.markdown("#### Service Level / Fill Rate Ranking")
                st.dataframe(rankings[2], use_container_width=True, hide_index=True)
                st.markdown("#### Defect Rate Ranking")
                st.dataframe(rankings[3], use_container_width=True, hide_index=True)
                st.markdown("#### Capacity Utilization Ranking")
                st.dataframe(rankings[4], use_container_width=True, hide_index=True)
                st.markdown("#### Forecast Accuracy Ranking")
                st.dataframe(rankings[5], use_container_width=True, hide_index=True)

                st.markdown("#### Persistent Team State")
                state_frame = _frame(_state_rows(load_team_states()))
                if state_frame.empty:
                    st.info("Persistent team state will appear after the first completed round.")
                else:
                    st.dataframe(state_frame, use_container_width=True, hide_index=True)
                    _download_frame(
                        "Download Team State CSV",
                        state_frame,
                        "persistent_team_state.csv",
                    )

        with round_trends_tab:
            st.subheader("Round-by-Round Team Performance")
            _render_round_trends(
                team_results_frame,
                key_prefix="admin",
                team_selector_enabled=True,
            )

        with teaching_debrief_tab:
            debrief_frame = _frame(build_debrief_rows(team_results, product_results))
            balanced_score_frame = _frame(build_balanced_score_rows(team_results))
            forecast_learning_frame = _frame(
                build_forecast_learning_rows(load_forecast_accuracy_results())
            )
            if debrief_frame.empty:
                st.info("Teaching debrief diagnostics appear after the first completed round.")
            else:
                st.subheader("Instructor Debrief Diagnostics")
                st.dataframe(debrief_frame, use_container_width=True, hide_index=True)
                _download_frame(
                    "Download Debrief Diagnostics CSV",
                    debrief_frame,
                    "latest_round_debrief_diagnostics.csv",
                )
                st.markdown("#### Optional Balanced Teaching Score")
                st.caption(
                    "This is not a hidden game rule. It is an optional classroom scoring lens: 40% profit, 20% service, 20% forecast accuracy, 20% liquidity, with a liquidity-stress penalty."
                )
                st.dataframe(balanced_score_frame, use_container_width=True, hide_index=True)
                _download_frame(
                    "Download Balanced Score CSV",
                    balanced_score_frame,
                    "latest_round_balanced_score.csv",
                )
                st.markdown("#### Forecast Learning Evidence")
                st.dataframe(forecast_learning_frame, use_container_width=True, hide_index=True)
                _download_frame(
                    "Download Forecast Learning CSV",
                    forecast_learning_frame,
                    "latest_round_forecast_learning.csv",
                )

        with forecast_accuracy_tab:
            if forecast_accuracy_frame.empty:
                st.info("Forecast-vs-actual rows will appear after the admin runs a round.")
            else:
                latest_accuracy_frame = _latest_round_frame(forecast_accuracy_frame)
                st.subheader("Latest Product Forecast vs Actual")
                st.dataframe(
                    latest_accuracy_frame[FORECAST_ACCURACY_COLUMNS],
                    use_container_width=True,
                    hide_index=True,
                )
                _download_frame(
                    "Download Latest Forecast Accuracy CSV",
                    latest_accuracy_frame[FORECAST_ACCURACY_COLUMNS],
                    "latest_product_forecast_accuracy.csv",
                )
                if not team_results_frame.empty:
                    latest_team_frame = _latest_round_frame(team_results_frame)
                    st.markdown("#### Team Planning Diagnostics")
                    st.dataframe(
                        latest_team_frame[
                            [
                                "team_name",
                                "total_forecast_units",
                                "total_actual_demand_units",
                                "forecast_error_units",
                                "absolute_forecast_error_units",
                                "forecast_wape",
                                "planned_production_units",
                                "service_gap_units",
                            ]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

        with product_detail_tab:
            if product_results_frame.empty:
                st.info("Run a round from the Instructor Panel to generate product-level results.")
            else:
                latest_product_frame = _latest_round_frame(product_results_frame)
                st.subheader("Latest Product Detail")
                st.dataframe(latest_product_frame[PRODUCT_RESULT_COLUMNS], use_container_width=True, hide_index=True)
                _download_frame(
                    "Download Latest Product Results CSV",
                    latest_product_frame[PRODUCT_RESULT_COLUMNS],
                    "latest_product_results.csv",
                )
                st.markdown("#### Product Profitability by Team")
                st.dataframe(_product_profitability_frame(latest_product_frame), use_container_width=True, hide_index=True)

        with liquidity_tab:
            if team_results_frame.empty:
                st.info("Liquidity and debt metrics will appear after the first completed round.")
            else:
                latest_team_frame = _latest_round_frame(team_results_frame)
                st.subheader("Latest Team Financial Summary")
                liquidity_frame = latest_team_frame[
                        [
                            "team_name",
                            "revenue",
                            "total_cost",
                            "profit",
                            "ending_cash_balance",
                            "short_term_debt_balance",
                            "interest_expense",
                            "working_capital_requirement",
                            "planned_borrowing_amount",
                            "automatic_borrowing_amount",
                            "liquidity_stress_flag",
                        ]
                    ]
                st.dataframe(
                    liquidity_frame,
                    use_container_width=True,
                    hide_index=True,
                )
                _download_frame(
                    "Download Latest Liquidity CSV",
                    liquidity_frame,
                    "latest_liquidity_summary.csv",
                )

        with portfolio_snapshot_tab:
            if product_lines_frame.empty:
                st.info("Portfolio slots will appear after teams open the decision page or after the first round runs.")
            else:
                st.subheader("Current Portfolio Composition by Team")
                portfolio_frame = _portfolio_snapshot_frame(product_lines_frame)
                st.dataframe(portfolio_frame, use_container_width=True, hide_index=True)
                _download_frame(
                    "Download Portfolio Snapshot CSV",
                    portfolio_frame,
                    "portfolio_snapshot.csv",
                )
                st.markdown("#### Lifecycle Stage Distribution")
                st.dataframe(_lifecycle_distribution(product_lines_frame), use_container_width=True, hide_index=True)

        with pipeline_tab:
            if project_frame.empty:
                st.info("No development projects are active yet.")
            else:
                st.subheader("Development Pipeline")
                pipeline_frame = _pipeline_snapshot_frame(project_frame)
                st.dataframe(pipeline_frame, use_container_width=True, hide_index=True)
                _download_frame(
                    "Download Development Pipeline CSV",
                    pipeline_frame,
                    "development_pipeline.csv",
                )

        with event_log_tab:
            launch_log = _launch_log_frame(product_results_frame)
            if launch_log.empty:
                st.info("Launch and retirement events appear after a round includes at least one project launch or product retirement.")
            else:
                st.dataframe(launch_log, use_container_width=True, hide_index=True)
        return

    team_name = user.team_name
    if not team_name:
        st.error("Your account does not have a team assignment yet.")
        st.stop()

    own_team_results = load_round_results(team_name=team_name)
    own_team_results_frame = _frame([item.to_dict() for item in own_team_results])
    own_forecast_accuracy_frame = _frame(
        [item.to_dict() for item in load_forecast_accuracy_results(team_name=team_name)]
    )
    own_product_results = load_product_round_results(team_name=team_name)
    own_product_results_frame = _frame([item.to_dict() for item in own_product_results])
    own_portfolio_lines_frame = _frame([item.to_dict() for item in load_product_lines(team_name=team_name)])
    own_project_frame = _frame([item.to_dict() for item in load_product_development_projects(team_name=team_name) if item.is_defined()])

    (
        team_summary_tab,
        round_trends_tab,
        forecast_accuracy_tab,
        active_portfolio_tab,
        pipeline_tab,
        product_results_tab,
        event_log_tab,
    ) = st.tabs(
        [
            "Team Summary",
            "Round Trends",
            "Forecast Accuracy",
            "Active Portfolio",
            "Development Pipeline",
            "Product Results",
            "Launch / Retirement Log",
        ]
    )

    with team_summary_tab:
        st.subheader("Your Team Aggregate Results")
        if own_team_results_frame.empty:
            st.info("Your team does not have any completed round results yet.")
        else:
            st.dataframe(own_team_results_frame[TEAM_RESULT_COLUMNS], use_container_width=True, hide_index=True)
            own_debrief_frame = _frame(
                build_debrief_rows(own_team_results, own_product_results)
            )
            if not own_debrief_frame.empty:
                st.markdown("#### Your Debrief Prompt")
                st.dataframe(own_debrief_frame, use_container_width=True, hide_index=True)

        st.markdown("#### Public Ranking Table")
        if team_results_frame.empty:
            st.info("Rankings appear after the admin runs a round.")
        else:
            latest_team_frame = _latest_round_frame(team_results_frame)
            rankings = _team_rankings(latest_team_frame, market_report.total_demand)
            st.dataframe(rankings[0], use_container_width=True, hide_index=True)

    with round_trends_tab:
        st.subheader("Your Round-by-Round Performance")
        _render_round_trends(
            own_team_results_frame,
            key_prefix="team_leader",
            team_selector_enabled=False,
        )

    with forecast_accuracy_tab:
        st.subheader("Your Forecast Accuracy")
        if own_forecast_accuracy_frame.empty:
            st.info("Your forecast-vs-actual rows will appear after the admin runs a round.")
        else:
            st.dataframe(
                own_forecast_accuracy_frame[FORECAST_ACCURACY_COLUMNS],
                use_container_width=True,
                hide_index=True,
            )

    with active_portfolio_tab:
        st.subheader("Your Active Portfolio")
        if own_portfolio_lines_frame.empty:
            st.info("Your current portfolio state will appear after your slots are initialized.")
        else:
            st.dataframe(_portfolio_snapshot_frame(own_portfolio_lines_frame), use_container_width=True, hide_index=True)

        st.markdown("#### Your Team State")
        own_state_frame = _frame(_state_rows(load_team_states(team_name=team_name)))
        if own_state_frame.empty:
            st.info("Your persistent team state will appear after the first completed round.")
        else:
            st.dataframe(own_state_frame, use_container_width=True, hide_index=True)

    with pipeline_tab:
        st.subheader("Your Development Pipeline")
        if own_project_frame.empty:
            st.info("Your development projects will appear here after you create them on the Team Decisions page.")
        else:
            st.dataframe(_pipeline_snapshot_frame(own_project_frame), use_container_width=True, hide_index=True)

    with product_results_tab:
        st.subheader("Your Product Results")
        if own_product_results_frame.empty:
            st.info("Your product-level results will appear after the admin runs a round.")
        else:
            st.dataframe(own_product_results_frame[PRODUCT_RESULT_COLUMNS], use_container_width=True, hide_index=True)

    with event_log_tab:
        own_launch_log = _launch_log_frame(own_product_results_frame)
        if own_launch_log.empty:
            st.info("Launch and retirement events will appear here after a round generates them.")
        else:
            st.dataframe(own_launch_log, use_container_width=True, hide_index=True)


main()
