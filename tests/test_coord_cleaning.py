"""Coordinate cleaning tests for outlier suppression."""

from __future__ import annotations

import unittest

import numpy as np

from km_digitizer.extractor.coord import _suppress_isolated_drop_outliers, clean_curve_points


class CoordCleaningTests(unittest.TestCase):
    def test_suppresses_single_point_drop_that_immediately_rebounds(self):
        survival = np.array([1.0, 0.95, 0.0, 0.94, 0.94], dtype=float)

        repaired = _suppress_isolated_drop_outliers(survival)

        np.testing.assert_allclose(repaired, [1.0, 0.95, 0.95, 0.94, 0.94])

    def test_preserves_real_sustained_drop(self):
        survival = np.array([1.0, 0.95, 0.60, 0.55, 0.55], dtype=float)

        repaired = _suppress_isolated_drop_outliers(survival)

        np.testing.assert_allclose(repaired, survival)

    def test_repairs_spike_even_when_rebound_contains_real_decline(self):
        survival = np.array([1.0, 0.95, 0.30, 0.72, 0.70], dtype=float)

        repaired = _suppress_isolated_drop_outliers(survival)

        np.testing.assert_allclose(repaired, [1.0, 0.95, 0.72, 0.72, 0.70])

    def test_inserted_origin_uses_axis_pixel_not_first_detected_pixel(self):
        x_pixels, y_pixels, time, survival = clean_curve_points(
            np.array([97.0, 98.0]),
            np.array([232.0, 232.0]),
            np.array([1.8, 1.9]),
            np.array([0.4, 0.4]),
            origin_pixel=(76.0, 108.0),
        )

        self.assertEqual((time[0], survival[0]), (0.0, 1.0))
        self.assertEqual((x_pixels[0], y_pixels[0]), (76.0, 108.0))


if __name__ == "__main__":
    unittest.main()
