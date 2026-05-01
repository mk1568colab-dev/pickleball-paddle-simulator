"""Detailed finance page for team and instructor financial debriefs."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import (
    load_product_round_results,
    load_round_results,
)


FINANCE_COLUMNS = [
    "round_number",
    "team_name",
    "archetype",
    "revenue",
    "procurement_cost",
    "production_cost",
    "holding_cost",
    "warranty_cost",
    "backlog_cost",
    "expansion_cost",
    "innovation_investment",
    "interest_expense",
    "total_cost",
    "profit",
    "ending_cash_balance",
    "short_term_debt_balance",
    "planned_borrowing_amount",
    "automatic_borrowing_amount",
    "working_capital_requirement",
    "liquidity_stress_flag",
    "sales_units",
    "demand_allocated",
    "ending_inventory",
    "backlog_units_end",
    "fill_rate",
    "forecast_wape",
]


def _frame(records: list[dict[str, object]]) -> pd.DataFrame:
    """Convert dictionaries into a DataFrame."""
    return pd.DataFrame(records) if records else pd.DataFrame()


def _money(value: float) -> str:
    """Format a dollar value for table display."""
    return f"${value:,.0f}"


def _pct(value: float) -> str:
    """Format a decimal as a percentage."""
    return f"{value * 100.0:.1f}%"


def _download_frame(label: str, frame: pd.DataFrame, file_name: str) -> None:
    """Render a CSV download button."""
    if frame.empty:
        return
    st.download_button(
        label=label,
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
    )


def _latest_round_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return rows from the latest available round."""
    if frame.empty:
        return frame
    return frame[frame["round_number"] == frame["round_number"].max()].copy()


def _estimated_beginning_cash(row: pd.Series) -> float:
    """Back-calculate beginning cash from the stored cash roll-forward fields."""
    return round(
        float(row["ending_cash_balance"])
        - float(row["automatic_borrowing_amount"])
        - float(row["planned_borrowing_amount"])
        - float(row["revenue"])
        + float(row["total_cost"]),
        2,
    )


def _estimated_beginning_debt(row: pd.Series) -> float:
    """Back-calculate beginning short-term debt."""
    return max(
        round(
            float(row["short_term_debt_balance"])
            - float(row["planned_borrowing_amount"])
            - float(row["automatic_borrowing_amount"]),
            2,
        ),
        0.0,
    )


def _cash_bridge_rows(row: pd.Series) -> pd.DataFrame:
    """Build a beginning-cash to ending-cash bridge for one team-round."""
    beginning_cash = _estimated_beginning_cash(row)
    cost_items = [
        ("Procurement cost", -float(row["procurement_cost"]), "Raw material purchases placed this round."),
        ("Production cost", -float(row["production_cost"]), "Conversion, labor, overtime, and product-level QC cost."),
        ("Holding cost", -float(row["holding_cost"]), "Finished-goods and raw-material carrying cost."),
        ("Warranty cost", -float(row["warranty_cost"]), "Defect-driven return/service cost."),
        ("Backlog cost", -float(row["backlog_cost"]), "Penalty for unmet demand carried as backlog."),
        ("Capacity expansion", -float(row["expansion_cost"]), "Investment in future installed capacity."),
        ("NPD / innovation investment", -float(row["innovation_investment"]), "Development-pipeline spending this round."),
        ("Interest expense", -float(row["interest_expense"]), "Cost of short-term borrowing."),
    ]
    ending_before_auto = (
        beginning_cash
        + float(row["planned_borrowing_amount"])
        + float(row["revenue"])
        + sum(amount for _, amount, _ in cost_items)
    )

    rows = [
        {
            "step": "Beginning cash",
            "cash_effect": beginning_cash,
            "display": _money(beginning_cash),
            "explanation": "Cash available before this round's revenue and spending.",
        },
        {
            "step": "Planned borrowing",
            "cash_effect": float(row["planned_borrowing_amount"]),
            "display": _money(float(row["planned_borrowing_amount"])),
            "explanation": "Borrowing intentionally entered by the team.",
        },
        {
            "step": "Sales and liquidation revenue",
            "cash_effect": float(row["revenue"]),
            "display": _money(float(row["revenue"])),
            "explanation": "Cash generated from product sales and any retirement liquidation.",
        },
    ]
    rows.extend(
        {
            "step": label,
            "cash_effect": amount,
            "display": _money(amount),
            "explanation": explanation,
        }
        for label, amount, explanation in cost_items
    )
    rows.extend(
        [
            {
                "step": "Ending cash before automatic borrowing",
                "cash_effect": ending_before_auto,
                "display": _money(ending_before_auto),
                "explanation": "If negative, the simulator automatically borrows to keep cash from going below zero.",
            },
            {
                "step": "Automatic borrowing",
                "cash_effect": float(row["automatic_borrowing_amount"]),
                "display": _money(float(row["automatic_borrowing_amount"])),
                "explanation": "Emergency short-term debt added when cash would otherwise be negative.",
            },
            {
                "step": "Ending cash",
                "cash_effect": float(row["ending_cash_balance"]),
                "display": _money(float(row["ending_cash_balance"])),
                "explanation": "Cash carried into the next round.",
            },
        ]
    )
    return pd.DataFrame(rows)


