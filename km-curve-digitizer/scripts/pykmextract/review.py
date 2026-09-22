"""Visual review helpers for extracted curves."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Dict, Optional

import numpy as np
from PIL import Image, ImageDraw

from .contracts import ExtractionResult


def save_overlay(result: ExtractionResult, output_path: str) -> str:
    """Save an overlay image showing extracted curves on top of the source."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.patches as patches
    import matplotlib.pyplot as plt

    image = np.array(Image.open(result.image_path).convert("RGB"))
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(image)

    palette = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd"]
    for index, curve in enumerate(result.curves):
        color = palette[index % len(palette)]
        x_pixels, y_pixels = _curve_data_to_pixel_trace(result, curve)
        ax.plot(
            x_pixels,
            y_pixels,
            linestyle="--",
            drawstyle="steps-post",
            linewidth=1.5,
            color=color,
            label=f"{curve.name} ({curve.extraction_tolerance}px tol)",
        )

    bounds = result.axis_bounds
    rect = patches.Rectangle(
        (bounds.left, bounds.top),
        bounds.width,
        bounds.height,
        linewidth=1.2,
        edgecolor="#111111",
        facecolor="none",
    )
    ax.add_patch(rect)
    # Acceptance is recorded separately by the model-authored review decision.
    # Keep the overlay itself status-neutral so an accepted artifact does not
    # continue to claim that verification is outstanding.
    ax.set_title("KM Curve Digitizer | digitization overlay")
    ax.legend(loc="upper right")
    ax.set_axis_off()
    fig.tight_layout()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(output)


