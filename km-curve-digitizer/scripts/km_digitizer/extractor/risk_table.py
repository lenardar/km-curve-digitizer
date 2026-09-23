"""Geometry-based localization of number-at-risk table cells."""

from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np
from PIL import Image

from ..contracts import AxisAnchors, AxisBounds, SemanticExtraction

if TYPE_CHECKING:
    from ..contracts import ExtractionResult

PixelRegion = Tuple[int, int, int, int]


def ensure_risk_table_cell_regions(result: "ExtractionResult") -> bool:
    """Populate missing risk-cell regions on an existing extraction result."""
    table = result.semantic.at_risk_table
    if result.risk_cell_regions:
        return True
    if not table.time_points or not table.counts_by_curve:
        return False
    image = np.array(Image.open(result.image_path).convert("RGB"))
    regions = locate_risk_table_cells(
        image,
        result.semantic,
        result.axis_bounds,
        result.axis_anchors,
    )
    result.risk_cell_regions = regions
    return bool(regions)


def locate_risk_table_cells(
    image: np.ndarray,
    semantic: SemanticExtraction,
    axis_bounds: AxisBounds,
    axis_anchors: AxisAnchors,
) -> List[List[Optional[PixelRegion]]]:
    """Estimate cell boxes using calibrated time columns and detected text rows.

    This deliberately localizes already-extracted cells; it does not OCR or infer counts.
    An empty list means the row geometry was not reliable enough to expose boxes.
    """
    table = semantic.at_risk_table
    row_count = len(table.counts_by_curve)
    column_count = len(table.time_points)
    if row_count == 0 or column_count == 0 or image.ndim not in {2, 3}:
        return []

    height, width = image.shape[:2]
    if axis_bounds.bottom + 3 >= height:
        return []

    x_span = axis_anchors.x_max_point.x - axis_anchors.x_min_point.x
    data_span = semantic.x_axis.max - semantic.x_axis.min
    if x_span <= 0 or data_span <= 0:
        return []
    centers = np.asarray(
        [
            axis_anchors.x_min_point.x
            + ((time_value - semantic.x_axis.min) / data_span) * x_span
            for time_value in table.time_points
        ],
        dtype=float,
    )
    if np.any(centers < -2) or np.any(centers > width + 2):
        return []

    if image.ndim == 3:
        gray = np.mean(image[..., :3].astype(float), axis=2)
    else:
        gray = image.astype(float)
    dark = gray < 190

    if column_count > 1:
        spacing = float(np.median(np.diff(np.sort(centers))))
    else:
        spacing = max(12.0, axis_bounds.width * 0.15)
    scan_half_width = max(3, min(14, int(round(spacing * 0.28))))
    minimum_occupied_columns = max(1, ceil(column_count * 0.6))

    active_rows: list[int] = []
    for y_value in range(axis_bounds.bottom + 1, height):
        occupied = 0
        for center in centers:
            left = max(0, int(round(center)) - scan_half_width)
            right = min(width, int(round(center)) + scan_half_width + 1)
            occupied += int(bool(np.any(dark[y_value, left:right])))
        if occupied >= minimum_occupied_columns:
            active_rows.append(y_value)

    bands = _group_rows(active_rows, maximum_gap=2)
    bands = [band for band in bands if band[1] - band[0] + 1 >= 3]
    if len(bands) < row_count:
        return []

    # Risk rows normally form the final dense, column-aligned text bands below the plot.
    selected_bands = bands[-row_count:]
    if row_count > 1:
        gaps = [
            selected_bands[index + 1][0] - selected_bands[index][1]
            for index in range(row_count - 1)
        ]
        if any(gap < 1 or gap > max(40, int(axis_bounds.height * 0.2)) for gap in gaps):
            return []

    x_boxes = _cell_horizontal_boxes(centers, width, spacing)
    regions: List[List[Optional[PixelRegion]]] = []
    for band_top, band_bottom in selected_bands:
        top = max(axis_bounds.bottom + 1, band_top - 2)
        bottom = min(height - 1, band_bottom + 2)
        regions.append(
            [
                (x_boxes[index][0], top, x_boxes[index][1], bottom)
                for index in range(column_count)
            ]
        )
    return regions


def _group_rows(rows: list[int], *, maximum_gap: int) -> list[tuple[int, int]]:
    if not rows:
        return []
    bands: list[tuple[int, int]] = []
    start = previous = rows[0]
    for current in rows[1:]:
        if current - previous > maximum_gap:
            bands.append((start, previous))
            start = current
        previous = current
    bands.append((start, previous))
    return bands


def _cell_horizontal_boxes(
    centers: np.ndarray,
    width: int,
    spacing: float,
) -> list[tuple[int, int]]:
    half_width = max(6.0, min(22.0, spacing * 0.38))
    return [
        (
            max(0, int(round(center - half_width))),
            min(width - 1, int(round(center + half_width))),
        )
        for center in centers
    ]
