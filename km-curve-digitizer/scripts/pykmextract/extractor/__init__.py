"""Extraction stages."""

from .coord import clean_curve_series, detect_axis_bounds, pixel_to_data, recalibrate_axis_bounds_from_curves
from .pixel import adaptive_color_extraction, pixels_to_curve, trim_curve_edge_outliers
from .semantic import SemanticExtractor, validate_semantic_output
from .validator import ExtractionValidator

__all__ = [
    "ExtractionValidator",
    "SemanticExtractor",
    "adaptive_color_extraction",
    "clean_curve_series",
    "detect_axis_bounds",
    "pixel_to_data",
    "pixels_to_curve",
    "trim_curve_edge_outliers",
    "recalibrate_axis_bounds_from_curves",
    "validate_semantic_output",
]
