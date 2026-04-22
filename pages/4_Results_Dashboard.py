"""Dashboard page for reviewing saved simulator records."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import (
    load_market_report,
    load_round_results,
    load_team_decisions,
    load_team_states,
)


def _frame(records: list[dict[str, object]]) -> pd.DataFrame:
    """Convert a list of dictionaries into a display-friendly DataFrame."""
    return pd.DataFrame(records) if records else pd.DataFrame()


def _build_rankings(round_results_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the two ranking tables for the latest available round."""
    latest_round = int(round_results_frame["round_number"].max())
    latest_round_frame = round_results_frame[
        round_results_frame["round_number"] == latest_round
    ]

    profit_ranking = latest_round_frame.sort_values(
        by="profit",
        ascending=False,
    )[
        [
            "team_name",
            "archetype",
            "profit",
            "revenue",
            "total_cost",
            "reputation_after_round",
        ]
    ]

    sales_ranking = latest_round_frame.sort_values(
        by=["sales_units", "demand_allocated"],
        ascending=[False, False],
    )[
        [
            "team_name",
            "archetype",
            "sales_units",
            "demand_allocated",
            "fill_rate",
            "stockout_units",
        ]
    ]
    return profit_ranking, sales_ranking


def main() -> None:
    """Render saved inputs and computed outputs."""
    ensure_app_storage()
    user = require_authenticated_user()

    st.title("Results Dashboard")
    st.caption("Review current round outcomes and persistent team performance.")

    market_report = load_market_report()
    current_round = market_report.round_number
    round_results = load_round_results()
    round_results_frame = _frame([item.to_dict() for item in round_results])

    st.subheader("Current Market Report")
    st.table(_frame([market_report.to_dict()]))

    if user.role == "admin":
        decisions = load_team_decisions(round_number=current_round)
        team_states = load_team_states()

        st.subheader("Saved Team Decisions")
        st.dataframe(_frame([item.to_dict() for item in decisions]), use_container_width=True)

        st.subheader("Round Results")
        if round_results_frame.empty:
            st.info("Run a round from the Instructor Panel to generate results.")
        else:
            st.dataframe(round_results_frame, use_container_width=True)
            profit_ranking, sales_ranking = _build_rankings(round_results_frame)

            latest_round = int(round_results_frame["round_number"].max())
            st.subheader(f"Profit Ranking - Round {latest_round}")
            st.dataframe(profit_ranking, use_container_width=True)

            st.subheader(f"Demand / Sales Ranking - Round {latest_round}")
            st.dataframe(sales_ranking, use_container_width=True)

        st.subheader("Persistent Team State")
        st.dataframe(_frame([item.to_dict() for item in team_states]), use_container_width=True)
        return

    team_name = user.team_name
    if not team_name:
        st.error("Your account does not have a team assignment yet.")
        st.stop()

    st.subheader("Your Team Results")
    own_results = load_round_results(team_name=team_name)
    own_results_frame = _frame([item.to_dict() for item in own_results])
    if own_results_frame.empty:
        st.info("Your team does not have any saved round results yet.")
    else:
        st.dataframe(own_results_frame, use_container_width=True)

    st.subheader("Your Team State")
    own_team_states = load_team_states(team_name=team_name)
    st.dataframe(_frame([item.to_dict() for item in own_team_states]), use_container_width=True)

    st.subheader("Public Rankings")
    if round_results_frame.empty:
        st.info("Rankings appear after the admin runs a round.")
    else:
        profit_ranking, sales_ranking = _build_rankings(round_results_frame)
        st.dataframe(profit_ranking, use_container_width=True)
        st.dataframe(sales_ranking, use_container_width=True)


main()
