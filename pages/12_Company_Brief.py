"""Opening handover and private, descriptive strategy evidence."""
import pandas as pd
import streamlit as st
from data.classroom_start import COMMON_PROFILE, COMMON_PROFILE_NAME, handover_rows
from engine.classroom_brief import strategy_signals
from utils.auth import require_authenticated_user
from utils.repository import (load_users, load_team_states, load_market_report,
    load_team_decision, load_product_decisions, load_product_development_projects,
    load_round_results)

st.set_page_config(page_title="Company Brief | Kiki", layout="wide")
st.html("<style>section[data-testid='stSidebar']{min-width:240px;max-width:240px} .stMainBlockContainer{padding-top:2.5rem} h1{font-size:2rem!important} h3{font-size:1.25rem!important}</style>")
user = require_authenticated_user()
st.title("Company Brief & Strategy")
if user.role == "admin":
    teams = sorted({u.team_name for u in load_users() if u.role == "team_leader" and u.is_active and u.team_name})
    if not teams:
        st.info("Create teams to view their company briefs.")
        st.stop()
    team = st.selectbox("Team", teams)
else:
    team = user.team_name
    if not team:
        st.error("No team assignment.")
        st.stop()
states = load_team_states(team_name=team)
if not states or states[0].archetype != COMMON_PROFILE_NAME:
    st.info("This team belongs to an earlier game setup. Its existing state has not been changed.")
    st.stop()
state = states[0]
st.caption(f"{team} | SHARED OPENING CONDITIONS")
opening, history, strategy = st.tabs(["Opening Position", "Pre-game Records", "Strategy Direction"])
with opening:
    cols = st.columns(4)
    for col, label, value in zip(cols, ["Opening cash", "Capacity / round", "Raw materials", "Debt"], ["$50,000", "300 units", "300 units", "$0"]):
        col.metric(label, value)
    st.subheader("Starting Product Portfolio")
    st.dataframe(pd.DataFrame([
        {"Slot": "A", "Paddle": "Core Control", "Segment": "Mid-market", "Price": "$149",
         "Technology": "Gen 2", "Lifecycle": "Growth", "Age (rounds)": "2", "Status": "Active"},
        {"Slot": "B", "Paddle": "Starter Play", "Segment": "Beginner", "Price": "$99",
         "Technology": "Gen 1", "Lifecycle": "Maturity", "Age (rounds)": "4", "Status": "Active"},
        {"Slot": "C", "Paddle": "Unoccupied", "Segment": "-", "Price": "-",
         "Technology": "-", "Lifecycle": "-", "Age (rounds)": "-", "Status": "New-product launch required"},
    ]), hide_index=True, use_container_width=True)
    st.subheader("Shared Operating Baseline")
    st.dataframe(pd.DataFrame([
        {"Measure": "Base cost parameter", "Opening value": "$70/unit"},
        {"Measure": "Base defect rate (before sourcing / QC adjustments)", "Opening value": "3.0%"},
        {"Measure": "Reputation", "Opening value": "60"},
        {"Measure": "Finished goods / backlog / open orders", "Opening value": "0 / 0 / 0"},
        {"Measure": "Development pipeline", "Opening value": "2 empty project slots"},
        {"Measure": "Cumulative game profit", "Opening value": "$0"},
    ]), hide_index=True, use_container_width=True)
with history:
    st.subheader("Pre-game Sales & Quality Records")
    st.warning("FICTIONAL TEACHING DATA | Same planning examples for every team. Not scored results or an accounting ledger; opening balances are set separately.")
    history_frame = pd.DataFrame(handover_rows())
    st.dataframe(history_frame, hide_index=True, use_container_width=True)
    st.caption("Historical sales are observed sales, not guaranteed demand. These examples are not added to cash, inventory, profit, or rankings.")
    st.download_button("Download pre-game records", history_frame.to_csv(index=False).encode(), "fictional_handover.csv", "text/csv")
with strategy:
    st.subheader("Decision Direction")
    st.caption("DESCRIPTIVE SIGNALS | No fixed company type, grade, bonus, or penalty. Multiple directions can coexist.")
    market = load_market_report()
    firm = load_team_decision(market.round_number, team)
    products = load_product_decisions(round_number=market.round_number, team_name=team)
    projects = load_product_development_projects(team_name=team)
    if firm:
        signals = strategy_signals(firm, products, projects, state.capacity_units)
        st.caption(f"Saved decisions | Round {market.round_number} | Unsaved edits are not included")
        st.dataframe(pd.DataFrame(signals)[["Direction", "Signals", "Decision evidence"]], hide_index=True, use_container_width=True)
    else:
        st.info("No saved plan this round. No strategy has been assigned.")
        from models.schemas import TeamDecision
        signals = strategy_signals(TeamDecision.from_dict({"team_name": team, "archetype": COMMON_PROFILE_NAME}), [], [], state.capacity_units)
    with st.expander("Signal definitions and outcome checks", expanded=not bool(firm)):
        st.caption("Classroom heuristics, not validated classifications. Each met condition counts as one signal. Price benchmarks: Beginner USD 99, Mid-market USD 149, Premium USD 189; technology benchmark: Gen 2.")
        for signal in signals:
            st.markdown(f"**{signal['Direction']}**")
            st.write(signal["Rule"])
            st.caption("Outcomes: " + signal["Outcome to check"])
    st.subheader("Observed Results")
    results = load_round_results(team_name=team)
    if not results:
        st.info("No completed rounds. A strategic intention is not evidence of success.")
    else:
        latest = max(results, key=lambda r: r.round_number)
        st.caption(f"Completed round {latest.round_number} | Separate from the current saved plan")
        st.dataframe(pd.DataFrame([{
            "Sales": latest.sales_units, "Profit ($)": latest.profit,
            "Ending cash ($)": latest.ending_cash_balance,
            "Debt ($)": latest.short_term_debt_balance,
            "Defects (%)": latest.defect_rate * 100,
            "Fill rate (%)": latest.fill_rate * 100,
            "Ending inventory": latest.ending_inventory,
        }]), hide_index=True, use_container_width=True)
