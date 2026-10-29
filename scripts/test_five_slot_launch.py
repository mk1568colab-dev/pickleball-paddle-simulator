import os
import sys
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temp = tempfile.TemporaryDirectory()
os.environ['SIMULATOR_DB_PATH'] = str(Path(temp.name) / 'test.db')
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'
from data.classroom_start import COMMON_PROFILE_NAME, initial_state
from data.defaults import DEFAULT_MARKET_REPORT
from models.schemas import TeamDecision, ProductDecision, ProductDevelopmentProject
from utils.repository import create_user, load_product_lines, save_product_development_projects, load_product_development_projects
from engine.simulator import run_round, estimate_development_project, _progress_projects


class LaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_user('launch_test', 'not-a-login-hash', 'team_leader', 'Launch Test', True)

    def project(self, slot='D'):
        return ProductDevelopmentProject.from_dict(dict(team_name='Launch Test',
            project_name='New Paddle', intended_slot_name=slot, target_segment='premium',
            target_tech_generation=2, created_round=1, planned_launch_round=2,
            investment_this_round=20000, testing_intensity=1, launch_now=True))

    def simulate(self, project):
        lines = load_product_lines(team_name='Launch Test')
        decisions = [ProductDecision.from_dict(dict(team_name='Launch Test',
            slot_name=p.slot_name, product_name=p.product_name, is_active=p.is_active,
            target_segment=p.target_segment, selling_price_per_unit=189,
            forecast_units=40, planned_production_units=40, qc_budget_per_unit=3)) for p in lines]
        firm = TeamDecision.from_dict(dict(team_name='Launch Test', archetype=COMMON_PROFILE_NAME,
            supplier_mix_offshore_pct=30, supplier_mix_balanced_pct=50, supplier_mix_premium_pct=20))
        return run_round(replace(DEFAULT_MARKET_REPORT, round_number=3), [firm], lines,
                         decisions, [project], [initial_state('Launch Test')])

    def ready_project(self, slot='D'):
        return replace(self.project(slot), cumulative_investment=20000,
                       cumulative_testing=1, launch_readiness_score=100, status='launch_ready')

    def test_launch_into_C_and_D_keeps_two_originals(self):
        for slot in ['C', 'D']:
            with self.subTest(slot=slot):
                output = self.simulate(self.ready_project(slot))
                lines = {p.slot_name: p for p in output[3]}
                self.assertEqual(len(lines), 4)
                self.assertEqual(lines[slot].product_name, 'New Paddle')
                self.assertTrue(lines[slot].is_active)
                self.assertTrue(lines['A'].is_active and lines['B'].is_active)
                self.assertEqual(sum(p.is_active for p in lines.values()), 3)

    def test_fifth_and_sixth_slots_rejected(self):
        for slot in ['E', 'F']:
            with self.subTest(slot=slot), self.assertRaisesRegex(ValueError, 'four slots'):
                self.simulate(self.project(slot))

    def test_legacy_empty_fifth_slot_is_preserved_but_not_loaded(self):
        from utils import repository as repo
        from utils.database import get_connection
        from models.schemas import ProductLine
        repo.create_user('legacy_four', 'not-a-login-hash', 'team_leader', 'Legacy Four', True)
        legacy = ProductLine.from_dict(dict(team_name='Legacy Four', slot_name='E',
            product_name='Open Product Slot', is_active=False, inventory_units=0, backlog_units=0))
        repo.save_product_lines([legacy])
        decision = ProductDecision.from_dict(dict(team_name='Legacy Four', slot_name='E',
            product_name='Open Product Slot', is_active=False, forecast_units=0,
            planned_production_units=0, target_finished_goods_inventory=0))
        repo.save_product_decisions([decision], round_number=1)
        self.assertEqual([p.slot_name for p in repo.load_product_lines('Legacy Four')], list('ABCD'))
        self.assertEqual(repo.load_product_decisions(1, 'Legacy Four'), [])
        with get_connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM product_lines WHERE team_name='Legacy Four'").fetchone()[0], 5)
            self.assertEqual(conn.execute("SELECT count(*) FROM product_decisions WHERE team_name='Legacy Four'").fetchone()[0], 1)
        # Unexpected real stock must remain visible to the engine's safety check.
        repo.save_product_lines([replace(legacy, inventory_units=5)])
        self.assertEqual(len(repo.load_product_lines('Legacy Four')), 5)
        repo.save_product_lines([legacy])

    def test_split_testing_accumulates_and_costs_less(self):
        project = self.project()
        required = estimate_development_project(project, current_round=3)['required_investment']
        half = replace(project, cumulative_investment=required, investment_this_round=0, testing_intensity=0.5)
        first = estimate_development_project(half, current_round=3)
        progressed = _progress_projects(replace(DEFAULT_MARKET_REPORT, round_number=3), [half])[0].project
        self.assertEqual(progressed.cumulative_testing, 0.5)
        self.assertAlmostEqual(round(progressed.launch_readiness_score, 1), first['projected_readiness_after_this_round'])
        repeated = estimate_development_project(progressed, current_round=4)
        full = estimate_development_project(replace(half, testing_intensity=1), current_round=3)
        self.assertEqual(full['projected_readiness_after_this_round'], repeated['projected_readiness_after_this_round'])
        self.assertEqual(first['testing_cost_this_round'] + repeated['testing_cost_this_round'], 1000)
        self.assertEqual(full['testing_cost_this_round'], 2000)
        self.assertGreater(full['projected_readiness_after_this_round'], first['projected_readiness_after_this_round'])
        print('Gen2, fully funded: testing0.5 =', first['projected_readiness_after_this_round'],
              '; repeated0.5 =', repeated['projected_readiness_after_this_round'],
              '; testing1.0 =', full['projected_readiness_after_this_round'])

    def test_save_and_reload_retains_coverage(self):
        project = replace(self.project(), cumulative_testing=0.5)
        save_product_development_projects([project])
        reloaded = load_product_development_projects('Launch Test')
        self.assertEqual(next(p for p in reloaded if p.project_id == project.project_id).cumulative_testing, 0.5)

    def test_launch_round_cost_is_charged(self):
        output = self.simulate(self.ready_project())
        self.assertEqual(output[0][0].innovation_investment, 22000)
        self.assertTrue(all(p.cumulative_testing == 0 for p in output[4]))

    def test_current_round_development_cannot_launch_until_next_round(self):
        output = self.simulate(self.project())
        self.assertEqual(next(p for p in output[3] if p.slot_name == 'D').product_name, 'Open Product Slot')
        self.assertEqual(output[0][0].innovation_investment, 22000)
        self.assertEqual(output[4][0].cumulative_testing, 1)

    def test_testing_cost_affects_cash_profit_and_total_cost(self):
        base = replace(self.project(), launch_now=False, testing_intensity=0)
        no_test = self.simulate(base)[0][0]
        tested = self.simulate(replace(base, testing_intensity=1))[0][0]
        self.assertAlmostEqual(tested.total_cost - no_test.total_cost, 2000)
        self.assertAlmostEqual(no_test.profit - tested.profit, 2000)
        self.assertAlmostEqual(no_test.ending_cash_balance - tested.ending_cash_balance, 2000)

    def test_cancel_no_charge_no_progress(self):
        output = self.simulate(replace(self.project(), cancel_now=True, cumulative_testing=0.5))
        self.assertEqual(output[0][0].innovation_investment, 0)
        self.assertEqual(output[4][0].cumulative_testing, 0.5)

    def test_coverage_caps_and_intensity_resets(self):
        output = self.simulate(replace(self.project(), launch_now=False, cumulative_testing=0.8))
        self.assertEqual(output[4][0].cumulative_testing, 1)
        self.assertEqual(output[4][0].testing_intensity, 0)
        estimate = estimate_development_project(output[4][0], current_round=4)
        self.assertEqual(estimate['testing_cost_this_round'], 0)

    def test_legacy_project_defaults_to_zero_coverage(self):
        self.assertEqual(ProductDevelopmentProject.from_dict({}).cumulative_testing, 0)

    def test_student_ui_keeps_accumulated_testing_when_saving(self):
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest
        from utils.demand_protocol import save_outlook
        from utils.repository import set_round_submissions_open
        create_user("testing_admin", "not-a-login-hash", "admin", None, True)
        save_outlook(1, 1000, 1400)
        set_round_submissions_open(1, True)
        project = replace(self.project(), cumulative_testing=0.5, cumulative_investment=5000,
                          testing_intensity=0.5, investment_this_round=0, launch_now=False, status="development")
        save_product_development_projects([project])
        with patch("streamlit.page_link"):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "pages" / "2_Team_Decisions.py"), default_timeout=40)
            app.session_state["authenticated_username"] = "launch_test"
            app.run()
            self.assertFalse(app.exception, str(app.exception))
            product_names = [w for w in app.text_input if w.label == 'Product Name']
            self.assertEqual({w.key for w in product_names},
                             {f'stage_b_product_{slot}_product_name' for slot in 'ABCD'})
            tables = [d.value for d in app.dataframe if "Testing Coverage" in d.value.columns]
            self.assertTrue(tables)
            self.assertEqual(tables[0].iloc[0]["Testing Coverage"], "100%")
            self.assertEqual(tables[0].iloc[0]["Testing Cost"], 500)
            next(b for b in app.button if b.label == "Save Portfolio and Pipeline Decision").click().run()
            self.assertFalse(app.exception, str(app.exception))
        saved = next(p for p in load_product_development_projects("Launch Test") if p.project_id == project.project_id)
        self.assertEqual(saved.cumulative_testing, 0.5)


if __name__ == '__main__':
    unittest.main()
