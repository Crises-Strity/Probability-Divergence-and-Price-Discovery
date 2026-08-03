"""
Build Track B joined hourly survival panel for lead-lag diagnostics.

This script does not run lead-lag regressions. It joins the primary
bucket-distribution Polymarket and Deribit local-survival panels, recomputes
within-event changes on the joined time grid, and reports the joint informative
coverage needed before any price-discovery test.

Inputs:
- data/processed/panels/pm_survival_hourly.parquet
- data/processed/panels/deribit_survival_hourly.parquet
- data/processed/panels/deribit_survival_<Nh>.parquet for coarser bars

Outputs:
- data/processed/panels/lead_lag_survival_panel.{csv,parquet}
- data/processed/panels/lead_lag_survival_panel_<Nh>.{csv,parquet}
- data/processed/panels/trackB_joint_informative_event_panel.{csv,parquet}
- data/processed/panels/trackB_lead_lag_panel_metadata.json
- paper/tables/tab_trackB_joint_survival_coverage.{csv,tex}
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path("/private/tmp") / "matplotlib-codex"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path("/private/tmp") / "codex-cache"))

import pandas as pd


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
PANELS_DIR = PROJECT_ROOT / "data" / "processed" / "panels"
TABLES_DIR = PROJECT_ROOT / "paper" / "tables"

PM_SURVIVAL = PANELS_DIR / "pm_survival_hourly.parquet"
DERIBIT_SURVIVAL = PANELS_DIR / "deribit_survival_hourly.parquet"


def output_suffix(bar_hours: int) -> str:
    return "" if bar_hours == 1 else f"_{bar_hours}h"


def output_stem(base: str, bar_hours: int) -> str:
    return f"{base}{output_suffix(bar_hours)}"


def deribit_survival_path(bar_hours: int) -> Path:
    if bar_hours == 1:
        return DERIBIT_SURVIVAL
    return PANELS_DIR / f"deribit_survival_{bar_hours}h.parquet"


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def write_table(df: pd.DataFrame, stem: str, caption: str, label: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES_DIR / f"{stem}.csv", index=False, encoding="utf-8-sig")
    tex = df.to_latex(index=False, escape=True, caption=caption, label=label, float_format="%.4f")
    (TABLES_DIR / f"{stem}.tex").write_text(tex, encoding="utf-8")


def write_paper_tables(summary: pd.DataFrame, bar_hours: int) -> None:
    coverage_stem = output_stem("tab_trackB_joint_survival_coverage", bar_hours)
    write_table(
        summary,
        coverage_stem,
        f"Track B joined PM-Deribit survival coverage ({bar_hours}h bars).",
        f"tab:trackB_joint_survival_coverage{output_suffix(bar_hours)}",
    )


def aggregate_pm_to_blocks(pm: pd.DataFrame, bar_hours: int) -> pd.DataFrame:
    if bar_hours == 1 or pm.empty:
        return pm
    work = pm.copy()
    work["source_hour_timestamp"] = pd.to_datetime(work["timestamp"], utc=True)
    work["timestamp"] = work["source_hour_timestamp"].dt.floor(f"{bar_hours}h")
    work = work.sort_values(["event_id", "timestamp", "source_hour_timestamp"]).copy()
    last = work.groupby(["event_id", "timestamp"], as_index=False).tail(1).copy()
    grouped = work.groupby(["event_id", "timestamp"], as_index=False).agg(
        pm_has_real_update=("pm_has_real_update", lambda values: bool(values.astype("boolean").fillna(False).any())),
        pm_update_count_in_bar=("pm_update_count_in_bar", "sum"),
        pm_block_source_hours=("source_hour_timestamp", "nunique"),
        pm_block_first_hour=("source_hour_timestamp", "min"),
        pm_block_last_hour=("source_hour_timestamp", "max"),
    )
    last = last.drop(columns=["pm_has_real_update", "pm_update_count_in_bar"], errors="ignore")
    out = last.merge(grouped, on=["event_id", "timestamp"], how="left")
    saturated = out["pm_survival"].le(0.05) | out["pm_survival"].ge(0.95)
    out["pm_survival_saturated"] = saturated.where(out["pm_survival"].notna(), pd.NA)
    out["pm_survival_low_power_flag"] = out["pm_survival_saturated"]
    out["trackB_pm_informative_candidate"] = (
        out["pm_survival_quality_status"].eq("pass")
        & out["pm_has_real_update"].fillna(False)
        & out["pm_survival_saturated"].eq(False)
    )
    return out.sort_values(["event_id", "timestamp"]).reset_index(drop=True)


def build_joined_panel(pm: pd.DataFrame, deribit: pd.DataFrame, bar_hours: int) -> pd.DataFrame:
    pm = aggregate_pm_to_blocks(pm, bar_hours)
    pm_primary = pm[
        pm["event_type_for_trackB"].eq("bucket_distribution")
        & pm["K_star_source"].eq("rule_selected")
    ].copy()
    deribit_primary = deribit[
        deribit["event_type_for_trackB"].eq("bucket_distribution")
        & deribit["K_star_source"].eq("rule_selected")
        & deribit["timestamp"].notna()
    ].copy()

    pm_primary["timestamp"] = pd.to_datetime(pm_primary["timestamp"], utc=True)
    deribit_primary["timestamp"] = pd.to_datetime(deribit_primary["timestamp"], utc=True)

    pm_cols = [
        "event_id",
        "timestamp",
        "pm_observed_timestamp",
        "asset",
        "event_type_for_trackB",
        "K_star",
        "K_star_source",
        "selection_reason",
        "pm_survival",
        "pm_survival_raw",
        "pm_survival_quality_status",
        "pm_survival_saturated",
        "trackB_pm_informative_candidate",
        "pm_has_real_update",
        "pm_update_count_in_bar",
        "pm_time_since_last_update_minutes",
        "initial_pm_survival",
    ]
    deribit_cols = [
        "event_id",
        "timestamp",
        "deribit_survival",
        "deribit_survival_raw",
        "deribit_survival_status",
        "failure_reason",
        "deribit_survival_clipped",
        "trackB_deribit_informative_candidate",
        "deribit_has_real_trade",
        "deribit_local_bracket_ok",
        "parity_implied_spot",
        "kstar_moneyness",
        "lower_call_strike",
        "upper_call_strike",
        "call_bracket_width",
        "n_parity_pairs",
        "n_fresh_call_strikes",
        "n_fresh_put_strikes",
        "deribit_total_volume",
        "timestamp_alignment",
    ]
    joined = pm_primary[pm_cols].merge(
        deribit_primary[deribit_cols],
        on=["event_id", "timestamp"],
        how="inner",
        validate="one_to_one",
    )
    joined = joined.sort_values(["event_id", "timestamp"]).reset_index(drop=True)
    joined["survival_divergence_pm_minus_deribit"] = joined["pm_survival"] - joined["deribit_survival"]
    joined["both_sides_informative_candidate"] = (
        joined["trackB_pm_informative_candidate"].fillna(False)
        & joined["trackB_deribit_informative_candidate"].fillna(False)
    )
    joined["both_sides_real_update"] = (
        joined["pm_has_real_update"].fillna(False)
        & joined["deribit_has_real_trade"].fillna(False)
    )
    joined["pm_change_joined_grid"] = joined.groupby("event_id")["pm_survival"].diff()
    joined["deribit_change_joined_grid"] = joined.groupby("event_id")["deribit_survival"].diff()
    joined["divergence_change_joined_grid"] = joined.groupby("event_id")[
        "survival_divergence_pm_minus_deribit"
    ].diff()
    return joined


def event_coverage(joined: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_panel = (
        joined.groupby(["event_type_for_trackB", "event_id"], as_index=False)
        .agg(
            joined_hours=("timestamp", "count"),
            pm_informative_hours=("trackB_pm_informative_candidate", lambda values: int(values.astype("boolean").fillna(False).sum())),
            deribit_informative_hours=("trackB_deribit_informative_candidate", lambda values: int(values.astype("boolean").fillna(False).sum())),
            joint_informative_hours=("both_sides_informative_candidate", lambda values: int(values.astype("boolean").fillna(False).sum())),
            joint_real_update_hours=("both_sides_real_update", lambda values: int(values.astype("boolean").fillna(False).sum())),
            median_pm_survival=("pm_survival", "median"),
            median_deribit_survival=("deribit_survival", "median"),
            median_abs_divergence=("survival_divergence_pm_minus_deribit", lambda values: float(values.abs().median())),
        )
    )
    rows = []
    for event_type, group in event_panel.groupby("event_type_for_trackB", dropna=False):
        rows.append(
            {
                "event_type_for_trackB": event_type,
                "events": int(len(group)),
                "total_joined_hours": int(group["joined_hours"].sum()),
                "total_pm_informative_hours": int(group["pm_informative_hours"].sum()),
                "total_deribit_informative_hours": int(group["deribit_informative_hours"].sum()),
                "total_joint_informative_hours": int(group["joint_informative_hours"].sum()),
                "median_joined_hours": float(group["joined_hours"].median()),
                "median_joint_informative_hours": float(group["joint_informative_hours"].median()),
                "events_ge_72_joint_informative_hours": int(group["joint_informative_hours"].ge(72).sum()),
                "events_ge_48_joint_informative_hours": int(group["joint_informative_hours"].ge(48).sum()),
                "events_zero_joint_informative_hours": int(group["joint_informative_hours"].eq(0).sum()),
                "median_abs_divergence": float(group["median_abs_divergence"].median()),
            }
        )
    return pd.DataFrame(rows), event_panel


def max_consecutive_run_hours(group: pd.DataFrame, bar_hours: int) -> int:
    good = group[group["both_sides_informative_candidate"]].sort_values("timestamp").copy()
    if good.empty:
        return 0
    timestamps = pd.to_datetime(good["timestamp"], utc=True).tolist()
    best = 1
    current = 1
    expected_delta = pd.Timedelta(hours=bar_hours)
    for previous, current_ts in zip(timestamps[:-1], timestamps[1:]):
        if current_ts - previous == expected_delta:
            current += 1
        else:
            best = max(best, current)
            current = 1
    best = max(best, current)
    return int(best * bar_hours)


def frequency_diagnostics(joined: pd.DataFrame, bar_hours: int) -> pd.DataFrame:
    rows = []
    work = joined.sort_values(["event_id", "timestamp"]).copy()
    work["deribit_change_lag1"] = work.groupby("event_id")["deribit_change_joined_grid"].shift(1)
    work["lag_gap_hours"] = (
        pd.to_datetime(work["timestamp"], utc=True)
        - pd.to_datetime(work.groupby("event_id")["timestamp"].shift(1), utc=True)
    ).dt.total_seconds() / 3600.0
    sample = work[
        work["both_sides_informative_candidate"]
        & work["pm_change_joined_grid"].notna()
        & work["deribit_change_joined_grid"].notna()
    ].copy()
    ac_sample = sample[sample["lag_gap_hours"].eq(float(bar_hours)) & sample["deribit_change_lag1"].notna()].copy()
    run_panel = work.groupby("event_id").apply(lambda group: max_consecutive_run_hours(group, bar_hours), include_groups=False)
    pm_std = float(sample["pm_change_joined_grid"].std(ddof=1)) if len(sample) >= 2 else math.nan
    deribit_std = float(sample["deribit_change_joined_grid"].std(ddof=1)) if len(sample) >= 2 else math.nan
    rows.append(
        {
            "bar_hours": int(bar_hours),
            "change_pair_rows": int(len(sample)),
            "corr_pm_deribit_changes": float(sample["pm_change_joined_grid"].corr(sample["deribit_change_joined_grid"])) if len(sample) >= 3 else math.nan,
            "pm_change_std": pm_std,
            "deribit_change_std": deribit_std,
            "deribit_pm_std_ratio": float(deribit_std / pm_std) if pm_std and math.isfinite(pm_std) and pm_std > 0 else math.nan,
            "deribit_change_lag1_autocorr": float(ac_sample["deribit_change_joined_grid"].corr(ac_sample["deribit_change_lag1"])) if len(ac_sample) >= 3 else math.nan,
            "median_max_consecutive_joint_informative_hours": float(run_panel.median()) if len(run_panel) else math.nan,
            "max_consecutive_joint_informative_hours": int(run_panel.max()) if len(run_panel) else 0,
            "events_ge_24h_consecutive_joint_informative": int(run_panel.ge(24).sum()) if len(run_panel) else 0,
            "events_ge_48h_consecutive_joint_informative": int(run_panel.ge(48).sum()) if len(run_panel) else 0,
        }
    )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bar-hours", type=int, default=1)
    args = parser.parse_args()
    if args.bar_hours < 1:
        raise ValueError("--bar-hours must be positive")

    pm = pd.read_parquet(PM_SURVIVAL)
    deribit_path = deribit_survival_path(args.bar_hours)
    deribit = pd.read_parquet(deribit_path)
    joined = build_joined_panel(pm, deribit, args.bar_hours)
    summary, event_panel = event_coverage(joined)
    diagnostics = frequency_diagnostics(joined, args.bar_hours)

    panel_stem = output_stem("lead_lag_survival_panel", args.bar_hours)
    event_stem = output_stem("trackB_joint_informative_event_panel", args.bar_hours)
    metadata_stem = output_stem("trackB_lead_lag_panel_metadata", args.bar_hours)
    coverage_table_stem = output_stem("tab_trackB_joint_survival_coverage", args.bar_hours)
    joined.to_csv(PANELS_DIR / f"{panel_stem}.csv", index=False, encoding="utf-8-sig")
    joined.to_parquet(PANELS_DIR / f"{panel_stem}.parquet", index=False)
    event_panel.to_csv(PANELS_DIR / f"{event_stem}.csv", index=False, encoding="utf-8-sig")
    event_panel.to_parquet(PANELS_DIR / f"{event_stem}.parquet", index=False)
    write_paper_tables(summary, args.bar_hours)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_trackB_lead_lag_panel.py",
        "git_commit": git_commit(),
        "inputs": {
            "pm_survival": str(PM_SURVIVAL.relative_to(PROJECT_ROOT)),
            "deribit_survival": str(deribit_path.relative_to(PROJECT_ROOT)),
        },
        "filter_rules": {
            "primary_sample": "bucket_distribution only; point_threshold excluded from primary Track B lead-lag panel",
            "bar_hours": args.bar_hours,
            "join": "inner join on event_id and floored hourly timestamp",
            "joint_informative": "PM informative candidate AND Deribit informative candidate",
            "timestamp_alignment": "both panels use floored hour-bucket labels; this does not eliminate within-hour non-synchronicity.",
        },
        "row_counts": {
            "rows": int(len(joined)),
            "events": int(joined["event_id"].nunique()) if not joined.empty else 0,
            "joint_informative_rows": int(joined["both_sides_informative_candidate"].sum()) if not joined.empty else 0,
            "joint_real_update_rows": int(joined["both_sides_real_update"].sum()) if not joined.empty else 0,
        },
        "summary": summary.to_dict(orient="records"),
        "frequency_diagnostics": diagnostics.to_dict(orient="records"),
        "known_caveats": [
            "The joined panel is not yet a regression sample; it is a coverage and alignment diagnostic.",
            "Within-hour non-synchronicity remains because Deribit 60-minute OHLC lacks exact last-trade timestamps.",
            "Lead-lag tests should use both_sides_informative_candidate or report full vs informative-sample differences explicitly.",
        ],
    }
    (PANELS_DIR / f"{metadata_stem}.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Track B joined lead-lag panel ===")
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value:,}")
    print("\nSummary:")
    print(summary.to_string(index=False) if not summary.empty else "empty")
    print("\nFrequency diagnostics:")
    print(diagnostics.to_string(index=False) if not diagnostics.empty else "empty")
    print("\nOutputs:")
    print(f"- {PANELS_DIR / f'{panel_stem}.parquet'}")
    print(f"- {PANELS_DIR / f'{event_stem}.parquet'}")
    print(f"- {PANELS_DIR / f'{metadata_stem}.json'}")
    print(f"- {TABLES_DIR / f'{coverage_table_stem}.tex'}")


if __name__ == "__main__":
    main()
