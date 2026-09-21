"""Extraction stages."""

from .axis_refiner import AxisRefiner, generate_axis_anchor_candidates, render_axis_review_board
from .coord import clean_curve_series, detect_axis_bounds, pixel_to_data, recalibrate_axis_bounds_from_curves
from .pixel import adaptive_color_extraction, pixels_to_curve, trim_curve_edge_outliers
from .semantic import SemanticExtractor, normalize_semantic_payload, validate_semantic_output
from .validator import ExtractionValidator

__all__ = [
    "AxisRefiner",
    "ExtractionValidator",
    "SemanticExtractor",
    "adaptive_color_extraction",
    "clean_curve_series",
    "detect_axis_bounds",
    "generate_axis_anchor_candidates",
    "normalize_semantic_payload",
    "pixel_to_data",
    "pixels_to_curve",
    "render_axis_review_board",
    "trim_curve_edge_outliers",
    "recalibrate_axis_bounds_from_curves",
    "validate_semantic_output",
]
