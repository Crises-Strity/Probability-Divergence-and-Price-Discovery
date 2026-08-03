"""
Build Track A daily quality gate panels.

This is the bridge between the Polymarket daily distribution panel and the
Deribit 1D option-grid quality panel. It does not estimate Deribit bucket
probabilities yet.

Outputs:
- data/processed/panels/trackA_event_day_quality.{csv,parquet}
- data/processed/panels/trackA_pm_cell_day_panel.{csv,parquet}
- data/processed/panels/trackA_daily_quality_metadata.json
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
POLY_DIR = PROJECT_ROOT / "data" / "processed" / "polymarket"
DERIBIT_DIR = PROJECT_ROOT / "data" / "processed" / "deribit"
PANELS_DIR = PROJECT_ROOT / "data" / "processed" / "panels"

EVENT_UNIVERSE = POLY_DIR / "event_universe.parquet"
PM_DAILY = POLY_DIR / "polymarket_distribution_daily.parquet"
PM_QUALITY = POLY_DIR / "polymarket_quality_diagnostics.parquet"
DERIBIT_QUALITY = DERIBIT_DIR / "deribit_bar_quality.parquet"


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


def build_pm_event_day(pm_daily: pd.DataFrame) -> pd.DataFrame:
    event_day = pm_daily.groupby(["event_id", "date"], as_index=False).agg(
        pm_snapshot_timestamp=("timestamp", "first"),
        pm_observed_timestamp_min=("observed_timestamp", "min"),
        pm_observed_timestamp_max=("observed_timestamp", "max"),
        pm_n_cells=("cell_id", "nunique"),
        pm_event_probability_sum=("probability_raw", "sum"),
        pm_normalized_probability_sum=("probability_normalized", "sum"),
        pm_update_count_in_bar=("has_real_update", "sum"),
        pm_max_time_since_last_update_minutes=("time_since_last_update_minutes", "max"),
        pm_median_time_since_last_update_minutes=("time_since_last_update_minutes", "median"),
    )
    event_day["pm_sum_error"] = event_day["pm_event_probability_sum"] - 1.0
    event_day["pm_abs_sum_error"] = event_day["pm_sum_error"].abs()
    event_day["pm_passes_sum_filter"] = event_day["pm_event_probability_sum"].between(0.9, 1.1)
    return event_day


def build_event_day_quality(
    event_universe: pd.DataFrame,
    pm_quality: pd.DataFrame,
    pm_daily: pd.DataFrame,
    deribit_quality: pd.DataFrame,
) -> pd.DataFrame:
    pm_event_day = build_pm_event_day(pm_daily)

    event_cols = [
        "event_id",
        "event_title",
        "asset",
        "event_start_time",
        "event_end_time",
        "nearest_deribit_expiry",
        "time_gap_hours",
        "abs_time_gap_hours",
        "calendar_gap_days",
        "mapping_quality",
        "settlement_reference",
        "settlement_reference_detail",
        "deribit_index_reference",
        "reference_basis_mismatch",
        "min_strike",
        "max_strike",
        "median_bucket_width",
    ]
    quality_cols = [
        "event_id",
        "pm_trackA_quality_flag",
        "pm_trackA_main_candidate",
        "nonwarm_complete_pass_sum_filter_share",
        "usable_daily_days",
    ]
    deribit_cols = [
        "event_id",
        "date",
        "timestamp",
        "n_rows",
        "n_traded_rows",
        "n_distinct_traded_strikes",
        "n_call_traded_strikes",
        "n_put_traded_strikes",
        "min_traded_strike",
        "max_traded_strike",
        "total_volume",
        "can_fit_full_curve_min6",
        "can_fit_full_curve_min8",
        "atm_local_coverage",
        "intraday_trade_time_diagnostics_available",
        "cross_strike_trade_time_spread_minutes",
        "stale_bar_share",
        "both_sides_real_update_candidate",
    ]

    panel = pm_event_day.merge(event_universe[event_cols], on="event_id", how="left")
    panel = panel.merge(pm_quality[quality_cols], on="event_id", how="left")
    panel = panel.merge(
        deribit_quality[deribit_cols].rename(
            columns={
                "timestamp": "deribit_bar_timestamp",
                "n_rows": "deribit_n_rows",
                "n_traded_rows": "deribit_n_traded_rows",
                "n_distinct_traded_strikes": "deribit_n_distinct_traded_strikes",
                "n_call_traded_strikes": "deribit_n_call_traded_strikes",
                "n_put_traded_strikes": "deribit_n_put_traded_strikes",
                "min_traded_strike": "deribit_min_traded_strike",
                "max_traded_strike": "deribit_max_traded_strike",
                "total_volume": "deribit_total_volume",
                "can_fit_full_curve_min6": "deribit_can_fit_full_curve_min6",
                "can_fit_full_curve_min8": "deribit_can_fit_full_curve_min8",
                "atm_local_coverage": "deribit_atm_local_coverage",
                "intraday_trade_time_diagnostics_available": "deribit_intraday_trade_time_diagnostics_available",
                "cross_strike_trade_time_spread_minutes": "deribit_cross_strike_trade_time_spread_minutes",
                "stale_bar_share": "deribit_stale_bar_share",
                "both_sides_real_update_candidate": "deribit_both_sides_real_update_candidate",
            }
        ),
        on=["event_id", "date"],
        how="left",
    )

    panel["has_deribit_daily_bar"] = panel["deribit_bar_timestamp"].notna()
    panel["deribit_daily_grid_ok_min6"] = panel["deribit_can_fit_full_curve_min6"].map(lambda value: bool(value) if pd.notna(value) else False)
    panel["deribit_daily_grid_ok_min8"] = panel["deribit_can_fit_full_curve_min8"].map(lambda value: bool(value) if pd.notna(value) else False)
    panel["signed_gap_hours"] = panel["time_gap_hours"]
    panel["horizon_gap_bin"] = panel["signed_gap_hours"].map(lambda value: f"{int(value):+d}h" if pd.notna(value) else None)
    panel["trackA_core_gap_minus8h"] = panel["signed_gap_hours"].eq(-8)
    panel["trackA_near_gap_abs_le_16h"] = panel["signed_gap_hours"].abs().le(16)
    panel["trackA_spread_clean"] = panel["trackA_core_gap_minus8h"]
    panel["deribit_stale_ok"] = panel["deribit_stale_bar_share"].le(0.30)
    panel["n_fresh_strikes_after_stale"] = panel["deribit_n_distinct_traded_strikes"]
    panel["deribit_fresh_min8_after_stale"] = panel["n_fresh_strikes_after_stale"].ge(8)
    panel["deribit_strike_range_covers_pm"] = (
        panel["deribit_min_traded_strike"].le(panel["min_strike"])
        & panel["deribit_max_traded_strike"].ge(panel["max_strike"])
    )
    panel["trackA_curve_input_candidate"] = (
        panel["pm_trackA_main_candidate"].fillna(False)
        & panel["pm_passes_sum_filter"]
        & panel["deribit_fresh_min8_after_stale"]
        & panel["deribit_stale_ok"]
    )
    panel["trackA_event_day_main_candidate_min6"] = (
        panel["pm_trackA_main_candidate"].fillna(False)
        & panel["pm_passes_sum_filter"]
        & panel["deribit_daily_grid_ok_min6"]
    )
    panel["trackA_event_day_main_candidate_min8"] = (
        panel["pm_trackA_main_candidate"].fillna(False)
        & panel["pm_passes_sum_filter"]
        & panel["deribit_daily_grid_ok_min8"]
    )

    ordered = [
        "event_id",
        "date",
        "asset",
        "event_title",
        "pm_snapshot_timestamp",
        "deribit_bar_timestamp",
        "pm_event_probability_sum",
        "pm_abs_sum_error",
        "pm_passes_sum_filter",
        "pm_trackA_quality_flag",
        "pm_trackA_main_candidate",
        "signed_gap_hours",
        "horizon_gap_bin",
        "trackA_core_gap_minus8h",
        "trackA_near_gap_abs_le_16h",
        "trackA_spread_clean",
        "settlement_reference",
        "deribit_index_reference",
        "reference_basis_mismatch",
        "deribit_n_distinct_traded_strikes",
        "n_fresh_strikes_after_stale",
        "deribit_can_fit_full_curve_min6",
        "deribit_can_fit_full_curve_min8",
        "deribit_fresh_min8_after_stale",
        "deribit_total_volume",
        "deribit_intraday_trade_time_diagnostics_available",
        "deribit_stale_bar_share",
        "deribit_stale_ok",
        "deribit_strike_range_covers_pm",
        "has_deribit_daily_bar",
        "trackA_curve_input_candidate",
        "trackA_event_day_main_candidate_min6",
        "trackA_event_day_main_candidate_min8",
    ]
    return panel[ordered + [c for c in panel.columns if c not in ordered]].sort_values(["event_id", "date"])


def build_cell_day_panel(pm_daily: pd.DataFrame, event_day_quality: pd.DataFrame) -> pd.DataFrame:
    cell_cols = [
        "event_id",
        "date",
        "cell_id",
        "market_id",
        "cell_type",
        "cell_low",
        "cell_high",
        "probability_raw",
        "probability_normalized",
        "sort_key",
    ]
    day_cols = [
        "event_id",
        "date",
        "asset",
        "event_title",
        "pm_snapshot_timestamp",
        "deribit_bar_timestamp",
        "pm_event_probability_sum",
        "pm_abs_sum_error",
        "pm_trackA_quality_flag",
        "pm_trackA_main_candidate",
        "signed_gap_hours",
        "horizon_gap_bin",
        "trackA_core_gap_minus8h",
        "trackA_near_gap_abs_le_16h",
        "trackA_spread_clean",
        "settlement_reference",
        "deribit_index_reference",
        "reference_basis_mismatch",
        "deribit_n_distinct_traded_strikes",
        "n_fresh_strikes_after_stale",
        "deribit_can_fit_full_curve_min6",
        "deribit_can_fit_full_curve_min8",
        "deribit_fresh_min8_after_stale",
        "deribit_intraday_trade_time_diagnostics_available",
        "deribit_stale_bar_share",
        "deribit_stale_ok",
        "deribit_strike_range_covers_pm",
        "trackA_curve_input_candidate",
        "trackA_event_day_main_candidate_min6",
        "trackA_event_day_main_candidate_min8",
    ]
    panel = pm_daily[cell_cols].rename(
        columns={
            "probability_raw": "pm_probability_raw",
            "probability_normalized": "pm_probability_normalized",
        }
    )
    panel = panel.merge(event_day_quality[day_cols], on=["event_id", "date"], how="left")
    return panel.sort_values(["event_id", "date", "sort_key"]).reset_index(drop=True)


def write_table(df: pd.DataFrame, stem: str) -> None:
    csv_path = PANELS_DIR / f"{stem}.csv"
    parquet_path = PANELS_DIR / f"{stem}.parquet"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_parquet(parquet_path, index=False)


def main() -> None:
    PANELS_DIR.mkdir(parents=True, exist_ok=True)

    event_universe = pd.read_parquet(EVENT_UNIVERSE)
    pm_daily = pd.read_parquet(PM_DAILY)
    pm_quality = pd.read_parquet(PM_QUALITY)
    deribit_quality = pd.read_parquet(DERIBIT_QUALITY)

    event_day = build_event_day_quality(event_universe, pm_quality, pm_daily, deribit_quality)
    cell_day = build_cell_day_panel(pm_daily, event_day)

    write_table(event_day, "trackA_event_day_quality")
    write_table(cell_day, "trackA_pm_cell_day_panel")

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_trackA_daily_quality_panel.py",
        "git_commit": git_commit(),
        "inputs": {
            "event_universe": str(EVENT_UNIVERSE.relative_to(PROJECT_ROOT)),
            "pm_daily": str(PM_DAILY.relative_to(PROJECT_ROOT)),
            "pm_quality": str(PM_QUALITY.relative_to(PROJECT_ROOT)),
            "deribit_quality": str(DERIBIT_QUALITY.relative_to(PROJECT_ROOT)),
        },
        "row_counts": {
            "event_day_rows": int(len(event_day)),
            "event_day_events": int(event_day["event_id"].nunique()),
            "cell_day_rows": int(len(cell_day)),
            "cell_day_events": int(cell_day["event_id"].nunique()),
            "main_event_days_min6": int(event_day["trackA_event_day_main_candidate_min6"].sum()),
            "main_event_days_min8": int(event_day["trackA_event_day_main_candidate_min8"].sum()),
            "curve_input_candidate_days": int(event_day["trackA_curve_input_candidate"].sum()),
            "core_gap_minus8h_curve_input_days": int(
                (event_day["trackA_curve_input_candidate"] & event_day["trackA_core_gap_minus8h"]).sum()
            ),
            "near_gap_abs_le_16h_curve_input_days": int(
                (event_day["trackA_curve_input_candidate"] & event_day["trackA_near_gap_abs_le_16h"]).sum()
            ),
        },
        "join_rules": {
            "join_key": "event_id + UTC date",
            "pm_daily_snapshot": "last clean non-warmup hourly observation per UTC date from Polymarket panel",
            "deribit_daily_bar": "Deribit get_tradingview_chart_data 1D bar matched on UTC date",
            "main_candidate_min8": "legacy gate: pm main event, PM daily sum filter pass, and Deribit event-day can_fit_full_curve_min8",
            "curve_input_candidate": "pm main event, PM daily sum filter pass, >=8 fresh traded strikes after stale filtering, and Deribit stale_bar_share <= 0.30",
        },
        "known_caveats": [
            "This is a quality gate panel, not the final daily_distribution_comparison panel.",
            "Deribit bucket probabilities are not estimated here.",
            "abs_time_gap_hours should not be used as a linear control; use signed_gap_hours or horizon_gap_bin fixed effects.",
            "cross_strike_trade_time_spread_minutes from daily OHLC is not a real non-synchronicity diagnostic and is not used as a gate.",
            "reference_basis_mismatch is expected because Polymarket settles to Binance 1m close while Deribit options use Deribit price indexes.",
            "Same-date matching is a first-pass alignment; later curve reconstruction should preserve the exact PM snapshot and Deribit bar timestamps.",
        ],
    }
    (PANELS_DIR / "trackA_daily_quality_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Track A daily quality panel ===")
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value:,}")
    print("\nEvent-day gate counts:")
    print(
        event_day[
            [
                "has_deribit_daily_bar",
                "pm_trackA_main_candidate",
                "deribit_stale_ok",
                "deribit_fresh_min8_after_stale",
                "trackA_curve_input_candidate",
                "trackA_event_day_main_candidate_min6",
                "trackA_event_day_main_candidate_min8",
            ]
        ]
        .value_counts(dropna=False)
        .to_string()
    )
    print("\nBy asset:")
    print(
        event_day.groupby("asset").agg(
            event_days=("date", "count"),
            main_min8=("trackA_event_day_main_candidate_min8", "sum"),
            curve_input=("trackA_curve_input_candidate", "sum"),
            events=("event_id", "nunique"),
        ).to_string()
    )
    print("\nBy signed gap:")
    print(
        event_day.groupby("horizon_gap_bin").agg(
            event_days=("date", "count"),
            curve_input=("trackA_curve_input_candidate", "sum"),
            events=("event_id", "nunique"),
        ).to_string()
    )
    print("\nOutputs:")
    print(f"- {PANELS_DIR / 'trackA_event_day_quality.parquet'}")
    print(f"- {PANELS_DIR / 'trackA_pm_cell_day_panel.parquet'}")
    print(f"- {PANELS_DIR / 'trackA_daily_quality_metadata.json'}")


if __name__ == "__main__":
    main()
