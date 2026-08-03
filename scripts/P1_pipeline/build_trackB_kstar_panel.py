"""
Build Track B ex-ante K* selection panel.

The current repository does not contain an external BTC/ETH index series at
event start. For bucket-distribution events, the implemented fallback selects
the Polymarket boundary whose first clean post-warmup survival probability is
closest to 0.5. For point-threshold events, it selects the market-defined
threshold whose first post-warmup YES price is closest to 0.5.

Outputs:
- data/processed/panels/trackB_kstar_panel.{csv,parquet}
- data/processed/panels/trackB_kstar_metadata.json
- paper/tables/tab_trackB_kstar_summary.{csv,tex}
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

EVENT_UNIVERSE = POLY_DIR / "event_universe.parquet"
EVENT_CELLS = POLY_DIR / "event_cells.parquet"
PM_HOURLY = POLY_DIR / "polymarket_distribution_hourly.parquet"

WARMUP_HOURS = 3


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


def finite_boundaries(cells: pd.DataFrame) -> list[float]:
    boundaries = cells.loc[np.isfinite(cells["cell_low"]), "cell_low"].astype(float).unique().tolist()
    return sorted(boundaries)


def bucket_survival_at_boundary(snapshot: pd.DataFrame, boundary: float) -> float:
    above = snapshot[np.isfinite(snapshot["cell_low"]) & (snapshot["cell_low"].astype(float) >= boundary)]
    return float(above["probability_normalized"].sum())


def select_bucket_kstar(event: pd.Series, cells: pd.DataFrame, hourly: pd.DataFrame) -> dict[str, Any]:
    event_id = int(event["event_id"])
    clean = hourly[
        (hourly["event_id"] == event_id)
        & hourly["is_complete_partition"]
        & hourly["passes_sum_filter"]
        & ~hourly["is_warmup"]
        & hourly["probability_normalized"].notna()
    ].copy()
    if clean.empty:
        return {
            "event_id": event_id,
            "kstar_selection_status": "fail_no_clean_pm_hourly_snapshot",
        }

    first_ts = clean["timestamp"].min()
    snapshot = clean[clean["timestamp"] == first_ts].copy()
    candidates = []
    for boundary in finite_boundaries(cells):
        survival = bucket_survival_at_boundary(snapshot, boundary)
        candidates.append(
            {
                "K_star": boundary,
                "initial_pm_survival": survival,
                "distance_to_half": abs(survival - 0.5),
            }
        )
    if not candidates:
        return {
            "event_id": event_id,
            "kstar_selection_status": "fail_no_finite_bucket_boundary",
        }

    selected = sorted(candidates, key=lambda row: (row["distance_to_half"], row["K_star"]))[0]
    return {
        "event_id": event_id,
        "kstar_selection_status": "pass",
        "K_star": float(selected["K_star"]),
        "K_star_source": "rule_selected",
        "selection_reason": "pm_start_implied_median_boundary",
        "kstar_market_id": None,
        "kstar_cell_id": None,
        "kstar_yes_token_id": None,
        "underlying_reference_time": None,
        "underlying_reference_price": math.nan,
        "initial_k_star_moneyness": math.nan,
        "initial_pm_reference_timestamp": str(first_ts),
        "initial_pm_survival": float(selected["initial_pm_survival"]),
        "initial_distance_to_half": float(selected["distance_to_half"]),
        "n_kstar_candidates": int(len(candidates)),
    }


def point_history_first_snapshot(event: pd.Series, cells: pd.DataFrame) -> pd.DataFrame:
    event_id = int(event["event_id"])
    path = raw_history_path(event_id)
    if not path.exists():
        return pd.DataFrame()

    history = pd.read_parquet(path)
    if history.empty:
        return history
    history = history[history["cell_id"].isin(cells["cell_id"])].copy()
    if history.empty:
        return history
    history["timestamp"] = pd.to_datetime(history["timestamp"], utc=True)
    event_start = parse_utc(event["event_start_time"])
    min_ts = event_start + pd.Timedelta(hours=WARMUP_HOURS)
    history = history[history["timestamp"] >= min_ts].copy()
    if history.empty:
        return history
    first_ts = history["timestamp"].min()
    snapshot = (
        history[history["timestamp"] == first_ts]
        .sort_values(["cell_id", "timestamp"])
        .drop_duplicates(["cell_id"], keep="last")
        .copy()
    )
    return snapshot


def select_point_kstar(event: pd.Series, cells: pd.DataFrame) -> dict[str, Any]:
    event_id = int(event["event_id"])
    point_cells = cells[cells["cell_type"].eq("point_above")].copy()
    if point_cells.empty:
        return {
            "event_id": event_id,
            "kstar_selection_status": "fail_no_point_above_market",
        }
    snapshot = point_history_first_snapshot(event, point_cells)
    if snapshot.empty:
        return {
            "event_id": event_id,
            "kstar_selection_status": "fail_no_point_history_after_warmup",
        }
    candidates = snapshot.merge(
        point_cells[
            [
                "cell_id",
                "market_id",
                "yes_token_id",
                "cell_low",
                "question",
                "volume",
                "spread",
            ]
        ],
        on=["cell_id", "market_id", "yes_token_id", "cell_low"],
        how="left",
    )
    candidates["distance_to_half"] = (candidates["price"].astype(float) - 0.5).abs()
    candidates = candidates.sort_values(["distance_to_half", "cell_low"]).reset_index(drop=True)
    selected = candidates.iloc[0]
    return {
        "event_id": event_id,
        "kstar_selection_status": "pass",
        "K_star": float(selected["cell_low"]),
        "K_star_source": "market_defined",
        "selection_reason": "market_defined_threshold_closest_to_start_yes_0p5",
        "kstar_market_id": selected["market_id"],
        "kstar_cell_id": int(selected["cell_id"]),
        "kstar_yes_token_id": str(selected["yes_token_id"]),
        "underlying_reference_time": None,
        "underlying_reference_price": math.nan,
        "initial_k_star_moneyness": math.nan,
        "initial_pm_reference_timestamp": str(selected["timestamp"]),
        "initial_pm_survival": float(selected["price"]),
        "initial_distance_to_half": float(selected["distance_to_half"]),
        "n_kstar_candidates": int(len(candidates)),
    }


def build_kstar_panel(events: pd.DataFrame, cells: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    trackb_events = events[events["trackB_eligible"]].sort_values("event_id").copy()
    for _, event in trackb_events.iterrows():
        event_id = int(event["event_id"])
        event_cells = cells[cells["event_id"] == event_id].copy()
        event_type = str(event["event_type_for_trackB"])
        if event_type == "bucket_distribution":
            selected = select_bucket_kstar(event, event_cells, hourly)
        elif event_type == "point_threshold":
            selected = select_point_kstar(event, event_cells)
        else:
            selected = {"event_id": event_id, "kstar_selection_status": "fail_not_trackB_type"}

        base = {
            "event_id": event_id,
            "event_title": event["event_title"],
            "asset": event["asset"],
            "event_type_for_trackB": event_type,
            "event_start_time": event["event_start_time"],
            "event_end_time": event["event_end_time"],
            "nearest_deribit_expiry": event["nearest_deribit_expiry"],
            "time_gap_hours": event["time_gap_hours"],
            "mapping_quality": event["mapping_quality"],
            "distribution_quality": event["distribution_quality"],
            "min_strike": event["min_strike"],
            "max_strike": event["max_strike"],
            "median_bucket_width": event["median_bucket_width"],
        }
        base.update(selected)
        rows.append(base)

    panel = pd.DataFrame(rows)
    ordered = [
        "event_id",
        "event_title",
        "asset",
        "event_type_for_trackB",
        "kstar_selection_status",
        "K_star",
        "K_star_source",
        "selection_reason",
        "kstar_market_id",
        "kstar_cell_id",
        "kstar_yes_token_id",
        "event_start_time",
        "event_end_time",
        "nearest_deribit_expiry",
        "time_gap_hours",
        "mapping_quality",
        "distribution_quality",
        "min_strike",
        "max_strike",
        "median_bucket_width",
        "underlying_reference_time",
        "underlying_reference_price",
        "initial_k_star_moneyness",
        "initial_pm_reference_timestamp",
        "initial_pm_survival",
        "initial_distance_to_half",
        "n_kstar_candidates",
    ]
    for col in ordered:
        if col not in panel:
            panel[col] = math.nan
    return panel[ordered].sort_values("event_id").reset_index(drop=True)


def write_table(df: pd.DataFrame, stem: str, caption: str, label: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES_DIR / f"{stem}.csv", index=False, encoding="utf-8-sig")
    tex = df.to_latex(index=False, escape=True, caption=caption, label=label, float_format="%.4f")
    (TABLES_DIR / f"{stem}.tex").write_text(tex, encoding="utf-8")


def summary_table(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for event_type, group in panel.groupby("event_type_for_trackB", dropna=False):
        rows.append(
            {
                "event_type_for_trackB": event_type,
                "events": int(len(group)),
                "pass_events": int(group["kstar_selection_status"].eq("pass").sum()),
                "pass_share": float(group["kstar_selection_status"].eq("pass").mean()),
                "median_initial_pm_survival": float(group.loc[group["kstar_selection_status"].eq("pass"), "initial_pm_survival"].median()),
                "median_distance_to_half": float(group.loc[group["kstar_selection_status"].eq("pass"), "initial_distance_to_half"].median()),
                "median_kstar": float(group.loc[group["kstar_selection_status"].eq("pass"), "K_star"].median()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    events = pd.read_parquet(EVENT_UNIVERSE)
    cells = pd.read_parquet(EVENT_CELLS)
    hourly = pd.read_parquet(PM_HOURLY)

    panel = build_kstar_panel(events, cells, hourly)
    summary = summary_table(panel)

    PANELS_DIR.mkdir(parents=True, exist_ok=True)
    panel.to_csv(PANELS_DIR / "trackB_kstar_panel.csv", index=False, encoding="utf-8-sig")
    panel.to_parquet(PANELS_DIR / "trackB_kstar_panel.parquet", index=False)
    write_table(summary, "tab_trackB_kstar_summary", "Track B K* selection summary.", "tab:trackB_kstar_summary")

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_trackB_kstar_panel.py",
        "git_commit": git_commit(),
        "inputs": {
            "event_universe": str(EVENT_UNIVERSE.relative_to(PROJECT_ROOT)),
            "event_cells": str(EVENT_CELLS.relative_to(PROJECT_ROOT)),
            "pm_hourly": str(PM_HOURLY.relative_to(PROJECT_ROOT)),
            "raw_point_histories": "data/raw/polymarket/prices_history_<event_id>.parquet",
        },
        "filter_rules": {
            "bucket_kstar": "finite Polymarket boundary with first clean post-warmup PM survival closest to 0.5",
            "point_kstar": "market-defined point_above threshold with first post-warmup YES price closest to 0.5",
            "warmup_hours": WARMUP_HOURS,
        },
        "row_counts": {
            "trackB_events": int(len(panel)),
            "pass_events": int(panel["kstar_selection_status"].eq("pass").sum()),
            "bucket_events": int(panel["event_type_for_trackB"].eq("bucket_distribution").sum()),
            "point_events": int(panel["event_type_for_trackB"].eq("point_threshold").sum()),
        },
        "summary": summary.to_dict(orient="records"),
        "known_caveats": [
            "No external BTC/ETH event-start index series is available in the repository yet; initial_k_star_moneyness is therefore null.",
            "Bucket-event K* currently uses an ex-ante Polymarket-implied fallback rather than a spot-index ATM boundary.",
            "Point-threshold events contain multiple market-defined thresholds; the current rule picks the least saturated threshold near 0.5 at the first post-warmup observation.",
        ],
    }
    (PANELS_DIR / "trackB_kstar_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Track B K* panel ===")
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value:,}")
    print("\nSummary:")
    print(summary.to_string(index=False))
    print("\nSelection failures:")
    failures = panel[~panel["kstar_selection_status"].eq("pass")]
    if failures.empty:
        print("none")
    else:
        print(failures[["event_id", "event_type_for_trackB", "kstar_selection_status"]].to_string(index=False))
    print("\nOutputs:")
    print(f"- {PANELS_DIR / 'trackB_kstar_panel.parquet'}")
    print(f"- {PANELS_DIR / 'trackB_kstar_metadata.json'}")
    print(f"- {TABLES_DIR / 'tab_trackB_kstar_summary.tex'}")


if __name__ == "__main__":
    main()
