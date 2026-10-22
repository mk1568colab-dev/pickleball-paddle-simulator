import os
import sys
import tempfile
import unittest
import sqlite3
from pathlib import Path
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
temp = tempfile.TemporaryDirectory()
os.environ['SIMULATOR_DB_PATH'] = str(Path(temp.name) / 'test.db')
os.environ['SIMULATOR_ENABLE_DEMO_ACCOUNTS'] = 'false'
from utils.repository import (load_market_report, save_market_report, load_round_status,
    set_round_submissions_open, advance_market_report_to_next_round, factory_reset_game_data)
from utils.demand_protocol import *


class DemandTests(unittest.TestCase):
    def setUp(self):
        factory_reset_game_data()

    def test_closed_until_outlook_saved(self):
        self.assertFalse(load_round_status(1).submissions_open)
        with self.assertRaises(ValueError):
            set_round_submissions_open(1, True)
        with self.assertRaises(ValueError):
            save_outlook(1, 1200, 1200)

    def test_lock_close_reopen_reveal_and_next_round(self):
        report = replace(load_market_report(), total_demand=1187)
        save_market_report(report)
        save_outlook(1, 1000, 1400)
        set_round_submissions_open(1, True)
        self.assertEqual(demand_status(1)['actual_demand'], 1187)
        self.assertEqual(planning_market_report(report).total_demand, 1200)
        self.assertNotIn('total_demand', public_market_row(report))
        self.assertNotIn('actual_total_demand', public_market_row(report))
        set_round_submissions_open(1, False)
        with self.assertRaises(sqlite3.IntegrityError):
            save_market_report(replace(report, total_demand=9999))
        with self.assertRaises(ValueError):
            save_outlook(1, 500, 600)
        set_round_submissions_open(1, True)
        self.assertEqual(committed_report(report).total_demand, 1187)
        set_round_submissions_open(1, False)
        complete_demand_round(1)
        self.assertEqual(public_market_row(report)['actual_total_demand'], 1187)
        with self.assertRaises(ValueError):
            set_round_submissions_open(1, True)
        with self.assertRaises(ValueError):
            committed_report(report)
        next_report = advance_market_report_to_next_round(report)
        self.assertFalse(load_round_status(2).submissions_open)
        self.assertNotIn('actual_total_demand', public_market_row(next_report))

    def test_preview_independent_of_private_demand(self):
        save_outlook(1, 900, 1500)
        report = load_market_report()
        self.assertEqual(planning_market_report(replace(report, total_demand=1)),
                         planning_market_report(replace(report, total_demand=999999)))


if __name__ == '__main__':
    unittest.main()
