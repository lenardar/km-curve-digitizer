# Review Bundle: review

## Summary

- Visual acceptance: `rejected; required local boards show unsupported plateaus and misplaced steps`
- Diagnostic checks: `5/8 passed` (navigation only)
- Diagnostic issues: `17`
- Image: `study04_os.png`
- Notes: Focused on panel A (OS) only. Total events and median OS were taken from the OS summary table above the plot. Legend is inside the OS panel; curve-color mapping estimated visually.

## Citation

Not provided

## Side-by-Side Review

| Original panel | Digitization overlay |
| --- | --- |
| ![original](original.png) | ![overlay](overlay.png) |



## Required Local Reviews

Acceptance requires comparing the source-only and overlay panes for every issue ID below.

- `q001-source_gap_review`: [source_gap_review](quality_hotspots/q001-source_gap_review.png) — curve 'Nivolumab' is forward-filled across 11 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q002-source_gap_review`: [source_gap_review](quality_hotspots/q002-source_gap_review.png) — curve 'Nivolumab' is forward-filled across 16 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q003-source_gap_review`: [source_gap_review](quality_hotspots/q003-source_gap_review.png) — curve 'Nivolumab' is forward-filled across 11 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q004-source_gap_review`: [source_gap_review](quality_hotspots/q004-source_gap_review.png) — curve 'Nivolumab' is forward-filled across 10 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q005-source_gap_review`: [source_gap_review](quality_hotspots/q005-source_gap_review.png) — curve 'Nivolumab' is forward-filled across 16 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q006-source_gap_review`: [source_gap_review](quality_hotspots/q006-source_gap_review.png) — curve 'Nivolumab' is forward-filled across 11 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q007-source_gap_review`: [source_gap_review](quality_hotspots/q007-source_gap_review.png) — curve 'Bevacizumab' is forward-filled across 19 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q008-source_gap_review`: [source_gap_review](quality_hotspots/q008-source_gap_review.png) — curve 'Bevacizumab' is forward-filled across 12 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q009-source_gap_review`: [source_gap_review](quality_hotspots/q009-source_gap_review.png) — curve 'Bevacizumab' is forward-filled across 16 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q010-source_gap_review`: [source_gap_review](quality_hotspots/q010-source_gap_review.png) — curve 'Bevacizumab' is forward-filled across 13 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q011-source_gap_review`: [source_gap_review](quality_hotspots/q011-source_gap_review.png) — curve 'Bevacizumab' is forward-filled across 12 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `q012-curve_identity_review`: [curve_identity_review](quality_hotspots/q012-curve_identity_review.png) — curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 7 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `q013-curve_identity_review`: [curve_identity_review](quality_hotspots/q013-curve_identity_review.png) — curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 17 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `q014-curve_identity_review`: [curve_identity_review](quality_hotspots/q014-curve_identity_review.png) — curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 13 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `q015-overlap_ambiguity`: [overlap_ambiguity](quality_hotspots/q015-overlap_ambiguity.png) — curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 22 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `q016-overlap_ambiguity`: [overlap_ambiguity](quality_hotspots/q016-overlap_ambiguity.png) — curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 20 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `q017-curve_identity_review`: [curve_identity_review](quality_hotspots/q017-curve_identity_review.png) — curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 16 consecutive columns; inspect the source crop to confirm that neither trace changes identity





## Number at Risk

![number-at-risk review](risk_table_review.png)


## Curves

- `Nivolumab`: 269 points, tolerance=12
- `Bevacizumab`: 303 points, tolerance=8

## Validation Issues

- `source_gap_review`: curve 'Nivolumab' is forward-filled across 11 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `source_gap_review`: curve 'Nivolumab' is forward-filled across 16 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `source_gap_review`: curve 'Nivolumab' is forward-filled across 11 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `source_gap_review`: curve 'Nivolumab' is forward-filled across 10 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `source_gap_review`: curve 'Nivolumab' is forward-filled across 16 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `source_gap_review`: curve 'Nivolumab' is forward-filled across 11 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `source_gap_review`: curve 'Bevacizumab' is forward-filled across 19 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `source_gap_review`: curve 'Bevacizumab' is forward-filled across 12 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `source_gap_review`: curve 'Bevacizumab' is forward-filled across 16 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `source_gap_review`: curve 'Bevacizumab' is forward-filled across 13 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `source_gap_review`: curve 'Bevacizumab' is forward-filled across 12 columns without matching source-color pixels; inspect the source crop for a missed drop or trace switch
- `curve_identity_review`: curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 7 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `curve_identity_review`: curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 17 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `curve_identity_review`: curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 13 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `overlap_ambiguity`: curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 22 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `overlap_ambiguity`: curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 20 consecutive columns; inspect the source crop to confirm that neither trace changes identity
- `curve_identity_review`: curves 'Nivolumab' and 'Bevacizumab' are within 4 pixels for 16 consecutive columns; inspect the source crop to confirm that neither trace changes identity

## Files

- [digitized_curves.csv](digitized_curves.csv)
- [validation_issues.csv](validation_issues.csv)
- [quality_hotspots.json](quality_hotspots.json)
- [risk_table.csv](risk_table.csv)
- [risk_table.json](risk_table.json)
