#!/usr/bin/env python3
"""Stable skill entry point for grouped Kaplan-Meier extraction."""

import os
from pathlib import Path
import tempfile

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "km-curve-digitizer-matplotlib"),
)

from pykmextract.batch_run import main


if __name__ == "__main__":
    raise SystemExit(main())
