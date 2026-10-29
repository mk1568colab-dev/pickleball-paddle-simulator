"""Read-only teaching views: no scoring bonuses or simulation mutations."""

from data.classroom_start import COMMON_PROFILE

SEGMENTS = {"mid": "Mid-market", "premium": "Premium", "beginner": "Beginner"}


def initial_catalog(team_names):
    return [
        {"Team": team, "Paddle": p.product_name, "Segment": SEGMENTS[p.target_segment],
         "Technology": f"Gen {p.tech_generation}", "Price ($)": p.suggested_selling_price_per_unit}
        for team in sorted(set(team_names)) for p in COMMON_PROFILE.suggested_product_templates if p.is_active
    ]


def completed_catalog(results, completed_round, decisions):
    """Allowlist public fields; never consume current-round drafts or private state."""
    active = {(d.team_name, d.slot_name) for d in decisions if d.is_active and not d.retire_flag}
    return [
        {"Team": r.team_name, "Paddle": r.product_name,
         "Segment": SEGMENTS.get(r.target_segment, r.target_segment),
         "Technology": f"Gen {r.tech_generation}", "Price ($)": r.selling_price_per_unit}
        for r in results if r.round_number == completed_round and not r.retired_this_round
        and ((r.team_name, r.slot_name) in active or r.launched_this_round)
    ]


def strategy_signals(firm, products, projects, capacity):
    """Transparent classroom heuristics, not validated company classifications."""
    products = [p for p in products if p.is_active and not p.retire_flag]
    units = sum(p.planned_production_units for p in products)
    weight = sum(max(p.planned_production_units, 1) for p in products)
    qc = sum(p.qc_budget_per_unit * max(p.planned_production_units, 1) for p in products) / max(weight, 1)
    thresholds = {"beginner": 99, "mid": 149, "premium": 189}
    price_index = sum(p.selling_price_per_unit / thresholds[p.target_segment] * max(p.planned_production_units, 1) for p in products) / max(weight, 1)
    active_projects = [p for p in projects if p.is_defined() and p.is_pipeline_active() and not p.cancel_now]
    investment = sum(p.investment_this_round for p in active_projects)
    launch = any(p.launch_now for p in active_projects)
    checks = [
        ("Premium / quality", [qc >= 5, firm.supplier_mix_premium_pct >= 40, any(p.target_segment == "premium" for p in products)],
         f"QC ${qc:.2f}/unit; Reliable sourcing {firm.supplier_mix_premium_pct:.0f}%; premium product {'yes' if any(p.target_segment == 'premium' for p in products) else 'no'}",
         "QC >= $5/unit; Reliable sourcing >= 40%; an active premium product", "Defect rate; contribution per unit; premium sales"),
        ("Low cost / volume", [price_index <= .95 and bool(products), firm.supplier_mix_offshore_pct >= 60, units >= .85 * max(capacity, 1)],
         f"Segment-relative price {price_index:.2f}x; Economy {firm.supplier_mix_offshore_pct:.0f}%; planned units {units}",
         "Price <= 95% of segment benchmark; Economy >= 60%; planned units >= 85% of installed capacity", "Unit cost; sales volume; utilization; inventory and defects"),
        ("Growth / expansion", [firm.capacity_expansion_units > 0, firm.overtime_capacity_units > 0, units > capacity],
         f"Expansion {firm.capacity_expansion_units}; overtime {firm.overtime_capacity_units}; planned units {units}",
         "Capacity expansion > 0; overtime > 0; planned units > installed capacity", "Sales and share growth; cash and debt exposure"),
        ("Technology / development", [investment > 0, any(p.target_tech_generation > 2 for p in active_projects), launch],
         f"Development ${investment:,.0f}; target above Gen 2 {'yes' if any(p.target_tech_generation > 2 for p in active_projects) else 'no'}; launch requested {'yes' if launch else 'no'}",
         "Development investment > 0; project target > Gen 2; launch requested", "Completed launches; technology gap; new-product sales and contribution"),
    ]
    return [{"Direction": name, "Signals": f"{sum(flags)}/3", "Decision evidence": evidence,
             "Rule": rule, "Outcome to check": outcome} for name, flags, evidence, rule, outcome in checks]
