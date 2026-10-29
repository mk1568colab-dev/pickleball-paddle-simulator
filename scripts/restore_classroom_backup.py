"""Recover a validated classroom ZIP to a NEW standalone database only."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.game_exports import restore_backup_to_new_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("new_database", type=Path)
    args = parser.parse_args()
    try:
        metadata = restore_backup_to_new_file(args.backup.read_bytes(), args.new_database)
    except Exception as error:
        parser.exit(1, f"Recovery stopped: {error}\n")
    print(f"Recovered {metadata['classroom_name']} as a new standalone copy: {args.new_database.resolve()}")
    print("No existing classroom was changed. Use the ZIP's RESTORE_README.txt to inspect this copy locally.")


if __name__ == "__main__":
    main()
