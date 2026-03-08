"""Tests for optional AI enhancement orchestration."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pykmextract as pkm
from pykmextract.providers import StaticVisionProvider

from tests.test_pipeline import make_synthetic_km_image


class AIEnhancementTests(unittest.TestCase):
    def test_apply_ai_enhancements_keeps_default_result_when_disabled(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            semantic, bounds = make_synthetic_km_image(image_path)
            result = pkm.extract(
                str(image_path),
                semantic=semantic,
                axis_bounds={
                    "left": bounds[0],
                    "right": bounds[1],
                    "top": bounds[2],
                    "bottom": bounds[3],
                },
                min_curve_pixels=20,
            )

            enhanced = pkm.apply_ai_enhancements(result, provider=None)

            self.assertIs(enhanced, result)

    def test_apply_ai_enhancements_requires_provider_for_axis_refine(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            semantic, bounds = make_synthetic_km_image(image_path)
            result = pkm.extract(
                str(image_path),
                semantic=semantic,
                axis_bounds={
                    "left": bounds[0],
                    "right": bounds[1],
                    "top": bounds[2],
                    "bottom": bounds[3],
                },
                min_curve_pixels=20,
            )

            with self.assertRaisesRegex(ValueError, "--axis-refine requires an online --provider configuration"):
                pkm.apply_ai_enhancements(
                    result,
                    provider=None,
                    options=pkm.AIEnhancementOptions(axis_refine=True),
                )

    def test_apply_ai_enhancements_reruns_extract_with_refined_axis_anchors(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            semantic, bounds = make_synthetic_km_image(image_path)
            result = pkm.extract(
                str(image_path),
                semantic=semantic,
                axis_bounds={
                    "left": bounds[0],
                    "right": bounds[1],
                    "top": bounds[2],
                    "bottom": bounds[3],
                },
                min_curve_pixels=20,
            )
            refined_anchors = {
                "x_min_point": {"x": bounds[0] + 1, "y": bounds[3]},
                "x_max_point": {"x": bounds[1] - 1, "y": bounds[3]},
                "y_min_point": {"x": bounds[0] + 1, "y": bounds[3]},
                "y_max_point": {"x": bounds[0] + 1, "y": bounds[2] + 1},
            }

            with patch("pykmextract.enhancements.AxisRefiner") as mock_refiner:
                mock_refiner.return_value.refine.return_value = pkm.AxisAnchors.model_validate(refined_anchors)
                enhanced = pkm.apply_ai_enhancements(
                    result,
                    provider=StaticVisionProvider(semantic),
                    model="fake-model",
                    api_key="fake-key",
                    options=pkm.AIEnhancementOptions(
                        axis_refine=True,
                        axis_review_image=str(Path(tmpdir) / "axis_review.png"),
                    ),
                )

            self.assertEqual(enhanced.axis_anchors.model_dump(mode="json"), refined_anchors)
            self.assertEqual(enhanced.axis_bounds.model_dump(mode="json"), result.axis_bounds.model_dump(mode="json"))
            mock_refiner.return_value.refine.assert_called_once()


if __name__ == "__main__":
    unittest.main()
