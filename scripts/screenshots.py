"""Capture the README screenshots: runs the app with the simulated hand and the demo tracks.

`python scripts/screenshots.py` -> docs/images/*.png (no camera needed).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"

if __name__ == "__main__":
    cmd = [sys.executable, "-m", "gesture_player", "--demo", "--simulate", "--volume", "40", "--screenshots", str(OUT)]
    raise SystemExit(subprocess.call(cmd, cwd=Path(__file__).resolve().parents[1]))
