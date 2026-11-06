"""One-time repair checks on disposable classrooms only."""
from contextlib import closing
from dataclasses import replace
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
from models.schemas import RoundResult
from utils.database import get_connection
from utils.repository import create_user, save_market_report, save_round_results, save_team_state
from utils.reputation_adjustments import adjust_late_entry_reputation


class AdjustmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'classroom.db'
        self.env = patch.dict(os.environ, {'SIMULATOR_DB_PATH': str(self.db), 'SIMULATOR_ENV': 'dev',
                                          'SIMULATOR_ENABLE_DEMO_ACCOUNTS': 'false'})
        self.env.start()
        create_user('admin', 'test-hash', 'admin', None, True)
        create_user('old', 'test-hash', 'team_leader', 'Opening', True)
        create_user('late', 'test-hash', 'team_leader', 'Late', True)
        save_round_results([RoundResult(1, 'Opening', COMMON_PROFILE_NAME),
                            RoundResult(2, 'Late', COMMON_PROFILE_NAME, reputation_after_round=11.66)])
        save_market_report(replace(DEFAULT_MARKET_REPORT, round_number=3))
        save_team_state(replace(initial_state('Late'), reputation_score=11.66, completed_rounds=[2]))
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

    def run_adjustment(self, **overrides):
        args = dict(team='Late', game_id=self.game, expected_round=3, expected_score=11.66, apply=True)
        args.update(overrides)
        return adjust_late_entry_reputation(self.db, **args)

    def test_only_current_reputation_and_appended_audit_change(self):
        before = self.records()
        result = self.run_adjustment()
        self.assertEqual((result['status'], result['before'], result['after']), ('applied', 11.66, 1.66))
        self.assertEqual(before, self.records(result['backup']))
        after = self.records()
        self.assertEqual({t for t in before if before[t] != after[t]},
                         {'team_states', 'decision_audit_events', 'decision_audit_changes'})
        with get_connection() as con:
            state = dict(con.execute("SELECT * FROM team_states WHERE team_name='Late'").fetchone())
            with closing(sqlite3.connect(result['backup'])) as old:
                state_before = dict(old.execute("SELECT team_name,cash_balance FROM team_states").fetchall())
            self.assertEqual(state['cash_balance'], state_before['Late'])
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(len(after['decision_audit_events']), len(before['decision_audit_events']) + 1)

    def test_duplicate_run_is_noop(self):
        self.run_adjustment()
        before = self.records()
        self.assertEqual(self.run_adjustment()['status'], 'already_applied')
        self.assertEqual(self.records(), before)

    def test_preview_does_not_write_or_create_backup(self):
        before = self.records()
        self.assertEqual(self.run_adjustment(apply=False)['after'], 1.66)
        self.assertEqual(self.records(), before)
        self.assertFalse((self.db.parent / 'instructor_correction_backups').exists())

    def test_wrong_game_round_score_and_invalid_deductions_abort(self):
        before = self.records()
        for args in ({'game_id': 'wrong'}, {'expected_round': 4}, {'expected_score': 10},
                     {'points': -1}, {'points': float('nan')}, {'admin_username': 'late'}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.run_adjustment(**args)
            self.assertEqual(self.records(), before)

    def test_opening_team_cannot_be_penalized(self):
        before = self.records()
        with self.assertRaises(ValueError):
            self.run_adjustment(team='Opening', expected_score=60)
        self.assertEqual(self.records(), before)

    def test_reputation_never_goes_negative(self):
        save_team_state(replace(initial_state('Late'), reputation_score=3, completed_rounds=[2]))
        result = self.run_adjustment(expected_score=3)
        self.assertEqual((result['after'], result['actual_deduction']), (0, 3))

    def test_failed_audit_rolls_back_score_change(self):
        before = self.records()
        with patch('utils.reputation_adjustments._snapshot', side_effect=[{}, RuntimeError('failed')]):
            with self.assertRaises(RuntimeError):
                self.run_adjustment()
        self.assertEqual(self.records(), before)


if __name__ == '__main__':
    unittest.main()
