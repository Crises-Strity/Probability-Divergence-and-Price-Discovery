"""
Build Polymarket P1 quality diagnostics.

Inputs:
- data/processed/polymarket/event_universe.parquet
- data/processed/polymarket/event_cells.parquet
- data/processed/polymarket/polymarket_distribution_hourly.parquet
- data/processed/polymarket/polymarket_distribution_daily.parquet

Outputs:
- data/processed/polymarket/polymarket_quality_diagnostics.{csv,parquet}
- data/processed/polymarket/polymarket_quality_metadata.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "polymarket"

EVENT_UNIVERSE = PROCESSED_DIR / "event_universe.parquet"
EVENT_CELLS = PROCESSED_DIR / "event_cells.parquet"
HOURLY_PANEL = PROCESSED_DIR / "polymarket_distribution_hourly.parquet"
DAILY_PANEL = PROCESSED_DIR / "polymarket_distribution_daily.parquet"


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


def quantile_or_na(series: pd.Series, q: float) -> float:
    clean = series.dropna()
    if clean.empty:
        return float("nan")
    return float(clean.quantile(q))


def event_bar_panel(hourly: pd.DataFrame) -> pd.DataFrame:
    if hourly.empty:
        return pd.DataFrame()

    bars = hourly.groupby(["event_id", "timestamp"], as_index=False).agg(
        n_cells=("cell_id", "nunique"),
        event_probability_sum=("probability_raw", "sum"),
        sum_error=("sum_error", "first"),
        is_complete_partition=("is_complete_partition", "first"),
        is_warmup=("is_warmup", "first"),
        passes_sum_filter=("passes_sum_filter", "first"),
        update_count_in_bar=("has_real_update", "sum"),
        max_time_since_last_update_minutes=("time_since_last_update_minutes", "max"),
        median_time_since_last_update_minutes=("time_since_last_update_minutes", "median"),
    )
    bars["abs_sum_error"] = bars["event_probability_sum"].sub(1.0).abs()
    bars["has_any_real_update"] = bars["update_count_in_bar"] > 0
    return bars


def daily_sum_panel(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()

    return daily.groupby(["event_id", "date"], as_index=False).agg(
        daily_probability_sum=("probability_raw", "sum"),
        daily_abs_sum_error=("sum_error", lambda x: abs(float(x.iloc[0]))),
        daily_update_count=("has_real_update", "sum"),
        n_cells=("cell_id", "nunique"),
        selected_timestamp=("timestamp", "first"),
    )


def classify_quality(row: pd.Series) -> str:
    pass_share = row.get("nonwarm_complete_pass_sum_filter_share", 0.0)
    usable_days = row.get("usable_daily_days", 0)
    nonwarm_bars = row.get("nonwarm_complete_bars", 0)

    if pd.isna(pass_share):
        return "fail_no_hourly_panel"
    if nonwarm_bars < 24 or usable_days < 3:
        return "fail_low_coverage"
    if pass_share >= 0.90 and usable_days >= 5:
        return "pass_main"
    if pass_share >= 0.80 and usable_days >= 5:
        return "borderline_sum_quality"
    return "fail_sum_quality"


def build_quality_table(
    event_universe: pd.DataFrame,
    cells: pd.DataFrame,
    hourly: pd.DataFrame,
    daily: pd.DataFrame,
) -> pd.DataFrame:
    track_a_events = event_universe[event_universe["trackA_eligible"]].copy()
    bars = event_bar_panel(hourly)
    daily_sums = daily_sum_panel(daily)

    expected_cells = cells.groupby("event_id")["cell_id"].nunique().rename("expected_cells")
    quality = track_a_events.merge(expected_cells, left_on="event_id", right_index=True, how="left")

    if not bars.empty:
        all_summary = bars.groupby("event_id").agg(
            total_hourly_bars=("timestamp", "count"),
            warmup_bars=("is_warmup", "sum"),
            complete_bar_share=("is_complete_partition", "mean"),
            all_pass_sum_filter_share=("passes_sum_filter", "mean"),
            all_min_probability_sum=("event_probability_sum", "min"),
            all_max_probability_sum=("event_probability_sum", "max"),
        )

        warmup = bars[bars["is_warmup"]].groupby("event_id").agg(
            warmup_pass_sum_filter_share=("passes_sum_filter", "mean"),
            warmup_mean_probability_sum=("event_probability_sum", "mean"),
            warmup_max_probability_sum=("event_probability_sum", "max"),
        )

        nonwarm_complete = bars[~bars["is_warmup"] & bars["is_complete_partition"]].copy()
        nonwarm_summary = nonwarm_complete.groupby("event_id").agg(
            nonwarm_complete_bars=("timestamp", "count"),
            nonwarm_complete_pass_sum_filter_share=("passes_sum_filter", "mean"),
            nonwarm_min_probability_sum=("event_probability_sum", "min"),
            nonwarm_max_probability_sum=("event_probability_sum", "max"),
            nonwarm_mean_probability_sum=("event_probability_sum", "mean"),
            nonwarm_median_abs_sum_error=("abs_sum_error", "median"),
            real_update_bar_share=("has_any_real_update", "mean"),
            mean_update_count_in_bar=("update_count_in_bar", "mean"),
            median_time_since_last_update_minutes=("median_time_since_last_update_minutes", "median"),
            max_time_since_last_update_minutes=("max_time_since_last_update_minutes", "max"),
        )

        p95_abs = (
            nonwarm_complete.groupby("event_id")["abs_sum_error"]
            .apply(lambda x: quantile_or_na(x, 0.95))
            .rename("nonwarm_p95_abs_sum_error")
        )
        p95_stale = (
            nonwarm_complete.groupby("event_id")["max_time_since_last_update_minutes"]
            .apply(lambda x: quantile_or_na(x, 0.95))
            .rename("p95_max_time_since_last_update_minutes")
        )

        quality = quality.merge(all_summary, left_on="event_id", right_index=True, how="left")
        quality = quality.merge(warmup, left_on="event_id", right_index=True, how="left")
        quality = quality.merge(nonwarm_summary, left_on="event_id", right_index=True, how="left")
        quality = quality.merge(p95_abs, left_on="event_id", right_index=True, how="left")
        quality = quality.merge(p95_stale, left_on="event_id", right_index=True, how="left")

    if not daily_sums.empty:
        daily_summary = daily_sums.groupby("event_id").agg(
            usable_daily_days=("date", "nunique"),
            daily_min_probability_sum=("daily_probability_sum", "min"),
            daily_max_probability_sum=("daily_probability_sum", "max"),
            daily_mean_probability_sum=("daily_probability_sum", "mean"),
            daily_median_abs_sum_error=("daily_abs_sum_error", "median"),
        )
        quality = quality.merge(daily_summary, left_on="event_id", right_index=True, how="left")

    quality["warmup_mean_minus_nonwarm_mean_sum"] = (
        quality["warmup_mean_probability_sum"] - quality["nonwarm_mean_probability_sum"]
    )
    quality["pm_trackA_quality_flag"] = quality.apply(classify_quality, axis=1)
    quality["pm_trackA_main_candidate"] = quality["pm_trackA_quality_flag"] == "pass_main"

    ordered_cols = [
        "event_id",
        "event_title",
        "asset",
        "event_start_time",
        "event_end_time",
        "nearest_deribit_expiry",
        "mapping_quality",
        "expected_cells",
        "total_hourly_bars",
        "warmup_bars",
        "complete_bar_share",
        "all_pass_sum_filter_share",
        "warmup_pass_sum_filter_share",
        "warmup_mean_probability_sum",
        "warmup_max_probability_sum",
        "nonwarm_complete_bars",
        "nonwarm_complete_pass_sum_filter_share",
        "nonwarm_min_probability_sum",
        "nonwarm_max_probability_sum",
        "nonwarm_mean_probability_sum",
        "nonwarm_median_abs_sum_error",
        "nonwarm_p95_abs_sum_error",
        "warmup_mean_minus_nonwarm_mean_sum",
        "usable_daily_days",
        "daily_min_probability_sum",
        "daily_max_probability_sum",
        "daily_mean_probability_sum",
        "daily_median_abs_sum_error",
        "real_update_bar_share",
        "mean_update_count_in_bar",
        "median_time_since_last_update_minutes",
        "p95_max_time_since_last_update_minutes",
        "max_time_since_last_update_minutes",
        "pm_trackA_quality_flag",
        "pm_trackA_main_candidate",
    ]
    existing_cols = [col for col in ordered_cols if col in quality.columns]
    remaining_cols = [col for col in quality.columns if col not in existing_cols]
    return quality[existing_cols + remaining_cols].sort_values(["pm_trackA_quality_flag", "event_id"]).reset_index(drop=True)


def write_outputs(quality: pd.DataFrame, metadata: dict[str, Any]) -> None:
    csv_path = PROCESSED_DIR / "polymarket_quality_diagnostics.csv"
    parquet_path = PROCESSED_DIR / "polymarket_quality_diagnostics.parquet"
    metadata_path = PROCESSED_DIR / "polymarket_quality_metadata.json"

    quality.to_csv(csv_path, index=False, encoding="utf-8-sig")
    quality.to_parquet(parquet_path, index=False)
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-pass-threshold", type=float, default=0.90)
    args = parser.parse_args()

    if args.main_pass_threshold != 0.90:
        raise RuntimeError("Custom thresholds are not implemented yet; keep the P1 default 0.90.")

    event_universe = pd.read_parquet(EVENT_UNIVERSE)
    cells = pd.read_parquet(EVENT_CELLS)
    hourly = pd.read_parquet(HOURLY_PANEL)
    daily = pd.read_parquet(DAILY_PANEL)

    quality = build_quality_table(event_universe, cells, hourly, daily)
    flag_counts = quality["pm_trackA_quality_flag"].value_counts(dropna=False).to_dict()
    asset_flag_counts = (
        quality.groupby(["asset", "pm_trackA_quality_flag"]).size().rename("n_events").reset_index().to_dict("records")
    )

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_polymarket_quality_diagnostics.py",
        "git_commit": git_commit(),
        "inputs": {
            "event_universe": str(EVENT_UNIVERSE.relative_to(PROJECT_ROOT)),
            "event_cells": str(EVENT_CELLS.relative_to(PROJECT_ROOT)),
            "hourly_panel": str(HOURLY_PANEL.relative_to(PROJECT_ROOT)),
            "daily_panel": str(DAILY_PANEL.relative_to(PROJECT_ROOT)),
        },
        "quality_rules": {
            "sample": "Track A clean bucket-distribution events only",
            "main_candidate": "nonwarm complete bars >=24, usable daily days >=5, and sum-filter pass share >=0.90",
            "borderline_sum_quality": "nonwarm complete bars >=24, usable daily days >=5, and sum-filter pass share in [0.80, 0.90)",
            "sum_filter": "event_probability_sum in [0.9, 1.1]",
        },
        "row_counts": {
            "trackA_events": int(len(quality)),
            "main_candidates": int(quality["pm_trackA_main_candidate"].sum()),
        },
        "flag_counts": flag_counts,
        "asset_flag_counts": asset_flag_counts,
        "known_caveats": [
            "has_real_update is a sampled-price change proxy, not raw CLOB message activity.",
            "This diagnostic only gates Polymarket Track A distribution quality; Deribit coverage gates are separate.",
            "Low-quality events are not deleted here; downstream panels should join this table and filter explicitly.",
        ],
    }
    write_outputs(quality, metadata)

    print("\n=== Polymarket quality diagnostics ===")
    print(f"Track A events: {len(quality):,}")
    print(f"Main candidates: {int(quality['pm_trackA_main_candidate'].sum()):,}")
    print("\nQuality flags:")
    print(quality["pm_trackA_quality_flag"].value_counts(dropna=False).to_string())
    print("\nPass-share summary:")
    print(quality["nonwarm_complete_pass_sum_filter_share"].describe().to_string())
    print("\nLowest-quality events:")
    print(
        quality[
            [
                "event_id",
                "asset",
                "nonwarm_complete_pass_sum_filter_share",
                "usable_daily_days",
                "nonwarm_max_probability_sum",
                "pm_trackA_quality_flag",
            ]
        ]
        .sort_values(["nonwarm_complete_pass_sum_filter_share", "usable_daily_days"])
        .head(15)
        .to_string(index=False)
    )
    print("\nOutputs:")
    print(f"- {PROCESSED_DIR / 'polymarket_quality_diagnostics.parquet'}")
    print(f"- {PROCESSED_DIR / 'polymarket_quality_metadata.json'}")


if __name__ == "__main__":
    main()
