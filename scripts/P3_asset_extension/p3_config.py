"""Load and freeze the thin P3 overlay on the frozen P1 Track A settings."""

from __future__ import annotations

import argparse
import copy
import importlib.metadata
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "p3_track_a_extension.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "p3_sol" / "p3_sol_run_config.json"

REQUIRED_INHERITED = {
    "resolution": "1D",
    "smooth_weight": 0.10,
    "minimum_fresh_strikes": 8,
    "maximum_stale_bar_share": 0.30,
    "state_grid_lower_multiplier": 0.5,
    "state_grid_upper_multiplier": 1.5,
    "open_tail_midpoint_widths": 0.5,
}


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_config(config: Mapping[str, Any]) -> None:
    inherited = config.get("inherited_track_a_parameters", {})
    for key, expected in REQUIRED_INHERITED.items():
        if inherited.get(key) != expected:
            raise ValueError(f"Frozen P1 carryover {key} must equal {expected!r}.")

    overrides = config.get("p3_feasibility_overrides", {})
    if overrides.get("primary_candidate") != "SOL":
        raise ValueError("The primary P3 candidate must be SOL.")
    if overrides.get("backup_candidate") != "XRP":
        raise ValueError("XRP is the only permitted backup candidate.")

    tolerance = config.get("contract_fit_tolerance", {})
    if tolerance.get("status") == "active" and tolerance.get("unit") == "coin":
        raise ValueError("SOL cannot activate a coin-denominated RMSE tolerance.")
    if tolerance.get("status") == "deferred":
        if tolerance.get("unit") is not None or tolerance.get("value") is not None:
            raise ValueError("Deferred contract tolerance must not contain a unit or value.")

    probe = overrides.get("small_probe_limits", {})
    if probe.get("download_full_price_histories") is not False:
        raise ValueError("The preparation probe must not download full price histories.")
    if probe.get("estimate_risk_neutral_distribution") is not False:
        raise ValueError("The preparation probe must not estimate a risk-neutral distribution.")


def git_commit(project_root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root,
        text=True,
    ).strip()


def software_versions() -> dict[str, str]:
    packages = ("requests", "pandas", "pyarrow", "pytest")
    return {
        "python": sys.version.split()[0],
        **{package: importlib.metadata.version(package) for package in packages},
    }


def build_run_snapshot(
    config: Mapping[str, Any],
    project_root: Path,
    snapshot_utc: str,
) -> dict[str, Any]:
    validate_config(config)
    snapshot = copy.deepcopy(dict(config))
    snapshot.update(
        {
            "git_commit": git_commit(project_root),
            "data_snapshot_utc": snapshot_utc,
            "software_versions": software_versions(),
            "deterministic": True,
        }
    )
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze the P3 feasibility run configuration.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--snapshot-utc", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    snapshot = build_run_snapshot(config, PROJECT_ROOT, args.snapshot_utc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    inherited = snapshot["inherited_track_a_parameters"]
    print(f"P3 primary candidate: {snapshot['p3_feasibility_overrides']['primary_candidate']}")
    print(f"resolution: {inherited['resolution']}")
    print(f"smooth_weight: {inherited['smooth_weight']}")
    print(f"minimum_fresh_strikes: {inherited['minimum_fresh_strikes']}")
    print(f"maximum_stale_bar_share: {inherited['maximum_stale_bar_share']}")
    print(f"- {args.output}")


if __name__ == "__main__":
    main()
