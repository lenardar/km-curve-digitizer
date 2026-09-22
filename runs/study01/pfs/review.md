# Review Bundle: study01 pfs detailed review

## Summary

- Visual acceptance: `accepted after detailed local model review`; see `review_decision.json`
- Diagnostic checks: `5/6 passed` (navigation only)
- Diagnostic issues: `1`
- Image: `study01_pfs.png`
- Notes: Focused on panel B (Progression-free survival). Legend/color mapping taken from the figure legend shown with panel A. At-risk table for PFS appears at 3-month intervals from 0 to 45 months; no total event counts are shown for the PFS panel.

## Citation

Not provided

## Side-by-Side Review

| Original panel | Digitization overlay |
| --- | --- |
| ![original](original.png) | ![overlay](overlay.png) |





## Number at Risk

![number-at-risk review](risk_table_review.png)


## Curves

- `Tislelizumab`: 549 points, tolerance=40
- `Sorafenib`: 438 points, tolerance=64

## Validation Issues

- `coverage`: curve 'Sorafenib' covers too little of the x-axis

## Files

- [digitized_curves.csv](digitized_curves.csv)
- [validation_issues.csv](validation_issues.csv)
- [risk_table.csv](risk_table.csv)
- [risk_table.json](risk_table.json)
