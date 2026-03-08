"""Pixel edge trimming tests."""

from __future__ import annotations

import unittest

import numpy as np

from pykmextract.extractor.pixel import trim_curve_edge_outliers


class PixelEdgeTrimTests(unittest.TestCase):
    def test_trim_unstable_prefix(self):
        x = np.arange(20, dtype=float)
        y = np.array(
            [12, 73, 135, 196, 197, 182, 176, 197, 41, 41, 41.2, 41.5, 41.8, 42.0, 42.3, 42.5, 42.8, 43.0, 43.2, 43.5],
            dtype=float,
        )
        x_trimmed, y_trimmed = trim_curve_edge_outliers(x, y)
        self.assertGreaterEqual(x_trimmed[0], 8)
        self.assertLess(max(y_trimmed[:8]) - min(y_trimmed[:8]), 8.0)

    def test_leave_stable_curve_untouched(self):
        x = np.arange(20, dtype=float)
        y = np.array([41, 41, 41.2, 41.3, 41.5, 41.6, 41.8, 42.0, 42.1, 42.3, 42.4, 42.6, 42.8, 42.9, 43.0, 43.1, 43.3, 43.4, 43.6, 43.8], dtype=float)
        x_trimmed, y_trimmed = trim_curve_edge_outliers(x, y)
        self.assertEqual(len(x_trimmed), len(x))
        self.assertEqual(len(y_trimmed), len(y))


if __name__ == "__main__":
    unittest.main()
