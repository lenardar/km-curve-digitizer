# Number-at-risk review and correction

Number-at-risk values are evidence copied from the figure, not values inferred from the extracted curves. Inspect the table before changing it:

```bash
python3 <skill-dir>/scripts/refine_km.py inspect-risk result.json \
  --output-dir risk-inspection
```

The command writes:

- `risk_table_review.png`: source context above an extracted table labelled with stable cell IDs.
- `risk_table.csv`: long-format rows for downstream software.
- `risk_table.json`: time points and full cell records, including raw text, confidence, and `pixel_region` when localization is reliable.

Cell IDs use `risk-c<curve-id>-t<zero-padded-time-index>`, for example `risk-c2-t004`. Review the source pixels, then pass corrections to the normal `apply` command:

For a crowded or ambiguous cell, render a dedicated enlarged crop before editing:

```bash
python3 <skill-dir>/scripts/refine_km.py inspect-risk-cell result.json \
  --cell-id risk-c2-t004 \
  --output-dir cell-inspection
```

Read `risk_cell.json` and view `risk_cell_review.png`. The orange rectangle is the localized cell; surrounding pixels are retained as context.

Then pass corrections to the normal `apply` command:

```bash
python3 <skill-dir>/scripts/refine_km.py apply result.json \
  --actions risk-corrections.json \
  --output-dir corrected
```

## Set one count

```json
{
  "type": "set_risk_cell",
  "cell_id": "risk-c1-t002",
  "count": 67
}
```

Counts must be non-negative integers. Use this only when the printed value is legible.

## Clear an incorrect or unreadable count

```json
{
  "type": "delete_risk_cell",
  "cell_id": "risk-c2-t004"
}
```

This preserves the cell and sets its value to `null`; it does not shift later columns.

## Correct a time column

```json
{
  "type": "set_risk_time",
  "time_index": 2,
  "time": 12
}
```

Time points must remain strictly increasing. A time edit applies to every curve row at that column.

## Review rules

- Do not derive counts from curve height or repair them through interpolation.
- Do not silently sort or monotonize a row. A count increase may indicate OCR error, a table layout issue, or unusual reporting; preserve it and inspect the validation issue.
- Use `delete_risk_cell` when the source is occluded or genuinely unreadable.
- Every action records its prior value in the revision history, and `apply` preserves the parent result.
- `pixel_region` contains `[left, top, right, bottom]` source-image coordinates when the calibrated time columns and table text rows can be localized reliably. It remains `null` rather than exposing a guessed box when localization fails.
