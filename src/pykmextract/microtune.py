"""Post-extraction micro-tuning tools for human/AI-assisted refinement."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
import tempfile
from typing import Iterable, List

import numpy as np
from PIL import Image

from .contracts import CurveData, ExtractionResult
from .extractor.validator import ExtractionValidator
from .providers import VisionProvider
from .review import save_review_bundle


@dataclass(frozen=True)
class SegmentSample:
    """One sampled point used in segment inspection."""

    time: float
    survival: float


@dataclass(frozen=True)
class OverlapWindow:
    """One time window where two curves are nearly coincident."""

    left_curve: str
    right_curve: str
    time_start: float
    time_end: float
    max_gap: float
    point_count: int


@dataclass(frozen=True)
class MicroTuneSuggestion:
    """One bounded AI suggestion for a local step adjustment."""

    action: str
    curve_name: str | None
    time_start: float | None
    time_end: float | None
    targets: list[tuple[float, float]]
    confidence: str = "medium"
    notes: str = ""


class CurveMicroTuneToolkit:
    """Restricted post-processing tools that can be safely called by an AI."""

    def __init__(self, *, validator: ExtractionValidator | None = None):
        self.validator = validator or ExtractionValidator()

    def find_overlap_windows(
        self,
        result: ExtractionResult,
        *,
        y_tolerance: float = 0.04,
        min_duration: float = 3.0,
        min_points: int = 6,
    ) -> List[OverlapWindow]:
        """Find windows where two extracted curves are nearly coincident."""
        windows: List[OverlapWindow] = []
        for left_curve, right_curve in combinations(result.curves, 2):
            grid = self._comparison_grid(left_curve, right_curve)
            if len(grid) < min_points:
                continue

            left_values = self._step_values(left_curve, grid)
            right_values = self._step_values(right_curve, grid)
            close = np.abs(left_values - right_values) <= y_tolerance
            windows.extend(
                self._close_runs_to_windows(
                    left_curve.name,
                    right_curve.name,
                    grid,
                    left_values,
                    right_values,
                    close,
                    min_duration=min_duration,
                    min_points=min_points,
                )
            )
        return windows

    def inspect_segment(
        self,
        result: ExtractionResult,
        *,
        curve_name: str,
        time_start: float,
        time_end: float,
        sample_count: int = 12,
    ) -> dict:
        """Return a compact summary of one curve segment for AI review."""
        curve = self._get_curve(result, curve_name)
        if time_end <= time_start:
            raise ValueError("time_end must be greater than time_start")

        sample_times = np.linspace(time_start, time_end, num=max(2, sample_count))
        segment_samples = [
            SegmentSample(time=float(time_value), survival=float(survival_value))
            for time_value, survival_value in zip(sample_times, self._step_values(curve, sample_times))
        ]

        neighbors = []
        for other_curve in result.curves:
            if other_curve.name == curve_name:
                continue
            other_values = self._step_values(other_curve, sample_times)
            mean_gap = float(
                np.mean(np.abs(np.asarray([sample.survival for sample in segment_samples]) - other_values))
            )
            neighbors.append(
                {
                    "curve_name": other_curve.name,
                    "mean_gap": mean_gap,
                    "samples": [
                        {"time": float(time_value), "survival": float(value)}
                        for time_value, value in zip(sample_times, other_values)
                    ],
                }
            )

        return {
            "curve_name": curve.name,
            "time_start": time_start,
            "time_end": time_end,
            "samples": [sample.__dict__ for sample in segment_samples],
            "neighbors": neighbors,
            "overlap_windows": [
                window.__dict__
                for window in self.find_overlap_windows(result)
                if curve.name in {window.left_curve, window.right_curve}
                and not (window.time_end < time_start or window.time_start > time_end)
            ],
        }

    def apply_step_targets(
        self,
        result: ExtractionResult,
        *,
        curve_name: str,
        targets: Iterable[tuple[float, float]],
        max_delta: float = 0.08,
    ) -> ExtractionResult:
        """Apply a bounded right-continuous step adjustment to one curve."""
        targets = sorted((float(time), float(survival)) for time, survival in targets)
        if not targets:
            raise ValueError("targets must contain at least one (time, survival) point")

        tuned = result.model_copy(deep=True)
        curve = self._get_curve(tuned, curve_name)

        time = np.asarray(curve.time, dtype=float)
        survival = np.asarray(curve.survival, dtype=float)
        target_times = np.asarray([time_value for time_value, _ in targets], dtype=float)
        target_values = np.asarray([survival_value for _, survival_value in targets], dtype=float)

        start = target_times[0]
        end = target_times[-1]
        segment_mask = (time >= start) & (time <= end)
        if not np.any(segment_mask):
            raise ValueError("target time window does not overlap the selected curve")

        idx = np.searchsorted(target_times, time[segment_mask], side="right") - 1
        idx = np.clip(idx, 0, len(target_values) - 1)
        proposed = target_values[idx]
        bounded = np.clip(proposed, survival[segment_mask] - max_delta, survival[segment_mask] + max_delta)
        survival[segment_mask] = bounded
        survival = np.clip(survival, 0.0, 1.0)
        survival = np.minimum.accumulate(survival)

        curve.survival = survival.tolist()
        x_pixels, y_pixels = self._project_curve_to_pixels(tuned, time, survival)
        curve.x_pixels = x_pixels.tolist()
        curve.y_pixels = y_pixels.tolist()

        tuned.validation = self.validator.validate(tuned.semantic, tuned.curves)
        return tuned

    def save_review(
        self,
        result: ExtractionResult,
        output_dir: str,
        *,
        title: str | None = None,
    ) -> dict:
        """Export a review bundle for a tuned result."""
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        return save_review_bundle(result, str(output_root), title=title)

    def _get_curve(self, result: ExtractionResult, curve_name: str) -> CurveData:
        for curve in result.curves:
            if curve.name == curve_name:
                return curve
        raise ValueError(f"curve '{curve_name}' not found")

    @staticmethod
    def _comparison_grid(left_curve: CurveData, right_curve: CurveData) -> np.ndarray:
        left_time = np.asarray(left_curve.time, dtype=float)
        right_time = np.asarray(right_curve.time, dtype=float)
        start = max(float(left_time[0]), float(right_time[0]))
        end = min(float(left_time[-1]), float(right_time[-1]))
        if end <= start:
            return np.asarray([], dtype=float)

        grid = np.unique(
            np.concatenate(
                [
                    left_time[(left_time >= start) & (left_time <= end)],
                    right_time[(right_time >= start) & (right_time <= end)],
                ]
            )
        )
        if len(grid) < 2:
            return grid
        return grid

    @staticmethod
    def _step_values(curve: CurveData, grid: np.ndarray) -> np.ndarray:
        time = np.asarray(curve.time, dtype=float)
        survival = np.asarray(curve.survival, dtype=float)
        idx = np.searchsorted(time, grid, side="right") - 1
        idx = np.clip(idx, 0, len(survival) - 1)
        return survival[idx]

    @staticmethod
    def _close_runs_to_windows(
        left_curve: str,
        right_curve: str,
        grid: np.ndarray,
        left_values: np.ndarray,
        right_values: np.ndarray,
        close: np.ndarray,
        *,
        min_duration: float,
        min_points: int,
    ) -> List[OverlapWindow]:
        windows: List[OverlapWindow] = []
        run_start: int | None = None
        for index, flag in enumerate(close):
            if flag and run_start is None:
                run_start = index
            if (not flag or index == len(close) - 1) and run_start is not None:
                run_end = index if flag and index == len(close) - 1 else index - 1
                if run_end >= run_start:
                    window_grid = grid[run_start : run_end + 1]
                    duration = float(window_grid[-1] - window_grid[0])
                    if len(window_grid) >= min_points and duration >= min_duration:
                        max_gap = float(
                            np.max(
                                np.abs(
                                    left_values[run_start : run_end + 1]
                                    - right_values[run_start : run_end + 1]
                                )
                            )
                        )
                        windows.append(
                            OverlapWindow(
                                left_curve=left_curve,
                                right_curve=right_curve,
                                time_start=float(window_grid[0]),
                                time_end=float(window_grid[-1]),
                                max_gap=max_gap,
                                point_count=len(window_grid),
                            )
                        )
                run_start = None
        return windows

    @staticmethod
    def _project_curve_to_pixels(
        result: ExtractionResult,
        time: np.ndarray,
        survival: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        anchors = result.axis_anchors
        semantic = result.semantic

        x_min = anchors.x_min_point.x
        x_max = anchors.x_max_point.x
        y_top = anchors.y_max_point.y
        y_bottom = anchors.y_min_point.y

        x_span = max(1.0, float(x_max - x_min))
        y_span = max(1.0, float(y_bottom - y_top))
        x_range = semantic.x_axis.max - semantic.x_axis.min
        y_min = semantic.y_axis.min
        y_max = semantic.y_axis.max

        x_pixels = x_min + ((time - semantic.x_axis.min) / x_range) * x_span
        projected_survival = survival * 100.0 if semantic.y_axis.is_percentage else survival
        y_pixels = y_top + ((y_max - projected_survival) / (y_max - y_min)) * y_span
        return x_pixels, y_pixels


class SegmentMicroTuner:
    """Automatic post-extraction local micro-tuning driven by a VLM."""

    def __init__(
        self,
        *,
        toolkit: CurveMicroTuneToolkit | None = None,
        validator: ExtractionValidator | None = None,
        max_delta: float = 0.04,
        max_score_drop: int = 5,
    ):
        self.toolkit = toolkit or CurveMicroTuneToolkit(validator=validator)
        self.validator = validator or ExtractionValidator()
        self.max_delta = max_delta
        self.max_score_drop = max_score_drop

    def refine(
        self,
        result: ExtractionResult,
        *,
        provider: VisionProvider | None,
        model: str | None = None,
        api_key: str | None = None,
        review_image_path: str | None = None,
    ) -> ExtractionResult:
        """Auto-select one suspicious segment, ask the VLM for local targets, and revalidate."""
        if provider is None:
            raise ValueError("segment micro-tune requires a provider")

        candidate = self._select_candidate_segment(result)
        if candidate is None:
            return result

        curve_name, time_start, time_end = candidate
        segment_summary = self.toolkit.inspect_segment(
            result,
            curve_name=curve_name,
            time_start=time_start,
            time_end=time_end,
            sample_count=8,
        )

        if review_image_path is None:
            temp_dir = Path(tempfile.mkdtemp(prefix="pykmextract-microtune-"))
            board_path = temp_dir / "micro_tune_review.png"
        else:
            board_path = Path(review_image_path)
            board_path.parent.mkdir(parents=True, exist_ok=True)

        render_segment_review_board(
            result,
            curve_name=curve_name,
            time_start=time_start,
            time_end=time_end,
            output_path=str(board_path),
        )

        payload = provider.extract_semantics(
            str(board_path),
            prompt=self._build_prompt(result, segment_summary),
            model=model,
            api_key=api_key,
        )
        suggestion = _normalize_micro_tune_payload(payload, default_curve_name=curve_name)
        if suggestion.action != "adjust" or not suggestion.targets or suggestion.curve_name is None:
            return result

        tuned = self.toolkit.apply_step_targets(
            result,
            curve_name=suggestion.curve_name,
            targets=suggestion.targets,
            max_delta=self.max_delta,
        )
        if tuned.validation.score < result.validation.score - self.max_score_drop:
            return result
        return tuned

    def _select_candidate_segment(self, result: ExtractionResult) -> tuple[str, float, float] | None:
        coverage_curves = {
            issue.curve_id
            for issue in result.validation.issues
            if issue.code in {"coverage", "atrisk"}
        }
        if coverage_curves:
            curve = max(
                (curve for curve in result.curves if curve.id in coverage_curves),
                key=lambda item: item.extraction_tolerance,
            )
            start = max(float(curve.time[0]), float(curve.time[-1]) - 15.0)
            end = float(curve.time[-1])
            if end > start:
                return curve.name, start, end

        overlap_windows = self.toolkit.find_overlap_windows(result)
        if overlap_windows:
            window = max(overlap_windows, key=lambda item: (item.time_end - item.time_start, item.point_count))
            left_curve = self.toolkit._get_curve(result, window.left_curve)
            right_curve = self.toolkit._get_curve(result, window.right_curve)
            focus_curve = left_curve if left_curve.extraction_tolerance >= right_curve.extraction_tolerance else right_curve
            return focus_curve.name, window.time_start, window.time_end

        return None

    @staticmethod
    def _build_prompt(result: ExtractionResult, segment_summary: dict) -> str:
        return (
            "You are a KM-curve local refinement assistant.\n"
            "Inspect the provided review image and only adjust the highlighted local segment if the current dashed trace is visibly biased.\n"
            "Use the original curve shape in the image as the primary evidence.\n"
            "Do not redraw the whole curve.\n"
            "Do not change any curve outside the specified window.\n"
            "Return JSON only.\n\n"
            "Rules:\n"
            "- Output action must be either 'adjust' or 'skip'.\n"
            "- If adjusting, return 2 to 5 step targets inside the window.\n"
            "- Targets must be non-increasing in survival.\n"
            "- Targets should stay close to the current curve and only make local corrections.\n"
            "- Prefer conservative adjustments when evidence is weak.\n\n"
            f"Curve to inspect: {segment_summary['curve_name']}\n"
            f"Window: {segment_summary['time_start']} to {segment_summary['time_end']} {result.semantic.x_axis.unit}\n"
            f"Current samples: {segment_summary['samples']}\n"
            f"Neighbor summaries: {segment_summary['neighbors']}\n"
            f"Detected overlap windows: {segment_summary['overlap_windows']}\n\n"
            "Valid response example:\n"
            "{\n"
            '  "action": "adjust",\n'
            f'  "curve_name": "{segment_summary["curve_name"]}",\n'
            f'  "time_start": {segment_summary["time_start"]},\n'
            f'  "time_end": {segment_summary["time_end"]},\n'
            '  "targets": [[18.0, 0.10], [24.0, 0.08], [30.0, 0.06]],\n'
            '  "confidence": "medium",\n'
            '  "notes": "local overlap made the dashed trace too high in the tail"\n'
            "}\n"
        )


def render_segment_review_board(
    result: ExtractionResult,
    *,
    curve_name: str,
    time_start: float,
    time_end: float,
    output_path: str,
) -> str:
    """Render a local review image that highlights one suspicious time window."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    image = np.array(Image.open(result.image_path).convert("RGB"))
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.imshow(image)

    x0, x1 = _time_window_to_pixels(result, time_start, time_end)
    bounds = result.axis_bounds
    crop_pad_x = 28
    crop_pad_y = 20
    ax.set_xlim(max(bounds.left - crop_pad_x, x0 - crop_pad_x), min(bounds.right + crop_pad_x, x1 + crop_pad_x))
    ax.set_ylim(bounds.bottom + crop_pad_y, max(bounds.top - crop_pad_y, 0))

    rect = plt.Rectangle(
        (x0, bounds.top),
        max(1.0, x1 - x0),
        bounds.height,
        linewidth=1.5,
        edgecolor="#f0c419",
        facecolor="none",
    )
    ax.add_patch(rect)

    palette = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e"]
    for index, curve in enumerate(result.curves):
        x_pixels, y_pixels = CurveMicroTuneToolkit._project_curve_to_pixels(
            result,
            np.asarray(curve.time, dtype=float),
            np.asarray(curve.survival, dtype=float),
        )
        linestyle = "--" if curve.name == curve_name else ":"
        linewidth = 2.2 if curve.name == curve_name else 1.4
        alpha = 0.95 if curve.name == curve_name else 0.7
        ax.plot(
            x_pixels,
            y_pixels,
            linestyle=linestyle,
            linewidth=linewidth,
            alpha=alpha,
            color=palette[index % len(palette)],
            label=curve.name,
        )

    ax.set_title(f"Micro-tune review | {curve_name} | {time_start:.1f}-{time_end:.1f}")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_axis_off()
    fig.tight_layout()

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(output)


