"""Board rendering helpers for axis refinement."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..contracts import AxisAnchorCandidate, AxisBounds
from ._axis_refiner_common import ANCHOR_COLORS, ANCHOR_KEYS


def render_axis_review_board(
    image_path: str,
    candidates: dict[str, list[AxisAnchorCandidate]],
    output_path: str,
    *,
    crop_radius: int = 120,
) -> str:
    """Render one annotated image board for VLM axis review."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    image = np.array(Image.open(image_path).convert("RGB"))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(12, 12))
    grid = GridSpec(3, 2, figure=fig, height_ratios=[2.0, 1.0, 1.0])

    full_ax = fig.add_subplot(grid[0, :])
    full_ax.imshow(image)
    full_ax.set_title("Axis review board | use numeric ticks and axis intersection, not curves")
    full_ax.set_axis_off()
    _plot_candidate_set(full_ax, candidates)

    for index, key in enumerate(ANCHOR_KEYS):
        row = 1 + (index // 2)
        col = index % 2
        ax = fig.add_subplot(grid[row, col])
        center = candidates[key][0].point
        left = max(0, center.x - crop_radius)
        right = min(image.shape[1], center.x + crop_radius)
        top = max(0, center.y - crop_radius)
        bottom = min(image.shape[0], center.y + crop_radius)
        ax.imshow(image[top:bottom, left:right])
        ax.set_title(f"{key} | inspect tick labels and tick marks")
        ax.set_axis_off()
        _plot_candidate_set(ax, {key: candidates[key]}, x_offset=left, y_offset=top)

    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(output)


def render_axis_evidence_board(
    image_path: str,
    bounds: AxisBounds,
    output_path: str,
    *,
    axis_margin: int = 140,
    origin_radius: int = 120,
) -> str:
    """Render a board that highlights x/y numeric tick regions and the axis intersection."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.patches as patches
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    image = np.array(Image.open(image_path).convert("RGB"))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(12, 11))
    grid = GridSpec(2, 2, figure=fig, height_ratios=[1.3, 1.0])

    full_ax = fig.add_subplot(grid[0, :])
    full_ax.imshow(image)
    full_ax.set_title("Axis evidence board | inspect numeric ticks and axis intersection")
    full_ax.set_axis_off()
    rect = patches.Rectangle(
        (bounds.left, bounds.top),
        bounds.width,
        bounds.height,
        linewidth=1.5,
        edgecolor="#111111",
        facecolor="none",
    )
    full_ax.add_patch(rect)
    full_ax.scatter([bounds.left], [bounds.bottom], s=70, color="#1f77b4")
    full_ax.text(bounds.left + 8, bounds.bottom - 8, "Axis intersection", color="#1f77b4", fontsize=9, weight="bold")

    left_margin = max(0, bounds.left - axis_margin)
    right_limit = min(image.shape[1], bounds.left + axis_margin)
    y_label_ax = fig.add_subplot(grid[1, 0])
    y_label_ax.imshow(image[max(0, bounds.top - 30) : min(image.shape[0], bounds.bottom + 30), left_margin:right_limit])
    y_label_ax.set_title("Y-axis labels and tick marks")
    y_label_ax.set_axis_off()

    x_label_ax = fig.add_subplot(grid[1, 1])
    x_top = max(0, bounds.bottom - axis_margin)
    x_left = max(0, bounds.left - 40)
    x_right = min(image.shape[1], bounds.right + 40)
    x_label_ax.imshow(image[x_top : image.shape[0], x_left:x_right])
    x_label_ax.set_title("X-axis labels and axis intersection")
    x_label_ax.set_axis_off()

    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(output)


def _plot_candidate_set(ax: Any, candidates: dict[str, list[AxisAnchorCandidate]], *, x_offset: int = 0, y_offset: int = 0) -> None:
    for key in ANCHOR_KEYS:
        for candidate in candidates.get(key, []):
            x = candidate.point.x - x_offset
            y = candidate.point.y - y_offset
            ax.scatter([x], [y], s=50, color=ANCHOR_COLORS[key], marker="o")
            ax.text(x + 4, y - 4, candidate.id, color=ANCHOR_COLORS[key], fontsize=8, weight="bold")
