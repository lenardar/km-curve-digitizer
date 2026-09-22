"""Shared runtime helpers for CLI and batch execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import ExtractionResult
from .pipeline import extract


def load_json_file(path: str | None) -> dict[str, Any] | None:
    """Load a JSON file if a path is provided."""
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_axis_overrides(path: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Load axis bounds and optional anchors from a JSON file."""
    payload = load_json_file(path) or {}
    axis_bounds = payload.get("axis_bounds", payload.get("bounds"))
    axis_anchors = payload.get("axis_anchors", payload.get("anchors"))
    return axis_bounds, axis_anchors


def run_extraction_job(
    image_path: str,
    *,
    semantic: dict[str, Any],
    axis_bounds: dict[str, Any] | None = None,
    axis_anchors: dict[str, Any] | None = None,
) -> ExtractionResult:
    """Run deterministic extraction from model-authored semantic metadata."""
    return extract(
        image_path,
        semantic=semantic,
        axis_bounds=axis_bounds,
        axis_anchors=axis_anchors,
    )


def save_result_json(result: ExtractionResult, output_path: str) -> str:
    """Serialize one extraction result to JSON."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result.to_jsonable(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(output)


def save_axis_json(result: ExtractionResult, output_path: str) -> str:
    """Write final axis bounds and anchors for reuse."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "axis_bounds": result.axis_bounds.model_dump(mode="json"),
                "axis_anchors": result.axis_anchors.model_dump(mode="json"),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return str(output)
