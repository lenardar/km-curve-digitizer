"""Normalization tests for non-native provider schemas."""

from __future__ import annotations

import unittest

from pykmextract.extractor.semantic import normalize_semantic_payload


class SemanticNormalizationTests(unittest.TestCase):
    def test_qwen_style_payload_is_normalized(self):
        raw = {
            "chart_type": "Kaplan-Meier",
            "panel_identifier": "A",
            "title": "Overall survival",
            "axes": {
                "x_axis": {
                    "label": "Time, mo",
                    "min": 0,
                    "max": 54,
                    "ticks": [0, 3, 6],
                },
                "y_axis": {
                    "label": "Probability, %",
                    "min": 0,
                    "max": 100,
                    "ticks": [0, 20, 40, 60, 80, 100],
                },
            },
            "curves": [
                {"label": "Tislelizumab", "color": "orange"},
                {"label": "Sorafenib", "color": "dark_blue_grey"},
            ],
            "at_risk_table": {
                "columns": [0, 3, 6],
                "rows": [
                    {"label": "Tislelizumab", "values": [342, 307, 259]},
                    {"label": "Sorafenib", "values": [332, 291, 247]},
                ],
            },
            "total_events": None,
            "censoring_marks": {"present": True},
            "confidence": {
                "overall": "high",
                "notes": "Panel B ignored as instructed.",
            },
            "notes": ["Legend is shared on the full figure."],
        }

        normalized = normalize_semantic_payload(raw)
        self.assertEqual(normalized["n_curves"], 2)
        self.assertEqual(normalized["x_axis"]["unit"], "months")
        self.assertTrue(normalized["y_axis"]["is_percentage"])
        self.assertEqual(normalized["curves"][0]["legend_name"], "Tislelizumab")
        self.assertEqual(normalized["curves"][1]["rgb_approx"], [78, 97, 114])
        self.assertEqual(normalized["at_risk_table"]["counts_by_curve"][0], [342, 307, 259])
        self.assertEqual(normalized["has_censoring_marks"], True)
        self.assertIn("Panel B ignored as instructed.", normalized["notes"])

    def test_at_risk_table_is_truncated_to_common_length(self):
        raw = {
            "axes": {
                "x_axis": {"label": "Time, mo", "min": 0, "max": 9},
                "y_axis": {"label": "Probability, %", "min": 0, "max": 100},
            },
            "curves": [
                {"label": "Arm A", "color": "orange"},
                {"label": "Arm B", "color": "blue"},
            ],
            "at_risk_table": {
                "columns": [0, 3, 6, 9],
                "rows": [
                    {"label": "Arm A", "values": [100, 80, 60]},
                    {"label": "Arm B", "values": [100, 75, 50, 20]},
                ],
            },
            "confidence": {"overall": "medium"},
        }

        normalized = normalize_semantic_payload(raw)
        self.assertEqual(normalized["at_risk_table"]["time_points"], [0, 3, 6])
        self.assertEqual(normalized["at_risk_table"]["counts_by_curve"][0], [100, 80, 60])
        self.assertEqual(normalized["at_risk_table"]["counts_by_curve"][1], [100, 75, 50])

    def test_at_risk_time_points_fall_back_to_x_ticks(self):
        raw = {
            "axes": {
                "x_axis": {"label": "Time, mo", "min": 0, "max": 9, "ticks": [0, 3, 6, 9]},
                "y_axis": {"label": "Probability, %", "min": 0, "max": 100},
            },
            "curves": [
                {"label": "Arm A", "color": "orange"},
                {"label": "Arm B", "color": "blue"},
            ],
            "at_risk_table": {
                "rows": [
                    {"label": "Arm A", "values": [100, 80, 60, 40]},
                    {"label": "Arm B", "values": [100, 75, 50, 25]},
                ],
            },
            "confidence": {"overall": "medium"},
        }

        normalized = normalize_semantic_payload(raw)
        self.assertEqual(normalized["at_risk_table"]["time_points"], [0, 3, 6, 9])
        self.assertEqual(normalized["at_risk_table"]["counts_by_curve"][1], [100, 75, 50, 25])

    def test_direct_counts_by_curve_is_coerced_to_non_increasing(self):
        raw = {
            "n_curves": 2,
            "x_axis": {"min": 0, "max": 12, "unit": "months", "label": "Time"},
            "y_axis": {"min": 0, "max": 100, "is_percentage": True, "label": "Probability, %"},
            "curves": [
                {
                    "id": 1,
                    "legend_name": "Arm A",
                    "color_description": "orange",
                    "rgb_approx": [242, 142, 43],
                    "line_style": "solid",
                },
                {
                    "id": 2,
                    "legend_name": "Arm B",
                    "color_description": "blue",
                    "rgb_approx": [78, 97, 114],
                    "line_style": "solid",
                },
            ],
            "at_risk_table": {
                "time_points": [0, 3, 6, 9, 12],
                "counts_by_curve": [
                    [100, 80, 82, 60, 40],
                    [95, 70, 65, 66, 10],
                ],
            },
            "total_events_by_curve": [40, 55],
            "has_confidence_interval": False,
            "has_censoring_marks": False,
            "confidence": {"overall": "medium", "at_risk_table": "medium", "color_identification": "medium"},
            "notes": "",
        }

        normalized = normalize_semantic_payload(raw)

        self.assertEqual(normalized["at_risk_table"]["counts_by_curve"][0], [100, 80, 80, 60, 40])
        self.assertEqual(normalized["at_risk_table"]["counts_by_curve"][1], [95, 70, 65, 65, 10])


if __name__ == "__main__":
    unittest.main()
