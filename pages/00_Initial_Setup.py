"""First-run admin setup page."""

from __future__ import annotations

import streamlit as st

from utils.auth import HOME_PAGE_PATH, LOGIN_PAGE_PATH, SESSION_USER_KEY, get_current_user, system_requires_initial_setup
from utils.bootstrap import ensure_app_storage
from utils.branding import APP_NAME, APP_TAGLINE, MASCOT_IMAGE_PATH
from utils.repository import create_initial_admin
from utils.security import hash_password, validate_password_strength


def main() -> None:
    """Render the one-time initial admin setup flow."""
    st.set_page_config(
        page_title=f"Initial Setup - {APP_NAME}",
        page_icon=":material/admin_panel_settings:",
        layout="centered",
    )

    ensure_app_storage()
    existing_user = get_current_user()

    st.image(MASCOT_IMAGE_PATH, width=220)
    st.title(f"{APP_NAME} Initial Setup")
    st.caption(APP_TAGLINE)
    st.caption("Create the first admin account for this hosted classroom app.")

    if not system_requires_initial_setup():
        st.success("Initial setup is already complete.")
        if existing_user is not None:
            if st.button("Go to Home", type="primary"):
                st.switch_page(HOME_PAGE_PATH)
        else:
            if st.button("Go to Login", type="primary"):
                st.switch_page(LOGIN_PAGE_PATH)
        return

    st.info(
        "No active admin account exists yet. Create the first admin now. "
        "After this step, normal login becomes available."
    )

    with st.form("initial_admin_setup_form"):
        username = st.text_input("Admin Username")
        password = st.text_input("Admin Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Create Initial Admin", type="primary")

    if submitted:
        if not username.strip():
            st.error("Admin username is required.")
            return
        if password != confirm_password:
            st.error("Passwords do not match.")
            return

        password_errors = validate_password_strength(password)
        if password_errors:
            for error in password_errors:
                st.error(error)
            return

        try:
            user = create_initial_admin(
                username=username.strip(),
                password_hash=hash_password(password),
            )
        except ValueError as error:
            st.error(str(error))
            return

        st.session_state[SESSION_USER_KEY] = user.username
        st.success("Initial admin account created.")
        st.switch_page(HOME_PAGE_PATH)


main()
