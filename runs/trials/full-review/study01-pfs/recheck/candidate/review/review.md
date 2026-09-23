# Review Bundle: curve_edit_r0002

## Summary

- Visual acceptance: `pending model review`
- Diagnostic checks: `6/8 passed` (navigation only)
- Diagnostic issues: `3`
- Image: `study01_pfs.png`
- Notes: Focused on panel B (Progression-free survival). Legend/color mapping taken from the figure legend shown with panel A. At-risk table for PFS appears at 3-month intervals from 0 to 45 months; no total event counts are shown for the PFS panel.

## Citation

Not provided

## Side-by-Side Review

| Original panel | Digitization overlay |
| --- | --- |
| ![original](original.png) | ![overlay](overlay.png) |



## Required Local Reviews

Acceptance requires comparing the source-only and overlay panes for every issue ID below.

- `q002-curve_identity_review`: [curve_identity_review](quality_hotspots/q002-curve_identity_review.png) — curves 'Tislelizumab' and 'Sorafenib' are within 4 pixels for 16 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `q003-curve_identity_review`: [curve_identity_review](quality_hotspots/q003-curve_identity_review.png) — curves 'Tislelizumab' and 'Sorafenib' are within 4 pixels for 13 consecutive columns; inspect the source crop to confirm that neither trace changes identity



## Required Left-to-Right Scan

Inspect every overlapping window, source first, then each curve-focused overlay. Complete `scan_review.json`; acceptance is blocked by unreviewed, defective, or ambiguous windows.





## Number at Risk

![number-at-risk review](risk_table_review.png)


## Curves

- `Tislelizumab`: 543 points, tolerance=40
- `Sorafenib`: 405 points, tolerance=64

## Validation Issues

- `coverage`: curve 'Sorafenib' covers too little of the x-axis
- `curve_identity_review`: curves 'Tislelizumab' and 'Sorafenib' are within 4 pixels for 16 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `curve_identity_review`: curves 'Tislelizumab' and 'Sorafenib' are within 4 pixels for 13 consecutive columns; inspect the source crop to confirm that neither trace changes identity

## Files

- [digitized_curves.csv](digitized_curves.csv)
- [validation_issues.csv](validation_issues.csv)
- [quality_hotspots.json](quality_hotspots.json)
- [scan_windows.json](scan_windows/scan_windows.json)
- [scan_review.json](scan_windows/scan_review.json)
- [risk_table.csv](risk_table.csv)
- [risk_table.json](risk_table.json)
