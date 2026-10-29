"""Administrator inspection of append-only submitted decision history."""

import json
import sqlite3
import streamlit as st

from utils.auth import render_user_sidebar
from utils.classrooms import classroom_name
from utils.decision_audit import SOURCE_LABELS, load_audit_history
from utils.game_exports import export_admin_user


st.set_page_config(page_title="Decision Audit Log | Kiki Pickleball", layout="wide")
try:
    user = export_admin_user()
except (PermissionError, ValueError, sqlite3.Error, OSError):
    st.error("This page is available to active admin users only.")
    st.page_link("pages/0_Login.py", label="Sign in", icon=":material/login:")
    st.stop()
render_user_sidebar(user)
st.title("Decision Audit Log")
st.subheader(classroom_name())
context, events, changes = load_audit_history()
if context is None:
    st.info("Decision audit logging has not been initialized in this classroom.")
    st.stop()
st.caption(f"Logging enabled (UTC): {context['enabled_at_utc']}. Successful saved decisions only; earlier edits and unsaved drafts are unavailable.")
st.page_link("pages/14_Data_Export_Backup.py", label="Download full history in Excel", icon=":material/download:")
if not events:
    st.info("No decision audit events yet.")
    st.stop()

filters = st.columns([2, 1, 2, 2])
team = filters[0].selectbox("Team", ['All teams'] + sorted({e['team_name'] for e in events}))
round_number = filters[1].selectbox("Round", ['All rounds'] + sorted({e['round_number'] for e in events}))
source = filters[2].selectbox("Source", ['All sources'] + list(SOURCE_LABELS.values()))
games = filters[3].selectbox("Game history", ['Current game', 'All games (including before reset)'])
filtered = [e for e in events if (team == 'All teams' or e['team_name'] == team)
            and (round_number == 'All rounds' or e['round_number'] == round_number)
            and (source == 'All sources' or SOURCE_LABELS[e['source']] == source)
            and (games != 'Current game' or e['game_id'] == context['game_id'])]
st.subheader(f"Saved Revisions ({len(filtered)})")
if not filtered:
    st.info("No revisions match these filters.")
    st.stop()
visible = filtered[:500]
st.dataframe([{
    'Time (UTC)': e['occurred_at_utc'][:19].replace('T', ' '), 'Team': e['team_name'], 'Round': e['round_number'],
    'Revision': e['revision'], 'Source': SOURCE_LABELS[e['source']], 'Account': e['actor_username'],
    'Initiated by': e['initiated_by_username'] or '', 'Changed fields': e['change_count'],
} for e in visible], hide_index=True, width='stretch')
if len(filtered) > 500:
    st.caption("Showing the latest 500 matches. Narrow the filters or download the complete Excel history.")
by_id = {e['event_id']: e for e in visible}
selected = st.selectbox("Revision to inspect", list(by_id), format_func=lambda key:
    f"{by_id[key]['team_name']} | Round {by_id[key]['round_number']} | Revision {by_id[key]['revision']} | {SOURCE_LABELS[by_id[key]['source']]}")
event = by_id[selected]
st.write(f"**{SOURCE_LABELS[event['source']]}** | Account: `{event['actor_username']}`")
st.caption(f"Saved at {event['occurred_at_utc']} (UTC)")
if event['initiated_by_username']:
    st.caption(f"Round run initiated by: {event['initiated_by_username']}")
st.write(event['reason'])
st.caption({'same_round_saved_plan': 'Compared with the previous saved submission in this round.',
            'prior_round_saved_plan': f"Firm/product inputs compared with Round {event['prior_round_number']}. Development compared with the saved pipeline before this submission.",
            'no_prior_saved_plan': 'No prior saved firm/product plan. Initial saved values are marked as not previously recorded.'}[event['comparison_basis']])

def display_value(raw, present):
    if not present:
        return '(not previously recorded)'
    value = json.loads(raw)
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)

details = [c for c in changes if c['event_id'] == selected]
st.subheader('Field Changes')
if details:
    st.dataframe([{'Decision group': c['decision_group'].replace('_', ' ').title(), 'Slot': c['slot_name'],
                   'Field': c['field_name'].replace('_', ' ').title(),
                   'Before': display_value(c['before_value_json'], c['before_present']),
                   'After': display_value(c['after_value_json'], c['after_present'])} for c in details],
                 hide_index=True, width='stretch')
else:
    st.info('Submitted again with no changes to the recorded decision values.')
with st.expander('Saved decision snapshots'):
    st.caption(f"Event ID: {selected} | Game ID: {event['game_id']}")
    st.write('Before')
    st.json(json.loads(event['before_json']), expanded=False)
    st.write('After')
    st.json(json.loads(event['after_json']), expanded=False)
