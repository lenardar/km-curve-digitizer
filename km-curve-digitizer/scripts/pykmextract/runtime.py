"""Shared runtime helpers for CLI and batch execution."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

from .contracts import ExtractionResult
from .enhancements import AIEnhancementOptions, apply_ai_enhancements
from .pipeline import extract
from .providers import OpenAICompatibleVisionProvider, VisionProvider


@dataclass(frozen=True)
class ProviderConfig:
    """Runtime configuration for an optional online vision provider."""

    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key_env: str = "OPENAI_API_KEY"


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


def resolve_vision_provider(config: ProviderConfig) -> tuple[VisionProvider | None, str | None]:
    """Instantiate an online provider from runtime config."""
    if config.provider is None:
        return None, None
    if config.provider != "openai-compatible":
        raise ValueError(f"Unsupported provider: {config.provider}")
    if not config.base_url:
        raise ValueError("--base-url is required when --provider=openai-compatible")
    if not config.model:
        raise ValueError("--model is required when --provider=openai-compatible")

    api_key = os.getenv(config.api_key_env)
    if not api_key:
        raise ValueError(f"{config.api_key_env} is not set")

    provider = OpenAICompatibleVisionProvider(
        base_url=config.base_url,
        api_key=api_key,
        default_model=config.model,
    )
    return provider, api_key


def build_enhancement_options(
    *,
    axis_refine: bool = False,
    axis_review_image: str | None = None,
    segment_micro_tune: bool = False,
    micro_tune_review_image: str | None = None,
) -> AIEnhancementOptions:
    """Construct a consistent enhancement options object."""
    return AIEnhancementOptions(
        axis_refine=axis_refine,
        axis_review_image=axis_review_image,
        segment_micro_tune=segment_micro_tune,
        micro_tune_review_image=micro_tune_review_image,
    )


def run_extraction_job(
    image_path: str,
    *,
    semantic: dict[str, Any] | None = None,
    provider: VisionProvider | None = None,
    model: str | None = None,
    api_key: str | None = None,
    axis_bounds: dict[str, Any] | None = None,
    axis_anchors: dict[str, Any] | None = None,
    semantic_image: str | None = None,
    semantic_focus_hint: str | None = None,
    enhancement_options: AIEnhancementOptions | None = None,
) -> ExtractionResult:
    """Run the default extraction flow and optional AI enhancements."""
    result = extract(
        image_path,
        semantic=semantic,
        vision_provider=provider,
        llm=model,
        api_key=api_key,
        axis_bounds=axis_bounds,
        axis_anchors=axis_anchors,
        semantic_image=semantic_image,
        semantic_focus_hint=semantic_focus_hint,
    )
    return apply_ai_enhancements(
        result,
        provider=provider,
        model=model,
        api_key=api_key,
        options=enhancement_options,
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
