"""
Build source metadata for P1 paper tables.

This script records which script, input panel, and metadata file produced each
paper-facing table. It is documentation, not an estimator.

Outputs:
- paper/tables/table_source_metadata.json
- paper/tables/table_source_metadata.md
"""

from __future__ import annotations

import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
TABLES_DIR = PROJECT_ROOT / "paper" / "tables"


TRACKA_DIAGNOSTIC_INPUTS = [
    "data/processed/panels/trackA_event_day_quality.parquet",
    "data/processed/panels/trackA_event_day_divergence.parquet",
    "data/processed/panels/daily_distribution_comparison.parquet",
    "data/processed/deribit/deribit_curve_fits.parquet",
]

TRACKA_REGRESSION_INPUTS = [
    "data/processed/panels/trackA_event_day_divergence.parquet",
    "data/processed/panels/daily_distribution_comparison.parquet",
    "data/processed/deribit/deribit_state_price_grid.parquet",
    "data/processed/panels/trackA_event_day_divergence_smooth005.parquet",
    "data/processed/panels/trackA_event_day_divergence_smooth02.parquet",
]


SOURCE_GROUPS: list[dict[str, Any]] = [
    {
        "prefixes": [
            "tab_trackA_sample_funnel",
            "tab_trackA_divergence_overall",
            "tab_trackA_divergence_by_asset",
            "tab_trackA_divergence_by_gap",
            "tab_trackA_divergence_by_asset_gap",
            "tab_trackA_cell_divergence",
            "tab_trackA_curve_quality",
            "tab_trackA_gap_confound_diagnostics",
            "tab_trackA_moments_by_gap",
            "tab_trackA_moments_by_tte_gap",
            "tab_trackA_tail_relative_wedge",
        ],
        "script": "scripts/P1_pipeline/build_trackA_diagnostics.py",
        "inputs": TRACKA_DIAGNOSTIC_INPUTS,
        "metadata": "data/processed/panels/trackA_diagnostics_summary.json",
        "paper_use": "Track A sample funnel, distribution-distance diagnostics, curve quality, and moment summaries.",
        "sample_gate": "trackA_comparison_main_candidate for final comparison tables unless table name explicitly reports funnel or curve quality.",
    },
    {
        "prefixes": [
            "tab_trackA_spread_regressions",
            "tab_trackA_partial_spearman",
            "tab_trackA_tail_midpoint_robustness",
            "tab_trackA_state_grid_truncation",
            "tab_trackA_state_grid_truncation_top",
            "tab_trackA_smoothness_regression_robustness",
            "tab_trackA_smoothness_fit_quality",
            "tab_trackA_smoothness_moment_grid",
        ],
        "script": "scripts/P1_pipeline/build_trackA_regression_diagnostics.py",
        "inputs": TRACKA_REGRESSION_INPUTS,
        "metadata": "data/processed/panels/trackA_regression_diagnostics_summary.json",
        "paper_use": "Track A spread-wedge controls and robustness checks.",
        "sample_gate": "trackA_comparison_main_candidate, event-clustered inference for regressions.",
    },
    {
        "prefixes": ["tab_trackB_kstar_summary"],
        "script": "scripts/P1_pipeline/build_trackB_kstar_panel.py",
        "inputs": [
            "data/processed/polymarket/event_universe.parquet",
            "data/processed/polymarket/event_cells.parquet",
            "data/processed/polymarket/polymarket_distribution_hourly.parquet",
        ],
        "metadata": "data/processed/panels/trackB_kstar_metadata.json",
        "paper_use": "Track B K* selection diagnostics.",
        "sample_gate": "All Track B-eligible event types for diagnostics; primary Track B later restricts to bucket_distribution.",
    },
    {
        "prefixes": [
            "tab_trackB_pm_survival_summary",
            "tab_trackB_pm_informative_event_summary",
        ],
        "script": "scripts/P1_pipeline/build_trackB_pm_survival_panel.py",
        "inputs": [
            "data/processed/panels/trackB_kstar_panel.parquet",
            "data/processed/polymarket/polymarket_distribution_hourly.parquet",
        ],
        "metadata": "data/processed/panels/trackB_pm_survival_metadata.json",
        "paper_use": "Track B Polymarket survival and saturation diagnostics.",
        "sample_gate": "PM informative candidate = pass quality AND real update AND survival in (0.05, 0.95).",
    },
    {
        "prefixes": ["tab_trackB_deribit_survival_summary"],
        "script": "scripts/P1_pipeline/build_trackB_deribit_survival_panel.py",
        "inputs": [
            "data/processed/panels/trackB_kstar_panel.parquet",
            "data/processed/deribit/deribit_bar_quality_60.parquet",
        ],
        "metadata": "data/processed/panels/trackB_deribit_survival_metadata.json",
        "paper_use": "Track B hourly Deribit local-survival feasibility diagnostics.",
        "sample_gate": "bucket_distribution events only; local call-spread digital with survival in (0.05, 0.95) for informative rows.",
    },
    {
        "prefixes": ["tab_trackB_deribit_survival_summary_6h"],
        "script": "scripts/P1_pipeline/build_trackB_deribit_survival_panel.py --bar-hours 6",
        "inputs": [
            "data/processed/panels/trackB_kstar_panel.parquet",
            "data/processed/deribit/deribit_bar_quality_60.parquet",
        ],
        "metadata": "data/processed/panels/trackB_deribit_survival_metadata_6h.json",
        "paper_use": "Track B 6h Deribit local-survival feasibility diagnostics.",
        "sample_gate": "bucket_distribution events only; 6h local call-spread digital with survival in (0.05, 0.95) for informative rows.",
    },
    {
        "prefixes": ["tab_trackB_joint_survival_coverage"],
        "script": "scripts/P1_pipeline/build_trackB_lead_lag_panel.py",
        "inputs": [
            "data/processed/panels/pm_survival_hourly.parquet",
            "data/processed/panels/deribit_survival_hourly.parquet",
        ],
        "metadata": "data/processed/panels/trackB_lead_lag_panel_metadata.json",
        "paper_use": "Track B hourly joined PM-Deribit coverage diagnostics.",
        "sample_gate": "both_sides_informative_candidate after joining PM and Deribit on event_id and timestamp.",
    },
    {
        "prefixes": ["tab_trackB_joint_survival_coverage_6h"],
        "script": "scripts/P1_pipeline/build_trackB_lead_lag_panel.py --bar-hours 6",
        "inputs": [
            "data/processed/panels/pm_survival_hourly.parquet",
            "data/processed/panels/deribit_survival_6h.parquet",
        ],
        "metadata": "data/processed/panels/trackB_lead_lag_panel_metadata_6h.json",
        "paper_use": "Track B 6h joined PM-Deribit coverage diagnostics.",
        "sample_gate": "both_sides_informative_candidate after joining PM and Deribit on event_id and 6h timestamp.",
    },
    {
        "prefixes": [
            "tab_trackB_frequency_diagnostics_6h",
            "tab_trackB_cross_correlation_6h",
            "tab_trackB_pooled_lead_lag_6h",
        ],
        "script": "scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py",
        "inputs": ["data/processed/panels/lead_lag_survival_panel_6h.parquet"],
        "metadata": "data/processed/panels/trackB_lead_lag_diagnostics_summary.json",
        "paper_use": "Track B 6h frequency diagnostics, symmetric cross-correlations, and pooled lead-lag regressions.",
        "sample_gate": "both_sides_informative_candidate with non-null changes; directional coefficients require measurement-error caveat.",
    },
    {
        "prefixes": ["tab_reference_basis_audit_summary"],
        "script": "scripts/P2_diagnostics/build_reference_basis_audit.py",
        "inputs": ["data/processed/polymarket/event_universe.parquet"],
        "metadata": "data/processed/panels/reference_basis_audit_metadata.json",
        "paper_use": "P2 reference-basis audit for Polymarket rule text versus Deribit index references.",
        "sample_gate": "All canonical events; reference_basis_status is a textual/provenance audit status, not an empirical exclusion gate.",
    },
]


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unavailable_not_git_repo"


