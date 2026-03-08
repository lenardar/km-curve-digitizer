"""Core data contracts shared across the extraction pipeline."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

if TYPE_CHECKING:
    from .review import ReviewBundleOptions


class ConfidenceLevel(str, Enum):
    """Confidence levels shared by semantic and validation outputs."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class XAxisSpec(BaseModel):
    """Semantic description of the x-axis."""

    min: float
    max: float
    unit: str = ""
    label: str = ""

    @model_validator(mode="after")
    def validate_range(self) -> "XAxisSpec":
        if self.max <= self.min:
            raise ValueError("x_axis.max must be larger than x_axis.min")
        return self


class YAxisSpec(BaseModel):
    """Semantic description of the y-axis."""

    min: float
    max: float
    is_percentage: bool = False
    label: str = ""

    @model_validator(mode="after")
    def validate_range(self) -> "YAxisSpec":
        if self.max <= self.min:
            raise ValueError("y_axis.max must be larger than y_axis.min")
        return self

    def normalized_range(self) -> Tuple[float, float]:
        """Return y-axis bounds normalized onto 0-1 scale when needed."""
        if self.is_percentage:
            return self.min / 100.0, self.max / 100.0
        return self.min, self.max


class CurveSemanticSpec(BaseModel):
    """Semantic metadata used to find and label a curve."""

    id: int
    legend_name: str
    color_description: str = ""
    rgb_approx: Tuple[int, int, int]
    line_style: str = "solid"

    @field_validator("rgb_approx")
    @classmethod
    def validate_rgb(cls, value: Tuple[int, int, int]) -> Tuple[int, int, int]:
        if len(value) != 3:
            raise ValueError("rgb_approx must contain exactly three channels")
        for channel in value:
            if not 0 <= channel <= 255:
                raise ValueError("RGB channels must be between 0 and 255")
        return value


