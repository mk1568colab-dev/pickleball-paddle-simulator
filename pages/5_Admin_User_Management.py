"""Admin-only account management page."""

from __future__ import annotations

import secrets
import string

import pandas as pd
import streamlit as st

from models.schemas import PersistentTeamState
from utils.auth import require_admin, require_authenticated_user
from utils.bootstrap import ensure_app_storage
from utils.repository import (
    create_user,
    get_user_by_id,
    get_user_by_username,
    load_team_names,
    load_users,
    remove_team_data,
    save_team_state,
    update_user,
)
from utils.security import hash_password, validate_password_strength


CREDENTIAL_NOTICE_KEY = "admin_credentials_notice"
BULK_IMPORT_SUMMARY_KEY = "bulk_import_summary"
TEAM_GENERATION_SUMMARY_KEY = "team_generation_summary"
REMOVE_TEAM_SUMMARY_KEY = "remove_team_summary"
PASSWORD_WORDS = ["Paddle", "Rally", "Volley", "Court", "Dink", "Serve"]
DEFAULT_STARTING_CASH = 50_000.0


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
    lines = [
        f"Username: {notice['username']}",
        f"Temporary Password: {notice['password']}",
        f"Role: {notice['role']}",
        f"Team: {notice['team_name'] or '-'}",
    ]
    if notice.get("starting_cash") is not None:
        lines.append(f"Starting Cash: ${float(notice['starting_cash']):,.0f}")

    st.code(
        "\n".join(lines),
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


def _show_team_generation_summary() -> None:
    """Render the latest generated team-account credentials."""
    summary = st.session_state.get(TEAM_GENERATION_SUMMARY_KEY)
    if not summary:
        return

    st.subheader("Latest Generated Team Accounts")
    st.write(
        f"Created: `{summary['created_count']}` | "
        f"Updated: `{summary['updated_count']}` | "
        f"Skipped: `{summary['skipped_count']}` | "
        f"Errors: `{len(summary['error_rows'])}`"
    )

    if summary["error_rows"]:
        st.dataframe(_frame(summary["error_rows"]), use_container_width=True)

    if summary["credential_rows"]:
        st.warning(
            "Download or copy these passwords now. They are not stored in plain text "
            "and cannot be viewed later."
        )
        credential_frame = _frame(summary["credential_rows"])
        st.dataframe(credential_frame, use_container_width=True)
        st.download_button(
            "Download Generated Team Credentials CSV",
            data=_credential_rows_to_csv(summary["credential_rows"]),
            file_name="generated_team_leader_credentials.csv",
            mime="text/csv",
        )

    if st.button("Clear Generated Team Account Summary"):
        st.session_state.pop(TEAM_GENERATION_SUMMARY_KEY, None)
        st.rerun()


def _show_remove_team_summary() -> None:
    """Render the latest team-removal summary."""
    summary = st.session_state.get(REMOVE_TEAM_SUMMARY_KEY)
    if not summary:
        return

    st.subheader("Latest Team Removal Summary")
    st.success(f"`{summary['team_name']}` was removed from the game.")
    st.dataframe(_frame(summary["rows_changed"]), use_container_width=True)

    if st.button("Clear Team Removal Summary"):
        st.session_state.pop(REMOVE_TEAM_SUMMARY_KEY, None)
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


def _slugify_username(value: str) -> str:
    """Convert instructor-entered text into a simple username prefix."""
    slug = "".join(
        character.lower() if character.isalnum() else "_"
        for character in value.strip()
    )
    return "_".join(part for part in slug.split("_") if part)


def _slugify_username_suffix(value: str) -> str:
    """Convert text into a username suffix while preserving a leading underscore."""
    slug = "".join(
        character.lower() if character.isalnum() else "_"
        for character in value.strip()
    )
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.rstrip("_")


def _generate_temporary_password(team_number: int) -> str:
    """Generate a readable one-time password that passes local strength rules."""
    word = secrets.choice(PASSWORD_WORDS)
    random_digits = secrets.randbelow(900) + 100
    random_tail = "".join(
        secrets.choice(string.ascii_letters + string.digits)
        for _ in range(4)
    )
    return f"Team{team_number:02d}-{word}{random_digits}{random_tail}"


def _save_initial_team_state(team_name: str, starting_cash_balance: float) -> None:
    """Store first-round cash before the team chooses its final archetype."""
    save_team_state(
        PersistentTeamState(
            team_name=team_name,
            archetype="",
            cash_balance=max(float(starting_cash_balance), 0.0),
            inventory_units=0,
            raw_material_inventory=0,
            backlog_units=0,
            capacity_units=0,
            reputation_score=0.0,
            completed_rounds=[],
            last_decision={},
            open_material_orders=[],
            cumulative_profit=0.0,
            short_term_debt_balance=0.0,
            interest_expense_last_round=0.0,
            liquidity_warning_flag=False,
            working_capital_stress_score=0.0,
        )
    )


def main() -> None:
    """Render the admin user management page."""
    ensure_app_storage()
    user = require_authenticated_user()
    require_admin(user)

    st.title("Admin User Management")
    st.caption("Create, update, deactivate, and bulk import classroom accounts.")

    _show_credential_notice()
    _show_bulk_import_summary()
    _show_team_generation_summary()
    _show_remove_team_summary()

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

    single_user_tab, generate_teams_tab, edit_user_tab, bulk_import_tab, remove_team_tab = st.tabs(
        [
            "Create User",
            "Generate Team Accounts",
            "Edit Existing User",
            "Bulk Import Team Leaders",
            "Remove Team",
        ]
    )

    with single_user_tab:
        with st.form("create_user_form"):
            username = st.text_input("Username")
            password = st.text_input("Temporary Password", type="password")
            role = st.selectbox("Role", options=["admin", "team_leader"])
            team_name = st.text_input("Team Name")
            starting_cash_balance = st.number_input(
                "Starting Cash for Team Leader Account",
                min_value=0.0,
                value=DEFAULT_STARTING_CASH,
                step=5_000.0,
                help="Used only when the new account is a team_leader.",
            )
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
                    if created_user.role == "team_leader" and created_user.team_name:
                        _save_initial_team_state(
                            created_user.team_name,
                            starting_cash_balance,
                        )
                    st.session_state[CREDENTIAL_NOTICE_KEY] = {
                        "username": created_user.username,
                        "password": password,
                        "role": created_user.role,
                        "team_name": created_user.team_name,
                        "starting_cash": (
                            starting_cash_balance
                            if created_user.role == "team_leader"
                            else None
                        ),
                    }
                    st.success(f"User `{created_user.username}` created.")
                    st.rerun()

    with generate_teams_tab:
        st.subheader("Quick Team Account Generator")
        st.caption(
            "Use this when you want to start a class quickly, for example with "
            "`Team 1` through `Team 6` and matching team-leader logins."
        )

        with st.form("generate_team_accounts_form"):
            team_count = st.number_input(
                "Number of Teams",
                min_value=1,
                max_value=50,
                value=6,
                step=1,
            )
            start_number = st.number_input(
                "Start Number",
                min_value=1,
                max_value=999,
                value=1,
                step=1,
            )
            team_name_prefix = st.text_input("Team Name Prefix", value="Team")
            username_prefix = st.text_input("Username Prefix", value="team")
            username_suffix = st.text_input("Username Suffix", value="_lead")
            starting_cash_balance = st.number_input(
                "Starting Cash per Team",
                min_value=0.0,
                value=DEFAULT_STARTING_CASH,
                step=5_000.0,
                help="Creates first-round cash for each generated team.",
            )
            is_active = st.checkbox("Create accounts as active", value=True)
            update_existing = st.checkbox(
                "Reset/update matching existing team-leader usernames",
                value=False,
                help=(
                    "Leave off for safest classroom setup. Existing usernames will be "
                    "skipped instead of overwritten."
                ),
            )
            submitted = st.form_submit_button(
                "Generate Team Leader Accounts",
                type="primary",
            )

        if submitted:
            summary = _run_team_account_generation(
                team_count=int(team_count),
                start_number=int(start_number),
                team_name_prefix=team_name_prefix,
                username_prefix=username_prefix,
                username_suffix=username_suffix,
                starting_cash_balance=starting_cash_balance,
                is_active=is_active,
                update_existing=update_existing,
            )
            st.session_state[TEAM_GENERATION_SUMMARY_KEY] = summary
            st.success("Team account generation finished.")
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
                                    "starting_cash": None,
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

    with remove_team_tab:
        st.subheader("Remove a Team")
        st.warning(
            "This removes simulator data for the selected team. By default, the "
            "team-leader account is deactivated instead of permanently deleted."
        )

        team_names = load_team_names(include_inactive_users=True)
        if not team_names:
            st.info("No teams are available to remove yet.")
        else:
            selected_team_name = st.selectbox("Team to Remove", options=team_names)
            linked_accounts = [
                {
                    "user_id": account.user_id,
                    "username": account.username,
                    "role": account.role,
                    "team_name": account.team_name,
                    "is_active": account.is_active,
                }
                for account in load_users(role="team_leader")
                if (account.team_name or "").strip().lower()
                == selected_team_name.strip().lower()
            ]

            st.write("Linked team-leader accounts")
            st.dataframe(_frame(linked_accounts), use_container_width=True)

            delete_accounts = st.checkbox(
                "Permanently delete linked team-leader account(s)",
                value=False,
                help=(
                    "Most classes should leave this off. Deactivation is safer because "
                    "it prevents login while keeping an account record."
                ),
            )
            confirmation = st.text_input(
                f'Type "{selected_team_name}" to confirm team removal'
            )

            if st.button("Remove Selected Team", type="primary"):
                if confirmation.strip() != selected_team_name:
                    st.error("Confirmation text does not match the selected team name.")
                else:
                    try:
                        summary = remove_team_data(
                            selected_team_name,
                            deactivate_team_leaders=not delete_accounts,
                            delete_team_leader_accounts=delete_accounts,
                        )
                    except ValueError as error:
                        st.error(str(error))
                    else:
                        st.session_state[REMOVE_TEAM_SUMMARY_KEY] = {
                            "team_name": selected_team_name,
                            "rows_changed": [
                                {"record_type": key, "rows_changed": value}
                                for key, value in summary.items()
                            ],
                        }
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


def _run_team_account_generation(
    *,
    team_count: int,
    start_number: int,
    team_name_prefix: str,
    username_prefix: str,
    username_suffix: str,
    starting_cash_balance: float,
    is_active: bool,
    update_existing: bool,
) -> dict[str, object]:
    """Generate a numbered set of team-leader accounts."""
    created_count = 0
    updated_count = 0
    skipped_count = 0
    error_rows: list[dict[str, object]] = []
    credential_rows: list[dict[str, object]] = []

    normalized_username_prefix = _slugify_username(username_prefix) or "team"
    normalized_username_suffix = _slugify_username_suffix(username_suffix)
    existing_team_users = {
        (account.team_name or "").strip().lower(): account
        for account in load_users(role="team_leader")
        if (account.team_name or "").strip()
    }

    for offset in range(team_count):
        team_number = start_number + offset
        team_name = f"{team_name_prefix.strip() or 'Team'} {team_number}"
        username = f"{normalized_username_prefix}{team_number}{normalized_username_suffix}"
        password = _generate_temporary_password(team_number)

        password_errors = validate_password_strength(password)
        if password_errors:
            error_rows.append(
                {
                    "team_name": team_name,
                    "username": username,
                    "error": " ".join(password_errors),
                }
            )
            continue

        existing_user = get_user_by_username(username)
        existing_team_user = existing_team_users.get(team_name.strip().lower())
        if (
            existing_team_user is not None
            and existing_team_user.username.strip().lower() != username.strip().lower()
        ):
            error_rows.append(
                {
                    "team_name": team_name,
                    "username": username,
                    "error": (
                        "Team name is already assigned to "
                        f"`{existing_team_user.username}`."
                    ),
                }
            )
            continue

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
                existing_team_users[team_name.strip().lower()] = get_user_by_username(username)
                _save_initial_team_state(team_name, starting_cash_balance)
            elif existing_user.role != "team_leader":
                error_rows.append(
                    {
                        "team_name": team_name,
                        "username": username,
                        "error": "Existing admin/non-team account was not changed.",
                    }
                )
                continue
            elif update_existing:
                update_user(
                    user_id=existing_user.user_id,
                    username=username,
                    role="team_leader",
                    team_name=team_name,
                    is_active=is_active,
                    password_hash=hash_password(password),
                )
                updated_count += 1
                existing_team_users[team_name.strip().lower()] = get_user_by_username(username)
                _save_initial_team_state(team_name, starting_cash_balance)
            else:
                skipped_count += 1
                continue

            credential_rows.append(
                {
                    "team_name": team_name,
                    "username": username,
                    "temporary_password": password,
                    "starting_cash": starting_cash_balance,
                    "role": "team_leader",
                    "is_active": is_active,
                }
            )
        except ValueError as error:
            error_rows.append(
                {
                    "team_name": team_name,
                    "username": username,
                    "error": str(error),
                }
            )

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