def _cost_breakdown_rows(row: pd.Series) -> pd.DataFrame:
    """Build a managerial cost breakdown for one team-round."""
    revenue = max(float(row["revenue"]), 1.0)
    sales_units = max(float(row["sales_units"]), 1.0)
    categories = [
        ("Procurement", float(row["procurement_cost"]), "Raw material order quantity and supplier mix."),
        ("Production", float(row["production_cost"]), "Actual production, conversion cost, overtime, and QC spend."),
        ("Holding", float(row["holding_cost"]), "Inventory left after sales plus raw material carrying cost."),
        ("Warranty", float(row["warranty_cost"]), "Defects caused by base quality, supplier risk, QC, and utilization stress."),
        ("Backlog", float(row["backlog_cost"]), "Unmet demand converted into backlog."),
        ("Capacity expansion", float(row["expansion_cost"]), "Capacity added for future rounds."),
        ("NPD / innovation", float(row["innovation_investment"]), "Development-project investment."),
        ("Interest", float(row["interest_expense"]), "Short-term debt cost."),
    ]
    return pd.DataFrame(
        [
            {
                "cost_category": category,
                "amount": amount,
                "display_amount": _money(amount),
                "cost_per_unit_sold": round(amount / sales_units, 2),
                "pct_of_revenue": round(amount / revenue, 4),
                "main_driver": driver,
            }
            for category, amount, driver in categories
        ]
    )


def _product_finance_frame(product_frame: pd.DataFrame) -> pd.DataFrame:
    """Build product-level contribution accounting rows."""
    if product_frame.empty:
        return product_frame

    frame = product_frame.copy()
    frame["visible_product_cost"] = (
        frame["production_cost"]
        + frame["holding_cost"]
        + frame["warranty_cost"]
        + frame["allocated_procurement_cost"]
        + frame["allocated_backlog_cost"]
        + frame["allocated_expansion_cost"]
    )
    frame["other_allocated_cost"] = (
        frame["revenue"]
        + frame["retirement_liquidation_revenue"]
        - frame["visible_product_cost"]
        - frame["profit_contribution"]
    ).round(2)
    frame["profit_margin_pct"] = (
        frame["profit_contribution"] / frame["revenue"].clip(lower=1.0)
    ).round(4)
    return frame[
        [
            "round_number",
            "slot_name",
            "product_name",
            "target_segment",
            "lifecycle_stage",
            "tech_generation",
            "forecast_units",
            "actual_demand_units",
            "sales_units",
            "ending_inventory",
            "revenue",
            "allocated_procurement_cost",
            "production_cost",
            "holding_cost",
            "warranty_cost",
            "allocated_backlog_cost",
            "allocated_expansion_cost",
            "other_allocated_cost",
            "profit_contribution",
            "profit_margin_pct",
            "fill_rate",
            "defect_rate",
        ]
    ]


