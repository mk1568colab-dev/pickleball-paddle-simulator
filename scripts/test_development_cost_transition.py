"""Apply new prices to saved, in-progress projects without touching classroom data."""

import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import test_development_costs as fixtures
from engine.config import (
    NPD_TECH_GENERATION_COST_MULTIPLIERS,
    TESTING_COST_MULTIPLIERS_BY_TECH_GENERATION,
)
from engine.simulator import estimate_development_project, project_ready_at_round_start, run_round
from utils import repository as repo
from utils.classrooms import database_scope
from utils.database import get_database_path
from utils.submission_fallback import complete_round_inputs


class DevelopmentCostTransitionTests(unittest.TestCase):
    project = fixtures.DevelopmentCostTests.project
    inputs = fixtures.DevelopmentCostTests.inputs
    simulate = fixtures.DevelopmentCostTests.simulate

    def setUp(self):
        scope = database_scope(Path(fixtures.TEMP.name) / (self._testMethodName + '.db'))
        scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)
        repo.create_user('cost_test', 'not-a-login-hash', 'team_leader', 'Cost Test', True)

    def legacy_project(self, generation=4, **overrides):
        old_cost = 16875 if generation == 3 else 21875
        project = self.project(generation, required_investment=old_cost,
                               cumulative_investment=old_cost, cumulative_testing=1,
                               status='launch_ready', earliest_launch_round=3)
        with patch.dict(NPD_TECH_GENERATION_COST_MULTIPLIERS, {3: 1.35, 4: 1.75}):
            estimate = estimate_development_project(project, False, 3)
        project.launch_readiness_score = estimate['projected_readiness_after_this_round']
        return replace(project, **overrides)

    def save_and_load(self, project):
        repo.save_product_development_projects([project])
        return next(p for p in repo.load_product_development_projects('Cost Test')
                    if p.project_id == project.project_id)

    def persist_round(self, output):
        repo.save_round_results(output[0])
        repo.save_product_round_results(output[1])
        repo.save_team_states(output[2])
        repo.save_product_lines(output[3])
        repo.save_product_development_projects(output[4])

    def test_existing_projects_reprice_without_mutation_or_automatic_charge(self):
        for generation, new_cost in ((3, 20250), (4, 26250)):
            for progress in (0.25, 1, 1.2):
                with self.subTest(generation=generation, progress=progress):
                    original = self.legacy_project(generation)
                    project = self.save_and_load(replace(original,
                        cumulative_investment=original.required_investment * progress,
                        cumulative_testing=0.5, status='development'))
                    before = project.to_dict()
                    estimate = estimate_development_project(project, False, 3)
                    self.assertEqual(estimate['required_investment'], new_cost)
                    self.assertEqual(project.to_dict(), before)
                    output = self.simulate(project)
                    updated = next(p for p in output[4] if p.project_id == project.project_id)
                    self.assertEqual(updated.required_investment, new_cost)
                    self.assertEqual(updated.cumulative_investment, project.cumulative_investment)
                    self.assertEqual(updated.cumulative_testing, 0.5)
                    self.assertEqual(output[0][0].innovation_investment, 0)
                    reloaded = next(p for p in repo.load_product_development_projects('Cost Test')
                                    if p.project_id == project.project_id)
                    self.assertEqual(reloaded.to_dict(), before)

    def test_saved_launch_request_cannot_bypass_new_funding_gate(self):
        for generation in (3, 4):
            for slot in ('A', 'C'):
                with self.subTest(generation=generation, slot=slot):
                    project = self.save_and_load(self.legacy_project(
                        generation, intended_slot_name=slot, launch_now=True))
                    self.assertFalse(project_ready_at_round_start(project, 3))
                    output = self.simulate(project)
                    originals = {p.slot_name: p for p in repo.load_product_lines('Cost Test')}
                    for line in output[3]:
                        self.assertEqual(line.product_name, originals[line.slot_name].product_name)
                        self.assertEqual(line.is_active, originals[line.slot_name].is_active)
                    self.assertEqual(output[0][0].innovation_investment, 0)
                    self.assertFalse(any(p.launched_this_round for p in output[1]))
                    self.assertEqual(output[4][0].cumulative_testing, 1)

    def test_top_up_then_launch_next_round(self):
        for generation, extra in ((3, 3375), (4, 4375)):
            with self.subTest(generation=generation):
                project = self.legacy_project(generation, investment_this_round=extra, launch_now=True)
                market, firm, lines, products, state = self.inputs(project)
                output = run_round(market, [firm], lines, products, [project], [state])
                self.assertEqual(output[0][0].innovation_investment, extra)
                self.assertFalse(any(p.launched_this_round for p in output[1]))
                ready = next(p for p in output[4] if p.project_id == project.project_id)
                ready = self.save_and_load(ready)
                self.assertTrue(project_ready_at_round_start(ready, 4))
                self.assertEqual(ready.investment_this_round, 0)
                self.assertEqual(ready.cumulative_testing, 1)
                launch_products = [replace(p, product_name=project.project_name, is_active=True,
                    selling_price_per_unit=189, forecast_units=40, planned_production_units=40)
                    if p.slot_name == 'C' else p for p in products]
                launched = run_round(replace(market, round_number=4), [firm], output[3],
                    launch_products, [replace(ready, launch_now=True)], output[2])
                line = next(p for p in launched[3] if p.slot_name == 'C')
                result = next(p for p in launched[1] if p.slot_name == 'C')
                self.assertTrue(line.is_active and result.launched_this_round)
                self.assertEqual(line.tech_generation, generation)
                self.assertEqual(result.selling_price_per_unit, 189)
                self.assertEqual(result.planned_production_units, 40)
                self.assertEqual(launched[0][0].innovation_investment, 0)

    def test_pending_testing_uses_new_price_once_and_preserves_coverage(self):
        project = self.save_and_load(self.legacy_project(cumulative_testing=0.6, testing_intensity=0.4))
        output = self.simulate(project)
        self.assertEqual(output[0][0].innovation_investment, 384)
        updated = self.save_and_load(output[4][0])
        self.assertEqual(updated.cumulative_testing, 1)
        self.assertEqual(updated.cumulative_investment, 21875)
        self.assertEqual(updated.testing_intensity, 0)
        self.assertEqual(self.simulate(updated)[0][0].innovation_investment, 0)

    def test_missing_submission_does_not_fund_or_test_automatically(self):
        project = self.save_and_load(self.legacy_project(
            investment_this_round=4375, testing_intensity=1, launch_now=True))
        market, firm, lines, products, state = self.inputs(project)
        firms, products, projects, lines, missing = complete_round_inputs(
            3, [], [], [project], lines, [state])
        self.assertEqual(missing, ['Cost Test'])
        output = run_round(market, firms, lines, products, projects, [state])
        self.assertEqual(output[0][0].innovation_investment, 0)
        self.assertEqual(output[4][0].cumulative_investment, 21875)
        self.assertEqual(output[4][0].cumulative_testing, 1)
        self.assertFalse(any(p.launched_this_round for p in output[1]))

    def test_completed_round_finances_and_accounts_are_unchanged(self):
        project = self.project(investment_this_round=21875, testing_intensity=1)
        market, firm, lines, products, state = self.inputs(project)
        with patch.dict(NPD_TECH_GENERATION_COST_MULTIPLIERS, {3: 1.35, 4: 1.75}), \
             patch.dict(TESTING_COST_MULTIPLIERS_BY_TECH_GENERATION, {4: 1.0}):
            old = run_round(replace(market, round_number=2), [firm], lines, products, [project], [state])
        self.assertEqual(old[0][0].innovation_investment, 23875)
        self.persist_round(old)
        history = [r.to_dict() for r in repo.load_round_results(2)]
        product_history = [r.to_dict() for r in repo.load_product_round_results(2)]
        users = [u.to_dict() for u in repo.load_users()]
        projects = repo.load_product_development_projects('Cost Test')
        next_output = run_round(market, [firm], repo.load_product_lines('Cost Test'), products,
                                projects, repo.load_team_states())
        self.persist_round(next_output)
        self.assertEqual(next_output[0][0].innovation_investment, 0)
        self.assertEqual(history, [r.to_dict() for r in repo.load_round_results(2)])
        self.assertEqual(product_history, [r.to_dict() for r in repo.load_product_round_results(2)])
        self.assertEqual(users, [u.to_dict() for u in repo.load_users()])

    def test_launched_project_record_keeps_original_requirement(self):
        project = self.save_and_load(self.legacy_project(status='launched', launched_round=2))
        before = project.to_dict()
        from engine.simulator import _progress_projects
        updated = _progress_projects(replace(fixtures.DEFAULT_MARKET_REPORT, round_number=3), [project])[0]
        self.assertEqual(updated.project.to_dict(), before)
        self.assertEqual(updated.required_investment, 21875)
        self.assertFalse(project_ready_at_round_start(project, 3))

    def test_student_screen_explains_changed_requirement_without_overwriting_state(self):
        from streamlit.testing.v1 import AppTest
        from utils.demand_protocol import save_outlook
        repo.create_user('cost_admin', 'not-a-login-hash', 'admin', None, True)
        repo.save_market_report(replace(fixtures.DEFAULT_MARKET_REPORT, round_number=3))
        save_outlook(3, 1000, 1400)
        repo.set_round_submissions_open(3, True)
        project = self.save_and_load(self.legacy_project())
        with patch.dict(os.environ, {'SIMULATOR_DB_PATH': str(get_database_path())}), patch('streamlit.page_link'):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'pages' / '2_Team_Decisions.py'), default_timeout=40)
            app.session_state['authenticated_username'] = 'cost_test'
            app.run()
            self.assertFalse(app.exception, str(app.exception))
            notices = ' '.join(e.value for e in app.info)
            self.assertIn('Development requirement updated: $21,875 to $26,250', notices)
            self.assertIn('$4,375', notices)
            headers = [e.value for e in app.markdown if 'kiki-row-header' in e.value and 'Project P1' in e.value]
            self.assertIn('Funding Needed', headers[0])
            self.assertNotIn('Launch Ready', headers[0])
        reloaded = next(p for p in repo.load_product_development_projects('Cost Test')
                        if p.project_id == project.project_id)
        self.assertEqual(reloaded.to_dict(), project.to_dict())


if __name__ == '__main__':
    unittest.main()
