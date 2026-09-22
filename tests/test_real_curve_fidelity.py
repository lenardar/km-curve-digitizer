"""Visual-fidelity regressions derived from printed KM landmark rates."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np

import pykmextract as pkm
from tests import ROOT


class RealCurveFidelityTests(unittest.TestCase):
    def test_study04_pfs_curves_match_printed_landmark_rates(self):
        prior = json.loads(
            (Path(ROOT) / "runs" / "study04" / "pfs" / "result.json").read_text(
                encoding="utf-8"
            )
        )
        result = pkm.extract(
            str(Path(ROOT) / "images" / "study04_pfs.png"),
            semantic=prior["semantic"],
            axis_bounds=prior["axis_bounds"],
            axis_anchors=prior["axis_anchors"],
            min_curve_pixels=30,
        )

        expected = {
            "Nivolumab": {6.0: 0.157, 12.0: 0.105, 18.0: 0.058},
            "Bevacizumab": {6.0: 0.296, 12.0: 0.174, 18.0: 0.089},
        }
        for curve in result.curves:
            for time, landmark in expected[curve.name].items():
                index = np.searchsorted(curve.time, time, side="right") - 1
                self.assertLess(abs(curve.survival[index] - landmark), 0.035)


if __name__ == "__main__":
    unittest.main()
