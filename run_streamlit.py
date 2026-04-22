"""Host-friendly entrypoint for running the Streamlit app."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    """Launch Streamlit using environment-aware host and port settings."""
    port = os.getenv("PORT", "8501")
    address = os.getenv("STREAMLIT_SERVER_ADDRESS", "0.0.0.0")

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.headless=true",
        f"--server.port={port}",
        f"--server.address={address}",
        "--browser.gatherUsageStats=false",
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
