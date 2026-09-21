"""Review bundle generation tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pykmextract as pkm
from tests.test_pipeline import make_synthetic_km_image


class ReviewBundleTests(unittest.TestCase):
    def test_review_bundle_exports_markdown_overlay_and_tables(self):
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
            self.assertTrue(Path(bundle["overlay"]).exists())
            self.assertTrue(Path(bundle["digitized_csv"]).exists())
            self.assertTrue(Path(bundle["validation_csv"]).exists())
            self.assertTrue(Path(bundle["risk_table_csv"]).exists())
            self.assertTrue(Path(bundle["risk_table_json"]).exists())
            self.assertTrue(Path(bundle["risk_table_review"]).exists())
            markdown = Path(bundle["review_md"]).read_text(encoding="utf-8")
            self.assertIn("Original panel", markdown)
            self.assertIn("Digitization overlay", markdown)
            self.assertIn("digitized_curves.csv", markdown)
            self.assertIn("risk_table.csv", markdown)


if __name__ == "__main__":
    unittest.main()
