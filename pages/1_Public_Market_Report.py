"""Page for viewing or editing the public market report."""

from __future__ import annotations

import streamlit as st

from data.market_scenarios import MARKET_SCENARIO_PRESETS, apply_market_scenario
from models.schemas import MAX_TECH_GENERATION, MIN_TECH_GENERATION, MarketReport
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
    st.caption("Round-wide market, technology, and demand conditions shared with all teams.")

    current_report = load_market_report()
    share_total = current_report.share_total()
    if abs(share_total - 1.0) > 0.02:
        st.warning(
            f"Demand shares currently sum to {share_total:.2f}. "
            "The engine will normalize them during round allocation."
        )

    if user.role != "admin":
        st.info("This page is view-only for team leaders.")
        _render_report_table(current_report)
        return

    st.subheader("Instructor Scenario Presets")
    preset_names = list(MARKET_SCENARIO_PRESETS)
    selected_preset_name = st.selectbox(
        "Apply a teaching scenario",
        options=preset_names,
        help="Presets change the public market report only. They do not change engine coefficients or private team state.",
    )
    selected_preset = MARKET_SCENARIO_PRESETS[selected_preset_name]
    st.caption(
        f"{selected_preset.description} Teaching focus: {selected_preset.teaching_focus}"
    )
    if st.button("Apply Preset to Current Round"):
        preset_report = apply_market_scenario(current_report, selected_preset_name)
        save_market_report(preset_report)
        st.success(f"Applied `{selected_preset_name}` to round {preset_report.round_number}.")
        st.rerun()

    with st.form("market_report_form"):
        round_number = st.number_input("Round Number", min_value=1, step=1, value=current_report.round_number)
        total_demand = st.number_input("Total Demand", min_value=0, step=50, value=current_report.total_demand)

        share_cols = st.columns(3)
        premium_share = share_cols[0].number_input("Premium Share", min_value=0.0, max_value=1.0, step=0.01, value=float(current_report.premium_share))
        mid_share = share_cols[1].number_input("Mid Share", min_value=0.0, max_value=1.0, step=0.01, value=float(current_report.mid_share))
        beginner_share = share_cols[2].number_input("Beginner Share", min_value=0.0, max_value=1.0, step=0.01, value=float(current_report.beginner_share))

        ops_cols = st.columns(3)
        material_cost_index = ops_cols[0].number_input("Material Cost Index", min_value=0.1, step=0.05, value=float(current_report.material_cost_index))
        supply_risk = ops_cols[1].selectbox(
            "Supply Risk",
            options=["Low", "Moderate", "High"],
            index=["Low", "Moderate", "High"].index(current_report.supply_risk),
        )
        quality_sensitivity = ops_cols[2].slider("Quality Sensitivity", min_value=0.0, max_value=1.0, step=0.05, value=float(current_report.quality_sensitivity))

        st.markdown("#### Technology Environment")
        tech_cols = st.columns(3)
        current_market_generation = tech_cols[0].number_input(
            "Current Market Generation",
            min_value=MIN_TECH_GENERATION,
            max_value=MAX_TECH_GENERATION,
            step=1,
            value=int(current_report.current_market_generation),
        )
        technology_shift_rate = tech_cols[1].slider(
            "Technology Shift Rate",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=float(current_report.technology_shift_rate),
        )
        beginner_price_pressure = tech_cols[2].slider(
            "Beginner Price Pressure",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=float(current_report.beginner_price_pressure),
        )

        adoption_cols = st.columns(2)
        premium_tech_adoption = adoption_cols[0].slider(
            "Premium Tech Adoption",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=float(current_report.premium_tech_adoption),
        )
        mid_market_tech_adoption = adoption_cols[1].slider(
            "Mid-Market Tech Adoption",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=float(current_report.mid_market_tech_adoption),
        )

        event = st.text_area("Market Event", value=current_report.event, height=100)
        submitted = st.form_submit_button("Save Market Report", type="primary")

    edited_share_total = premium_share + mid_share + beginner_share
    if abs(edited_share_total - 1.0) > 0.02:
        st.warning(
            f"Edited demand shares currently sum to {edited_share_total:.2f}. "
            "The engine will normalize them during round allocation."
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
            current_market_generation=int(current_market_generation),
            technology_shift_rate=float(technology_shift_rate),
            premium_tech_adoption=float(premium_tech_adoption),
            mid_market_tech_adoption=float(mid_market_tech_adoption),
            beginner_price_pressure=float(beginner_price_pressure),
        )
        save_market_report(report)
        st.success("Market report saved.")
        _render_report_table(report)


main()
