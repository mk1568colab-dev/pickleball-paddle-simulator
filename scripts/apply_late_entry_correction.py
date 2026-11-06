"""Server-side instructor repair. Preview by default; --apply is explicit."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.database import get_base_database_path
from utils.reputation_adjustments import adjust_late_entry_reputation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, help='Explicit classroom DB; default is the original classroom.')
    parser.add_argument('--team', required=True)
    parser.add_argument('--game-id', required=True)
    parser.add_argument('--expected-round', type=int, required=True)
    parser.add_argument('--expected-score', type=float, required=True)
    parser.add_argument('--points', type=float, default=10)
    parser.add_argument('--admin-username', default='admin')
    parser.add_argument('--apply', action='store_true')
    args = vars(parser.parse_args())
    path = args.pop('db') or get_base_database_path()
    try:
        print(json.dumps(adjust_late_entry_reputation(path, **args), indent=2))
    except (ValueError, OSError, sqlite3.Error) as error:
        raise SystemExit(str(error)) from error


if __name__ == '__main__':
    main()
