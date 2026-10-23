"""Portable student overview without internal model formulas."""

from pathlib import Path


def big_picture_download() -> bytes:
    return (Path(__file__).resolve().parents[1] / "documentation" / "Kiki_Game_Big_Picture.html").read_bytes()
