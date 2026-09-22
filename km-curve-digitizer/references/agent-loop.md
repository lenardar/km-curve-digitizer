# Model-operated review loop

The calling model owns the review. Scripts provide perception and action primitives; diagnostic output does not authorize edits. There is intentionally no aggregate quality score.

## Observe

1. View the original figure and the complete extraction overlay.
2. Compare curve identity, plot bounds, step shape, tails, and number-at-risk values against visible source evidence.
3. Use validation issues only to decide where to look next. Also inspect visible problems that no validator reports.
4. Open every local board listed in `quality_hotspots.json`. Compare its source-only pane with its extraction-overlay pane; these boards localize close traces, overlaps, and unsupported forward-filled gaps.

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
3. Run `verify --decision accept|reject --verification "..."` into another new directory. For acceptance, repeat `--reviewed-issue <issue-id>` for every required entry in `quality_hotspots.json`. The command refuses acceptance when any required local review is missing. Acceptance keeps the edited data; rejection restores the parent data and retains the rejected candidate for audit.

When the base extraction already follows the source and no edit is necessary, run `verify` directly on that base result. The command records a `base_extraction` decision without inventing a point revision.
4. Continue only from the verified `result.json`, and repeat only while a visible, resolvable discrepancy remains.

Stop with an explicit uncertainty note when the pixels cannot distinguish the alternatives. Do not guess merely to make validation pass, and do not hand an executable edit back to the user when the model can perform it itself.
