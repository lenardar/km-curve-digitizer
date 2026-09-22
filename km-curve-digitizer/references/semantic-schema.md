# Semantic metadata schema

Use this schema to describe what is printed in the Kaplan-Meier figure before pixel extraction:

```json
{
  "n_curves": 2,
  "x_axis": {
    "min": 0,
    "max": 24,
    "unit": "months",
    "label": "Time"
  },
  "y_axis": {
    "min": 0,
    "max": 100,
    "is_percentage": true,
    "label": "Overall survival (%)"
  },
  "curves": [
    {
      "id": 1,
      "legend_name": "Treatment",
      "color_description": "blue solid line",
      "rgb_approx": [31, 119, 180],
      "pixel_tolerance": 18,
      "line_style": "solid"
    },
    {
      "id": 2,
      "legend_name": "Control",
      "color_description": "red solid line",
      "rgb_approx": [214, 39, 40],
      "pixel_tolerance": 12,
      "line_style": "solid"
    }
  ],
  "at_risk_table": {
    "time_points": [0, 6, 12, 18, 24],
    "counts_by_curve": [
      [120, 95, 70, 48, 30],
      [118, 90, null, 41, 22]
    ]
  },
  "total_events_by_curve": [null, null],
  "has_confidence_interval": false,
  "has_censoring_marks": true,
  "confidence": {
    "overall": "high",
    "at_risk_table": "high",
    "color_identification": "medium"
  },
  "notes": ""
}
```

Requirements:

- `n_curves` must equal the number of entries in `curves`.
- Axis maxima and minima describe the focused plot panel, not a neighboring panel.
- Use the treatment or group name for `legend_name`.
- `rgb_approx` is always three integers from 0 to 255. Sample the visible curve color, not the legend text or confidence ribbon.
- `pixel_tolerance` is optional. Leave it out for adaptive extraction. Set it only after comparing overlays at different tolerances; smaller values reduce cross-curve contamination, while larger values recover faint antialiased traces.
- Every at-risk row must correspond to the curves in the same order and contain one cell per time point.
- Use `null` for an unreadable cell. Use empty arrays when no at-risk table is visible. Do not invent missing counts.
- Preserve the value as printed or observed, even when a row is unexpectedly non-monotonic. Validation will flag the sequence for visual review instead of silently changing it.
- Confidence values are `high`, `medium`, or `low`.

An axis override file may contain:

```json
{
  "axis_bounds": {"left": 70, "right": 580, "top": 40, "bottom": 300},
  "axis_anchors": {
    "x_min_point": {"x": 70, "y": 300},
    "x_max_point": {"x": 580, "y": 300},
    "y_min_point": {"x": 70, "y": 300},
    "y_max_point": {"x": 70, "y": 40}
  }
}
```

Bounds use source-image pixel coordinates. Anchors are optional; when absent they are derived from the rectangular bounds.