def save_point_review(
    result: ExtractionResult,
    output_path: str,
    *,
    curve_name: str,
    time_range: tuple[float, float] | None = None,
    pixel_region: tuple[float, float, float, float] | None = None,
    max_labels: int = 60,
    annotate: bool = True,
) -> tuple[str, list[dict[str, float | str]]]:
    """Render a local review board with stable point identifiers."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    curve = next((item for item in result.curves if item.name == curve_name), None)
    if curve is None:
        raise ValueError(f"Curve not found: {curve_name}")

    x_pixels = np.asarray(curve.x_pixels, dtype=float)
    y_pixels = np.asarray(curve.y_pixels, dtype=float)
    display_x, display_y = _curve_data_to_pixel_trace(result, curve)
    times = np.asarray(curve.time, dtype=float)
    survival = np.asarray(curve.survival, dtype=float)
    selected = np.ones(len(times), dtype=bool)
    if time_range is not None:
        start, end = time_range
        selected &= (times >= start) & (times <= end)
    if pixel_region is not None:
        left, top, right, bottom = pixel_region
        selected &= (
            (x_pixels >= left)
            & (x_pixels <= right)
            & (y_pixels >= top)
            & (y_pixels <= bottom)
        )

    selected_indices = np.where(selected)[0]
    if len(selected_indices) == 0:
        raise ValueError("The requested inspection region contains no curve points")

    points = [
        {
            "point_id": curve.point_ids[index],
            "x_pixel": float(x_pixels[index]),
            "y_pixel": float(y_pixels[index]),
            "time": float(times[index]),
            "survival": float(survival[index]),
        }
        for index in selected_indices
    ]

    label_count = min(max(1, int(max_labels)), len(selected_indices))
    label_positions = np.linspace(0, len(selected_indices) - 1, label_count, dtype=int)
    label_indices = selected_indices[np.unique(label_positions)]

    image = np.array(Image.open(result.image_path).convert("RGB"))
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.imshow(image)
    if annotate:
        for other in result.curves:
            color = "#777777" if other.name != curve_name else "#0066cc"
            width = 1.0 if other.name != curve_name else 1.8
            alpha = 0.45 if other.name != curve_name else 0.9
            if other.name == curve_name:
                plot_x = display_x[selected_indices]
                plot_y = display_y[selected_indices]
            else:
                plot_x, plot_y = _curve_data_to_pixel_trace(result, other)
            ax.plot(
                plot_x,
                plot_y,
                color=color,
                linewidth=width,
                alpha=alpha,
                drawstyle="steps-post",
            )

        ax.scatter(
            display_x[selected_indices],
            display_y[selected_indices],
            s=22,
            facecolors="none",
            edgecolors="#ff3300",
            linewidths=0.9,
            zorder=4,
        )
        for index in label_indices:
            ax.annotate(
                curve.point_ids[index],
                (display_x[index], display_y[index]),
                xytext=(3, -6),
                textcoords="offset points",
                fontsize=6,
                color="#aa0000",
                zorder=5,
            )

    if pixel_region is not None:
        left, top, right, bottom = pixel_region
    else:
        margin = 20.0
        left = max(0.0, float(display_x[selected_indices].min() - margin))
        right = min(float(image.shape[1]), float(display_x[selected_indices].max() + margin))
        top = max(0.0, float(display_y[selected_indices].min() - margin))
        bottom = min(float(image.shape[0]), float(display_y[selected_indices].max() + margin))
    ax.set_xlim(left, right)
    ax.set_ylim(bottom, top)
    title_prefix = "Point review" if annotate else "Source-only review"
    ax.set_title(f"{title_prefix}: {curve.name} | {len(points)} selected")
    ax.set_axis_off()
    fig.tight_layout()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return str(output), points


def save_risk_table_review(result: ExtractionResult, output_path: str) -> str:
    """Render source-table context beside stable risk-cell identifiers."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    from .extractor.risk_table import ensure_risk_table_cell_regions

    table = result.semantic.at_risk_table
    ensure_risk_table_cell_regions(result)
    records = result.risk_table_records()
    if not records:
        raise ValueError("No number-at-risk table is available for review")

    image = np.array(Image.open(result.image_path).convert("RGB"))
    crop_top = max(0, result.axis_bounds.bottom - 15)
    source_crop = image[crop_top:, :]

    figure_width = max(12.0, 1.25 * (len(table.time_points) + 1))
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(figure_width, 7.5),
        gridspec_kw={"height_ratios": [1.3, 1.0]},
    )
    axes[0].imshow(source_crop)
    axes[0].set_title("Source context below the plotting area")
    for record in records:
        region = record["pixel_region"]
        if not region:
            continue
        left, top, right, bottom = region
        axes[0].add_patch(
            Rectangle(
                (left, top - crop_top),
                right - left,
                bottom - top,
                fill=False,
                edgecolor="#ff7f0e",
                linewidth=0.8,
            )
        )
        axes[0].text(
            left + 1,
            top - crop_top - 1,
            record["cell_id"],
            color="#b23b00",
            fontsize=4,
            va="bottom",
        )
    axes[0].set_axis_off()

    cell_text = []
    for curve_index, curve_spec in enumerate(result.semantic.curves):
        row = []
        for time_index, count in enumerate(table.counts_by_curve[curve_index]):
            cell_id = f"risk-c{curve_spec.id}-t{time_index:03d}"
            value = "?" if count is None else str(count)
            row.append(f"{value}\n{cell_id}")
        cell_text.append(row)

    display = axes[1].table(
        cellText=cell_text,
        rowLabels=[curve.legend_name for curve in result.semantic.curves],
        colLabels=[str(value) for value in table.time_points],
        loc="center",
        cellLoc="center",
    )
    display.auto_set_font_size(False)
    display.set_fontsize(7)
    display.scale(1.0, 1.8)
    axes[1].set_title(
        f"Extracted number-at-risk cells | confidence={result.semantic.confidence.at_risk_table}"
    )
    axes[1].set_axis_off()
    fig.tight_layout()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return str(output)


def _curve_data_to_pixel_trace(result: ExtractionResult, curve) -> tuple[np.ndarray, np.ndarray]:
    """Project cleaned time/survival back into pixel space for review plotting."""
    anchors = result.axis_anchors
    semantic = result.semantic

    x_min = anchors.x_min_point.x
    x_max = anchors.x_max_point.x
    y_top = anchors.y_max_point.y
    y_bottom = anchors.y_min_point.y

    x_span = max(1.0, float(x_max - x_min))
    y_span = max(1.0, float(y_bottom - y_top))
    x_range = semantic.x_axis.max - semantic.x_axis.min
    y_min = semantic.y_axis.min
    y_max = semantic.y_axis.max

    time = np.asarray(curve.time, dtype=float)
    survival = np.asarray(curve.survival, dtype=float)
    x_pixels = x_min + ((time - semantic.x_axis.min) / x_range) * x_span

    if semantic.y_axis.is_percentage:
        survival = survival * 100.0
    y_pixels = y_top + ((y_max - survival) / (y_max - y_min)) * y_span
    return x_pixels, y_pixels


