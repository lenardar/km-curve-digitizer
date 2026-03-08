"""Axis recalibration tests."""

from __future__ import annotations

import unittest

import numpy as np

from tests import ROOT, SRC

from pykmextract.contracts import AxisBounds
from pykmextract.extractor.coord import recalibrate_axis_bounds_from_curves


class AxisRecalibrationTests(unittest.TestCase):
    def test_recalibrate_left_and_top_when_curve_starts_far_inside(self):
        bounds = AxisBounds(left=70, right=780, top=4, bottom=240)
        curve_sets = [
            (np.array([132.0, 133.0, 134.0]), np.array([42.0, 42.0, 43.0])),
            (np.array([130.0, 131.0, 132.0]), np.array([41.0, 41.5, 42.0])),
        ]

        refined = recalibrate_axis_bounds_from_curves(bounds, curve_sets)
        self.assertEqual(refined.left, 130)
        self.assertEqual(refined.top, 41)
        self.assertEqual(refined.right, 780)
        self.assertEqual(refined.bottom, 240)

    def test_no_recalibration_for_small_offset(self):
        bounds = AxisBounds(left=70, right=780, top=40, bottom=240)
        curve_sets = [
            (np.array([75.0, 76.0, 77.0]), np.array([44.0, 45.0, 46.0])),
        ]

        refined = recalibrate_axis_bounds_from_curves(bounds, curve_sets)
        self.assertEqual(refined, bounds)


if __name__ == "__main__":
    unittest.main()
