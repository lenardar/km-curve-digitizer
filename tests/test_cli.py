"""CLI smoke tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.test_pipeline import make_synthetic_km_image


class CLITests(unittest.TestCase):
    def test_cli_writes_json_and_overlay(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            semantic_path = Path(tmpdir) / "semantic.json"
            output_path = Path(tmpdir) / "result.json"
            overlay_path = Path(tmpdir) / "overlay.png"

            semantic, _ = make_synthetic_km_image(image_path)
            semantic_path.write_text(json.dumps(semantic), encoding="utf-8")

            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            env.setdefault("MPLCONFIGDIR", str(Path(tmpdir) / ".mplconfig"))

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pykmextract.cli",
                    str(image_path),
                    "--semantic-json",
                    str(semantic_path),
                    "--output-json",
                    str(output_path),
                    "--overlay",
                    str(overlay_path),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output_path.exists())
            self.assertTrue(overlay_path.exists())

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["semantic"]["n_curves"], 2)
            self.assertEqual(len(payload["curves"]), 2)

    def test_cli_writes_review_bundle(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            semantic_path = Path(tmpdir) / "semantic.json"
            output_path = Path(tmpdir) / "result.json"
            review_dir = Path(tmpdir) / "review"

            semantic, _ = make_synthetic_km_image(image_path)
            semantic_path.write_text(json.dumps(semantic), encoding="utf-8")

            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            env.setdefault("MPLCONFIGDIR", str(Path(tmpdir) / ".mplconfig"))

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pykmextract.cli",
                    str(image_path),
                    "--semantic-json",
                    str(semantic_path),
                    "--output-json",
                    str(output_path),
                    "--review-dir",
                    str(review_dir),
                    "--review-title",
                    "synthetic",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((review_dir / "review.md").exists())
            self.assertTrue((review_dir / "digitized_curves.csv").exists())

    def test_cli_requires_provider_for_axis_refine(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            semantic_path = Path(tmpdir) / "semantic.json"
            output_path = Path(tmpdir) / "result.json"

            semantic, _ = make_synthetic_km_image(image_path)
            semantic_path.write_text(json.dumps(semantic), encoding="utf-8")

            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            env.setdefault("MPLCONFIGDIR", str(Path(tmpdir) / ".mplconfig"))

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pykmextract.cli",
                    str(image_path),
                    "--semantic-json",
                    str(semantic_path),
                    "--output-json",
                    str(output_path),
                    "--axis-refine",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("--axis-refine requires an online --provider configuration", completed.stderr)

    def test_cli_reads_axis_json_and_exports_final_axis_json(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            semantic_path = Path(tmpdir) / "semantic.json"
            axis_path = Path(tmpdir) / "axis.json"
            export_path = Path(tmpdir) / "axis_out.json"
            output_path = Path(tmpdir) / "result.json"

            semantic, bounds = make_synthetic_km_image(image_path)
            semantic_path.write_text(json.dumps(semantic), encoding="utf-8")
            axis_path.write_text(
                json.dumps(
                    {
                        "axis_bounds": {
                            "left": bounds[0],
                            "right": bounds[1],
                            "top": bounds[2],
                            "bottom": bounds[3],
                        },
                        "axis_anchors": {
                            "x_min_point": {"x": bounds[0], "y": bounds[3]},
                            "x_max_point": {"x": bounds[1], "y": bounds[3]},
                            "y_min_point": {"x": bounds[0], "y": bounds[3]},
                            "y_max_point": {"x": bounds[0], "y": bounds[2]},
                        },
                    }
                ),
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            env.setdefault("MPLCONFIGDIR", str(Path(tmpdir) / ".mplconfig"))

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pykmextract.cli",
                    str(image_path),
                    "--semantic-json",
                    str(semantic_path),
                    "--axis-json",
                    str(axis_path),
                    "--axis-export-json",
                    str(export_path),
                    "--output-json",
                    str(output_path),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            exported = json.loads(export_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["axis_bounds"]["left"], bounds[0])
            self.assertEqual(payload["axis_bounds"]["bottom"], bounds[3])
            self.assertEqual(exported["axis_anchors"]["y_max_point"]["y"], bounds[2])


if __name__ == "__main__":
    unittest.main()
