"""End-to-end tests on synthetic KM plots."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image, ImageDraw

import km_digitizer as pkm


def _step_points(series):
    points = []
    previous_time, previous_survival = series[0]
    points.append((previous_time, previous_survival))
    for time_value, survival_value in series[1:]:
        points.append((time_value, previous_survival))
        points.append((time_value, survival_value))
        previous_time, previous_survival = time_value, survival_value
    return points


def _pixel_from_data(time_value, survival_value, bounds, x_max):
    left, right, top, bottom = bounds
    x_pixel = left + (time_value / x_max) * (right - left)
    y_pixel = bottom - survival_value * (bottom - top)
    return int(round(x_pixel)), int(round(y_pixel))


def make_synthetic_km_image(path: Path):
    width, height = 640, 420
    bounds = (70, 580, 40, 300)
    x_max = 24

    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    left, right, top, bottom = bounds
    draw.line([(left, bottom), (right, bottom)], fill=(0, 0, 0), width=3)
    draw.line([(left, bottom), (left, top)], fill=(0, 0, 0), width=3)

    treatment = [(0, 1.0), (4, 0.95), (8, 0.82), (12, 0.68), (18, 0.50), (24, 0.35)]
    control = [(0, 1.0), (4, 0.90), (8, 0.72), (12, 0.55), (18, 0.32), (24, 0.15)]

    for series, color in [
        (treatment, (30, 90, 200)),
        (control, (210, 50, 60)),
    ]:
        pixels = [_pixel_from_data(t, s, bounds, x_max) for t, s in _step_points(series)]
        draw.line(pixels, fill=color, width=3)

    image.save(path)

    semantic = {
        "n_curves": 2,
        "x_axis": {"min": 0, "max": 24, "unit": "months", "label": "Time"},
        "y_axis": {"min": 0, "max": 1, "is_percentage": False, "label": "Survival"},
        "curves": [
            {
                "id": 1,
                "legend_name": "Treatment",
                "color_description": "blue solid",
                "rgb_approx": [30, 90, 200],
                "line_style": "solid",
            },
            {
                "id": 2,
                "legend_name": "Control",
                "color_description": "red solid",
                "rgb_approx": [210, 50, 60],
                "line_style": "solid",
            },
        ],
        "at_risk_table": {
            "time_points": [0, 8, 12, 18, 24],
            "counts_by_curve": [
                [100, 82, 68, 50, 35],
                [100, 72, 55, 32, 15],
            ],
        },
        "total_events_by_curve": [65, 85],
        "has_confidence_interval": False,
        "has_censoring_marks": False,
        "confidence": {
            "overall": "high",
            "at_risk_table": "high",
            "color_identification": "high",
        },
        "notes": "",
    }
    return semantic, bounds


class ExtractionPipelineTests(unittest.TestCase):
    def test_extract_from_static_semantics(self):
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

            self.assertEqual(len(result.curves), 2)
            self.assertTrue(result.validation.checks["range"])
            self.assertTrue(result.validation.checks["monotonicity"])
            frame = result.curve_frame()
            self.assertGreater(len(frame), 400)

            expected = {
                # Sample just after each synthetic vertical edge. A thick
                # rasterized edge spans several x-columns, while the KM value
                # is right-continuous once that visible edge is crossed.
                "Treatment": {0: 1.0, 8.25: 0.82, 12.25: 0.68, 24: 0.35},
                "Control": {0: 1.0, 8.25: 0.72, 12.25: 0.55, 24: 0.15},
            }
            for curve in result.curves:
                observed = np.interp(
                    np.array(list(expected[curve.name].keys()), dtype=float),
                    np.array(curve.time, dtype=float),
                    np.array(curve.survival, dtype=float),
                )
                for value, target in zip(observed, expected[curve.name].values()):
                    self.assertLess(abs(value - target), 0.08)

    def test_auto_axis_detection_without_override(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            semantic, bounds = make_synthetic_km_image(image_path)

            result = pkm.extract(
                str(image_path),
                semantic=semantic,
                min_curve_pixels=20,
            )

            self.assertLessEqual(abs(result.axis_bounds.left - bounds[0]), 2)
            self.assertLessEqual(abs(result.axis_bounds.right - bounds[1]), 2)
            self.assertLessEqual(abs(result.axis_bounds.top - bounds[2]), 2)
            self.assertLessEqual(abs(result.axis_bounds.bottom - bounds[3]), 2)

    def test_semantic_pixel_tolerance_overrides_adaptive_choice(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            semantic, bounds = make_synthetic_km_image(image_path)
            semantic["curves"][0]["pixel_tolerance"] = 7

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

            self.assertEqual(result.curves[0].extraction_tolerance, 7)

    def test_overlay_export(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "km.png"
            overlay_path = Path(tmpdir) / "overlay.png"
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
            saved = result.save_overlay(str(overlay_path))

            self.assertEqual(saved, str(overlay_path))
            self.assertTrue(overlay_path.exists())
            self.assertGreater(overlay_path.stat().st_size, 0)

if __name__ == "__main__":
    unittest.main()
