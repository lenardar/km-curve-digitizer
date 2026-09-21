"""Dataset helpers for grouped real-world KM figures."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}


def discover_real_km_studies(image_dir: str | Path) -> List[Dict[str, object]]:
    """Discover study groups from filenames like study01_full.png."""
    root = Path(image_dir)
    groups: Dict[str, Dict[str, object]] = {}

    for path in sorted(root.iterdir() if root.exists() else []):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        stem = path.stem
        if "_" not in stem:
            continue

        study_id, panel_name = stem.rsplit("_", 1)
        entry = groups.setdefault(
            study_id,
            {
                "study_id": study_id,
                "full": None,
                "panels": {},
                "all_images": [],
            },
        )
        entry["all_images"].append(str(path))
        if panel_name == "full":
            entry["full"] = str(path)
        else:
            entry["panels"][panel_name] = str(path)

    return [groups[key] for key in sorted(groups)]


def parse_literature_notes(markdown_path: str | Path) -> Dict[str, str]:
    """Parse `# study01` style literature notes markdown."""
    path = Path(markdown_path)
    if not path.exists():
        return {}

    current_key: Optional[str] = None
    notes: Dict[str, List[str]] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^#\s+(\S+)$", line)
        if match:
            current_key = match.group(1)
            notes.setdefault(current_key, [])
            continue
        if current_key:
            notes[current_key].append(line)

    return {key: " ".join(lines).strip() for key, lines in notes.items()}


def build_real_km_manifest(
    image_dir: str | Path,
    *,
    literature_md: str | Path | None = None,
) -> Dict[str, object]:
    """Build a manifest and extraction plan for grouped study images."""
    studies = discover_real_km_studies(image_dir)
    notes = parse_literature_notes(literature_md) if literature_md else {}

    manifest_studies: List[Dict[str, object]] = []
    plan: List[Dict[str, object]] = []

    for study in studies:
        study_id = str(study["study_id"])
        full_image = study.get("full")
        panels = dict(study.get("panels", {}))
        endpoints = sorted(panels.keys())
        status = "ready" if endpoints else "incomplete"
        warnings: List[str] = []

        if not full_image:
            warnings.append("missing_full_image")
        if not endpoints:
            warnings.append("missing_endpoint_panels")

        manifest_entry = {
            "study_id": study_id,
            "citation": notes.get(study_id),
            "full": full_image,
            "panels": panels,
            "endpoints": endpoints,
            "warnings": warnings,
            "status": status,
        }
        manifest_studies.append(manifest_entry)

        for endpoint, image_path in panels.items():
            plan.append(
                {
                    "study_id": study_id,
                    "endpoint": endpoint,
                    "image": image_path,
                    "semantic_context_image": full_image or image_path,
                    "inherit_legend_from_full": bool(full_image),
                    "citation": notes.get(study_id),
                }
            )

    summary = {
        "n_studies": len(manifest_studies),
        "n_ready": sum(1 for item in manifest_studies if item["status"] == "ready"),
        "n_with_full": sum(1 for item in manifest_studies if item["full"]),
        "n_panel_jobs": len(plan),
    }
    return {"summary": summary, "studies": manifest_studies, "plan": plan}
