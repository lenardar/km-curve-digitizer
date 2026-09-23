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
from .review import (
    result_review_signature,
    save_point_review,
    save_risk_table_review,
    save_scan_comparison,
    save_scan_windows,
)
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
        help="Accept or reject a base extraction or edited candidate after visual review",
    )
    verify_parser.add_argument("result", help="Extraction or candidate result JSON")
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
        "--reviewed-issue",
        action="append",
        default=[],
        help=(
            "Deprecated issue acknowledgement retained for audit compatibility; it does not "
            "replace the required scan-review evidence"
        ),
    )
    verify_parser.add_argument(
        "--scan-review",
        help="Completed scan_review.json tied to this exact result; required for acceptance",
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

    scan_parser = subparsers.add_parser(
        "scan",
        help="Render overlapping left-to-right source and curve-focused review windows",
    )
    scan_parser.add_argument("result", help="Existing extraction result JSON")
    scan_parser.add_argument("--output-dir", required=True, help="New directory for scan outputs")
    scan_parser.add_argument("--window-width", type=int, default=160, help="Window width in source pixels")
    scan_parser.add_argument("--overlap", type=int, default=48, help="Horizontal overlap in source pixels")
    scan_parser.add_argument("--padding", type=int, default=6, help="Context padding in source pixels")
    scan_parser.add_argument("--scale", type=int, default=3, help="Integer nearest-neighbor enlargement")

    compare_parser = subparsers.add_parser(
        "compare-scan",
        help="Render overlapping source/before/after triptychs for each curve",
    )
    compare_parser.add_argument("before_result", help="Parent or pre-edit result JSON")
    compare_parser.add_argument("after_result", help="Candidate or accepted result JSON")
    compare_parser.add_argument("--output-dir", required=True, help="New directory for comparison boards")
    compare_parser.add_argument("--window-width", type=int, default=160, help="Window width in source pixels")
    compare_parser.add_argument("--overlap", type=int, default=48, help="Horizontal overlap in source pixels")
    compare_parser.add_argument("--padding", type=int, default=6, help="Context padding in source pixels")
    compare_parser.add_argument("--scale", type=int, default=3, help="Integer nearest-neighbor enlargement")

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
    reviewed_issue_ids = set(args.reviewed_issue)
    unknown_issue_ids = reviewed_issue_ids - {
        issue.issue_id for issue in candidate.validation.issues
    }
    if unknown_issue_ids:
        raise ValueError(
            "Unknown reviewed issue IDs: " + ", ".join(sorted(unknown_issue_ids))
        )
    scan_review_payload = None
    if args.decision == "accept":
        if not args.scan_review:
            raise ValueError(
                "Acceptance requires --scan-review with completed left-to-right evidence"
            )
        scan_review_payload = _load_json(args.scan_review)
        _validate_scan_review(candidate, scan_review_payload)
    output_dir = _prepare_output_dir(args.output_dir)
    reviewed_revision = None
    reverified_revision = None
    if not candidate.revisions:
        # A clean first-pass extraction still needs an auditable model decision,
        # even when no point edit was necessary.
        verified = candidate.model_copy(deep=True)
    elif candidate.revisions[-1].status == "accepted" and args.decision == "accept":
        # A result can acquire stronger review evidence after its point revision was
        # accepted. The signature-bound scan proves the curve data are unchanged,
        # so record a fresh decision without inventing another edit revision.
        verified = candidate.model_copy(deep=True)
        reverified_revision = candidate.revisions[-1].model_copy(deep=True)
    else:
        if candidate.revisions[-1].status != "candidate":
            raise ValueError(
                "Only an accepted result can be reverified, and only with an accept decision"
            )
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
        "review_kind": (
            "edited_candidate"
            if reviewed_revision
            else "reverified_result"
            if reverified_revision
            else "base_extraction"
        ),
        "reviewed_issue_ids": sorted(reviewed_issue_ids),
        "scan_review": "scan_review.json" if scan_review_payload is not None else None,
        "revision": (
            (reviewed_revision or reverified_revision).model_dump(mode="json")
            if reviewed_revision or reverified_revision
            else None
        ),
        "result": str(output_result),
        "overlay": overlay_path,
    }
    decision_path = output_dir / "review_decision.json"
    decision_path.write_text(
        json.dumps(decision_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if scan_review_payload is not None:
        (output_dir / "scan_review.json").write_text(
            json.dumps(scan_review_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    print(json.dumps(decision_payload, indent=2, ensure_ascii=False))
    return 0


def _validate_scan_review(result: ExtractionResult, payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("scan-review must be a JSON object")
    expected_signature = result_review_signature(result)
    if payload.get("result_signature") != expected_signature:
        raise ValueError(
            "scan-review belongs to different curve data; regenerate it for this exact result"
        )

    window_reviews = payload.get("window_reviews")
    if not isinstance(window_reviews, list) or not window_reviews:
        raise ValueError("scan-review contains no window reviews")
    window_ids = [item.get("window_id") for item in window_reviews if isinstance(item, dict)]
    if len(set(window_ids)) != len(window_reviews) or any(not value for value in window_ids):
        raise ValueError("scan-review window IDs must be present and unique")

    regions: list[tuple[float, float, float, float]] = []
    for window in window_reviews:
        region = window.get("pixel_region") if isinstance(window, dict) else None
        if not isinstance(region, list) or len(region) != 4:
            raise ValueError("Every scan window must preserve its four-value pixel_region")
        left, top, right, bottom = (float(value) for value in region)
        if right <= left or bottom <= top or right - left > 220:
            raise ValueError("Scan windows must be valid and no wider than 220 source pixels")
        if top > result.axis_bounds.top or bottom < result.axis_bounds.bottom:
            raise ValueError("Every scan window must cover the full plot height")
        regions.append((left, top, right, bottom))
    regions.sort(key=lambda item: item[0])
    if regions[0][0] > result.axis_bounds.left or regions[-1][2] < result.axis_bounds.right:
        raise ValueError("Scan windows must cover the complete plot width")
    for previous, current in zip(regions, regions[1:]):
        if current[0] >= previous[2]:
            raise ValueError("Adjacent scan windows must overlap")

    expected_curve_ids = {curve.id for curve in result.curves}
    incomplete: list[str] = []
    for window in window_reviews:
        if not isinstance(window, dict):
            incomplete.append("invalid-window")
            continue
        window_id = str(window.get("window_id", "unknown"))
        if window.get("status") not in {"clear", "resolved"}:
            incomplete.append(window_id)
        if not str(window.get("observation", "")).strip():
            incomplete.append(f"{window_id}:observation")
        curve_reviews = window.get("curve_reviews")
        if not isinstance(curve_reviews, list):
            incomplete.append(f"{window_id}:curves")
            continue
        actual_curve_ids = {
            item.get("curve_id") for item in curve_reviews if isinstance(item, dict)
        }
        if actual_curve_ids != expected_curve_ids:
            incomplete.append(f"{window_id}:curves")
        for curve_review in curve_reviews:
            if not isinstance(curve_review, dict):
                continue
            curve_key = f"{window_id}:curve-{curve_review.get('curve_id', '?')}"
            if curve_review.get("status") not in {"clear", "resolved"}:
                incomplete.append(curve_key)
            if not str(curve_review.get("observation", "")).strip():
                incomplete.append(f"{curve_key}:observation")

    required_issue_ids = {
        issue.issue_id for issue in result.validation.issues if issue.requires_visual_review
    }
    issue_reviews = payload.get("issue_reviews")
    if not isinstance(issue_reviews, list):
        issue_reviews = []
    actual_issue_ids = {
        item.get("issue_id") for item in issue_reviews if isinstance(item, dict)
    }
    if actual_issue_ids != required_issue_ids:
        incomplete.append("issue-review-set")
    known_window_ids = set(window_ids)
    for issue_review in issue_reviews:
        if not isinstance(issue_review, dict):
            continue
        issue_id = str(issue_review.get("issue_id", "unknown"))
        if issue_review.get("status") not in {"false_positive", "resolved"}:
            incomplete.append(issue_id)
        if not str(issue_review.get("observation", "")).strip():
            incomplete.append(f"{issue_id}:observation")
        linked_windows = issue_review.get("window_ids")
        if (
            not isinstance(linked_windows, list)
            or not linked_windows
            or not set(linked_windows).issubset(known_window_ids)
        ):
            incomplete.append(f"{issue_id}:windows")

    if incomplete:
        raise ValueError(
            "Acceptance requires completed scan evidence for: "
            + ", ".join(sorted(set(incomplete)))
        )


def _run_scan(args: argparse.Namespace) -> int:
    result = ExtractionResult.model_validate(_load_json(args.result))
    output_dir = _prepare_output_dir(args.output_dir)
    bundle = save_scan_windows(
        result,
        str(output_dir),
        window_width=args.window_width,
        overlap=args.overlap,
        padding=args.padding,
        scale=args.scale,
    )
    print(json.dumps(bundle, indent=2, ensure_ascii=False))
    return 0


def _run_compare_scan(args: argparse.Namespace) -> int:
    before = ExtractionResult.model_validate(_load_json(args.before_result))
    after = ExtractionResult.model_validate(_load_json(args.after_result))
    output_dir = _prepare_output_dir(args.output_dir)
    bundle = save_scan_comparison(
        before,
        after,
        str(output_dir),
        window_width=args.window_width,
        overlap=args.overlap,
        padding=args.padding,
        scale=args.scale,
    )
    print(json.dumps(bundle, indent=2, ensure_ascii=False))
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
        if args.command == "scan":
            return _run_scan(args)
        if args.command == "compare-scan":
            return _run_compare_scan(args)
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
