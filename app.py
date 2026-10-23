"""Home page for the classroom simulator."""

import streamlit as st

from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.branding import APP_NAME, APP_TAGLINE


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon=":material/sports_tennis:", layout="wide")
    ensure_app_storage()
    user = require_authenticated_user()
    st.title(APP_NAME)
    st.caption(APP_TAGLINE)
    st.subheader(user.team_name or "Classroom Overview")
    st.page_link("pages/1_Public_Market_Report.py", label="Public Market Report", icon=":material/monitoring:")
    if user.role == "admin":
        st.page_link("pages/3_Instructor_Panel.py", label="Instructor Panel", icon=":material/tune:")
    else:
        st.page_link("pages/2_Team_Decisions.py", label="Team Decisions", icon=":material/edit_note:")
    st.page_link("pages/4_Results_Dashboard.py", label="Results Dashboard", icon=":material/bar_chart:")


if __name__ == "__main__":
    main()
