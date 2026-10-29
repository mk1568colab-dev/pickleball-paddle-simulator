"""Private, current-classroom downloads for instructors."""

import sqlite3
import streamlit as st

from utils.auth import render_user_sidebar
from utils.classrooms import active_classroom_id, classroom_name
from utils.game_exports import export_admin_user, prepare_classroom_downloads


st.set_page_config(page_title="Data Export & Backup | Kiki Pickleball", layout="wide")
try:
    user = export_admin_user()
except (PermissionError, ValueError, sqlite3.Error, OSError):
    st.session_state.pop("classroom_download_bundle", None)
    st.error("This page is available to active admin users only. Sign in to the correct classroom.")
    st.page_link("pages/0_Login.py", label="Sign in", icon=":material/login:")
    st.stop()
render_user_sidebar(user)
st.title("Data Export & Backup")
st.subheader(classroom_name())
st.page_link("pages/13_Classrooms.py", label="Switch classroom", icon=":material/school:")
st.warning("Private instructor files. Excel includes account names and unrevealed market demand. "
           "The backup also contains password hashes and is not encrypted. Do not share these files with students.")

key = "classroom_download_bundle"
scope = (active_classroom_id(), user.username)
saved = st.session_state.get(key)
if saved and saved["scope"] != scope:
    del st.session_state[key]
    saved = None

if st.button("Prepare Downloads", type="primary", icon=":material/archive:"):
    st.session_state.pop(key, None)
    saved = None
    try:
        with st.spinner("Creating a read-only classroom snapshot..."):
            saved = {"scope": scope, "bundle": prepare_classroom_downloads()}
    except (ValueError, TimeoutError) as error:
        st.error(str(error))
    except (PermissionError, sqlite3.Error, OSError):
        st.error("Downloads could not be prepared. Sign in to this classroom again and retry. "
                 "No game records were changed.")
    else:
        st.session_state[key] = saved

if saved:
    bundle = saved["bundle"]
    meta = bundle["metadata"]
    st.caption(f"Snapshot (UTC): {meta['captured_at_utc']} | Latest completed round: {meta['latest_completed_round']}")
    excel, backup = st.columns(2)
    with excel:
        if bundle["excel"] is not None:
            st.download_button("Download All Game Data (.xlsx)", bundle["excel"], bundle["excel_name"],
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               icon=":material/download:", on_click="ignore", width="stretch")
        else:
            st.error(bundle["excel_error"])
    with backup:
        st.download_button("Download Recovery Backup (.zip)", bundle["backup"], bundle["backup_name"],
                           "application/zip", icon=":material/download:", on_click="ignore", width="stretch")
    st.info("Both files contain this classroom only, at the snapshot time above. Prepare again for newer records. "
            "Recovery instructions are inside the ZIP. No existing classroom is replaced.")
    with st.expander("Included records"):
        st.dataframe([{"Source table": table, "Saved rows": count} for table, count in meta["table_counts"].items()],
                     hide_index=True, width="stretch")
else:
    st.caption("No snapshot prepared for this session.")

st.caption("All saved rounds are included. Decision audit events and field changes are included from the time logging was enabled. "
           "Unsaved drafts and earlier overwritten edits are unavailable. Team state, portfolio and pipeline sheets remain current snapshots.")
