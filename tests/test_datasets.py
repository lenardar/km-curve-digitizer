"""Dataset grouping tests."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from km_digitizer.datasets import build_real_km_manifest, discover_real_km_studies, parse_literature_notes


class DatasetTests(unittest.TestCase):
    def test_discover_real_km_studies(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for name in [
                "study01_full.png",
                "study01_pfs.png",
                "study01_os.png",
                "study02_pfs.png",
                "study02_os.png",
            ]:
                (root / name).write_bytes(b"fake")

            studies = discover_real_km_studies(root)
            self.assertEqual(len(studies), 2)
            self.assertEqual(studies[0]["study_id"], "study01")
            self.assertIn("pfs", studies[0]["panels"])
            self.assertTrue(studies[0]["full"])
            self.assertFalse(studies[1]["full"])

    def test_parse_literature_notes(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "literatures.md"
            path.write_text(
                "# study01\nFirst citation line\n\n# study02\nSecond citation line\n",
                encoding="utf-8",
            )
            notes = parse_literature_notes(path)
            self.assertEqual(notes["study01"], "First citation line")
            self.assertEqual(notes["study02"], "Second citation line")

    def test_build_manifest(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_dir = root / "images"
            image_dir.mkdir()
            for name in [
                "study01_full.png",
                "study01_pfs.png",
                "study01_os.png",
                "study02_pfs.png",
                "study02_os.png",
            ]:
                (image_dir / name).write_bytes(b"fake")
            notes_path = image_dir / "literatures.md"
            notes_path.write_text("# study01\nCitation A\n# study02\nCitation B\n", encoding="utf-8")

            manifest = build_real_km_manifest(image_dir, literature_md=notes_path)
            self.assertEqual(manifest["summary"]["n_studies"], 2)
            self.assertEqual(manifest["summary"]["n_panel_jobs"], 4)
            self.assertEqual(manifest["summary"]["n_with_full"], 1)
            study02 = next(item for item in manifest["studies"] if item["study_id"] == "study02")
            self.assertIn("missing_full_image", study02["warnings"])
            plan_job = next(item for item in manifest["plan"] if item["study_id"] == "study01" and item["endpoint"] == "pfs")
            self.assertTrue(plan_job["inherit_legend_from_full"])


if __name__ == "__main__":
    unittest.main()
