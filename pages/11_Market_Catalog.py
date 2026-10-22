"""Public competitor listings sourced only from initial or completed-round data."""
import pandas as pd
import streamlit as st
from data.classroom_start import COMMON_PROFILE_NAME
from engine.classroom_brief import initial_catalog, completed_catalog
from utils.auth import require_authenticated_user
from utils.repository import (load_round_results, load_product_round_results,
                              load_product_decisions, load_users, load_team_states)

st.set_page_config(page_title="Competitor Prices | Kiki", layout="wide")
st.html("<style>section[data-testid='stSidebar']{min-width:240px;max-width:240px} .stMainBlockContainer{padding-top:2.5rem} h1{font-size:2rem!important}</style>")
user = require_authenticated_user()
st.title("Competitor Prices")
results = load_round_results()
active_teams = {u.team_name for u in load_users() if u.role == "team_leader" and u.is_active and u.team_name}
if results:
    completed = max(r.round_number for r in results)
    st.caption(f"PUBLIC SNAPSHOT | COMPLETED ROUND {completed}")
    rows = completed_catalog(load_product_round_results(), completed, load_product_decisions(round_number=completed))
    rows = [r for r in rows if r["Team"] in active_teams]
else:
    st.caption("PUBLIC SNAPSHOT | OPENING PRICES")
    common = {s.team_name for s in load_team_states() if s.archetype == COMMON_PROFILE_NAME}
    rows = initial_catalog(active_teams & common)
if not rows:
    st.info("No published product listings yet.")
else:
    frame = pd.DataFrame(rows)
    cols = st.columns([1.25, 1, 1, 1])
    query = cols[0].text_input("Search paddles", placeholder="Product name")
    team = cols[1].selectbox("Team", ["All teams"] + sorted(frame["Team"].unique()))
    segment = cols[2].selectbox("Segment", ["All segments"] + sorted(frame["Segment"].unique()))
    sort = cols[3].selectbox("Sort", ["Team", "Price: low to high", "Price: high to low"])
    if query:
        frame = frame[frame["Paddle"].str.contains(query, case=False, regex=False)]
    if team != "All teams":
        frame = frame[frame["Team"] == team]
    if segment != "All segments":
        frame = frame[frame["Segment"] == segment]
    frame = frame.sort_values(["Team", "Paddle"] if sort == "Team" else "Price ($)", ascending=sort != "Price: high to low")
    st.dataframe(frame, hide_index=True, use_container_width=True,
                 column_config={"Price ($)": st.column_config.NumberColumn(format="$%.2f")},
                 height=min(650, 38 + 35 * len(frame)))
    st.caption(f"{len(frame)} public products")
    st.download_button("Download catalog", frame.to_csv(index=False).encode(), "public_catalog.csv", "text/csv")
