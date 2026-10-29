"""Supply detail UI and isolation checks, using disposable databases only."""

from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEMP = tempfile.TemporaryDirectory()
os.environ['SIMULATOR_DB_PATH'] = str(Path(TEMP.name) / 'unused.db')
os.environ['SIMULATOR_ENV'] = 'dev'
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'

from data.classroom_start import COMMON_PROFILE, COMMON_PROFILE_NAME, initial_state
from data.defaults import DEFAULT_MARKET_REPORT
from models.schemas import OpenMaterialOrder, TeamDecision
from utils import repository as repo
from utils.classrooms import database_scope
from utils.database import get_connection
from utils.demand_protocol import save_outlook
from utils.sourcing_rules import DeliveryPolicy, initialize_delivery_policy
from utils.supply_planning import (
    COMPARISON_KEY, KEEP_KEY, arrival_rows, comparison_context, comparison_rows,
    plan_snapshot, product_comparison_rows, proposed_receipts,
)


def firm(**changes):
    return TeamDecision.from_dict(dict(team_name='Plan Team', archetype=COMMON_PROFILE_NAME,
        raw_material_order_qty=240, supplier_mix_offshore_pct=30,
        supplier_mix_balanced_pct=50, supplier_mix_premium_pct=20) | changes)


class PublicPlanTests(unittest.TestCase):
    def test_existing_legacy_rounding_is_unchanged(self):
        report = replace(DEFAULT_MARKET_REPORT, round_number=6, supply_risk='Moderate')
        plan = firm(raw_material_order_qty=460, supplier_mix_offshore_pct=100,
                    supplier_mix_balanced_pct=0, supplier_mix_premium_pct=0)
        self.assertEqual(proposed_receipts(plan, report, COMMON_PROFILE, None),
                         [dict(supplier='Mixed order', quantity=460, first=8, last=8, on_time='-')])

    def test_zero_order_and_invalid_mix_have_no_proposed_receipts(self):
        for plan in (firm(raw_material_order_qty=0), firm(supplier_mix_offshore_pct=0)):
            self.assertEqual(proposed_receipts(plan, DEFAULT_MARKET_REPORT, COMMON_PROFILE, None), [])

    def test_future_delay_draws_do_not_leak(self):
        order = OpenMaterialOrder(50, 3, 1, 25.2, 2, 'Offshore Value', 3, 5, .75, 0, 300, 'Moderate')
        delayed = replace(order, arrival_round=5, weighted_lead_time=4, delay_rounds=2)
        original = deepcopy(order.to_dict())
        self.assertEqual(arrival_rows([order], 2, []), arrival_rows([delayed], 2, []))
        self.assertEqual(arrival_rows([order], 3, [])[0]['Status'], 'Available this round')
        self.assertEqual(arrival_rows([delayed], 3, [])[0]['Status'], 'Delayed / in transit')
        self.assertEqual(order.to_dict(), original)

    def test_supplier_windows_are_public_and_orders_remain_distinct(self):
        policy = DeliveryPolicy('test-private-seed')
        report = replace(DEFAULT_MARKET_REPORT, round_number=2, supply_risk='Moderate')
        proposed = proposed_receipts(firm(), report, COMMON_PROFILE, policy)
        self.assertEqual(sum(row['quantity'] for row in proposed), 240)
        reliable = next(row for row in proposed if row['supplier'] == 'Reliable')
        self.assertEqual((reliable['first'], reliable['last']), (3, 4))
        existing = OpenMaterialOrder(100, 3, 1, 30, 2)
        rows = arrival_rows([existing], 2, proposed)
        self.assertEqual([row['Order'] for row in rows], ['Existing', 'Proposed', 'Proposed', 'Proposed'])
        self.assertTrue(all(row['Status'] == 'Not placed' for row in rows[1:]))
        self.assertNotIn(policy.seed, str(rows))

    def test_snapshot_is_independent_and_deltas_are_not_recommendations(self):
        preview = SimpleNamespace(total_planned_production_units=240, total_material_required=233,
            raw_material_units_available=300, weighted_material_unit_cost=30.55,
            projected_ordering_cost=0, projected_procurement_cost=7332,
            material_rows=[{'Slot': 'A', 'Product': 'Paddle', 'Planned Paddles': 130, 'RM Required': 156}])
        saved = plan_snapshot(preview, firm(), [])
        preview.material_rows[0]['Planned Paddles'] = 200
        self.assertEqual(saved['products'][0]['Planned Paddles'], 130)
        current = deepcopy(saved)
        current.update(order_cash=12220, balance=-17, mix='Reliable 100%')
        rows = {row['Measure']: row for row in comparison_rows(saved, current)}
        self.assertEqual(rows['Total order cash']['Change'], '+$4,888.00')
        self.assertEqual(rows['RM surplus / shortage']['Change'], '-84.00')
        self.assertEqual(rows['Supplier mix']['Change'], 'Changed')
        current['products'] = []
        self.assertEqual(product_comparison_rows(saved, current)[0]['Current paddles'], 0)


class SupplyPageTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(TEMP.name) / (self.id().split('.')[-1] + '.db')
        scope = database_scope(self.path)
        scope.__enter__()
        self.addCleanup(scope.__exit__, None, None, None)
        env = patch.dict(os.environ, {'SIMULATOR_DB_PATH': str(self.path)})
        env.start()
        self.addCleanup(env.stop)
        links = patch('streamlit.page_link')
        links.start()
        self.addCleanup(links.stop)
        self.admin = repo.create_user('plan_admin', 'test-only-hash', 'admin', None, True)
        self.user = repo.create_user('plan_student', 'test-only-hash', 'team_leader', 'Plan Team', True)
        repo.create_user('plan_other', 'test-only-hash', 'team_leader', 'Other Team', True)
        state = initial_state('Plan Team')
        state.open_material_orders = [OpenMaterialOrder(100, 3, 1, 31.5, 2)]
        repo.save_team_states([state])

    def app(self, probabilistic=False):
        from streamlit.testing.v1 import AppTest
        if probabilistic:
            initialize_delivery_policy()
        save_outlook(1, 1000, 1400)
        repo.set_round_submissions_open(1, True)
        app = AppTest.from_file(str(ROOT / 'pages/2_Team_Decisions.py'), default_timeout=45)
        app.session_state['authenticated_username'] = self.user.username
        app.run()
        self.assertFalse(app.exception, str(app.exception))
        return app

    def dump(self):
        with get_connection() as connection:
            schema = [tuple(row) for row in connection.execute(
                'SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name')]
            tables = {}
            for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                identifier = '"' + name.replace('"', '""') + '"'
                columns = [row[1] for row in connection.execute(f'PRAGMA table_info({identifier})')]
                # Existing bootstrap refreshes this reference-table timestamp on every rerun.
                selected = [column for column in columns
                            if not (name == 'team_archetypes' and column == 'updated_at')]
                projection = ', '.join('"' + column.replace('"', '""') + '"' for column in selected)
                tables[name] = sorted((tuple(row) for row in connection.execute(
                    f'SELECT {projection} FROM {identifier}')), key=repr)
            return schema, tables

    def test_collapsed_panels_keep_existing_controls_and_do_not_save(self):
        app = self.app()
        expanders = {item.label: item for item in app.expander}
        for label in ('Arrival schedule', 'Compare options'):
            self.assertIn(label, expanders)
            self.assertFalse(expanders[label].proto.expanded)
        labels = {item.label for item in app.number_input}
        self.assertTrue({'Raw Material Order', 'Economy %', 'Standard %', 'Reliable %', 'Borrowing'} <= labels)
        self.assertIn('Save Portfolio and Pipeline Decision', [item.label for item in app.button])
        before = self.dump()
        app.button(key=KEEP_KEY).click().run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(self.dump(), before)
        self.assertIsNone(repo.load_team_decision(1, 'Plan Team'))
        self.assertTrue(app.session_state[COMPARISON_KEY]['plan'])

    def test_product_and_sourcing_changes_update_only_current_comparison(self):
        app = self.app()
        app.button(key=KEEP_KEY).click().run()
        saved = deepcopy(app.session_state[COMPARISON_KEY])
        before = self.dump()
        app.number_input(key='stage_b_raw_material_order_qty').set_value(400)
        app.number_input(key='stage_b_product_A_planned_production_units').set_value(200).run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(app.session_state[COMPARISON_KEY], saved)
        comparison = next(item.value for item in app.dataframe if 'Kept comparison' in item.value.columns)
        rows = comparison.set_index('Measure')
        self.assertEqual(rows.loc['New RM order', 'Current plan'], '400')
        self.assertEqual(rows.loc['New RM order', 'Kept comparison'], '240')
        self.assertEqual(rows.loc['Required RM', 'Current plan'], '317.00')
        self.assertEqual(rows.loc['Total order cash', 'Current plan'], '$12,220.00')
        self.assertEqual(self.dump(), before)
        app.button(key=KEEP_KEY).click().run()
        self.assertEqual(app.session_state[COMPARISON_KEY]['plan']['order'], 400)

    def test_invalid_mix_disables_capture_without_losing_kept_plan(self):
        app = self.app()
        app.button(key=KEEP_KEY).click().run()
        kept = deepcopy(app.session_state[COMPARISON_KEY])
        app.number_input(key='stage_b_supplier_mix_offshore_pct').set_value(0).run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(app.button(key=KEEP_KEY).disabled)
        self.assertEqual(app.session_state[COMPARISON_KEY], kept)
        self.assertFalse(any('Kept comparison' in item.value.columns for item in app.dataframe))

    def test_zero_order_has_no_receipt_or_cash_and_still_compares(self):
        app = self.app()
        app.number_input(key='stage_b_raw_material_order_qty').set_value(0).run()
        app.button(key=KEEP_KEY).click().run()
        saved = app.session_state[COMPARISON_KEY]['plan']
        self.assertEqual((saved['order_cash'], saved['window']), (0, '-'))
        schedule = next(item.value for item in app.dataframe if 'Order' in item.value.columns)
        self.assertEqual(set(schedule['Order']), {'Existing'})

    def test_probabilistic_page_keeps_public_windows_and_fees(self):
        app = self.app(probabilistic=True)
        before = self.dump()
        app.button(key=KEEP_KEY).click().run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(app.session_state[COMPARISON_KEY]['plan']['fees'], 450)
        schedule = next(item.value for item in app.dataframe if 'Order' in item.value.columns)
        self.assertEqual((schedule['Order'] == 'Proposed').sum(), 3)
        self.assertEqual(self.dump(), before)

    def test_switching_user_team_clears_comparison(self):
        app = self.app()
        app.button(key=KEEP_KEY).click().run()
        app.session_state['authenticated_username'] = 'plan_other'
        app.run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertNotIn(COMPARISON_KEY, app.session_state.filtered_state)

    def test_next_round_clears_comparison(self):
        app = self.app()
        app.button(key=KEEP_KEY).click().run()
        repo.save_market_report(replace(DEFAULT_MARKET_REPORT, round_number=2))
        save_outlook(2, 1000, 1400)
        app.run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertNotIn(COMPARISON_KEY, app.session_state.filtered_state)

    def test_context_includes_classroom_game_rules_and_account(self):
        report = DEFAULT_MARKET_REPORT
        def context(**changes):
            return comparison_context(changes.get('user', self.user), changes.get('firm', firm()),
                changes.get('report', report), COMMON_PROFILE, changes.get('policy'))
        original = context()
        for changes in (dict(user=self.admin), dict(firm=firm(team_name='Other Team')),
                        dict(report=replace(report, round_number=2)),
                        dict(report=replace(report, material_cost_index=1.2)),
                        dict(policy=DeliveryPolicy('test-seed'))):
            self.assertNotEqual(context(**changes), original)
        with patch('utils.supply_planning.active_classroom_id', return_value='another-class'):
            self.assertNotEqual(context(), original)
        with get_connection() as connection:
            connection.execute("UPDATE decision_audit_context SET game_id='different-game'")
        self.assertNotEqual(context(), original)


if __name__ == '__main__':
    unittest.main()
