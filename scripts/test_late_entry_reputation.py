"""Late-entry account tests using temporary classroom databases only."""

import ast
from dataclasses import replace
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from data.classroom_start import COMMON_PROFILE, COMMON_PROFILE_NAME, initial_state
from data.defaults import DEFAULT_MARKET_REPORT
from models.schemas import RoundResult, TeamDecision, ProductDecision
from engine import simulator
from utils.bootstrap import ensure_app_storage
from utils.classrooms import database_scope
from utils.database import get_connection
from utils.repository import (
    create_user, ensure_equal_start_team, load_team_states, save_market_report,
    save_round_results, save_team_state, update_user, load_product_lines,
)
from utils.team_entry import load_entry_reputation
from utils import team_excel_import as importer


def admin_functions():
    """Load real account handlers without running the page's top-level main()."""
    path = ROOT / "pages/5_Admin_User_Management.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name) and node.value.func.id == "main"
    )]
    namespace = {"__file__": str(path), "__name__": "admin_account_test"}
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace


class LateEntryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {
            "SIMULATOR_DB_PATH": str(Path(self.directory.name) / "classroom.db"),
            "SIMULATOR_ENV": "dev",
            "SIMULATOR_ENABLE_DEMO_ACCOUNTS": "false",
        })
        self.environment.start()
        ensure_app_storage()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def add_team(self, name, *, active=True):
        return create_user(name.lower().replace(" ", "_"), "test-hash",
                           "team_leader", name, active)

    def results(self, scores, round_number=1, *, completed=True, legacy=False):
        save_round_results([
            RoundResult(round_number=round_number, team_name=name,
                        archetype=COMMON_PROFILE_NAME, reputation_after_round=score)
            for name, score in scores
        ])
        if not legacy:
            with get_connection() as connection:
                connection.execute(
                    """INSERT INTO demand_commitments
                       (round_number, outlook_low, outlook_high, actual_demand,
                        locked_at, completed_at) VALUES (?, 100, 200, 150, ?, ?)""",
                    (round_number, "2026-01-01 00:00:00",
                     "2026-01-01 00:01:00" if completed else None),
                )
        if completed:
            save_market_report(replace(DEFAULT_MARKET_REPORT, round_number=round_number + 1))

    def incumbents(self, scores=(10, 20, 30, 40, 50)):
        names = [f"Firm {i}" for i in range(len(scores))]
        for name in names:
            self.add_team(name)
        self.results(list(zip(names, scores)))
        return names

    def reputation(self, name):
        return load_team_states(team_name=name)[0].reputation_score

    def existing_records(self, names):
        with get_connection() as connection:
            return {
                table: [tuple(row) for row in connection.execute(
                    f"SELECT * FROM {table} WHERE team_name IN "
                    f"({','.join('?' for _ in names)}) ORDER BY rowid", names)]
                for table in ("users", "team_states", "round_results", "product_lines",
                              "product_development_projects")
            }

    def test_initial_game_keeps_standard_baseline(self):
        self.add_team("Opening Team")
        snapshot = load_entry_reputation()
        self.assertEqual((snapshot.score, snapshot.team_count, snapshot.round_number), (60, 0, None))
        self.assertEqual(self.reputation("Opening Team"), 60)

    def test_manual_creation_uses_interpolated_twentieth_percentile(self):
        names = self.incumbents()
        before = self.existing_records(names)
        snapshot = load_entry_reputation()
        self.assertEqual((snapshot.score, snapshot.team_count, snapshot.round_number), (8, 5, 1))
        self.assertEqual(snapshot.benchmark_score, 18)
        self.add_team("Late Firm")
        state = load_team_states(team_name="Late Firm")[0]
        self.assertEqual(state, replace(initial_state("Late Firm"), reputation_score=8))
        self.assertEqual(before, self.existing_records(names))

    def test_latest_completed_results_not_live_state_or_pending_results(self):
        names = self.incumbents()
        self.results(list(zip(names, (40, 50, 60, 70, 80))), round_number=2)
        for name in names:
            save_team_state(replace(initial_state(name), reputation_score=99))
        self.results([(name, 1) for name in names], round_number=3, completed=False)
        snapshot = load_entry_reputation()
        self.assertEqual((snapshot.score, snapshot.round_number), (38, 2))

    def test_inactive_unplayed_deleted_and_admin_teams_do_not_count(self):
        self.incumbents()
        self.add_team("Inactive", active=False)
        self.add_team("Not Played")
        create_user("admin_only", "hash", "admin", None, True)
        save_round_results([
            RoundResult(1, name, COMMON_PROFILE_NAME, reputation_after_round=0)
            for name in ("Inactive", "Deleted", "admin_only")
        ])
        self.assertEqual(load_entry_reputation().team_count, 5)
        self.assertEqual(load_entry_reputation().score, 8)

    def test_multiple_logins_for_one_team_do_not_weight_percentile(self):
        self.incumbents()
        create_user("second_login", "hash", "team_leader", "Firm 0", True)
        self.assertEqual(load_entry_reputation().team_count, 5)
        self.assertEqual(load_entry_reputation().score, 8)

    def test_new_teams_without_results_do_not_lower_later_entry_scores(self):
        self.incumbents()
        for i in range(4):
            self.add_team(f"New Firm {i}")
            self.assertEqual(self.reputation(f"New Firm {i}"), 8)
        self.assertEqual(load_entry_reputation().team_count, 5)

    def test_existing_team_reputation_is_never_reinitialized(self):
        self.incumbents()
        user = self.add_team("Late Firm")
        save_team_state(replace(initial_state("Late Firm"), reputation_score=77.3,
                                cash_balance=12345, completed_rounds=[2]))
        ensure_equal_start_team("Late Firm")
        create_user("another_login", "hash", "team_leader", "Late Firm", True)
        update_user(user.user_id, user.username, "team_leader", "Late Firm", False)
        state = load_team_states(team_name="Late Firm")[0]
        self.assertEqual((state.reputation_score, state.cash_balance, state.completed_rounds),
                         (77.3, 12345, [2]))

    def test_single_team_and_zero_reputation_are_valid(self):
        self.incumbents((0,))
        self.add_team("Late Firm")
        self.assertEqual(self.reputation("Late Firm"), 0)
        self.assertEqual(load_entry_reputation().team_count, 1)

    def test_late_entry_without_active_benchmark_still_has_deduction(self):
        user = self.add_team("Inactive")
        self.results([("Inactive", 12)])
        update_user(user.user_id, user.username, "team_leader", "Inactive", False)
        self.add_team("New Firm")
        self.assertEqual(self.reputation("New Firm"), 50)

    def test_legacy_completed_rounds_without_commitment_are_supported(self):
        self.add_team("Legacy Firm")
        self.results([("Legacy Firm", 37.25)], legacy=True)
        self.add_team("New Firm")
        self.assertEqual(self.reputation("New Firm"), 27.25)

    def test_unfinished_first_round_is_not_a_benchmark(self):
        self.add_team("Existing")
        self.results([("Existing", 2)], completed=False)
        self.add_team("New Firm")
        self.assertEqual(self.reputation("New Firm"), 60)

    def test_classrooms_are_isolated(self):
        with database_scope(Path(self.directory.name) / "section_022.db"):
            self.incumbents((10, 20, 30, 40, 50))
        with database_scope(Path(self.directory.name) / "section_122.db"):
            self.incumbents((60, 70, 80, 90, 100))
            self.add_team("Late Firm")
            self.assertEqual(self.reputation("Late Firm"), 50)
        with database_scope(Path(self.directory.name) / "section_022.db"):
            self.add_team("Late Firm")
            self.assertEqual(self.reputation("Late Firm"), 8)

    def test_excel_batch_uses_one_snapshot_and_preserves_incumbents(self):
        names = self.incumbents()
        before = self.existing_records(names)
        rows = [dict(team_name=f"Excel {i}", username=f"excel_{i}",
                     password="ExamplePass123!", row=i + 2) for i in range(3)]
        with patch.object(importer, "load_entry_reputation", wraps=load_entry_reputation) as loader:
            self.assertEqual(importer.create_teams_from_workbook(rows), 3)
        self.assertEqual(loader.call_count, 1)
        for row in rows:
            self.assertEqual(self.reputation(row["team_name"]), 8)
        self.assertEqual(before, self.existing_records(names))

    def test_numbered_generator_and_csv_import_freeze_one_snapshot_each(self):
        self.incumbents()
        namespace = admin_functions()
        loader = Mock(wraps=load_entry_reputation)
        namespace["load_entry_reputation"] = loader
        generated = namespace["_run_team_account_generation"](
            team_count=3, start_number=1, team_name_prefix="Generated",
            username_prefix="generated", username_suffix="", starting_cash_balance=50000,
            is_active=True, update_existing=False,
        )
        self.assertEqual((generated["created_count"], generated["error_rows"]), (3, []))
        self.assertEqual(loader.call_count, 1)
        loader.reset_mock()
        imported = namespace["_run_bulk_import"](pd.DataFrame([
            dict(username=f"csv_{i}", password="ExamplePass123!", team_name=f"CSV {i}")
            for i in range(3)
        ]), False)
        self.assertEqual((imported["created_count"], imported["error_rows"]), (3, []))
        self.assertEqual(loader.call_count, 1)
        for name in ["Generated 1", "Generated 2", "Generated 3", "CSV 0", "CSV 1", "CSV 2"]:
            self.assertEqual(self.reputation(name), 8)

    def test_admin_page_shows_reputation_and_source_round(self):
        from streamlit.testing.v1 import AppTest
        self.incumbents()
        create_user("test_admin", "hash", "admin", None, True)
        app = AppTest.from_file(str(ROOT / "pages/5_Admin_User_Management.py"))
        app.session_state["authenticated_username"] = "test_admin"
        with patch("utils.auth.render_user_sidebar"):
            app.run(timeout=30)
        self.assertFalse(app.exception)
        metric = next(m for m in app.metric if m.label == "New-Team Starting Reputation")
        self.assertEqual(metric.value, "8.00")
        self.assertTrue(any("Round 1 | 5 active teams | 20th percentile" in c.value for c in app.caption))
        self.assertTrue(any("minus 10 entry points; minimum 0" in c.value for c in app.caption))

    def test_penalty_boundaries_and_cap(self):
        self.incumbents((100,))
        for benchmark, expected in ((0, 0), (5, 0), (10, 0), (10.01, .01), (30, 20), (60, 50), (100, 50)):
            with self.subTest(benchmark=benchmark):
                save_round_results([RoundResult(1, 'Firm 0', COMMON_PROFILE_NAME, reputation_after_round=benchmark)])
                self.assertEqual(load_entry_reputation().score, expected)

    def test_first_round_engine_preserves_zero_and_low_assigned_scores(self):
        firm = TeamDecision.from_dict({'team_name': 'New', 'archetype': COMMON_PROFILE_NAME})
        for score in (0, .01, 8, 50, 60):
            with self.subTest(score=score):
                state = replace(initial_state('New'), reputation_score=score)
                initialized = simulator._initialize_team_state(state, firm, COMMON_PROFILE)
                self.assertEqual(initialized.reputation_score, score)
                self.assertEqual(state.reputation_score, score)
        self.assertEqual(simulator._initialize_team_state(None, firm, COMMON_PROFILE).reputation_score, 60)

    def test_zero_entry_survives_preview_and_first_competitive_round(self):
        self.incumbents((0,))
        self.add_team('Late Firm')
        state = load_team_states(team_name='Late Firm')[0]
        firm = TeamDecision.from_dict({'team_name': 'Late Firm', 'archetype': COMMON_PROFILE_NAME})
        lines = load_product_lines(team_name='Late Firm')
        products = [ProductDecision.from_dict(dict(line.to_dict(), selling_price_per_unit=150,
                    planned_production_units=100 if line.is_active else 0, forecast_units=100 if line.is_active else 0,
                    qc_budget_per_unit=3)) for line in lines]
        market = replace(DEFAULT_MARKET_REPORT, round_number=2, total_demand=200)
        with patch.object(simulator, '_update_reputation', wraps=simulator._update_reputation) as update:
            simulator.preview_team_decision(market, firm, products, [], lines, [], [], [], [state])
            simulator.run_round(market, [firm], lines, products, [], [state])
            self.assertTrue(update.call_args_list)
            self.assertTrue(all(call.kwargs['current_reputation'] == 0 for call in update.call_args_list))
        self.assertEqual(self.reputation('Late Firm'), 0)

    def test_existing_low_and_zero_scores_not_reinitialized_or_penalized_again(self):
        self.incumbents((30,))
        self.add_team('Late Firm')
        firm = TeamDecision.from_dict({'team_name': 'Late Firm', 'archetype': COMMON_PROFILE_NAME})
        for score in (0, 12):
            state = replace(initial_state('Late Firm'), reputation_score=score, completed_rounds=[2])
            save_team_state(state)
            self.assertEqual(simulator._initialize_team_state(state, firm, COMMON_PROFILE), state)
            ensure_equal_start_team('Late Firm')
            self.assertEqual(self.reputation('Late Firm'), score)


if __name__ == "__main__":
    unittest.main()