def _time_window_to_pixels(result: ExtractionResult, time_start: float, time_end: float) -> tuple[float, float]:
    anchors = result.axis_anchors
    x_min = anchors.x_min_point.x
    x_max = anchors.x_max_point.x
    x_range = result.semantic.x_axis.max - result.semantic.x_axis.min
    x_span = max(1.0, float(x_max - x_min))
    x0 = x_min + ((time_start - result.semantic.x_axis.min) / x_range) * x_span
    x1 = x_min + ((time_end - result.semantic.x_axis.min) / x_range) * x_span
    return float(min(x0, x1)), float(max(x0, x1))


def _normalize_micro_tune_payload(payload: dict, *, default_curve_name: str) -> MicroTuneSuggestion:
    action = str(payload.get("action", "skip")).strip().lower()
    curve_name = payload.get("curve_name") or default_curve_name
    time_start = payload.get("time_start")
    time_end = payload.get("time_end")
    raw_targets = payload.get("targets") or []
    targets: list[tuple[float, float]] = []
    for item in raw_targets:
        if isinstance(item, dict):
            time_value = item.get("time")
            survival_value = item.get("survival")
        else:
            time_value, survival_value = item
        targets.append((float(time_value), float(survival_value)))
    targets.sort(key=lambda item: item[0])
    return MicroTuneSuggestion(
        action=action,
        curve_name=str(curve_name) if curve_name is not None else None,
        time_start=float(time_start) if time_start is not None else None,
        time_end=float(time_end) if time_end is not None else None,
        targets=targets,
        confidence=str(payload.get("confidence", "medium")),
        notes=str(payload.get("notes", "")),
    )
