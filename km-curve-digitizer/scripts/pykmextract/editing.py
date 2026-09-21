"""Deterministic, auditable editing operations for extracted KM curves."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import numpy as np

from .contracts import CurveData, CurveRevision, ExtractionResult
from .extractor.coord import clean_curve_points, pixel_to_data
from .extractor.validator import ExtractionValidator


class CurveEditor:
    """Apply model- or user-authored point edits without mutating the source result."""

    def __init__(self, *, validator: ExtractionValidator | None = None):
        self.validator = validator or ExtractionValidator()

    def apply(
        self,
        result: ExtractionResult,
        actions: Iterable[dict[str, Any]],
        *,
        reason: str = "",
    ) -> ExtractionResult:
        actions = [dict(action) for action in actions]
        if not actions:
            raise ValueError("actions must contain at least one edit")

        edited = result.model_copy(deep=True)
        revision_id = f"r{len(edited.revisions) + 1:04d}"
        touched: dict[int, CurveData] = {}

        for action_index, action in enumerate(actions):
            action_type = str(action.get("type", "")).strip().lower()
            curve = self._find_curve(edited, action.get("curve"))
            touched[curve.id] = curve

            if action_type == "delete_points":
                self._delete_points(curve, action)
            elif action_type == "add_points":
                self._add_points(edited, curve, action, revision_id, action_index)
            elif action_type == "move_point":
                self._move_point(edited, curve, action)
            elif action_type == "replace_segment":
                self._replace_segment(edited, curve, action, revision_id, action_index)
            else:
                raise ValueError(f"Unsupported edit action type: {action_type or '<missing>'}")

        for curve in touched.values():
            self._normalize_curve(edited, curve, revision_id)

        edited.validation = self.validator.validate(edited.semantic, edited.curves)
        edited.revisions.append(
            CurveRevision(
                revision_id=revision_id,
                created_at=datetime.now(timezone.utc).isoformat(),
                reason=reason,
                actions=actions,
            )
        )
        return ExtractionResult.model_validate(edited.model_dump())

    @staticmethod
    def _find_curve(result: ExtractionResult, curve_selector: Any) -> CurveData:
        if curve_selector is None:
            raise ValueError("Each edit action must specify a curve name or id")
        for curve in result.curves:
            if curve_selector == curve.name or str(curve_selector) == str(curve.id):
                return curve
        raise ValueError(f"Curve not found: {curve_selector}")

    def _delete_points(self, curve: CurveData, action: dict[str, Any]) -> None:
        selected = self._selected_indices(curve, action)
        if not selected:
            raise ValueError(f"delete_points selected no points on curve '{curve.name}'")
        if len(curve.time) - len(selected) < 2:
            raise ValueError("delete_points must leave at least two points on the curve")
        self._drop_indices(curve, selected)

    def _add_points(
        self,
        result: ExtractionResult,
        curve: CurveData,
        action: dict[str, Any],
        revision_id: str,
        action_index: int,
    ) -> None:
        points = action.get("points") or []
        if not isinstance(points, list) or not points:
            raise ValueError("add_points requires a non-empty points list")

        for point_index, point in enumerate(points):
            x_pixel, y_pixel = self._resolve_point_to_pixels(result, point)
            curve.x_pixels.append(x_pixel)
            curve.y_pixels.append(y_pixel)
            curve.time.append(0.0)
            curve.survival.append(0.0)
            curve.point_ids.append(
                f"c{curve.id}-{revision_id}-a{action_index:02d}p{point_index:04d}"
            )

    def _move_point(
        self,
        result: ExtractionResult,
        curve: CurveData,
        action: dict[str, Any],
    ) -> None:
        point_id = str(action.get("point_id", ""))
        if not point_id or point_id not in curve.point_ids:
            raise ValueError(f"move_point could not find point_id '{point_id}'")
        target = action.get("to")
        if not isinstance(target, dict):
            raise ValueError("move_point requires a 'to' point")
        x_pixel, y_pixel = self._resolve_point_to_pixels(result, target)
        index = curve.point_ids.index(point_id)
        curve.x_pixels[index] = x_pixel
        curve.y_pixels[index] = y_pixel

    def _replace_segment(
        self,
        result: ExtractionResult,
        curve: CurveData,
        action: dict[str, Any],
        revision_id: str,
        action_index: int,
    ) -> None:
        time_range = action.get("time_range")
        if not self._valid_range(time_range):
            raise ValueError("replace_segment requires time_range=[start, end]")
        points = action.get("points") or []
        if not isinstance(points, list) or not points:
            raise ValueError("replace_segment requires a non-empty points list")

        selected = self._indices_in_time_range(curve, time_range)
        if selected:
            self._drop_indices(curve, selected)
        self._add_points(result, curve, {"points": points}, revision_id, action_index)

    def _selected_indices(self, curve: CurveData, action: dict[str, Any]) -> set[int]:
        selected: set[int] = set()
        selectors_found = False

        if "point_ids" in action:
            selectors_found = True
            requested = {str(value) for value in action.get("point_ids") or []}
            missing = requested.difference(curve.point_ids)
            if missing:
                raise ValueError(f"Unknown point_ids for curve '{curve.name}': {sorted(missing)}")
            selected.update(index for index, point_id in enumerate(curve.point_ids) if point_id in requested)

        if "point_indices" in action:
            selectors_found = True
            for raw_index in action.get("point_indices") or []:
                index = int(raw_index)
                if not 0 <= index < len(curve.time):
                    raise ValueError(f"point index out of range: {index}")
                selected.add(index)

        if "time_range" in action:
            selectors_found = True
            selected.update(self._indices_in_time_range(curve, action.get("time_range")))

        if "pixel_region" in action:
            selectors_found = True
            region = action.get("pixel_region")
            if not isinstance(region, list) or len(region) != 4:
                raise ValueError("pixel_region must be [left, top, right, bottom]")
            left, top, right, bottom = (float(value) for value in region)
            if right < left or bottom < top:
                raise ValueError("pixel_region bounds are invalid")
            selected.update(
                index
                for index, (x_pixel, y_pixel) in enumerate(zip(curve.x_pixels, curve.y_pixels))
                if left <= x_pixel <= right and top <= y_pixel <= bottom
            )

        if not selectors_found:
            raise ValueError(
                "delete_points requires point_ids, point_indices, time_range, or pixel_region"
            )
        return selected

    @staticmethod
    def _indices_in_time_range(curve: CurveData, time_range: Any) -> set[int]:
        if not CurveEditor._valid_range(time_range):
            raise ValueError("time_range must be [start, end] with end >= start")
        start, end = (float(value) for value in time_range)
        return {index for index, time in enumerate(curve.time) if start <= time <= end}

    @staticmethod
    def _valid_range(value: Any) -> bool:
        return (
            isinstance(value, list)
            and len(value) == 2
            and float(value[1]) >= float(value[0])
        )

    @staticmethod
    def _drop_indices(curve: CurveData, indices: set[int]) -> None:
        keep = [index for index in range(len(curve.time)) if index not in indices]
        curve.x_pixels = [curve.x_pixels[index] for index in keep]
        curve.y_pixels = [curve.y_pixels[index] for index in keep]
        curve.time = [curve.time[index] for index in keep]
        curve.survival = [curve.survival[index] for index in keep]
        curve.point_ids = [curve.point_ids[index] for index in keep]

    @staticmethod
    def _resolve_point_to_pixels(
        result: ExtractionResult,
        point: dict[str, Any],
    ) -> tuple[float, float]:
        if not isinstance(point, dict):
            raise ValueError("Each point must be an object")
        if "x_pixel" in point and "y_pixel" in point:
            return float(point["x_pixel"]), float(point["y_pixel"])
        if "time" in point and "survival" in point:
            return CurveEditor._data_to_pixel(
                result,
                float(point["time"]),
                float(point["survival"]),
            )
        raise ValueError("A point requires x_pixel/y_pixel or time/survival")

    @staticmethod
    def _data_to_pixel(
        result: ExtractionResult,
        time: float,
        survival: float,
    ) -> tuple[float, float]:
        semantic = result.semantic
        anchors = result.axis_anchors
        if not semantic.x_axis.min <= time <= semantic.x_axis.max:
            raise ValueError(f"time {time} is outside the x-axis range")
        if not 0.0 <= survival <= 1.0:
            raise ValueError(f"survival {survival} must be between 0 and 1")

        x_fraction = (time - semantic.x_axis.min) / (semantic.x_axis.max - semantic.x_axis.min)
        x_pixel = anchors.x_min_point.x + x_fraction * (
            anchors.x_max_point.x - anchors.x_min_point.x
        )

        y_value = survival * 100.0 if semantic.y_axis.is_percentage else survival
        y_fraction = (semantic.y_axis.max - y_value) / (
            semantic.y_axis.max - semantic.y_axis.min
        )
        y_pixel = anchors.y_max_point.y + y_fraction * (
            anchors.y_min_point.y - anchors.y_max_point.y
        )
        return float(x_pixel), float(y_pixel)

    @staticmethod
    def _normalize_curve(
        result: ExtractionResult,
        curve: CurveData,
        revision_id: str,
    ) -> None:
        x_pixels = np.asarray(curve.x_pixels, dtype=float)
        y_pixels = np.asarray(curve.y_pixels, dtype=float)
        time, survival = pixel_to_data(
            x_pixels,
            y_pixels,
            result.axis_bounds,
            result.semantic.x_axis,
            result.semantic.y_axis,
            axis_anchors=result.axis_anchors,
        )

        order = np.argsort(time, kind="stable")
        ordered_ids = [curve.point_ids[index] for index in order]
        ordered_x = x_pixels[order]
        ordered_y = y_pixels[order]
        ordered_time = time[order]
        ordered_survival = survival[order]
        keep = np.ones(len(ordered_time), dtype=bool)
        keep[1:] = np.diff(ordered_time) > 0
        normalized_ids = [point_id for point_id, should_keep in zip(ordered_ids, keep) if should_keep]

        x_clean, y_clean, time_clean, survival_clean = clean_curve_points(
            ordered_x[keep],
            ordered_y[keep],
            ordered_time[keep],
            ordered_survival[keep],
        )
        if len(time_clean) == len(normalized_ids) + 1 and time_clean[0] == 0:
            normalized_ids.insert(0, f"c{curve.id}-{revision_id}-origin")
        if len(time_clean) != len(normalized_ids):
            raise ValueError("Curve normalization changed point alignment unexpectedly")

        curve.x_pixels = x_clean.tolist()
        curve.y_pixels = y_clean.tolist()
        curve.time = time_clean.tolist()
        curve.survival = survival_clean.tolist()
        curve.point_ids = normalized_ids
        curve.point_count = len(curve.time)
