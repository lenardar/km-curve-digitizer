# Model-operated review loop

The calling model owns the review. Scripts provide perception and action primitives; validation output does not authorize edits.

## Observe

1. View the original figure and the complete extraction overlay.
2. Compare curve identity, plot bounds, step shape, tails, and number-at-risk values against visible source evidence.
3. Use validation issues only to decide where to look next. Also inspect visible problems that no validator reports.

## Inspect

- For a curve segment, run `refine_km.py inspect` with a narrow time range or pixel region and view the labelled point board.
- For the table, run `refine_km.py inspect-risk`; use `inspect-risk-cell` for a crowded or ambiguous cell.
- Inspect neighboring points or cells before deciding. Context distinguishes a real step from noise and a target value from an adjacent row.

## Act

Choose the smallest action supported by the image:

- Curve: `delete_points`, `add_points`, `move_point`, or `replace_segment`.
- Table: `set_risk_cell`, `delete_risk_cell`, or `set_risk_time`.
- Axis: write reviewed bounds or anchors and rerun extraction.

Do not translate a validation warning directly into an action. For example, a non-monotonic risk row is a reason to inspect the cells, not permission to decrease a value.

## Verify

1. Run `apply` into a new directory.
2. View both before and after overlays and any relevant focused inspection.
3. Accept by continuing from the new `result.json`; reject by retaining `parent_result.json`.
4. Repeat only while a visible, resolvable discrepancy remains.

Stop with an explicit uncertainty note when the pixels cannot distinguish the alternatives. Do not guess merely to make validation pass, and do not hand an executable edit back to the user when the model can perform it itself.
