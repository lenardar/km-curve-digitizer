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

5. Read [references/agent-loop.md](references/agent-loop.md), then personally scan every entry in `review/scan_windows/scan_windows.json` from left to right. Inspect the source-only window first, then the combined and per-curve overlays. Adjacent windows overlap so curve identity and step continuity can be checked across boundaries. Also inspect `review/overlay.png`, `review/validation_issues.csv`, localized comparisons in `review/quality_hotspots.json`, and—when present—`review/risk_table_review.png`. Treat validation as a navigation hint, never as edit authority.
6. Fill the generated `review/scan_windows/scan_review.json` with visible observations for every window and every curve. Use `clear` only when source and trace agree, `confirmed_defect` when they visibly disagree, `resolved` only after an edit has been checked in the regenerated after-window, and `ambiguous` when the pixels cannot decide. Resolve each diagnostic issue as `false_positive`, `confirmed_defect`, `resolved`, or `ambiguous`, linking it to inspected windows.
7. Use the inspection tools to gather focused evidence, decide the smallest pixel-backed edit, and apply it as a candidate revision. Every edit invalidates the previous scan signature: scan the candidate again rather than reusing old evidence.
8. Compare the before/after artifacts, then run `refine_km.py verify --scan-review <completed-scan-review.json>` to explicitly accept or reject the candidate. Acceptance is refused while any window, curve, or diagnostic issue remains unreviewed, defective, or ambiguous. If no edit was needed, verify the base extraction with its completed scan review. Rejection restores the parent data while preserving the rejected revision in the audit trail.
9. Repeat until no visible defect remains that the available evidence can resolve. Do not stop at recommending that a human perform an edit the skill already exposes.
10. If the overlay shows incorrect plot bounds, write a reviewed `--axis-json`, rerun, and inspect the new overlay. Use `--axis-export-json` to preserve accepted calibration.
11. Report the accepted output paths, revisions, unresolved ambiguity, and diagnostic findings. The Skill intentionally has no aggregate quality score; visual agreement with the source is the acceptance criterion.

## Agent Authority

- The calling model chooses what to inspect and whether to add, delete, move, replace, correct, clear, accept, or reject.
- Geometry detection and diagnostic checks may direct attention but must not autonomously change extracted evidence.
- Keep edits narrow and evidence-backed. A related cluster may be edited together, but do not bundle unrelated guesses into one revision.
- Scan coverage is mandatory evidence, not a detector-selected checklist. A clean diagnostic report never permits skipping windows.
- Do not delegate semantic reading, axis choice, point correction, or acceptance to an internal or external model. Use the deterministic tools directly.

## Visual Point Editing

When the overlay contains missing, misplaced, or extraneous points, read [references/correction-schema.md](references/correction-schema.md). Inspect the affected segment to obtain stable point IDs, then apply the model's narrow add, delete, move, or replace decision through `scripts/refine_km.py`.

Always compare the generated before/after overlays. Accept an edit only when it follows visible source evidence and does not damage neighboring segments. The editor preserves the parent result and records observation, actions, status, and verification in the new result's `revisions` list.

For edited candidates, generate source/before/after triptychs when a full-panel overlay is too dense to judge:

```bash
python3 <skill-dir>/scripts/refine_km.py compare-scan parent_result.json result.json \
  --window-width 140 --overlap 48 --output-dir comparison
```

Read [references/worked-example.md](references/worked-example.md) when handling similarly colored curves, annotation contamination, or failed tolerance-only retries.

For a narrower or wider pass, regenerate the scan without changing the data:

```bash
python3 <skill-dir>/scripts/refine_km.py scan result.json \
  --window-width 140 --overlap 48 --output-dir scan
```

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

- For grayscale or similarly colored curves, compare a low-tolerance extraction against a source-only board before acceptance. Follow each curve through crossings; reject any trace that switches to its neighbor, even if the overall trend and landmark values look plausible.
- Treat `source_gap_review` as an unsupported forward-filled interval, not as a real plateau. Inspect the localized source crop and either confirm visible continuity or replace the segment with model-authored points.
- Preserve KM curves as right-continuous steps; do not smooth them into continuous trajectories.
- Reject any overlay that visually connects KM plateaus with diagonal interpolation; inspect or edit the underlying segment and render it as `steps-post`.
- Treat every number-at-risk correction as a visible transcription claim. Prefer `null` to a guessed count.
- Do not infer hazard ratios, medians, patient-level events, or treatment effects unless they are independently visible or supplied.
- Keep credentials out of semantic JSON, result files, and review bundles.

## Environment

The scripts require Python 3.9+ and the packages listed in `scripts/requirements.txt`. If imports fail, explain the missing packages and ask before installing anything.
