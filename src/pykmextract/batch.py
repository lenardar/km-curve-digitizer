"""Batch utilities for grouped real-world KM study images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .datasets import build_real_km_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a grouped KM image manifest")
    parser.add_argument(
        "--image-dir",
        default="images",
        help="Directory containing files like study01_full.png and study01_pfs.png",
    )
    parser.add_argument(
        "--literature-md",
        default="images/literatures.md",
        help="Optional markdown file with study metadata",
    )
    parser.add_argument(
        "--output-json",
        default="images/manifest.json",
        help="Path to write the generated manifest JSON",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    manifest = build_real_km_manifest(
        args.image_dir,
        literature_md=args.literature_md,
    )
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
