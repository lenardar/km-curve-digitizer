"""Command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .runtime import (
    ProviderConfig,
    build_enhancement_options,
    load_axis_overrides,
    load_json_file,
    resolve_vision_provider,
    run_extraction_job,
    save_axis_json,
    save_result_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract KM curves from an image")
    parser.add_argument("image", help="Path to the KM figure image")
    parser.add_argument(
        "--semantic-json",
        help="Path to semantic metadata JSON. Required until a live vision provider is configured.",
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
        help="Optional JSON file containing axis_bounds and optionally axis_anchors for manual calibration",
    )
    parser.add_argument(
        "--axis-export-json",
        help="Optional path to write the final axis_bounds and axis_anchors JSON",
    )
    parser.add_argument(
        "--provider",
        choices=["openai-compatible"],
        help="Online semantic provider type",
    )
    parser.add_argument(
        "--base-url",
        help="Base URL for an OpenAI-compatible provider, for example https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    parser.add_argument(
        "--model",
        help="Vision model name, for example qwen-vl-plus or gpt-4o",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable used to read the provider API key",
    )
    parser.add_argument(
        "--axis-refine",
        action="store_true",
        help="Run one extra VLM review pass to refine four axis anchors",
    )
    parser.add_argument(
        "--axis-review-image",
        help="Optional path to save the annotated axis review board image",
    )
    parser.add_argument(
        "--segment-micro-tune",
        action="store_true",
        help="Run one extra VLM pass to propose bounded local step targets after extraction",
    )
    parser.add_argument(
        "--micro-tune-review-image",
        help="Optional path to save the local micro-tune review board image",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        semantic_payload = load_json_file(args.semantic_json)
        axis_bounds, axis_anchors = load_axis_overrides(args.axis_json)
        provider, api_key = resolve_vision_provider(
            ProviderConfig(
                provider=args.provider,
                base_url=args.base_url,
                model=args.model,
                api_key_env=args.api_key_env,
            )
        )
        if provider is None and semantic_payload is None:
            parser.error("Provide either --semantic-json or an online --provider configuration")

        axis_review_image = None
        if args.axis_refine:
            axis_review_image = args.axis_review_image or str(
                Path(args.output_json).with_name("axis_review.png")
            )
        micro_tune_review_image = None
        if args.segment_micro_tune:
            micro_tune_review_image = args.micro_tune_review_image or str(
                Path(args.output_json).with_name("micro_tune_review.png")
            )
        enhancement_options = build_enhancement_options(
            axis_refine=args.axis_refine,
            axis_review_image=axis_review_image,
            segment_micro_tune=args.segment_micro_tune,
            micro_tune_review_image=micro_tune_review_image,
        )
        result = run_extraction_job(
            args.image,
            semantic=semantic_payload,
            provider=provider,
            model=args.model,
            api_key=api_key,
            axis_bounds=axis_bounds,
            axis_anchors=axis_anchors,
            enhancement_options=enhancement_options,
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
