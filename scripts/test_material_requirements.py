"""Isolated shared-material engine, authorization, migration and UI checks."""

import os
from pathlib import Path
import random
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEMP = tempfile.TemporaryDirectory()
os.environ['SIMULATOR_DB_PATH'] = str(Path(TEMP.name) / 'unused-base.db')
os.environ['SIMULATOR_ENV'] = 'dev'
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'

from data.classroom_start import COMMON_PROFILE_NAME, initial_state
from data.defaults import DEFAULT_MARKET_REPORT
from engine.materials import allocate_materials
from engine.simulator import run_round, preview_team_decision
from models.schemas import ProductDecision, TeamDecision, OpenMaterialOrder, ProductDevelopmentProject
from utils import repository as repo
from utils.classrooms import database_scope
from utils.database import get_connection, get_database_path
from utils.demand_protocol import save_outlook
from utils.material_rules import load_material_requirements, save_material_requirements


class MaterialsTests(unittest.TestCase):
    def setUp(self):
        self.scope = database_scope(Path(TEMP.name) / (self.id().split('.')[-1] + '.db'))
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)
        self.admin = repo.create_user('mat_admin', 'test-only-hash', 'admin', None, True)
        self.student = repo.create_user('mat_student', 'test-only-hash', 'team_leader', 'Materials Team', True)
        self.lines = repo.load_product_lines('Materials Team')
        self.firm = TeamDecision.from_dict(dict(team_name='Materials Team', archetype=COMMON_PROFILE_NAME,
            raw_material_order_qty=240, supplier_mix_offshore_pct=30,
            supplier_mix_balanced_pct=50, supplier_mix_premium_pct=20))
        self.decisions = [ProductDecision.from_dict(dict(
            team_name='Materials Team', slot_name=p.slot_name, product_name=p.product_name,
            is_active=p.is_active, target_segment=p.target_segment, selling_price_per_unit=189,
            planned_production_units={'A': 130, 'B': 110}.get(p.slot_name, 0),
            forecast_units=100, qc_budget_per_unit=3)) for p in self.lines]

    def save(self, round_number, values, user=None):
        with patch('utils.auth.get_current_user', return_value=user or self.admin):
            save_material_requirements(round_number, values)

    def simulate(self, state=None, decisions=None, projects=None, round_number=1, lines=None):
        return run_round(replace(DEFAULT_MARKET_REPORT, round_number=round_number), [self.firm],
                         lines or self.lines, decisions or self.decisions, projects or [],
                         [state or initial_state('Materials Team')])

    def test_default_required_consumption_and_cash(self):
        results, products, states, *_ = self.simulate()
        self.assertEqual(results[0].raw_material_units_consumed, 233)
        self.assertEqual(results[0].actual_production_units, 240)
        self.assertEqual(states[0].raw_material_inventory, 67)
        self.assertAlmostEqual(results[0].procurement_cost, 7332.0)
        preview = preview_team_decision(DEFAULT_MARKET_REPORT, self.firm, self.decisions, [],
                                        self.lines, [], [], [], [initial_state('Materials Team')])
        self.assertEqual(preview.total_material_required, 233)
        self.assertAlmostEqual(sum(r['Planned Material Value'] for r in preview.material_rows), 7118.15)
        self.assertEqual({r['Slot'] for r in preview.material_rows}, {'A', 'B'})
        self.assertEqual(preview.projected_max_feasible_production, 240)

    def test_fractional_inventory_and_results_round_trip(self):
        decisions = [replace(d, planned_production_units=1 if d.is_active else 0) for d in self.decisions]
        out = self.simulate(decisions=decisions)
        self.assertEqual(out[0][0].raw_material_units_consumed, 1.9)
        self.assertEqual(out[2][0].raw_material_inventory, 298.1)
        repo.save_team_states(out[2]); repo.save_round_results(out[0])
        self.assertEqual(repo.load_team_states('Materials Team')[0].raw_material_inventory, 298.1)
        self.assertEqual(repo.load_round_results(1)[0].raw_material_units_consumed, 1.9)
        state = replace(out[2][0], open_material_orders=[])
        next_out = self.simulate(state=state, decisions=decisions, round_number=2, lines=out[3])
        self.assertEqual(next_out[2][0].raw_material_inventory, 296.2)

    def test_shortage_arrivals_and_capacity(self):
        state = replace(initial_state('Materials Team'), raw_material_inventory=60, completed_rounds=[1])
        out = self.simulate(state=state, round_number=2)
        self.assertLessEqual(out[0][0].raw_material_units_consumed, 60)
        self.assertGreater(out[0][0].actual_production_units, 60)
        self.assertGreaterEqual(out[2][0].raw_material_inventory, 0)
        state = replace(state, open_material_orders=[OpenMaterialOrder.from_dict(dict(quantity=240, arrival_round=2))])
        out = self.simulate(state=state, round_number=2)
        self.assertEqual(out[0][0].actual_production_units, 240)
        self.assertEqual(out[2][0].raw_material_inventory, 67)
        large = [replace(d, planned_production_units=300 if d.is_active else 0) for d in self.decisions]
        out = self.simulate(state=replace(state, raw_material_inventory=1000), decisions=large, round_number=2)
        self.assertEqual(out[0][0].actual_production_units, 300)

    def test_target_changes_do_not_change_material_design(self):
        decisions = [replace(d, target_segment='beginner') for d in self.decisions]
        changed = [replace(p, target_segment='beginner') for p in self.lines]
        repo.save_product_lines(changed)
        self.assertEqual(repo.load_product_lines('Materials Team')[0].material_design, 'premium')
        out = self.simulate(decisions=decisions, lines=changed)
        self.assertEqual(out[0][0].raw_material_units_consumed, 233)
        self.assertEqual(out[3][0].material_design, 'premium')

    def test_authorization_validation_and_round_lock(self):
        rates = {'beginner': .8, 'mid': 1, 'premium': 1.4}
        with self.assertRaises(PermissionError):
            self.save(1, rates, self.student)
        with patch('utils.auth.get_current_user', return_value=None), self.assertRaises(PermissionError):
            save_material_requirements(1, rates)
        for value in (0, -1, float('nan'), float('inf'), 10.01, .001, None, 'not-a-number'):
            with self.assertRaises(ValueError):
                self.save(1, dict(rates, beginner=value))
        self.save(1, rates)
        self.assertEqual(load_material_requirements(1), rates)
        save_outlook(1, 1000, 1400); repo.set_round_submissions_open(1, True)
        repo.set_round_submissions_open(1, False)
        with self.assertRaises(ValueError): self.save(1, dict(rates, beginner=.7))
        repo.advance_market_report_to_next_round()
        self.assertEqual(load_material_requirements(2), rates)
        self.save(2, dict(rates, premium=1.2))
        self.assertEqual(load_material_requirements(1), rates)
        self.assertEqual(load_material_requirements(2)['premium'], 1.2)

    def test_existing_game_is_not_rebalanced_on_upgrade(self):
        saved_state = replace(initial_state('Materials Team'), cash_balance=12345.67,
                              raw_material_inventory=53.5, completed_rounds=[1, 2])
        repo.save_team_states([saved_state])
        repo.save_team_decision(self.firm, round_number=3)
        before_lines = [p.to_dict() for p in repo.load_product_lines('Materials Team')]
        with get_connection() as db:
            db.execute('DROP TABLE material_rules')
        before_users = [u.to_dict() for u in repo.load_users()]
        self.assertEqual(load_material_requirements(1), {'beginner':1, 'mid':1, 'premium':1})
        self.assertEqual([u.to_dict() for u in repo.load_users()], before_users)
        self.assertEqual(repo.load_team_states('Materials Team')[0].to_dict(), saved_state.to_dict())
        self.assertEqual([p.to_dict() for p in repo.load_product_lines('Materials Team')], before_lines)
        self.assertEqual(repo.load_team_decision(3, 'Materials Team').to_dict(), self.firm.to_dict())
        self.assertEqual(self.simulate()[0][0].raw_material_units_consumed, 240)

    def test_classroom_isolation(self):
        self.save(1, {'beginner': .8, 'mid':1, 'premium':1.4})
        with database_scope(Path(TEMP.name) / 'other_classroom.db'):
            self.assertEqual(load_material_requirements(1), {'beginner':.7, 'mid':1, 'premium':1.2})
            with patch('utils.auth.get_current_user', return_value=self.admin), self.assertRaises(PermissionError):
                save_material_requirements(1, {'beginner': .8, 'mid':1, 'premium':1.4})
        self.assertEqual(load_material_requirements(1)['premium'], 1.4)

    def test_retire_then_launch_uses_new_design(self):
        retired = self.simulate(decisions=[replace(d, retire_flag=True) if d.slot_name=='A' else d for d in self.decisions])
        repo.save_product_lines(retired[3])
        project = ProductDevelopmentProject.from_dict(dict(team_name='Materials Team', project_slot_name='P1',
            project_name='New Mid', intended_slot_name='A', target_segment='mid', target_tech_generation=2,
            created_round=1, planned_launch_round=3, cumulative_investment=100000,
            launch_readiness_score=100, cumulative_testing=1, investment_this_round=0,
            testing_intensity=0, status='launch_ready', launch_now=True))
        decisions = [replace(d, product_name='New Mid', target_segment='mid', is_active=True,
                             planned_production_units=100, retire_flag=False) if d.slot_name=='A'
                     else replace(d, planned_production_units=0) for d in self.decisions]
        out = self.simulate(state=replace(retired[2][0], raw_material_inventory=300),
                            decisions=decisions, projects=[project], round_number=3, lines=retired[3])
        self.assertEqual(out[3][0].material_design, 'mid')
        self.assertEqual(out[0][0].raw_material_units_consumed, 100)
        repo.save_product_lines(out[3])
        self.assertEqual(repo.load_product_lines('Materials Team')[0].material_design, 'mid')

    def test_randomized_allocator_conserves_resources(self):
        rng = random.Random(7)
        for _ in range(500):
            requests = {s: rng.randrange(400) for s in 'ABCD'}
            rates = {s: rng.randrange(1,1001)/100 for s in requests}
            capacity, stock = rng.randrange(600), rng.randrange(40000)/100
            actual, used = allocate_materials(requests, rates, capacity, stock)
            self.assertLessEqual(sum(actual.values()), capacity)
            self.assertLessEqual(used, stock + 1e-8)
            self.assertAlmostEqual(used, sum(actual[s]*rates[s] for s in actual))
            self.assertTrue(all(0 <= actual[s] <= requests[s] for s in actual))
            self.assertEqual((actual, used), allocate_materials(requests, rates, capacity, stock))

    def test_admin_and_student_pages(self):
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ, {'SIMULATOR_DB_PATH': str(get_database_path())}), patch('streamlit.page_link'):
            admin = AppTest.from_file(str(ROOT / 'pages/3_Instructor_Panel.py'), default_timeout=45)
            admin.session_state['authenticated_username'] = 'mat_admin'
            admin.run()
            self.assertFalse(admin.exception, str(admin.exception))
            next(w for w in admin.number_input if w.label == 'Beginner RM / Paddle').set_value(.8)
            next(w for w in admin.button if w.label == 'Save Material Requirements').click().run()
            self.assertFalse(admin.exception, str(admin.exception))
            self.assertEqual(load_material_requirements(1)['beginner'], .8)
            student = AppTest.from_file(str(ROOT / 'pages/2_Team_Decisions.py'), default_timeout=45)
            student.session_state['authenticated_username'] = 'mat_student'
            student.run()
            self.assertFalse(student.exception, str(student.exception))
            self.assertFalse(any('RM / Paddle' in w.label for w in student.number_input))
            student.number_input(key='stage_b_product_A_planned_production_units').set_value(200).run()
            self.assertFalse(student.exception, str(student.exception))
            metrics = {m.label:m.value for m in student.metric}
            self.assertEqual(metrics['Required RM'], '328.00')
            self.assertEqual(metrics['Planned Material Value'], '$10,020.40')
            student.selectbox(key='stage_b_product_A_target_segment').select('beginner').run()
            self.assertEqual({m.label:m.value for m in student.metric}['Required RM'], '328.00')
            save_outlook(1, 1000, 1400); repo.set_round_submissions_open(1, True)
            admin.run()
            self.assertTrue(next(w for w in admin.button if w.label == 'Save Material Requirements').disabled)
            self.assertTrue(all(w.disabled for w in admin.number_input if 'RM / Paddle' in w.label))
            forbidden = AppTest.from_file(str(ROOT / 'pages/3_Instructor_Panel.py'), default_timeout=45)
            forbidden.session_state['authenticated_username'] = 'mat_student'
            forbidden.run()
            self.assertFalse(any(w.label == 'Save Material Requirements' for w in forbidden.button))


if __name__ == '__main__':
    unittest.main()
