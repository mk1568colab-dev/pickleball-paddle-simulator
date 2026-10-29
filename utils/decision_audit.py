"""Append-only records of successful saved decisions, not unsaved UI activity."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import uuid

from utils.classrooms import _session
from utils.database import atomic_write, initialize_database


FIRM_FIELDS = (
    'archetype', 'overtime_capacity_units', 'capacity_expansion_units', 'raw_material_order_qty',
    'supplier_mix_offshore_pct', 'supplier_mix_balanced_pct', 'supplier_mix_premium_pct',
    'expedited_order_share_pct', 'max_backorder_units', 'planned_borrowing_amount',
)
PRODUCT_FIELDS = (
    'product_id', 'product_name', 'is_active', 'target_segment', 'selling_price_per_unit',
    'forecast_units', 'planned_production_units', 'qc_budget_per_unit',
    'target_finished_goods_inventory', 'retire_flag',
)
PIPELINE_FIELDS = (
    'project_id', 'project_name', 'target_segment', 'target_tech_generation', 'intended_slot_name',
    'investment_this_round', 'testing_intensity', 'planned_launch_round', 'launch_now', 'cancel_now',
)
SOURCE_LABELS = {
    'student_submission': 'Student submission',
    'admin_submission': 'Admin submission',
    'automatic_carry_forward': 'Automatic carry-forward',
}


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _fields(row, fields):
    return {name: row[name] for name in fields if name in row.keys()}


def _pipeline(connection, team):
    return {row['project_slot_name']: _fields(row, PIPELINE_FIELDS) for row in connection.execute(
        'SELECT * FROM product_development_projects WHERE LOWER(team_name)=LOWER(?) ORDER BY project_slot_name', (team,))}


def _snapshot(connection, round_number, team):
    firm = connection.execute('SELECT * FROM team_decisions WHERE round_number=? AND LOWER(team_name)=LOWER(?)',
                              (round_number, team)).fetchone()
    return {
        'firm': _fields(firm, FIRM_FIELDS) if firm else {},
        'products': {row['slot_name']: _fields(row, PRODUCT_FIELDS) for row in connection.execute(
            'SELECT * FROM product_decisions WHERE round_number=? AND LOWER(team_name)=LOWER(?) ORDER BY slot_name',
            (round_number, team))},
        'pipeline': _pipeline(connection, team),
    }


def _flat(snapshot):
    result = {('Firm', '', name): value for name, value in snapshot['firm'].items()}
    for group, key in (('Product', 'products'), ('Development', 'pipeline')):
        for slot, values in snapshot[key].items():
            result.update({(group, slot, field): value for field, value in values.items()})
    return result


def _actor(connection, team, submitted_by_user_id, automatic):
    session = _session()
    username = session.get('authenticated_username') if session is not None else None
    actor = connection.execute('SELECT * FROM users WHERE username=? AND is_active=1', (username,)).fetchone() if username else None
    if automatic:
        # Offline engine runs have no browser actor. A browser run must be an admin.
        if session is not None and (actor is None or actor['role'] != 'admin'):
            raise PermissionError('Automatic carry-forward requires an administrator.')
        return dict(source='automatic_carry_forward', actor_user_id=None, actor_username='System', actor_role='system',
                    initiated_by_user_id=actor['user_id'] if actor else None,
                    initiated_by_username=actor['username'] if actor else None)
    if actor is None or str(actor['user_id']) != str(submitted_by_user_id):
        raise PermissionError('The submitting account must match the authenticated account.')
    if actor['role'] != 'admin' and (actor['team_name'] or '').casefold() != team.casefold():
        raise PermissionError('Students can submit only for their assigned team.')
    return dict(source='admin_submission' if actor['role'] == 'admin' else 'student_submission',
                actor_user_id=actor['user_id'], actor_username=actor['username'], actor_role=actor['role'],
                initiated_by_user_id=None, initiated_by_username=None)


@contextmanager
def decision_revision(round_number, team_name, *, submitted_by_user_id=None, automatic=False, effective_projects=None):
    """Commit all plan writes and one immutable revision together, or neither."""
    from utils.game_exports import _classroom_metadata
    initialize_database()  # Additive schema only; never fabricate earlier history.
    classroom_id, classroom_name = _classroom_metadata()
    with atomic_write() as connection:
        actor = _actor(connection, team_name, submitted_by_user_id, automatic)
        canonical = connection.execute('SELECT team_name FROM users WHERE LOWER(team_name)=LOWER(?) LIMIT 1', (team_name,)).fetchone()
        team = canonical[0] if canonical else team_name
        prior = connection.execute('SELECT MAX(round_number) FROM team_decisions WHERE round_number<=? AND LOWER(team_name)=LOWER(?)',
                                   (round_number, team)).fetchone()[0]
        basis = 'same_round_saved_plan' if prior == round_number else 'prior_round_saved_plan' if prior else 'no_prior_saved_plan'
        before = _snapshot(connection, prior if prior else round_number, team)
        yield
        after = _snapshot(connection, round_number, team)
        if not after['firm']:
            raise ValueError('No saved firm decision exists for this revision.')
        if automatic:
            projects = effective_projects
            if projects is None:
                after['pipeline'] = {slot: dict(values, investment_this_round=0, testing_intensity=0,
                                              launch_now=0, cancel_now=0) for slot, values in before['pipeline'].items()}
            else:
                after['pipeline'] = {p.project_slot_name: _fields(p.to_dict(), PIPELINE_FIELDS)
                                     for p in projects if p.team_name.casefold() == team.casefold()}
        old, new = _flat(before), _flat(after)
        changed = [key for key in sorted(old.keys() | new.keys())
                   if key not in old or key not in new or old[key] != new[key]]
        game_id = connection.execute('SELECT game_id FROM decision_audit_context WHERE singleton=1').fetchone()[0]
        revision = connection.execute('SELECT COALESCE(MAX(revision),0)+1 FROM decision_audit_events WHERE game_id=? AND team_name=? AND round_number=?',
                                      (game_id, team, round_number)).fetchone()[0]
        event = dict(event_id=uuid.uuid4().hex, game_id=game_id, classroom_id=classroom_id, classroom_name=classroom_name,
                     team_name=team, round_number=round_number, revision=revision,
                     occurred_at_utc=datetime.now(timezone.utc).isoformat(timespec='microseconds'),
                     comparison_basis=basis, prior_round_number=prior, change_count=len(changed),
                     reason=('No team submission. Effective plan carried forward; development investment, testing, launch and cancellation are zero/off.'
                             if automatic else 'Successful explicit save/submit. Unsaved edits are not recorded.'),
                     before_json=_json(before), after_json=_json(after), **actor)
        columns = ', '.join(event)
        connection.execute(f"INSERT INTO decision_audit_events ({columns}) VALUES ({', '.join(':'+k for k in event)})", event)
        for group, slot, field in changed:
            key = (group, slot, field)
            connection.execute('''INSERT INTO decision_audit_changes
                (event_id,game_id,team_name,round_number,revision,occurred_at_utc,source,actor_username,
                 decision_group,slot_name,field_name,before_present,before_value_json,after_present,after_value_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (event['event_id'], game_id, team, round_number, revision, event['occurred_at_utc'], actor['source'], actor['actor_username'],
                 group, slot, field, int(key in old), _json(old.get(key)), int(key in new), _json(new.get(key))))


def save_audited_submission(firm, products, projects, product_lines, round_number, submitted_by_user_id):
    """Persist the existing submission payload with its actor and complete audit."""
    from models.schemas import ProductForecast
    from utils import repository as repo
    if any(record.team_name.casefold() != firm.team_name.casefold() for record in [*products, *projects, *product_lines]):
        raise PermissionError('All submitted records must belong to the selected team.')
    with decision_revision(round_number, firm.team_name, submitted_by_user_id=submitted_by_user_id):
        repo.save_team_decision(firm, round_number, submitted_by_user_id)
        repo.save_product_decisions(products, round_number)
        repo.save_product_forecasts([ProductForecast.from_dict(dict(p.to_dict(), round_number=round_number,
                                                                  forecast_units=p.forecast_units if p.is_active else 0)) for p in products])
        repo.save_product_development_projects(projects)
        repo.save_product_lines(product_lines)


def start_new_audit_game(connection):
    """Separate reused round/team names after a reset, without deleting history."""
    connection.execute('UPDATE decision_audit_context SET game_id=?, game_started_at_utc=? WHERE singleton=1',
                       (uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(timespec='microseconds')))


def load_audit_history():
    """Read this classroom's audit records; never initialize or modify its DB."""
    from utils.game_exports import _authorized_source
    with _authorized_source() as connection:
        import sqlite3
        connection.row_factory = sqlite3.Row
        if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='decision_audit_events'").fetchone():
            return None, [], []
        context = dict(connection.execute('SELECT * FROM decision_audit_context WHERE singleton=1').fetchone())
        events = [dict(row) for row in connection.execute('SELECT * FROM decision_audit_events ORDER BY event_sequence DESC')]
        changes = [dict(row) for row in connection.execute('SELECT * FROM decision_audit_changes ORDER BY change_id')]
        return context, events, changes
