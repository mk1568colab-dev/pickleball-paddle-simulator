"""Authenticated account settings page."""

from __future__ import annotations

import streamlit as st

from utils.auth import require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import update_user_password
from utils.security import hash_password, validate_password_strength, verify_password


def main() -> None:
    """Render the current user's account settings."""
    ensure_app_storage()
    user = require_authenticated_user()

    st.title("My Account")
    st.caption("Review your account details and change your password.")

    st.write(f"Username: `{user.username}`")
    st.write(f"Role: `{user.role}`")
    if user.team_name:
        st.write(f"Team: `{user.team_name}`")

    with st.form("change_password_form"):
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Change Password", type="primary")

    if submitted:
        if not verify_password(current_password, user.password_hash):
            st.error("Current password is incorrect.")
            return
        if new_password != confirm_password:
            st.error("New passwords do not match.")
            return

        password_errors = validate_password_strength(new_password)
        if password_errors:
            for error in password_errors:
                st.error(error)
            return

        try:
            update_user_password(
                user_id=user.user_id,
                password_hash=hash_password(new_password),
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.success("Your password has been updated.")


main()
