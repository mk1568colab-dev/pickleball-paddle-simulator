import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from streamlit.testing.v1 import AppTest
from data.defaults import DEFAULT_MARKET_REPORT
from models.schemas import RoundResult

PAGE = Path(__file__).resolve().parents[1] / 'pages/4_Results_Dashboard.py'


class RankingTests(unittest.TestCase):
    def render(self, role='team_leader', completed=4):
        rows = [RoundResult.from_dict(dict(round_number=r, team_name=team,
                    archetype='Equal Start', profit=r * (100 if team == 'Own' else 1000)))
                for r in range(1, completed + 1) for team in ['Own', 'Other']]
        def results(round_number=None, team_name=None):
            return [r for r in rows if (round_number is None or r.round_number == round_number)
                    and (team_name is None or r.team_name == team_name)]
        with patch('utils.bootstrap.ensure_app_storage'), \
             patch('utils.auth.require_authenticated_user', return_value=SimpleNamespace(role=role, team_name='Own')), \
             patch('utils.demand_protocol.public_market_row', return_value={'round_number': completed + 1}), \
             patch('utils.demand_protocol.revealed_demands', return_value=[]), \
             patch.multiple('utils.repository', load_round_results=results,
                 load_market_report=lambda r=None: replace(DEFAULT_MARKET_REPORT, round_number=r or completed + 1),
                 load_product_round_results=lambda **kw: [], load_forecast_accuracy_results=lambda **kw: [],
                 load_product_lines=lambda **kw: [], load_product_development_projects=lambda **kw: [],
                 load_team_states=lambda **kw: []):
            app = AppTest.from_file(str(PAGE)).run(timeout=20)
        self.assertFalse(app.exception)
        return app

    def test_student_sees_odd_competitor_snapshot_and_all_own_rounds(self):
        app = self.render()
        public = [d.value for d in app.dataframe if 'team_name' in d.value
                  and 'Other' in set(d.value['team_name'])]
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0].loc[public[0].team_name == 'Other', 'profit'].iloc[0], 3000)
        own = next(d.value for d in app.dataframe if 'round_number' in d.value
                   and 'profit' in d.value and len(d.value) == 4)
        self.assertEqual(set(own.round_number), {1, 2, 3, 4})
        self.assertTrue(any('Round 3' in c.value and 'Round 5' in c.value for c in app.caption))

    def test_first_and_next_odd_release(self):
        for completed, expected in [(1, 1000), (2, 1000), (3, 3000), (5, 5000), (7, 7000)]:
            with self.subTest(completed=completed):
                app = self.render(completed=completed)
                public = next(d.value for d in app.dataframe if 'team_name' in d.value
                              and 'Other' in set(d.value['team_name']))
                self.assertEqual(public.loc[public.team_name == 'Other', 'profit'].iloc[0], expected)

    def test_admin_retains_even_round_results(self):
        app = self.render(role='admin')
        latest = next(d.value for d in app.dataframe if 'round_number' in d.value
                      and 'profit' in d.value and len(d.value) == 2)
        self.assertEqual(set(latest.round_number), {4})
        self.assertIn(4000, set(latest.profit))

    def test_no_completed_rounds(self):
        app = self.render(completed=0)
        self.assertTrue(any('Competitor rankings' in i.value for i in app.info))


if __name__ == '__main__':
    unittest.main()
