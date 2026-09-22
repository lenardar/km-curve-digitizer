---
name: km-curve-digitizer
description: Autonomously inspect, digitize, and refine Kaplan-Meier curves and number-at-risk tables from figure images, using agent-controlled point and cell edits with reviewable CSV, JSON, and overlays. Use when extracting or correcting KM figures from papers or screenshots; do not use for fitting survival models or reconstructing individual patient data.
---

# KM Curve Digitizer

Turn one or more Kaplan-Meier figure images into inspectable curve and number-at-risk data. The model is the operator: deterministic scripts expose evidence and execute precise edits, but they do not decide what the figure means or which visible value should replace another. Keep measurement and interpretation separate; do not reconstruct patient-level data or fit survival models.

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

5. Read [references/agent-loop.md](references/agent-loop.md), then personally inspect `review/overlay.png`, `result.json`, `review/validation_issues.csv`, and—when present—`review/risk_table_review.png`. Treat validation as a navigation hint, never as edit authority.
6. Use the inspection tools to gather focused evidence, decide the edit, apply it, and compare before/after artifacts. Continue from the edited result only when the visible source supports the change; otherwise retain the parent result.
7. Repeat until no visible defect remains that the available evidence can resolve. Do not stop at recommending that a human perform an edit the skill already exposes.
8. If the overlay shows incorrect plot bounds, write a reviewed `--axis-json`, rerun, and inspect the new overlay. Use `--axis-export-json` to preserve accepted calibration.
9. Report the accepted output paths, revisions, unresolved ambiguity, and validation findings. A high score is not proof of scientific accuracy.

## Agent Authority

- The calling model chooses what to inspect and whether to add, delete, move, replace, correct, clear, accept, or reject.
- Geometry detection, validation checks, and scores may direct attention but must not autonomously change extracted evidence.
- Keep edits narrow and evidence-backed. A related cluster may be edited together, but do not bundle unrelated guesses into one revision.
- The optional internal provider passes `--axis-refine` and `--segment-micro-tune` are not the primary Skill workflow. Do not invoke them as a substitute for the calling model's own inspection unless the user explicitly requests those automatic passes.

## Visual Point Editing

When the overlay contains missing, misplaced, or extraneous points, read [references/correction-schema.md](references/correction-schema.md). Inspect the affected segment to obtain stable point IDs, then apply the model's narrow add, delete, move, or replace decision through `scripts/refine_km.py`.

Always compare the generated before/after overlays. Accept an edit only when it follows visible source evidence and does not damage neighboring segments. The editor preserves the parent result and records every action in the new result's `revisions` list.

## Number-at-Risk Table Editing

When a number-at-risk table is visible, read [references/risk-table.md](references/risk-table.md). The review bundle exports long-format `risk_table.csv`, structured `risk_table.json`, and a board that places the source table beside stable cell IDs and localized source boxes when geometry is reliable.

Use `scripts/refine_km.py inspect-risk` before editing, and `inspect-risk-cell` when a single value needs a larger source crop. The model may correct or clear individual cells and adjust a time column through narrow, auditable actions. Never invent a value for an unreadable cell, and never silently force the row to decrease; preserve the observed value and let validation flag implausible sequences.

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

- Give grayscale curves, similar colors, confidence ribbons, dense censoring marks, and overlapping curves closer model inspection.
- Preserve KM curves as right-continuous steps; do not smooth them into continuous trajectories.
- Treat every number-at-risk correction as a visible transcription claim. Prefer `null` to a guessed count.
- Do not infer hazard ratios, medians, patient-level events, or treatment effects unless they are independently visible or supplied.
- Keep credentials out of semantic JSON, result files, and review bundles.

## Environment

The scripts require Python 3.9+ and the packages listed in `scripts/requirements.txt`. If imports fail, explain the missing packages and ask before installing anything.
