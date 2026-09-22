# Study04 OS overlapping-window example

## Outcome

The edited candidate was accepted after five overlapping source-first windows. Four Nivolumab segments were replaced with source-pixel coordinates; Bevacizumab and all 20 number-at-risk cells were preserved.

## Why this panel is difficult

- Both curves are blue-gray and repeatedly approach or cross.
- Censor marks interrupt exact-color coverage.
- The HR annotation overlaps the region where the dark curve descends.
- A tighter color tolerance loses genuine steps instead of reliably separating the traces.

## Evidence

- [Edit actions](nivolumab-corrections.json)
- [Before/after comparison manifest](comparison/scan_comparison.json)
- [Window 1: source / before / after Nivolumab](comparison/w001_curve_1_comparison.png)
- [Window 2: source / before / after Nivolumab](comparison/w002_curve_1_comparison.png)
- [Window 3: annotation-affected Nivolumab segment](comparison/w003_curve_1_comparison.png)
- [Window 4: late Nivolumab descent](comparison/w004_curve_1_comparison.png)
- [Window 5: terminal Nivolumab plateau](comparison/w005_curve_1_comparison.png)
- [Unchanged Bevacizumab control](comparison/w003_curve_2_comparison.png)
- [Completed after-scan evidence](candidate/narrow-scan/scan_review.json)
- [Number-at-risk review](candidate/review/risk_table_review.png)
- [Accepted overlay](accepted/overlay.png)
- [Accepted result](accepted/result.json)
- [Acceptance decision](accepted/review_decision.json)

## Decision trail

1. The initial five-window scan recorded Nivolumab defects across the complete x-axis while Bevacizumab remained clear.
2. A tolerance-only retry was rejected because it created longer unsupported plateaus.
3. Four narrow Nivolumab segments were replaced using visible source pixels.
4. The candidate was rescanned with a new result signature.
5. All after windows and diagnostic issues received evidence-backed terminal states before `verify` accepted revision `r0002`.
