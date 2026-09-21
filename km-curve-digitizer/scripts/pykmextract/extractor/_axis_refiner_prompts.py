"""Prompt builders for AI-assisted axis refinement."""

from __future__ import annotations

from typing import Any

from ..contracts import AxisAnchorCandidate
from ._axis_refiner_common import ANCHOR_KEYS


def build_axis_review_prompt(
    candidates: dict[str, list[AxisAnchorCandidate]],
    *,
    adjustment_limit: int = 6,
    evidence: dict[str, Any] | None = None,
) -> str:
    """Build the review prompt sent to the VLM."""
    candidate_text = []
    for key in ANCHOR_KEYS:
        candidate_text.append(
            f"{key}: " + ", ".join(
                f"{candidate.id}=({candidate.point.x},{candidate.point.y})"
                for candidate in candidates[key]
            )
        )

    evidence_block = ""
    if evidence is not None:
        evidence_block = f"""

Evidence from the axis-number review:
- origin_intersection_visible: {evidence.get("origin_intersection_visible")}
- x_min_tick_at_intersection: {evidence.get("x_axis", {}).get("min_tick_at_intersection")}
- y_min_tick_at_intersection: {evidence.get("y_axis", {}).get("min_tick_at_intersection")}
- y_max_substantially_below_top_border: {evidence.get("y_axis", {}).get("max_tick_substantially_below_top_border")}
- x_axis labels: min={evidence.get("x_axis", {}).get("min_label_text")}, max={evidence.get("x_axis", {}).get("max_label_text")}
- y_axis labels: min={evidence.get("y_axis", {}).get("min_label_text")}, max={evidence.get("y_axis", {}).get("max_label_text")}
""".rstrip()

    return f"""
You are reviewing four axis calibration anchors on a Kaplan-Meier plot.
The image contains one annotated full view and four zoomed views.
Your task is to choose the best candidate for each anchor and optionally apply a very small pixel offset.

Anchor meanings:
- x_min_point: the pixel on the x-axis line where the minimum labeled x tick meets the axis
- x_max_point: the pixel on the x-axis line where the maximum labeled x tick meets the axis
- y_min_point: the pixel on the y-axis line where the minimum labeled y tick meets the axis
- y_max_point: the pixel on the y-axis line where the maximum labeled y tick meets the axis

{evidence_block}

Candidate ids:
{chr(10).join(candidate_text)}

Rules:
- Use numeric tick labels, their tick marks, and the axis lines as the primary evidence.
- If the minimum labeled x tick and minimum labeled y tick visibly intersect, use that intersection as the shared reference for x_min_point and y_min_point.
- If the evidence says the maximum labeled y tick is substantially below the top border, do not choose the topmost y_max candidate on the plot border.
- Do not use curve position, curve plateaus, tail height, confidence bands, censoring marks, or the plotting frame border as axis anchors.
- Do not choose where a survival curve begins or becomes flat unless that location is exactly the labeled tick on the axis.
- Select exactly one candidate id per anchor.
- Only use integer offsets `dx` and `dy` between -{adjustment_limit} and {adjustment_limit}.
- If the current candidates already look correct, use `decision: "accept"` and keep `dx=0, dy=0`.
- Do not invent new candidate ids.
- Return exactly one JSON object and nothing else.

Valid response example:
{{
  "decision": "adjust",
  "x_min_point": {{"candidate_id": "XMIN_1", "dx": 1, "dy": 0, "confidence": "high"}},
  "x_max_point": {{"candidate_id": "XMAX_2", "dx": 0, "dy": -1, "confidence": "medium"}},
  "y_min_point": {{"candidate_id": "YMIN_1", "dx": 0, "dy": 0, "confidence": "high"}},
  "y_max_point": {{"candidate_id": "YMAX_1", "dx": 1, "dy": 0, "confidence": "high"}},
  "issues": ["x-axis end slightly inside the plotting area"]
}}
""".strip()


def build_axis_evidence_prompt() -> str:
    """Build the prompt used to read axis numbers and tick evidence."""
    return """
You are inspecting axis numbers and tick marks on a Kaplan-Meier plot.
Focus on numeric tick labels, tick marks, and the axis intersection. Do not use the survival curves as evidence.

Return exactly one JSON object and nothing else:
{
  "origin_intersection_visible": bool,
  "x_axis": {
    "min_label_text": str or null,
    "max_label_text": str or null,
    "min_tick_at_intersection": bool or null,
    "max_tick_visible": bool or null
  },
  "y_axis": {
    "min_label_text": str or null,
    "max_label_text": str or null,
    "min_tick_at_intersection": bool or null,
    "max_tick_visible": bool or null,
    "max_tick_substantially_below_top_border": bool or null
  },
  "notes": str
}

Rules:
- Read the axis numbers if visible.
- Judge whether the minimum x tick and minimum y tick meet at the visible axis intersection.
- Judge whether the maximum y tick is clearly below the top border of the plotting region.
- Do not infer from curve height or from where the curve becomes flat.
- Use null if a specific label text is unreadable.
""".strip()
