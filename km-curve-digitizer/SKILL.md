---
name: km-curve-digitizer
description: Digitize and visually refine Kaplan-Meier survival curves and number-at-risk tables from figure images into inspectable CSV and JSON outputs, with controlled point and cell editing, axis calibration, validation signals, and review overlays. Use when extracting or correcting KM figures from papers or screenshots; do not use for fitting survival models or reconstructing individual patient data.
---

# KM Curve Digitizer

Turn one or more Kaplan-Meier figure images into inspectable curve and number-at-risk data. Keep measurement and interpretation separate: this skill digitizes visible evidence but does not reconstruct patient-level data or fit survival models.

## Workflow

1. Inspect the source image and determine whether it contains one panel or several. For a multi-panel figure, prefer a cropped panel for measurement and retain the full figure as semantic context.
2. Resolve semantic metadata before measuring pixels:
   - Use a supplied semantic JSON when available.
   - Otherwise inspect the figure and create JSON matching [references/semantic-schema.md](references/semantic-schema.md).
   - Use an OpenAI-compatible vision endpoint only when the user has configured and authorized one.
3. Create a dedicated output directory. Do not overwrite the source image.
4. Run the deterministic extractor:

   ```bash
   python3 <skill-dir>/scripts/extract_km.py figure.png \
     --semantic-json semantic.json \
     --output-json output/result.json \
     --review-dir output/review
   ```

5. Inspect `review/overlay.png`, `result.json`, `review/validation_issues.csv`, and—when present—`review/risk_table_review.png`. A high score is a heuristic signal, not proof that the extraction is scientifically accurate.
6. If the overlay shows incorrect plot bounds, provide a reviewed `--axis-json`, rerun, and inspect the new overlay. Use `--axis-export-json` to preserve accepted calibration.
7. Report the output paths, validation findings, and any visible uncertainty. Explicitly flag weak cases rather than forcing a clean-looking result.

## Visual Point Editing

When the overlay contains missing, misplaced, or extraneous points, read [references/correction-schema.md](references/correction-schema.md). Inspect the affected segment to obtain stable point IDs, then let the model apply narrow add, delete, move, or replace actions through `scripts/refine_km.py`.

Always compare the generated before/after overlays. Accept an edit only when it follows visible source evidence and does not damage neighboring segments. The editor preserves the parent result and records every action in the new result's `revisions` list.

## Number-at-Risk Table Editing

When a number-at-risk table is visible, read [references/risk-table.md](references/risk-table.md). The review bundle exports long-format `risk_table.csv`, structured `risk_table.json`, and a board that places the source table beside stable cell IDs.

Use `scripts/refine_km.py inspect-risk` before editing. The model may correct or clear individual cells and adjust a time column through narrow, auditable actions. Never invent a value for an unreadable cell, and never silently force the row to decrease; preserve the observed value and let validation flag implausible sequences.

## Multiple Studies

For grouped files named like `study01_full.png`, `study01_pfs.png`, and `study01_os.png`, build a manifest with:

```bash
python3 <skill-dir>/scripts/build_manifest.py \
  --image-dir images \
  --literature-md images/literatures.md \
  --output-json output/manifest.json
```

Run the online batch workflow only when an OpenAI-compatible vision endpoint and API-key environment variable are already configured:

```bash
python3 <skill-dir>/scripts/run_batch.py \
  --image-dir images \
  --base-url <base-url> \
  --model <vision-model> \
  --api-key-env <key-variable> \
  --output-dir output/batch
```

## Review Rules

- Treat grayscale curves, similar colors, confidence ribbons, dense censoring marks, and overlapping curves as manual-review cases.
- Preserve KM curves as right-continuous steps; do not smooth them into continuous trajectories.
- Treat every number-at-risk correction as a visible transcription claim. Prefer `null` to a guessed count.
- Do not infer hazard ratios, medians, patient-level events, or treatment effects unless they are independently visible or supplied.
- Keep credentials out of semantic JSON, result files, and review bundles.

## Environment

The scripts require Python 3.9+ and the packages listed in `scripts/requirements.txt`. If imports fail, explain the missing packages and ask before installing anything.
