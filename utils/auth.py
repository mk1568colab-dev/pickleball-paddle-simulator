"""Authentication and role-based page helpers."""

from __future__ import annotations

import streamlit as st

from models.schemas import AppUser
from utils.repository import get_user_by_username, has_active_admin
from utils.security import verify_password


SESSION_USER_KEY = "authenticated_username"
HOME_PAGE_PATH = "app.py"
LOGIN_PAGE_PATH = "pages/0_Login.py"
INITIAL_SETUP_PAGE_PATH = "pages/00_Initial_Setup.py"
ACCOUNT_PAGE_PATH = "pages/6_My_Account.py"
PUBLIC_MARKET_REPORT_PAGE_PATH = "pages/1_Public_Market_Report.py"
TEAM_DECISIONS_PAGE_PATH = "pages/2_Team_Decisions.py"
INSTRUCTOR_PANEL_PAGE_PATH = "pages/3_Instructor_Panel.py"
RESULTS_DASHBOARD_PAGE_PATH = "pages/4_Results_Dashboard.py"
ADMIN_USER_MANAGEMENT_PAGE_PATH = "pages/5_Admin_User_Management.py"
MODEL_FORMULA_GUIDE_PAGE_PATH = "pages/7_Model_Formula_Guide.py"
FINANCE_DETAIL_PAGE_PATH = "pages/8_Finance_Detail.py"


def _render_sidebar_navigation(user: AppUser) -> None:
    """Render role-aware sidebar navigation links."""
    st.markdown("### Navigation")
    st.page_link(HOME_PAGE_PATH, label="Home")
    st.page_link(
        PUBLIC_MARKET_REPORT_PAGE_PATH,
        label="Public Market Report",
    )
    st.page_link(
        TEAM_DECISIONS_PAGE_PATH,
        label="Team Decisions",
    )
    if user.role == "admin":
        st.page_link(
            INSTRUCTOR_PANEL_PAGE_PATH,
            label="Instructor Panel",
        )
        st.page_link(
            ADMIN_USER_MANAGEMENT_PAGE_PATH,
            label="Admin User Management",
        )
    st.page_link(
        RESULTS_DASHBOARD_PAGE_PATH,
        label="Results Dashboard",
    )
    st.page_link(
        FINANCE_DETAIL_PAGE_PATH,
        label="Finance Detail",
    )
    st.page_link(
        MODEL_FORMULA_GUIDE_PAGE_PATH,
        label="Model Formula Guide",
    )
    st.page_link(
        ACCOUNT_PAGE_PATH,
        label="My Account",
    )


def system_requires_initial_setup() -> bool:
    """Return whether the app still needs its first admin account."""
    return not has_active_admin()


def get_current_user() -> AppUser | None:
    """Return the current authenticated user, if any."""
    username = st.session_state.get(SESSION_USER_KEY)
    if not username:
        return None

    user = get_user_by_username(username)
    if user is None or not user.is_active:
        logout_user()
        return None

    return user


def login_user(username: str, password: str) -> tuple[bool, str]:
    """Authenticate a username/password pair."""
    if system_requires_initial_setup():
        return False, "Initial admin setup must be completed before users can log in."

    user = get_user_by_username(username.strip())
    if user is None:
        return False, "Invalid username or password."
    if not user.is_active:
        return False, "This account is inactive. Contact your instructor."
    if not verify_password(password, user.password_hash):
        return False, "Invalid username or password."

    st.session_state[SESSION_USER_KEY] = user.username
    return True, "Login successful."


def logout_user() -> None:
    """Clear the current user session."""
    st.session_state.pop(SESSION_USER_KEY, None)


def render_login_form() -> None:
    """Render the shared login form."""
    st.title("Login")
    st.caption("Use the account created by your instructor or admin.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", type="primary")

    if submitted:
        success, message = login_user(username=username, password=password)
        if success:
            st.success(message)
            st.switch_page(HOME_PAGE_PATH)
        else:
            st.error(message)


def render_user_sidebar(user: AppUser) -> None:
    """Show the current user and logout action in the sidebar."""
    with st.sidebar:
        _render_sidebar_navigation(user)
        st.divider()
        st.markdown("### Session")
        st.write(f"**User:** `{user.username}`")
        st.write(f"**Role:** `{user.role}`")
        if user.team_name:
            st.write(f"**Team:** `{user.team_name}`")
        st.caption("Use `My Account` to change your password.")

        if st.button("Log Out"):
            logout_user()
            st.switch_page(LOGIN_PAGE_PATH)


def require_authenticated_user() -> AppUser:
    """Ensure a page is only accessible to authenticated users."""
    if system_requires_initial_setup():
        st.switch_page(INITIAL_SETUP_PAGE_PATH)
        st.stop()

    user = get_current_user()
    if user is None:
        st.switch_page(LOGIN_PAGE_PATH)
        st.stop()

    render_user_sidebar(user)
    return user


def require_admin(user: AppUser) -> None:
    """Stop the page if the current user is not an admin."""
    if user.role != "admin":
        st.error("This page is available to admin users only.")
        st.stop()
