"""Shared opening conditions and fictional, non-accounting handover records."""

from models.schemas import PersistentTeamState, ProductTemplate, TeamArchetype

COMMON_PROFILE_NAME = "Equal Start"
STARTING_CASH = 50_000.0
COMMON_PROFILE = TeamArchetype(
    name=COMMON_PROFILE_NAME,
    description="Common operating baseline; strategy emerges from decisions, not a selected type.",
    base_cost=70.0, base_capacity=300, base_reputation=60.0,
    base_defect_rate=0.03, premium_fit=0.65, mid_fit=0.75, beginner_fit=0.65,
    suggested_overtime_capacity_units=0, suggested_capacity_expansion_units=0,
    suggested_max_backorder_units=30, suggested_raw_material_order_qty=240,
    suggested_supplier_mix_offshore_pct=30.0,
    suggested_supplier_mix_balanced_pct=50.0,
    suggested_supplier_mix_premium_pct=20.0,
    suggested_expedited_order_share_pct=0.0,
    suggested_product_templates=[
        ProductTemplate("A", "Core Control", True, "mid", "growth", 2,
                        0.0, 1.0, 149.0, 130, 3.0, 0, tech_generation=2,
                        cannibalization_group="control"),
        ProductTemplate("B", "Starter Play", True, "beginner", "maturity", 4,
                        0.0, 1.0, 99.0, 110, 3.0, 0, tech_generation=1,
                        cannibalization_group="entry"),
        ProductTemplate("C", "Open Product Slot", False, "mid", "launch", 0,
                        0.0, 1.0, 149.0, 0, 3.0, 0, tech_generation=2,
                        retirement_flag=True, retired_round=0),
    ],
)


def initial_state(team_name: str) -> PersistentTeamState:
    return PersistentTeamState(
        team_name=team_name, archetype=COMMON_PROFILE_NAME,
        cash_balance=STARTING_CASH, raw_material_inventory=300,
        capacity_units=300, reputation_score=60.0,
    )


def handover_rows() -> list[dict]:
    """Planning examples only: never inserted into scored results or cash ledgers."""
    rows = []
    for period, core, starter, defects in [(-3, 112, 118, 3.2), (-2, 122, 114, 3.0), (-1, 130, 110, 2.8)]:
        for product, units, price in [("Core Control", core, 149.0), ("Starter Play", starter, 99.0)]:
            rows.append({"Period": f"Pre-game {period}", "Product": product,
                         "Price ($)": price, "Sales (units)": units,
                         "QC ($/unit)": 3.0, "Inspection defect rate (%)": defects})
    return rows
