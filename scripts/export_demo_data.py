"""Fictional two-classroom fixtures, only for a newly created local database."""

from dataclasses import replace
from pathlib import Path


def seed_export_demo(base_path, configure_classroom=None):
    from data.classroom_start import COMMON_PROFILE_NAME
    from engine.simulator import run_round
    from models.schemas import ProductDecision, ProductForecast, TeamDecision
    from utils.classrooms import _registry, create_classroom, database_scope
    from utils.database import get_base_database_path
    from utils.demand_protocol import complete_demand_round, save_outlook
    from utils import repository as repo
    from utils.security import hash_password

    base_path = Path(base_path).resolve()
    if base_path.exists() or base_path != get_base_database_path().resolve():
        raise ValueError("Demo seeding requires a new SIMULATOR_DB_PATH.")
    password_hash = hash_password("PreviewOnly123!")
    repo.create_user("export_admin", password_hash, "admin", None, True)
    with _registry() as connection:
        connection.execute("UPDATE classrooms SET name='022 (Local Demo)' WHERE classroom_id='default'")
    second_id = create_classroom("122 (Local Demo)", "export_admin", "export_admin")
    classes = [dict(id="default", section="022", path=base_path, rounds=3),
               dict(id=second_id, section="122", path=base_path.parent / "classrooms" / f"{second_id}.db", rounds=2)]
    for classroom in classes:
        with database_scope(classroom["path"]):
            if configure_classroom:
                configure_classroom()
            for i in (1, 2):
                repo.create_user(f"demo_{classroom['section']}_{i}", password_hash, "team_leader",
                                 f"Demo {classroom['section']} Team {i}", True)
            for round_number in range(1, classroom["rounds"] + 1):
                market = replace(repo.load_market_report(), total_demand=460 + round_number * 20,
                                 event=f"Fictional Section {classroom['section']}, round {round_number}.")
                repo.save_market_report(market)
                save_outlook(round_number, 400, 600)
                repo.set_round_submissions_open(round_number, True)
                firms, decisions, lines = [], [], []
                for i in (1, 2):
                    team = f"Demo {classroom['section']} Team {i}"
                    firm = TeamDecision.from_dict(dict(team_name=team, archetype=COMMON_PROFILE_NAME,
                        raw_material_order_qty=240, supplier_mix_offshore_pct=30,
                        supplier_mix_balanced_pct=50, supplier_mix_premium_pct=20))
                    firms.append(firm)
                    repo.save_team_decision(firm, round_number=round_number)
                    products = repo.load_product_lines(team)
                    lines.extend(products)
                    product_decisions = [ProductDecision.from_dict(dict(
                        team_name=team, product_id=p.product_id, product_name=p.product_name,
                        slot_name=p.slot_name, is_active=p.is_active, target_segment=p.target_segment,
                        selling_price_per_unit=185 if p.target_segment == 'premium' else 80,
                        planned_production_units=(100 + round_number * 5) if p.is_active else 0,
                        forecast_units=120 if p.is_active else 0, qc_budget_per_unit=3)) for p in products]
                    decisions.extend(product_decisions)
                    repo.save_product_decisions(product_decisions, round_number)
                    repo.save_product_forecasts([ProductForecast.from_dict(dict(p.to_dict(), round_number=round_number))
                                                 for p in product_decisions])
                repo.set_round_submissions_open(round_number, False)
                result = run_round(market, firms, lines, decisions, [], repo.load_team_states())
                for save, values in zip((repo.save_round_results, repo.save_product_round_results,
                                        repo.save_team_states, repo.save_product_lines,
                                        repo.save_product_development_projects, repo.save_forecast_accuracy_results), result):
                    save(values)
                complete_demand_round(round_number)
                repo.advance_market_report_to_next_round(market)
    return classes
