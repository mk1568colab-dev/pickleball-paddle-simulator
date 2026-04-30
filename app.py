"""Home page for the pickleball paddle classroom simulator."""

import streamlit as st

from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage


def main() -> None:
    """Render the authenticated home page."""
    st.set_page_config(
        page_title="Pickleball Paddle Simulator",
        page_icon=":material/sports_tennis:",
        layout="wide",
    )

    database_path = ensure_app_storage()
    user = require_authenticated_user()

    st.title("Pickleball Paddle Market Simulator")
    st.caption(
        "A hosted classroom competition app for quantitative OM, SCM, portfolio, product-pipeline, forecasting, and cash-control rounds."
    )

    st.write(f"You are signed in as `{user.username}` with the role `{user.role}`.")
    if user.team_name:
        st.write(f"Assigned team: `{user.team_name}`")

    st.subheader("What This Version Supports")
    st.markdown(
        """
        - secure username/password login
        - first-run admin setup when no admin account exists
        - `admin` and `team_leader` roles
        - SQLite-backed classroom persistence
        - up to three product slots per team with product-level pricing, production, QC, and inventory decisions
        - lifecycle tracking with `launch`, `growth`, `maturity`, and `decline`
        - up to two future development projects per team with delayed launches and launch-readiness gates
        - technology-generation effects and market-generation pressure
        - product-level demand allocation with team-level rollups and intra-portfolio cannibalization
        - retirement and replacement decisions for aging products
        - product-level forecasting with forecast-vs-actual tracking
        - shared firm constraints for capacity, materials, backlog, reputation, cash, and debt
        - simple short-term borrowing, interest expense, and liquidity pressure
        - live portfolio, planning, and finance analytics before a team submits the round
        - instructor scenario presets, submission open/close controls, CSV exports, debrief diagnostics, and a formula guide for classroom use
        """
    )

    st.subheader("How To Use The App")
    if user.role == "admin":
        st.markdown(
            """
            - Update the current round in `Public Market Report`
            - Create and manage classroom accounts in `Admin User Management`
            - Review team submissions, project pipelines, and pre-run validation in `Instructor Panel`
            - Run the round and review full portfolio and pipeline performance in `Results Dashboard`
            - Use the `Teaching Debrief` dashboard tab and `Model Formula Guide` to support class discussion and research evidence collection
            - Change your own password in `My Account`
            """
        )
    else:
        st.markdown(
            """
            - Review the public market conditions in `Public Market Report`
            - Submit or revise only your own team's firm-level, product-slot, product-forecast, and development-project decisions in `Team Decisions`
            - Review your team's aggregate result, active portfolio, forecast accuracy, liquidity position, pipeline, and the public rankings in `Results Dashboard`
            - Use `Model Formula Guide` to understand how key outcomes are calculated
            - Change your own password in `My Account`
            """
        )

    st.subheader("Deployment Note")
    st.write(
        "This app is designed to run as one central hosted Streamlit instance while "
        "multiple users connect from their own browsers."
    )

    st.subheader("Database")
    st.write(f"SQLite database path: `{database_path}`")


if __name__ == "__main__":
    main()
