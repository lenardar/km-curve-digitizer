"""Shared constants and helpers for axis refinement."""

from __future__ import annotations

from typing import Any

from ..contracts import AxisAnchorCandidate, ConfidenceLevel

ANCHOR_KEYS = ("x_min_point", "x_max_point", "y_min_point", "y_max_point")
ANCHOR_COLORS = {
    "x_min_point": "#1f77b4",
    "x_max_point": "#ff7f0e",
    "y_min_point": "#2ca02c",
    "y_max_point": "#d62728",
}
ANCHOR_ALIASES = {
    "x_min": "x_min_point",
    "x_max": "x_max_point",
    "y_min": "y_min_point",
    "y_max": "y_max_point",
}


def candidate_lookup(candidates: list[AxisAnchorCandidate]) -> dict[str, AxisAnchorCandidate]:
    """Index candidates by id."""
    return {candidate.id: candidate for candidate in candidates}


def normalize_confidence(value: Any) -> str:
    """Normalize raw confidence text into the constrained enum values."""
    if isinstance(value, str):
        lowered = value.lower().strip()
        if lowered in {ConfidenceLevel.HIGH.value, ConfidenceLevel.MEDIUM.value, ConfidenceLevel.LOW.value}:
            return lowered
    return ConfidenceLevel.MEDIUM.value


def clamp(value: int, minimum: int, maximum: int) -> int:
    """Clamp one integer value to a closed interval."""
    return max(minimum, min(maximum, int(value)))


def candidate_offsets(span: int, *, step: int, candidate_count: int) -> list[int]:
    """Generate local-to-wide offsets while keeping early candidates near the axis."""
    max_offset = max(0, span)
    offsets: list[int] = []
    for index in range(candidate_count):
        offset = step * (index**2)
        offsets.append(min(max_offset, offset))
    return offsets


def normalize_optional_bool(value: Any) -> bool | None:
    """Normalize loosely formatted booleans from VLM output."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower().strip()
        if lowered in {"true", "yes"}:
            return True
        if lowered in {"false", "no"}:
            return False
    return None


def normalize_optional_text(value: Any) -> str | None:
    """Normalize optional text values from VLM output."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
