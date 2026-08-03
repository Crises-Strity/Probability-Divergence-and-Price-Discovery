"""
Build Track B Polymarket hourly survival-probability panel.

Inputs:
- data/processed/panels/trackB_kstar_panel.parquet
- data/processed/polymarket/polymarket_distribution_hourly.parquet
- data/raw/polymarket/prices_history_<event_id>.parquet for point-threshold events

Outputs:
- data/processed/panels/pm_survival_hourly.{csv,parquet}
- data/processed/panels/trackB_pm_informative_event_summary.{csv,parquet}
- data/processed/panels/trackB_pm_survival_metadata.json
- paper/tables/tab_trackB_pm_survival_summary.{csv,tex}
- paper/tables/tab_trackB_pm_informative_event_summary.{csv,tex}
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path("/private/tmp") / "matplotlib-codex"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path("/private/tmp") / "codex-cache"))

import numpy as np
import pandas as pd


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
POLY_DIR = PROJECT_ROOT / "data" / "processed" / "polymarket"
PANELS_DIR = PROJECT_ROOT / "data" / "processed" / "panels"
RAW_POLY_DIR = PROJECT_ROOT / "data" / "raw" / "polymarket"
TABLES_DIR = PROJECT_ROOT / "paper" / "tables"

KSTAR_PANEL = PANELS_DIR / "trackB_kstar_panel.parquet"
PM_HOURLY = POLY_DIR / "polymarket_distribution_hourly.parquet"

WARMUP_HOURS = 3
SATURATION_LOW = 0.05
SATURATION_HIGH = 0.95


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


def parse_utc(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"Could not parse timestamp: {value}")
    return ts


def raw_history_path(event_id: int) -> Path:
    return RAW_POLY_DIR / f"prices_history_{event_id}.parquet"


def add_update_proxy(history: pd.DataFrame, price_col: str) -> pd.DataFrame:
    if history.empty:
        return history
    history = history.sort_values(["event_id", "timestamp"]).copy()
    history["previous_price"] = history.groupby("event_id")[price_col].shift()
    history["pm_has_real_update"] = history["previous_price"].isna() | (history[price_col] != history["previous_price"])
    history["last_update_timestamp"] = history["timestamp"].where(history["pm_has_real_update"])
    history["last_update_timestamp"] = history.groupby("event_id")["last_update_timestamp"].ffill()
    history["pm_time_since_last_update_minutes"] = (
        pd.to_datetime(history["timestamp"], utc=True)
        - pd.to_datetime(history["last_update_timestamp"], utc=True)
    ).dt.total_seconds() / 60.0
    return history.drop(columns=["previous_price", "last_update_timestamp"])


def build_bucket_survival(kstar: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    bucket = kstar[
        kstar["kstar_selection_status"].eq("pass")
        & kstar["event_type_for_trackB"].eq("bucket_distribution")
    ].copy()
    if bucket.empty:
        return pd.DataFrame()

    rows = []
    hourly = hourly[hourly["event_id"].isin(bucket["event_id"])].copy()
    for _, event in bucket.iterrows():
        event_id = int(event["event_id"])
        k_star = float(event["K_star"])
        group = hourly[hourly["event_id"].eq(event_id)].copy()
        if group.empty:
            continue
        above = group[np.isfinite(group["cell_low"]) & (group["cell_low"].astype(float) >= k_star)].copy()
        if above.empty:
            continue
        grouped = above.groupby(["event_id", "timestamp"], as_index=False).agg(
            pm_survival_raw=("probability_raw", lambda values: values.sum(min_count=1)),
            pm_survival=("probability_normalized", lambda values: values.sum(min_count=1)),
            pm_has_real_update=("has_real_update", "max"),
            pm_update_count_in_bar=("has_real_update", "sum"),
            pm_time_since_last_update_minutes=("time_since_last_update_minutes", "min"),
            pm_time_since_last_update_minutes_median=("time_since_last_update_minutes", "median"),
            pm_component_cells=("cell_id", "nunique"),
            pm_observed_timestamp=("observed_timestamp", "max"),
            event_probability_sum=("event_probability_sum", "first"),
            sum_error=("sum_error", "first"),
            is_complete_partition=("is_complete_partition", "first"),
            is_warmup=("is_warmup", "first"),
            passes_sum_filter=("passes_sum_filter", "first"),
        )
        grouped["event_type_for_trackB"] = event["event_type_for_trackB"]
        grouped["asset"] = event["asset"]
        grouped["K_star"] = k_star
        grouped["K_star_source"] = event["K_star_source"]
        grouped["selection_reason"] = event["selection_reason"]
        grouped["initial_pm_survival"] = event["initial_pm_survival"]
        grouped["initial_k_star_moneyness"] = event["initial_k_star_moneyness"]
        grouped["pm_survival_source"] = "bucket_cell_sum_normalized"
        grouped["pm_survival_quality_status"] = np.where(
            grouped["is_complete_partition"] & grouped["passes_sum_filter"] & ~grouped["is_warmup"],
            "pass",
            "fail_pm_partition_quality",
        )
        rows.append(grouped)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def build_point_survival(kstar: pd.DataFrame) -> pd.DataFrame:
    point = kstar[
        kstar["kstar_selection_status"].eq("pass")
        & kstar["event_type_for_trackB"].eq("point_threshold")
    ].copy()
    if point.empty:
        return pd.DataFrame()

    rows = []
    for _, event in point.iterrows():
        event_id = int(event["event_id"])
        path = raw_history_path(event_id)
        if not path.exists():
            continue
        history = pd.read_parquet(path)
        if history.empty:
            continue
        history = history[history["cell_id"].eq(int(event["kstar_cell_id"]))].copy()
        if history.empty:
            continue
        history["observed_timestamp"] = pd.to_datetime(history["timestamp"], utc=True)
        history["timestamp"] = history["observed_timestamp"].dt.floor("h")
        history = (
            history.sort_values(["event_id", "timestamp", "observed_timestamp"])
            .drop_duplicates(["event_id", "timestamp"], keep="last")
            .reset_index(drop=True)
        )
        history = add_update_proxy(history.rename(columns={"price": "pm_survival"}), price_col="pm_survival")
        event_start = parse_utc(event["event_start_time"])
        history["is_warmup"] = pd.to_datetime(history["timestamp"], utc=True) < (
            event_start + pd.Timedelta(hours=WARMUP_HOURS)
        )
        history["event_type_for_trackB"] = event["event_type_for_trackB"]
        history["asset"] = event["asset"]
        history["K_star"] = float(event["K_star"])
        history["K_star_source"] = event["K_star_source"]
        history["selection_reason"] = event["selection_reason"]
        history["initial_pm_survival"] = event["initial_pm_survival"]
        history["initial_k_star_moneyness"] = event["initial_k_star_moneyness"]
        history["pm_survival_raw"] = history["pm_survival"]
        history["pm_survival_source"] = "point_threshold_yes_price"
        history["pm_update_count_in_bar"] = history["pm_has_real_update"].astype(int)
        history["pm_time_since_last_update_minutes_median"] = history["pm_time_since_last_update_minutes"]
        history["pm_component_cells"] = 1
        history["pm_observed_timestamp"] = history["observed_timestamp"]
        history["event_probability_sum"] = math.nan
        history["sum_error"] = math.nan
        history["is_complete_partition"] = pd.NA
        history["passes_sum_filter"] = pd.NA
        history["pm_survival_quality_status"] = np.where(
            ~history["is_warmup"],
            "pass",
            "fail_pm_warmup",
        )
        rows.append(history)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def finalize_panel(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return panel
    panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True)
    panel["pm_observed_timestamp"] = pd.to_datetime(panel["pm_observed_timestamp"], utc=True)
    saturated = panel["pm_survival"].le(SATURATION_LOW) | panel["pm_survival"].ge(SATURATION_HIGH)
    panel["pm_survival_saturated"] = saturated.where(panel["pm_survival"].notna(), pd.NA)
    panel["pm_survival_low_power_flag"] = panel["pm_survival_saturated"]
    panel["trackB_pm_informative_candidate"] = (
        panel["pm_survival_quality_status"].eq("pass")
        & panel["pm_has_real_update"].fillna(False)
        & panel["pm_survival_saturated"].eq(False)
    )
    panel["pm_survival_change"] = panel.sort_values(["event_id", "timestamp"]).groupby("event_id")["pm_survival"].diff()
    panel["pm_survival_abs_change"] = panel["pm_survival_change"].abs()
    ordered = [
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
        "pm_survival_change",
        "pm_survival_abs_change",
        "pm_survival_source",
        "pm_survival_quality_status",
        "pm_survival_saturated",
        "pm_survival_low_power_flag",
        "trackB_pm_informative_candidate",
        "pm_has_real_update",
        "pm_update_count_in_bar",
        "pm_time_since_last_update_minutes",
        "pm_time_since_last_update_minutes_median",
        "pm_component_cells",
        "event_probability_sum",
        "sum_error",
        "is_complete_partition",
        "is_warmup",
        "passes_sum_filter",
        "initial_pm_survival",
        "initial_k_star_moneyness",
    ]
    for col in ordered:
        if col not in panel:
            panel[col] = math.nan
    return panel[ordered].sort_values(["event_id", "timestamp"]).reset_index(drop=True)


def write_table(df: pd.DataFrame, stem: str, caption: str, label: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES_DIR / f"{stem}.csv", index=False, encoding="utf-8-sig")
    tex = df.to_latex(index=False, escape=True, caption=caption, label=label, float_format="%.4f")
    (TABLES_DIR / f"{stem}.tex").write_text(tex, encoding="utf-8")


def summary_table(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    rows = []
    for event_type, group in panel.groupby("event_type_for_trackB", dropna=False):
        event_bars = group.drop_duplicates(["event_id", "timestamp"])
        pass_bars = event_bars[event_bars["pm_survival_quality_status"].eq("pass")].copy()
        rows.append(
            {
                "event_type_for_trackB": event_type,
                "events": int(event_bars["event_id"].nunique()),
                "hourly_bars": int(len(event_bars)),
                "pass_quality_bars": int(event_bars["pm_survival_quality_status"].eq("pass").sum()),
                "pass_quality_share": float(event_bars["pm_survival_quality_status"].eq("pass").mean()),
                "real_update_share": float(event_bars["pm_has_real_update"].mean()),
                "saturated_share": float(event_bars["pm_survival_saturated"].mean()),
                "pass_quality_real_update_share": float(pass_bars["pm_has_real_update"].mean()) if not pass_bars.empty else math.nan,
                "pass_quality_saturated_share": float(pass_bars["pm_survival_saturated"].mean()) if not pass_bars.empty else math.nan,
                "median_survival": float(event_bars["pm_survival"].median()),
                "pass_quality_median_survival": float(pass_bars["pm_survival"].median()) if not pass_bars.empty else math.nan,
                "median_abs_change": float(event_bars["pm_survival_abs_change"].median()),
                "pass_quality_median_abs_change": float(pass_bars["pm_survival_abs_change"].median()) if not pass_bars.empty else math.nan,
            }
        )
    return pd.DataFrame(rows)


def informative_event_summary(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    event_summary = (
        panel.groupby(["event_type_for_trackB", "event_id"], as_index=False)
        .agg(
            hourly_bars=("timestamp", "count"),
            pass_quality_hours=("pm_survival_quality_status", lambda values: int(values.eq("pass").sum())),
            real_update_hours=("pm_has_real_update", lambda values: int(values.astype("boolean").fillna(False).sum())),
            saturated_hours=("pm_survival_saturated", lambda values: int(values.astype("boolean").fillna(False).sum())),
            informative_hours=("trackB_pm_informative_candidate", lambda values: int(values.astype("boolean").fillna(False).sum())),
            informative_share=("trackB_pm_informative_candidate", "mean"),
            median_pm_survival=("pm_survival", "median"),
            median_abs_change=("pm_survival_abs_change", "median"),
        )
    )
    rows = []
    for event_type, group in event_summary.groupby("event_type_for_trackB", dropna=False):
        rows.append(
            {
                "event_type_for_trackB": event_type,
                "events": int(len(group)),
                "total_informative_hours": int(group["informative_hours"].sum()),
                "median_informative_hours": float(group["informative_hours"].median()),
                "events_ge_72_informative_hours": int(group["informative_hours"].ge(72).sum()),
                "events_ge_48_informative_hours": int(group["informative_hours"].ge(48).sum()),
                "events_zero_informative_hours": int(group["informative_hours"].eq(0).sum()),
                "median_informative_share": float(group["informative_share"].median()),
                "median_event_survival": float(group["median_pm_survival"].median()),
                "median_event_abs_change": float(group["median_abs_change"].median()),
            }
        )
    return pd.DataFrame(rows), event_summary


def main() -> None:
    kstar = pd.read_parquet(KSTAR_PANEL)
    hourly = pd.read_parquet(PM_HOURLY)

    bucket_panel = build_bucket_survival(kstar, hourly)
    point_panel = build_point_survival(kstar)
    panel = finalize_panel(pd.concat([bucket_panel, point_panel], ignore_index=True))
    summary = summary_table(panel)
    informative_summary, informative_event_panel = informative_event_summary(panel)

    PANELS_DIR.mkdir(parents=True, exist_ok=True)
    panel.to_csv(PANELS_DIR / "pm_survival_hourly.csv", index=False, encoding="utf-8-sig")
    panel.to_parquet(PANELS_DIR / "pm_survival_hourly.parquet", index=False)
    informative_event_panel.to_csv(PANELS_DIR / "trackB_pm_informative_event_panel.csv", index=False, encoding="utf-8-sig")
    informative_event_panel.to_parquet(PANELS_DIR / "trackB_pm_informative_event_panel.parquet", index=False)
    write_table(summary, "tab_trackB_pm_survival_summary", "Track B Polymarket survival-probability summary.", "tab:trackB_pm_survival_summary")
    write_table(informative_summary, "tab_trackB_pm_informative_event_summary", "Track B Polymarket informative-hour event summary.", "tab:trackB_pm_informative_event_summary")

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_trackB_pm_survival_panel.py",
        "git_commit": git_commit(),
        "inputs": {
            "kstar_panel": str(KSTAR_PANEL.relative_to(PROJECT_ROOT)),
            "pm_hourly_distribution": str(PM_HOURLY.relative_to(PROJECT_ROOT)),
            "raw_point_histories": "data/raw/polymarket/prices_history_<event_id>.parquet",
        },
        "filter_rules": {
            "bucket_survival": "sum normalized bucket probabilities for cells with cell_low >= K_star",
            "point_survival": "YES price for the selected point_above threshold",
            "saturation_flag": f"pm_survival <= {SATURATION_LOW} or >= {SATURATION_HIGH}",
            "warmup_hours": WARMUP_HOURS,
        },
        "row_counts": {
            "rows": int(len(panel)),
            "events": int(panel["event_id"].nunique()) if not panel.empty else 0,
            "bucket_events": int(panel.loc[panel["event_type_for_trackB"].eq("bucket_distribution"), "event_id"].nunique()) if not panel.empty else 0,
            "point_events": int(panel.loc[panel["event_type_for_trackB"].eq("point_threshold"), "event_id"].nunique()) if not panel.empty else 0,
            "pass_quality_rows": int(panel["pm_survival_quality_status"].eq("pass").sum()) if not panel.empty else 0,
            "informative_rows": int(panel["trackB_pm_informative_candidate"].sum()) if not panel.empty else 0,
        },
        "summary": summary.to_dict(orient="records"),
        "informative_summary": informative_summary.to_dict(orient="records"),
        "known_caveats": [
            "Polymarket prices-history is sampled; has_real_update is a price-change proxy, not order-book message activity.",
            "Bucket survival uses normalized probabilities and therefore inherits the partition-sum quality gate.",
            "Point-threshold survival has no partition-sum gate and is highly saturation-prone; point-threshold events should not be in the primary lead-lag sample unless explicitly promoted after Deribit-side coverage checks.",
            "trackB_pm_informative_candidate is pass_quality AND real_update AND non-saturated; it is a PM-side eligibility flag, not a final lead-lag sample flag.",
        ],
    }
    (PANELS_DIR / "trackB_pm_survival_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Track B Polymarket survival panel ===")
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value:,}")
    print("\nSummary:")
    print(summary.to_string(index=False))
    print("\nInformative-hour summary:")
    print(informative_summary.to_string(index=False))
    print("\nOutputs:")
    print(f"- {PANELS_DIR / 'pm_survival_hourly.parquet'}")
    print(f"- {PANELS_DIR / 'trackB_pm_informative_event_panel.parquet'}")
    print(f"- {PANELS_DIR / 'trackB_pm_survival_metadata.json'}")
    print(f"- {TABLES_DIR / 'tab_trackB_pm_survival_summary.tex'}")
    print(f"- {TABLES_DIR / 'tab_trackB_pm_informative_event_summary.tex'}")


if __name__ == "__main__":
    main()
