"""Pixel-to-curve sampling tests for KM-style step preservation."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw

from pykmextract.contracts import AxisBounds
from pykmextract.extractor.pixel import adaptive_color_extraction, color_distance_mask, pixels_to_curve


class PixelSamplingTests(unittest.TestCase):
    def test_color_distance_mask_excludes_neutral_gray_for_colored_target(self):
        pixels = np.array(
            [
                [[176, 165, 142], [181, 171, 151]],
                [[158, 158, 158], [160, 160, 160]],
            ],
            dtype=np.uint8,
        )

        mask = color_distance_mask(pixels, (176, 165, 142), tolerance=32)

        self.assertEqual(mask.tolist(), [[True, True], [False, False]])

    def test_adaptive_color_extraction_waits_for_x_coverage(self):
        with TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "coverage.png"
            image = Image.new("RGB", (120, 60), (255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.line([(10, 20), (50, 20)], fill=(30, 90, 200), width=2)
            draw.line([(50, 20), (90, 20)], fill=(45, 105, 215), width=2)
            image.save(image_path)

            coords, tolerance = adaptive_color_extraction(
                str(image_path),
                (30, 90, 200),
                plot_bounds=AxisBounds(left=10, right=90, top=10, bottom=30),
                min_pixels=20,
                tolerance_steps=(8, 18, 32),
            )

            self.assertEqual(tolerance, 32)
            self.assertGreaterEqual(len(np.unique(coords[:, 1])), 24)

    def test_adaptive_color_extraction_reuses_preloaded_pixels(self):
        pixels = np.full((40, 80, 3), 255, dtype=np.uint8)
        pixels[12:14, 8:24] = (30, 90, 200)
        pixels[12:14, 24:56] = (45, 105, 215)

        with patch(
            "pykmextract.extractor.pixel.load_image_array",
            side_effect=AssertionError("image should not be reloaded when pixels are provided"),
        ):
            coords, tolerance = adaptive_color_extraction(
                "ignored.png",
                (30, 90, 200),
                pixels=pixels,
                plot_bounds=AxisBounds(left=8, right=56, top=8, bottom=20),
                min_pixels=20,
                tolerance_steps=(8, 18, 32),
            )

        self.assertEqual(tolerance, 32)
        self.assertGreater(len(coords), 0)

    def test_pixels_to_curve_forward_fills_missing_columns(self):
        coords = np.array(
            [
                [10, 0],
                [10, 1],
                [10, 2],
                [10, 3],
                [10, 4],
                [10, 5],
                [10, 6],
                [10, 7],
                [10, 8],
                [20, 10],
                [20, 11],
                [20, 12],
            ],
            dtype=int,
        )

        x_pixels, y_pixels = pixels_to_curve(coords)

        self.assertEqual(x_pixels.tolist(), list(range(13)))
        self.assertEqual(y_pixels[:10].tolist(), [10.0] * 10)
        self.assertEqual(y_pixels[10:].tolist(), [20.0, 20.0, 20.0])

    def test_pixels_to_curve_supports_x_step_sampling(self):
        coords = np.array(
            [
                [10, 0],
                [10, 1],
                [10, 2],
                [10, 3],
                [20, 4],
                [20, 5],
                [20, 6],
                [20, 7],
            ],
            dtype=int,
        )

        x_pixels, y_pixels = pixels_to_curve(coords, x_step=2.0)

        self.assertEqual(x_pixels.tolist(), [0.0, 2.0, 4.0, 6.0, 7.0])
        self.assertEqual(y_pixels.tolist(), [10.0, 10.0, 20.0, 20.0, 20.0])

    def test_pixels_to_curve_tracks_plateau_across_vertical_drop_column(self):
        coords = np.array(
            [
                [10, 0],
                [10, 1],
                [10, 2],
                [11, 2],
                [12, 2],
                [13, 2],
                [14, 2],
                [15, 2],
                [16, 2],
                [17, 2],
                [18, 2],
                [19, 2],
                [20, 2],
                [20, 3],
                [20, 4],
            ],
            dtype=int,
        )

        x_pixels, y_pixels = pixels_to_curve(coords)

        self.assertEqual(x_pixels.tolist(), [0.0, 1.0, 2.0, 3.0, 4.0])
        self.assertEqual(y_pixels.tolist(), [10.0, 10.0, 20.0, 20.0, 20.0])


if __name__ == "__main__":
    unittest.main()
