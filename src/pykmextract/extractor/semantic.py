"""Semantic extraction orchestration and normalization."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..contracts import SemanticExtraction
from ..exceptions import SemanticExtractionError
from ..providers.vision import VisionProvider

SYSTEM_PROMPT = """
You are a Kaplan-Meier chart digitization assistant.
Return exactly one JSON object and nothing else.
Do not return markdown, code fences, prose, or any extra top-level keys.
Do not invent values. If information is truly absent, use null or [] as required.
If the figure contains multiple panels, follow the focus instruction strictly, but you may use
shared legend or shared at-risk context from other parts of the same figure when relevant.
""".strip()

USER_PROMPT = """
Extract semantic metadata from a Kaplan-Meier survival plot into exactly this schema:
{
  "n_curves": int,
  "x_axis": {
    "min": float,
    "max": float,
    "unit": str,
    "label": str
  },
  "y_axis": {
    "min": float,
    "max": float,
    "is_percentage": bool,
    "label": str
  },
  "curves": [
    {
      "id": int,
      "legend_name": str,
      "color_description": str,
      "rgb_approx": [int, int, int],
      "line_style": str
    }
  ],
  "at_risk_table": {
    "time_points": [float],
    "counts_by_curve": [[int]]
  },
  "total_events_by_curve": [int or null],
  "has_confidence_interval": bool,
  "has_censoring_marks": bool,
  "confidence": {
    "overall": "high" | "medium" | "low",
    "at_risk_table": "high" | "medium" | "low",
    "color_identification": "high" | "medium" | "low"
  },
  "notes": str
}

Rules:
- The top-level keys must be exactly the keys above.
- Do not use alternative keys such as "axes", "chart_type", "statistics", "panel_identifier", "title", or "censoring_marks".
- `n_curves` must equal `len(curves)` and must be > 0 if any KM curves are visible.
- `legend_name` must be the treatment/group name, not a generic color name.
- `rgb_approx` must always be a 3-integer array.
- If a number-at-risk table exists, every row in `counts_by_curve` must have exactly the same length as `time_points`.
- `confidence` fields must be strings: high, medium, or low.
- `notes` must be a single string, not a list.
- If you are unsure but the field is visually present, make the best estimate and lower the confidence.

Valid example response:
{
  "n_curves": 2,
  "x_axis": {
    "min": 0,
    "max": 24,
    "unit": "months",
    "label": "Time, months"
  },
  "y_axis": {
    "min": 0,
    "max": 100,
    "is_percentage": true,
    "label": "Overall survival, %"
  },
  "curves": [
    {
      "id": 1,
      "legend_name": "Treatment",
      "color_description": "orange solid line",
      "rgb_approx": [242, 142, 43],
      "line_style": "solid"
    },
    {
      "id": 2,
      "legend_name": "Control",
      "color_description": "blue solid line",
      "rgb_approx": [78, 97, 114],
      "line_style": "solid"
    }
  ],
  "at_risk_table": {
    "time_points": [0, 6, 12, 18, 24],
    "counts_by_curve": [
      [120, 95, 70, 48, 30],
      [118, 90, 66, 41, 22]
    ]
  },
  "total_events_by_curve": [96, 104],
  "has_confidence_interval": false,
  "has_censoring_marks": true,
  "confidence": {
    "overall": "high",
    "at_risk_table": "high",
    "color_identification": "medium"
  },
  "notes": "Legend is shared across panels; values estimated visually where needed."
}

Invalid output patterns to avoid:
- top-level keys like `axes`, `chart_type`, `statistics`, `panel_identifier`, `title`
- `notes` as a list
- `confidence.overall` as a float
- missing `rgb_approx`
""".strip()

RETRY_PROMPT_SUFFIX = """
Mandatory requirements:
- `n_curves` must be greater than 0 if any KM curve is visible.
- `curves` must not be empty when curves are present.
- If a number-at-risk table exists anywhere in the relevant panel or full figure, extract it.
- Do not drop legend labels just because the legend is outside the focused panel.
- Do not use alternative top-level keys such as `axes`, `chart_type`, `statistics`, or `panel_identifier`.
- Before finalizing, verify:
  1. `n_curves == len(curves)`
  2. every curve has `legend_name`, `color_description`, and `rgb_approx`
  3. if `at_risk_table.counts_by_curve` is not empty, every row length equals `len(at_risk_table.time_points)`
  4. `notes` is a string
  5. `confidence` values are only `high`, `medium`, or `low`
