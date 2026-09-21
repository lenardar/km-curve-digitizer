"""Coordinate-axis detection and pixel-to-data conversion."""

from __future__ import annotations

from typing import Tuple

import numpy as np
from PIL import Image

from ..contracts import AxisAnchors, AxisBounds, XAxisSpec, YAxisSpec


def _largest_run_bounds(mask: np.ndarray) -> Tuple[int, int, int]:
    """Return the start, end, and length of the largest True run."""
    best_start = 0
    best_end = -1
    best_len = 0
    current_start = None

    for index, flag in enumerate(mask):
        if flag and current_start is None:
            current_start = index
        if not flag and current_start is not None:
            length = index - current_start
            if length > best_len:
                best_start = current_start
                best_end = index - 1
                best_len = length
            current_start = None

    if current_start is not None:
        length = len(mask) - current_start
        if length > best_len:
            best_start = current_start
            best_end = len(mask) - 1
            best_len = length

    return best_start, best_end, best_len


def _detect_axis_line_candidates(gray: np.ndarray) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Return horizontal and vertical axis-line candidates from light-gray ink."""
    soft_ink = gray < 220
    strong_ink = gray < 170
    height, width = gray.shape

    row_start = max(0, int(height * 0.45))
    best_horizontal = (row_start, 0, width - 1, 0)
    best_horizontal_score = -1.0
    for row_index in range(row_start, height):
        start, end, run_length = _largest_run_bounds(soft_ink[row_index, :])
        if run_length < max(24, int(width * 0.3)):
            continue
        strong_count = int(np.sum(strong_ink[row_index, start : end + 1]))
        score = (run_length * 3.0) + strong_count + (row_index * 0.1)
        if score > best_horizontal_score:
            best_horizontal = (row_index, start, end, run_length)
            best_horizontal_score = score

    col_end = max(1, int(width * 0.35))
    best_vertical = (0, 0, height - 1, 0)
    best_vertical_score = -1.0
    for col_index in range(col_end):
        start, end, run_length = _largest_run_bounds(soft_ink[:, col_index])
        if run_length < max(24, int(height * 0.25)):
            continue
        strong_count = int(np.sum(strong_ink[start : end + 1, col_index]))
        score = (run_length * 3.0) + strong_count - (col_index * 0.1)
        if score > best_vertical_score:
            best_vertical = (col_index, start, end, run_length)
            best_vertical_score = score

    return best_horizontal, best_vertical


def _to_grayscale_array(image: np.ndarray) -> np.ndarray:
    """Normalize an RGB or grayscale array into an 8-bit grayscale image."""
    if image.ndim == 2:
        return image.astype(np.uint8, copy=False)
    if image.ndim == 3:
        return np.array(Image.fromarray(image.astype(np.uint8)).convert("L"))
    raise ValueError("image array must be 2D grayscale or 3D RGB")


def detect_axis_bounds_from_array(image: np.ndarray) -> AxisBounds:
    """Detect plotting bounds from an already-loaded image array."""
    gray = _to_grayscale_array(image)
    height, width = gray.shape

    best_horizontal, best_vertical = _detect_axis_line_candidates(gray)
    bottom, horizontal_start, horizontal_end, horizontal_run = best_horizontal
    left, top, vertical_end, vertical_run = best_vertical

    if horizontal_run > 0 and vertical_run > 0:
        # When the two axis lines almost intersect, snap them together.
        if abs(horizontal_start - left) <= 4:
            left = min(left, horizontal_start)

        if horizontal_end > left and bottom > top:
            return AxisBounds(left=left, right=horizontal_end, top=top, bottom=bottom)

    non_white = gray < 245
    rows = np.where(non_white.any(axis=1))[0]
    cols = np.where(non_white.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        raise ValueError("Could not detect non-white plotting area")
    return AxisBounds(
        left=int(cols[0]),
        right=int(cols[-1]),
        top=int(rows[0]),
        bottom=int(rows[-1]),
    )


def detect_axis_bounds(image_path: str) -> AxisBounds:
    """Detect plotting bounds from axis lines, with a non-white fallback."""
    return detect_axis_bounds_from_array(np.array(Image.open(image_path).convert("RGB")))


def pixel_to_data(
    x_pixels: np.ndarray,
    y_pixels: np.ndarray,
    axis_bounds: AxisBounds,
    x_axis: XAxisSpec,
    y_axis: YAxisSpec,
    *,
    axis_anchors: AxisAnchors | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Map pixel coordinates onto time and normalized survival coordinates."""
    if axis_anchors is None:
        axis_anchors = AxisAnchors.from_bounds(axis_bounds)

    x_min = axis_anchors.x_min_point.x
    x_max = axis_anchors.x_max_point.x
    y_bottom = axis_anchors.y_min_point.y
    y_top = axis_anchors.y_max_point.y

    x_span = x_max - x_min
    y_span = y_bottom - y_top
    if x_span <= 0 or y_span <= 0:
        raise ValueError("Axis bounds are invalid for conversion")

    x_data = x_axis.min + ((x_pixels - x_min) / x_span) * (x_axis.max - x_axis.min)

    y_min, y_max = y_axis.min, y_axis.max
    y_data = y_max - ((y_pixels - y_top) / y_span) * (y_max - y_min)
    if y_axis.is_percentage:
        y_data = y_data / 100.0

    return x_data.astype(float), y_data.astype(float)


