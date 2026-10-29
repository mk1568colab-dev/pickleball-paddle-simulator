"""Isolated import tests; never open the classroom database."""
import os
import sys
import tempfile
import unittest
from io import BytesIO
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import team_excel_import as importer
from utils.bootstrap import ensure_app_storage
from utils.database import get_connection
from utils.repository import load_users, load_team_states, load_product_lines
from utils.security import verify_password, validate_password_strength


class TeamImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"SIMULATOR_DB_PATH": str(Path(self.directory.name) / "test.db"),
                                                  "SIMULATOR_ENV": "dev"})
        self.environment.start()
        ensure_app_storage()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def rows(self, count=1):
        return [dict(team_name=f"Import Team {i}", username=f"import_{i:03}",
                     password=f"ExactPass{i:03}!", row=i+2) for i in range(count)]

    def test_template_and_40_team_import(self):
        rows = importer.read_team_workbook((ROOT / "data/templates/Kiki_Team_Import_Template.xlsx").read_bytes())
        # Blank passwords in the distributed template must not produce accounts.
        self.assertEqual(len(rows), 40)
        self.assertTrue(importer.validate_team_rows(rows))
        records = self.rows(40)
        self.assertEqual(importer.create_teams_from_workbook(records), 40)
        users = {u.username: u for u in load_users()}
        for row in records:
            self.assertTrue(verify_password(row['password'], users[row['username']].password_hash))
        state = load_team_states(team_name=records[0]['team_name'])[0]
        self.assertEqual((state.cash_balance, state.raw_material_inventory, state.capacity_units), (50000,300,300))
        products = load_product_lines(team_name=records[0]['team_name'])
        self.assertEqual(len(products), 4)
        self.assertEqual(sum(p.is_active for p in products), 2)

    def test_existing_data_and_repeat_upload_are_preserved(self):
        importer.create_teams_from_workbook(self.rows())
        with get_connection() as c:
            before = {t: [tuple(r) for r in c.execute(f'SELECT * FROM {t}')] for t in
                      ('users','team_states','product_lines','product_development_projects')}
        with self.assertRaises(ValueError):
            importer.create_teams_from_workbook(self.rows())
        with get_connection() as c:
            self.assertEqual(before, {t:[tuple(r) for r in c.execute(f'SELECT * FROM {t}')] for t in before})

    def test_duplicates_and_internal_identifier_collision(self):
        records = self.rows(2)
        records[1]['username'] = records[0]['username'].upper()
        self.assertTrue(importer.validate_team_rows(records))
        records = self.rows(2)
        records[0]['team_name'], records[1]['team_name'] = 'New Team', 'New-Team'
        self.assertTrue(importer.validate_team_rows(records))

    def test_all_or_nothing_on_database_failure(self):
        original = importer._insert_new
        def fail(connection, table, payload):
            if table == 'product_lines':
                raise RuntimeError('injected failure')
            original(connection, table, payload)
        with patch.object(importer, '_insert_new', side_effect=fail):
            with self.assertRaises(RuntimeError):
                importer.create_teams_from_workbook(self.rows())
        self.assertFalse(any(u.username == 'import_000' for u in load_users()))
        self.assertFalse(load_team_states(team_name='Import Team 0'))

    def test_password_is_not_trimmed_or_replaced(self):
        records = self.rows()
        records[0]['password'] = ' ExactPass123! '
        self.assertTrue(importer.validate_team_rows(records))
        with self.assertRaises(ValueError):
            importer.create_teams_from_workbook(records)

    def test_bad_file(self):
        with self.assertRaises(ValueError):
            importer.read_team_workbook(b'not excel')

    def test_first_name_passwords_require_explicit_opt_in(self):
        records = self.rows()
        records[0]['password'] = 'Amy'
        self.assertTrue(importer.validate_team_rows(records))
        with self.assertRaises(ValueError):
            importer.create_teams_from_workbook(records)
        self.assertFalse(importer.validate_team_rows(records, allow_classroom_passwords=True))
        self.assertEqual(importer.create_teams_from_workbook(records, allow_classroom_passwords=True), 1)
        account = next(u for u in load_users() if u.username == records[0]['username'])
        self.assertEqual(account.role, 'team_leader')
        self.assertTrue(verify_password('Amy', account.password_hash))
        self.assertFalse(verify_password('amy', account.password_hash))
        self.assertTrue(validate_password_strength('Amy'))

    def test_classroom_password_mode_keeps_input_safety_and_duplicates(self):
        for password in ('', ' Amy', 'Amy ', 'Amy\n', 'x' * 129):
            with self.subTest(password_length=len(password)):
                records = self.rows()
                records[0]['password'] = password
                self.assertTrue(importer.validate_team_rows(records, allow_classroom_passwords=True))
                with self.assertRaises(ValueError):
                    importer.create_teams_from_workbook(records, allow_classroom_passwords=True)
        records = self.rows(2)
        records[0]['password'] = records[1]['password'] = 'Amy'
        records[1]['username'] = records[0]['username']
        self.assertTrue(importer.validate_team_rows(records, allow_classroom_passwords=True))

    def test_workbook_text_leading_zeros_and_formula_rejection(self):
        source = (ROOT / 'data/templates/Kiki_Team_Import_Template.xlsx').read_bytes()
        def changed_workbook(formula=False):
            output = BytesIO()
            ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
            with zipfile.ZipFile(BytesIO(source)) as original, zipfile.ZipFile(output, 'w') as target:
                for item in original.infolist():
                    data = original.read(item.filename)
                    if item.filename == 'xl/worksheets/sheet1.xml':
                        root = ET.fromstring(data)
                        for row in root.findall(f'{ns}sheetData/{ns}row'):
                            number = int(row.attrib['r'])
                            if number == 1 or number > 41:
                                continue
                            for c in list(row):
                                if c.attrib['r'].startswith('C'):
                                    row.remove(c)
                            cell = ET.SubElement(row, ns+'c', r=f'C{number}', t='inlineStr')
                            ET.SubElement(ET.SubElement(cell, ns+'is'), ns+'t').text = '00ExactPass123!'
                            if formula and number == 2:
                                ET.SubElement(cell, ns+'f').text = '1+1'
                        data = ET.tostring(root)
                    target.writestr(item, data)
            return output.getvalue()
        rows = importer.read_team_workbook(changed_workbook())
        self.assertEqual(rows[0]['password'], '00ExactPass123!')
        self.assertFalse(importer.validate_team_rows(rows))
        with self.assertRaises(ValueError):
            importer.read_team_workbook(changed_workbook(formula=True))

    def test_admin_page_renders(self):
        from streamlit.testing.v1 import AppTest
        from utils.repository import create_user
        create_user('import_admin', importer.hash_password('TestAdmin123!'), 'admin', None, True)
        app = AppTest.from_file(str(ROOT / 'pages/5_Admin_User_Management.py'))
        app.session_state['authenticated_username'] = 'import_admin'
        with patch('utils.auth.render_user_sidebar'):
            app.run(timeout=30)
        self.assertFalse(app.exception)
        self.assertIn('Import Excel Teams', [tab.label for tab in app.tabs])

    def test_admin_checkbox_passes_classroom_mode_to_creation(self):
        from streamlit.testing.v1 import AppTest
        from utils.repository import create_user
        create_user('import_admin', importer.hash_password('TestAdmin123!'), 'admin', None, True)
        records = self.rows()
        records[0]['password'] = 'Amy'
        app = AppTest.from_file(str(ROOT / 'pages/5_Admin_User_Management.py'))
        app.session_state['authenticated_username'] = 'import_admin'
        with patch('utils.auth.render_user_sidebar'), \
                patch('streamlit.file_uploader', return_value=BytesIO(b'synthetic upload')), \
                patch('utils.team_excel_import.read_team_workbook', return_value=records):
            app.run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(any('No teams created' in e.value for e in app.error))
            option = next(c for c in app.checkbox if c.label.startswith('Allow simple student'))
            self.assertFalse(option.value)
            option.check().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            next(c for c in app.checkbox if c.label == 'Create 1 new teams and their accounts').check().run(timeout=30)
            next(b for b in app.button if b.label == 'Create Teams from Excel').click().run(timeout=30)
            self.assertFalse(app.exception)
        account = next(u for u in load_users() if u.username == records[0]['username'])
        self.assertTrue(verify_password('Amy', account.password_hash))


if __name__ == '__main__':
    unittest.main()
