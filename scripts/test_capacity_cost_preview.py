"""Capacity expansion display and settlement checks using disposable data."""
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import test_development_costs as fixtures
from engine.config import CAPACITY_EXPANSION_CAPEX_PER_UNIT
from engine.simulator import preview_team_decision, run_round
from utils import repository as repo
from utils.demand_protocol import save_outlook


class CapacityCostPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo.create_user('capacity_admin', 'test-only-hash', 'admin', None, True)
        repo.create_user('cost_test', 'test-only-hash', 'team_leader', 'Cost Test', True)
        repo.save_market_report(replace(fixtures.DEFAULT_MARKET_REPORT, round_number=3))
        save_outlook(3, 1000, 1400)
        repo.set_round_submissions_open(3, True)

    def app(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'pages/2_Team_Decisions.py'), default_timeout=45)
        app.session_state['authenticated_username'] = 'cost_test'
        return app

    def caption(self, app):
        return next(item.value for item in app.caption if 'Expansion cost this round:' in item.value)

    def test_preview_updates_without_saving_or_changing_capacity(self):
        original_state = [s.to_dict() for s in repo.load_team_states()]
        original_decision = repo.load_team_decision(3, 'Cost Test')
        with patch('streamlit.page_link'):
            app = self.app().run()
            self.assertFalse(app.exception, str(app.exception))
            for units in (0, 10, 50, 100, 0):
                with self.subTest(units=units):
                    app.number_input(key='stage_b_capacity_expansion_units').set_value(units).run()
                    self.assertFalse(app.exception, str(app.exception))
                    text = self.caption(app)
                    self.assertIn(f'\\${units * CAPACITY_EXPANSION_CAPEX_PER_UNIT:,.2f}', text)
                    self.assertIn(f'{units} units x \\$72.00/unit', text)
                    self.assertIn('No extra capacity this round.', text)
                    self.assertTrue(any('Expansion | From Round 4' in item.value for item in app.markdown))
                    self.assertTrue(any(f'300 to {300 + units:,}' in item.value for item in app.markdown))
        self.assertEqual(repo.load_team_decision(3, 'Cost Test'), original_decision)
        self.assertEqual([s.to_dict() for s in repo.load_team_states()], original_state)

    def test_expansion_display_matches_actual_charge_and_next_round_capacity(self):
        helper = fixtures.DevelopmentCostTests()
        market, firm, lines, products, state = helper.inputs(helper.project())
        baseline = run_round(market, [firm], lines, products, [], [state])
        for units in (0, 10, 50, 100):
            with self.subTest(units=units):
                output = run_round(market, [replace(firm, capacity_expansion_units=units)],
                                   lines, products, [], [state])
                expected = units * CAPACITY_EXPANSION_CAPEX_PER_UNIT
                self.assertEqual(output[0][0].expansion_cost, expected)
                self.assertAlmostEqual(baseline[0][0].ending_cash_balance - output[0][0].ending_cash_balance, expected)
                self.assertEqual(output[0][0].effective_capacity_units, baseline[0][0].effective_capacity_units)
                self.assertEqual(output[2][0].capacity_units, state.capacity_units + units)

    def test_overtime_is_not_treated_as_permanent_expansion(self):
        helper = fixtures.DevelopmentCostTests()
        market, firm, lines, products, state = helper.inputs(helper.project())
        output = run_round(market, [replace(firm, overtime_capacity_units=40, capacity_expansion_units=50)],
                           lines, products, [], [state])
        self.assertEqual(output[0][0].effective_capacity_units, state.capacity_units + 40)
        self.assertEqual(output[2][0].capacity_units, state.capacity_units + 50)
        self.assertEqual(output[0][0].expansion_cost, 3600)

    def test_display_uses_the_shared_configured_unit_price(self):
        with patch('streamlit.page_link'), patch('engine.config.CAPACITY_EXPANSION_CAPEX_PER_UNIT', 80), \
             patch('engine.simulator.CAPACITY_EXPANSION_CAPEX_PER_UNIT', 80):
            app = self.app().run()
            app.number_input(key='stage_b_capacity_expansion_units').set_value(50).run()
            self.assertFalse(app.exception, str(app.exception))
            text = self.caption(app)
            self.assertIn(r'\$4,000.00', text)
            self.assertIn(r'\$80.00/unit', text)

    def test_overtime_display_updates_with_current_plan(self):
        with patch('streamlit.page_link'):
            app = self.app().run()
            app.number_input(key='stage_b_overtime_capacity_units').set_value(40).run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertTrue(any('300 to 340' in item.value for item in app.markdown))
            self.assertTrue(any('Round 3 only' in item.value for item in app.markdown))
            self.assertTrue(any('Feasible production:' in item.value for item in app.caption))
            self.assertTrue(any('No permanent capacity added.' in item.value for item in app.caption))
            app.number_input(key='stage_b_overtime_capacity_units').set_value(0).run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertTrue(any(r'Estimated overtime premium: \$0.00' in item.value for item in app.caption))

    def test_preview_matches_engine_across_production_and_material_constraints(self):
        helper = fixtures.DevelopmentCostTests()
        market, firm, lines, products, state = helper.inputs(helper.project())
        for overtime in (0, 40, 400):
            for planned_each in (0, 40, 200):
                for materials in (0, 70, 1000):
                    with self.subTest(overtime=overtime, planned=planned_each, materials=materials):
                        candidate = replace(firm, overtime_capacity_units=overtime, capacity_expansion_units=50)
                        decisions = [replace(p, planned_production_units=planned_each if p.is_active else 0)
                                     for p in products]
                        starting = replace(state, raw_material_inventory=materials, open_material_orders=[],
                                           completed_rounds=[1, 2])
                        preview = preview_team_decision(market, candidate, decisions, [], lines, [], [], [], [starting])
                        output = run_round(market, [candidate], lines, decisions, [], [starting])
                        actual = output[0][0]
                        actual_units = {p.slot_name: p.actual_production_units for p in output[1]}
                        # Hold output fixed to isolate the overtime rate premium from volume costs.
                        same_output = [replace(p, planned_production_units=actual_units[p.slot_name])
                                       for p in decisions]
                        baseline = run_round(
                            market, [replace(candidate, overtime_capacity_units=0)], lines, same_output, [],
                            [replace(starting, capacity_units=max(starting.capacity_units, sum(actual_units.values())))],
                        )[0][0]
                        self.assertEqual(preview.projected_max_feasible_production, sum(actual_units.values()))
                        self.assertEqual(preview.projected_expansion_cost, actual.expansion_cost)
                        self.assertAlmostEqual(preview.projected_overtime_premium,
                                               actual.production_cost - baseline.production_cost, places=2)
                        if overtime == 0 or planned_each == 0 or materials == 0:
                            self.assertEqual(preview.projected_overtime_premium, 0)

    def test_overtime_premium_below_installed_capacity_is_not_hidden(self):
        helper = fixtures.DevelopmentCostTests()
        market, firm, lines, products, state = helper.inputs(helper.project())
        preview = preview_team_decision(market, replace(firm, overtime_capacity_units=40),
                                        products, [], lines, [], [], [], [state])
        self.assertLess(preview.projected_max_feasible_production, state.capacity_units)
        self.assertGreater(preview.projected_overtime_premium, 0)


if __name__ == '__main__':
    unittest.main()
