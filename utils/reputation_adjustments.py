"""Explicit, audited instructor corrections; never called during startup or play."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from utils.decision_audit import _snapshot


def adjust_late_entry_reputation(path, *, team, game_id, expected_round, expected_score,
                                 points=10.0, admin_username='admin', apply=False):
    """Deduct once per team/game, with optimistic checks and an online backup."""
    if not math.isfinite(points) or not 0 < points <= 100:
        raise ValueError('Deduction must be greater than 0 and at most 100.')
    if not math.isfinite(expected_score) or not 0 <= expected_score <= 100:
        raise ValueError('Expected reputation must be between 0 and 100.')
    path = Path(path).resolve(strict=True)
    mode = 'rw' if apply else 'ro'
    connection = sqlite3.connect(path.as_uri() + '?mode=' + mode, uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('BEGIN IMMEDIATE' if apply else 'BEGIN')
        context = connection.execute('SELECT game_id FROM decision_audit_context WHERE singleton=1').fetchone()
        if not context or context['game_id'] != game_id:
            raise ValueError('Wrong game/classroom. No changes made.')
        state = connection.execute('SELECT * FROM team_states WHERE team_name=? COLLATE NOCASE', (team,)).fetchone()
        if state is None:
            raise ValueError('Team does not exist. No changes made.')
        team = state['team_name']
        marker = 'late-entry-adjustment-' + hashlib.sha256((game_id + ':' + team.casefold()).encode()).hexdigest()
        if connection.execute('SELECT 1 FROM decision_audit_events WHERE event_id=?', (marker,)).fetchone():
            return dict(status='already_applied', team=team, reputation=state['reputation_score'])
        admin = connection.execute("SELECT * FROM users WHERE username=? AND role='admin' AND is_active=1", (admin_username,)).fetchone()
        if admin is None:
            raise ValueError('Active administrator required. No changes made.')
        current_round = connection.execute('SELECT MAX(round_number) FROM market_reports').fetchone()[0]
        if current_round != expected_round:
            raise ValueError('Round changed. Review current data before adjusting.')
        first_round = connection.execute('SELECT MIN(round_number) FROM round_results WHERE team_name=?', (team,)).fetchone()[0]
        first_game_round = connection.execute('SELECT MIN(round_number) FROM round_results').fetchone()[0]
        if first_round is None or first_round <= first_game_round:
            raise ValueError('Team is not a played late entrant. No changes made.')
        old_score = float(state['reputation_score'])
        if abs(old_score - expected_score) > 0.000001:
            raise ValueError(f'Reputation changed to {old_score:.2f}. Review before adjusting.')
        metadata = connection.execute('SELECT classroom_id,classroom_name FROM decision_audit_events WHERE game_id=? ORDER BY event_sequence DESC LIMIT 1', (game_id,)).fetchone()
        if metadata is None:
            raise ValueError('Classroom audit metadata unavailable. No changes made.')
        new_score = round(max(0.0, old_score - points), 2)
        result = dict(status='preview', classroom=metadata['classroom_name'], team=team,
                      first_played_round=first_round, round=current_round, before=old_score,
                      after=new_score, requested_deduction=points, actual_deduction=round(old_score-new_score, 2))
        if not apply:
            return result
        directory = path.parent / 'instructor_correction_backups'
        directory.mkdir(exist_ok=True)
        backup = directory / ('before_entry_adjustment_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(backup)) as destination:
            source.backup(destination)
        before = _snapshot(connection, current_round, team)
        before['administrative_state'] = {'reputation_score': old_score}
        connection.execute('UPDATE team_states SET reputation_score=?,updated_at=CURRENT_TIMESTAMP WHERE team_name=?', (new_score, team))
        after = _snapshot(connection, current_round, team)
        after['administrative_state'] = {'reputation_score': new_score}
        revision = connection.execute('SELECT COALESCE(MAX(revision),0)+1 FROM decision_audit_events WHERE game_id=? AND team_name=? AND round_number=?', (game_id, team, current_round)).fetchone()[0]
        now = datetime.now(timezone.utc).isoformat()
        reason = (f'Instructor-authorized ONE-TIME late-entry reputation adjustment: {old_score:.2f} -> {new_score:.2f}; '
                  f'requested deduction {points:.2f}, floor 0. First played round {first_round}. '
                  'Not a student submission; no round rerun. Cash, products, decisions, accounts and historical results unchanged. '
                  f'Backup: {backup}')
        event = dict(event_id=marker, game_id=game_id, classroom_id=metadata['classroom_id'],
                     classroom_name=metadata['classroom_name'], team_name=team, round_number=current_round,
                     revision=revision, occurred_at_utc=now, source='admin_submission',
                     actor_user_id=admin['user_id'], actor_username=admin_username, actor_role='admin',
                     comparison_basis='instructor_authorized_state_correction', prior_round_number=None,
                     change_count=1, reason=reason, before_json=json.dumps(before), after_json=json.dumps(after))
        connection.execute(f"INSERT INTO decision_audit_events ({','.join(event)}) VALUES ({','.join(':'+key for key in event)})", event)
        connection.execute('''INSERT INTO decision_audit_changes
            (event_id,game_id,team_name,round_number,revision,occurred_at_utc,source,actor_username,
             decision_group,slot_name,field_name,before_present,before_value_json,after_present,after_value_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (marker, game_id, team, current_round, revision, now, 'admin_submission', admin_username,
             'Firm state', '', 'reputation_score', 1, json.dumps(old_score), 1, json.dumps(new_score)))
        connection.commit()
        return dict(result, status='applied', backup=str(backup))
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()
