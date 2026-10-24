"""Resolve missing submissions at run time without impersonating a student."""
from dataclasses import replace

from data.classroom_start import COMMON_PROFILE_NAME
from models.schemas import ProductDecision, ProductForecast, TeamDecision
from utils import repository as repo


def complete_round_inputs(round_number, firms, products, projects, lines, states):
    """Return effective inputs plus names whose saved plan was carried forward."""
    firms, products, lines = list(firms), list(products), list(lines)
    submitted = {f.team_name.casefold() for f in firms}
    profiles = {p.name: p for p in repo.load_team_archetypes()}
    state_by_team = {s.team_name.casefold(): s for s in states}
    teams = {u.team_name.casefold(): u.team_name for u in
             repo.load_users(role="team_leader", is_active=True) if u.team_name}
    fallback = []
    for key, team in sorted(teams.items()):
        if key in submitted:
            continue
        fallback.append(team)
        previous = None
        prior_products = []
        prior_round = None
        for r in range(round_number - 1, 0, -1):
            previous = repo.load_team_decision(r, team)
            if previous is not None:
                prior_products = repo.load_product_decisions(r, team)
                prior_round = r
                break
        state = state_by_team.get(key)
        profile = profiles[state.archetype if state else
                           previous.archetype if previous else COMMON_PROFILE_NAME]
        if previous is None:
            previous = TeamDecision.from_dict(dict(
                team_name=team, archetype=profile.name,
                **{name: getattr(profile, "suggested_" + name) for name in (
                    "overtime_capacity_units", "capacity_expansion_units",
                    "raw_material_order_qty", "supplier_mix_offshore_pct",
                    "supplier_mix_balanced_pct", "supplier_mix_premium_pct",
                    "expedited_order_share_pct", "max_backorder_units")}))
        firms.append(replace(previous, team_name=team))
        team_lines = repo.ensure_product_lines_for_team(team, profile.name)
        lines = [p for p in lines if p.team_name.casefold() != key] + team_lines
        products = [p for p in products if p.team_name.casefold() != key]
        prior = {p.slot_name: p for p in prior_products}
        templates = {p.slot_name: p for p in profile.suggested_product_templates}
        results = {p.slot_name: p for p in repo.load_product_round_results(
            round_number=prior_round, team_name=team)} if prior_round else {}
        for line in team_lines:
            template = templates.get(line.slot_name)
            old = prior.get(line.slot_name)
            active = line.is_active and not line.retirement_flag
            payload = old.to_dict() if old else dict(
                selling_price_per_unit=template.suggested_selling_price_per_unit if template else 130,
                planned_production_units=template.suggested_planned_production_units if template else 0,
                forecast_units=template.suggested_planned_production_units if template else 0,
                qc_budget_per_unit=template.suggested_qc_budget_per_unit if template else 3,
                target_finished_goods_inventory=template.suggested_target_finished_goods_inventory if template else 0)
            # A launch can replace the slot after its old decision was saved.
            result = results.get(line.slot_name)
            if active and result and result.launched_this_round:
                for field in ("selling_price_per_unit", "forecast_units", "planned_production_units"):
                    payload[field] = getattr(result, field)
            if not active:
                for field in ("selling_price_per_unit", "forecast_units", "planned_production_units",
                              "qc_budget_per_unit", "target_finished_goods_inventory"):
                    payload[field] = 0
            payload.update(product_id=line.product_id, team_name=team, slot_name=line.slot_name,
                           product_name=line.product_name, target_segment=line.target_segment,
                           is_active=active, retire_flag=False)
            products.append(ProductDecision.from_dict(payload))
    missing = {name.casefold() for name in fallback}
    projects = [replace(p, investment_this_round=0, testing_intensity=0,
                        launch_now=False, cancel_now=False)
                if p.team_name.casefold() in missing else p for p in projects]
    return firms, products, projects, lines, fallback


def save_fallback_decisions(round_number, firms, products, fallback):
    """Keep the effective plan for next round; no student submitter is recorded."""
    missing = {name.casefold() for name in fallback}
    for firm in firms:
        if firm.team_name.casefold() in missing:
            repo.save_team_decision(firm, round_number, submitted_by_user_id=None)
    selected = [p for p in products if p.team_name.casefold() in missing]
    repo.save_product_decisions(selected, round_number)
    repo.save_product_forecasts([ProductForecast.from_dict(
        dict(p.to_dict(), round_number=round_number)) for p in selected])
