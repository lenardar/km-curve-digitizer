# Model-operated review loop

The calling model owns the review. Scripts provide perception and action primitives; diagnostic output does not authorize edits. There is intentionally no aggregate quality score.

## Observe

1. View the original figure and the complete extraction overlay to establish context.
2. Open `scan_windows/scan_windows.json` and move through every window in order. For each window, view the source-only image before any overlay, then the combined overlay and each curve-focused overlay. Follow each curve into the overlap with the next window; a trace may not silently change identity at the boundary.
3. Record a concrete observation for the window and for every curve in `scan_review.json`. Do not mark a window from the overlay alone.
4. Compare plot bounds, right-continuous step shape, vertical drops, plateaus, crossings, and tails against visible source evidence.
5. Use validation issues only to decide where to zoom further. Open every local board listed in `quality_hotspots.json`, but also act on visible problems that no validator reports.

## Inspect

- For a curve segment, run `refine_km.py inspect --source-only` first to view unobscured pixels, then run it again without that flag to obtain stable point IDs for editing.
- For the table, run `refine_km.py inspect-risk`; use `inspect-risk-cell` for a crowded or ambiguous cell.
- Inspect neighboring points or cells before deciding. Context distinguishes a real step from noise and a target value from an adjacent row.

## Act

Choose the smallest action supported by the image:

- Curve: `delete_points`, `add_points`, `move_point`, or `replace_segment`.
- Table: `set_risk_cell`, `delete_risk_cell`, or `set_risk_time`.
- Axis: write reviewed bounds or anchors and rerun extraction.

Do not translate a validation warning directly into an action. For example, a non-monotonic risk row is a reason to inspect the cells, not permission to decrease a value.

## Verify

1. Run `apply` into a new directory; this creates a `candidate` revision.
2. View both before and after overlays and any relevant focused inspection.
3. Use the candidate's generated scan windows and complete its new `scan_review.json`. Never reuse the parent's scan review: the result signature deliberately makes that fail.
4. Use `clear` when a window/curve agrees with the source, `confirmed_defect` when it visibly disagrees, `resolved` when the current candidate fixes that discrepancy, and `ambiguous` when the pixels cannot decide. Diagnostic issue reviews additionally allow `false_positive`; include the window IDs and the visible reason.
5. Run `verify --decision accept|reject --verification "..." --scan-review <path>` into another new directory. Acceptance keeps the edited data only when all windows, curves, and issues have evidence-backed terminal states; rejection restores the parent and retains the rejected candidate for audit.

When the base extraction already follows the source and no edit is necessary, run `verify` directly on that base result. The command records a `base_extraction` decision without inventing a point revision.
6. Continue only from the verified `result.json`, and repeat only while a visible, resolvable discrepancy remains.

Stop with an explicit uncertainty note when the pixels cannot distinguish the alternatives. Do not guess merely to make validation pass, and do not hand an executable edit back to the user when the model can perform it itself.
