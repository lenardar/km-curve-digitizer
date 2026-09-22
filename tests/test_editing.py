"""Tests for model-directed, auditable curve point editing."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from tempfile import TemporaryDirectory

import pykmextract as pkm
from pykmextract.editing import CurveEditor
from tests.test_pipeline import make_synthetic_km_image


def make_result(tmpdir: str):
    image_path = Path(tmpdir) / "km.png"
    semantic, bounds = make_synthetic_km_image(image_path)
    return pkm.extract(
        str(image_path),
        semantic=semantic,
        axis_bounds={
            "left": bounds[0],
            "right": bounds[1],
            "top": bounds[2],
            "bottom": bounds[3],
        },
        min_curve_pixels=20,
    )


class CurveEditorTests(unittest.TestCase):
    def test_extraction_assigns_stable_point_ids(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            for curve in result.curves:
                self.assertEqual(len(curve.point_ids), len(curve.time))
                self.assertEqual(len(set(curve.point_ids)), len(curve.point_ids))
            self.assertIn("point_id", result.curve_frame().columns)

    def test_delete_add_and_move_are_audited_without_mutating_parent(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            parent = result.model_copy(deep=True)
            curve = result.curves[0]
            deleted_id = curve.point_ids[20]
            moved_id = curve.point_ids[40]
            target_time = curve.time[40]
            target_survival = min(1.0, curve.survival[40] + 0.01)

            edited = CurveEditor().apply(
                result,
                [
                    {
                        "type": "delete_points",
                        "curve": curve.name,
                        "point_ids": [deleted_id],
                    },
                    {
                        "type": "move_point",
                        "curve": curve.name,
                        "point_id": moved_id,
                        "to": {"time": target_time, "survival": target_survival},
                    },
                    {
                        "type": "add_points",
                        "curve": curve.name,
                        "points": [{"time": 10.25, "survival": 0.65}],
                    },
                ],
                observation="One isolated point is visibly below the source trace",
                reason="model visual review",
            )

            edited_curve = edited.curves[0]
            self.assertNotIn(deleted_id, edited_curve.point_ids)
            self.assertIn(moved_id, edited_curve.point_ids)
            self.assertTrue(any("-r0001-" in point_id for point_id in edited_curve.point_ids))
            self.assertEqual(len(edited.revisions), 1)
            self.assertEqual(
                edited.revisions[0].observation,
                "One isolated point is visibly below the source trace",
            )
            self.assertEqual(edited.revisions[0].reason, "model visual review")
            self.assertEqual(edited.revisions[0].status, "candidate")
            self.assertIn(deleted_id, parent.curves[0].point_ids)
            self.assertEqual(result.to_jsonable(), parent.to_jsonable())

    def test_replace_segment_changes_only_selected_curve(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            control_before = result.curves[1].model_dump()

            edited = CurveEditor().apply(
                result,
                [
                    {
                        "type": "replace_segment",
                        "curve": "Treatment",
                        "time_range": [10.0, 12.0],
                        "points": [
                            {"time": 10.0, "survival": 0.72},
                            {"time": 11.0, "survival": 0.70},
                            {"time": 12.0, "survival": 0.68},
                        ],
                    }
                ],
            )

            self.assertEqual(edited.curves[1].model_dump(), control_before)
            self.assertTrue(any("-r0001-" in point_id for point_id in edited.curves[0].point_ids))

    def test_unknown_point_id_is_rejected(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            with self.assertRaisesRegex(ValueError, "Unknown point_ids"):
                CurveEditor().apply(
                    result,
                    [
                        {
                            "type": "delete_points",
                            "curve": "Treatment",
                            "point_ids": ["missing"],
                        }
                    ],
                )

    def test_risk_cells_have_stable_ids_and_auditable_edits(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            records = result.risk_table_records()
            self.assertEqual(records[0]["cell_id"], "risk-c1-t000")
            self.assertEqual(records[0]["confidence"], "high")
            self.assertEqual(len(records), 10)

            edited = CurveEditor().apply(
                result,
                [
                    {
                        "type": "set_risk_cell",
                        "cell_id": "risk-c1-t002",
                        "count": 67,
                    },
                    {
                        "type": "delete_risk_cell",
                        "cell_id": "risk-c2-t004",
                    },
                    {
                        "type": "set_risk_time",
                        "time_index": 1,
                        "time": 7.5,
                    },
                ],
                reason="risk table visual review",
            )

            self.assertEqual(result.semantic.at_risk_table.counts_by_curve[0][2], 68)
            self.assertEqual(edited.semantic.at_risk_table.counts_by_curve[0][2], 67)
            self.assertIsNone(edited.semantic.at_risk_table.counts_by_curve[1][4])
            self.assertEqual(edited.semantic.at_risk_table.time_points[1], 7.5)
            self.assertEqual(edited.revisions[0].actions[0]["previous_count"], 68)
            self.assertEqual(edited.revisions[0].actions[2]["previous_time"], 8)

    def test_non_monotonic_risk_edit_is_preserved_and_flagged(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            edited = CurveEditor().apply(
                result,
                [
                    {
                        "type": "set_risk_cell",
                        "cell_id": "risk-c1-t002",
                        "count": 90,
                    }
                ],
            )

            self.assertEqual(edited.semantic.at_risk_table.counts_by_curve[0][2], 90)
            self.assertIn(
                "risk_table_non_monotonic",
                {issue.code for issue in edited.validation.issues},
            )
            self.assertFalse(edited.validation.checks["risk_table"])

    def test_fractional_risk_count_is_rejected(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            with self.assertRaisesRegex(ValueError, "whole numbers"):
                CurveEditor().apply(
                    result,
                    [
                        {
                            "type": "set_risk_cell",
                            "cell_id": "risk-c1-t002",
                            "count": 67.5,
                        }
                    ],
                )

    def test_refine_cli_writes_parent_result_and_review(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            result_path = Path(tmpdir) / "result.json"
            actions_path = Path(tmpdir) / "actions.json"
            output_dir = Path(tmpdir) / "edited"
            result_path.write_text(json.dumps(result.to_jsonable()), encoding="utf-8")
            actions_path.write_text(
                json.dumps(
                    {
                        "observation": "One extracted point is a visible outlier",
                        "reason": "remove visual outlier",
                        "actions": [
                            {
                                "type": "delete_points",
                                "curve": "Treatment",
                                "point_ids": [result.curves[0].point_ids[20]],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            script = (
                Path(__file__).resolve().parents[1]
                / "km-curve-digitizer"
                / "scripts"
                / "refine_km.py"
            )
            env = os.environ.copy()
            env.setdefault("MPLCONFIGDIR", str(Path(tmpdir) / ".mplconfig"))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "apply",
                    str(result_path),
                    "--actions",
                    str(actions_path),
                    "--output-dir",
                    str(output_dir),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output_dir / "parent_result.json").exists())
            self.assertTrue((output_dir / "before_overlay.png").exists())
            self.assertTrue((output_dir / "result.json").exists())
            self.assertTrue((output_dir / "review" / "overlay.png").exists())
            payload = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(
                payload["revisions"][0]["observation"],
                "One extracted point is a visible outlier",
            )
            self.assertEqual(payload["revisions"][0]["reason"], "remove visual outlier")
            self.assertEqual(payload["revisions"][0]["status"], "candidate")

    def test_refine_cli_accepts_candidate_after_visual_verification(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            candidate = CurveEditor().apply(
                result,
                [
                    {
                        "type": "delete_points",
                        "curve": "Treatment",
                        "point_ids": [result.curves[0].point_ids[20]],
                    }
                ],
                observation="The point is not on the visible curve",
                reason="remove visual outlier",
            )
            candidate_path = Path(tmpdir) / "candidate.json"
            output_dir = Path(tmpdir) / "accepted"
            candidate_path.write_text(json.dumps(candidate.to_jsonable()), encoding="utf-8")
            script = (
                Path(__file__).resolve().parents[1]
                / "km-curve-digitizer"
                / "scripts"
                / "refine_km.py"
            )
            env = os.environ.copy()
            env.setdefault("MPLCONFIGDIR", str(Path(tmpdir) / ".mplconfig"))

            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "verify",
                    str(candidate_path),
                    "--decision",
                    "accept",
                    "--verification",
                    "The edited overlay follows the source and its neighbors",
                    "--output-dir",
                    str(output_dir),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["revisions"][-1]["status"], "accepted")
            self.assertEqual(
                payload["revisions"][-1]["verification"],
                "The edited overlay follows the source and its neighbors",
            )
            self.assertTrue((output_dir / "review_decision.json").exists())

    def test_refine_cli_rejects_candidate_and_restores_parent(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            candidate = CurveEditor().apply(
                result,
                [
                    {
                        "type": "delete_points",
                        "curve": "Treatment",
                        "point_ids": [result.curves[0].point_ids[20]],
                    }
                ],
                reason="candidate edit",
            )
            edit_dir = Path(tmpdir) / "candidate"
            edit_dir.mkdir()
            candidate_path = edit_dir / "result.json"
            parent_path = edit_dir / "parent_result.json"
            candidate_path.write_text(json.dumps(candidate.to_jsonable()), encoding="utf-8")
            parent_path.write_text(json.dumps(result.to_jsonable()), encoding="utf-8")
            output_dir = Path(tmpdir) / "rejected"
            script = (
                Path(__file__).resolve().parents[1]
                / "km-curve-digitizer"
                / "scripts"
                / "refine_km.py"
            )
            env = os.environ.copy()
            env.setdefault("MPLCONFIGDIR", str(Path(tmpdir) / ".mplconfig"))

            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "verify",
                    str(candidate_path),
                    "--decision",
                    "reject",
                    "--verification",
                    "The edit removes a genuine visible step",
                    "--output-dir",
                    str(output_dir),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads((output_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["curves"], result.to_jsonable()["curves"])
            self.assertEqual(payload["revisions"][-1]["status"], "rejected")
            self.assertTrue((output_dir / "rejected_candidate.json").exists())

    def test_refine_cli_inspect_exports_point_ids(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            result_path = Path(tmpdir) / "result.json"
            output_dir = Path(tmpdir) / "inspection"
            result_path.write_text(json.dumps(result.to_jsonable()), encoding="utf-8")
            script = (
                Path(__file__).resolve().parents[1]
                / "km-curve-digitizer"
                / "scripts"
                / "refine_km.py"
            )
            env = os.environ.copy()
            env.setdefault("MPLCONFIGDIR", str(Path(tmpdir) / ".mplconfig"))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "inspect",
                    str(result_path),
                    "--curve",
                    "Treatment",
                    "--time-range",
                    "8,12",
                    "--max-labels",
                    "12",
                    "--output-dir",
                    str(output_dir),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output_dir / "point_review.png").exists())
            payload = json.loads((output_dir / "points.json").read_text(encoding="utf-8"))
            self.assertTrue(payload["points"])
            self.assertTrue(all("point_id" in point for point in payload["points"]))
            self.assertTrue(all(8 <= point["time"] <= 12 for point in payload["points"]))

    def test_refine_cli_inspect_risk_exports_cells_and_review(self):
        with TemporaryDirectory() as tmpdir:
            result = make_result(tmpdir)
            result_path = Path(tmpdir) / "result.json"
            output_dir = Path(tmpdir) / "risk_inspection"
            result_path.write_text(json.dumps(result.to_jsonable()), encoding="utf-8")
            script = (
                Path(__file__).resolve().parents[1]
                / "km-curve-digitizer"
                / "scripts"
                / "refine_km.py"
            )
            env = os.environ.copy()
            env.setdefault("MPLCONFIGDIR", str(Path(tmpdir) / ".mplconfig"))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "inspect-risk",
                    str(result_path),
                    "--output-dir",
                    str(output_dir),
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output_dir / "risk_table_review.png").exists())
            self.assertTrue((output_dir / "risk_table.csv").exists())
            payload = json.loads((output_dir / "risk_table.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["cells"][0]["cell_id"], "risk-c1-t000")
            self.assertEqual(payload["cells"][0]["confidence"], "high")


if __name__ == "__main__":
    unittest.main()
