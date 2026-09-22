"""Command-line interface for auditable curve point editing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

from PIL import Image, ImageDraw

from .contracts import ExtractionResult
from .editing import CurveEditor
from .review import save_point_review, save_risk_table_review
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
    apply_parser.add_argument(
        "--observation",
        default="",
        help="Visible source discrepancy that motivated the edit",
    )
    apply_parser.add_argument("--reason", default="", help="Optional revision reason override")

    verify_parser = subparsers.add_parser(
        "verify",
        help="Accept or reject a candidate after visual before/after comparison",
    )
    verify_parser.add_argument("result", help="Candidate extraction result JSON")
    verify_parser.add_argument(
        "--decision",
        required=True,
        choices=["accept", "reject"],
        help="Model decision after visual verification",
    )
    verify_parser.add_argument(
        "--verification",
        required=True,
        help="Visible evidence supporting acceptance or rejection",
    )
    verify_parser.add_argument(
        "--parent-result",
        help="Parent JSON used on rejection; defaults to parent_result.json beside the candidate",
    )
    verify_parser.add_argument(
        "--output-dir",
        required=True,
        help="New directory for verified outputs",
    )

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
    inspect_parser.add_argument(
        "--source-only",
        action="store_true",
        help="Show an enlarged source crop without overlays or point labels",
    )

    risk_parser = subparsers.add_parser(
        "inspect-risk",
        help="Render and export stable number-at-risk cells for model inspection",
    )
    risk_parser.add_argument("result", help="Existing extraction result JSON")
    risk_parser.add_argument("--output-dir", required=True, help="New directory for risk-table outputs")

    risk_cell_parser = subparsers.add_parser(
        "inspect-risk-cell",
        help="Render an enlarged source crop for one stable number-at-risk cell",
    )
    risk_cell_parser.add_argument("result", help="Existing extraction result JSON")
    risk_cell_parser.add_argument("--cell-id", required=True, help="Stable cell ID such as risk-c1-t002")
    risk_cell_parser.add_argument("--output-dir", required=True, help="New directory for cell inspection")
    risk_cell_parser.add_argument("--padding", type=int, default=8, help="Source-pixel context padding")
    risk_cell_parser.add_argument("--scale", type=int, default=4, help="Integer output enlargement")
    return parser


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_actions(path: str) -> tuple[list[dict[str, Any]], str, str]:
    payload = _load_json(path)
    if isinstance(payload, list):
        return payload, "", ""
    if isinstance(payload, dict) and isinstance(payload.get("actions"), list):
        return (
            payload["actions"],
            str(payload.get("observation", "")),
            str(payload.get("reason", "")),
        )
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
    actions, payload_observation, payload_reason = _load_actions(args.actions)
    observation = args.observation or payload_observation
    reason = args.reason or payload_reason
    output_dir = _prepare_output_dir(args.output_dir)
    output_result = output_dir / "result.json"
    if result_path.resolve() == output_result.resolve():
        raise ValueError("Edited output must not overwrite the source result")

    edited = CurveEditor().apply(
        result,
        actions,
        observation=observation,
        reason=reason,
    )

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


def _run_verify(args: argparse.Namespace) -> int:
    candidate_path = Path(args.result)
    candidate = ExtractionResult.model_validate(_load_json(str(candidate_path)))
    if not candidate.revisions:
        raise ValueError("Candidate result has no revision to verify")
    if candidate.revisions[-1].status != "candidate":
        raise ValueError("The latest revision has already been verified")

    output_dir = _prepare_output_dir(args.output_dir)
    reviewed_revision = candidate.revisions[-1].model_copy(deep=True)
    reviewed_revision.status = "accepted" if args.decision == "accept" else "rejected"
    reviewed_revision.verification = args.verification

    if args.decision == "accept":
        verified = candidate.model_copy(deep=True)
        verified.revisions[-1] = reviewed_revision
    else:
        parent_path = (
            Path(args.parent_result)
            if args.parent_result
            else candidate_path.with_name("parent_result.json")
        )
        if not parent_path.exists():
            raise ValueError(
                "Rejected candidates require --parent-result or parent_result.json beside the candidate"
            )
        verified = ExtractionResult.model_validate(_load_json(str(parent_path)))
        verified.revisions.append(reviewed_revision)
        shutil.copy2(candidate_path, output_dir / "rejected_candidate.json")

    output_result = output_dir / "result.json"
    save_result_json(verified, str(output_result))
    overlay_path = verified.save_overlay(str(output_dir / "overlay.png"))
    decision_payload = {
        "decision": args.decision,
        "verification": args.verification,
        "revision": reviewed_revision.model_dump(mode="json"),
        "result": str(output_result),
        "overlay": overlay_path,
    }
    decision_path = output_dir / "review_decision.json"
    decision_path.write_text(
        json.dumps(decision_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(decision_payload, indent=2, ensure_ascii=False))
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
        annotate=not args.source_only,
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


def _run_inspect_risk(args: argparse.Namespace) -> int:
    result = ExtractionResult.model_validate(_load_json(args.result))
    output_dir = _prepare_output_dir(args.output_dir)
    review_path = save_risk_table_review(result, str(output_dir / "risk_table_review.png"))
    records = result.risk_table_records()
    if not records:
        raise ValueError("No number-at-risk table is available for inspection")

    csv_path = output_dir / "risk_table.csv"
    result.risk_table_frame().to_csv(csv_path, index=False)
    json_path = output_dir / "risk_table.json"
    json_path.write_text(
        json.dumps(
            {
                "time_points": result.semantic.at_risk_table.time_points,
                "cells": records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    summary = {
        "review_image": review_path,
        "risk_table_csv": str(csv_path),
        "risk_table_json": str(json_path),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _run_inspect_risk_cell(args: argparse.Namespace) -> int:
    from .extractor.risk_table import ensure_risk_table_cell_regions

    if args.padding < 0:
        raise ValueError("padding must be non-negative")
    if not 1 <= args.scale <= 12:
        raise ValueError("scale must be between 1 and 12")

    result = ExtractionResult.model_validate(_load_json(args.result))
    if not ensure_risk_table_cell_regions(result):
        raise ValueError("Risk-table cells could not be localized in the source image")
    record = next(
        (item for item in result.risk_table_records() if item["cell_id"] == args.cell_id),
        None,
    )
    if record is None:
        raise ValueError(f"Risk-table cell not found: {args.cell_id}")
    region = record["pixel_region"]
    if region is None:
        raise ValueError(f"Risk-table cell has no localized source box: {args.cell_id}")

    output_dir = _prepare_output_dir(args.output_dir)
    source = Image.open(result.image_path).convert("RGB")
    left, top, right, bottom = (int(value) for value in region)
    crop_box = (
        max(0, left - args.padding),
        max(0, top - args.padding),
        min(source.width, right + args.padding),
        min(source.height, bottom + args.padding),
    )
    crop = source.crop(crop_box)
    draw = ImageDraw.Draw(crop)
    draw.rectangle(
        (
            left - crop_box[0],
            top - crop_box[1],
            right - crop_box[0],
            bottom - crop_box[1],
        ),
        outline=(255, 96, 0),
        width=1,
    )
    resampling = getattr(Image, "Resampling", Image).NEAREST
    enlarged = crop.resize(
        (crop.width * args.scale, crop.height * args.scale),
        resample=resampling,
    )
    image_path = output_dir / "risk_cell_review.png"
    enlarged.save(image_path)

    payload = {
        "cell": record,
        "crop_region": crop_box,
        "scale": args.scale,
        "review_image": str(image_path),
    }
    json_path = output_dir / "risk_cell.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {"review_image": str(image_path), "cell_json": str(json_path)},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "apply":
            return _run_apply(args)
        if args.command == "verify":
            return _run_verify(args)
        if args.command == "inspect":
            return _run_inspect(args)
        if args.command == "inspect-risk":
            return _run_inspect_risk(args)
        if args.command == "inspect-risk-cell":
            return _run_inspect_risk_cell(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
