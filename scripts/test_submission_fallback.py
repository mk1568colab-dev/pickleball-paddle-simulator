import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temp = tempfile.TemporaryDirectory()
os.environ['SIMULATOR_DB_PATH'] = str(Path(temp.name) / 'fallback.db')
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'

from data.defaults import DEFAULT_MARKET_REPORT
from engine.simulator import run_round
from models.schemas import ProductDevelopmentProject
from utils import repository as repo
from utils.submission_fallback import complete_round_inputs, save_fallback_decisions


class FallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for i in range(40):
            repo.create_user(f'fallback_{i}', 'not-a-login-hash', 'team_leader', f'Team {i:02}', True)

    def inputs(self, round_number, firms=None, products=None, projects=None):
        return complete_round_inputs(round_number, firms or [], products or [], projects or [],
                                     repo.load_product_lines(), repo.load_team_states())

    def test_all_40_missing_first_round_and_consecutive_rounds(self):
        firms, products, projects, lines, missing = self.inputs(1)
        self.assertEqual(len(firms), 40)
        self.assertEqual(len(missing), 40)
        self.assertEqual(len(products), 200)
        self.assertEqual(sum(p.planned_production_units for p in products), 9600)
        states = repo.load_team_states()
        self.assertTrue(all(s.raw_material_inventory == 300 for s in states))
        for r in range(1, 4):
            output = run_round(replace(DEFAULT_MARKET_REPORT, round_number=r, total_demand=9000),
                               firms, lines, products, projects, states)
            self.assertEqual(len(output[0]), 40)
            save_fallback_decisions(r, firms, products, missing)
            repo.save_product_lines(output[3])
            repo.save_team_states(output[2])
            repo.save_product_round_results(output[1])
            firms, products, projects, lines, missing = self.inputs(r + 1)
            states = repo.load_team_states()
            self.assertEqual(len(firms), 40)
            self.assertEqual(firms[0].raw_material_order_qty, 240)

    def test_mixed_submissions_and_development_is_paused(self):
        firms, products, _, _, _ = self.inputs(1)
        submitted = replace(firms[0], raw_material_order_qty=777)
        saved = [p for p in products if p.team_name == submitted.team_name]
        projects = [ProductDevelopmentProject.from_dict(dict(
            team_name=f.team_name, project_name='Development', investment_this_round=500,
            cumulative_investment=1200, cumulative_testing=0.5, testing_intensity=0.5,
            launch_now=True, cancel_now=True)) for f in firms[:2]]
        effective = self.inputs(5, [submitted], saved, projects)
        self.assertEqual(len(effective[4]), 39)
        self.assertEqual(effective[0][0].raw_material_order_qty, 777)
        self.assertEqual(effective[1][:5], saved)
        self.assertEqual(effective[2][0], projects[0])
        paused = effective[2][1]
        self.assertEqual((paused.investment_this_round, paused.testing_intensity), (0, 0))
        self.assertFalse(paused.launch_now or paused.cancel_now)
        self.assertEqual((paused.cumulative_investment, paused.cumulative_testing), (1200, 0.5))
        self.assertEqual(projects[1].investment_this_round, 500)

    def test_retired_product_is_not_resurrected(self):
        firms, products, _, lines, _ = self.inputs(1)
        team = firms[-1].team_name
        selected = [p for p in products if p.team_name == team]
        repo.save_team_decision(firms[-1], 7)
        repo.save_product_decisions(selected, 7)
        retired = replace(next(p for p in lines if p.team_name == team and p.slot_name == 'A'),
                          is_active=False, retirement_flag=True)
        repo.save_product_lines([retired])
        effective = self.inputs(8)
        product = next(p for p in effective[1] if p.team_name == team and p.slot_name == 'A')
        self.assertFalse(product.is_active)
        self.assertEqual(product.planned_production_units, 0)

    def test_all_submitted_is_unchanged(self):
        firms, products, projects, lines, _ = self.inputs(1)
        effective = complete_round_inputs(1, firms, products, projects, lines, repo.load_team_states())
        self.assertEqual(effective, (firms, products, projects, lines, []))


if __name__ == '__main__':
    unittest.main()
