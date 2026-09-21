# KM Curve Digitizer Skill

This repository contains the installable Codex skill in [`km-curve-digitizer/`](km-curve-digitizer/).

The skill digitizes Kaplan-Meier figure images into structured time-survival data and produces visual review artifacts. It intentionally does not reconstruct individual patient data or fit survival models.

## Skill layout

```text
km-curve-digitizer/
├── SKILL.md
├── agents/openai.yaml
├── references/semantic-schema.md
└── scripts/
    ├── extract_km.py
    ├── build_manifest.py
    ├── run_batch.py
    ├── requirements.txt
    └── pykmextract/          # internal implementation, not a public package
```

The repository-level `tests/`, `images/`, and `runs/` directories are development fixtures and historical review outputs. They are not required when installing the skill folder.

## Development checks

```bash
python3 -m unittest discover -s tests -t . -v
python3 /path/to/skill-creator/scripts/quick_validate.py km-curve-digitizer
```

See [`km-curve-digitizer/SKILL.md`](km-curve-digitizer/SKILL.md) for the agent-facing workflow.
