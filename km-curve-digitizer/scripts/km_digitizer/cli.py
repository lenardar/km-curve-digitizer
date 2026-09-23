"""Command-line entry point."""

from __future__ import annotations

import argparse
from .runtime import (
    load_axis_overrides,
    load_json_file,
    run_extraction_job,
    save_axis_json,
    save_result_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract KM curves from an image")
    parser.add_argument("image", help="Path to the KM figure image")
    parser.add_argument(
        "--semantic-json",
        required=True,
        help="Path to semantic metadata JSON authored from the calling model's image inspection",
    )
    parser.add_argument(
        "--output-json",
        default="extraction_result.json",
        help="Path to write the structured extraction result JSON",
    )
    parser.add_argument(
        "--overlay",
        help="Optional path to save a visual overlay review image",
    )
    parser.add_argument(
        "--review-dir",
        help="Optional directory to save a review bundle with markdown, overlay, and CSV outputs",
    )
    parser.add_argument(
        "--review-title",
        help="Optional title used inside the review bundle markdown",
    )
    parser.add_argument(
        "--citation",
        help="Optional citation text included in the review bundle markdown",
    )
    parser.add_argument(
        "--axis-json",
        help="Optional JSON file containing model-reviewed axis_bounds and optionally axis_anchors",
    )
    parser.add_argument(
        "--axis-export-json",
        help="Optional path to write the final axis_bounds and axis_anchors JSON",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        semantic_payload = load_json_file(args.semantic_json)
        axis_bounds, axis_anchors = load_axis_overrides(args.axis_json)
        result = run_extraction_job(
            args.image,
            semantic=semantic_payload,
            axis_bounds=axis_bounds,
            axis_anchors=axis_anchors,
        )
    except ValueError as exc:
        parser.error(str(exc))

    save_result_json(result, args.output_json)

    if args.axis_export_json:
        save_axis_json(result, args.axis_export_json)

    if args.overlay:
        result.save_overlay(args.overlay)

    if args.review_dir:
        result.save_review_bundle(
            args.review_dir,
            title=args.review_title,
            citation=args.citation,
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
