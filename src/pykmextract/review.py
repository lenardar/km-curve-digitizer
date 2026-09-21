"""Visual review helpers for extracted curves."""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Dict, Optional

import numpy as np
from PIL import Image

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
    ax.set_title(f"PyKMExtract review overlay | score={result.validation.score}")
    ax.legend(loc="upper right")
    ax.set_axis_off()
    fig.tight_layout()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight")
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
            semantic_context_image=context_copy,
        ),
        encoding="utf-8",
    )

    bundle = {
        "original_image": str(original_copy),
        "overlay": str(overlay_path),
        "digitized_csv": str(digitized_csv),
        "validation_csv": str(validation_csv),
        "review_md": str(review_md),
    }
    if context_copy:
        bundle["semantic_context_image"] = str(context_copy)
    return bundle


def _build_review_markdown(
    *,
    result: ExtractionResult,
    title: str,
    citation: Optional[str],
    original_image: Path,
    overlay_image: Path,
    digitized_csv: Path,
    validation_csv: Path,
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

    review_block = (
        "## Side-by-Side Review\n\n"
        "| Original panel | Digitization overlay |\n"
        "| --- | --- |\n"
        f"| ![original]({original_image.name}) | ![overlay]({overlay_image.name}) |\n"
    )

    return f"""# Review Bundle: {title}

## Summary

- Validation score: `{result.validation.score}`
- Validation level: `{result.validation.level}`
- Image: `{Path(result.image_path).name}`
- Notes: {result.semantic.notes or "None"}

## Citation

{citation or "Not provided"}

{review_block}

{context_block}

## Curves

{curve_lines}

## Validation Issues

{issue_lines}

## Files

- [digitized_curves.csv]({digitized_csv.name})
- [validation_issues.csv]({validation_csv.name})
"""
