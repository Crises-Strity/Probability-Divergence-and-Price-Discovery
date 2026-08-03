"""
Run the frozen P1 paper-output rebuild sequence.

The default sequence reruns Track A diagnostics, the P2 reference-basis audit,
and table provenance. Full Track B table reconstruction is opt-in.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()

TRACK_A_INPUTS = (
    "data/processed/panels/trackA_event_day_quality.parquet",
    "data/processed/panels/trackA_event_day_divergence.parquet",
    "data/processed/panels/daily_distribution_comparison.parquet",
    "data/processed/panels/trackA_event_day_divergence_smooth005.parquet",
    "data/processed/panels/trackA_event_day_divergence_smooth02.parquet",
    "data/processed/deribit/deribit_curve_fits.parquet",
    "data/processed/deribit/deribit_state_price_grid.parquet",
    "data/processed/polymarket/event_universe.parquet",
)

TRACK_B_INPUTS = (
    "data/processed/deribit/deribit_bar_quality_60.parquet",
    "data/processed/polymarket/event_cells.parquet",
    "data/processed/polymarket/polymarket_distribution_hourly.parquet",
)


class Command(NamedTuple):
    script: str
    args: tuple[str, ...] = ()


def command_plan(include_track_b: bool) -> list[Command]:
    commands = [
        Command("scripts/P1_pipeline/build_trackA_diagnostics.py"),
        Command("scripts/P1_pipeline/build_trackA_regression_diagnostics.py"),
        Command("scripts/P2_diagnostics/build_reference_basis_audit.py"),
    ]
    if include_track_b:
        commands.extend(
            [
                Command("scripts/P1_pipeline/build_trackB_kstar_panel.py"),
                Command("scripts/P1_pipeline/build_trackB_pm_survival_panel.py"),
                Command("scripts/P1_pipeline/build_trackB_deribit_survival_panel.py"),
                Command("scripts/P1_pipeline/build_trackB_lead_lag_panel.py"),
                Command("scripts/P1_pipeline/build_trackB_deribit_survival_panel.py", ("--bar-hours", "6")),
                Command("scripts/P1_pipeline/build_trackB_lead_lag_panel.py", ("--bar-hours", "6")),
                Command("scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py"),
            ]
        )
    commands.append(Command("scripts/P2_diagnostics/build_p1_table_provenance.py"))
    return commands


def python_executable() -> str:
    return sys.executable


def required_inputs(include_track_b: bool) -> tuple[str, ...]:
    if include_track_b:
        return TRACK_A_INPUTS + TRACK_B_INPUTS
    return TRACK_A_INPUTS


def validate_required_inputs(include_track_b: bool) -> None:
    missing = [
        relative
        for relative in required_inputs(include_track_b)
        if not (PROJECT_ROOT / relative).exists()
    ]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(f"Missing freeze-runner inputs:\n{formatted}")


def run_command(command: Command) -> None:
    argv = [python_executable(), command.script, *command.args]
    print("\n$", " ".join(argv), flush=True)
    subprocess.run(argv, cwd=PROJECT_ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run frozen P1 rebuild sequence.")
    parser.add_argument(
        "--include-track-b",
        action="store_true",
        help="Rebuild all Track B hourly/6h tables and diagnostics before provenance.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dry_run:
        validate_required_inputs(include_track_b=args.include_track_b)
    commands = command_plan(include_track_b=args.include_track_b)
    for command in commands:
        argv = [python_executable(), command.script, *command.args]
        if args.dry_run:
            print(" ".join(argv))
        else:
            run_command(command)


if __name__ == "__main__":
    main()