- Return JSON only.
""".strip()

COLOR_HINTS = {
    "orange": [242, 142, 43],
    "red": [214, 39, 40],
    "blue": [31, 119, 180],
    "dark_blue": [57, 81, 108],
    "dark_blue_grey": [78, 97, 114],
    "grey": [127, 127, 127],
    "gray": [127, 127, 127],
    "green": [44, 160, 44],
    "black": [0, 0, 0],
    "purple": [148, 103, 189],
    "yellow": [237, 201, 72],
}


def validate_semantic_output(result: SemanticExtraction) -> Tuple[bool, List[str]]:
    """Run lightweight logical checks on a parsed semantic result."""
    issues: List[str] = []

    if result.n_curves < 1 or not result.curves:
        issues.append("no curves were extracted")

    if not (0 <= result.y_axis.min < result.y_axis.max):
        issues.append("y_axis range is invalid")

    if result.at_risk_table.counts_by_curve:
        for index, row in enumerate(result.at_risk_table.counts_by_curve):
            if any(a < b for a, b in zip(row, row[1:])):
                issues.append(f"at-risk row {index} is not monotonically non-increasing")
        if len(result.at_risk_table.counts_by_curve) != len(result.curves):
            issues.append("curve count does not match at-risk row count")

    return not issues, issues


def build_semantic_prompt(*, focus_hint: Optional[str] = None, retry: bool = False) -> str:
    """Build the semantic extraction prompt used by online providers."""
    parts = [SYSTEM_PROMPT, USER_PROMPT]
    if focus_hint:
        parts.extend(["Additional instruction:", focus_hint.strip()])
    if retry:
        parts.append(RETRY_PROMPT_SUFFIX)
    return "\n\n".join(parts)


def normalize_semantic_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize provider-specific semantic payloads into the internal schema."""
    if {"n_curves", "x_axis", "y_axis", "curves"}.issubset(payload.keys()):
        normalized = dict(payload)
        curve_labels = [
            _curve_label(curve, fallback=f"curve_{index + 1}")
            for index, curve in enumerate(payload.get("curves", []))
        ]
        normalized["at_risk_table"] = _normalize_at_risk_table(
            payload.get("at_risk_table"),
            curve_labels,
            fallback_time_points=(payload.get("x_axis") or {}).get("ticks") or [],
        )
        return normalized

    axes = payload.get("axes", {})
    x_axis_raw = payload.get("x_axis") or axes.get("x_axis") or {}
    y_axis_raw = payload.get("y_axis") or axes.get("y_axis") or {}
    curves_raw = payload.get("curves", [])
    curve_labels = [_curve_label(curve, fallback=f"curve_{index + 1}") for index, curve in enumerate(curves_raw)]

    normalized = {
        "n_curves": payload.get("n_curves") or len(curves_raw),
        "x_axis": _normalize_x_axis(x_axis_raw),
        "y_axis": _normalize_y_axis(y_axis_raw),
        "curves": [
            {
                "id": curve.get("id", index + 1),
                "legend_name": _curve_label(curve, fallback=f"curve_{index + 1}"),
                "color_description": _curve_color_description(curve),
                "rgb_approx": _curve_rgb(curve),
                "line_style": curve.get("line_style", "solid"),
            }
            for index, curve in enumerate(curves_raw)
        ],
        "at_risk_table": _normalize_at_risk_table(
            payload.get("at_risk_table"),
            curve_labels,
            fallback_time_points=x_axis_raw.get("ticks") or [],
        ),
        "total_events_by_curve": _normalize_total_events(
            payload.get("total_events") or payload.get("total_events_by_curve"),
            curve_labels,
        ),
        "has_confidence_interval": _detect_curve_confidence_interval(payload),
        "has_censoring_marks": _detect_censoring_marks(payload),
        "confidence": _normalize_confidence(payload, curves_raw),
        "notes": _normalize_notes(payload),
    }
    return normalized


def _normalize_x_axis(raw: Dict[str, Any]) -> Dict[str, Any]:
    minimum, maximum = _extract_axis_min_max(raw)
    label = str(raw.get("label", ""))
    unit = str(raw.get("unit") or _infer_x_unit(label))
    return {"min": minimum, "max": maximum, "unit": unit, "label": label}


def _normalize_y_axis(raw: Dict[str, Any]) -> Dict[str, Any]:
    minimum, maximum = _extract_axis_min_max(raw)
    label = str(raw.get("label", ""))
    is_percentage = bool(raw.get("is_percentage"))
    if "%" in label or maximum > 1.0:
        is_percentage = True
    return {"min": minimum, "max": maximum, "is_percentage": is_percentage, "label": label}


