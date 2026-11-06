"""50/50 formula and operator migration checks on disposable databases."""
from contextlib import closing
from dataclasses import replace
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.classroom_start import COMMON_PROFILE_NAME, initial_state
from data.defaults import DEFAULT_MARKET_REPORT
from engine.reputation import POLICY_BASIS, entry_score, reputation_step, replay_reputation
from models.schemas import RoundResult
from utils.database import get_connection
from utils.repository import create_user, save_market_report, save_round_results, save_team_state
from utils.reputation_adjustments import adjust_late_entry_reputation
from utils.reputation_recalculation import recalculate_reputation
from utils.team_entry import load_entry_reputation


class FormulaTests(unittest.TestCase):
    def test_half_history_half_performance(self):
        self.assertEqual(reputation_step(60, 1, 0, 0, 100)['reputation'], 80)
        self.assertEqual(reputation_step(60, .5, 0, 0, 100)['reputation'], 50)

    def test_floor_and_recovery(self):
        score = 60
        for _ in range(20):
            score = reputation_step(score, 0, .1, 0, 100)['reputation']
        self.assertEqual(score, 10)
        self.assertEqual(reputation_step(score, 1, 0, 0, 100)['reputation'], 55)
        self.assertEqual(reputation_step(100, 1, 0, 0, 100)['reputation'], 100)

    def test_no_production_gets_no_free_quality_credit(self):
        self.assertEqual(reputation_step(60, 0, 0, 1, 0)['reputation'], 30)

    def test_no_service_demand_holds_reputation(self):
        self.assertEqual(reputation_step(40, 1, 0, 1, 100, has_service_demand=False)['reputation'], 40)

    def test_quality_sensitivity_and_precision(self):
        self.assertGreater(reputation_step(60, 1, .05, -1, 100)['reputation'],
                           reputation_step(60, 1, .05, 1, 100)['reputation'])
        self.assertEqual(reputation_step(60, .723456, .017123, .5, 200),
                         reputation_step(60, .7235, .0171, .5, 200))

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            reputation_step(60, float('nan'), .01, 0, 100)

    def test_late_entry_floor_cap_and_percentile(self):
        self.assertEqual(entry_score([40, 50, 60]), 34)
        self.assertEqual(entry_score([0, 0]), 10)
        self.assertEqual(entry_score([100]), 50)


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'classroom.db'
        self.env = patch.dict(os.environ, {'SIMULATOR_DB_PATH': str(self.db), 'SIMULATOR_ENV': 'dev',
                                          'SIMULATOR_ENABLE_DEMO_ACCOUNTS': 'false'})
        self.env.start()
        create_user('admin', 'test-hash', 'admin', None, True)
        for name in ('Opening', 'Late', 'Unplayed'):
            create_user(name.lower(), 'test-hash', 'team_leader', name, True)
            save_team_state(replace(initial_state(name), reputation_score=0, cash_balance=123456))
        for number in (1, 2, 3):
            save_market_report(replace(DEFAULT_MARKET_REPORT, round_number=number, quality_sensitivity=0))
        self.results = [RoundResult(r, name, COMMON_PROFILE_NAME, fill_rate=1, defect_rate=0,
                                   actual_production_units=100, demand_allocated=100, reputation_after_round=0)
                        for r, name in ((1, 'Opening'), (2, 'Opening'), (2, 'Late'))]
        save_round_results(self.results)
        with get_connection() as con:
            self.game = con.execute('SELECT game_id FROM decision_audit_context').fetchone()[0]
            con.execute('''INSERT INTO decision_audit_events
                (event_id,game_id,classroom_id,classroom_name,team_name,round_number,revision,
                 occurred_at_utc,source,actor_username,actor_role,comparison_basis,change_count,reason,before_json,after_json)
                VALUES ('fixture',?,'default','Test Class','Late',2,1,'test','student_submission',
                        'late','team_leader','fixture',0,'fixture','{}','{}')''', (self.game,))

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def records(self, db=None):
        with closing(sqlite3.connect(db or self.db)) as con:
            return {t: con.execute('SELECT * FROM ' + t).fetchall() for (t,) in
                    con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}

    def run_replay(self, **kwargs):
        options = dict(game_id=self.game, completed_round=2, admin_username='admin', apply=True)
        options.update(kwargs)
        return recalculate_reputation(self.db, **options)

    def test_only_reputation_and_audit_change_backup_is_exact(self):
        before = self.records()
        result = self.run_replay()
        after = self.records()
        self.assertEqual(before, self.records(result['backup']))
        self.assertEqual({t for t in before if before[t] != after[t]},
                         {'team_states', 'decision_audit_events', 'decision_audit_changes'})
        with get_connection() as con, closing(sqlite3.connect(result['backup'])) as original:
            original.row_factory = sqlite3.Row
            for row in con.execute('SELECT * FROM team_states'):
                old = dict(original.execute('SELECT * FROM team_states WHERE team_name=?', (row['team_name'],)).fetchone())
                self.assertEqual({k:v for k,v in dict(row).items() if k not in ('reputation_score','updated_at')},
                                 {k:v for k,v in old.items() if k not in ('reputation_score','updated_at')})
            trace = json.loads(con.execute('SELECT after_json FROM decision_audit_events WHERE comparison_basis=? AND team_name=?',
                                           (POLICY_BASIS, 'Late')).fetchone()[0])['reputation_replay']['trace']
            self.assertEqual((trace[0]['previous'], trace[0]['reputation']), (50, 75))
        self.assertEqual({r['team']:r['after'] for r in result['teams']}, {'Opening':90, 'Late':75, 'Unplayed':50})

    def test_preview_and_duplicate_apply_do_not_write(self):
        before = self.records()
        self.assertEqual(self.run_replay(apply=False)['status'], 'preview')
        self.assertEqual(self.records(), before)
        self.assertFalse((self.db.parent / 'instructor_correction_backups').exists())
        self.run_replay()
        before = self.records()
        self.assertEqual(self.run_replay()['status'], 'already_applied')
        self.assertEqual(self.records(), before)

    def test_wrong_game_round_admin_abort(self):
        before = self.records()
        for options in ({'game_id':'wrong'}, {'completed_round':1}, {'admin_username':'late'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.run_replay(**options)
            self.assertEqual(before, self.records())

    def test_missing_market_and_duplicate_results_are_rejected(self):
        rows = [r.to_dict() for r in self.results]
        with self.assertRaises(ValueError):
            replay_reputation(rows, {})
        with self.assertRaises(ValueError):
            replay_reputation(rows + rows, {1:{'quality_sensitivity':0}, 2:{'quality_sensitivity':0}})

    def test_failed_audit_rolls_back_all_teams(self):
        before = self.records()
        with patch('utils.reputation_recalculation._snapshot', side_effect=[{}, {}, RuntimeError('audit failed')]):
            with self.assertRaises(RuntimeError):
                self.run_replay()
        self.assertEqual(before, self.records())

    def test_old_deduction_cannot_be_applied_again(self):
        self.run_replay()
        before = self.records()
        with self.assertRaisesRegex(ValueError, 'Superseded'):
            adjust_late_entry_reputation(self.db, team='Late', game_id=self.game, expected_round=3, expected_score=75, apply=True)
        self.assertEqual(self.records(), before)

    def test_entry_uses_rebased_state_not_original_historical_score(self):
        self.run_replay()
        entry = load_entry_reputation()
        self.assertEqual((entry.score, entry.benchmark_score), (50, 78))
        with get_connection() as con:
            con.execute("UPDATE team_states SET reputation_score=40 WHERE team_name='Opening'")
            con.execute("UPDATE team_states SET reputation_score=50 WHERE team_name='Late'")
        self.assertEqual(load_entry_reputation().score, 32)
        with get_connection() as con:
            con.execute("UPDATE decision_audit_context SET game_id='new-game'")
        self.assertEqual(load_entry_reputation().score, 10)


if __name__ == '__main__':
    unittest.main()
