"""Candidate generation and payload normalization for axis refinement."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..contracts import AxisAnchorCandidate, AxisAnchors, AxisBounds, AxisReviewResult, PixelPoint
from ._axis_refiner_common import (
    ANCHOR_ALIASES,
    ANCHOR_KEYS,
    candidate_lookup,
    candidate_offsets,
    clamp,
    normalize_confidence,
    normalize_optional_bool,
    normalize_optional_text,
)


def generate_axis_anchor_candidates(
    bounds: AxisBounds,
    *,
    step: int = 4,
    candidate_count: int = 5,
) -> dict[str, list[AxisAnchorCandidate]]:
    """Generate a small set of axis anchor candidates from a plotting box."""
    count = max(1, candidate_count)
    x_offsets = candidate_offsets(bounds.width, step=step, candidate_count=count)
    y_offsets = candidate_offsets(bounds.height, step=step, candidate_count=count)
    return {
        "x_min_point": [
            AxisAnchorCandidate(
                id=f"XMIN_{index + 1}",
                point=PixelPoint(x=min(bounds.right, bounds.left + offset), y=bounds.bottom),
            )
            for index, offset in enumerate(x_offsets)
        ],
        "x_max_point": [
            AxisAnchorCandidate(
                id=f"XMAX_{index + 1}",
                point=PixelPoint(x=max(bounds.left, bounds.right - offset), y=bounds.bottom),
            )
            for index, offset in enumerate(x_offsets)
        ],
        "y_min_point": [
            AxisAnchorCandidate(
                id=f"YMIN_{index + 1}",
                point=PixelPoint(x=bounds.left, y=max(bounds.top, bounds.bottom - offset)),
            )
            for index, offset in enumerate(y_offsets)
        ],
        "y_max_point": [
            AxisAnchorCandidate(
                id=f"YMAX_{index + 1}",
                point=PixelPoint(x=bounds.left, y=min(bounds.bottom, bounds.top + offset)),
            )
            for index, offset in enumerate(y_offsets)
        ],
    }


def normalize_axis_review_payload(
    payload: dict[str, Any],
    candidates: dict[str, list[AxisAnchorCandidate]],
) -> dict[str, Any]:
    """Normalize a raw VLM response into the review schema."""
    normalized: dict[str, Any] = {"decision": str(payload.get("decision") or "accept").lower()}

    raw_issues = payload.get("issues") or []
    if isinstance(raw_issues, str):
        normalized["issues"] = [raw_issues]
    elif isinstance(raw_issues, list):
        normalized["issues"] = [str(item) for item in raw_issues]
    else:
        normalized["issues"] = []

    for key in ANCHOR_KEYS:
        raw_value = payload.get(key)
        if raw_value is None:
            alias = next((alias for alias, canonical in ANCHOR_ALIASES.items() if canonical == key), None)
            raw_value = payload.get(alias) if alias else None

        if isinstance(raw_value, str):
            raw_value = {"candidate_id": raw_value}
        if not isinstance(raw_value, dict):
            raw_value = {}

        default_candidate = candidates[key][0]
        normalized[key] = {
            "candidate_id": str(raw_value.get("candidate_id") or default_candidate.id),
            "dx": int(raw_value.get("dx") or 0),
            "dy": int(raw_value.get("dy") or 0),
            "confidence": normalize_confidence(raw_value.get("confidence")),
        }

    return normalized


def normalize_axis_evidence_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw VLM response for axis number evidence."""
    x_axis = payload.get("x_axis") if isinstance(payload.get("x_axis"), dict) else {}
    y_axis = payload.get("y_axis") if isinstance(payload.get("y_axis"), dict) else {}
    notes = payload.get("notes") or ""
    return {
        "origin_intersection_visible": normalize_optional_bool(payload.get("origin_intersection_visible")),
        "x_axis": {
            "min_label_text": normalize_optional_text(x_axis.get("min_label_text")),
            "max_label_text": normalize_optional_text(x_axis.get("max_label_text")),
            "min_tick_at_intersection": normalize_optional_bool(x_axis.get("min_tick_at_intersection")),
            "max_tick_visible": normalize_optional_bool(x_axis.get("max_tick_visible")),
        },
        "y_axis": {
            "min_label_text": normalize_optional_text(y_axis.get("min_label_text")),
            "max_label_text": normalize_optional_text(y_axis.get("max_label_text")),
            "min_tick_at_intersection": normalize_optional_bool(y_axis.get("min_tick_at_intersection")),
            "max_tick_visible": normalize_optional_bool(y_axis.get("max_tick_visible")),
            "max_tick_substantially_below_top_border": normalize_optional_bool(
                y_axis.get("max_tick_substantially_below_top_border")
            ),
        },
        "notes": str(notes),
    }


def apply_axis_review(
    bounds: AxisBounds,
    candidates: dict[str, list[AxisAnchorCandidate]],
    review: AxisReviewResult,
    *,
    adjustment_limit: int = 6,
) -> AxisAnchors:
    """Resolve reviewed candidates into concrete axis anchors."""
    resolved: dict[str, PixelPoint] = {}
    for key in ANCHOR_KEYS:
        selection = getattr(review, key)
        candidate = candidate_lookup(candidates[key]).get(selection.candidate_id, candidates[key][0])
        dx = clamp(selection.dx, -adjustment_limit, adjustment_limit)
        dy = clamp(selection.dy, -adjustment_limit, adjustment_limit)
        resolved[key] = PixelPoint(
            x=clamp(candidate.point.x + dx, bounds.left, bounds.right),
            y=clamp(candidate.point.y + dy, bounds.top, bounds.bottom),
        )
    return AxisAnchors(**resolved)


def refine_candidates_with_evidence(
    candidates: dict[str, list[AxisAnchorCandidate]],
    *,
    evidence: dict[str, Any],
    bounds: AxisBounds,
) -> dict[str, list[AxisAnchorCandidate]]:
    """Apply simple candidate constraints from the axis-number evidence pass."""
    refined = deepcopy(candidates)
    max_x_inset = max(12, int(bounds.width * 0.05))
    max_y_inset = max(12, int(bounds.height * 0.05))

    xmax_near_axis_end = [
        candidate
        for candidate in refined["x_max_point"]
        if bounds.right - candidate.point.x <= max_x_inset
    ]
    if xmax_near_axis_end:
        refined["x_max_point"] = xmax_near_axis_end

    ymin_near_axis_end = [
        candidate
        for candidate in refined["y_min_point"]
        if bounds.bottom - candidate.point.y <= max_y_inset
    ]
    if ymin_near_axis_end:
        refined["y_min_point"] = ymin_near_axis_end

    y_axis = evidence.get("y_axis", {})
    if y_axis.get("max_tick_substantially_below_top_border") is True:
        min_interior_offset = max(12, int(bounds.height * 0.08))
        interior = [
            candidate
            for candidate in refined["y_max_point"]
            if candidate.point.y - bounds.top >= min_interior_offset
        ]
        if interior:
            refined["y_max_point"] = interior
    return refined
