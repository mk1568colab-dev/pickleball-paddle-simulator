"""Operator-only historical reputation replay. Never invoked by app startup."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from engine.reputation import OPENING_REPUTATION, POLICY_BASIS, POLICY_ID, entry_score, replay_reputation
from utils.decision_audit import _snapshot


def recalculate_reputation(path, *, game_id, completed_round, admin_username, apply=False):
    path = Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + ('?mode=rw' if apply else '?mode=ro'),
                                uri=True, timeout=30)) as con:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        con.execute('BEGIN IMMEDIATE' if apply else 'BEGIN')
        try:
            context = con.execute('SELECT game_id FROM decision_audit_context WHERE singleton=1').fetchone()
            if not context or context['game_id'] != game_id:
                raise ValueError('Game ID changed or wrong classroom; no changes made.')
            admin = con.execute("SELECT * FROM users WHERE username=? AND role='admin' AND is_active=1",
                                (admin_username,)).fetchone()
            if admin is None:
                raise ValueError('Active classroom administrator required.')
            if con.execute('SELECT 1 FROM decision_audit_events WHERE game_id=? AND comparison_basis=?',
                           (game_id, POLICY_BASIS)).fetchone():
                return dict(status='already_applied', game_id=game_id, policy=POLICY_ID)
            latest = con.execute('SELECT MAX(round_number) FROM round_results').fetchone()[0]
            current = con.execute('SELECT MAX(round_number) FROM market_reports').fetchone()[0]
            if latest != completed_round or current != completed_round + 1:
                raise ValueError(f'Round changed: completed {latest}, current {current}. Review before applying.')
            metadata = con.execute('''SELECT classroom_id,classroom_name FROM decision_audit_events
                WHERE game_id=? ORDER BY event_sequence DESC LIMIT 1''', (game_id,)).fetchone()
            if metadata is None:
                raise ValueError('Classroom audit metadata unavailable.')
            results = [dict(r) for r in con.execute('SELECT * FROM round_results ORDER BY round_number,team_name')]
            markets = {r['round_number']: dict(r) for r in con.execute('SELECT * FROM market_reports')}
            states = {r['team_name']: dict(r) for r in con.execute('SELECT * FROM team_states ORDER BY team_name')}
            scores, trace = replay_reputation(results, markets)
            if not states or set(scores) - set(states):
                raise ValueError('Missing team state; review classroom before applying.')
            active = {r[0] for r in con.execute("SELECT team_name FROM users WHERE role='team_leader' AND is_active=1")}
            benchmarks = [scores[r['team_name']] for r in results
                          if r['round_number'] == completed_round and r['team_name'] in active]
            new_entry_score = entry_score(benchmarks) if completed_round else OPENING_REPUTATION
            changes = [dict(team=name, before=state['reputation_score'], after=scores.get(name, new_entry_score),
                            trace=[r for r in trace if r['team'] == name]) for name, state in states.items()]
            summary = dict(status='preview', classroom=metadata['classroom_name'], game_id=game_id,
                           completed_round=completed_round, current_round=current, policy=POLICY_ID,
                           teams=[{k:v for k,v in change.items() if k != 'trace'} for change in changes])
            if not apply:
                return summary

            # Lock remains held while the online backup captures the pre-correction state.
            directory = path.parent / 'instructor_correction_backups'
            directory.mkdir(exist_ok=True)
            backup = directory / ('before_reputation_50_50_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(backup)) as destination:
                source.backup(destination)
                if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed; no changes made.')
            now = datetime.now(timezone.utc).isoformat()
            for change in changes:
                team, old, new = change['team'], change['before'], change['after']
                marker = POLICY_ID + '-' + hashlib.sha256((game_id + ':' + team).encode()).hexdigest()
                before = _snapshot(con, current, team)
                before['administrative_state'] = {'reputation_score': old}
                con.execute('UPDATE team_states SET reputation_score=?,updated_at=CURRENT_TIMESTAMP WHERE team_name=?', (new, team))
                after = _snapshot(con, current, team)
                after['administrative_state'] = {'reputation_score': new}
                after['reputation_replay'] = dict(policy=POLICY_ID, history_weight=0.5, floor=10, ceiling=100,
                                                 opening_score=OPENING_REPUTATION, late_entry_deduction=10,
                                                 completed_round=completed_round, trace=change['trace'])
                revision = con.execute('''SELECT COALESCE(MAX(revision),0)+1 FROM decision_audit_events
                    WHERE game_id=? AND team_name=? AND round_number=?''', (game_id, team, current)).fetchone()[0]
                reason = ('Instructor-authorized 50/50 reputation policy replay from recorded outcomes. '
                          'Late-entry penalty included once at entry; supersedes earlier current-score corrections. '
                          'Not a student submission or round rerun. Historical results, decisions, cash, products, '
                          f'investments and accounts unchanged. Backup: {backup}')
                event = dict(event_id=marker, game_id=game_id, classroom_id=metadata['classroom_id'],
                             classroom_name=metadata['classroom_name'], team_name=team, round_number=current,
                             revision=revision, occurred_at_utc=now, source='admin_submission',
                             actor_user_id=admin['user_id'], actor_username=admin_username, actor_role='admin',
                             comparison_basis=POLICY_BASIS, prior_round_number=completed_round,
                             change_count=1, reason=reason, before_json=json.dumps(before), after_json=json.dumps(after))
                con.execute(f"INSERT INTO decision_audit_events ({','.join(event)}) VALUES ({','.join(':'+k for k in event)})", event)
                con.execute('''INSERT INTO decision_audit_changes
                    (event_id,game_id,team_name,round_number,revision,occurred_at_utc,source,actor_username,
                     decision_group,slot_name,field_name,before_present,before_value_json,after_present,after_value_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (marker, game_id, team, current, revision, now, 'admin_submission', admin_username,
                     'Firm state', '', 'reputation_score', 1, json.dumps(old), 1, json.dumps(new)))
            con.commit()
            return dict(summary, status='applied', backup=str(backup))
        finally:
            if con.in_transaction:
                con.rollback()


def resolve_classroom(base_path, classroom_id):
    """Read an existing registry without creating or bootstrapping any databases."""
    base = Path(base_path).resolve(strict=True)
    registry = base.parent / (base.stem + '_classrooms.db')
    with closing(sqlite3.connect(registry.as_uri() + '?mode=ro', uri=True)) as con:
        row = con.execute('SELECT filename FROM classrooms WHERE classroom_id=? AND ready=1', (classroom_id,)).fetchone()
    if row is None:
        raise ValueError('Unknown classroom.')
    if classroom_id == 'default':
        return base
    folder = (base.parent / 'classrooms').resolve()
    path = (folder / row[0]).resolve(strict=True)
    if path.parent != folder:
        raise ValueError('Invalid classroom database path.')
    return path
