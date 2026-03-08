# Contributing

Thanks for contributing to PyKMExtract.

## Scope

This project is intentionally conservative. Please prefer:

- small, reviewable changes
- explicit heuristics over opaque complexity
- failure visibility over silent overfitting
- opt-in AI enhancement over implicit behavior changes

## Local Setup

Install in editable mode:

```bash
pip install -e .
```

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

If you are working from source without installation:

```bash
PYTHONPATH=src python3 -m pykmextract.cli ...
```

## Project Conventions

- Keep the default extraction path simple and deterministic.
- Add AI behavior only as an explicit enhancement path.
- Preserve KM curves as step functions; do not smooth them into continuous curves.
- Prefer relative links in documentation so the repository renders correctly on GitHub.
- Keep difficult figures visible as manual-review or failure cases instead of forcing the default pipeline to fit them.

## Code Style

- Python 3.9+
- Prefer small functions with clear boundaries.
- Avoid adding duplicate public APIs when an existing result object already exposes the capability.
- Add tests for every behavioral change.
- Avoid broad architectural rewrites unless they clearly reduce complexity.

## Real Figure Data

If you contribute new real KM examples, use predictable grouped filenames:

- `studyXX_full.png`
- `studyXX_pfs.png`
- `studyXX_os.png`

Recommended supporting files:

- `images/literatures.md`
- `data/real_km/notes/`
- `data/real_km/semantic_seed/`

## Pull Requests

A good PR should include:

- what changed
- why it changed
- what risks remain
- which tests were run

If the change affects extraction quality, include at least one before/after example or point to the relevant files under `runs/`.
