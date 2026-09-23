# Study03 PFS overlapping-window example

## Outcome

The edited candidate was accepted after five overlapping source-first windows. Both curves were rebuilt from visible pixel breakpoints, replacing the earlier coarse data-coordinate approximation. All 12 number-at-risk cells were independently checked against the source.

## Why this panel is difficult

- Both curves contain many tightly spaced drops during the first 15 months.
- The blue-gray BSC curve has several transitions only two to four pixels apart.
- Censor marks interrupt the curve colors and can be mistaken for drops.
- Whole-panel overlays hide small horizontal timing errors that become obvious in enlarged local windows.

## Evidence

- [Pixel-coordinate edit actions](pixel-curve-corrections.json)
- [Before/after comparison manifest](comparison/scan_comparison.json)
- [Window 1: Capecitabine source / before / after](comparison/w001_curve_1_comparison.png)
- [Window 1: BSC source / before / after](comparison/w001_curve_2_comparison.png)
- [Window 2: Capecitabine overlap check](comparison/w002_curve_1_comparison.png)
- [Window 2: BSC overlap check](comparison/w002_curve_2_comparison.png)
- [Late-curve Capecitabine control](comparison/w004_curve_1_comparison.png)
- [Late-curve BSC control](comparison/w004_curve_2_comparison.png)
- [Completed initial defect review](base-scan/scan_review.json)
- [Completed candidate review](candidate/narrow-scan/scan_review.json)
- [Number-at-risk review](candidate/review/risk_table_review.png)
- [Accepted overlay](accepted/overlay.png)
- [Accepted result](accepted/result.json)
- [Acceptance decision](accepted/review_decision.json)

## Decision trail

1. The initial five-window scan found two orange transitions displaced by about 5-6 pixels and multiple early BSC transitions displaced by about 5-28 pixels.
2. Source-only enlargements were used to read right-continuous step breakpoints directly in image coordinates.
3. Both full curves were replaced so the repair would not mix incompatible coarse and pixel-level coordinate estimates.
4. A new five-window scan checked all ten curve-specific overlays, including overlapping boundary regions and unchanged late plateaus.
5. The 12 number-at-risk cells matched the visible table: 52/38/19/6/4/1 and 52/20/9/5/3/0.
6. The scan review received evidence-backed terminal states before `verify` accepted revision `r0002`.