def _extract_axis_min_max(raw: Dict[str, Any]) -> Tuple[float, float]:
    if "min" in raw and "max" in raw:
        return float(raw["min"]), float(raw["max"])
    if isinstance(raw.get("range"), list) and len(raw["range"]) == 2:
        return float(raw["range"][0]), float(raw["range"][1])
    ticks = raw.get("ticks") or []
    if ticks:
        return float(min(ticks)), float(max(ticks))
    return 0.0, 1.0


def _infer_x_unit(label: str) -> str:
    text = label.lower()
    if "month" in text or " mo" in text or text.endswith(", mo") or text.endswith("mo"):
        return "months"
    if "year" in text or "yr" in text:
        return "years"
    if "day" in text:
        return "days"
    return ""


def _curve_label(curve: Dict[str, Any], *, fallback: str) -> str:
    return str(
        curve.get("legend_name")
        or curve.get("label")
        or curve.get("name")
        or curve.get("group_id")
        or fallback
    )


def _curve_color_description(curve: Dict[str, Any]) -> str:
    return str(curve.get("color_description") or curve.get("color") or "unknown")


def _curve_rgb(curve: Dict[str, Any]) -> List[int]:
    if "rgb_approx" in curve and isinstance(curve["rgb_approx"], (list, tuple)) and len(curve["rgb_approx"]) == 3:
        return [int(channel) for channel in curve["rgb_approx"]]

    color_text = _curve_color_description(curve).lower().replace(" ", "_")
    if color_text in COLOR_HINTS:
        return COLOR_HINTS[color_text]

    for key, value in COLOR_HINTS.items():
        if key in color_text:
            return value
    return [127, 127, 127]


def _normalize_at_risk_table(
    raw: Any,
    curve_labels: List[str],
    *,
    fallback_time_points: Optional[List[float]] = None,
) -> Dict[str, Any]:
    if not raw:
        return {"time_points": [], "counts_by_curve": []}
    if "time_points" in raw and "counts_by_curve" in raw:
        time_points = list(raw.get("time_points") or [])
        counts_by_curve = [
            _coerce_non_increasing_counts(list(values))
            for values in (raw.get("counts_by_curve") or [])
        ]
        if not time_points or not counts_by_curve:
            return {"time_points": [], "counts_by_curve": []}
        common_len = min([len(time_points)] + [len(values) for values in counts_by_curve if values])
        return {
            "time_points": time_points[:common_len],
            "counts_by_curve": [values[:common_len] for values in counts_by_curve],
        }

    time_points = list(raw.get("columns") or raw.get("time_points") or fallback_time_points or [])
    rows = raw.get("rows") or []
    row_map = {
        _canonical_label(str(row.get("label") or row.get("group_id") or "").strip()): row.get("values", [])
        for row in rows
    }

    counts_by_curve = []
    for label in curve_labels:
        counts_by_curve.append(list(row_map.get(_canonical_label(label), [])))

    ordered_rows = [list(row.get("values", [])) for row in rows]
    if rows and all(len(values) == 0 for values in counts_by_curve):
        counts_by_curve = ordered_rows[: len(curve_labels)]

    if len(counts_by_curve) < len(curve_labels):
        counts_by_curve.extend([[] for _ in range(len(curve_labels) - len(counts_by_curve))])

    non_empty_lengths = [len(values) for values in counts_by_curve if values]
    if non_empty_lengths:
        if not time_points and fallback_time_points:
            time_points = list(fallback_time_points)
        common_len = min([len(time_points)] + non_empty_lengths) if time_points else min(non_empty_lengths)
        time_points = time_points[:common_len]
        counts_by_curve = [
            _coerce_non_increasing_counts(values[:common_len]) if values else []
            for values in counts_by_curve
        ]

    if any(len(values) == 0 for values in counts_by_curve):
        return {"time_points": [], "counts_by_curve": []}

    return {"time_points": time_points, "counts_by_curve": counts_by_curve}


def _coerce_non_increasing_counts(values: List[Any]) -> List[int]:
    """Repair minor OCR reversals in at-risk counts by enforcing a running minimum."""
    repaired: List[int] = []
    running = None
    for value in values:
        current = int(value)
        if running is None:
            running = current
        else:
            running = min(running, current)
        repaired.append(running)
    return repaired


def _normalize_total_events(raw: Any, curve_labels: List[str]) -> List[Optional[int]]:
    if raw is None:
        return [None for _ in curve_labels]
    if isinstance(raw, list):
        return [None if value is None else int(value) for value in raw]
    if isinstance(raw, dict):
        return [None if raw.get(label) is None else int(raw[label]) for label in curve_labels]
    if isinstance(raw, (int, float)) and len(curve_labels) == 1:
        return [int(raw)]
    return [None for _ in curve_labels]


