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

    def detect_overlap_ambiguity(self, curves: List[CurveData]) -> List[tuple[CurveData, CurveData]]:
        """Flag long nearly coincident segments between different extracted curves."""
        ambiguous_pairs: List[tuple[CurveData, CurveData]] = []
        if len(curves) < 2:
            return ambiguous_pairs

        for left_index, left_curve in enumerate(curves):
            left_trace = {
                int(round(x_pixel)): float(y_pixel)
                for x_pixel, y_pixel in zip(left_curve.x_pixels, left_curve.y_pixels)
            }
            if not left_trace:
                continue

            for right_curve in curves[left_index + 1 :]:
                right_trace = {
                    int(round(x_pixel)): float(y_pixel)
                    for x_pixel, y_pixel in zip(right_curve.x_pixels, right_curve.y_pixels)
                }
                common_x = sorted(set(left_trace).intersection(right_trace))
                if len(common_x) < 24:
                    continue

                close_x = [
                    x_value
                    for x_value in common_x
                    if abs(left_trace[x_value] - right_trace[x_value]) <= 3.0
                ]
                if len(close_x) < max(20, int(len(common_x) * 0.18)):
                    continue

                longest_run = 1
                run = 1
                for previous, current in zip(close_x, close_x[1:]):
                    if current - previous <= 1:
                        run += 1
                    else:
                        longest_run = max(longest_run, run)
                        run = 1
                longest_run = max(longest_run, run)

                if longest_run >= 20:
                    ambiguous_pairs.append((left_curve, right_curve))

        return ambiguous_pairs

    def validate(self, semantic: SemanticExtraction, curves: List[CurveData]) -> ValidationReport:
        """Return an aggregate validation report across all curves."""
        if not curves:
            return ValidationReport(
                score=0,
                level="low",
                checks={
                    "monotonicity": False,
                    "range": False,
                    "start": False,
                    "coverage": False,
                    "risk_table": False,
                    "overlap_ambiguity": False,
                },
                issues=[
                    ValidationIssue(
                        code="no_curves",
                        message="No curves were extracted from the image.",
                    )
                ],
            )

        weights = {
            "monotonicity": 30,
            "range": 20,
            "start": 15,
            "coverage": 15,
            "risk_table": 20,
        }
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

        overlap_pairs = self.detect_overlap_ambiguity(curves)
        checks["overlap_ambiguity"] = not overlap_pairs
        for left_curve, right_curve in overlap_pairs:
            issues.append(
                ValidationIssue(
                    code="overlap_ambiguity",
                    message=(
                        f"curves '{left_curve.name}' and '{right_curve.name}' share a long overlapping segment; "
                        "manual review is recommended"
                    ),
                )
            )

        score = int(sum(weight for key, weight in weights.items() if checks.get(key, False)))
        if score >= 80:
            level = "high"
        elif score >= 60:
            level = "medium"
        else:
            level = "low"

        if overlap_pairs and level == "high":
            level = "medium"

        return ValidationReport(score=score, level=level, checks=checks, issues=issues)
