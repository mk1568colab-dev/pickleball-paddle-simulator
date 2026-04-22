"""JSON storage helpers for local simulator persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path, default: Any) -> Any:
    """Read JSON from disk and fall back to a default value when missing."""
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, payload: Any) -> None:
    """Write JSON data to disk with readable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def reset_json(path: Path, payload: Any) -> None:
    """Overwrite a JSON file with a fresh payload."""
    write_json(path, payload)
