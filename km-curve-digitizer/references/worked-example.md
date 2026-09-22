# Worked example: overlapping grayscale curves

This example records a failure pattern observed on a two-curve OS panel with dark gray-blue and light gray-blue KM traces, censor marks, and an HR annotation inside the plot.

## What failed

- A broad color tolerance produced plausible full-panel curves but allowed annotation pixels to enter the dark trace.
- Monotonic normalization then converted that local contamination into a long false plateau.
- Tightening both tolerances did not solve the problem: sparse exact-color columns created longer forward-filled plateaus.
- The full-panel overlay made both failures look less severe than they were.

## Evidence-led response

1. Scan the panel with narrow overlapping windows and view the source-only image before the overlay.
2. Review each curve separately so the neighboring curve is muted.
3. Treat a tighter-tolerance extraction as a candidate, not an automatic improvement. Reject it when the window sequence shows lost steps or longer unsupported plateaus.
4. Preserve the curve that already follows its source. Replace only visibly defective segments of the other curve with pixel-coordinate points.
5. Generate `compare-scan` triptychs and inspect every overlap. The after trace must follow the source and join unchanged neighbors without changing identity.
6. Regenerate the candidate scan review. Record detector warnings as `false_positive` only when the visible source supports continuity; record repaired regions as `resolved`.

## Decision rule

Do not choose between two extractions by tolerance, point count, warning count, or visual neatness. Prefer the candidate whose source-first windows preserve curve identity and visible KM steps across the complete x-axis. If neither does, edit the smallest source-supported segments and scan again.
