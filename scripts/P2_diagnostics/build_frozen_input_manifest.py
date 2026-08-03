"""Build a deterministic manifest for the compact P2 freeze inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


FROZEN_INPUTS = (
    "data/processed/panels/trackA_event_day_quality.parquet",
    "data/processed/panels/trackA_event_day_divergence.parquet",
    "data/processed/panels/daily_distribution_comparison.parquet",
    "data/processed/panels/trackA_event_day_divergence_smooth005.parquet",
    "data/processed/panels/trackA_event_day_divergence_smooth02.parquet",
    "data/processed/deribit/deribit_curve_fits.parquet",
    "data/processed/deribit/deribit_state_price_grid.parquet",
    "data/processed/deribit/deribit_bar_quality_60.parquet",
    "data/processed/polymarket/event_universe.parquet",
    "data/processed/polymarket/event_cells.parquet",
    "data/processed/polymarket/polymarket_distribution_hourly.parquet",
)


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


def file_record(path: Path) -> dict[str, Any]:
    frame = pd.read_parquet(path)
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
        "rows": len(frame),
        "columns": list(frame.columns),
    }


def build_manifest(project_root: Path) -> dict[str, Any]:
    missing = [relative for relative in FROZEN_INPUTS if not (project_root / relative).exists()]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing frozen inputs:\n{formatted}")

    files = []
    for relative in FROZEN_INPUTS:
        record = {"path": relative, **file_record(project_root / relative)}
        files.append(record)
    return {"file_count": len(files), "files": files}


def main() -> None:
    project_root = find_project_root()
    output_path = project_root / "data" / "processed" / "frozen_input_manifest.json"
    manifest = build_manifest(project_root)
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"frozen inputs documented: {manifest['file_count']}")
    print(f"- {output_path}")


if __name__ == "__main__":
    main()
