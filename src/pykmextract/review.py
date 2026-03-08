"""Visual review helpers for extracted curves."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
from typing import Dict, Optional

import numpy as np
import pandas as pd
from PIL import Image

from .contracts import ExtractionResult


@dataclass(frozen=True)
class ReviewBundleOptions:
    """Options that control how much output a review bundle produces."""

    include_reconstruction: bool = True
    include_ipd_csv: bool = True

    @classmethod
    def lightweight(cls) -> "ReviewBundleOptions":
        """Return a lighter bundle that skips PyHEOR reconstruction outputs."""
        return cls(include_reconstruction=False, include_ipd_csv=False)


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


def save_reconstructed_km_plot(
    result: ExtractionResult,
    output_path: str,
    *,
    ipds: Optional[Dict[str, Dict[str, np.ndarray]]] = None,
) -> str:
    """Plot KM curves re-estimated from reconstructed IPD."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .bridge.pyheor import PyHEORBridge

    bridge = PyHEORBridge()
    ipds = ipds or bridge.extracted_to_ipd(result)
    km_tables = bridge.ipd_to_km(ipds)

    fig, ax = plt.subplots(figsize=(7.5, 5))
    palette = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd"]

    for index, curve in enumerate(result.curves):
        color = palette[index % len(palette)]
        km = km_tables[curve.name]
        ax.step(
            km["time"],
            km["survival"],
            where="post",
            linewidth=2.0,
            color=color,
            label=f"{curve.name} | KM from IPD",
        )
        ax.plot(
            curve.time,
            curve.survival,
            linestyle="--",
            linewidth=1.2,
            color=color,
            alpha=0.6,
            label=f"{curve.name} | digitized",
        )

    x_label = result.semantic.x_axis.label or "Time"
    if result.semantic.x_axis.unit:
        x_label = f"{x_label} ({result.semantic.x_axis.unit})"
    y_label = "Survival probability"
    if result.semantic.y_axis.label:
        y_label = result.semantic.y_axis.label

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_ylim(0, 1.02)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    ax.set_title("Reconstructed KM from IPD")
    fig.tight_layout()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(output)


def save_review_bundle(
    result: ExtractionResult,
    output_dir: str,
    *,
    semantic_context_image: Optional[str] = None,
    citation: Optional[str] = None,
    title: Optional[str] = None,
    options: ReviewBundleOptions | None = None,
) -> Dict[str, str]:
    """Save a full human-review bundle for one extraction job."""
    options = options or ReviewBundleOptions()
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

    ipd_csv_paths = []
    reconstructed_km_path = None
    reconstruction_note = None
    if options.include_reconstruction or options.include_ipd_csv:
        try:
            ipds = result.to_pyheor_ipd()
            if options.include_reconstruction:
                reconstructed_km_path = Path(
                    save_reconstructed_km_plot(result, str(output_root / "reconstructed_km.png"), ipds=ipds)
                )
            if options.include_ipd_csv:
                for curve_name, ipd in ipds.items():
                    curve_slug = _slugify(curve_name)
                    ipd_path = output_root / f"ipd_{curve_slug}.csv"
                    pd.DataFrame({"time": ipd["time"], "event": ipd["event"]}).to_csv(ipd_path, index=False)
                    ipd_csv_paths.append(ipd_path)
        except Exception as exc:
            reconstruction_note = str(exc)
    else:
        reconstruction_note = "Skipped in lightweight review bundle."

    review_md = output_root / "review.md"
    review_md.write_text(
        _build_review_markdown(
            result=result,
            title=title or Path(output_dir).name,
            citation=citation,
            original_image=original_copy,
            overlay_image=overlay_path,
            reconstructed_km_image=reconstructed_km_path,
            digitized_csv=digitized_csv,
            ipd_csv_paths=ipd_csv_paths,
            semantic_context_image=context_copy,
            reconstruction_note=reconstruction_note,
        ),
        encoding="utf-8",
    )

    bundle = {
        "original_image": str(original_copy),
        "overlay": str(overlay_path),
        "digitized_csv": str(digitized_csv),
        "review_md": str(review_md),
    }
    if reconstructed_km_path:
        bundle["reconstructed_km"] = str(reconstructed_km_path)
    if reconstruction_note:
        bundle["reconstruction_note"] = reconstruction_note
    if context_copy:
        bundle["semantic_context_image"] = str(context_copy)
    for path in ipd_csv_paths:
        bundle[f"ipd_{path.stem[4:]}"] = str(path)
    return bundle


def _build_review_markdown(
    *,
    result: ExtractionResult,
    title: str,
    citation: Optional[str],
    original_image: Path,
    overlay_image: Path,
    reconstructed_km_image: Optional[Path],
    digitized_csv: Path,
    ipd_csv_paths: list[Path],
    semantic_context_image: Optional[Path],
    reconstruction_note: Optional[str],
) -> str:
    curve_lines = "\n".join(
        f"- `{curve.name}`: {len(curve.time)} points, tolerance={curve.extraction_tolerance}"
        for curve in result.curves
    )
    ipd_lines = "\n".join(f"- [{path.name}]({path.name})" for path in ipd_csv_paths)
    context_block = ""
    if semantic_context_image:
        context_block = (
            "\n## Semantic Context Figure\n\n"
            f"![semantic-context]({semantic_context_image.name})\n"
        )

    if reconstructed_km_image:
        review_block = (
            "## Side-by-Side Review\n\n"
            "| Original panel | KM redrawn from reconstructed IPD |\n"
            "| --- | --- |\n"
            f"| ![original]({original_image.name}) | ![reconstructed-km]({reconstructed_km_image.name}) |\n"
        )
    else:
        review_block = (
            "## Side-by-Side Review\n\n"
            f"![original]({original_image.name})\n\n"
            f"IPD reconstruction unavailable: `{reconstruction_note or 'unknown error'}`\n"
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

## Overlay

![overlay]({overlay_image.name})
{context_block}

## Curves

{curve_lines}

## Files

- [digitized_curves.csv]({digitized_csv.name})
{ipd_lines}
"""


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    return slug or "curve"
