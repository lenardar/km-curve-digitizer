"""Validator tests."""

from __future__ import annotations

import unittest

from pykmextract.contracts import (
    AtRiskTable,
    AxisAnchors,
    AxisBounds,
    CurveData,
    CurveSemanticSpec,
    ExtractionResult,
    SemanticConfidence,
    SemanticExtraction,
    ValidationReport,
    XAxisSpec,
    YAxisSpec,
)
from pykmextract.extractor.validator import ExtractionValidator


class ValidatorTests(unittest.TestCase):
    def test_bad_curve_is_downgraded(self):
        semantic = SemanticExtraction(
            n_curves=1,
            x_axis=XAxisSpec(min=0, max=24, unit="months", label="Time"),
            y_axis=YAxisSpec(min=0, max=1, is_percentage=False, label="Survival"),
            curves=[
                {
                    "id": 1,
                    "legend_name": "Arm A",
                    "color_description": "blue",
                    "rgb_approx": [30, 90, 200],
                    "line_style": "solid",
                }
            ],
            at_risk_table=AtRiskTable(time_points=[0, 12, 24], counts_by_curve=[[100, 80, 60]]),
            total_events_by_curve=[40],
            has_confidence_interval=False,
            has_censoring_marks=False,
            confidence=SemanticConfidence(),
            notes="",
        )
        curve = CurveData(
            id=1,
            name="Arm A",
            color_description="blue",
            extraction_tolerance=20,
            point_count=30,
            x_pixels=[0, 1, 2, 3],
            y_pixels=[10, 20, 15, 25],
            time=[0, 8, 16, 24],
            survival=[1.0, 0.7, 0.8, 1.2],
        )

        report = ExtractionValidator().validate(semantic, [curve])
        self.assertIsInstance(report, ValidationReport)
        self.assertLess(report.score, 60)
        self.assertEqual(report.level, "low")
        self.assertGreaterEqual(len(report.issues), 2)

    def test_overlapping_curves_are_flagged_for_manual_review(self):
        semantic = SemanticExtraction(
            n_curves=2,
            x_axis=XAxisSpec(min=0, max=24, unit="months", label="Time"),
            y_axis=YAxisSpec(min=0, max=1, is_percentage=False, label="Survival"),
            curves=[
                {
                    "id": 1,
                    "legend_name": "Arm A",
                    "color_description": "blue",
                    "rgb_approx": [30, 90, 200],
                    "line_style": "solid",
                },
                {
                    "id": 2,
                    "legend_name": "Arm B",
                    "color_description": "orange",
                    "rgb_approx": [240, 140, 40],
                    "line_style": "solid",
                },
            ],
            at_risk_table=AtRiskTable(
                time_points=[0, 12, 24],
                counts_by_curve=[[100, 70, 50], [100, 70, 50]],
            ),
            total_events_by_curve=[50, 50],
            has_confidence_interval=False,
            has_censoring_marks=False,
            confidence=SemanticConfidence(),
            notes="",
        )
        base_time = list(range(25))
        base_survival = [1.0] + [0.7] * 12 + [0.5] * 12
        curve_a = CurveData(
            id=1,
            name="Arm A",
            color_description="blue",
            extraction_tolerance=20,
            point_count=60,
            x_pixels=list(range(25)),
            y_pixels=[20.0] * 13 + [40.0] * 12,
            time=base_time,
            survival=base_survival,
        )
        curve_b = CurveData(
            id=2,
            name="Arm B",
            color_description="orange",
            extraction_tolerance=22,
            point_count=60,
            x_pixels=list(range(25)),
            y_pixels=[21.0] * 13 + [41.0] * 12,
            time=base_time,
            survival=base_survival,
        )

        report = ExtractionValidator().validate(semantic, [curve_a, curve_b])

        self.assertEqual(report.level, "medium")
        self.assertFalse(report.checks["overlap_ambiguity"])
        self.assertTrue(any(issue.code == "overlap_ambiguity" for issue in report.issues))

    def test_extraction_result_validation_frame_exports_issue_rows(self):
        semantic = SemanticExtraction(
            n_curves=1,
            x_axis=XAxisSpec(min=0, max=24, unit="months", label="Time"),
            y_axis=YAxisSpec(min=0, max=1, is_percentage=False, label="Survival"),
            curves=[
                CurveSemanticSpec(
                    id=1,
                    legend_name="Arm A",
                    color_description="blue",
                    rgb_approx=(30, 90, 200),
                    line_style="solid",
                )
            ],
            at_risk_table=AtRiskTable(time_points=[0, 12, 24], counts_by_curve=[[100, 80, 60]]),
            total_events_by_curve=[40],
            has_confidence_interval=False,
            has_censoring_marks=False,
            confidence=SemanticConfidence(),
            notes="",
        )
        curve = CurveData(
            id=1,
            name="Arm A",
            color_description="blue",
            extraction_tolerance=20,
            point_count=30,
            x_pixels=[0, 1, 2, 3],
            y_pixels=[10, 20, 15, 25],
            time=[0, 8, 16, 24],
            survival=[1.0, 0.7, 0.8, 1.2],
        )
        report = ExtractionValidator().validate(semantic, [curve])
        result = ExtractionResult(
            image_path="synthetic.png",
            semantic=semantic,
            axis_bounds=AxisBounds(left=0, right=100, top=0, bottom=100),
            axis_anchors=AxisAnchors.from_bounds(AxisBounds(left=0, right=100, top=0, bottom=100)),
            curves=[curve],
            validation=report,
        )

        frame = result.validation_frame()

        self.assertEqual(list(frame.columns), ["code", "message", "curve_id"])
        self.assertGreaterEqual(len(frame), 1)
        self.assertIn("range", set(frame["code"]))


if __name__ == "__main__":
    unittest.main()
