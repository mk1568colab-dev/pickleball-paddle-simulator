import sys
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data.defaults import DEFAULT_MARKET_REPORT
from engine.market_brief import market_brief


class BriefTests(unittest.TestCase):
    def report(self, **changes):
        row = DEFAULT_MARKET_REPORT.to_dict()
        row.update(demand_outlook_low=1000, demand_outlook_high=1400)
        row.update(changes)
        return row

    def test_private_actual_cannot_affect_summary(self):
        self.assertEqual(market_brief(self.report(total_demand=1)),
                         market_brief(self.report(total_demand=999999)))

    def test_neutral_narrative_without_raw_coefficients_or_advice(self):
        text = market_brief(self.report(material_cost_index=1.2, supply_risk="High", quality_sensitivity=.9))
        self.assertIn("above the baseline", text)
        self.assertIn("higher risk of late", text)
        self.assertIn("particularly strong", text)
        self.assertIn("not confirmed demand", text)
        self.assertIn("1,000 to 1,400", text)
        for unwanted in ('1.2', '0.9', 'midpoint', 'your team', 'you should', 'review', 'check margins'):
            self.assertNotIn(unwanted, text)

    def test_unpublished_outlook(self):
        text = market_brief(self.report(demand_outlook_low="Not published", demand_outlook_high="Not published"))
        self.assertIn("not been published", text)
        self.assertIn('Material prices', text)

    def test_same_public_report_for_different_team_inputs(self):
        self.assertEqual(market_brief(self.report(team_name='A', cash=1, inventory=0)),
                         market_brief(self.report(team_name='B', cash=999999, inventory=999)))

    def test_cost_and_risk_bands(self):
        for value, phrase in ((.8, 'below'), (1.0, 'close to'), (1.05, 'above'), (1.2, 'above')):
            self.assertIn(f'Material prices are {phrase} the baseline', market_brief(self.report(material_cost_index=value)))
        for value, phrase in (('Low', 'relatively stable'), ('Moderate', 'some delivery uncertainty'), ('High', 'higher risk')):
            self.assertIn(phrase, market_brief(self.report(supply_risk=value)))

    def test_technology_quality_and_beginner_signals_are_covered(self):
        for value, emphasis in ((.1, 'limited'), (.5, 'moderate'), (.75, 'strong'), (.9, 'particularly strong')):
            text = market_brief(self.report(premium_tech_adoption=value, mid_market_tech_adoption=value))
            for segment in ('Premium', 'Mid-market'):
                self.assertIn(f'{segment} buyers place {emphasis} emphasis', text)
        for value, phrase in ((.1, 'relatively limited additional'), (.2, 'moderate additional'), (.35, 'strong additional'), (.6, 'particularly strong additional')):
            self.assertIn(phrase, market_brief(self.report(technology_shift_rate=value)))
        for value, phrase in ((.1, 'relatively limited influence'), (.5, 'moderate influence'), (.75, 'a strong influence'), (.9, 'particularly strong influence')):
            self.assertIn(phrase, market_brief(self.report(quality_sensitivity=value)))
        for value, phrase in ((.1, 'narrower range'), (.5, 'moderate range'), (.9, 'broader range')):
            self.assertIn(phrase, market_brief(self.report(beginner_price_pressure=value)))
        self.assertIn('Generation 3', market_brief(self.report(current_market_generation=3)))

    def test_segment_ties_and_empty_mix(self):
        self.assertIn('evenly distributed', market_brief(self.report(beginner_share=1, mid_share=1, premium_share=1)))
        self.assertIn('share the largest', market_brief(self.report(beginner_share=.4, mid_share=.4, premium_share=.2)))
        self.assertIn('equal, smaller portions', market_brief(self.report(beginner_share=.2, mid_share=.6, premium_share=.2)))
        self.assertIn('concentrated entirely in Premium', market_brief(self.report(beginner_share=0, mid_share=0, premium_share=1)))
        self.assertIn('mix is not available', market_brief(self.report(beginner_share=0, mid_share=0, premium_share=0)))

    def test_event_is_not_invented_or_rewritten(self):
        text = market_brief(self.report(event='Retailers announce a tournament promotion.'))
        self.assertIn('Market event: Retailers announce a tournament promotion.', text.split('\n\n')[1])
        self.assertNotIn('Market event:', market_brief(self.report(event='')))

    def test_three_english_paragraphs_for_each_round(self):
        cases = [
            dict(round_number=1, material_cost_index=.8, supply_risk='Low', quality_sensitivity=.2, event=''),
            dict(round_number=2, material_cost_index=1.0, supply_risk='Moderate', quality_sensitivity=.5, event='Classroom market update.'),
            dict(round_number=3, material_cost_index=1.2, supply_risk='High', quality_sensitivity=.9, event='Supply disruption scenario.'),
        ]
        reports = []
        for case in cases:
            text = market_brief(self.report(**case))
            self.assertEqual(len(text.split('\n\n')), 3)
            self.assertIn(f'Round {case["round_number"]}', text)
            self.assertTrue(text.isascii())
            self.assertEqual(text, market_brief(self.report(**case)))
            reports.append(text)
        self.assertEqual(len(set(reports)), 3)

    def test_exact_numeric_boundaries(self):
        for value, phrase in ((.949999, 'below'), (.95, 'close to'), (1.049999, 'close to'), (1.05, 'above')):
            self.assertIn(f'Material prices are {phrase} the baseline', market_brief(self.report(material_cost_index=value)))
        for key in ('quality_sensitivity', 'premium_tech_adoption', 'mid_market_tech_adoption', 'beginner_price_pressure'):
            low = market_brief(self.report(**{key: .399999}))
            at_middle = market_brief(self.report(**{key: .4}))
            below_high = market_brief(self.report(**{key: .699999}))
            at_high = market_brief(self.report(**{key: .7}))
            self.assertNotEqual(low, at_middle)
            self.assertEqual(at_middle, below_high)
            self.assertNotEqual(below_high, at_high)
        for value, phrase in ((.149999, 'relatively limited'), (.15, 'moderate'), (.299999, 'moderate'), (.3, 'strong')):
            self.assertIn(f'face {phrase} additional obsolescence pressure', market_brief(self.report(technology_shift_rate=value)))

    def test_student_page_shared_narrative_and_post_round_reveal(self):
        from streamlit.testing.v1 import AppTest
        from utils.classrooms import database_scope
        from utils import repository as repo
        from utils.demand_protocol import save_outlook, complete_demand_round, public_market_row
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'narrative.db'
            with patch.dict(os.environ, {'SIMULATOR_DB_PATH': str(path), 'SIMULATOR_ENV': 'dev',
                                        'SIMULATOR_ENABLE_DEMO_ACCOUNTS': 'false'}), database_scope(path):
                for username, role, team in [('report_admin', 'admin', None), ('report_a', 'team_leader', 'Team A'),
                                             ('report_b', 'team_leader', 'Team B')]:
                    repo.create_user(username, 'unused-test-hash', role, team, True)
                report = replace(repo.load_market_report(), total_demand=1187, event='Public test event.')
                repo.save_market_report(report)
                save_outlook(report.round_number, 1000, 1400)
                expected = market_brief(public_market_row(report))
                with patch('streamlit.page_link'):
                    for username in ('report_a', 'report_b'):
                        app = AppTest.from_file(str(root / 'pages/1_Public_Market_Report.py'), default_timeout=30)
                        app.session_state['authenticated_username'] = username
                        app.run()
                        self.assertFalse(app.exception, str(app.exception))
                        texts = [item.value for item in app.markdown]
                        self.assertIn(expected, texts)
                        self.assertNotIn('1187', '\n'.join(texts))
                        self.assertEqual(len(app.table), 0)
                        self.assertEqual(len(app.number_input), 0)
                    admin = AppTest.from_file(str(root / 'pages/1_Public_Market_Report.py'), default_timeout=30)
                    admin.session_state['authenticated_username'] = 'report_admin'
                    admin.run()
                    self.assertFalse(admin.exception, str(admin.exception))
                    self.assertIn('Material Cost Index', [w.label for w in admin.number_input])
                    repo.set_round_submissions_open(report.round_number, True)
                    app.run()
                    self.assertEqual(len(app.table), 0)
                    repo.set_round_submissions_open(report.round_number, False)
                    complete_demand_round(report.round_number)
                    app.run()
                    self.assertFalse(app.exception, str(app.exception))
                    self.assertEqual(app.table[0].value['Actual Market Demand'].iloc[0], 1187)

    def test_refined_quality_and_technology_boundaries(self):
        fields = [('quality_sensitivity', .85), ('premium_tech_adoption', .85),
                  ('mid_market_tech_adoption', .85), ('technology_shift_rate', .50)]
        baseline = self.report(event='')
        for key, cutoff in fields:
            with self.subTest(key=key):
                before = market_brief(dict(baseline, **{key: cutoff - .000001}))
                at = market_brief(dict(baseline, **{key: cutoff}))
                after = market_brief(dict(baseline, **{key: 1.0}))
                self.assertNotEqual(before, at)
                self.assertEqual(at, after)
                self.assertEqual(before.split('\n\n')[:2], at.split('\n\n')[:2])
                self.assertEqual(len(at.split('\n\n')), 3)

    def test_exactly_four_levels_without_expanding_other_indicators(self):
        for key, values in [('quality_sensitivity', (0, .5, .75, .9)),
                            ('premium_tech_adoption', (0, .5, .75, .9)),
                            ('mid_market_tech_adoption', (0, .5, .75, .9)),
                            ('technology_shift_rate', (0, .2, .4, .6))]:
            self.assertEqual(len({market_brief(self.report(**{key: value})) for value in values}), 4)
        self.assertEqual(market_brief(self.report(beginner_price_pressure=.75)),
                         market_brief(self.report(beginner_price_pressure=.9)))
        self.assertEqual(market_brief(self.report(material_cost_index=1.1)),
                         market_brief(self.report(material_cost_index=1.4)))


if __name__ == "__main__":
    unittest.main()
