"""Admin-only account management page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.auth import require_admin, require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import (
    create_user,
    get_user_by_id,
    get_user_by_username,
    load_users,
    update_user,
)
from utils.security import hash_password, validate_password_strength


CREDENTIAL_NOTICE_KEY = "admin_credentials_notice"
BULK_IMPORT_SUMMARY_KEY = "bulk_import_summary"


def _frame(records: list[dict[str, object]]) -> pd.DataFrame:
    """Convert dictionaries into a display DataFrame."""
    return pd.DataFrame(records) if records else pd.DataFrame()


def _credential_rows_to_csv(rows: list[dict[str, object]]) -> bytes:
    """Convert newly created credentials into CSV bytes."""
    frame = pd.DataFrame(rows)
    return frame.to_csv(index=False).encode("utf-8")


def _show_credential_notice() -> None:
    """Render the one-time credential display after create/reset actions."""
    notice = st.session_state.get(CREDENTIAL_NOTICE_KEY)
    if not notice:
        return

    st.subheader("Share These Credentials Now")
    st.warning(
        "Passwords are shown only immediately after creation or reset. "
        "They cannot be viewed later because only password hashes are stored."
    )
    st.code(
        (
            f"Username: {notice['username']}\n"
            f"Temporary Password: {notice['password']}\n"
            f"Role: {notice['role']}\n"
            f"Team: {notice['team_name'] or '-'}"
        ),
        language="text",
    )

    if st.button("Clear Credential Display"):
        st.session_state.pop(CREDENTIAL_NOTICE_KEY, None)
        st.rerun()


def _show_bulk_import_summary() -> None:
    """Render the latest bulk import summary and credential export."""
    summary = st.session_state.get(BULK_IMPORT_SUMMARY_KEY)
    if not summary:
        return

    st.subheader("Latest Bulk Import Summary")
    st.write(
        f"Created: `{summary['created_count']}` | "
        f"Updated: `{summary['updated_count']}` | "
        f"Skipped: `{summary['skipped_count']}` | "
        f"Errors: `{len(summary['error_rows'])}`"
    )

    if summary["error_rows"]:
        st.dataframe(_frame(summary["error_rows"]), use_container_width=True)

    if summary["credential_rows"]:
        credential_frame = _frame(summary["credential_rows"])
        st.dataframe(credential_frame, use_container_width=True)
        st.download_button(
            "Download New Credentials CSV",
            data=_credential_rows_to_csv(summary["credential_rows"]),
            file_name="new_team_leader_credentials.csv",
            mime="text/csv",
        )

    if st.button("Clear Bulk Import Summary"):
        st.session_state.pop(BULK_IMPORT_SUMMARY_KEY, None)
        st.rerun()


def _parse_is_active(value: object) -> bool:
    """Parse the CSV active flag into a boolean."""
    text = str(value).strip().lower()
    if text in {"", "1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    raise ValueError("Invalid is_active value. Use true/false or yes/no.")


def _template_csv_bytes() -> bytes:
    """Return a simple CSV template for bulk imports."""
    template_frame = pd.DataFrame(
        [
            {
                "username": "team_alpha_lead",
                "password": "AlphaLeader123",
                "team_name": "Team Alpha",
                "is_active": "true",
            }
        ]
    )
    return template_frame.to_csv(index=False).encode("utf-8")


def main() -> None:
    """Render the admin user management page."""
    ensure_app_storage()
    user = require_authenticated_user()
    require_admin(user)

    st.title("Admin User Management")
    st.caption("Create, update, deactivate, and bulk import classroom accounts.")

    _show_credential_notice()
    _show_bulk_import_summary()

    users = load_users()
    role_filter = st.selectbox("Role Filter", options=["All", "admin", "team_leader"])
    status_filter = st.selectbox("Status Filter", options=["All", "Active", "Inactive"])

    filtered_users = users
    if role_filter != "All":
        filtered_users = [account for account in filtered_users if account.role == role_filter]
    if status_filter == "Active":
        filtered_users = [account for account in filtered_users if account.is_active]
    elif status_filter == "Inactive":
        filtered_users = [account for account in filtered_users if not account.is_active]

    public_users = [
        {
            "user_id": account.user_id,
            "username": account.username,
            "role": account.role,
            "team_name": account.team_name,
            "is_active": account.is_active,
        }
        for account in filtered_users
    ]
    st.dataframe(_frame(public_users), use_container_width=True)

    single_user_tab, edit_user_tab, bulk_import_tab = st.tabs(
        ["Create User", "Edit Existing User", "Bulk Import Team Leaders"]
    )

    with single_user_tab:
        with st.form("create_user_form"):
            username = st.text_input("Username")
            password = st.text_input("Temporary Password", type="password")
            role = st.selectbox("Role", options=["admin", "team_leader"])
            team_name = st.text_input("Team Name")
            is_active = st.checkbox("Active", value=True)
            submitted = st.form_submit_button("Create User", type="primary")

        if submitted:
            password_errors = validate_password_strength(password)
            if password_errors:
                for error in password_errors:
                    st.error(error)
            else:
                try:
                    created_user = create_user(
                        username=username,
                        password_hash=hash_password(password),
                        role=role,
                        team_name=team_name,
                        is_active=is_active,
                    )
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state[CREDENTIAL_NOTICE_KEY] = {
                        "username": created_user.username,
                        "password": password,
                        "role": created_user.role,
                        "team_name": created_user.team_name,
                    }
                    st.success(f"User `{created_user.username}` created.")
                    st.rerun()

    with edit_user_tab:
        user_options = [account.user_id for account in users]
        if not user_options:
            st.info("No users are available to edit yet.")
        else:
            selected_user_id = st.selectbox(
                "User to Edit",
                options=user_options,
                format_func=lambda user_id: _format_user_option(get_user_by_id(user_id)),
            )
            selected_user = get_user_by_id(selected_user_id)

            if selected_user is None:
                st.error("Selected user could not be loaded.")
            else:
                username_key = f"edit_username_{selected_user.user_id}"
                role_key = f"edit_role_{selected_user.user_id}"
                team_key = f"edit_team_{selected_user.user_id}"
                active_key = f"edit_active_{selected_user.user_id}"

                with st.form(f"edit_user_form_{selected_user.user_id}"):
                    username = st.text_input("Username", value=selected_user.username, key=username_key)
                    password = st.text_input(
                        "New Temporary Password",
                        type="password",
                        help="Leave blank to keep the current password.",
                    )
                    role = st.selectbox(
                        "Role",
                        options=["admin", "team_leader"],
                        index=["admin", "team_leader"].index(selected_user.role),
                        key=role_key,
                    )
                    team_name = st.text_input(
                        "Team Name",
                        value=selected_user.team_name or "",
                        key=team_key,
                    )
                    is_active = st.checkbox("Active", value=selected_user.is_active, key=active_key)
                    submitted = st.form_submit_button("Update User", type="primary")

                if submitted:
                    password_hash = None
                    if password:
                        password_errors = validate_password_strength(password)
                        if password_errors:
                            for error in password_errors:
                                st.error(error)
                        else:
                            password_hash = hash_password(password)

                    if not password or not password_errors:
                        try:
                            updated_user = update_user(
                                user_id=selected_user.user_id,
                                username=username,
                                role=role,
                                team_name=team_name,
                                is_active=is_active,
                                password_hash=password_hash,
                            )
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            if password:
                                st.session_state[CREDENTIAL_NOTICE_KEY] = {
                                    "username": updated_user.username,
                                    "password": password,
                                    "role": updated_user.role,
                                    "team_name": updated_user.team_name,
                                }
                            st.success(f"User `{updated_user.username}` updated.")
                            st.rerun()

    with bulk_import_tab:
        st.download_button(
            "Download CSV Template",
            data=_template_csv_bytes(),
            file_name="team_leader_import_template.csv",
            mime="text/csv",
        )

        uploaded_file = st.file_uploader("Upload Team Leader CSV", type=["csv"])
        update_existing = st.checkbox("Update existing usernames if found")

        if st.button("Run Bulk Import", type="primary"):
            if uploaded_file is None:
                st.error("Upload a CSV file before running bulk import.")
            else:
                try:
                    import_frame = pd.read_csv(uploaded_file, dtype=str).fillna("")
                except Exception as error:  # noqa: BLE001
                    st.error(f"Could not read CSV file: {error}")
                else:
                    required_columns = {"username", "password", "team_name", "is_active"}
                    missing_columns = required_columns - set(import_frame.columns)
                    if missing_columns:
                        st.error(
                            "CSV is missing required columns: "
                            + ", ".join(sorted(missing_columns))
                        )
                    else:
                        summary = _run_bulk_import(
                            import_frame=import_frame,
                            update_existing=update_existing,
                        )
                        st.session_state[BULK_IMPORT_SUMMARY_KEY] = summary
                        st.success("Bulk import finished.")
                        st.rerun()


def _run_bulk_import(import_frame: pd.DataFrame, update_existing: bool) -> dict[str, object]:
    """Create or update team leader accounts from a CSV upload."""
    created_count = 0
    updated_count = 0
    skipped_count = 0
    error_rows: list[dict[str, object]] = []
    credential_rows: list[dict[str, object]] = []

    for row_number, row in enumerate(import_frame.to_dict(orient="records"), start=2):
        username = str(row.get("username", "")).strip()
        password = str(row.get("password", "")).strip()
        team_name = str(row.get("team_name", "")).strip()

        if not username:
            error_rows.append({"row": row_number, "error": "Missing username."})
            continue
        if not password:
            error_rows.append({"row": row_number, "username": username, "error": "Missing password."})
            continue
        if not team_name:
            error_rows.append({"row": row_number, "username": username, "error": "Missing team_name."})
            continue

        password_errors = validate_password_strength(password)
        if password_errors:
            error_rows.append(
                {
                    "row": row_number,
                    "username": username,
                    "error": " ".join(password_errors),
                }
            )
            continue

        try:
            is_active = _parse_is_active(row.get("is_active", "true"))
        except ValueError as error:
            error_rows.append({"row": row_number, "username": username, "error": str(error)})
            continue

        existing_user = get_user_by_username(username)
        try:
            if existing_user is None:
                create_user(
                    username=username,
                    password_hash=hash_password(password),
                    role="team_leader",
                    team_name=team_name,
                    is_active=is_active,
                )
                created_count += 1
                credential_rows.append(
                    {
                        "username": username,
                        "temporary_password": password,
                        "team_name": team_name,
                    }
                )
                continue

            if existing_user.role != "team_leader":
                error_rows.append(
                    {
                        "row": row_number,
                        "username": username,
                        "error": "Existing non-team_leader account cannot be updated by bulk import.",
                    }
                )
                continue

            if not update_existing:
                skipped_count += 1
                continue

            update_user(
                user_id=existing_user.user_id,
                username=username,
                role="team_leader",
                team_name=team_name,
                is_active=is_active,
                password_hash=hash_password(password),
            )
            updated_count += 1
            credential_rows.append(
                {
                    "username": username,
                    "temporary_password": password,
                    "team_name": team_name,
                }
            )
        except ValueError as error:
            error_rows.append({"row": row_number, "username": username, "error": str(error)})

    return {
        "created_count": created_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "error_rows": error_rows,
        "credential_rows": credential_rows,
    }


def _format_user_option(user) -> str:
    """Build a readable label for the edit-user selector."""
    if user is None:
        return "Unknown user"
    team_suffix = f" / {user.team_name}" if user.team_name else ""
    active_suffix = "" if user.is_active else " / inactive"
    return f"{user.username} ({user.role}{team_suffix}{active_suffix})"


main()
