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
   - Otherwise inspect the figure yourself and create JSON matching [references/semantic-schema.md](references/semantic-schema.md).
   - Do not call or configure another vision model. The Codex instance using this Skill is the visual reasoner.
3. Create a dedicated output directory. Do not overwrite the source image.
4. Run the deterministic extractor:

   ```bash
   python3 <skill-dir>/scripts/extract_km.py figure.png \
     --semantic-json semantic.json \
     --output-json output/result.json \
     --review-dir output/review
   ```

5. Read [references/agent-loop.md](references/agent-loop.md), then personally inspect `review/overlay.png`, `result.json`, `review/validation_issues.csv`, and—when present—`review/risk_table_review.png`. Treat validation as a navigation hint, never as edit authority.
6. Use the inspection tools to gather focused evidence, record the visible observation, decide the edit, and apply it as a candidate revision.
7. Compare the before/after artifacts, then run `refine_km.py verify` to explicitly accept or reject the candidate. If no edit was needed, run `verify` on the base extraction so the visual acceptance is still recorded. Continue from an accepted result only when the visible source supports it; rejection restores the parent data while preserving the rejected revision in the audit trail.
8. Repeat until no visible defect remains that the available evidence can resolve. Do not stop at recommending that a human perform an edit the skill already exposes.
9. If the overlay shows incorrect plot bounds, write a reviewed `--axis-json`, rerun, and inspect the new overlay. Use `--axis-export-json` to preserve accepted calibration.
10. Report the accepted output paths, revisions, unresolved ambiguity, and diagnostic findings. The Skill intentionally has no aggregate quality score; visual agreement with the source is the acceptance criterion.

## Agent Authority

- The calling model chooses what to inspect and whether to add, delete, move, replace, correct, clear, accept, or reject.
- Geometry detection and diagnostic checks may direct attention but must not autonomously change extracted evidence.
- Keep edits narrow and evidence-backed. A related cluster may be edited together, but do not bundle unrelated guesses into one revision.
- Do not delegate semantic reading, axis choice, point correction, or acceptance to an internal or external model. Use the deterministic tools directly.

## Visual Point Editing

When the overlay contains missing, misplaced, or extraneous points, read [references/correction-schema.md](references/correction-schema.md). Inspect the affected segment to obtain stable point IDs, then apply the model's narrow add, delete, move, or replace decision through `scripts/refine_km.py`.

Always compare the generated before/after overlays. Accept an edit only when it follows visible source evidence and does not damage neighboring segments. The editor preserves the parent result and records observation, actions, status, and verification in the new result's `revisions` list.

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

For several panels, create one semantic JSON per panel from your own inspection and invoke `extract_km.py` for each manifest entry. Batch orchestration belongs to the calling Codex workflow; this Skill does not call another model or require an API key.

## Review Rules

- Give grayscale curves, similar colors, confidence ribbons, dense censoring marks, and overlapping curves closer model inspection.
- Preserve KM curves as right-continuous steps; do not smooth them into continuous trajectories.
- Reject any overlay that visually connects KM plateaus with diagonal interpolation; inspect or edit the underlying segment and render it as `steps-post`.
- Treat every number-at-risk correction as a visible transcription claim. Prefer `null` to a guessed count.
- Do not infer hazard ratios, medians, patient-level events, or treatment effects unless they are independently visible or supplied.
- Keep credentials out of semantic JSON, result files, and review bundles.

## Environment

The scripts require Python 3.9+ and the packages listed in `scripts/requirements.txt`. If imports fail, explain the missing packages and ask before installing anything.
