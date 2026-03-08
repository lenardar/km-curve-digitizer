"""Review bundle generation tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pykmextract as pkm
from tests.test_pipeline import make_synthetic_km_image


class ReviewBundleTests(unittest.TestCase):
    def test_review_bundle_exports_markdown_and_plots(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            output_dir = Path(tmpdir) / "review"
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

            bundle = result.save_review_bundle(
                str(output_dir),
                citation="Synthetic citation",
                title="synthetic_case",
            )

            self.assertTrue(Path(bundle["review_md"]).exists())
            self.assertTrue(Path(bundle["reconstructed_km"]).exists())
            self.assertTrue(Path(bundle["overlay"]).exists())
            markdown = Path(bundle["review_md"]).read_text(encoding="utf-8")
            self.assertIn("Original panel", markdown)
            self.assertIn("KM redrawn from reconstructed IPD", markdown)
            self.assertIn("digitized_curves.csv", markdown)

    def test_lightweight_review_bundle_skips_reconstruction_outputs(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            output_dir = Path(tmpdir) / "review_light"
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

            bundle = result.save_review_bundle(
                str(output_dir),
                title="synthetic_light",
                options=pkm.ReviewBundleOptions.lightweight(),
            )

            self.assertTrue(Path(bundle["review_md"]).exists())
            self.assertTrue(Path(bundle["overlay"]).exists())
            self.assertNotIn("reconstructed_km", bundle)
            self.assertFalse(list(output_dir.glob("ipd_*.csv")))
            markdown = Path(bundle["review_md"]).read_text(encoding="utf-8")
            self.assertIn("Skipped in lightweight review bundle.", markdown)


if __name__ == "__main__":
    unittest.main()
