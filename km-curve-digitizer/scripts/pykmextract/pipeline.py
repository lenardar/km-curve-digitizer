"""Pipeline orchestration for end-to-end KM extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np

from .contracts import AxisAnchors, AxisBounds, CurveData, CurveSemanticSpec, ExtractionResult, SemanticExtraction
from .extractor.coord import clean_curve_points, detect_axis_bounds_from_array, pixel_to_data
from .extractor.pixel import (
    adaptive_color_extraction,
    load_image_array,
    pixels_to_curve,
    remove_ci_band,
    trim_curve_edge_outliers,
)
from .extractor.semantic import SemanticExtractor
from .extractor.risk_table import locate_risk_table_cells
from .extractor.validator import ExtractionValidator


@dataclass
class CurveTrace:
    """Intermediate pixel trace for one extracted curve."""

    spec: CurveSemanticSpec
    tolerance: int
    point_count: int
    x_pixels: np.ndarray
    y_pixels: np.ndarray


class ExtractionPipeline:
    """High-level KM extraction pipeline."""

    def __init__(
        self,
        *,
        semantic_extractor: Optional[SemanticExtractor] = None,
        validator: Optional[ExtractionValidator] = None,
    ):
        self.semantic_extractor = semantic_extractor or SemanticExtractor()
        self.validator = validator or ExtractionValidator()

    def run(
        self,
        image_path: str,
        *,
        semantic: Optional[Dict[str, Any] | SemanticExtraction] = None,
        vision_provider: Any = None,
        llm: Optional[str] = None,
        api_key: Optional[str] = None,
        axis_bounds: Optional[AxisBounds | Dict[str, int]] = None,
        axis_anchors: Optional[AxisAnchors | Dict[str, Any]] = None,
        min_curve_pixels: int = 30,
        semantic_image: Optional[str] = None,
        semantic_focus_hint: Optional[str] = None,
    ) -> ExtractionResult:
        """Execute semantic resolution, pixel extraction, and validation."""
        parsed_semantic = self.semantic_extractor.extract(
            image_path,
            semantic=semantic,
            provider=vision_provider,
            model=llm,
            api_key=api_key,
            semantic_image_path=semantic_image,
            focus_hint=semantic_focus_hint,
        )
        image_pixels = load_image_array(image_path)
        parsed_bounds, _ = self._resolve_axis_bounds(image_pixels, axis_bounds)
        image_width = image_pixels.shape[1]

        traces = self._extract_curve_traces(
            image_path=image_path,
            image_pixels=image_pixels,
            semantic=parsed_semantic,
            axis_bounds=parsed_bounds,
            image_width=image_width,
            min_curve_pixels=min_curve_pixels,
        )

        parsed_anchors = self._resolve_axis_anchors(parsed_bounds, axis_anchors)
        curves = [self._build_curve_data(trace, parsed_bounds, parsed_anchors, parsed_semantic) for trace in traces]

        risk_cell_regions = locate_risk_table_cells(
            image_pixels,
            parsed_semantic,
            parsed_bounds,
            parsed_anchors,
        )

        validation = self.validator.validate(parsed_semantic, curves)
        return ExtractionResult(
            image_path=image_path,
            semantic=parsed_semantic,
            axis_bounds=parsed_bounds,
            axis_anchors=parsed_anchors,
            curves=curves,
            validation=validation,
            risk_cell_regions=risk_cell_regions,
        )

    def _resolve_axis_bounds(
        self,
        image_pixels: np.ndarray,
        axis_bounds: Optional[AxisBounds | Dict[str, int]],
    ) -> tuple[AxisBounds, bool]:
        if axis_bounds is not None:
            return AxisBounds.model_validate(axis_bounds), False
        return detect_axis_bounds_from_array(image_pixels), True

    def _resolve_axis_anchors(
        self,
        axis_bounds: AxisBounds,
        axis_anchors: Optional[AxisAnchors | Dict[str, Any]],
    ) -> AxisAnchors:
        if axis_anchors is not None:
            return AxisAnchors.model_validate(axis_anchors)
        return AxisAnchors.from_bounds(axis_bounds)

    def _extract_curve_traces(
        self,
        *,
        image_path: str,
        image_pixels: np.ndarray,
        semantic: SemanticExtraction,
        axis_bounds: AxisBounds,
        image_width: int,
        min_curve_pixels: int,
    ) -> list[CurveTrace]:
        return [
            self._extract_curve_trace(
                image_path=image_path,
                image_pixels=image_pixels,
                curve_spec=curve_spec,
                has_confidence_interval=semantic.has_confidence_interval,
                axis_bounds=axis_bounds,
                image_width=image_width,
                min_curve_pixels=min_curve_pixels,
            )
            for curve_spec in semantic.curves
        ]

    def _extract_curve_trace(
        self,
        *,
        image_path: str,
        image_pixels: np.ndarray,
        curve_spec: CurveSemanticSpec,
        has_confidence_interval: bool,
        axis_bounds: AxisBounds,
        image_width: int,
        min_curve_pixels: int,
    ) -> CurveTrace:
        coords, tolerance = adaptive_color_extraction(
            image_path,
            curve_spec.rgb_approx,
            pixels=image_pixels,
            plot_bounds=axis_bounds,
            min_pixels=min_curve_pixels,
        )
        if has_confidence_interval:
            coords = remove_ci_band(coords, image_width=image_width)

        x_pixels, y_pixels = pixels_to_curve(coords)
        x_pixels, y_pixels = trim_curve_edge_outliers(x_pixels, y_pixels)
        return CurveTrace(
            spec=curve_spec,
            tolerance=tolerance,
            point_count=len(coords),
            x_pixels=x_pixels,
            y_pixels=y_pixels,
        )

    def _build_curve_data(
        self,
        trace: CurveTrace,
        axis_bounds: AxisBounds,
        axis_anchors: AxisAnchors,
        semantic: SemanticExtraction,
    ) -> CurveData:
        time, survival = pixel_to_data(
            trace.x_pixels,
            trace.y_pixels,
            axis_bounds,
            semantic.x_axis,
            semantic.y_axis,
            axis_anchors=axis_anchors,
        )
        x_pixels, y_pixels, time, survival = clean_curve_points(
            trace.x_pixels,
            trace.y_pixels,
            time,
            survival,
        )
        return CurveData(
            id=trace.spec.id,
            name=trace.spec.legend_name,
            color_description=trace.spec.color_description,
            extraction_tolerance=trace.tolerance,
            point_count=trace.point_count,
            x_pixels=x_pixels.tolist(),
            y_pixels=y_pixels.tolist(),
            time=time.tolist(),
            survival=survival.tolist(),
        )


def extract(
    image: str,
    *,
    semantic: Optional[Dict[str, Any] | SemanticExtraction] = None,
    vision_provider: Any = None,
    llm: Optional[str] = None,
    api_key: Optional[str] = None,
    axis_bounds: Optional[AxisBounds | Dict[str, int]] = None,
    axis_anchors: Optional[AxisAnchors | Dict[str, Any]] = None,
    min_curve_pixels: int = 30,
    semantic_image: Optional[str] = None,
    semantic_focus_hint: Optional[str] = None,
) -> ExtractionResult:
    """Convenience wrapper around :class:`ExtractionPipeline`."""
    return ExtractionPipeline().run(
        image,
        semantic=semantic,
        vision_provider=vision_provider,
        llm=llm,
        api_key=api_key,
        axis_bounds=axis_bounds,
        axis_anchors=axis_anchors,
        min_curve_pixels=min_curve_pixels,
        semantic_image=semantic_image,
        semantic_focus_hint=semantic_focus_hint,
    )
