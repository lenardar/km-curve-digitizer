"""Test package bootstrap for the skill's internal scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "km-curve-digitizer" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))
