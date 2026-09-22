"""Validation and confidence scoring for extracted curves."""

from __future__ import annotations

from typing import Dict, List

import numpy as np

from ..contracts import CurveData, ExtractionResult, SemanticExtraction, ValidationIssue, ValidationReport


class ExtractionValidator:
    """Apply heuristic checks to extracted survival curves."""

    def validate_monotonicity(self, curve: CurveData) -> bool:
        diffs = np.diff(np.asarray(curve.survival, dtype=float))
        return bool(np.all(diffs <= 0.02))

    def validate_range(self, curve: CurveData) -> bool:
        survival = np.asarray(curve.survival, dtype=float)
        return bool(np.all((survival >= 0.0) & (survival <= 1.0)))

    def validate_start(self, curve: CurveData) -> bool:
        return bool(curve.survival and curve.survival[0] >= 0.9)

    def validate_coverage(self, curve: CurveData, semantic: SemanticExtraction) -> bool:
        x_max = semantic.x_axis.max
        return bool(curve.time and curve.time[-1] >= 0.75 * x_max)

    def validate_risk_table(self, semantic: SemanticExtraction, curve_index: int) -> bool:
        """Check observed risk counts without treating count ratios as survival."""
        at_risk = semantic.at_risk_table
        if not at_risk.time_points or not at_risk.counts_by_curve:
            return True

        counts = at_risk.counts_by_curve[curve_index]
        observed = [count for count in counts if count is not None]
        return not any(left < right for left, right in zip(observed, observed[1:]))

    def detect_source_gap_regions(
        self,
        curves: List[CurveData],
        *,
        min_missing_columns: int = 10,
    ) -> List[dict]:
        """Locate long resampled spans unsupported by observed source-color columns."""
        regions: List[dict] = []
        for curve in curves:
            observed_x = np.unique(np.asarray(curve.source_x_pixels, dtype=float))
            if len(observed_x) < 2:
                continue
            curve_x = np.asarray(curve.x_pixels, dtype=float)
            curve_y = np.asarray(curve.y_pixels, dtype=float)
            curve_time = np.asarray(curve.time, dtype=float)
            for left_x, right_x in zip(observed_x, observed_x[1:]):
                missing_columns = int(round(right_x - left_x)) - 1
                if missing_columns < min_missing_columns:
                    continue
                endpoint_y = np.interp([left_x, right_x], curve_x, curve_y)
                endpoint_time = np.interp([left_x, right_x], curve_x, curve_time)
                regions.append(
                    {
                        "curve": curve,
                        "missing_columns": missing_columns,
                        "time_range": (float(endpoint_time[0]), float(endpoint_time[1])),
                        "pixel_region": (
                            max(0, int(left_x) - 8),
                            max(0, int(endpoint_y.min()) - 16),
                            int(right_x) + 8,
                            int(endpoint_y.max()) + 16,
                        ),
                    }
                )
                if sum(item["curve"].id == curve.id for item in regions) >= 12:
                    break
        return regions

    def detect_curve_identity_regions(
        self,
        curves: List[CurveData],
        *,
        distance_pixels: float = 4.0,
        min_run_pixels: int = 6,
    ) -> List[dict]:
        """Locate close runs where independently extracted traces may switch identity."""
        regions: List[dict] = []
        if len(curves) < 2:
            return regions

        for left_index, left_curve in enumerate(curves):
            left_trace = {
                int(round(x_pixel)): (float(y_pixel), float(time_value))
                for x_pixel, y_pixel, time_value in zip(
                    left_curve.x_pixels,
                    left_curve.y_pixels,
                    left_curve.time,
                )
            }
            if not left_trace:
                continue

            for right_curve in curves[left_index + 1 :]:
                right_trace = {
                    int(round(x_pixel)): (float(y_pixel), float(time_value))
                    for x_pixel, y_pixel, time_value in zip(
                        right_curve.x_pixels,
                        right_curve.y_pixels,
                        right_curve.time,
                    )
                }
                common_x = sorted(set(left_trace).intersection(right_trace))
                if len(common_x) < min_run_pixels:
                    continue

                close_x = [
                    x_value
                    for x_value in common_x
                    if abs(left_trace[x_value][0] - right_trace[x_value][0])
                    <= distance_pixels
                ]
                if len(close_x) < min_run_pixels:
                    continue

                runs: List[List[int]] = []
                current_run = [close_x[0]]
                for previous, current in zip(close_x, close_x[1:]):
                    if current - previous <= 1:
                        current_run.append(current)
                    else:
                        if len(current_run) >= min_run_pixels:
                            runs.append(current_run)
                        current_run = [current]
                if len(current_run) >= min_run_pixels:
                    runs.append(current_run)

                for run in runs[:12]:
                    start_x, end_x = run[0], run[-1]
                    y_values = [
                        left_trace[x_value][0]
                        for x_value in run
                    ] + [
                        right_trace[x_value][0]
                        for x_value in run
                    ]
                    regions.append(
                        {
                            "left": left_curve,
                            "right": right_curve,
                            "run_length": len(run),
                            "time_range": (
                                min(left_trace[start_x][1], right_trace[start_x][1]),
                                max(left_trace[end_x][1], right_trace[end_x][1]),
                            ),
                            "pixel_region": (
                                max(0, start_x - 10),
                                max(0, int(min(y_values)) - 14),
                                end_x + 10,
                                int(max(y_values)) + 14,
                            ),
                        }
                    )

        return regions

    def validate(self, semantic: SemanticExtraction, curves: List[CurveData]) -> ValidationReport:
        """Return diagnostic checks and findings across all curves."""
        if not curves:
            return ValidationReport(
                checks={
                    "monotonicity": False,
                    "range": False,
                    "start": False,
                    "coverage": False,
                    "risk_table": False,
                    "overlap_ambiguity": False,
                    "curve_identity_review": False,
                    "source_gap_review": False,
                },
                issues=[
                    ValidationIssue(
                        code="no_curves",
                        message="No curves were extracted from the image.",
                    )
                ],
            )

        checks: Dict[str, bool] = {}
        issues: List[ValidationIssue] = []

        check_functions = {
            "monotonicity": self.validate_monotonicity,
            "range": self.validate_range,
            "start": self.validate_start,
        }

        for check_name, check_function in check_functions.items():
            values = [check_function(curve) for curve in curves]
            passed = all(values)
            checks[check_name] = passed
            if not passed:
                for curve, curve_passed in zip(curves, values):
                    if not curve_passed:
                        issues.append(
                            ValidationIssue(
                                code=check_name,
                                curve_id=curve.id,
                                message=f"{check_name} validation failed for curve '{curve.name}'",
                            )
                        )

        coverage_values = [self.validate_coverage(curve, semantic) for curve in curves]
        checks["coverage"] = all(coverage_values)
        if not checks["coverage"]:
            for curve, curve_passed in zip(curves, coverage_values):
                if not curve_passed:
                    issues.append(
                        ValidationIssue(
                            code="coverage",
                            curve_id=curve.id,
                            message=f"curve '{curve.name}' covers too little of the x-axis",
                        )
                    )

        risk_table_values = [
            self.validate_risk_table(semantic, index)
            for index, _curve in enumerate(curves)
        ]
        checks["risk_table"] = all(risk_table_values)
        if not checks["risk_table"]:
            for curve, curve_passed in zip(curves, risk_table_values):
                if not curve_passed:
                    issues.append(
                        ValidationIssue(
                            code="risk_table_non_monotonic",
                            curve_id=curve.id,
                            message=(
                                f"at-risk counts for curve '{curve.name}' increase at a later time; "
                                "review the source table instead of silently repairing the value"
                            ),
                        )
                    )

        source_gap_regions = self.detect_source_gap_regions(curves)
        checks["source_gap_review"] = not source_gap_regions
        for region in source_gap_regions:
            curve = region["curve"]
            issues.append(
                ValidationIssue(
                    code="source_gap_review",
                    curve_id=curve.id,
                    curve_ids=[curve.id],
                    time_range=region["time_range"],
                    pixel_region=region["pixel_region"],
                    requires_visual_review=True,
                    message=(
                        f"curve '{curve.name}' is forward-filled across "
                        f"{region['missing_columns']} columns without matching source-color pixels; "
                        "inspect the source crop for a missed drop or trace switch"
                    ),
                )
            )

        identity_regions = self.detect_curve_identity_regions(curves)
        long_regions = [region for region in identity_regions if region["run_length"] >= 20]
        checks["overlap_ambiguity"] = not long_regions
        checks["curve_identity_review"] = not identity_regions
        for region in identity_regions:
            left_curve = region["left"]
            right_curve = region["right"]
            is_long = region["run_length"] >= 20
            issues.append(
                ValidationIssue(
                    code="overlap_ambiguity" if is_long else "curve_identity_review",
                    curve_ids=[left_curve.id, right_curve.id],
                    time_range=region["time_range"],
                    pixel_region=region["pixel_region"],
                    requires_visual_review=True,
                    message=(
                        f"curves '{left_curve.name}' and '{right_curve.name}' are within 4 pixels "
                        f"for {region['run_length']} consecutive columns; inspect the source crop "
                        "to confirm that neither trace changes identity"
                    ),
                )
            )

        return ValidationReport(checks=checks, issues=issues)
