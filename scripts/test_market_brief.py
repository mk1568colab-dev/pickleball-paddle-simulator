import sys
import unittest
from pathlib import Path
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

    def test_meaningful_summary_and_scenarios(self):
        text, rows = market_brief(self.report(material_cost_index=1.2, supply_risk="High", quality_sensitivity=.9))
        self.assertIn("more expensive", text)
        self.assertIn("Supply risk is high", text)
        self.assertIn("Quality is especially", text)
        self.assertIn("not a guaranteed", text)
        self.assertEqual(sum(r["Midpoint scenario"] for r in rows), 1200)

    def test_unpublished_outlook(self):
        text, rows = market_brief(self.report(demand_outlook_low="Not published", demand_outlook_high="Not published"))
        self.assertIn("not published", text)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
