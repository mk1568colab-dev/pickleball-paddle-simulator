"""Fresh fictional local game with opt-in shipping. Never reuse classroom data."""

from datetime import datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / '.preview' / ('probabilistic_sourcing_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
LAB.mkdir(parents=True, exist_ok=False)
os.environ['SIMULATOR_DB_PATH'] = str(LAB / 'demo.db')
os.environ['SIMULATOR_ENV'] = 'dev'
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'
sys.path.insert(0, str(ROOT))

from scripts.export_demo_data import seed_export_demo
from utils.sourcing_rules import initialize_delivery_policy
from utils.classrooms import database_scope
from utils.database import get_connection
from utils.demand_protocol import save_outlook
from utils import repository as repo


def configure():
    initialize_delivery_policy()
    with get_connection() as connection:
        connection.execute('INSERT OR REPLACE INTO material_rules VALUES (1,.7,1,1.2)')


classes = seed_export_demo(LAB / 'demo.db', configure_classroom=configure)
for classroom in classes:
    with database_scope(classroom['path']):
        current = repo.load_market_report()
        save_outlook(current.round_number, 400, 600)
        repo.set_round_submissions_open(current.round_number, True)

port = 8550
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
