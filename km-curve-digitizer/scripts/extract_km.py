#!/usr/bin/env python3
"""Stable skill entry point for a single Kaplan-Meier figure."""

import os
from pathlib import Path
import tempfile

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "km-curve-digitizer-matplotlib"),
)

from km_digitizer.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
