"""Read-only UI checks for the production material balance."""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'pages/2_Team_Decisions.py').read_text(encoding='utf-8')
NODE = next(n for n in ast.parse(SOURCE).body if isinstance(n, ast.FunctionDef)
            and n.name == '_render_state_snapshot')
FUNCTION = ast.get_source_segment(SOURCE, NODE)


class MaterialSnapshotTests(unittest.TestCase):
    def render(self, round_number, inventory, completed, orders):
        script = '''
import streamlit as st
import pandas as pd
from dataclasses import replace
from data.classroom_start import COMMON_PROFILE, initial_state
from data.defaults import DEFAULT_MARKET_REPORT
from models.schemas import TeamArchetype, ProductLine, OpenMaterialOrder
from engine.config import STARTING_RAW_MATERIAL_COVERAGE
'''
        script += FUNCTION
        script += f'''
state = replace(initial_state("UI Test"), raw_material_inventory={inventory},
                completed_rounds={completed!r},
                open_material_orders=[OpenMaterialOrder.from_dict(o) for o in {orders!r}])
_render_state_snapshot([], state, replace(DEFAULT_MARKET_REPORT, round_number={round_number}), COMMON_PROFILE)
'''
        app = AppTest.from_string(script).run()
        self.assertFalse(app.exception)
        return {m.label: m.value for m in app.metric}

    def test_due_future_and_overdue_orders(self):
        values = self.render(3, 60, [1, 2], [
            dict(quantity=240, arrival_round=3), dict(quantity=500, arrival_round=4),
            dict(quantity=10, arrival_round=2)])
        self.assertEqual(values['RM Carried Over'], '60')
        self.assertEqual(values['RM Arriving This Round'], '250')
        self.assertEqual(values['RM Available for Production'], '310')

    def test_zero_stock_is_not_reseeded_after_first_round(self):
        values = self.render(3, 0, [1, 2], [dict(quantity=240, arrival_round=3)])
        self.assertEqual(values['RM Carried Over'], '0')
        self.assertEqual(values['RM Available for Production'], '240')

    def test_initial_and_consumed_inventory(self):
        self.assertEqual(self.render(1, 300, [], [])['RM Available for Production'], '300')
        values = self.render(4, 40, [1, 2, 3], [])
        self.assertEqual(values['RM Arriving This Round'], '0')
        self.assertEqual(values['RM Available for Production'], '40')


if __name__ == '__main__':
    unittest.main()