def _finance_diagnostics(row: pd.Series, product_frame: pd.DataFrame) -> list[str]:
    """Create plain-English explanations for why the financial result happened."""
    notes: list[str] = []
    total_actual_demand = float(row["total_actual_demand_units"])
    sales_units = float(row["sales_units"])
    planned_production = float(row["planned_production_units"])
    ending_inventory = float(row["ending_inventory"])
    backlog_end = float(row["backlog_units_end"])
    fill_rate = float(row["fill_rate"])
    forecast_wape = float(row["forecast_wape"])

    if sales_units < total_actual_demand:
        notes.append(
            "Sales were below allocated demand, so the team left revenue on the table through stockouts, lost sales, or backlog."
        )
    if ending_inventory > max(sales_units * 0.25, 25):
        notes.append(
            "Ending inventory is high relative to sales, which ties up working capital and increases holding cost."
        )
    if planned_production > total_actual_demand * 1.25 and total_actual_demand > 0:
        notes.append(
            "Production was much higher than realized demand, creating inventory and cash pressure."
        )
    if planned_production < total_actual_demand * 0.75 and total_actual_demand > 0:
        notes.append(
            "Production was well below realized demand, limiting sales even if the market wanted more units."
        )
    if backlog_end > 0:
        notes.append(
            "The team carried backlog into the next round, which can hurt service performance and future reputation."
        )
    if fill_rate < 0.9:
        notes.append(
            "Fill rate was below 90%, meaning service performance was a major operational issue."
        )
    if forecast_wape > 0.3:
        notes.append(
            "Forecast accuracy was weak, so production and sourcing decisions were harder to align with actual demand."
        )
    if float(row["automatic_borrowing_amount"]) > 0:
        notes.append(
            "Automatic borrowing was needed because cash would have gone negative after round spending."
        )
    if bool(row["liquidity_stress_flag"]):
        notes.append(
            "Liquidity stress was flagged, so debt, low cash, or working capital pressure should be discussed."
        )

    if not product_frame.empty:
        worst_product = product_frame.sort_values(
            by="profit_contribution",
            ascending=True,
        ).iloc[0]
        best_product = product_frame.sort_values(
            by="profit_contribution",
            ascending=False,
        ).iloc[0]
        notes.append(
            f"Best product contribution came from {best_product['product_name']} "
            f"({_money(float(best_product['profit_contribution']))})."
        )
        notes.append(
            f"Weakest product contribution came from {worst_product['product_name']} "
            f"({_money(float(worst_product['profit_contribution']))})."
        )

    if not notes:
        notes.append(
            "The round was financially stable: demand, production, inventory, and cash were reasonably aligned."
        )
    return notes


def _render_finance_kpis(row: pd.Series) -> None:
    """Show top finance metrics."""
    beginning_cash = _estimated_beginning_cash(row)
    beginning_debt = _estimated_beginning_debt(row)
    cols = st.columns(6)
    cols[0].metric("Beginning Cash", _money(beginning_cash))
    cols[1].metric("Revenue", _money(float(row["revenue"])))
    cols[2].metric("Total Cost", _money(float(row["total_cost"])))
    cols[3].metric("Profit", _money(float(row["profit"])))
    cols[4].metric("Ending Cash", _money(float(row["ending_cash_balance"])))
    cols[5].metric("Debt", _money(float(row["short_term_debt_balance"])))

    st.caption(
        f"Beginning debt was approximately {_money(beginning_debt)}. "
        f"Service level was {_pct(float(row['fill_rate']))}; forecast error was "
        f"{_pct(float(row['forecast_wape']))} WAPE."
    )


def _render_team_round_detail(
    team_result_row: pd.Series,
    team_product_frame: pd.DataFrame,
) -> None:
    """Render detailed financial analysis for one selected team-round."""
    _render_finance_kpis(team_result_row)

    cash_bridge_tab, cost_tab, product_tab, explanation_tab = st.tabs(
        [
            "Cash Bridge",
            "Cost Breakdown",
            "Product Contribution",
            "Why This Happened",
        ]
    )

    with cash_bridge_tab:
        st.subheader("Round Cash Bridge")
        bridge_frame = _cash_bridge_rows(team_result_row)
        st.dataframe(
            bridge_frame[["step", "display", "explanation"]],
            use_container_width=True,
            hide_index=True,
        )
        _download_frame("Download Cash Bridge CSV", bridge_frame, "cash_bridge.csv")

    with cost_tab:
        st.subheader("Cost Breakdown")
        cost_frame = _cost_breakdown_rows(team_result_row)
        st.dataframe(
            cost_frame,
            use_container_width=True,
            hide_index=True,
        )
        _download_frame("Download Cost Breakdown CSV", cost_frame, "cost_breakdown.csv")

    with product_tab:
        st.subheader("Product-Level Financial Contribution")
        product_finance = _product_finance_frame(team_product_frame)
        if product_finance.empty:
            st.info("Product contribution rows appear after product results are generated.")
        else:
            st.dataframe(product_finance, use_container_width=True, hide_index=True)
            _download_frame(
                "Download Product Contribution CSV",
                product_finance,
                "product_contribution.csv",
            )

    with explanation_tab:
        st.subheader("Demand-to-Finance Explanation")
        for note in _finance_diagnostics(team_result_row, team_product_frame):
            st.write(f"- {note}")


