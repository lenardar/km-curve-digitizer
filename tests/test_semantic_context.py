"""Semantic context routing tests."""

from __future__ import annotations

import unittest

from pykmextract.extractor.semantic import SemanticExtractor
from pykmextract.providers import CallableVisionProvider


class SemanticContextTests(unittest.TestCase):
    def test_semantic_image_and_focus_hint_are_forwarded(self):
        captured = {}

        def callback(**kwargs):
            captured.update(kwargs)
            return {
                "n_curves": 1,
                "x_axis": {"min": 0, "max": 24, "unit": "months", "label": "Time"},
                "y_axis": {"min": 0, "max": 1, "is_percentage": False, "label": "Survival"},
                "curves": [
                    {
                        "id": 1,
                        "legend_name": "Arm A",
                        "color_description": "blue",
                        "rgb_approx": [10, 20, 30],
                        "line_style": "solid",
                    }
                ],
                "at_risk_table": {"time_points": [], "counts_by_curve": []},
                "total_events_by_curve": [None],
                "has_confidence_interval": False,
                "has_censoring_marks": False,
                "confidence": {
                    "overall": "medium",
                    "at_risk_table": "low",
                    "color_identification": "medium",
                },
                "notes": "",
            }

        extractor = SemanticExtractor()
        result = extractor.extract(
            "images/study01_pfs.png",
            provider=CallableVisionProvider(callback),
            model="qwen-vl-plus",
            semantic_image_path="images/study01_full.png",
            focus_hint="Focus on the PFS panel only.",
        )

        self.assertEqual(result.n_curves, 1)
        self.assertEqual(captured["image_path"], "images/study01_full.png")
        self.assertIn("Focus on the PFS panel only.", captured["prompt"])


if __name__ == "__main__":
    unittest.main()
