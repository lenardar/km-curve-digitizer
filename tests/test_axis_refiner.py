"""Axis anchor and AI review tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from pykmextract.contracts import AxisAnchors, AxisBounds, XAxisSpec, YAxisSpec
from pykmextract.extractor.axis_refiner import (
    build_axis_evidence_prompt,
    AxisRefiner,
    build_axis_review_prompt,
    generate_axis_anchor_candidates,
    normalize_axis_evidence_payload,
    normalize_axis_review_payload,
    refine_candidates_with_evidence,
)
from pykmextract.extractor.coord import pixel_to_data
from pykmextract.providers import CallableVisionProvider
from tests.test_pipeline import make_synthetic_km_image


class AxisRefinerTests(unittest.TestCase):
    def test_pixel_to_data_uses_four_point_anchors(self):
        bounds = AxisBounds(left=0, right=100, top=0, bottom=100)
        anchors = AxisAnchors.model_validate(
            {
                "x_min_point": {"x": 10, "y": 90},
                "x_max_point": {"x": 90, "y": 92},
                "y_min_point": {"x": 8, "y": 80},
                "y_max_point": {"x": 9, "y": 20},
            }
        )

        time, survival = pixel_to_data(
            x_pixels=np.array([10, 50, 90], dtype=float),
            y_pixels=np.array([20, 50, 80], dtype=float),
            axis_bounds=bounds,
            x_axis=XAxisSpec(min=0, max=24, unit="months", label="Time"),
            y_axis=YAxisSpec(min=0, max=1, is_percentage=False, label="Survival"),
            axis_anchors=anchors,
        )

        self.assertAlmostEqual(time[0], 0.0)
        self.assertAlmostEqual(time[-1], 24.0)
        self.assertAlmostEqual(survival[0], 1.0)
        self.assertAlmostEqual(survival[-1], 0.0)

    def test_axis_refiner_review_returns_adjusted_anchors(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            review_path = Path(tmpdir) / "axis_review.png"
            make_synthetic_km_image(image_path)
            bounds = AxisBounds(left=70, right=580, top=40, bottom=300)

            call_count = {"value": 0}

            def callback(*, image_path: str, prompt: str, model=None, api_key=None):
                call_count["value"] += 1
                self.assertTrue(Path(image_path).exists())
                if "You are inspecting axis numbers and tick marks" in prompt:
                    self.assertIn("numeric tick labels", prompt)
                    return {
                        "origin_intersection_visible": True,
                        "x_axis": {
                            "min_label_text": "0",
                            "max_label_text": "24",
                            "min_tick_at_intersection": True,
                            "max_tick_visible": True,
                        },
                        "y_axis": {
                            "min_label_text": "0",
                            "max_label_text": "1.0",
                            "min_tick_at_intersection": True,
                            "max_tick_visible": True,
                            "max_tick_substantially_below_top_border": False,
                        },
                        "notes": "",
                    }
                self.assertIn("XMIN_1", prompt)
                self.assertIn("YMAX_1", prompt)
                return {
                    "decision": "adjust",
                    "x_min_point": {"candidate_id": "XMIN_2", "dx": 1, "dy": 0, "confidence": "high"},
                    "x_max": {"candidate_id": "XMAX_1", "dx": -2, "dy": 0, "confidence": "medium"},
                    "y_min_point": {"candidate_id": "YMIN_1", "dx": 0, "dy": -3, "confidence": "high"},
                    "y_max_point": {"candidate_id": "YMAX_2", "dx": 0, "dy": 1, "confidence": "high"},
                    "issues": "x-axis starts slightly inside the panel",
                }

            provider = CallableVisionProvider(callback)
            anchors = AxisRefiner(candidate_step=4, candidate_count=3, adjustment_limit=6).refine(
                str(image_path),
                axis_bounds=bounds,
                provider=provider,
                review_image_path=str(review_path),
            )

            self.assertTrue(review_path.exists())
            self.assertEqual(call_count["value"], 2)
            self.assertEqual(anchors.x_min_point.x, 75)
            self.assertEqual(anchors.x_max_point.x, 578)
            self.assertEqual(anchors.y_min_point.y, 297)
            self.assertEqual(anchors.y_max_point.y, 45)

    def test_normalize_axis_review_payload_accepts_aliases(self):
        bounds = AxisBounds(left=70, right=580, top=40, bottom=300)
        candidates = generate_axis_anchor_candidates(bounds, step=4, candidate_count=2)

        payload = normalize_axis_review_payload(
            {
                "decision": "accept",
                "x_min": "XMIN_1",
                "x_max": {"candidate_id": "XMAX_1", "dx": 0, "dy": 0, "confidence": "high"},
                "y_min": {"candidate_id": "YMIN_1"},
                "y_max": {"candidate_id": "YMAX_1", "confidence": "low"},
                "issues": "none",
            },
            candidates,
        )

        self.assertEqual(payload["x_min_point"]["candidate_id"], "XMIN_1")
        self.assertEqual(payload["issues"], ["none"])

    def test_generate_axis_anchor_candidates_expand_beyond_tiny_local_step(self):
        bounds = AxisBounds(left=132, right=784, top=4, bottom=239)
        candidates = generate_axis_anchor_candidates(bounds, step=4, candidate_count=5)

        self.assertEqual(
            [candidate.point.y for candidate in candidates["y_max_point"]],
            [4, 8, 20, 40, 68],
        )
        self.assertEqual(
            [candidate.point.x for candidate in candidates["x_min_point"]],
            [132, 136, 148, 168, 196],
        )

    def test_axis_review_prompt_mentions_ticks_and_forbids_curve_anchors(self):
        bounds = AxisBounds(left=70, right=580, top=40, bottom=300)
        prompt = build_axis_review_prompt(
            generate_axis_anchor_candidates(bounds, step=4, candidate_count=3)
        )

        self.assertIn("numeric tick labels", prompt)
        self.assertIn("shared reference for x_min_point and y_min_point", prompt)
        self.assertIn("Do not use curve position", prompt)

    def test_axis_evidence_prompt_mentions_intersection_and_tick_numbers(self):
        prompt = build_axis_evidence_prompt()
        self.assertIn("axis intersection", prompt)
        self.assertIn("numeric tick labels", prompt)
        self.assertIn("max_tick_substantially_below_top_border", prompt)

    def test_normalize_axis_evidence_payload_parses_strings_and_nulls(self):
        payload = normalize_axis_evidence_payload(
            {
                "origin_intersection_visible": "true",
                "x_axis": {
                    "min_label_text": "0",
                    "max_label_text": None,
                    "min_tick_at_intersection": "yes",
                    "max_tick_visible": "false",
                },
                "y_axis": {
                    "min_label_text": "0",
                    "max_label_text": "100",
                    "min_tick_at_intersection": True,
                    "max_tick_visible": False,
                    "max_tick_substantially_below_top_border": "true",
                },
                "notes": "tick labels visible",
            }
        )

        self.assertEqual(payload["origin_intersection_visible"], True)
        self.assertEqual(payload["x_axis"]["max_label_text"], None)
        self.assertEqual(payload["x_axis"]["min_tick_at_intersection"], True)
        self.assertEqual(payload["x_axis"]["max_tick_visible"], False)
        self.assertEqual(payload["y_axis"]["max_tick_substantially_below_top_border"], True)

    def test_refine_candidates_with_evidence_drops_top_border_ymax_when_needed(self):
        bounds = AxisBounds(left=132, right=784, top=4, bottom=239)
        candidates = generate_axis_anchor_candidates(bounds, step=4, candidate_count=5)
        refined = refine_candidates_with_evidence(
            candidates,
            evidence={
                "origin_intersection_visible": True,
                "x_axis": {},
                "y_axis": {"max_tick_substantially_below_top_border": True},
                "notes": "",
            },
            bounds=bounds,
        )

        self.assertEqual(
            [candidate.point.y for candidate in refined["y_max_point"]],
            [40, 68],
        )

    def test_refine_candidates_with_evidence_keeps_xmax_and_ymin_near_axis_end(self):
        bounds = AxisBounds(left=120, right=797, top=40, bottom=291)
        candidates = generate_axis_anchor_candidates(bounds, step=4, candidate_count=5)

        refined = refine_candidates_with_evidence(
            candidates,
            evidence={
                "origin_intersection_visible": True,
                "x_axis": {"max_tick_visible": True},
                "y_axis": {},
                "notes": "",
            },
            bounds=bounds,
        )

        self.assertEqual(
            [candidate.point.x for candidate in refined["x_max_point"]],
            [797, 793, 781],
        )
        self.assertEqual(
            [candidate.point.y for candidate in refined["y_min_point"]],
            [291, 287],
        )


if __name__ == "__main__":
    unittest.main()
