"""Validation for semantic metadata authored by the calling Codex model."""

from __future__ import annotations

from typing import Any, Dict

from ..contracts import SemanticExtraction
from ..exceptions import SemanticExtractionError


def validate_semantic_output(result: SemanticExtraction) -> tuple[bool, list[str]]:
    """Run lightweight logical checks on model-authored semantic metadata."""
    issues: list[str] = []
    if result.n_curves < 1 or not result.curves:
        issues.append("no curves were described")
    if not (0 <= result.y_axis.min < result.y_axis.max):
        issues.append("y_axis range is invalid")
    if result.at_risk_table.counts_by_curve and (
        len(result.at_risk_table.counts_by_curve) != len(result.curves)
    ):
        issues.append("curve count does not match at-risk row count")
    return not issues, issues


class SemanticExtractor:
    """Validate semantic metadata authored from Codex image inspection."""

    def extract(
        self,
        image_path: str,
        *,
        semantic: Dict[str, Any] | SemanticExtraction | None = None,
    ) -> SemanticExtraction:
        """Return canonical semantic metadata; never call another model."""
        del image_path
        if semantic is None:
            raise SemanticExtractionError(
                "Semantic metadata is required; inspect the image and author semantic JSON."
            )
        parsed = (
            semantic
            if isinstance(semantic, SemanticExtraction)
            else SemanticExtraction.model_validate(semantic)
        )
        ok, issues = validate_semantic_output(parsed)
        if not ok:
            raise SemanticExtractionError("; ".join(issues))
        return parsed
