"""Local sourcing changes, using only disposable classroom data."""

from dataclasses import replace
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEMP = tempfile.TemporaryDirectory()
os.environ['SIMULATOR_DB_PATH'] = str(Path(TEMP.name) / 'sourcing.db')
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'
os.environ['SIMULATOR_ENV'] = 'dev'

from data.classroom_start import COMMON_PROFILE, COMMON_PROFILE_NAME
from data.defaults import DEFAULT_MARKET_REPORT
from engine.config import SUPPLIER_MATERIAL_COST_MULTIPLIERS, SUPPLY_RISK_INDEX
from engine.simulator import (
    _build_material_order, _compute_supplier_metrics, _normalized_supplier_mix,
    _split_open_material_orders,
)
from engine.sourcing import material_lead_time_rounds, material_order_timing
from models.schemas import OpenMaterialOrder, TeamDecision
from utils import repository as repo
from utils.classrooms import database_scope
from utils.demand_protocol import save_outlook
from utils.submission_fallback import complete_round_inputs


class SourcingTests(unittest.TestCase):
    def firm(self, **values):
        return TeamDecision.from_dict(dict(
            team_name='Sourcing Test', archetype=COMMON_PROFILE_NAME,
            raw_material_order_qty=240, **values))

    def metrics(self, firm, risk='Moderate'):
        return _compute_supplier_metrics(firm, replace(DEFAULT_MARKET_REPORT, supply_risk=risk), COMMON_PROFILE)

    def test_price_indices_and_supplier_aliases(self):
        self.assertEqual(list(SUPPLIER_MATERIAL_COST_MULTIPLIERS.values()), [.8, 1, 1.15])
        standard = self.metrics(self.firm(supplier_choice='Standard')).weighted_material_unit_cost
        for name, multiplier in [('Economy', .8), ('Standard', 1), ('Reliable', 1.15)]:
            self.assertAlmostEqual(self.metrics(self.firm(supplier_choice=name)).weighted_material_unit_cost,
                                   standard * multiplier, delta=.011)
        for old, new in [('Offshore Value', 'Economy'), ('Balanced Source', 'Standard'),
                         ('Premium Reliable', 'Reliable')]:
            self.assertEqual(self.metrics(self.firm(supplier_choice=old)),
                             self.metrics(self.firm(supplier_choice=new)))

    def test_saved_expedite_cannot_change_new_order_timing_or_cost(self):
        firm = self.firm(supplier_mix_offshore_pct=30, supplier_mix_balanced_pct=50,
                         supplier_mix_premium_pct=20)
        for risk in SUPPLY_RISK_INDEX:
            expected = self.metrics(firm, risk)
            for legacy_value in (3, 50, 100):
                actual = self.metrics(replace(firm, expedited_order_share_pct=legacy_value), risk)
                self.assertEqual(expected, actual)

    def test_every_integer_mix_agrees_with_preview_for_all_risk_levels(self):
        for economy in range(101):
            for standard in range(101 - economy):
                firm = self.firm(supplier_mix_offshore_pct=economy,
                                 supplier_mix_balanced_pct=standard,
                                 supplier_mix_premium_pct=100 - economy - standard)
                for risk in SUPPLY_RISK_INDEX:
                    report = replace(DEFAULT_MARKET_REPORT, round_number=3, supply_risk=risk)
                    timing = material_order_timing(_normalized_supplier_mix(firm), risk)
                    order = _build_material_order(report, firm, self.metrics(firm, risk))
                    self.assertEqual(order.arrival_round, 3 + timing['lead_time_rounds'])
                    self.assertEqual(order.weighted_lead_time, timing['adjusted_lead_time'])

    def test_rounding_boundaries_and_reliable_arrivals(self):
        for value, expected in [(1.49, 1), (1.496, 2), (1.5, 2), (1.6, 2), (2.5, 2)]:
            self.assertEqual(material_lead_time_rounds(value), expected)
        firm = self.firm(supplier_choice='Reliable')
        for risk in SUPPLY_RISK_INDEX:
            self.assertEqual(material_order_timing(_normalized_supplier_mix(firm), risk)['lead_time_rounds'], 1)

    def test_existing_order_keeps_recorded_cost_and_arrival(self):
        order = OpenMaterialOrder.from_dict(dict(quantity=240, arrival_round=3,
            placed_round=1, weighted_material_unit_cost=37.12, weighted_lead_time=1.6))
        original = order.to_dict()
        self.assertEqual(_split_open_material_orders(2, [order]), ([], [order]))
        self.assertEqual(_split_open_material_orders(3, [order]), ([order], []))
        self.assertEqual(order.to_dict(), original)

    def test_fallback_clears_expedite_without_rewriting_history(self):
        with database_scope(Path(TEMP.name) / 'fallback.db'):
            repo.create_user('sourcing_user', 'not-a-login-hash', 'team_leader', 'Sourcing Test', True)
            old = self.firm(supplier_choice='Standard', expedited_order_share_pct=100)
            repo.save_team_decision(old, 1)
            firms, *_ = complete_round_inputs(2, [], [], [], repo.load_product_lines(), repo.load_team_states())
            self.assertEqual(firms[0].expedited_order_share_pct, 0)
            self.assertEqual(repo.load_team_decision(1, 'Sourcing Test').expedited_order_share_pct, 100)

    def test_student_controls_save_new_names_and_no_expedite(self):
        from streamlit.testing.v1 import AppTest
        db_path = Path(TEMP.name) / 'student.db'
        with database_scope(db_path), patch.dict(os.environ, {'SIMULATOR_DB_PATH': str(db_path)}):
            repo.create_user('sourcing_admin', 'not-a-login-hash', 'admin', None, True)
            user = repo.create_user('sourcing_student', 'not-a-login-hash', 'team_leader', 'Sourcing Test', True)
            save_outlook(1, 1000, 1400)
            repo.set_round_submissions_open(1, True)
            with patch('streamlit.page_link'):
                app = AppTest.from_file(str(ROOT / 'pages/2_Team_Decisions.py'), default_timeout=45)
                app.session_state['authenticated_username'] = user.username
                app.session_state['stage_b_expedited_order_share_pct'] = 100
                app.run()
                self.assertFalse(app.exception, str(app.exception))
                labels = {w.label for w in app.number_input}
                self.assertTrue({'Economy %', 'Standard %', 'Reliable %'} <= labels)
                self.assertFalse(any('Expedite' in w.label for w in app.slider))
                app.number_input(key='stage_b_supplier_mix_offshore_pct').set_value(0)
                app.number_input(key='stage_b_supplier_mix_balanced_pct').set_value(0)
                app.number_input(key='stage_b_supplier_mix_premium_pct').set_value(100).run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertEqual({m.label: m.value for m in app.metric}['Est. Arrival If Ordered'], 'Round 2')
                next(b for b in app.button if b.label == 'Save Portfolio and Pipeline Decision').click().run()
                self.assertFalse(app.exception, str(app.exception))
                saved = repo.load_team_decision(1, 'Sourcing Test')
                self.assertIsNotNone(saved)
                self.assertEqual(saved.expedited_order_share_pct, 0)
                self.assertEqual(saved.supplier_mix_premium_pct, 100)


if __name__ == '__main__':
    unittest.main()
