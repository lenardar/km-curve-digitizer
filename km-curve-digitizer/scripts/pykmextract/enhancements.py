"""Optional AI enhancement orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import ExtractionResult
from .extractor import AxisRefiner
from .microtune import SegmentMicroTuner
from .pipeline import extract
from .providers import VisionProvider


@dataclass(frozen=True)
class AIEnhancementOptions:
    """Optional AI enhancements applied after the default extraction run."""

    axis_refine: bool = False
    axis_review_image: str | None = None
    segment_micro_tune: bool = False
    micro_tune_review_image: str | None = None

    def enabled(self) -> bool:
        """Return whether any AI enhancement is enabled."""
        return self.axis_refine or self.segment_micro_tune


def apply_ai_enhancements(
    result: ExtractionResult,
    *,
    provider: VisionProvider | None,
    model: str | None = None,
    api_key: str | None = None,
    options: AIEnhancementOptions | None = None,
    axis_refiner: AxisRefiner | None = None,
    segment_micro_tuner: SegmentMicroTuner | None = None,
) -> ExtractionResult:
    """Apply optional AI refinement steps without changing the default pipeline."""
    options = options or AIEnhancementOptions()
    if not options.enabled():
        return result
    if options.axis_refine and provider is None:
        raise ValueError("--axis-refine requires an online --provider configuration")
    if options.segment_micro_tune and provider is None:
        raise ValueError("--segment-micro-tune requires an online --provider configuration")

    refined_result = result
    if options.axis_refine:
        refined_result = _apply_axis_refinement(
            refined_result,
            provider=provider,
            model=model,
            api_key=api_key,
            axis_review_image=options.axis_review_image,
            axis_refiner=axis_refiner,
        )
    if options.segment_micro_tune:
        refined_result = _apply_segment_micro_tune(
            refined_result,
            provider=provider,
            model=model,
            api_key=api_key,
            micro_tune_review_image=options.micro_tune_review_image,
            segment_micro_tuner=segment_micro_tuner,
        )
    return refined_result


def _apply_axis_refinement(
    result: ExtractionResult,
    *,
    provider: VisionProvider | None,
    model: str | None,
    api_key: str | None,
    axis_review_image: str | None,
    axis_refiner: AxisRefiner | None,
) -> ExtractionResult:
    refiner = axis_refiner or AxisRefiner()
    axis_anchors = refiner.refine(
        result.image_path,
        axis_bounds=result.axis_bounds,
        provider=provider,
        model=model,
        api_key=api_key,
        review_image_path=axis_review_image,
    )
    return extract(
        result.image_path,
        semantic=result.semantic,
        axis_bounds=result.axis_bounds,
        axis_anchors=axis_anchors,
    )


def _apply_segment_micro_tune(
    result: ExtractionResult,
    *,
    provider: VisionProvider | None,
    model: str | None,
    api_key: str | None,
    micro_tune_review_image: str | None,
    segment_micro_tuner: SegmentMicroTuner | None,
) -> ExtractionResult:
    tuner = segment_micro_tuner or SegmentMicroTuner()
    return tuner.refine(
        result,
        provider=provider,
        model=model,
        api_key=api_key,
        review_image_path=micro_tune_review_image,
    )
