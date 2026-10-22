import os
from pathlib import Path
import sys
import tempfile
import unittest
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temp = tempfile.TemporaryDirectory()
os.environ["SIMULATOR_DB_PATH"] = str(Path(temp.name) / "test.db")
os.environ["SIMULATOR_ENABLE_DEMO_ACCOUNTS"] = "false"
from data.classroom_start import COMMON_PROFILE_NAME, handover_rows
from engine.classroom_brief import initial_catalog, completed_catalog, strategy_signals
from models.schemas import TeamDecision, ProductDecision, ProductRoundResult
from utils.repository import (create_user, load_team_states, load_product_lines,
    ensure_equal_start_team, save_team_state, load_team_archetypes, save_team_decision)


class EqualStartTests(unittest.TestCase):
    def test_equal_new_accounts_and_no_reset(self):
        for i in range(4):
            create_user(f"test{i}", "not-a-login-hash", "team_leader", f"Team {i}", True)
        states = load_team_states()
        self.assertEqual(len(states), 4)
        normalized = [{k: v for k, v in s.to_dict().items() if k != "team_name"} for s in states]
        self.assertTrue(all(s == normalized[0] for s in normalized))
        self.assertEqual(states[0].cash_balance, 50000)
        self.assertEqual(states[0].capacity_units, 300)
        self.assertEqual(len([p for p in load_product_lines(team_name="Team 0") if p.is_active]), 2)
        self.assertTrue(load_product_lines(team_name="Team 0")[2].retirement_flag)
        save_team_state(replace(states[0], cash_balance=43210))
        ensure_equal_start_team(states[0].team_name)
        self.assertEqual(load_team_states(team_name=states[0].team_name)[0].cash_balance, 43210)
        with self.assertRaises(ValueError):
            save_team_decision(TeamDecision.from_dict({"team_name": states[0].team_name, "archetype": "Premium Quality"}), 1)

    def test_only_common_profile_available(self):
        self.assertEqual([a.name for a in load_team_archetypes()], [COMMON_PROFILE_NAME])

    def test_opening_catalog_is_independent_of_drafts(self):
        rows = initial_catalog(["Team 1", "Team 2"])
        self.assertEqual(len(rows), 4)
        self.assertEqual(set(rows[0]), {"Team", "Paddle", "Segment", "Technology", "Price ($)"})
        self.assertEqual([r["Price ($)"] for r in rows], [149, 99, 149, 99])

    def test_completed_catalog_filters_round_inactive_and_retired(self):
        base = ProductRoundResult.from_dict({"round_number": 1, "team_name": "Team 1", "slot_name": "A", "product_name": "Public", "selling_price_per_unit": 150})
        decision = ProductDecision.from_dict({"team_name": "Team 1", "slot_name": "A", "is_active": True})
        rows = completed_catalog([base, replace(base, round_number=2, selling_price_per_unit=999)], 1, [decision])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Price ($)"], 150)
        self.assertEqual(completed_catalog([replace(base, retired_this_round=True)], 1, [decision]), [])
        self.assertEqual(completed_catalog([base], 1, []), [])
        self.assertEqual(len(completed_catalog([replace(base, launched_this_round=True)], 1, [])), 1)

    def test_signals_can_overlap_without_changing_decisions(self):
        firm = TeamDecision.from_dict({"team_name": "Test", "archetype": COMMON_PROFILE_NAME, "capacity_expansion_units": 40, "overtime_capacity_units": 20, "supplier_mix_premium_pct": 50})
        product = ProductDecision.from_dict({"team_name": "Test", "is_active": True, "target_segment": "premium", "planned_production_units": 350, "selling_price_per_unit": 199, "qc_budget_per_unit": 6})
        before = firm.to_dict()
        signals = strategy_signals(firm, [product], [], 300)
        self.assertEqual(signals[0]["Signals"], "3/3")
        self.assertEqual(signals[2]["Signals"], "3/3")
        self.assertEqual(before, firm.to_dict())
        self.assertFalse(any("Community" in s["Direction"] for s in signals))

    def test_handover_is_fictional_and_repeatable(self):
        self.assertEqual(len(handover_rows()), 6)
        self.assertEqual(handover_rows(), handover_rows())

    def test_student_pages_render_without_results(self):
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest
        create_user("ui_admin", "not-a-login-hash", "admin", None, True)
        create_user("ui_student", "not-a-login-hash", "team_leader", "UI Team", True)
        from utils.repository import set_round_submissions_open, load_team_decision
        from utils.demand_protocol import save_outlook
        save_outlook(1, 1000, 1400)
        set_round_submissions_open(1, True)
        root = Path(__file__).resolve().parents[1]
        for page in ["11_Market_Catalog.py", "12_Company_Brief.py", "2_Team_Decisions.py"]:
            with patch("streamlit.page_link"):
                app = AppTest.from_file(str(root / "pages" / page), default_timeout=30)
                app.session_state["authenticated_username"] = "ui_student"
                app.run()
                self.assertEqual(len(app.exception), 0, str(app.exception))
                if page == "2_Team_Decisions.py":
                    self.assertFalse(any(s.label == "Archetype" for s in app.selectbox))
                    next(b for b in app.button if b.label == "Save Portfolio and Pipeline Decision").click().run()
                    self.assertEqual(len(app.exception), 0, str(app.exception))
                    self.assertIsNotNone(load_team_decision(1, "UI Team"))
        with patch("streamlit.page_link"):
            app = AppTest.from_file(str(root / "pages" / "12_Company_Brief.py"), default_timeout=30)
            app.session_state["authenticated_username"] = "ui_student"
            app.run()
            self.assertEqual(len(app.exception), 0, str(app.exception))


if __name__ == "__main__":
    unittest.main()
