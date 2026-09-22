"""Batch execution of grouped KM image extraction jobs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .datasets import build_real_km_manifest
from .runtime import (
    ProviderConfig,
    build_enhancement_options,
    resolve_vision_provider,
    run_extraction_job,
    save_result_json,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run batch extraction over grouped KM study images")
    parser.add_argument(
        "--image-dir",
        default="images",
        help="Directory containing grouped study images",
    )
    parser.add_argument(
        "--literature-md",
        default="images/literatures.md",
        help="Optional markdown file with literature references",
    )
    parser.add_argument(
        "--provider",
        choices=["openai-compatible"],
        default="openai-compatible",
        help="Semantic extraction provider type",
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL for the OpenAI-compatible endpoint",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Vision-capable model name",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable used to load the API key",
    )
    parser.add_argument(
        "--output-dir",
        default="runs/latest",
        help="Directory where extraction results will be written",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit on the number of panel jobs to run",
    )
    parser.add_argument(
        "--axis-refine",
        action="store_true",
        help="Opt in to one internal-provider VLM axis pass per panel",
    )
    parser.add_argument(
        "--segment-micro-tune",
        action="store_true",
        help="Opt in to one internal-provider VLM curve-adjustment pass per panel",
    )
    return parser


def _focus_hint(endpoint: str) -> str:
    return (
        f"The image may contain multiple Kaplan-Meier panels. "
        f"Focus only on the {endpoint.upper()} panel. "
        f"If legend or color mapping appears elsewhere in the figure, use it to label "
        f"the curves in this {endpoint.upper()} panel. "
        f"Ignore the other panels when reporting axes, at-risk values, and total events."
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        provider, api_key = resolve_vision_provider(
            ProviderConfig(
                provider=args.provider,
                base_url=args.base_url,
                model=args.model,
                api_key_env=args.api_key_env,
            )
        )
    except ValueError as exc:
        parser.error(str(exc))

    manifest = build_real_km_manifest(args.image_dir, literature_md=args.literature_md)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    limit = args.limit if args.limit and args.limit > 0 else None
    jobs = manifest["plan"][:limit]
    summary = []

    for job in jobs:
        study_id = job["study_id"]
        endpoint = job["endpoint"]
        image_path = job["image"]
        semantic_context = job["semantic_context_image"]

        job_name = f"{study_id}_{endpoint}"
        study_dir = output_dir / study_id
        study_dir.mkdir(parents=True, exist_ok=True)
        job_dir = study_dir / endpoint
        job_dir.mkdir(parents=True, exist_ok=True)

        axis_review_image = str(job_dir / "axis_review.png") if args.axis_refine else None
        micro_tune_review_image = str(job_dir / "micro_tune_review.png") if args.segment_micro_tune else None
        enhancement_options = build_enhancement_options(
            axis_refine=args.axis_refine,
            axis_review_image=axis_review_image,
            segment_micro_tune=args.segment_micro_tune,
            micro_tune_review_image=micro_tune_review_image,
        )

        result = run_extraction_job(
            image_path,
            provider=provider,
            model=args.model,
            api_key=api_key,
            semantic_image=semantic_context,
            semantic_focus_hint=_focus_hint(endpoint),
            enhancement_options=enhancement_options,
        )

        result_path = job_dir / "result.json"
        save_result_json(result, str(result_path))
        review_bundle = result.save_review_bundle(
            str(job_dir),
            semantic_context_image=semantic_context,
            citation=job.get("citation"),
            title=job_name,
        )

        summary.append(
            {
                "study_id": study_id,
                "endpoint": endpoint,
                "image": image_path,
                "semantic_context_image": semantic_context,
                "diagnostic_checks": result.validation.checks,
                "diagnostic_issue_count": len(result.validation.issues),
                "result_json": str(result_path),
                "overlay": review_bundle["overlay"],
                "digitized_csv": review_bundle["digitized_csv"],
                "validation_csv": review_bundle["validation_csv"],
                "risk_table_csv": review_bundle["risk_table_csv"],
                "risk_table_json": review_bundle["risk_table_json"],
                "review_md": review_bundle["review_md"],
            }
        )
        if axis_review_image:
            summary[-1]["axis_review_image"] = axis_review_image
        if micro_tune_review_image:
            summary[-1]["micro_tune_review_image"] = micro_tune_review_image
    (output_dir / "summary.json").write_text(
        json.dumps({"jobs": summary}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
