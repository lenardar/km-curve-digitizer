# Review Bundle: review

## Summary

- Visual acceptance: `accepted after source-only grayscale identity review; see review_decision.json`
- Diagnostic checks: `5/6 passed` (navigation only)
- Diagnostic issues: `1`
- Image: `study04_os.png`
- Notes: Focused on panel A (OS) only. Total events and median OS were taken from the OS summary table above the plot. Legend is inside the OS panel; curve-color mapping estimated visually.

## Citation

Not provided

## Side-by-Side Review

| Original panel | Digitization overlay |
| --- | --- |
| ![original](original.png) | ![overlay](overlay.png) |





## Number at Risk

![number-at-risk review](risk_table_review.png)


## Curves

- `Nivolumab`: 269 points, tolerance=12
- `Bevacizumab`: 303 points, tolerance=8

## Validation Issues

- `overlap_ambiguity`: curves 'Nivolumab' and 'Bevacizumab' share a long overlapping segment; closer model inspection is recommended

## Files

- [digitized_curves.csv](digitized_curves.csv)
- [validation_issues.csv](validation_issues.csv)
- [risk_table.csv](risk_table.csv)
- [risk_table.json](risk_table.json)
