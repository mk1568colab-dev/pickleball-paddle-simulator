"""Administrator management of independent classroom games."""

import sqlite3
import streamlit as st

from utils.auth import require_authenticated_user, require_admin
from utils.bootstrap import ensure_app_storage
from utils.classrooms import (DEFAULT_CLASSROOM, active_classroom_id, classroom_name,
                              create_classroom, list_classrooms, select_classroom)

ensure_app_storage()
user = require_authenticated_user()
require_admin(user)
st.title("Classrooms")
st.subheader(classroom_name())
st.info("Each classroom has independent teams, accounts, markets, rounds, results and rankings. "
        "Excel imports, round execution and resets apply only to the classroom shown in the sidebar.")

for classroom in list_classrooms():
    left, right = st.columns([3, 1])
    left.write(classroom['name'])
    if right.button("Selected" if classroom['classroom_id'] == active_classroom_id() else "Switch classroom",
                    key=f"switch_class_{classroom['classroom_id']}",
                    disabled=classroom['classroom_id'] == active_classroom_id()):
        select_classroom(classroom['classroom_id'])
        st.switch_page("pages/0_Login.py")

if active_classroom_id() == DEFAULT_CLASSROOM:
    st.divider()
    st.subheader("Create Independent Classroom")
    with st.form("create_classroom", clear_on_submit=True):
        name = st.text_input("Classroom name", placeholder="Class 2")
        admin_username = st.text_input("New classroom admin username", placeholder="admin2")
        acknowledged = st.checkbox("Use my current admin password for this new admin account")
        st.caption("The new account is separate. Future password changes apply only to that account. "
                   "No student accounts or game progress are copied.")
        submitted = st.form_submit_button("Create Classroom", type="primary")
    if submitted:
        if not acknowledged:
            st.error("Confirm the new administrator's initial password before creating the classroom.")
        else:
            try:
                create_classroom(name, admin_username, user.username)
            except (ValueError, sqlite3.Error) as error:
                st.error(str(error))
            else:
                st.session_state['classroom_created_notice'] = name.strip()
                st.rerun()
    if 'classroom_created_notice' in st.session_state:
        st.success(f"Created {st.session_state.pop('classroom_created_notice')}. Switch classrooms to sign in and import its teams.")
else:
    st.caption("New classrooms are created by an administrator signed in to Class 1.")
