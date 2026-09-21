"""Tests for post-extraction micro-tuning tools."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

from pykmextract.contracts import (
    AtRiskTable,
    AxisAnchors,
    AxisBounds,
    CurveData,
    ExtractionResult,
    SemanticConfidence,
    SemanticExtraction,
    ValidationIssue,
    ValidationReport,
    XAxisSpec,
    YAxisSpec,
)
from pykmextract.microtune import CurveMicroTuneToolkit, SegmentMicroTuner
from pykmextract.providers import StaticVisionProvider


def _build_result() -> ExtractionResult:
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
    time = list(range(25))
    curve_a = CurveData(
        id=1,
        name="Arm A",
        color_description="blue",
        extraction_tolerance=20,
        point_count=60,
        x_pixels=list(range(25)),
        y_pixels=[20.0] * 13 + [40.0] * 12,
        time=time,
        survival=[1.0] + [0.7] * 12 + [0.5] * 12,
    )
    curve_b = CurveData(
        id=2,
        name="Arm B",
        color_description="orange",
        extraction_tolerance=22,
        point_count=60,
        x_pixels=list(range(25)),
        y_pixels=[21.0] * 13 + [41.0] * 12,
        time=time,
        survival=[1.0] + [0.69] * 12 + [0.49] * 12,
    )
    return ExtractionResult(
        image_path="dummy.png",
        semantic=semantic,
        axis_bounds=AxisBounds(left=0, right=240, top=0, bottom=100),
        axis_anchors=AxisAnchors.from_bounds(AxisBounds(left=0, right=240, top=0, bottom=100)),
        curves=[curve_a, curve_b],
        validation=ValidationReport(
            score=100,
            level="high",
            checks={
                "monotonicity": True,
                "range": True,
                "start": True,
                "coverage": True,
                "risk_table": True,
            },
            issues=[],
        ),
    )


class MicroTuneTests(unittest.TestCase):
    def test_find_overlap_windows_detects_long_close_segment(self):
        toolkit = CurveMicroTuneToolkit()
        result = _build_result()

        windows = toolkit.find_overlap_windows(result, y_tolerance=0.03, min_duration=3.0, min_points=4)

        self.assertTrue(windows)
        self.assertEqual(windows[0].left_curve, "Arm A")
        self.assertEqual(windows[0].right_curve, "Arm B")

    def test_inspect_segment_returns_curve_and_neighbor_samples(self):
        toolkit = CurveMicroTuneToolkit()
        result = _build_result()

        summary = toolkit.inspect_segment(result, curve_name="Arm A", time_start=10, time_end=18, sample_count=5)

        self.assertEqual(summary["curve_name"], "Arm A")
        self.assertEqual(len(summary["samples"]), 5)
        self.assertEqual(summary["neighbors"][0]["curve_name"], "Arm B")

    def test_apply_step_targets_only_adjusts_selected_segment(self):
        toolkit = CurveMicroTuneToolkit()
        result = _build_result()

        tuned = toolkit.apply_step_targets(
            result,
            curve_name="Arm B",
            targets=[(12.0, 0.62), (18.0, 0.45)],
            max_delta=0.08,
        )

        original_curve = next(curve for curve in result.curves if curve.name == "Arm B")
        tuned_curve = next(curve for curve in tuned.curves if curve.name == "Arm B")
        np.testing.assert_allclose(tuned_curve.survival[:11], original_curve.survival[:11])
        self.assertLessEqual(tuned_curve.survival[12], 0.69)
        self.assertGreaterEqual(tuned_curve.survival[12], 0.61)
        self.assertLessEqual(tuned_curve.survival[18], 0.49)

    def test_segment_micro_tuner_applies_provider_targets(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "dummy.png"
            Image.new("RGB", (260, 120), (255, 255, 255)).save(image_path)
            result = _build_result().model_copy(update={"image_path": str(image_path)})
            provider = StaticVisionProvider(
                {
                    "action": "adjust",
                    "curve_name": "Arm B",
                    "time_start": 9.0,
                    "time_end": 24.0,
                    "targets": [[12.0, 0.62], [18.0, 0.45]],
                    "confidence": "medium",
                    "notes": "test",
                }
            )

            tuned = SegmentMicroTuner(max_delta=0.04).refine(
                result,
                provider=provider,
                model="fake-model",
                api_key="fake-key",
                review_image_path=str(Path(tmpdir) / "micro_review.png"),
            )

            original_curve = next(curve for curve in result.curves if curve.name == "Arm B")
            tuned_curve = next(curve for curve in tuned.curves if curve.name == "Arm B")
            self.assertNotEqual(tuned_curve.survival, original_curve.survival)

    def test_segment_micro_tuner_rejects_large_score_drop(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "dummy.png"
            Image.new("RGB", (260, 120), (255, 255, 255)).save(image_path)
            result = _build_result().model_copy(update={"image_path": str(image_path)})
            provider = StaticVisionProvider(
                {
                    "action": "adjust",
                    "curve_name": "Arm B",
                    "time_start": 0.0,
                    "time_end": 24.0,
                    "targets": [[0.0, 0.2], [12.0, 0.1], [24.0, 0.0]],
                    "confidence": "high",
                    "notes": "bad adjustment",
                }
            )

            tuned = SegmentMicroTuner(max_delta=0.50, max_score_drop=0).refine(
                result,
                provider=provider,
                model="fake-model",
                api_key="fake-key",
                review_image_path=str(Path(tmpdir) / "micro_review.png"),
            )

            self.assertEqual(tuned.model_dump(mode="json"), result.model_dump(mode="json"))

    def test_segment_micro_tuner_prioritizes_issue_curve_tail_before_overlap_window(self):
        result = _build_result()
        result.validation = ValidationReport(
            score=80,
            level="high",
            checks={
                "monotonicity": True,
                "range": True,
                "start": True,
                "coverage": False,
                "risk_table": True,
            },
            issues=[ValidationIssue(code="coverage", curve_id=2, message="tail too short")],
        )

        candidate = SegmentMicroTuner()._select_candidate_segment(result)

        self.assertIsNotNone(candidate)
        curve_name, time_start, time_end = candidate
        self.assertEqual(curve_name, "Arm B")
        self.assertGreaterEqual(time_start, 9.0)
        self.assertGreater(time_end, time_start)


if __name__ == "__main__":
    unittest.main()
