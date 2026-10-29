"""Shipping, cash, persistence and student UI checks in disposable databases."""

from collections import Counter
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
DB = Path(TEMP.name) / 'shipping.db'
os.environ['SIMULATOR_DB_PATH'] = str(DB)
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'
os.environ['SIMULATOR_ENV'] = 'dev'

from data.classroom_start import COMMON_PROFILE
from engine.sourcing import (DELAY_PROBABILITIES, DISPLAY_NAMES, public_incoming_orders,
                             sourcing_quote, supplier_delay, supplier_quantities)
from engine.simulator import (_build_material_orders, _compute_supplier_metrics,
                              _normalized_supplier_mix, _split_open_material_orders, run_round)
from models.schemas import OpenMaterialOrder
from scripts.export_demo_data import seed_export_demo
from utils.sourcing_rules import DeliveryPolicy, initialize_delivery_policy, load_delivery_policy
from utils import repository as repo
from utils.classrooms import database_scope
from utils.demand_protocol import save_outlook


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes = seed_export_demo(DB, configure_classroom=initialize_delivery_policy)
        cls.policy = load_delivery_policy()
        cls.report = replace(repo.load_market_report(), round_number=1, supply_risk='Moderate', material_cost_index=1)
        cls.firm = repo.load_team_decision(1, 'Demo 022 Team 1')
        cls.lines = repo.load_product_lines(cls.firm.team_name)
        cls.decisions = repo.load_product_decisions(1, cls.firm.team_name)

    def quote(self, qty=240, mix=None, risk='Moderate'):
        return sourcing_quote(qty, mix or _normalized_supplier_mix(self.firm), risk,
                              1, 70, 1, self.policy)

    def test_prices_and_fee_basis(self):
        rows = self.quote()
        self.assertEqual([r['unit_cost'] for r in rows], [25.2, 31.5, 36.22])
        self.assertEqual([r['quantity'] for r in rows], [72, 120, 48])
        self.assertEqual(sum(r['order_fee'] for r in rows), 450)
        self.assertEqual([r['order_fee'] for r in rows], [150, 150, 150])
        self.assertEqual(sum(r['order_fee'] for r in self.quote(0)), 0)
        one = self.quote(240, {'Premium Reliable': 1})
        self.assertEqual(sum(r['order_fee'] for r in one), 300)
        self.assertEqual(sum(r['order_fee'] for r in self.quote(1)), 300)

    def test_400_unit_combinations_and_small_orders(self):
        combinations = [
            ({'Offshore Value': 1}, 300, 10380),
            ({'Balanced Source': 1}, 300, 12900),
            ({'Premium Reliable': 1}, 300, 14788),
            ({'Offshore Value': .7, 'Premium Reliable': .3}, 375, 11777.4),
            ({'Offshore Value': .5, 'Balanced Source': .3, 'Premium Reliable': .2}, 450, 12167.6),
        ]
        for mix, fee, total in combinations:
            quote = self.quote(400, mix)
            self.assertEqual(sum(row['order_fee'] for row in quote), fee)
            self.assertAlmostEqual(sum(row['material_cost'] + row['order_fee'] for row in quote), total)
        # A positive percentage that rounds to zero units must not create a fee.
        self.assertEqual(sum(row['order_fee'] for row in self.quote(2)), 375)
        two = self.quote(400, {'Balanced Source': .5, 'Premium Reliable': .5})
        self.assertEqual([row['order_fee'] for row in two], [0, 187.5, 187.5])

    def test_legacy_policy_load_is_read_only_and_keeps_old_fees(self):
        from utils.database import get_connection
        with database_scope(Path(TEMP.name) / 'legacy_policy.db'):
            repo.load_market_report()
            with get_connection() as connection:
                connection.execute('CREATE TABLE delivery_policy (singleton INTEGER PRIMARY KEY, version INTEGER, seed TEXT, order_fee REAL)')
                connection.execute("INSERT INTO delivery_policy VALUES (1,1,'legacy-seed',300)")
            with get_connection() as connection:
                before = list(connection.iterdump())
            old = load_delivery_policy()
            self.assertEqual(old.version, 1)
            quote = sourcing_quote(400, _normalized_supplier_mix(self.firm), 'Moderate', 1, 70, 1, old)
            self.assertEqual(sum(row['order_fee'] for row in quote), 900)
            with get_connection() as connection:
                self.assertEqual(list(connection.iterdump()), before)

    def test_prices_holding_and_delivery_unchanged_between_policy_versions(self):
        from engine.config import HOLDING_COST_PER_UNIT, RAW_MATERIAL_HOLDING_COST_PER_UNIT
        self.assertEqual((RAW_MATERIAL_HOLDING_COST_PER_UNIT, HOLDING_COST_PER_UNIT), (2, 6))
        old = replace(self.policy, version=1)
        new_quote = self.quote(400)
        old_quote = sourcing_quote(400, _normalized_supplier_mix(self.firm), 'Moderate', 1, 70, 1, old)
        for new, prior in zip(new_quote, old_quote):
            self.assertEqual({k: v for k, v in new.items() if k != 'order_fee'},
                             {k: v for k, v in prior.items() if k != 'order_fee'})

    def test_whole_unit_allocation(self):
        for qty in (0, 1, 2, 7, 101, 240, 10001):
            for economy in range(101):
                quantities = supplier_quantities(qty, {'Offshore Value': economy, 'Balanced Source': 100-economy})
                self.assertEqual(sum(quantities.values()), qty)
                self.assertEqual(quantities['Premium Reliable'], 0)
                self.assertTrue(all(q >= 0 for q in quantities.values()))

    def test_probability_distribution_and_reliable_limit(self):
        for supplier in DISPLAY_NAMES:
            for risk, probabilities in DELAY_PROBABILITIES[supplier].items():
                self.assertAlmostEqual(sum(probabilities), 1)
                sample = Counter(supplier_delay('test-distribution', r, supplier, risk) for r in range(20000))
                for delay, p in enumerate(probabilities):
                    self.assertAlmostEqual(sample[delay]/20000, p, delta=.01)
                if supplier == 'Premium Reliable':
                    self.assertEqual(sample[2], 0)
                    self.assertGreater(sample[0]/20000, .975)

    def test_risk_increases_delay_without_changing_base_time(self):
        for supplier in DISPLAY_NAMES:
            for r in range(1000):
                low, moderate, high = [supplier_delay('monotone', r, supplier, risk)
                                       for risk in ('Low', 'Moderate', 'High')]
                self.assertLessEqual(low, moderate)
                self.assertLessEqual(moderate, high)

    def test_orders_reproducible_and_shared_between_teams(self):
        metrics = _compute_supplier_metrics(self.firm, self.report, COMMON_PROFILE, self.policy)
        orders = _build_material_orders(self.report, self.firm, metrics, COMMON_PROFILE, self.policy)
        other = _build_material_orders(self.report, replace(self.firm, team_name='Different team'),
                                       metrics, COMMON_PROFILE, self.policy)
        self.assertEqual(orders, other)
        self.assertEqual(orders, _build_material_orders(self.report, self.firm, metrics, COMMON_PROFILE, self.policy))
        for order in orders:
            self.assertLessEqual(order.normal_arrival_round, order.arrival_round)
            self.assertLessEqual(order.arrival_round, order.latest_arrival_round)
            self.assertEqual(OpenMaterialOrder.from_dict(order.to_dict()), order)

    def test_separate_classrooms_keep_separate_persistent_seeds(self):
        with database_scope(self.classes[1]['path']):
            other = load_delivery_policy()
        self.assertNotEqual(other.seed, self.policy.seed)
        self.assertEqual(load_delivery_policy(), self.policy)
        with self.assertRaises(ValueError):
            initialize_delivery_policy()

    def test_backup_replays_seed_and_excel_reports_fees_without_seed(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from utils.classrooms import AUTH_CLASSROOM_KEY
        from utils.game_exports import prepare_classroom_downloads, restore_backup_to_new_file
        state = {'authenticated_username': 'export_admin', AUTH_CLASSROOM_KEY: 'default'}
        with patch('utils.classrooms._session', return_value=state), patch('utils.game_exports._session', return_value=state):
            bundle = prepare_classroom_downloads()
        workbook = load_workbook(BytesIO(bundle['excel']))
        self.assertIn('ordering_cost', [c.value for c in workbook['Team Results'][1]])
        self.assertNotIn('seed', [c.value for c in workbook['Delivery Policy'][1]])
        restored = Path(TEMP.name) / 'recovered.db'
        restore_backup_to_new_file(bundle['backup'], restored)
        with database_scope(restored):
            self.assertEqual(load_delivery_policy(), self.policy)
            self.assertEqual(repo.load_team_states(), self.saved_states())

    def saved_states(self):
        with database_scope(DB):
            return repo.load_team_states()

    def test_public_quote_and_transit_table_do_not_leak_future_draw(self):
        normal = OpenMaterialOrder(50, 3, 1, 25.2, 2, 'Offshore Value', 3, 5, .75, 0, 300, 'Moderate')
        delayed = replace(normal, arrival_round=5, weighted_lead_time=4, delay_rounds=2)
        self.assertEqual(public_incoming_orders([normal], 2), public_incoming_orders([delayed], 2))
        self.assertEqual(public_incoming_orders([normal], 3)[0]['Status'], 'Available this round')
        self.assertEqual(public_incoming_orders([delayed], 3)[0]['Status'], 'Delayed / in transit')
        for row in self.quote():
            self.assertNotIn('arrival_round', row)
            self.assertNotIn('delay_rounds', row)

    def test_legacy_orders_not_retimed_or_repriced(self):
        order = OpenMaterialOrder.from_dict(dict(quantity=240, arrival_round=3, placed_round=1,
                    weighted_material_unit_cost=37.12, weighted_lead_time=1.6))
        original = order.to_dict()
        self.assertEqual(_split_open_material_orders(2, [order]), ([], [order]))
        self.assertEqual(_split_open_material_orders(3, [order]), ([order], []))
        self.assertEqual(order.to_dict(), original)

    def test_fees_in_profit_and_cash_once_and_persisted(self):
        def simulate():
            return run_round(self.report, [self.firm], self.lines, self.decisions, [], [])
        new = simulate()
        again = simulate()
        self.assertEqual(new, again)
        with patch('engine.simulator.load_delivery_policy', return_value=None):
            old = simulate()
        row = new[0][0]
        quote = self.quote()
        self.assertEqual(row.ordering_cost, 450)
        self.assertAlmostEqual(row.procurement_cost, sum(r['material_cost'] + r['order_fee'] for r in quote))
        delta = row.procurement_cost - old[0][0].procurement_cost
        self.assertAlmostEqual(row.profit, old[0][0].profit - delta, places=2)
        self.assertAlmostEqual(row.ending_cash_balance, old[0][0].ending_cash_balance - delta, places=2)
        self.assertEqual(sum(o.quantity for o in new[2][0].open_material_orders), 240)
        self.assertEqual(len(new[2][0].open_material_orders), 3)
        # A new throwaway database checks serialization without overwriting fixture history.
        with database_scope(Path(TEMP.name) / 'roundtrip.db'):
            repo.save_round_results([row])
            repo.save_team_states(new[2])
            self.assertEqual(repo.load_round_results(1)[0].ordering_cost, 450)
            self.assertEqual(repo.load_team_states()[0].open_material_orders, new[2][0].open_material_orders)
            self.assertIsNone(load_delivery_policy())

    def test_arrival_only_once_and_no_fee_on_receipt(self):
        orders = [OpenMaterialOrder(10, 3, 1, 25.2, 2), OpenMaterialOrder(20, 4, 1, 31.5, 3)]
        first, remaining = _split_open_material_orders(3, orders)
        second, remaining = _split_open_material_orders(4, remaining)
        self.assertEqual(sum(o.quantity for o in first + second), 30)
        self.assertEqual(remaining, [])

    def test_student_preview_live_costs_and_no_future_arrival_column(self):
        from streamlit.testing.v1 import AppTest
        current = repo.load_market_report().round_number
        save_outlook(current, 400, 600)
        repo.set_round_submissions_open(current, True)
        with patch('streamlit.page_link'):
            app = AppTest.from_file(str(ROOT / 'pages/2_Team_Decisions.py'), default_timeout=60)
            app.session_state['authenticated_username'] = 'demo_022_1'
            app.run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertTrue(any('Supplier Quotes' in h.value for h in app.markdown))
            metrics = {m.label: m.value for m in app.metric}
            self.assertEqual(metrics['Total Ordering Fee'], '$450')
            for field, value in [('supplier_mix_offshore_pct', 70), ('supplier_mix_balanced_pct', 0),
                                 ('supplier_mix_premium_pct', 30), ('raw_material_order_qty', 400)]:
                app.number_input(key='stage_b_' + field).set_value(value)
            app.run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertEqual({m.label: m.value for m in app.metric}['Total Ordering Fee'], '$375')
            self.assertEqual({m.label: m.value for m in app.metric}['Total Order Cash'], '$11,777.40')
            for field, value in [('supplier_mix_offshore_pct', 0), ('supplier_mix_balanced_pct', 0),
                                 ('supplier_mix_premium_pct', 100)]:
                app.number_input(key='stage_b_' + field).set_value(value)
            app.run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertEqual({m.label: m.value for m in app.metric}['Total Ordering Fee'], '$300')
            app.number_input(key='stage_b_raw_material_order_qty').set_value(0).run()
            self.assertEqual({m.label: m.value for m in app.metric}['Total Order Cash'], '$0.00')
            self.assertFalse(app.exception, str(app.exception))
            for table in app.dataframe:
                self.assertNotIn('arrival_round', table.value.columns)
                self.assertNotIn('Scheduled Arrival', table.value.columns)


if __name__ == '__main__':
    unittest.main()
