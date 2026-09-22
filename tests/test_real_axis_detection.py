"""Regression tests for axis detection on a real KM panel."""

from __future__ import annotations

import unittest
from pathlib import Path

from tests import ROOT

from pykmextract.extractor.coord import detect_axis_bounds


class RealAxisDetectionTests(unittest.TestCase):
    def test_detect_axis_bounds_on_study01_os(self):
        image_path = Path(ROOT) / "images" / "study01_os.png"
        bounds = detect_axis_bounds(str(image_path))

        self.assertLessEqual(abs(bounds.left - 123), 2)
        self.assertLessEqual(abs(bounds.right - 801), 2)
        self.assertLessEqual(abs(bounds.top - 35), 4)
        self.assertLessEqual(abs(bounds.bottom - 286), 2)

    def test_detect_axis_bounds_on_study04_os(self):
        image_path = Path(ROOT) / "images" / "study04_os.png"
        bounds = detect_axis_bounds(str(image_path))

        self.assertLessEqual(abs(bounds.left - 75), 2)
        self.assertLessEqual(abs(bounds.right - 391), 2)
        self.assertLessEqual(abs(bounds.top - 108), 2)
        self.assertLessEqual(abs(bounds.bottom - 315), 2)


if __name__ == "__main__":
    unittest.main()
