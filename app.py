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
    st.caption("A hosted classroom competition app for OM decision rounds.")

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
        - OM round logic for price, production, capacity, quality, and inventory posture
        """
    )

    st.subheader("How To Use The App")
    if user.role == "admin":
        st.markdown(
            """
            - Update the current round in `Public Market Report`
            - Create and manage classroom accounts in `Admin User Management`
            - Review team submissions and run rounds from `Instructor Panel`
            - Review full results in `Results Dashboard`
            - Change your own password in `My Account`
            """
        )
    else:
        st.markdown(
            """
            - Review the public market conditions in `Public Market Report`
            - Submit or revise only your own team's decision in `Team Decisions`
            - Review your team's result and the public rankings in `Results Dashboard`
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
