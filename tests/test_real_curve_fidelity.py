"""Visual-fidelity regressions derived from printed KM landmark rates."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np

import pykmextract as pkm
from tests import ROOT


class RealCurveFidelityTests(unittest.TestCase):
    def test_study04_os_grayscale_curves_keep_identity_at_landmarks(self):
        prior = json.loads(
            (Path(ROOT) / "runs" / "study04" / "os" / "result.json").read_text(
                encoding="utf-8"
            )
        )
        result = pkm.extract(
            str(Path(ROOT) / "images" / "study04_os.png"),
            semantic=prior["semantic"],
            axis_bounds=prior["axis_bounds"],
            axis_anchors=prior["axis_anchors"],
            min_curve_pixels=30,
        )

        expected = {
            "Nivolumab": {6.0: 0.723, 12.0: 0.418, 18.0: 0.217},
            "Bevacizumab": {6.0: 0.782, 12.0: 0.420, 18.0: 0.216},
        }
        observed = {}
        for curve in result.curves:
            observed[curve.name] = {}
            for time, landmark in expected[curve.name].items():
                # The rasterized vertical step can land one or two pixels to
                # the right of the printed landmark tick.  Sample just after
                # the tick, consistent with a right-continuous KM curve.
                index = np.searchsorted(curve.time, time + 0.2, side="right") - 1
                value = curve.survival[index]
                observed[curve.name][time] = value
                self.assertLess(abs(value - landmark), 0.04)

        # The two gray traces are visibly separated at six months.  This
        # catches a light-curve extraction that switches onto the dark trace
        # while still looking plausible in a full-panel overlay.
        self.assertGreater(
            observed["Bevacizumab"][6.0] - observed["Nivolumab"][6.0],
            0.025,
        )

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
