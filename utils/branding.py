"""Shared app branding constants."""

from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

APP_NAME = "Kiki Pickleball Business Simulation"
APP_TAGLINE = (
    "A classroom competition for OM, SCM, product portfolio, forecasting, "
    "innovation, and cash-control decisions."
)
MASCOT_NAME = "Kiki"
MASCOT_IMAGE_PATH = ROOT_DIR / "assets" / "kiki_mascot.png"

