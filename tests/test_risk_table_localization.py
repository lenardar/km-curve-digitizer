"""Tests for geometry-based number-at-risk cell localization."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from PIL import Image, ImageDraw

from pykmextract.contracts import AxisAnchors, AxisBounds, SemanticExtraction
from pykmextract.extractor.risk_table import locate_risk_table_cells


class RiskTableLocalizationTests(unittest.TestCase):
    def test_locates_dense_rows_at_calibrated_time_columns(self):
        width, height = 520, 340
        bounds = AxisBounds(left=60, right=460, top=30, bottom=220)
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        draw.line([(bounds.left, bounds.bottom), (bounds.right, bounds.bottom)], fill="black", width=2)

        time_points = [0, 6, 12, 18, 24]
        centers = [60, 160, 260, 360, 460]
        for x_value, label in zip(centers, time_points):
            draw.text((x_value - 3, 228), str(label), fill="black")
        draw.text((240, 246), "Months", fill="black")

        counts = [[100, 82, 68, 50, 35], [100, 72, 55, 32, 15]]
        for y_value, row in zip([282, 304], counts):
            for x_value, count in zip(centers, row):
                text = str(count)
                box = draw.textbbox((0, 0), text)
                draw.text((x_value - (box[2] - box[0]) / 2, y_value), text, fill="black")

        semantic = SemanticExtraction.model_validate(
            {
                "n_curves": 2,
                "x_axis": {"min": 0, "max": 24, "unit": "months", "label": "Time"},
                "y_axis": {"min": 0, "max": 1, "is_percentage": False, "label": "Survival"},
                "curves": [
                    {"id": 1, "legend_name": "A", "rgb_approx": [0, 0, 255]},
                    {"id": 2, "legend_name": "B", "rgb_approx": [255, 0, 0]},
                ],
                "at_risk_table": {
                    "time_points": time_points,
                    "counts_by_curve": counts,
                },
            }
        )

        regions = locate_risk_table_cells(
            np.array(image),
            semantic,
            bounds,
            AxisAnchors.from_bounds(bounds),
        )

        self.assertEqual(len(regions), 2)
        self.assertTrue(all(len(row) == 5 for row in regions))
        first = regions[0][0]
        last = regions[1][-1]
        self.assertIsNotNone(first)
        self.assertIsNotNone(last)
        assert first is not None and last is not None
        self.assertLessEqual(first[0], 60)
        self.assertGreaterEqual(first[2], 60)
        self.assertGreater(first[1], 270)
        self.assertLess(last[1], 315)

    def test_returns_empty_when_no_table_text_is_visible(self):
        bounds = AxisBounds(left=20, right=180, top=20, bottom=100)
        semantic = SemanticExtraction.model_validate(
            {
                "n_curves": 1,
                "x_axis": {"min": 0, "max": 12},
                "y_axis": {"min": 0, "max": 1},
                "curves": [{"id": 1, "legend_name": "A", "rgb_approx": [0, 0, 0]}],
                "at_risk_table": {
                    "time_points": [0, 6, 12],
                    "counts_by_curve": [[50, 30, 10]],
                },
            }
        )

        regions = locate_risk_table_cells(
            np.full((160, 200, 3), 255, dtype=np.uint8),
            semantic,
            bounds,
            AxisAnchors.from_bounds(bounds),
        )

        self.assertEqual(regions, [])

    def test_cli_renders_one_real_localized_cell(self):
        repository = Path(__file__).resolve().parents[1]
        result_path = repository / "runs" / "study04" / "os" / "result.json"
        script = repository / "km-curve-digitizer" / "scripts" / "refine_km.py"
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "cell"
            env = os.environ.copy()
            env.setdefault("MPLCONFIGDIR", str(Path(tmpdir) / ".mplconfig"))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "inspect-risk-cell",
                    str(result_path),
                    "--cell-id",
                    "risk-c1-t002",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=repository,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output_dir / "risk_cell_review.png").exists())
            payload = json.loads((output_dir / "risk_cell.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["cell"]["cell_id"], "risk-c1-t002")
            self.assertIsNotNone(payload["cell"]["pixel_region"])


if __name__ == "__main__":
    unittest.main()
