"""Page for viewing or editing the public market report."""

from __future__ import annotations

import streamlit as st
from engine.market_brief import market_brief

from data.market_scenarios import MARKET_SCENARIO_PRESETS, apply_market_scenario
from models.schemas import MAX_TECH_GENERATION, MIN_TECH_GENERATION, MarketReport
from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import load_market_report, save_market_report
from utils.demand_protocol import demand_status, public_market_row, save_outlook, revealed_demands


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
        st.caption("The outlook range describes the current decision round. Actual market demand is revealed only after results. It is not your team's guaranteed demand.")
        public = public_market_row(current_report)
        cols = st.columns(2)
        cols[0].metric("Decision Round", current_report.round_number)
        low, high = public.pop('demand_outlook_low'), public.pop('demand_outlook_high')
        cols[1].metric("Market Demand Outlook", f"{low:,} to {high:,} units" if isinstance(low, (int, float)) else "Not published")
        summary, scenarios = market_brief(public_market_row(current_report))
        st.subheader("Market Brief")
        st.write(summary)
        if scenarios:
            st.table(scenarios)
            st.caption("Public-range scenarios, rounded by segment. These are not actual demand or guaranteed team sales.")
        public.pop("round_number", None)
        st.table([{"Market factor": key.replace("_", " ").title(), "Value": str(value)} for key, value in public.items()])
        if revealed_demands():
            st.subheader("Completed Round Demand")
            st.table([{"Round": r["round_number"], "Outlook Low": r["outlook_low"],
                       "Outlook High": r["outlook_high"], "Actual Market Demand": r["actual_demand"]}
                      for r in revealed_demands()])
        return

    status = demand_status(current_report.round_number)
    if status and status["locked_at"]:
        st.info("Market settings and actual demand are locked. Closing or reopening submissions does not unlock them.")
        _render_report_table(current_report)
        st.table([status])
        return

    st.warning("Save the demand outlook and market settings before opening submissions. Opening commits actual demand and freezes this round's market settings.")
    with st.form("demand_outlook"):
        low = st.number_input("Public demand outlook lower bound", min_value=0, value=int(status["outlook_low"]) if status else 1000)
        high = st.number_input("Public demand outlook upper bound", min_value=1, value=int(status["outlook_high"]) if status else 1400)
        if st.form_submit_button("Save Public Outlook"):
            try:
                save_outlook(current_report.round_number, int(low), int(high))
                st.success("Public outlook saved. Actual demand remains private.")
            except ValueError as exc:
                st.error(str(exc))

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
        round_number = st.number_input("Round Number", min_value=1, step=1, value=current_report.round_number, disabled=True)
        total_demand = st.number_input("Actual Total Demand (instructor only)", min_value=0, step=50, value=current_report.total_demand)

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