def match_source(stem: str) -> dict[str, Any]:
    for group in SOURCE_GROUPS:
        if any(stem == prefix for prefix in group["prefixes"]):
            return group
    candidates = []
    for group in SOURCE_GROUPS:
        for prefix in group["prefixes"]:
            if stem.startswith(f"{prefix}_"):
                candidates.append((len(prefix), group))
    if candidates:
        return sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]
    return {
        "script": "unknown",
        "inputs": [],
        "metadata": None,
        "paper_use": "unmapped table; add to scripts/P2_diagnostics/build_p1_table_provenance.py",
        "sample_gate": "unknown",
    }


def file_rows(path: Path) -> int | None:
    if not path.exists() or path.suffix != ".csv":
        return None
    with path.open("r", encoding="utf-8-sig") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def parse_script_command(command: str) -> tuple[str, list[str]]:
    parts = shlex.split(command)
    if not parts:
        raise ValueError("Script command cannot be empty.")
    return parts[0], parts[1:]


def build_entries() -> list[dict[str, Any]]:
    entries = []
    for csv_path in sorted(TABLES_DIR.glob("tab_*.csv")):
        stem = csv_path.stem
        source = match_source(stem)
        tex_path = csv_path.with_suffix(".tex")
        metadata_path = PROJECT_ROOT / source["metadata"] if source["metadata"] else None
        script_file, script_args = parse_script_command(source["script"])
        entries.append(
            {
                "table_stem": stem,
                "csv": str(csv_path.relative_to(PROJECT_ROOT)),
                "tex": str(tex_path.relative_to(PROJECT_ROOT)) if tex_path.exists() else None,
                "tex_file_exists": tex_path.exists(),
                "rows": file_rows(csv_path),
                "script": source["script"],
                "script_file": script_file,
                "script_args": script_args,
                "script_file_exists": (PROJECT_ROOT / script_file).exists(),
                "input_files": [
                    {"path": path, "exists": (PROJECT_ROOT / path).exists()}
                    for path in source["inputs"]
                ],
                "metadata_file": source["metadata"],
                "metadata_file_exists": bool(metadata_path and metadata_path.exists()),
                "paper_use": source["paper_use"],
                "sample_gate": source["sample_gate"],
            }
        )
    return entries