def clean_curve_series(time: np.ndarray, survival: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Sort, clip, deduplicate, and enforce non-increasing survival."""
    _, _, time, survival = clean_curve_points(
        np.arange(len(time), dtype=float),
        np.arange(len(time), dtype=float),
        time,
        survival,
    )
    return time, survival


def clean_curve_points(
    x_pixels: np.ndarray,
    y_pixels: np.ndarray,
    time: np.ndarray,
    survival: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Clean curve arrays while preserving alignment between pixels and data."""
    order = np.argsort(time)
    x_pixels = np.asarray(x_pixels, dtype=float)[order]
    y_pixels = np.asarray(y_pixels, dtype=float)[order]
    time = np.asarray(time, dtype=float)[order]
    survival = np.asarray(survival, dtype=float)[order]

    x_pixels, y_pixels, time, survival = _drop_duplicate_time_points(
        x_pixels,
        y_pixels,
        time,
        survival,
    )
    survival = np.clip(survival, 0.0, 1.0)
    survival = _suppress_isolated_drop_outliers(survival)
    survival = np.minimum.accumulate(survival)
    survival = _collapse_short_drop_runs(survival)
    return _ensure_curve_origin(x_pixels, y_pixels, time, survival)


def _suppress_isolated_drop_outliers(
    survival: np.ndarray,
    *,
    max_run: int = 2,
    min_drop: float = 0.08,
    rebound_tolerance: float = 0.03,
) -> np.ndarray:
    """Remove short downward spikes that immediately rebound on the next columns."""
    if len(survival) < 4:
        return survival

    repaired = survival.copy()
    index = 1
    while index < len(repaired) - 1:
        previous = repaired[index - 1]
        if repaired[index] >= previous - min_drop:
            index += 1
            continue

        end = index
        while end + 1 < len(repaired) and repaired[end + 1] < previous - min_drop:
            end += 1

        run_len = end - index + 1
        if run_len > max_run or end + 1 >= len(repaired):
            index = end + 1
            continue

        rebound = repaired[end + 1]
        if rebound >= previous - rebound_tolerance:
            repaired[index : end + 1] = previous

        index = end + 1

    return repaired


def _collapse_short_drop_runs(survival: np.ndarray, *, max_run: int = 8) -> np.ndarray:
    """Flatten short descending ramps created by thick plotted step edges."""
    if len(survival) < 3:
        return survival

    collapsed = survival.copy()
    index = 1
    while index < len(collapsed):
        if collapsed[index] < collapsed[index - 1] - 1e-9:
            start = index - 1
            end = index
            while end + 1 < len(collapsed) and collapsed[end + 1] < collapsed[end] - 1e-9:
                end += 1
            if end - start <= max_run:
                collapsed[start : end + 1] = collapsed[end]
            index = end + 1
        else:
            index += 1
    return collapsed


def _drop_duplicate_time_points(
    x_pixels: np.ndarray,
    y_pixels: np.ndarray,
    time: np.ndarray,
    survival: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    keep = np.ones(len(time), dtype=bool)
    keep[1:] = np.diff(time) > 0
    return x_pixels[keep], y_pixels[keep], time[keep], survival[keep]


def _ensure_curve_origin(
    x_pixels: np.ndarray,
    y_pixels: np.ndarray,
    time: np.ndarray,
    survival: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if len(time) == 0:
        return x_pixels, y_pixels, time, survival
    if time[0] > 0:
        x_pixels = np.concatenate([[x_pixels[0]], x_pixels])
        y_pixels = np.concatenate([[y_pixels[0]], y_pixels])
        time = np.concatenate([[0.0], time])
        survival = np.concatenate([[1.0], survival])
        return x_pixels, y_pixels, time, survival

    survival[0] = min(1.0, max(survival[0], 0.95))
    return x_pixels, y_pixels, time, survival


def recalibrate_axis_bounds_from_curves(
    axis_bounds: AxisBounds,
    curve_pixel_sets: list[tuple[np.ndarray, np.ndarray]],
) -> AxisBounds:
    """Shift auto-detected left/top bounds to the earliest visible curve start."""
    if not curve_pixel_sets:
        return axis_bounds

    min_x = min(int(np.floor(np.min(x_pixels))) for x_pixels, _ in curve_pixel_sets if len(x_pixels))
    min_y = min(int(np.floor(np.min(y_pixels))) for _, y_pixels in curve_pixel_sets if len(y_pixels))

    left = axis_bounds.left
    top = axis_bounds.top
    width = max(1, axis_bounds.width)
    height = max(1, axis_bounds.height)

    if min_x - axis_bounds.left > max(8, int(width * 0.04)):
        left = min_x
    if min_y - axis_bounds.top > max(8, int(height * 0.04)):
        top = min_y

    return AxisBounds(left=left, right=axis_bounds.right, top=top, bottom=axis_bounds.bottom)
