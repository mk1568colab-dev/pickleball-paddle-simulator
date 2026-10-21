"""Exercise bulk removal only in fresh temporary databases, including rollback."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

from engine.simulator import run_round
from models.schemas import ProductForecast
from utils import repository as repo
from utils.bootstrap import ensure_app_storage
from utils.security import hash_password
import run_strategy_simulation as strategy


@contextmanager
def connection(path):
    c = sqlite3.connect(path)
    try:
        with c:
            yield c
    finally:
        c.close()


def snapshot(path):
    with connection(path) as c:
        result = {}
        for (table,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
            q = '"' + table.replace('"', '""') + '"'
            cols = [r[1] for r in c.execute("PRAGMA table_info(" + q + ")")]
            rows = []
            for row in c.execute("SELECT * FROM " + q):
                record = dict(zip(cols, row))
                if table == "team_archetypes":
                    record.pop("updated_at", None)
                rows.append(repr(record))
            result[table] = sorted(rows)
        return result


class BulkRemovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="kiki_bulk_removal_")
        cls.base = Path(cls.directory.name)
        cls.env = patch.dict(os.environ, {"SIMULATOR_ENV": "prod", "SIMULATOR_ENABLE_DEMO_ACCOUNTS": "0"})
        cls.env.start()
        cls.original_path = os.environ.get("SIMULATOR_DB_PATH")
        cls.fixture = cls.base / "fixture.db"
        os.environ["SIMULATOR_DB_PATH"] = str(cls.fixture)
        ensure_app_storage()
        password_hash = hash_password("FixturePassword123!")
        repo.create_initial_admin("fixture_admin", password_hash)
        cls.names = ["Alpha's Team", "Beta", "Gamma"]
        specs = strategy.build_team_specs(3, tuple(strategy.DEFAULT_STRATEGY_ROTATION), repo.load_team_archetypes())
        market = repo.load_market_report()
        for name, team in zip(cls.names, specs):
            team["team_name"] = name
            user = repo.create_user("fixture_" + str(cls.names.index(name)), password_hash, "team_leader", name, True)
            lines = strategy.lines_for_team(name, team["archetype"], [])
            products = strategy.build_product_decisions(team, lines, 1)
            firm = strategy.build_team_decision(team, sum(p.planned_production_units for p in products if p.is_active), sum(p.forecast_units for p in products if p.is_active))
            repo.save_product_lines(lines)
            repo.save_team_decision(firm, 1, user.user_id)
            repo.save_product_decisions(products, 1)
            repo.save_product_forecasts([
                ProductForecast(1, name, p.product_id, p.slot_name, p.product_name, p.forecast_units)
                for p in products
            ])
            repo.save_product_development_projects(strategy.build_project_decisions(team, [], 1, market))
        results, products, states, lines, projects, forecasts = run_round(market, repo.load_team_decisions(1), repo.load_product_lines(), repo.load_product_decisions(1), repo.load_product_development_projects(), [])
        repo.save_round_results(results)
        repo.save_product_round_results(products)
        repo.save_team_states(states)
        repo.save_product_lines(lines)
        repo.save_product_development_projects(projects)
        repo.save_forecast_accuracy_results(forecasts)
        repo.set_round_submissions_open(1, False, "Fixture round")

    @classmethod
    def tearDownClass(cls):
        if cls.original_path is None:
            os.environ.pop("SIMULATOR_DB_PATH", None)
        else:
            os.environ["SIMULATOR_DB_PATH"] = cls.original_path
        cls.env.stop()
        cls.directory.cleanup()

    def setUp(self):
        self.path = self.base / (self.id().split(".")[-1] + ".db")
        with connection(self.fixture) as src, connection(self.path) as dst:
            src.backup(dst)
        os.environ["SIMULATOR_DB_PATH"] = str(self.path)
        self.before = snapshot(self.path)

    def assert_admin_and_market_kept(self):
        after = snapshot(self.path)
        for table in ("market_reports", "classroom_rounds", "team_archetypes"):
            self.assertEqual(self.before[table], after[table])
        before_admin = [r for r in self.before["users"] if "fixture_admin" in r]
        self.assertEqual(before_admin, [r for r in after["users"] if "fixture_admin" in r])

    def test_subset_permanent_case_duplicates_and_quoted_name(self):
        counts = repo.remove_teams_data([" alpha'S team ", "Beta", "BETA"], delete_team_leader_accounts=True)
        self.assertEqual(counts["deleted_team_leader_accounts"], 2)
        for table, rows in self.before.items():
            if table not in ("team_archetypes", "market_reports", "classroom_rounds"):
                kept = [r for r in rows if "Gamma" in r]
                self.assertEqual(kept, [r for r in snapshot(self.path)[table] if "Gamma" in r])
        with connection(self.path) as c:
            for table, count in counts.items():
                if table in self.before and table != "users":
                    self.assertGreater(count, 0, table)
                    self.assertEqual(c.execute(f"SELECT COUNT(*) FROM {table} WHERE team_name <> ?", ("Gamma",)).fetchone()[0], 0)
        self.assert_admin_and_market_kept()

    def test_all_teams_keeps_admin_and_market(self):
        counts = repo.remove_teams_data(repo.load_team_names(), delete_team_leader_accounts=True)
        self.assertEqual(counts["deleted_team_leader_accounts"], 3)
        self.assertEqual([u.username for u in repo.load_users()], ["fixture_admin"])
        self.assertEqual(repo.load_team_names(), [])
        self.assert_admin_and_market_kept()

    def test_default_deactivation_preserves_passwords(self):
        before = {u.user_id: u for u in repo.load_users()}
        result = repo.remove_teams_data(self.names[:2])
        self.assertEqual(result["deactivated_team_leader_accounts"], 2)
        for u in repo.load_users():
            self.assertEqual(u.password_hash, before[u.user_id].password_hash)
            self.assertEqual(u.is_active, u.team_name not in self.names[:2])
        self.assert_admin_and_market_kept()

    def test_optional_keep_accounts_active_and_single_api(self):
        result = repo.remove_team_data(self.names[0], deactivate_team_leaders=False)
        self.assertEqual(result["deactivated_team_leader_accounts"], 0)
        self.assertTrue(all(u.is_active for u in repo.load_users()))
        self.assertEqual(repo.load_round_results(team_name=self.names[0]), [])
        self.assert_admin_and_market_kept()

    def test_failure_on_second_account_rolls_back_all_team_records(self):
        with connection(self.path) as c:
            c.execute("CREATE TRIGGER fail_fixture_delete BEFORE DELETE ON users WHEN OLD.username='fixture_1' BEGIN SELECT RAISE(ABORT,'forced fixture failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            repo.remove_teams_data(self.names[:2], delete_team_leader_accounts=True)
        self.assertEqual(snapshot(self.path), self.before)

    def test_invalid_selection_does_not_change_records(self):
        for value in ([], "Beta", [""], ["Beta", "  "], [None]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                repo.remove_teams_data(value)
            self.assertEqual(snapshot(self.path), self.before)

    def test_bulk_ui_confirmation_selection_and_delete_all(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Install app requirements to run the UI checks.")
        from utils import auth
        with patch.object(auth, "_render_sidebar_navigation", lambda user: None):
            at = AppTest.from_file(str(ROOT / "pages/5_Admin_User_Management.py"), default_timeout=20)
            at.session_state[auth.SESSION_USER_KEY] = "fixture_admin"
            at.run()
            self.assertFalse(at.exception, list(at.exception))
            self.assertTrue(at.button(key="remove_selected_teams").disabled)
            at.multiselect(key="remove_team_selection_False").set_value(self.names[:2]).run()
            at.button(key="remove_selected_teams").click().run()
            self.assertTrue(any("No teams were removed" in e.value for e in at.error))
            self.assertEqual(snapshot(self.path), self.before)
            confirmation = next(t for t in at.text_input if t.label.startswith('Type "'))
            confirmation.set_value("REMOVE 2 TEAMS").run()
            at.multiselect(key="remove_team_selection_False").set_value(self.names[1:]).run()
            self.assertEqual(next(t for t in at.text_input if t.label.startswith('Type "')).value, "")
            at.checkbox(key="remove_all_teams").check().run()
            self.assertEqual(set(at.multiselect(key="remove_team_selection_True").value), set(self.names))
            next(c for c in at.checkbox if c.label.startswith("Permanently delete")).check().run()
            next(t for t in at.text_input if t.label.startswith('Type "')).set_value("REMOVE 3 TEAMS").run()
            at.button(key="remove_selected_teams").click().run()
            self.assertFalse(at.exception, list(at.exception))
            self.assertTrue(any("Removed 3 team(s)" in s.value for s in at.success))
            self.assertEqual([u.username for u in repo.load_users()], ["fixture_admin"])
            self.assert_admin_and_market_kept()


if __name__ == "__main__":
    unittest.main(verbosity=2)
