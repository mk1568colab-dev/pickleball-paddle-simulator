"""New fictional classroom lab for submitted revisions and automatic carry-forward."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / '.preview' / ('decision_audit_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
LAB.mkdir(parents=True, exist_ok=False)
os.environ['SIMULATOR_DB_PATH'] = str(LAB / 'demo.db')
os.environ['SIMULATOR_ENV'] = 'dev'
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'
sys.path.insert(0, str(ROOT))

from scripts.export_demo_data import seed_export_demo
from engine.simulator import run_round
from utils import repository as repo
from utils.classrooms import AUTH_CLASSROOM_KEY, database_scope
from utils.decision_audit import save_audited_submission
from utils.demand_protocol import complete_demand_round, save_outlook
from utils.submission_fallback import complete_round_inputs, save_fallback_decisions


@contextmanager
def virtual_actor(classroom, username):
    state = {'authenticated_username': username, AUTH_CLASSROOM_KEY: classroom['id']}
    with patch('utils.classrooms._session', return_value=state), patch('utils.decision_audit._session', return_value=state):
        yield


classes = seed_export_demo(LAB / 'demo.db')
for classroom in classes:
    with database_scope(classroom['path']):
        current = repo.load_market_report()
        r = current.round_number
        save_outlook(r, 400, 600)
        repo.set_round_submissions_open(r, True)
        team = f"Demo {classroom['section']} Team 1"
        username = f"demo_{classroom['section']}_1"
        user = repo.get_user_by_username(username)
        firm = repo.load_team_decision(r - 1, team)
        products = repo.load_product_decisions(r - 1, team)
        projects = repo.load_product_development_projects(team)
        for price, investment in ((150, 500), (180, 800), (170, 650)):
            selected = [replace(p, selling_price_per_unit=price) if p.slot_name == 'A' else p for p in products]
            pipeline = [replace(p, project_name='Next Premium Paddle', investment_this_round=investment,
                                testing_intensity=.25, target_segment='premium', target_tech_generation=3,
                                planned_launch_round=r+2, created_round=r) if p.project_slot_name == 'P1' else p for p in projects]
            with virtual_actor(classroom, username):
                save_audited_submission(firm, selected, pipeline, repo.load_product_lines(team), r, user.user_id)
        with virtual_actor(classroom, 'export_admin'):
            repo.set_round_submissions_open(r, False)
            effective = complete_round_inputs(r, repo.load_team_decisions(r), repo.load_product_decisions(r),
                                              repo.load_product_development_projects(), repo.load_product_lines(), repo.load_team_states())
            firms, products, projects, lines, missing = effective
            output = run_round(current, firms, lines, products, projects, repo.load_team_states())
            save_fallback_decisions(r, firms, products, missing, projects)
            for save, values in zip((repo.save_round_results, repo.save_product_round_results, repo.save_team_states,
                                    repo.save_product_lines, repo.save_product_development_projects,
                                    repo.save_forecast_accuracy_results), output):
                save(values)
            complete_demand_round(r)
            next_report = repo.advance_market_report_to_next_round(current)
            save_outlook(next_report.round_number, 400, 600)
            repo.set_round_submissions_open(next_report.round_number, True)

port = 8542
while True:
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', port)) != 0:
            break
    port += 1
with (LAB / 'server.log').open('a', encoding='utf-8') as log:
    process = subprocess.Popen(
        [sys.executable, '-m', 'streamlit', 'run', 'app.py', '--server.address=127.0.0.1',
         f'--server.port={port}', '--server.headless=true', '--browser.gatherUsageStats=false'],
        cwd=ROOT, env=os.environ.copy(), stdout=log, stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
metadata = dict(url=f'http://127.0.0.1:{port}', pid=process.pid, database=str(LAB / 'demo.db'))
(LAB / 'server.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print(json.dumps(metadata))