def _render_finance_trends(team_results_frame: pd.DataFrame) -> None:
    """Render round-by-round financial performance."""
    if team_results_frame.empty:
        st.info("Finance trends appear after at least one completed round.")
        return

    trend_frame = team_results_frame.sort_values(by=["team_name", "round_number"]).copy()
    trend_frame["cumulative_profit"] = trend_frame.groupby("team_name")["profit"].cumsum()
    trend_frame["beginning_cash_estimate"] = trend_frame.apply(_estimated_beginning_cash, axis=1)
    trend_frame["cash_change"] = (
        trend_frame["ending_cash_balance"] - trend_frame["beginning_cash_estimate"]
    )

    chart_options = {
        "Profit": "profit",
        "Cumulative Profit": "cumulative_profit",
        "Revenue": "revenue",
        "Total Cost": "total_cost",
        "Ending Cash": "ending_cash_balance",
        "Short-Term Debt": "short_term_debt_balance",
        "Working Capital Requirement": "working_capital_requirement",
    }
    selected_metric = st.selectbox(
        "Finance metric to chart",
        options=list(chart_options.keys()),
    )
    chart_data = (
        trend_frame.pivot_table(
            index="round_number",
            columns="team_name",
            values=chart_options[selected_metric],
            aggfunc="sum",
        )
        .sort_index()
        .apply(pd.to_numeric, errors="coerce")
    )
    st.line_chart(chart_data, use_container_width=True)

    trend_columns = [
        "round_number",
        "team_name",
        "beginning_cash_estimate",
        "revenue",
        "total_cost",
        "profit",
        "cash_change",
        "ending_cash_balance",
        "short_term_debt_balance",
        "planned_borrowing_amount",
        "automatic_borrowing_amount",
        "working_capital_requirement",
        "liquidity_stress_flag",
    ]
    st.dataframe(trend_frame[trend_columns], use_container_width=True, hide_index=True)
    _download_frame(
        "Download Finance Trend CSV",
        trend_frame[trend_columns],
        "finance_trends.csv",
    )


def main() -> None:
    """Render the detailed finance page."""
    ensure_app_storage()
    user = require_authenticated_user()

    st.title("Finance Detail")
    st.caption(
        "Explain where money came from, where it went, which products made money, "
        "and whether the team is creating cash pressure."
    )

    all_team_results = load_round_results()
    all_product_results = load_product_round_results()
    team_results_frame = _frame([item.to_dict() for item in all_team_results])
    product_results_frame = _frame([item.to_dict() for item in all_product_results])

    if team_results_frame.empty:
        st.info("Finance details will appear after the instructor runs at least one round.")
        return

    if user.role == "team_leader":
        if not user.team_name:
            st.error("Your account does not have a team assignment.")
            st.stop()
        team_options = [user.team_name]
        scoped_team_results = team_results_frame[
            team_results_frame["team_name"].str.lower() == user.team_name.lower()
        ].copy()
    else:
        known_teams = sorted(
            set(team_results_frame["team_name"].dropna().tolist()),
            key=str.lower,
        )
        team_options = known_teams
        scoped_team_results = team_results_frame.copy()

    if scoped_team_results.empty:
        st.info("No completed finance results are available for your team yet.")
        return

    overview_tab, round_detail_tab, trend_tab = st.tabs(
        ["Financial Overview", "Selected Round Detail", "Round-by-Round Finance"]
    )

    with overview_tab:
        latest_frame = _latest_round_frame(scoped_team_results)
        st.subheader("Latest Financial Summary")
        st.dataframe(
            latest_frame[[column for column in FINANCE_COLUMNS if column in latest_frame.columns]],
            use_container_width=True,
            hide_index=True,
        )
        _download_frame(
            "Download Latest Financial Summary CSV",
            latest_frame,
            "latest_financial_summary.csv",
        )

    with round_detail_tab:
        selected_team = st.selectbox("Team", options=team_options)
        team_rounds = team_results_frame[
            team_results_frame["team_name"].str.lower() == selected_team.lower()
        ].copy()
        available_rounds = sorted(team_rounds["round_number"].unique().tolist(), reverse=True)
        selected_round = st.selectbox("Round", options=available_rounds)

        selected_team_row = team_rounds[
            team_rounds["round_number"] == selected_round
        ].iloc[0]
        selected_product_frame = product_results_frame[
            (product_results_frame["team_name"].str.lower() == selected_team.lower())
            & (product_results_frame["round_number"] == selected_round)
        ].copy()
        _render_team_round_detail(selected_team_row, selected_product_frame)

    with trend_tab:
        st.subheader("Round-by-Round Finance")
        if user.role == "admin":
            selected_teams = st.multiselect(
                "Teams to include",
                options=team_options,
                default=team_options,
            )
            trend_scope = team_results_frame[
                team_results_frame["team_name"].isin(selected_teams)
            ].copy()
        else:
            trend_scope = scoped_team_results
        _render_finance_trends(trend_scope)


main()