def save_review_bundle(
    result: ExtractionResult,
    output_dir: str,
    *,
    semantic_context_image: Optional[str] = None,
    citation: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, str]:
    """Save a self-contained human-review bundle for one extraction job."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    original_copy = output_root / "original.png"
    shutil.copy2(result.image_path, original_copy)

    context_copy = None
    if semantic_context_image and Path(semantic_context_image).resolve() != Path(result.image_path).resolve():
        context_copy = output_root / "semantic_context.png"
        shutil.copy2(semantic_context_image, context_copy)

    overlay_path = Path(save_overlay(result, str(output_root / "overlay.png")))

    digitized_csv = output_root / "digitized_curves.csv"
    result.curve_frame().to_csv(digitized_csv, index=False)

    validation_csv = output_root / "validation_issues.csv"
    result.validation_frame().to_csv(validation_csv, index=False)

    quality_hotspots = save_quality_hotspots(
        result,
        str(output_root / "quality_hotspots"),
    )
    quality_hotspots_json = output_root / "quality_hotspots.json"
    quality_hotspots_json.write_text(
        json.dumps(quality_hotspots, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    from .extractor.risk_table import ensure_risk_table_cell_regions

    ensure_risk_table_cell_regions(result)
    risk_table_csv = output_root / "risk_table.csv"
    result.risk_table_frame().to_csv(risk_table_csv, index=False)
    risk_table_json = output_root / "risk_table.json"
    risk_records = result.risk_table_records()
    risk_table_json.write_text(
        json.dumps(
            {
                "time_points": result.semantic.at_risk_table.time_points,
                "cells": risk_records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    risk_table_review = None
    if risk_records:
        risk_table_review = Path(
            save_risk_table_review(result, str(output_root / "risk_table_review.png"))
        )

    review_md = output_root / "review.md"
    review_md.write_text(
        _build_review_markdown(
            result=result,
            title=title or Path(output_dir).name,
            citation=citation,
            original_image=original_copy,
            overlay_image=overlay_path,
            digitized_csv=digitized_csv,
            validation_csv=validation_csv,
            quality_hotspots=quality_hotspots,
            quality_hotspots_json=quality_hotspots_json,
            risk_table_csv=risk_table_csv,
            risk_table_json=risk_table_json,
            risk_table_review=risk_table_review,
            semantic_context_image=context_copy,
        ),
        encoding="utf-8",
    )

    bundle = {
        "original_image": str(original_copy),
        "overlay": str(overlay_path),
        "digitized_csv": str(digitized_csv),
        "validation_csv": str(validation_csv),
        "quality_hotspots_json": str(quality_hotspots_json),
        "risk_table_csv": str(risk_table_csv),
        "risk_table_json": str(risk_table_json),
        "review_md": str(review_md),
    }
    if risk_table_review:
        bundle["risk_table_review"] = str(risk_table_review)
    if context_copy:
        bundle["semantic_context_image"] = str(context_copy)
    return bundle


def save_quality_hotspots(
    result: ExtractionResult,
    output_dir: str,
    *,
    padding: int = 6,
    scale: int = 4,
) -> list[dict]:
    """Export enlarged source/overlay boards for findings requiring visual review."""
    source = Image.open(result.image_path).convert("RGB")
    overlay = source.copy()
    overlay_draw = ImageDraw.Draw(overlay)
    palette = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00"]
    for curve_index, curve in enumerate(result.curves):
        x_pixels, y_pixels = _curve_data_to_pixel_trace(result, curve)
        color = palette[curve_index % len(palette)]
        for index in range(1, len(x_pixels)):
            previous = (float(x_pixels[index - 1]), float(y_pixels[index - 1]))
            corner = (float(x_pixels[index]), float(y_pixels[index - 1]))
            current = (float(x_pixels[index]), float(y_pixels[index]))
            overlay_draw.line([previous, corner, current], fill=color, width=2)
    output_root = Path(output_dir)
    records: list[dict] = []

    for issue in result.validation.issues:
        if not issue.requires_visual_review or issue.pixel_region is None:
            continue
        left, top, right, bottom = issue.pixel_region
        left = max(0, int(left) - padding)
        top = max(0, int(top) - padding)
        right = min(source.width, int(right) + padding + 1)
        bottom = min(source.height, int(bottom) + padding + 1)
        if right <= left or bottom <= top:
            continue

        output_root.mkdir(parents=True, exist_ok=True)
        source_crop = source.crop((left, top, right, bottom))
        overlay_crop = overlay.crop((left, top, right, bottom))
        scaled_size = (
            max(1, source_crop.width * scale),
            max(1, source_crop.height * scale),
        )
        source_crop = source_crop.resize(
            scaled_size,
            Image.Resampling.NEAREST,
        )
        overlay_crop = overlay_crop.resize(scaled_size, Image.Resampling.NEAREST)
        label_height = 34
        gap = 12
        board = Image.new(
            "RGB",
            (max(960, source_crop.width * 2 + gap), source_crop.height + label_height),
            "white",
        )
        board.paste(source_crop, (0, label_height))
        board.paste(overlay_crop, (source_crop.width + gap, label_height))
        board_draw = ImageDraw.Draw(board)
        board_draw.text((8, 8), f"{issue.issue_id}: {issue.code}", fill="black")
        board_draw.text((source_crop.width + gap + 8, 8), "extraction overlay", fill="black")
        filename = f"{issue.issue_id}.png"
        output_path = output_root / filename
        board.save(output_path)
        records.append(
            {
                "issue_id": issue.issue_id,
                "code": issue.code,
                "message": issue.message,
                "curve_ids": issue.curve_ids,
                "time_range": issue.time_range,
                "pixel_region": [left, top, right - 1, bottom - 1],
                "image": str(Path(output_root.name) / filename),
            }
        )
    return records


def _build_review_markdown(
    *,
    result: ExtractionResult,
    title: str,
    citation: Optional[str],
    original_image: Path,
    overlay_image: Path,
    digitized_csv: Path,
    validation_csv: Path,
    quality_hotspots: list[dict],
    quality_hotspots_json: Path,
    risk_table_csv: Path,
    risk_table_json: Path,
    risk_table_review: Optional[Path],
    semantic_context_image: Optional[Path],
) -> str:
    curve_lines = "\n".join(
        f"- `{curve.name}`: {len(curve.time)} points, tolerance={curve.extraction_tolerance}"
        for curve in result.curves
    )
    issue_lines = "\n".join(
        f"- `{issue.code}`: {issue.message}"
        for issue in result.validation.issues
    ) or "- None"
    context_block = ""
    if semantic_context_image:
        context_block = (
            "\n## Semantic Context Figure\n\n"
            f"![semantic-context]({semantic_context_image.name})\n"
        )

    risk_block = "\n## Number at Risk\n\n"
    if risk_table_review:
        risk_block += f"![number-at-risk review]({risk_table_review.name})\n"
    else:
        risk_block += "No number-at-risk table was extracted.\n"

    review_block = (
        "## Side-by-Side Review\n\n"
        "| Original panel | Digitization overlay |\n"
        "| --- | --- |\n"
        f"| ![original]({original_image.name}) | ![overlay]({overlay_image.name}) |\n"
    )

    hotspot_block = "\n## Required Local Reviews\n\n"
    if quality_hotspots:
        hotspot_block += "Acceptance requires comparing the source-only and overlay panes for every issue ID below.\n\n"
        hotspot_block += "\n".join(
            f"- `{item['issue_id']}`: [{item['code']}]({item['image']}) — {item['message']}"
            for item in quality_hotspots
        )
        hotspot_block += "\n"
    else:
        hotspot_block += "No automatically localized high-risk regions.\n"

    return f"""# Review Bundle: {title}

## Summary

- Visual acceptance: `pending model review`
- Diagnostic checks: `{sum(result.validation.checks.values())}/{len(result.validation.checks)} passed` (navigation only)
- Diagnostic issues: `{len(result.validation.issues)}`
- Image: `{Path(result.image_path).name}`
- Notes: {result.semantic.notes or "None"}

## Citation

{citation or "Not provided"}

{review_block}

{hotspot_block}

{context_block}

{risk_block}

## Curves

{curve_lines}

## Validation Issues

{issue_lines}

## Files

- [digitized_curves.csv]({digitized_csv.name})
- [validation_issues.csv]({validation_csv.name})
- [quality_hotspots.json]({quality_hotspots_json.name})
- [risk_table.csv]({risk_table_csv.name})
- [risk_table.json]({risk_table_json.name})
"""
