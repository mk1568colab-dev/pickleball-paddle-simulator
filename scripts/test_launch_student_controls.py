"""Student launch regressions; the database is always an isolated temporary file."""
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LAB = tempfile.TemporaryDirectory()
os.environ['SIMULATOR_DB_PATH'] = str(Path(LAB.name) / 'launch.db')
os.environ['SIMULATOR_ENV'] = 'dev'
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'

from streamlit.testing.v1 import AppTest
from data.defaults import DEFAULT_MARKET_REPORT
from data.classroom_start import initial_state
from utils import repository as repo
from utils.demand_protocol import save_outlook
from engine.simulator import run_round

FIELDS = ('selling_price_per_unit', 'forecast_units', 'planned_production_units',
          'qc_budget_per_unit', 'target_finished_goods_inventory')


class StudentLaunchTests(unittest.TestCase):
    def test_two_launches_edit_save_reload_and_compete_in_same_round(self):
        team = 'Launch Lab'
        repo.create_user('lab_admin', 'not-a-login-hash', 'admin', None, True)
        repo.create_user('lab_student', 'not-a-login-hash', 'team_leader', team, True)
        repo.save_team_state(replace(initial_state(team), raw_material_inventory=2000,
                                    capacity_units=600, completed_rounds=[1, 2]))
        projects = [replace(p, project_name=f'New Paddle {slot}', intended_slot_name=slot,
                            target_segment='premium', target_tech_generation=3,
                            cumulative_investment=30000, cumulative_testing=1,
                            status='launch_ready', launch_readiness_score=100,
                            created_round=1, planned_launch_round=3, earliest_launch_round=3,
                            investment_this_round=0, testing_intensity=0, launch_now=False)
                    for p, slot in zip(repo.load_product_development_projects(team), 'CD')]
        repo.save_product_development_projects(projects)
        market = replace(DEFAULT_MARKET_REPORT, round_number=3, total_demand=900)
        repo.save_market_report(market)
        save_outlook(3, 800, 1000)
        repo.set_round_submissions_open(3, True)
        values = {'C': (199.0, 80, 70, 4.0, 15), 'D': (219.0, 90, 85, 5.0, 20)}

        def page():
            app = AppTest.from_file(str(ROOT / 'pages/2_Team_Decisions.py'), default_timeout=45)
            app.session_state['authenticated_username'] = 'lab_student'
            app.run()
            self.assertFalse(app.exception, str(app.exception))
            return app

        def check(app):
            self.assertFalse(app.exception, str(app.exception))
            for slot in 'CD':
                self.assertEqual(app.text_input(key=f'stage_b_product_{slot}_product_name').value,
                                 f'New Paddle {slot}')
                for field, value in zip(FIELDS, values[slot]):
                    widget = app.number_input(key=f'stage_b_product_{slot}_{field}')
                    self.assertFalse(widget.disabled)
                    self.assertEqual(widget.value, value)

        with patch('streamlit.page_link'):
            app = page()
            # The shortcut must work without an explicit rerun losing widget state.
            next(b for b in app.button if b.label == 'Launch New Paddle C in Product C').click().run()
            self.assertTrue(app.checkbox(key='stage_b_project_P1_launch_now').value)
            # The second launch can also be requested in the pipeline.
            app.checkbox(key='stage_b_project_P2_launch_now').check().run()
            for slot in 'CD':
                for field, value in zip(FIELDS, values[slot]):
                    widget = app.number_input(key=f'stage_b_product_{slot}_{field}')
                    self.assertFalse(widget.disabled)
                    widget.set_value(value)
            app.run()
            check(app)
            app.number_input(key='stage_b_raw_material_order_qty').set_value(250).run()
            check(app)
            app.number_input(key='stage_b_overtime_capacity_units').set_value(40).run()
            app.number_input(key='stage_b_capacity_expansion_units').set_value(50).run()
            check(app)
            self.assertTrue(any('Expansion cost this round: \\$3,600.00' in c.value
                                for c in app.caption))
            self.assertTrue(any('Expansion | From Round 4' in m.value for m in app.markdown))
            # Toggling one launch must not erase the other project's price/production.
            app.checkbox(key='stage_b_project_P2_launch_now').uncheck().run()
            self.assertTrue(app.number_input(key='stage_b_product_D_selling_price_per_unit').disabled)
            self.assertEqual(app.number_input(key='stage_b_product_C_selling_price_per_unit').value, 199)
            next(b for b in app.button if b.label == 'Launch New Paddle D in Product D').click().run()
            for field, value in zip(FIELDS, values['D']):
                app.number_input(key=f'stage_b_product_D_{field}').set_value(value)
            app.run()
            check(app)
            next(b for b in app.button if b.label == 'Save Portfolio and Pipeline Decision').click().run()
            confirms = [b for b in app.button if b.key == 'stage_b_submit_warning_confirm']
            if confirms:
                confirms[0].click().run()
            self.assertFalse(app.error, [e.value for e in app.error])
            check(page())

        for slot in 'CD':
            saved = next(p for p in repo.load_product_decisions(3, team) if p.slot_name == slot)
            self.assertEqual(tuple(getattr(saved, f) for f in FIELDS), values[slot])
        output = run_round(market, repo.load_team_decisions(3), repo.load_product_lines(),
                           repo.load_product_decisions(3), repo.load_product_development_projects(),
                           repo.load_team_states())
        for slot in 'CD':
            result = next(p for p in output[1] if p.slot_name == slot)
            self.assertTrue(result.launched_this_round)
            self.assertEqual(result.selling_price_per_unit, values[slot][0])
            self.assertEqual(result.actual_production_units, values[slot][2])
            self.assertGreater(result.sales_units, 0)
            self.assertAlmostEqual(result.revenue, result.sales_units * result.selling_price_per_unit)


if __name__ == '__main__':
    unittest.main()