class AtRiskTable(BaseModel):
    """Structured number-at-risk table."""

    time_points: List[float] = Field(default_factory=list)
    counts_by_curve: List[List[int]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rows(self) -> "AtRiskTable":
        if self.counts_by_curve:
            expected = len(self.time_points)
            for row in self.counts_by_curve:
                if len(row) != expected:
                    raise ValueError("Each at-risk row must match time_points length")
                if any(a < b for a, b in zip(row, row[1:])):
                    raise ValueError("At-risk counts must be monotonically non-increasing")
        return self


class SemanticConfidence(BaseModel):
    """Confidence reported by the semantic stage."""

    overall: ConfidenceLevel = ConfidenceLevel.MEDIUM
    at_risk_table: ConfidenceLevel = ConfidenceLevel.MEDIUM
    color_identification: ConfidenceLevel = ConfidenceLevel.MEDIUM


class SemanticExtraction(BaseModel):
    """Complete semantic result consumed by the pixel extraction pipeline."""

    model_config = ConfigDict(use_enum_values=True)

    n_curves: int
    x_axis: XAxisSpec
    y_axis: YAxisSpec
    curves: List[CurveSemanticSpec]
    at_risk_table: AtRiskTable = Field(default_factory=AtRiskTable)
    total_events_by_curve: Optional[List[Optional[int]]] = None
    has_confidence_interval: bool = False
    has_censoring_marks: bool = False
    confidence: SemanticConfidence = Field(default_factory=SemanticConfidence)
    notes: str = ""

    @model_validator(mode="after")
    def validate_consistency(self) -> "SemanticExtraction":
        if self.n_curves != len(self.curves):
            raise ValueError("n_curves must match the number of curve entries")
        if self.at_risk_table.counts_by_curve and (
            len(self.at_risk_table.counts_by_curve) != len(self.curves)
        ):
            raise ValueError("At-risk rows must match the number of curves")
        if self.total_events_by_curve is not None and (
            len(self.total_events_by_curve) != len(self.curves)
        ):
            raise ValueError("total_events_by_curve must match the number of curves")
        return self


class AxisBounds(BaseModel):
    """Pixel-space bounds of the plotting area."""

    left: int
    right: int
    top: int
    bottom: int

    @model_validator(mode="after")
    def validate_bounds(self) -> "AxisBounds":
        if self.right <= self.left:
            raise ValueError("right must be greater than left")
        if self.bottom <= self.top:
            raise ValueError("bottom must be greater than top")
        return self

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class PixelPoint(BaseModel):
    """One pixel-space point."""

    x: int
    y: int


class AxisAnchors(BaseModel):
    """Four-point axis calibration independent of an explicit axis intersection."""

    x_min_point: PixelPoint
    x_max_point: PixelPoint
    y_min_point: PixelPoint
    y_max_point: PixelPoint

    @model_validator(mode="after")
    def validate_spans(self) -> "AxisAnchors":
        if self.x_max_point.x <= self.x_min_point.x:
            raise ValueError("x_max_point.x must be greater than x_min_point.x")
        if self.y_min_point.y <= self.y_max_point.y:
            raise ValueError("y_min_point.y must be greater than y_max_point.y")
        return self

    @classmethod
    def from_bounds(cls, bounds: AxisBounds) -> "AxisAnchors":
        """Build the default four anchors from a rectangular plotting box."""
        return cls(
            x_min_point=PixelPoint(x=bounds.left, y=bounds.bottom),
            x_max_point=PixelPoint(x=bounds.right, y=bounds.bottom),
            y_min_point=PixelPoint(x=bounds.left, y=bounds.bottom),
            y_max_point=PixelPoint(x=bounds.left, y=bounds.top),
        )

    def as_bounds(self) -> AxisBounds:
        """Approximate the anchors as a rectangular plotting box."""
        return AxisBounds(
            left=min(self.x_min_point.x, self.y_min_point.x, self.y_max_point.x),
            right=max(self.x_max_point.x, self.x_min_point.x),
            top=min(self.y_max_point.y, self.y_min_point.y),
            bottom=max(self.y_min_point.y, self.x_min_point.y, self.x_max_point.y),
        )


class AxisAnchorCandidate(BaseModel):
    """One candidate point shown to the reviewing VLM."""

    id: str
    point: PixelPoint


class AxisAnchorSelection(BaseModel):
    """Model-selected candidate plus a small offset adjustment."""

    candidate_id: str
    dx: int = 0
    dy: int = 0
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class AxisReviewResult(BaseModel):
    """Structured review output returned by the VLM axis refiner."""

    model_config = ConfigDict(use_enum_values=True)

    decision: str = "accept"
    x_min_point: AxisAnchorSelection
    x_max_point: AxisAnchorSelection
    y_min_point: AxisAnchorSelection
    y_max_point: AxisAnchorSelection
    issues: List[str] = Field(default_factory=list)


class CurveData(BaseModel):
    """Extracted pixel and data-space representation of one curve."""

    id: int
    name: str
    color_description: str = ""
    extraction_tolerance: int
    point_count: int
    x_pixels: List[float]
    y_pixels: List[float]
    time: List[float]
    survival: List[float]

    @model_validator(mode="after")
    def validate_lengths(self) -> "CurveData":
        expected = len(self.time)
        if expected == 0:
            raise ValueError("curve must contain at least one data point")
        if len(self.survival) != expected:
            raise ValueError("time and survival lengths must match")
        if len(self.x_pixels) != len(self.y_pixels):
            raise ValueError("x_pixels and y_pixels lengths must match")
        return self

    def to_frame(self) -> pd.DataFrame:
        """Return curve data as a tidy dataframe."""
        return pd.DataFrame(
            {
                "curve_id": self.id,
                "curve_name": self.name,
                "time": self.time,
                "survival": self.survival,
                "x_pixel": self.x_pixels,
                "y_pixel": self.y_pixels,
            }
        )


class ValidationIssue(BaseModel):
    """One validation finding emitted by the validator."""

    code: str
    message: str
    curve_id: Optional[int] = None


class ValidationReport(BaseModel):
    """Aggregate validation summary."""

    model_config = ConfigDict(use_enum_values=True)

    score: int
    level: ConfidenceLevel
    checks: Dict[str, bool]
    issues: List[ValidationIssue] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Full pipeline output."""

    model_config = ConfigDict(use_enum_values=True)

    image_path: str
    semantic: SemanticExtraction
    axis_bounds: AxisBounds
    axis_anchors: AxisAnchors
    curves: List[CurveData]
    validation: ValidationReport

    def curve_frame(self) -> pd.DataFrame:
        """Flatten all curve outputs into a single dataframe."""
        if not self.curves:
            return pd.DataFrame(
                columns=["curve_id", "curve_name", "time", "survival", "x_pixel", "y_pixel"]
            )
        return pd.concat([curve.to_frame() for curve in self.curves], ignore_index=True)

    def to_jsonable(self) -> Dict[str, Any]:
        """Return a JSON-serializable mapping."""
        return self.model_dump(mode="json")

    def validation_frame(self) -> pd.DataFrame:
        """Return validation issues as a dataframe."""
        return pd.DataFrame(
            [issue.model_dump() for issue in self.validation.issues],
            columns=["code", "message", "curve_id"],
        )

    def to_pyheor_ipd(self) -> Dict[str, Dict[str, Sequence[float]]]:
        """Reconstruct IPD via the PyHEOR bridge."""
        from .bridge.pyheor import PyHEORBridge

        return PyHEORBridge().extracted_to_ipd(self)

    def to_pyheor_distributions(self) -> Dict[str, Any]:
        """Fit and return PyHEOR survival distributions."""
        from .bridge.pyheor import PyHEORBridge

        return PyHEORBridge().to_distributions(self)

    def save_overlay(self, output_path: str) -> str:
        """Save an extraction review overlay image."""
        from .review import save_overlay

        return save_overlay(self, output_path)

    def save_review_bundle(
        self,
        output_dir: str,
        *,
        semantic_context_image: Optional[str] = None,
        citation: Optional[str] = None,
        title: Optional[str] = None,
        options: Optional["ReviewBundleOptions"] = None,
    ) -> Dict[str, str]:
        """Save a review bundle with plots, IPD exports, and Markdown."""
        from .review import save_review_bundle

        return save_review_bundle(
            self,
            output_dir,
            semantic_context_image=semantic_context_image,
            citation=citation,
            title=title,
            options=options,
        )
