"""Coordinate cleaning tests for outlier suppression."""

from __future__ import annotations

import unittest

import numpy as np

from pykmextract.extractor.coord import _suppress_isolated_drop_outliers


class CoordCleaningTests(unittest.TestCase):
    def test_suppresses_single_point_drop_that_immediately_rebounds(self):
        survival = np.array([1.0, 0.95, 0.0, 0.94, 0.94], dtype=float)

        repaired = _suppress_isolated_drop_outliers(survival)

        np.testing.assert_allclose(repaired, [1.0, 0.95, 0.95, 0.94, 0.94])

    def test_preserves_real_sustained_drop(self):
        survival = np.array([1.0, 0.95, 0.60, 0.55, 0.55], dtype=float)

        repaired = _suppress_isolated_drop_outliers(survival)

        np.testing.assert_allclose(repaired, survival)


if __name__ == "__main__":
    unittest.main()
