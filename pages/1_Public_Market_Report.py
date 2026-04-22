"""Page for viewing or editing the public market report."""

from __future__ import annotations

import streamlit as st

from models.schemas import MarketReport
from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import load_market_report, save_market_report


def _render_report_table(report: MarketReport) -> None:
    """Show the market report in a simple read-only table."""
    st.table([report.to_dict()])


def main() -> None:
    """Render the public market report page."""
    ensure_app_storage()
    user = require_authenticated_user()

    st.title("Public Market Report")
    st.caption("Round-wide market conditions shared with all teams.")

    current_report = load_market_report()
    share_total = current_report.share_total()
    if abs(share_total - 1.0) > 0.02:
        st.warning(
            f"Demand shares currently sum to {share_total:.2f}. "
            "The OM engine will normalize them during round allocation."
        )

    if user.role != "admin":
        st.info("This page is view-only for team leaders.")
        _render_report_table(current_report)
        return

    with st.form("market_report_form"):
        round_number = st.number_input(
            "Round Number",
            min_value=1,
            step=1,
            value=current_report.round_number,
        )
        total_demand = st.number_input(
            "Total Demand",
            min_value=0,
            step=50,
            value=current_report.total_demand,
        )

        col_1, col_2, col_3 = st.columns(3)
        with col_1:
            premium_share = st.number_input(
                "Premium Share",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                value=float(current_report.premium_share),
            )
        with col_2:
            mid_share = st.number_input(
                "Mid Share",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                value=float(current_report.mid_share),
            )
        with col_3:
            beginner_share = st.number_input(
                "Beginner Share",
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                value=float(current_report.beginner_share),
            )

        material_cost_index = st.number_input(
            "Material Cost Index",
            min_value=0.1,
            step=0.05,
            value=float(current_report.material_cost_index),
        )
        supply_risk = st.selectbox(
            "Supply Risk",
            options=["Low", "Moderate", "High"],
            index=["Low", "Moderate", "High"].index(current_report.supply_risk),
        )
        quality_sensitivity = st.slider(
            "Quality Sensitivity",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=float(current_report.quality_sensitivity),
        )
        event = st.text_area("Market Event", value=current_report.event, height=100)

        submitted = st.form_submit_button("Save Market Report", type="primary")

    edited_share_total = premium_share + mid_share + beginner_share
    if abs(edited_share_total - 1.0) > 0.02:
        st.warning(
            f"Edited demand shares currently sum to {edited_share_total:.2f}. "
            "The OM engine will normalize them during round allocation."
        )

    if submitted:
        report = MarketReport(
            round_number=int(round_number),
            total_demand=int(total_demand),
            premium_share=float(premium_share),
            mid_share=float(mid_share),
            beginner_share=float(beginner_share),
            material_cost_index=float(material_cost_index),
            supply_risk=supply_risk,
            quality_sensitivity=float(quality_sensitivity),
            event=event,
        )
        save_market_report(report)
        st.success("Market report saved.")
        _render_report_table(report)


main()
