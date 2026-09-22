"""Review bundle generation tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

import pykmextract as pkm
from pykmextract.contracts import ValidationIssue, ValidationReport
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
            self.assertTrue(Path(bundle["scan_windows_json"]).exists())
            self.assertTrue(Path(bundle["scan_review_json"]).exists())
            scan_manifest = json.loads(
                Path(bundle["scan_windows_json"]).read_text(encoding="utf-8")
            )
            self.assertGreaterEqual(len(scan_manifest["windows"]), 2)
            first = scan_manifest["windows"][0]
            second = scan_manifest["windows"][1]
            self.assertGreater(first["pixel_region"][2], second["pixel_region"][0])
            self.assertTrue(
                (Path(bundle["scan_windows_json"]).parent / first["source_image"]).exists()
            )
            self.assertEqual(set(first["curve_images"]), {"1", "2"})
            markdown = Path(bundle["review_md"]).read_text(encoding="utf-8")
            self.assertIn("Original panel", markdown)
            self.assertIn("Digitization overlay", markdown)
            self.assertIn("digitized_curves.csv", markdown)
            self.assertIn("risk_table.csv", markdown)
            self.assertIn("Required Left-to-Right Scan", markdown)

    def test_review_bundle_exports_required_source_only_hotspot(self):
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
            issue = ValidationIssue(
                issue_id="q001-curve_identity_review",
                code="curve_identity_review",
                message="Two traces are locally close",
                curve_ids=[1, 2],
                time_range=(4.0, 6.0),
                pixel_region=(25, 20, 55, 60),
                requires_visual_review=True,
            )
            result.validation = ValidationReport(
                checks={"curve_identity_review": False},
                issues=[issue],
            )

            bundle = result.save_review_bundle(str(output_dir))
            manifest = json.loads(
                Path(bundle["quality_hotspots_json"]).read_text(encoding="utf-8")
            )

            self.assertEqual(manifest[0]["issue_id"], issue.issue_id)
            self.assertTrue((output_dir / manifest[0]["image"]).exists())
            markdown = Path(bundle["review_md"]).read_text(encoding="utf-8")
            self.assertIn(issue.issue_id, markdown)


if __name__ == "__main__":
    unittest.main()
