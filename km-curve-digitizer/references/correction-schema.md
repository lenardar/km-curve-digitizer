# Curve correction actions

Use `scripts/refine_km.py` when the model's visual comparison shows missing, misplaced, or extraneous points. Inspect a focused segment first; issue an edit only after viewing that evidence:

```bash
python3 <skill-dir>/scripts/refine_km.py inspect result.json \
  --curve Nivolumab \
  --time-range 10,16 \
  --output-dir inspection
```

Read `inspection/points.json` and view `inspection/point_review.png`. Then create an actions file:

```json
{
  "reason": "Visual review of the 10-16 month segment",
  "actions": []
}
```

Apply it to a new output directory:

```bash
python3 <skill-dir>/scripts/refine_km.py apply result.json \
  --actions corrections.json \
  --output-dir refined
```

The command preserves `parent_result.json`, writes the new `result.json`, records a revision, and generates before/after overlays. It refuses to write into a non-empty output directory.

## Delete points

Prefer stable point IDs from `points.json`:

```json
{
  "type": "delete_points",
  "curve": "Nivolumab",
  "point_ids": ["c1-p0121", "c1-p0122"]
}
```

The action also accepts one or more of these selectors:

```json
{
  "type": "delete_points",
  "curve": "Nivolumab",
  "point_indices": [121, 122],
  "time_range": [12.0, 12.4],
  "pixel_region": [210, 170, 245, 205]
}
```

Selectors are combined. Use a narrow region and inspect it first.

## Add points

Add points from visible image pixels when possible:

```json
{
  "type": "add_points",
  "curve": "Nivolumab",
  "points": [
    {"x_pixel": 245, "y_pixel": 196},
    {"x_pixel": 252, "y_pixel": 198}
  ]
}
```

Data coordinates are also accepted:

```json
{
  "type": "add_points",
  "curve": "Nivolumab",
  "points": [{"time": 12.0, "survival": 0.41}]
}
```

Do not add points where the source curve is not visible.

## Move one point

```json
{
  "type": "move_point",
  "curve": "Nivolumab",
  "point_id": "c1-p0121",
  "to": {"x_pixel": 245, "y_pixel": 196}
}
```

The target may instead contain `time` and `survival`.

## Replace a segment

```json
{
  "type": "replace_segment",
  "curve": "Nivolumab",
  "time_range": [12, 15],
  "points": [
    {"x_pixel": 245, "y_pixel": 196},
    {"x_pixel": 252, "y_pixel": 198}
  ]
}
```

Replacement removes the existing points in the inclusive time range and inserts the supplied visible points.

## Invariants

- The model selects actions from source evidence; validators never select or apply them.
- Edits never overwrite the parent result.
- Pixel and data coordinates are recalculated together after editing.
- Survival remains within 0-1 and is normalized to a non-increasing KM curve.
- Unedited curves retain their point IDs and values.
- Every applied action is stored in `revisions` in the edited result.
