# PyKMExtract

**English** | [中文](README_zh.md) | [Français](README_fr.md)

PyKMExtract is a research-oriented Kaplan-Meier digitization toolkit. It extracts structured `time / survival` curves from published KM figures, validates the result, and bridges the output into [PyHEOR](src/pykmextract/bridge/pyheor.py) for Guyot reconstruction and downstream survival modeling.

## Overview

PyKMExtract is built around one conservative idea:

`simple default extraction pipeline + optional AI enhancement modules`

The default path stays deterministic and inspectable. AI is allowed, but only as an explicit refinement layer, not as the core measurement engine.

Current default pipeline:

`semantic -> axis detection -> color extraction -> KM step sampling -> coordinate mapping -> validation`

## Status

This repository is currently a practical MVP, not a fully general KM digitizer.

What already works well:

- structured semantic input from JSON or a vision model
- automatic left/bottom axis detection on common white-background KM figures
- color-based curve extraction for 1-2 high-contrast curves
- KM-style step-preserving sampling instead of naive linear interpolation
- validation, scoring, and review bundle export
- PyHEOR bridge for Guyot reconstruction and KM redraw

What is still intentionally conservative:

- grayscale or near-color curves
- dense multi-curve figures
- heavy confidence ribbons and dense censoring marks
- low-resolution scans and compressed screenshots
- full PDF page splitting and GUI-style manual correction

## Features

- Structured semantic extraction from `semantic.json` or an OpenAI-compatible vision endpoint
- Axis bounds and optional four-point axis-anchor refinement
- KM-specific step sampling
- Validation signals for monotonicity, range, coverage, `at-risk`, and overlap ambiguity
- Human review bundle with `overlay.png`, `review.md`, digitized CSV, and optional IPD redraw
- Batch workflow for grouped studies such as `study01_full.png`, `study01_pfs.png`, `study01_os.png`

## Installation

Editable install:

```bash
pip install -e .
```

Or run directly from source:

```bash
PYTHONPATH=src python3 -m pykmextract.cli ...
```

## Quick Start

### 1. Single figure with prepared semantic JSON

```bash
PYTHONPATH=src python3 -m pykmextract.cli figure.png \
  --semantic-json semantic.json \
  --output-json extraction.json \
  --overlay overlay.png
```

### 2. Single figure with an OpenAI-compatible vision endpoint

```bash
export OPENROUTER_API_KEY="..."
PYTHONPATH=src python3 -m pykmextract.cli figure.png \
  --provider openai-compatible \
  --base-url https://openrouter.ai/api/v1 \
  --model openai/gpt-5.4 \
  --api-key-env OPENROUTER_API_KEY \
  --output-json extraction.json \
  --overlay overlay.png
```

### 3. Enable optional AI axis refinement

```bash
export OPENROUTER_API_KEY="..."
PYTHONPATH=src python3 -m pykmextract.cli figure.png \
  --provider openai-compatible \
  --base-url https://openrouter.ai/api/v1 \
  --model openai/gpt-5.4 \
  --api-key-env OPENROUTER_API_KEY \
  --axis-refine \
  --axis-review-image axis_review.png \
  --output-json extraction.json \
  --overlay overlay.png
```

### 4. Python usage

```python
import pykmextract as pkm

result = pkm.extract("figure.png", semantic=semantic_payload)
curve_df = result.curve_frame()
validation_df = result.validation_frame()

result.save_review_bundle("runs/example")
ipd = result.to_pyheor_ipd()
```

## Batch Workflow

Grouped figures should use a predictable naming pattern:

- `study01_full.png`
- `study01_pfs.png`
- `study01_os.png`

Build a manifest:

```bash
PYTHONPATH=src python3 -m pykmextract.batch \
  --image-dir images \
  --literature-md images/literatures.md \
  --output-json images/manifest.json
```

Run grouped extraction:

```bash
export OPENROUTER_API_KEY="..."
PYTHONPATH=src python3 -m pykmextract.batch_run \
  --image-dir images \
  --literature-md images/literatures.md \
  --base-url https://openrouter.ai/api/v1 \
  --model openai/gpt-5.4 \
  --api-key-env OPENROUTER_API_KEY \
  --axis-refine \
  --output-dir runs/openrouter-batch
```

Batch output is organized per study and per endpoint:

- `runs/study01/os/`
- `runs/study01/pfs/`
- `runs/study02/os/`
- `runs/study02/pfs/`

## Outputs

Main structured fields:

- `semantic`
- `axis_bounds`
- `axis_anchors`
- `curves[].time`
- `curves[].survival`
- `validation.score`
- `validation.level`
- `validation.issues`

Review bundle outputs:

