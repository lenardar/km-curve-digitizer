# Review Bundle: study01 PFS

## Summary

- Visual acceptance: `pending model review`
- Diagnostic checks: `5/6 passed` (navigation only)
- Diagnostic issues: `1`
- Image: `study01_pfs.png`
- Notes: Focused on panel B (Progression-free survival). Legend/color mapping taken from the figure legend shown with panel A. At-risk table for PFS appears at 3-month intervals from 0 to 45 months; no total event counts are shown for the PFS panel.

## Citation

Qin S, Kudo M, Meyer T, et al. Tislelizumab vs Sorafenib as First-Line Treatment for Unresectable Hepatocellular Carcinoma: A Phase 3 Randomized Clinical Trial. JAMA Oncol. 2023;9(12):1651–1659. doi:10.1001/jamaoncol.2023.4003

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
