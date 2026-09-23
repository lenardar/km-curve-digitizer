#!/usr/bin/env python3
"""Stable skill entry point for model-directed curve editing."""

import os
from pathlib import Path
import tempfile

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "km-curve-digitizer-matplotlib"),
)

from km_digitizer.refine_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
