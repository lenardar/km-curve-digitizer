"""Pixel-level KM curve extraction utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import numpy as np
from PIL import Image

from ..contracts import AxisBounds
from ..exceptions import PixelExtractionError


@dataclass(frozen=True)
class _ExtractionStats:
    pixel_count: int
    unique_x_count: int
    x_span: int

    def quality_key(self) -> tuple[int, int, int]:
        return (self.x_span, self.unique_x_count, self.pixel_count)


def load_image_array(image_path: str) -> np.ndarray:
    """Load an image as an RGB numpy array."""
    return np.array(Image.open(image_path).convert("RGB"))


def color_distance_mask(
    pixels: np.ndarray,
    rgb_target: Sequence[int],
    tolerance: int,
) -> np.ndarray:
    """Return a boolean mask using Euclidean RGB distance."""
    target = np.asarray(rgb_target, dtype=int).reshape(1, 1, 3)
    diff = pixels.astype(int) - target
    distance = np.sqrt(np.sum(diff * diff, axis=2))
    mask = distance <= tolerance

    target_span = int(np.max(target) - np.min(target))
    if target_span >= 28:
        pixel_span = np.max(pixels.astype(int), axis=2) - np.min(pixels.astype(int), axis=2)
        mask &= pixel_span >= 8
    return mask


def extract_curve_pixels(
    image_path: str,
    rgb_target: Sequence[int],
    *,
    tolerance: int = 30,
    plot_bounds: AxisBounds | None = None,
    pixels: np.ndarray | None = None,
) -> np.ndarray:
    """Extract raw matching pixels for a single curve."""
    pixels = pixels if pixels is not None else load_image_array(image_path)

    if plot_bounds is not None:
        cropped = pixels[plot_bounds.top : plot_bounds.bottom + 1, plot_bounds.left : plot_bounds.right + 1]
        y_offset = plot_bounds.top
        x_offset = plot_bounds.left
    else:
        cropped = pixels
        y_offset = 0
        x_offset = 0

    mask = color_distance_mask(cropped, rgb_target, tolerance)
    coords = np.argwhere(mask)

    if coords.size == 0:
        return coords.reshape(0, 2)

    coords = coords.astype(int)
    coords[:, 0] += y_offset
    coords[:, 1] += x_offset
    return coords


def adaptive_color_extraction(
    image_path: str,
    rgb_target: Sequence[int],
    *,
    pixels: np.ndarray | None = None,
    plot_bounds: AxisBounds | None = None,
    min_pixels: int = 50,
    min_x_span_ratio: float = 0.75,
    min_unique_x_ratio: float = 0.3,
    tolerance_steps: Iterable[int] = (8, 12, 18, 24, 32, 40, 52, 64),
) -> Tuple[np.ndarray, int]:
    """Increase color tolerance until enough pixels and x coverage are captured."""
    image_pixels = pixels if pixels is not None else load_image_array(image_path)
    best_coords = np.empty((0, 2), dtype=int)
    best_tolerance = 0
    best_stats = _ExtractionStats(pixel_count=0, unique_x_count=0, x_span=0)
    min_x_span, min_unique_x = _minimum_x_coverage_requirements(
        plot_bounds,
        min_x_span_ratio=min_x_span_ratio,
        min_unique_x_ratio=min_unique_x_ratio,
    )

    for tolerance in tolerance_steps:
        coords = extract_curve_pixels(
            image_path,
            rgb_target,
            tolerance=tolerance,
            plot_bounds=plot_bounds,
            pixels=image_pixels,
        )
        stats = _summarize_extraction(coords)
        if stats.quality_key() > best_stats.quality_key():
            best_coords = coords
            best_tolerance = tolerance
            best_stats = stats
        if _meets_extraction_requirements(
            stats,
            min_pixels=min_pixels,
            min_x_span=min_x_span,
            min_unique_x=min_unique_x,
        ):
            return coords, tolerance

    if best_stats.pixel_count >= min_pixels:
        return best_coords, best_tolerance

    raise PixelExtractionError(
        f"Could not find enough pixels for RGB target {tuple(rgb_target)}; "
        f"best match contained {best_stats.pixel_count} pixels across "
        f"{best_stats.unique_x_count} x-columns."
    )


def _minimum_x_coverage_requirements(
    plot_bounds: AxisBounds | None,
    *,
    min_x_span_ratio: float,
    min_unique_x_ratio: float,
) -> tuple[int, int]:
    """Return minimum x-span and unique-column coverage targets."""
    if plot_bounds is None:
        return 0, 0

    width = max(1, plot_bounds.width)
    min_x_span = max(16, int(round(width * min_x_span_ratio)))
    min_unique_x = max(12, int(round(width * min_unique_x_ratio)))
    return min_x_span, min_unique_x


def _summarize_extraction(coords: np.ndarray) -> _ExtractionStats:
    """Summarize raw extracted pixels by count and x coverage."""
    if len(coords) == 0:
        return _ExtractionStats(pixel_count=0, unique_x_count=0, x_span=0)

    unique_x = np.unique(coords[:, 1])
    x_span = int(unique_x[-1] - unique_x[0] + 1)
    return _ExtractionStats(
        pixel_count=int(len(coords)),
        unique_x_count=int(len(unique_x)),
        x_span=x_span,
    )


def _meets_extraction_requirements(
    stats: _ExtractionStats,
    *,
    min_pixels: int,
    min_x_span: int,
    min_unique_x: int,
) -> bool:
    """Decide whether one extraction pass is dense enough to stop."""
    return (
        stats.pixel_count >= min_pixels
        and stats.x_span >= min_x_span
        and stats.unique_x_count >= min_unique_x
    )


def remove_ci_band(coords: np.ndarray, *, image_width: int) -> np.ndarray:
    """Remove dense columns that more likely belong to a filled CI band."""
    if len(coords) == 0:
        return coords

    col_counts = np.bincount(coords[:, 1], minlength=image_width)
    non_zero = col_counts[col_counts > 0]
    if len(non_zero) == 0:
        return coords

    threshold = max(3, int(np.percentile(non_zero, 70)))
    sparse_cols = np.where(col_counts <= threshold)[0]
    return coords[np.isin(coords[:, 1], sparse_cols)]


def pixels_to_curve(
    coords: np.ndarray,
    *,
    x_step: float = 1.0,
    averaging_window: int = 0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Collapse a pixel cloud into a KM-style step curve sampled along x."""
    if len(coords) == 0:
        raise PixelExtractionError("No curve pixels were found")

    x_series, y_values = _collapse_columns_to_lower_envelope(coords)

    if averaging_window > 0:
        y_values = _apply_step_averaging_window(y_values, averaging_window=averaging_window)

    if len(x_series) == 1:
        return x_series, y_values

    x_samples = _build_x_samples(x_series, x_step=x_step)
    y_step = _step_resample_columns(x_series, y_values, x_samples)
    return x_samples, y_step