def _detect_curve_confidence_interval(payload: Dict[str, Any]) -> bool:
    keys = (
        "has_confidence_interval",
        "confidence_band",
        "confidence_interval_band",
        "curve_confidence_interval",
    )
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, dict) and "present" in value:
            return bool(value["present"])
    return False


def _detect_censoring_marks(payload: Dict[str, Any]) -> bool:
    value = payload.get("has_censoring_marks")
    if isinstance(value, bool):
        return value
    marks = payload.get("censoring_marks")
    if isinstance(marks, dict) and "present" in marks:
        return bool(marks["present"])
    return False


def _normalize_confidence(payload: Dict[str, Any], curves_raw: List[Dict[str, Any]]) -> Dict[str, str]:
    confidence = payload.get("confidence", {})
    overall = _confidence_level(confidence.get("overall"), default="medium")
    at_risk = "high" if payload.get("at_risk_table", {}).get("rows") else "low"
    color_identification = "high" if any(_curve_color_description(curve) != "unknown" for curve in curves_raw) else "medium"
    return {
        "overall": overall,
        "at_risk_table": _confidence_level(confidence.get("at_risk_table"), default=at_risk),
        "color_identification": _confidence_level(
            confidence.get("color_identification"),
            default=color_identification,
        ),
    }


def _confidence_level(value: Any, *, default: str) -> str:
    if isinstance(value, str):
        text = value.lower().strip()
        if text in {"high", "medium", "low"}:
            return text
    if isinstance(value, (int, float)):
        if value >= 0.8:
            return "high"
        if value >= 0.5:
            return "medium"
        return "low"
    return default


def _normalize_notes(payload: Dict[str, Any]) -> str:
    notes = []
    raw_notes = payload.get("notes")
    if isinstance(raw_notes, list):
        notes.extend(str(item) for item in raw_notes)
    elif raw_notes:
        notes.append(str(raw_notes))

    confidence_notes = payload.get("confidence", {}).get("notes")
    if confidence_notes:
        notes.append(str(confidence_notes))

    panel_identifier = payload.get("panel_identifier")
    title = payload.get("title")
    if panel_identifier or title:
        notes.append(
            " / ".join(part for part in [f"panel={panel_identifier}" if panel_identifier else "", title or ""] if part)
        )
    return " | ".join(note for note in notes if note).strip()


def _canonical_label(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


class SemanticExtractor:
    """Resolve semantic metadata from a direct payload or a provider."""

    def extract(
        self,
        image_path: str,
        *,
        semantic: Optional[Dict[str, Any] | SemanticExtraction] = None,
        provider: Optional[VisionProvider] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        semantic_image_path: Optional[str] = None,
        focus_hint: Optional[str] = None,
    ) -> SemanticExtraction:
        """Return a validated semantic extraction."""
        if semantic is not None:
            parsed = self._parse_direct_semantic(semantic)
            self._validate_parsed_semantic(parsed)
            return parsed

        self._ensure_provider(provider, model=model)
        return self._extract_from_provider(
            image_path=semantic_image_path or image_path,
            provider=provider,
            model=model,
            api_key=api_key,
            focus_hint=focus_hint,
        )

    def _parse_direct_semantic(
        self,
        semantic: Dict[str, Any] | SemanticExtraction,
    ) -> SemanticExtraction:
        if isinstance(semantic, SemanticExtraction):
            return semantic
        return SemanticExtraction.model_validate(semantic)

    def _ensure_provider(
        self,
        provider: Optional[VisionProvider],
        *,
        model: Optional[str],
    ) -> None:
        if provider is not None:
            return
        if model is not None:
            raise SemanticExtractionError(
                "A model name was provided, but no VisionProvider is configured."
            )
        raise SemanticExtractionError(
            "Semantic metadata or a VisionProvider is required for extraction."
        )

    def _extract_from_provider(
        self,
        *,
        image_path: str,
        provider: VisionProvider,
        model: Optional[str],
        api_key: Optional[str],
        focus_hint: Optional[str],
    ) -> SemanticExtraction:
        last_error: Optional[Exception] = None

        for retry in (False, True):
            try:
                payload = provider.extract_semantics(
                    image_path,
                    prompt=build_semantic_prompt(focus_hint=focus_hint, retry=retry),
                    model=model,
                    api_key=api_key,
                )
                parsed = SemanticExtraction.model_validate(normalize_semantic_payload(payload))
                self._validate_parsed_semantic(parsed)
                return parsed
            except Exception as exc:
                last_error = exc

        raise SemanticExtractionError(str(last_error))

    def _validate_parsed_semantic(self, parsed: SemanticExtraction) -> None:
        ok, issues = validate_semantic_output(parsed)
        if not ok:
            raise SemanticExtractionError("; ".join(issues))