def write_markdown(entries: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    lines = [
        "# P1 Table Source Metadata",
        "",
        f"Generated at UTC: `{meta['generated_at_utc']}`",
        f"Git commit: `{meta['git_commit']}`",
        "",
        "Use this file to trace every paper-facing table back to the script and panel that produced it.",
        "",
        "| table | rows | script | script exists | inputs exist | metadata exists | TeX exists | paper use | sample gate |",
        "|---|---:|---|:---:|:---:|:---:|:---:|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| {table} | {rows} | `{script}` | {script_exists} | {inputs_exist} | {metadata_exists} | {tex_exists} | {paper_use} | {sample_gate} |".format(
                table=entry["table_stem"],
                rows=entry["rows"],
                script=entry["script"],
                script_exists=entry["script_file_exists"],
                inputs_exist=all(item["exists"] for item in entry["input_files"]),
                metadata_exists=entry["metadata_file_exists"],
                tex_exists=entry["tex_file_exists"],
                paper_use=entry["paper_use"],
                sample_gate=entry["sample_gate"],
            )
        )
    (TABLES_DIR / "table_source_metadata.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    entries = build_entries()
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "table_count": len(entries),
        "entries": entries,
    }
    (TABLES_DIR / "table_source_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_markdown(entries, metadata)
    print(f"tables documented: {len(entries)}")
    print(f"- {TABLES_DIR / 'table_source_metadata.json'}")
    print(f"- {TABLES_DIR / 'table_source_metadata.md'}")


if __name__ == "__main__":
    main()
