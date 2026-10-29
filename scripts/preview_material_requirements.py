"""Start a fresh loopback-only materials lab, never an existing classroom DB."""

from datetime import datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / '.preview' / ('materials_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
LAB.mkdir(parents=True, exist_ok=False)
os.environ['SIMULATOR_DB_PATH'] = str(LAB / 'lab.db')
os.environ['SIMULATOR_ENV'] = 'dev'
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'
sys.path.insert(0, str(ROOT))

from utils.repository import create_user
from utils.security import hash_password
from utils.demand_protocol import save_outlook
from utils.classrooms import _registry

password_hash = hash_password('PreviewOnly123!')
create_user('materials_admin', password_hash, 'admin', None, True)
for i in range(1, 3):
    create_user(f'materials_team{i}', password_hash, 'team_leader', f'Material Lab Team {i}', True)
with _registry() as connection:
    connection.execute("UPDATE classrooms SET name='Local Materials Lab' WHERE classroom_id='default'")
save_outlook(1, 400, 560)
# Leave the round unopened so the instructor settings can be inspected safely.
port = 8540
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
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )
metadata = dict(url=f'http://127.0.0.1:{port}', pid=process.pid, database=str(LAB / 'lab.db'))
(LAB / 'server.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print(json.dumps(metadata))
