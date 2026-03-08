"""AI-assisted review orchestration for four-point axis anchors."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from ..contracts import AxisAnchors, AxisBounds, AxisReviewResult
from ..providers.vision import VisionProvider
from ._axis_refiner_board import render_axis_evidence_board, render_axis_review_board
from ._axis_refiner_payloads import (
    apply_axis_review,
    generate_axis_anchor_candidates,
    normalize_axis_evidence_payload,
    normalize_axis_review_payload,
    refine_candidates_with_evidence,
)
from ._axis_refiner_prompts import build_axis_evidence_prompt, build_axis_review_prompt


class AxisRefiner:
    """Optional VLM reviewer for four-point axis anchors."""

    def __init__(
        self,
        *,
        candidate_step: int = 4,
        candidate_count: int = 5,
        adjustment_limit: int = 6,
        crop_radius: int = 120,
    ):
        self.candidate_step = candidate_step
        self.candidate_count = candidate_count
        self.adjustment_limit = adjustment_limit
        self.crop_radius = crop_radius

    def refine(
        self,
        image_path: str,
        *,
        axis_bounds: AxisBounds,
        provider: VisionProvider,
        model: str | None = None,
        api_key: str | None = None,
        review_image_path: str | None = None,
    ) -> AxisAnchors:
        """Ask a VLM to select and micro-adjust four axis anchors."""
        candidates = generate_axis_anchor_candidates(
            axis_bounds,
            step=self.candidate_step,
            candidate_count=self.candidate_count,
        )
        cleanup_review = False
        review_image_path, cleanup_review = _ensure_temp_path(
            review_image_path,
            prefix="pykmextract-axis-review-",
        )
        evidence_image_path, cleanup_evidence = _ensure_temp_path(
            None,
            prefix="pykmextract-axis-evidence-",
        )

        try:
            evidence = self._collect_axis_evidence(
                image_path=image_path,
                axis_bounds=axis_bounds,
                provider=provider,
                model=model,
                api_key=api_key,
                evidence_image_path=evidence_image_path,
            )
            candidates = refine_candidates_with_evidence(
                candidates,
                evidence=evidence,
                bounds=axis_bounds,
            )
            review = self._review_anchor_candidates(
                image_path=image_path,
                candidates=candidates,
                provider=provider,
                model=model,
                api_key=api_key,
                evidence=evidence,
                review_image_path=review_image_path,
            )
            return apply_axis_review(
                axis_bounds,
                candidates,
                review,
                adjustment_limit=self.adjustment_limit,
            )
        finally:
            if cleanup_review:
                Path(review_image_path).unlink(missing_ok=True)
            if cleanup_evidence:
                Path(evidence_image_path).unlink(missing_ok=True)

    def _collect_axis_evidence(
        self,
        *,
        image_path: str,
        axis_bounds: AxisBounds,
        provider: VisionProvider,
        model: str | None,
        api_key: str | None,
        evidence_image_path: str,
    ) -> dict:
        render_axis_evidence_board(
            image_path,
            axis_bounds,
            evidence_image_path,
            axis_margin=max(self.crop_radius, 140),
            origin_radius=self.crop_radius,
        )
        evidence_payload = provider.extract_semantics(
            evidence_image_path,
            prompt=build_axis_evidence_prompt(),
            model=model,
            api_key=api_key,
        )
        return normalize_axis_evidence_payload(evidence_payload)

    def _review_anchor_candidates(
        self,
        *,
        image_path: str,
        candidates: dict,
        provider: VisionProvider,
        model: str | None,
        api_key: str | None,
        evidence: dict,
        review_image_path: str,
    ) -> AxisReviewResult:
        render_axis_review_board(
            image_path,
            candidates,
            review_image_path,
            crop_radius=self.crop_radius,
        )
        payload = provider.extract_semantics(
            review_image_path,
            prompt=build_axis_review_prompt(
                candidates,
                adjustment_limit=self.adjustment_limit,
                evidence=evidence,
            ),
            model=model,
            api_key=api_key,
        )
        return AxisReviewResult.model_validate(
            normalize_axis_review_payload(payload, candidates)
        )


def _ensure_temp_path(path: str | None, *, prefix: str) -> tuple[str, bool]:
    """Return a concrete path, allocating a temp file when needed."""
    if path is not None:
        return path, False
    tmp = NamedTemporaryFile(prefix=prefix, suffix=".png", delete=False)
    tmp.close()
    return tmp.name, True


__all__ = [
    "AxisRefiner",
    "apply_axis_review",
    "build_axis_evidence_prompt",
    "build_axis_review_prompt",
    "generate_axis_anchor_candidates",
    "normalize_axis_evidence_payload",
    "normalize_axis_review_payload",
    "refine_candidates_with_evidence",
    "render_axis_evidence_board",
    "render_axis_review_board",
]