- `original.png`
- `overlay.png`
- `digitized_curves.csv`
- `review.md`
- `reconstructed_km.png` when IPD reconstruction succeeds
- `ipd_<curve>.csv` when IPD reconstruction succeeds

## Current Real-Figure Results

Latest batch summary:

- [`runs/summary.json`](runs/summary.json)

All 10 panel overlays:

![all overlays](runs/all_overlays_contact_sheet.png)

Manual visual assessment of the current batch:

| Panel | Score / Level | Assessment | Main concern |
| --- | --- | --- | --- |
| `study01 / os` | `80 / high` | good | tail diverges from `at-risk` |
| `study01 / pfs` | `85 / high` | usable but weaker in the middle and tail | `Sorafenib` coverage is thin in the back half |
| `study02 / os` | `80 / high` | usable | both curves diverge from `at-risk` |
| `study02 / pfs` | `80 / high` | weak | `Placebo plus chemotherapy` remains too low in the middle and tail |
| `study03 / os` | `80 / high` | weak | coarse steps and weak `at-risk` agreement |
| `study03 / pfs` | `80 / high` | weak | late segments still look approximate |
| `study04 / os` | `100 / high` | best panel in the batch | strongest visual match |
| `study04 / pfs` | `100 / medium` | good but still needs review | long overlapping segment between curves |
| `study05 / os` | `80 / high` | good | visually strong; score limited by `at-risk` checks |
| `study05 / pfs` | `80 / high` | good | similar to `study05 / os` |

Most realistic takeaway:

- `study04 / os` is the best showcase panel
- `study05 / os` and `study05 / pfs` are visually better than their raw `80 / high`
- `study02 / pfs`, `study03 / os`, and `study03 / pfs` remain weak cases
- `study04 / pfs` is intentionally downgraded because of `overlap_ambiguity`

## Known Limitation: Reconstructed KM Tail

At the moment, `reconstructed_km.png` may visually lose the final flat tail segment even when the digitized curve and reconstructed IPD still contain late follow-up.

This is currently a downstream PyHEOR display limitation:

- reconstructed IPD still keeps late censoring times
- KM tables are currently reported only at event times
- the last horizontal plateau after the final event may therefore not be drawn

So if the redrawn KM tail looks shorter than the original figure, do not immediately assume digitization failed.

## Repository Layout

Key modules:

- [`src/pykmextract/pipeline.py`](src/pykmextract/pipeline.py): main extraction orchestrator
- [`src/pykmextract/runtime.py`](src/pykmextract/runtime.py): shared runtime helpers for CLI and batch
- [`src/pykmextract/extractor/semantic.py`](src/pykmextract/extractor/semantic.py): semantic parsing and normalization
- [`src/pykmextract/extractor/coord.py`](src/pykmextract/extractor/coord.py): axis detection and pixel-to-data mapping
- [`src/pykmextract/extractor/pixel.py`](src/pykmextract/extractor/pixel.py): color extraction and KM step sampling
- [`src/pykmextract/extractor/validator.py`](src/pykmextract/extractor/validator.py): validation and confidence scoring
- [`src/pykmextract/extractor/axis_refiner.py`](src/pykmextract/extractor/axis_refiner.py): AI axis-refinement orchestration
- [`src/pykmextract/extractor/_axis_refiner_prompts.py`](src/pykmextract/extractor/_axis_refiner_prompts.py): axis-refinement prompts
- [`src/pykmextract/extractor/_axis_refiner_payloads.py`](src/pykmextract/extractor/_axis_refiner_payloads.py): candidate generation and payload normalization
- [`src/pykmextract/extractor/_axis_refiner_board.py`](src/pykmextract/extractor/_axis_refiner_board.py): axis review boards
- [`src/pykmextract/enhancements.py`](src/pykmextract/enhancements.py): optional AI enhancement orchestration
- [`src/pykmextract/microtune.py`](src/pykmextract/microtune.py): bounded post-extraction micro-tuning tools
- [`src/pykmextract/review.py`](src/pykmextract/review.py): overlay export and review bundle generation
- [`src/pykmextract/bridge/pyheor.py`](src/pykmextract/bridge/pyheor.py): PyHEOR bridge

## Development

Run the full test suite:

```bash
python3 -m unittest discover -s tests -v
```

Current tests cover:

- synthetic end-to-end extraction
- CLI smoke paths
- axis refinement prompts and candidate logic
- pixel sampling behavior
- review bundle export
- provider response parsing
- PyHEOR bridge smoke path

Project files:

- [LICENSE](LICENSE)
- [Contributing Guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Design Principles

- keep the default extraction path simple
- keep AI enhancement optional and explicit
- prefer understandable heuristics over stacked special cases
- keep difficult figures visible as failure cases instead of hiding them
