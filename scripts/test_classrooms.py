"""Isolation and authentication checks using two disposable 20-team classrooms."""
import os
import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from contextlib import closing

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from streamlit.testing.v1 import AppTest
from utils import repository as repo
from utils import classrooms
from utils.database import get_database_path
from utils.security import hash_password
from utils.team_excel_import import create_teams_from_workbook
from utils.demand_protocol import save_outlook, demand_status


def snapshot(path):
    with closing(sqlite3.connect(path)) as connection:
        tables = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'team_archetypes'")]
        return {t: sorted(connection.execute(f'SELECT * FROM {t}').fetchall(), key=repr) for t in tables}


class ClassroomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name) / 'original.db'
        cls.env = patch.dict(os.environ, {'SIMULATOR_DB_PATH':str(cls.base), 'SIMULATOR_ENV':'dev',
                                         'SIMULATOR_ENABLE_DEMO_ACCOUNTS':'false'})
        cls.env.start()
        repo.create_user('admin', hash_password('IsolationAdmin123!'), 'admin', None, True)
        cls.second_id = classrooms.create_classroom('Class 2', 'admin2', 'admin')
        cls.second = cls.base.parent / 'classrooms' / (cls.second_id + '.db')
        for path in (cls.base, cls.second):
            with classrooms.database_scope(path):
                create_teams_from_workbook([dict(row=i+2, team_name=f'Team {i+1:02}', username=f'team{i+1:02}',
                                                password='StudentPass123!') for i in range(20)])
        cls.original = snapshot(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.tmp.cleanup()

    def app(self, script, selected, user=None, pinned=None):
        app = AppTest.from_string(script, default_timeout=60)
        app.session_state[classrooms.ACTIVE_CLASSROOM_KEY] = selected
        if user:
            app.session_state['authenticated_username'] = user
            app.session_state[classrooms.AUTH_CLASSROOM_KEY] = pinned or selected
        with patch('streamlit.page_link'):
            app.run()
        self.assertFalse(app.exception, str(app.exception))
        return app

    def test_01_twenty_teams_and_actual_round_are_separate(self):
        for path in (self.base, self.second):
            with classrooms.database_scope(path):
                self.assertEqual(len(repo.load_users(role='team_leader')), 20)
                self.assertEqual(len(repo.load_product_lines()), 80)
        with classrooms.database_scope(self.second):
            report = replace(repo.load_market_report(), total_demand=5000)
            repo.save_market_report(report)
            save_outlook(1,4500,5500)
            repo.set_round_submissions_open(1,True)
            repo.set_round_submissions_open(1,False)
        app = AppTest.from_file(str(ROOT / 'pages/3_Instructor_Panel.py'), default_timeout=90)
        app.session_state[classrooms.ACTIVE_CLASSROOM_KEY] = self.second_id
        app.session_state[classrooms.AUTH_CLASSROOM_KEY] = self.second_id
        app.session_state['authenticated_username'] = 'admin2'
        with patch('streamlit.page_link'):
            app.run()
            self.assertFalse(app.exception, str(app.exception))
            app.button(key='instructor_run_round').click().run()
        self.assertFalse(app.exception, str(app.exception))
        with classrooms.database_scope(self.second):
            self.assertEqual(repo.load_market_report().round_number, 2)
            self.assertEqual(len(repo.load_round_results(round_number=1)), 20)
        self.assertEqual(snapshot(self.base), self.original)

    def test_02_session_pinning_and_legacy_login(self):
        script = 'import streamlit as st\nfrom utils.auth import get_current_user\nfrom utils.classrooms import classroom_name\nst.write(get_current_user().username)\nst.write(classroom_name())'
        app = self.app(script, self.second_id, user='admin', pinned='default')
        self.assertEqual([item.value for item in app.markdown], ['admin','Class 1'])
        legacy = AppTest.from_string(script)
        legacy.session_state['authenticated_username'] = 'admin'
        legacy.run()
        self.assertFalse(legacy.exception)
        self.assertEqual(legacy.markdown[1].value, 'Class 1')

    def test_03_wrong_class_admin_cannot_log_in(self):
        script = "import streamlit as st\nfrom utils.auth import login_user\nst.write(login_user('admin', 'IsolationAdmin123!')[0])"
        app = self.app(script, self.second_id)
        self.assertIn('False', app.markdown[0].value)
        app = self.app(script.replace("'admin'", "'admin2'"), self.second_id)
        self.assertIn('True', app.markdown[0].value)
        self.assertEqual(app.session_state[classrooms.AUTH_CLASSROOM_KEY], self.second_id)

    def test_04_switch_clears_auth_and_drafts(self):
        script = f'''import streamlit as st
from utils.classrooms import select_classroom
st.session_state['old_product_draft'] = 'private'
select_classroom({self.second_id!r})
st.write('authenticated_username' in st.session_state)
st.write('old_product_draft' in st.session_state)
'''
        app = self.app(script, 'default', user='admin')
        self.assertTrue(all('False' in item.value for item in app.markdown))

    def test_05_concurrent_scopes_do_not_share_market(self):
        def write(path, low):
            with classrooms.database_scope(path):
                save_outlook(9,low,low+100)
                return str(get_database_path()), demand_status(9)['outlook_low']
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(write,self.base,100)
            b = pool.submit(write,self.second,900)
            self.assertEqual(a.result(),(str(self.base),100))
            self.assertEqual(b.result(),(str(self.second),900))

    def test_06_reset_and_team_removal_do_not_cross_classes(self):
        before = snapshot(self.base)
        with classrooms.database_scope(self.second):
            repo.factory_reset_game_data()
            repo.remove_teams_data(['Team 01'],deactivate_team_leaders=True,delete_team_leader_accounts=False)
            self.assertEqual(repo.load_market_report().round_number,1)
            self.assertFalse(repo.load_round_results())
        self.assertEqual(snapshot(self.base),before)

    def test_07_unknown_class_fails_closed(self):
        with patch('utils.classrooms.active_classroom_id',return_value='../../other'):
            with self.assertRaises(ValueError):
                get_database_path()

    def test_08_duplicate_class_name_is_rejected(self):
        with self.assertRaises(ValueError):
            classrooms.create_classroom('Class 2','another_admin','admin')
        self.assertEqual(len(classrooms.list_classrooms()),2)


if __name__ == '__main__':
    unittest.main()
