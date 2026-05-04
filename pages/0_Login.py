"""Login page for the simulator."""

from __future__ import annotations

import streamlit as st

from utils.auth import (
    INITIAL_SETUP_PAGE_PATH,
    get_current_user,
    logout_user,
    render_login_form,
    render_user_sidebar,
    system_requires_initial_setup,
)
from utils.bootstrap import ensure_app_storage
from utils.branding import APP_NAME


def main() -> None:
    """Render the login experience."""
    st.set_page_config(
        page_title=f"Login - {APP_NAME}",
        page_icon=":material/login:",
        layout="centered",
    )

    ensure_app_storage()
    if system_requires_initial_setup():
        st.switch_page(INITIAL_SETUP_PAGE_PATH)
        st.stop()

    user = get_current_user()
    if user is not None:
        render_user_sidebar(user)
        st.title(APP_NAME)
        st.info(f"You are already signed in as `{user.username}`.")

        if st.button("Go to Home", type="primary"):
            st.switch_page("app.py")

        if st.button("Log Out Here"):
            logout_user()
            st.rerun()
        return

    render_login_form()


main()
