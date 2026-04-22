"""Instructor tools for running the OM engine."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from engine.simulator import run_round
from utils.auth import require_admin, require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import (
    load_market_report,
    load_team_decisions,
    load_team_states,
    reset_runtime_data,
    save_round_results,
    save_team_states,
)


def _frame(records: list[dict[str, object]]) -> pd.DataFrame:
    """Convert dictionaries into a display DataFrame."""
    return pd.DataFrame(records) if records else pd.DataFrame()


def main() -> None:
    """Render the instructor control page."""
    ensure_app_storage()
    user = require_authenticated_user()
    require_admin(user)

    st.title("Instructor Panel")
    st.caption("Admin-only controls for submissions, reset actions, and round execution.")

    market_report = load_market_report()
    current_round = market_report.round_number
    decisions = load_team_decisions(round_number=current_round)

    st.subheader("Round Controls")
    st.write(f"Current round: `{current_round}`")
    st.write(f"Saved team submissions for this round: `{len(decisions)}`")

    if st.button("Run Round", type="primary"):
        if not decisions:
            st.error("Save at least one team decision before running the round.")
        else:
            team_states = load_team_states()
            results, updated_states = run_round(
                market_report=market_report,
                team_decisions=decisions,
                existing_states=team_states,
            )
            save_round_results(results)
            save_team_states(updated_states)
            st.success(f"Round completed for {len(results)} teams.")

    if st.button("Reset Decisions, Results, and Team State"):
        reset_runtime_data()
        st.warning("Runtime decisions, results, and team states have been reset.")

    st.subheader("Current Round Submissions")
    submission_frame = _frame([item.to_dict() for item in decisions])
    if submission_frame.empty:
        st.info("No team decisions have been submitted for the current round yet.")
    else:
        st.dataframe(submission_frame, use_container_width=True)

    st.subheader("Notes")
    st.info(
        "Use `Admin User Management` to create accounts, reset passwords, and bulk import team leaders. "
        "This page is only for running the round and monitoring submissions."
    )


main()
