# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, adapted for a research codebase.

## [Unreleased]

### Removed

- Removed the PyHEOR bridge and IPD reconstruction APIs. PyKMExtract now focuses on curve digitization, validation, and review artifacts.

### Changed

- README files were rewritten into GitHub-style project homepages in English, Chinese, and French.
- Review bundles now export `validation_issues.csv` and compare the source panel directly with the digitization overlay.

## [0.1.0] - 2026-03-08

### Added

- End-to-end KM extraction pipeline with semantic parsing, axis detection, pixel extraction, coordinate mapping, and validation.
- OpenAI-compatible vision provider support.
- Optional AI axis refinement via four-point anchor review.
- Optional bounded post-extraction micro-tuning tools.
- Review bundle export with overlay, markdown review, digitized CSV, and optional reconstructed KM outputs.
- Batch workflow for grouped real-study figures.
- PyHEOR bridge for Guyot reconstruction and downstream survival workflows.
- Real-figure benchmark runs for `study01` to `study05`.

### Changed

- Image decoding is reused within a single pipeline run instead of reopening the same image repeatedly.
- CLI and batch execution now share a common runtime helper layer.
- Review bundle generation now supports both full and lightweight modes.
- Validation dataframe export now lives directly on `ExtractionResult`.
- The axis refinement subsystem was split into orchestration, prompts, payload handling, and board rendering modules.
- PyHEOR import fallback is now cached.

### Known Limitations

- Grayscale and near-color curves remain difficult.
- Heavy confidence ribbons and dense censoring marks are still weak cases.
- Reconstructed KM tail display may be shortened by the current downstream PyHEOR plotting path.
