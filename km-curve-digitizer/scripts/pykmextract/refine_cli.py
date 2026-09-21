"""Command-line interface for auditable curve point editing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

from .contracts import ExtractionResult
from .editing import CurveEditor
from .review import save_point_review
from .runtime import save_result_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply auditable point edits to a KM digitization result"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply add, delete, move, or replace actions from JSON",
    )
    apply_parser.add_argument("result", help="Existing extraction result JSON")
    apply_parser.add_argument("--actions", required=True, help="Curve edit actions JSON")
    apply_parser.add_argument("--output-dir", required=True, help="New directory for edited outputs")
    apply_parser.add_argument("--reason", default="", help="Optional revision reason override")

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Render a local point-ID review board for model inspection",
    )
    inspect_parser.add_argument("result", help="Existing extraction result JSON")
    inspect_parser.add_argument("--curve", required=True, help="Curve name")
    inspect_parser.add_argument("--output-dir", required=True, help="New directory for inspection outputs")
    inspect_parser.add_argument("--time-range", help="Optional start,end data range")
    inspect_parser.add_argument("--pixel-region", help="Optional left,top,right,bottom pixel box")
    inspect_parser.add_argument("--max-labels", type=int, default=60)
    return parser


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_actions(path: str) -> tuple[list[dict[str, Any]], str]:
    payload = _load_json(path)
    if isinstance(payload, list):
        return payload, ""
    if isinstance(payload, dict) and isinstance(payload.get("actions"), list):
        return payload["actions"], str(payload.get("reason", ""))
    raise ValueError("Actions JSON must be a list or an object containing an actions list")


def _prepare_output_dir(path: str) -> Path:
    output_dir = Path(path)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _parse_numbers(value: str | None, *, count: int, label: str) -> tuple[float, ...] | None:
    if value is None:
        return None
    try:
        parsed = tuple(float(item.strip()) for item in value.split(","))
    except ValueError as exc:
        raise ValueError(f"{label} must contain comma-separated numbers") from exc
    if len(parsed) != count:
        raise ValueError(f"{label} must contain exactly {count} numbers")
    return parsed


def _run_apply(args: argparse.Namespace) -> int:
    result_path = Path(args.result)
    result = ExtractionResult.model_validate(_load_json(str(result_path)))
    actions, payload_reason = _load_actions(args.actions)
    reason = args.reason or payload_reason
    output_dir = _prepare_output_dir(args.output_dir)
    output_result = output_dir / "result.json"
    if result_path.resolve() == output_result.resolve():
        raise ValueError("Edited output must not overwrite the source result")

    edited = CurveEditor().apply(result, actions, reason=reason)

    shutil.copy2(result_path, output_dir / "parent_result.json")
    result.save_overlay(str(output_dir / "before_overlay.png"))
    save_result_json(edited, str(output_result))
    bundle = edited.save_review_bundle(
        str(output_dir / "review"),
        title=f"curve_edit_{edited.revisions[-1].revision_id}",
    )
    summary = {
        "revision": edited.revisions[-1].model_dump(mode="json"),
        "parent_result": str(output_dir / "parent_result.json"),
        "result": str(output_result),
        "before_overlay": str(output_dir / "before_overlay.png"),
        "after_overlay": bundle["overlay"],
        "review": bundle,
        "validation": edited.validation.model_dump(mode="json"),
    }
    (output_dir / "edit_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _run_inspect(args: argparse.Namespace) -> int:
    result = ExtractionResult.model_validate(_load_json(args.result))
    output_dir = _prepare_output_dir(args.output_dir)
    time_range = _parse_numbers(args.time_range, count=2, label="time-range")
    pixel_region = _parse_numbers(args.pixel_region, count=4, label="pixel-region")
    if time_range is not None and time_range[1] < time_range[0]:
        raise ValueError("time-range end must be greater than or equal to start")
    if pixel_region is not None and (
        pixel_region[2] < pixel_region[0] or pixel_region[3] < pixel_region[1]
    ):
        raise ValueError("pixel-region bounds are invalid")

    review_path, points = save_point_review(
        result,
        str(output_dir / "point_review.png"),
        curve_name=args.curve,
        time_range=time_range,
        pixel_region=pixel_region,
        max_labels=args.max_labels,
    )
    payload = {
        "curve": args.curve,
        "time_range": time_range,
        "pixel_region": pixel_region,
        "review_image": review_path,
        "points": points,
    }
    inspection_path = output_dir / "points.json"
    inspection_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({"review_image": review_path, "points_json": str(inspection_path)}, indent=2))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "apply":
            return _run_apply(args)
        if args.command == "inspect":
            return _run_inspect(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
