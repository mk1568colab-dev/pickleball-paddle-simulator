"""Explicit, guarded classroom reputation update. Preview unless --apply is given."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.database import get_base_database_path
from utils.reputation_recalculation import recalculate_reputation, resolve_classroom


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--classroom', action='append', required=True,
                        help='ClassroomID:GameID:LastCompletedRound:AdminUsername (repeat for each classroom)')
    parser.add_argument('--base-db', type=Path, default=None)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    targets = []
    for value in args.classroom:
        classroom, game, completed, admin = value.split(':')
        path = resolve_classroom(args.base_db or get_base_database_path(), classroom)
        if any(path == target[0] for target in targets):
            raise ValueError('Duplicate classroom target.')
        targets.append((path, dict(game_id=game, completed_round=int(completed), admin_username=admin)))
    # All targets must pass read-only preflight before either classroom is changed.
    for path, options in targets:
        print(json.dumps(recalculate_reputation(path, **options)))
    if args.apply:
        for path, options in targets:
            print(json.dumps(recalculate_reputation(path, apply=True, **options)))


if __name__ == '__main__':
    main()
