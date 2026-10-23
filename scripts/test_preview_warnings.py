from dataclasses import replace
import unittest
import test_five_slot_launch as fixtures
from test_five_slot_launch import COMMON_PROFILE_NAME, initial_state, DEFAULT_MARKET_REPORT, TeamDecision, ProductDecision, load_product_lines
from engine.simulator import preview_team_decision


class WarningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.LaunchTests.setUpClass()

    def preview(self, active_price=189, project=None, demand=1200):
        lines = load_product_lines(team_name="Launch Test")
        decisions = [ProductDecision.from_dict(dict(
            team_name="Launch Test", slot_name=p.slot_name, product_name=p.product_name,
            is_active=p.is_active, target_segment=p.target_segment,
            selling_price_per_unit=active_price if p.is_active else 0,
            forecast_units=40 if p.is_active else 0,
            planned_production_units=40 if p.is_active else 0,
            qc_budget_per_unit=3)) for p in lines]
        firm = TeamDecision.from_dict(dict(team_name="Launch Test", archetype=COMMON_PROFILE_NAME,
            supplier_mix_offshore_pct=30, supplier_mix_balanced_pct=50, supplier_mix_premium_pct=20))
        return preview_team_decision(replace(DEFAULT_MARKET_REPORT, round_number=3, total_demand=demand),
            firm, decisions, [project] if project else [], lines, [], [], [],
            [initial_state("Launch Test")])

    def test_empty_slots_never_trigger_price_warning(self):
        for demand in [0, 1200]:
            result = self.preview(demand=demand)
            self.assertFalse(any("priced below" in w for w in result.warnings))

    def test_active_low_prices_still_warn(self):
        result = self.preview(active_price=1)
        self.assertEqual(sum("priced below" in w for w in result.warnings), 2)
        self.assertFalse(any("Open Product Slot" in w for w in result.warnings))

    def test_launch_into_vacant_slot_still_checks_new_price(self):
        result = self.preview(project=fixtures.LaunchTests().project("D"))
        self.assertTrue(any("New Paddle is priced below" in w for w in result.warnings))


if __name__ == "__main__":
    unittest.main()
