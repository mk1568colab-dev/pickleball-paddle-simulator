"""Development-price regression checks against an isolated classroom database."""

import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEMP = tempfile.TemporaryDirectory()
os.environ['SIMULATOR_DB_PATH'] = str(Path(TEMP.name) / 'development_costs.db')
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'

from data.classroom_start import COMMON_PROFILE_NAME, initial_state
from data.defaults import DEFAULT_MARKET_REPORT
from engine.simulator import (
    _progress_projects,
    estimate_development_project,
    preview_team_decision,
    project_ready_at_round_start,
    run_round,
)
from models.schemas import ProductDecision, ProductDevelopmentProject, TeamDecision
from utils import repository as repo


class DevelopmentCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo.create_user('cost_test', 'not-a-login-hash', 'team_leader', 'Cost Test', True)

    def project(self, generation=4, **overrides):
        values = dict(team_name='Cost Test', project_name='Cost Check',
                      target_segment='premium', target_tech_generation=generation,
                      intended_slot_name='C', created_round=1, planned_launch_round=3,
                      investment_this_round=0, testing_intensity=0, status='development')
        values.update(overrides)
        return ProductDevelopmentProject.from_dict(values)

    def inputs(self, project):
        lines = repo.load_product_lines('Cost Test')
        products = [ProductDecision.from_dict(dict(
            team_name='Cost Test', slot_name=p.slot_name, product_name=p.product_name,
            is_active=p.is_active, target_segment=p.target_segment,
            selling_price_per_unit=189, forecast_units=40,
            planned_production_units=40 if p.is_active else 0, qc_budget_per_unit=3,
        )) for p in lines]
        firm = TeamDecision.from_dict(dict(
            team_name='Cost Test', archetype=COMMON_PROFILE_NAME,
            supplier_mix_offshore_pct=30, supplier_mix_balanced_pct=50,
            supplier_mix_premium_pct=20, raw_material_order_qty=0,
        ))
        state = replace(initial_state('Cost Test'), cash_balance=100000)
        return replace(DEFAULT_MARKET_REPORT, round_number=3), firm, lines, products, state

    def simulate(self, project):
        market, firm, lines, products, state = self.inputs(project)
        return run_round(market, [firm], lines, products, [project], [state])

    def test_development_prices_by_generation_and_segment(self):
        expected = {
            1: (6800, 8000, 10000),
            2: (8500, 10000, 12500),
            3: (13770, 16200, 20250),
            4: (17850, 21000, 26250),
        }
        for generation, costs in expected.items():
            for segment, cost in zip(('beginner', 'mid', 'premium'), costs):
                with self.subTest(generation=generation, segment=segment):
                    estimate = estimate_development_project(self.project(generation, target_segment=segment))
                    self.assertEqual(estimate['required_investment'], cost)

    def test_higher_design_ambition_still_scales_development_cost(self):
        estimate = estimate_development_project(self.project(
            projected_demand_fit_modifier=1.2, projected_base_defect_modifier=-0.01,
        ))
        self.assertEqual(estimate['required_investment'], round(26250 * 1.06 * 1.12, 2))

    def test_only_gen4_testing_cost_increases(self):
        for generation in range(1, 5):
            for intensity in (0, 0.4, 0.5, 0.85, 1):
                with self.subTest(generation=generation, intensity=intensity):
                    estimate = estimate_development_project(self.project(generation, testing_intensity=intensity))
                    base = 2400 if generation == 4 else 2000
                    self.assertEqual(estimate['testing_cost_this_round'], round(base * intensity ** 2, 2))

    def test_testing_splits_keep_same_coverage_and_readiness(self):
        half = self.project(cumulative_investment=26250, testing_intensity=0.5)
        market = replace(DEFAULT_MARKET_REPORT, round_number=1)
        progressed = _progress_projects(market, [half])[0].project
        self.assertEqual(progressed.cumulative_testing, 0.5)
        split = estimate_development_project(progressed, current_round=2)
        full = estimate_development_project(replace(half, testing_intensity=1), current_round=2)
        self.assertEqual(split['cumulative_testing_after_this_round'], 1)
        self.assertEqual(split['projected_readiness_after_this_round'], full['projected_readiness_after_this_round'])
        self.assertEqual(split['testing_cost_this_round'], 600)
        self.assertEqual(full['testing_cost_this_round'], 2400)

    def test_readiness_and_timing_at_full_funding_are_unchanged(self):
        for generation, required, testing, earliest in [(3, 20250, .7, 2), (4, 26250, .85, 3)]:
            with self.subTest(generation=generation):
                project = self.project(generation, cumulative_investment=required,
                                       cumulative_testing=testing, planned_launch_round=2)
                self.assertFalse(project_ready_at_round_start(project, earliest - 1))
                self.assertTrue(project_ready_at_round_start(project, earliest))
                self.assertEqual(estimate_development_project(project, False)['readiness_threshold'], 84)

    def test_testing_does_not_count_as_development_funding(self):
        project = self.project(cumulative_investment=25000, testing_intensity=1)
        estimate = estimate_development_project(project, current_round=3)
        self.assertEqual(estimate['remaining_investment_after_this_round'], 1250)
        self.assertFalse(estimate['funding_gate_met'])
        progressed = _progress_projects(replace(DEFAULT_MARKET_REPORT, round_number=3), [project])[0].project
        self.assertEqual(progressed.cumulative_investment, 25000)

    def test_gen4_testing_cost_reaches_actual_cash_profit_and_total_cost(self):
        base = self.project(investment_this_round=1000)
        without = self.simulate(base)[0][0]
        with_testing = self.simulate(replace(base, testing_intensity=1))[0][0]
        self.assertEqual(with_testing.innovation_investment, 3400)
        self.assertAlmostEqual(with_testing.total_cost - without.total_cost, 2400)
        self.assertAlmostEqual(without.profit - with_testing.profit, 2400)
        self.assertAlmostEqual(without.ending_cash_balance - with_testing.ending_cash_balance, 2400)

    def test_preview_and_actual_use_same_testing_cost(self):
        project = self.project(testing_intensity=.5, investment_this_round=1000)
        market, firm, lines, products, state = self.inputs(project)
        preview = preview_team_decision(
            market_report=market, candidate_team_decision=firm,
            candidate_product_decisions=products, candidate_projects=[project],
            product_lines=lines, current_round_team_decisions=[],
            current_round_product_decisions=[], current_round_projects=[], existing_states=[state],
        )
        self.assertEqual(self.simulate(project)[0][0].innovation_investment, 1600)
        self.assertEqual(preview.projected_innovation_investment, 1600)

    def test_canceled_or_launched_project_has_no_new_testing_charge(self):
        for status, cancel in [('development', True), ('launched', False)]:
            with self.subTest(status=status):
                project = self.project(status=status, cancel_now=cancel, testing_intensity=1)
                self.assertEqual(estimate_development_project(project)['testing_cost_this_round'], 0)
                self.assertEqual(self.simulate(project)[0][0].innovation_investment, 0)

    def test_canceled_project_without_new_effort_has_no_charge(self):
        project = self.project(status='canceled', testing_intensity=0)
        self.assertEqual(estimate_development_project(project)['testing_cost_this_round'], 0)
        self.assertEqual(self.simulate(project)[0][0].innovation_investment, 0)

    def test_student_preview_shows_gen4_price_and_updated_explanation(self):
        from streamlit.testing.v1 import AppTest
        from utils.demand_protocol import save_outlook
        repo.create_user('cost_admin', 'not-a-login-hash', 'admin', None, True)
        save_outlook(1, 1000, 1400)
        repo.set_round_submissions_open(1, True)
        repo.save_product_development_projects([self.project(testing_intensity=.5)])
        with patch('streamlit.page_link'):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'pages' / '2_Team_Decisions.py'), default_timeout=40)
            app.session_state['authenticated_username'] = 'cost_test'
            app.run()
            self.assertFalse(app.exception, str(app.exception))
            tables = [d.value for d in app.dataframe if 'Testing Cost' in d.value.columns]
            self.assertEqual(tables[0].iloc[0]['Testing Cost'], 600)
            text = ' '.join(c.value for c in app.caption)
            self.assertIn(r'For Gen 4, the same choices cost \$600 each or \$2,400 in one round.', text)


if __name__ == '__main__':
    unittest.main()