def _collapse_columns_to_lower_envelope(coords: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Reduce raw matching pixels to one KM-consistent y value per observed x column."""
    order = np.argsort(coords[:, 1], kind="stable")
    ordered = coords[order]
    unique_x = np.unique(ordered[:, 1])
    y_values = np.empty(len(unique_x), dtype=float)

    for index, x_value in enumerate(unique_x):
        column_pixels = ordered[ordered[:, 1] == x_value, 0]
        # KM curves are right-continuous step functions. Taking the lower
        # pixel in each column is more robust on vertical drops than median.
        y_values[index] = float(column_pixels.max())
    return unique_x.astype(float), y_values


def _build_x_samples(x_series: np.ndarray, *, x_step: float) -> np.ndarray:
    """Build a regular x grid while preserving the final observed x column."""
    step = max(float(x_step), 1.0)
    x_samples = np.arange(x_series.min(), x_series.max() + step, step, dtype=float)
    x_samples = x_samples[x_samples <= x_series.max()]
    if x_samples[-1] != x_series[-1]:
        x_samples = np.append(x_samples, x_series[-1])
    return x_samples


def _apply_step_averaging_window(
    y_values: np.ndarray,
    *,
    averaging_window: int,
) -> np.ndarray:
    """Smooth isolated column noise without linearly blending real step drops."""
    if averaging_window <= 0 or len(y_values) < 3:
        return y_values

    smoothed = y_values.copy()
    for index in range(len(y_values)):
        left = max(0, index - averaging_window)
        right = min(len(y_values), index + averaging_window + 1)
        window = y_values[left:right]
        # Preserve the lower envelope so vertical drops remain right-continuous.
        smoothed[index] = float(np.max(window))
    return smoothed


def _step_resample_columns(
    observed_x: np.ndarray,
    observed_y: np.ndarray,
    sample_x: np.ndarray,
) -> np.ndarray:
    """Resample observed columns with right-continuous forward fill."""
    indices = np.searchsorted(observed_x, sample_x, side="right") - 1
    indices = np.clip(indices, 0, len(observed_x) - 1)
    return observed_y[indices].astype(float)


def trim_curve_edge_outliers(
    x_pixels: np.ndarray,
    y_pixels: np.ndarray,
    *,
    plot_bounds: AxisBounds | None = None,
    window: int = 8,
    stable_span: float = 8.0,
    stable_step: float = 4.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Trim unstable leading segments caused by labels, axes, or dark annotations."""
    if len(x_pixels) <= window * 2:
        return x_pixels, y_pixels

    if plot_bounds is not None:
        near_left = x_pixels[0] <= plot_bounds.left + max(8, int(plot_bounds.width * 0.04))
        near_top = y_pixels[0] <= plot_bounds.top + max(8, int(plot_bounds.height * 0.04))
        if near_left and near_top:
            # A KM trace that begins near the calibrated (t=0, S=1) corner may
            # legitimately fall steeply. Do not mistake that evidence for a
            # noisy prefix merely because it is not locally flat.
            return x_pixels, y_pixels

    start_index = _find_stable_start_index(
        y_pixels,
        window=window,
        stable_span=stable_span,
        stable_step=stable_step,
    )
    if start_index >= len(x_pixels):
        return x_pixels, y_pixels
    return x_pixels[start_index:], y_pixels[start_index:]


def _find_stable_start_index(
    y_pixels: np.ndarray,
    *,
    window: int,
    stable_span: float,
    stable_step: float,
) -> int:
    initial = y_pixels[:window]
    if _window_span(initial) <= stable_span and _window_max_step(initial) <= stable_step:
        return 0

    for index in range(0, len(y_pixels) - window + 1):
        segment = y_pixels[index : index + window]
        if _window_span(segment) <= stable_span and _window_max_step(segment) <= stable_step:
            return index
    return 0


def _window_span(values: np.ndarray) -> float:
    return float(np.max(values) - np.min(values))


def _window_max_step(values: np.ndarray) -> float:
    if len(values) < 2:
        return 0.0
    return float(np.max(np.abs(np.diff(values))))
