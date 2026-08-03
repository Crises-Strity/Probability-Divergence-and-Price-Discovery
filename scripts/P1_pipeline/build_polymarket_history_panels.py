"""
Download Polymarket prices-history and build P1 probability panels.

This script consumes the canonical P1 event/cell tables from
scripts/P1_pipeline/build_p1_event_cells.py. It writes raw per-event history files and
cell-level hourly/daily panels for clean bucket-distribution events.

Outputs:
- data/raw/polymarket/prices_history_<event_id>.parquet
- data/processed/polymarket/polymarket_distribution_hourly.{csv,parquet}
- data/processed/polymarket/polymarket_distribution_daily.{csv,parquet}
- data/processed/polymarket/polymarket_history_metadata.json
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "polymarket"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "polymarket"
EVENT_UNIVERSE = PROCESSED_DIR / "event_universe.parquet"
EVENT_CELLS = PROCESSED_DIR / "event_cells.parquet"

CLOB = "https://clob.polymarket.com"
HEADERS = {"User-Agent": "ucl-dissertation-research/0.3"}


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
        raise ValueError(f"Could not parse UTC timestamp: {value}")
    return ts


def raw_history_path(event_id: int) -> Path:
    return RAW_DIR / f"prices_history_{event_id}.parquet"


def iter_windows(start: pd.Timestamp, end: pd.Timestamp, chunk_hours: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    cursor = start
    step = pd.Timedelta(hours=chunk_hours)
    while cursor < end:
        window_end = min(cursor + step, end)
        windows.append((cursor, window_end))
        cursor = window_end + pd.Timedelta(seconds=1)
    return windows


def fetch_price_history(
    session: requests.Session,
    token_id: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    fidelity: int,
    timeout: int,
) -> list[dict[str, Any]]:
    response = session.get(
        f"{CLOB}/prices-history",
        params={
            "market": token_id,
            "startTs": int(start.timestamp()),
            "endTs": int(end.timestamp()),
            "fidelity": fidelity,
        },
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload.get("history", [])


def download_event_history(
    event_row: pd.Series,
    event_cells: pd.DataFrame,
    fidelity: int,
    chunk_hours: int,
    sleep_seconds: float,
    timeout: int,
) -> pd.DataFrame:
    event_id = int(event_row["event_id"])
    start = parse_utc(event_row["event_start_time"])
    end = parse_utc(event_row["event_end_time"])

    rows: list[dict[str, Any]] = []
    session = requests.Session()
    for _, cell in event_cells.sort_values("cell_id").iterrows():
        token_id = str(cell["yes_token_id"])
        for window_start, window_end in iter_windows(start, end, chunk_hours):
            points = fetch_price_history(session, token_id, window_start, window_end, fidelity, timeout)
            for point in points:
                ts = datetime.fromtimestamp(point["t"], tz=timezone.utc)
                rows.append(
                    {
                        "event_id": event_id,
                        "cell_id": int(cell["cell_id"]),
                        "market_id": cell["market_id"],
                        "condition_id": cell["condition_id"],
                        "yes_token_id": token_id,
                        "timestamp": ts,
                        "price": float(point["p"]),
                        "cell_type": cell["cell_type"],
                        "cell_low": float(cell["cell_low"]),
                        "cell_high": float(cell["cell_high"]),
                        "sort_key": float(cell["sort_key"]),
                    }
                )
            time.sleep(sleep_seconds)

    history = pd.DataFrame(rows)
    if history.empty:
        return history
    history = history.drop_duplicates(["event_id", "cell_id", "timestamp"]).sort_values(
        ["event_id", "timestamp", "sort_key"]
    )
    return history.reset_index(drop=True)


def load_or_download_histories(
    events: pd.DataFrame,
    cells: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    histories: list[pd.DataFrame] = []
    event_stats: list[dict[str, Any]] = []

    for _, event_row in events.iterrows():
        event_id = int(event_row["event_id"])
        path = raw_history_path(event_id)
        event_cells = cells[cells["event_id"] == event_id].copy()

        if path.exists() and not args.force_download:
            history = pd.read_parquet(path)
            source = "cached"
        else:
            history = download_event_history(
                event_row,
                event_cells,
                fidelity=args.fidelity,
                chunk_hours=args.chunk_hours,
                sleep_seconds=args.sleep_seconds,
                timeout=args.timeout,
            )
            history.to_parquet(path, index=False)
            source = "downloaded"

        histories.append(history)
        event_stats.append(
            {
                "event_id": event_id,
                "event_title": event_row["event_title"],
                "event_type_for_trackB": event_row["event_type_for_trackB"],
                "source": source,
                "n_cells": int(len(event_cells)),
                "history_rows": int(len(history)),
                "raw_path": str(path.relative_to(PROJECT_ROOT)),
            }
        )
        print(f"event_id={event_id} source={source} rows={len(history):,}")

    if histories:
        return pd.concat(histories, ignore_index=True), {"events": event_stats}
    return pd.DataFrame(), {"events": event_stats}


def add_update_proxy(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history

    history = history.sort_values(["event_id", "cell_id", "timestamp"]).copy()
    history["previous_price"] = history.groupby(["event_id", "cell_id"])["price"].shift()
    history["has_real_update"] = history["previous_price"].isna() | (history["price"] != history["previous_price"])
    history["last_update_timestamp"] = history["timestamp"].where(history["has_real_update"])
    history["last_update_timestamp"] = history.groupby(["event_id", "cell_id"])["last_update_timestamp"].ffill()
    history["time_since_last_update_minutes"] = (
        pd.to_datetime(history["timestamp"], utc=True)
        - pd.to_datetime(history["last_update_timestamp"], utc=True)
    ).dt.total_seconds() / 60
    return history.drop(columns=["previous_price", "last_update_timestamp"])


def build_hourly_distribution(history: pd.DataFrame, events: pd.DataFrame, cells: pd.DataFrame, warmup_hours: int) -> pd.DataFrame:
    bucket_events = events[events["event_type_for_trackB"] == "bucket_distribution"].copy()
    if history.empty or bucket_events.empty:
        return pd.DataFrame()

    bucket_event_ids = set(bucket_events["event_id"].astype(int))
    history = history[history["event_id"].isin(bucket_event_ids)].copy()
    history["observed_timestamp"] = pd.to_datetime(history["timestamp"], utc=True)
    history["timestamp"] = history["observed_timestamp"].dt.floor("h")
    history = (
        history.sort_values(["event_id", "cell_id", "timestamp", "observed_timestamp"])
        .drop_duplicates(["event_id", "cell_id", "timestamp"], keep="last")
        .reset_index(drop=True)
    )
    history = add_update_proxy(history)

    expected_cells = cells[cells["event_id"].isin(bucket_event_ids)].groupby("event_id")["cell_id"].nunique()
    grouped = history.groupby(["event_id", "timestamp"], as_index=False).agg(
        n_cells=("cell_id", "nunique"),
        event_probability_sum=("price", "sum"),
        update_count_in_bar=("has_real_update", "sum"),
    )
    grouped["expected_cells"] = grouped["event_id"].map(expected_cells)
    grouped["is_complete_partition"] = grouped["n_cells"] == grouped["expected_cells"]
    grouped["sum_error"] = grouped["event_probability_sum"] - 1.0
    grouped["passes_sum_filter"] = grouped["event_probability_sum"].between(0.9, 1.1)

    event_start = bucket_events.set_index("event_id")["event_start_time"].map(parse_utc)
    grouped["event_start_time"] = grouped["event_id"].map(event_start)
    grouped["is_warmup"] = pd.to_datetime(grouped["timestamp"], utc=True) < (
        pd.to_datetime(grouped["event_start_time"], utc=True) + pd.Timedelta(hours=warmup_hours)
    )

    panel = history.merge(
        grouped[
            [
                "event_id",
                "timestamp",
                "event_probability_sum",
                "sum_error",
                "is_complete_partition",
                "passes_sum_filter",
                "is_warmup",
                "update_count_in_bar",
            ]
        ],
        on=["event_id", "timestamp"],
        how="left",
    )
    panel = panel.rename(columns={"price": "probability_raw"})
    panel["probability_normalized"] = panel["probability_raw"] / panel["event_probability_sum"]
    panel.loc[~panel["passes_sum_filter"] | panel["event_probability_sum"].eq(0), "probability_normalized"] = math.nan

    ordered_cols = [
        "event_id",
        "timestamp",
        "observed_timestamp",
        "cell_id",
        "market_id",
        "cell_type",
        "cell_low",
        "cell_high",
        "probability_raw",
        "event_probability_sum",
        "probability_normalized",
        "sum_error",
        "is_complete_partition",
        "is_warmup",
        "passes_sum_filter",
        "has_real_update",
        "time_since_last_update_minutes",
        "update_count_in_bar",
        "yes_token_id",
        "condition_id",
        "sort_key",
    ]
    return panel[ordered_cols].sort_values(["event_id", "timestamp", "sort_key"]).reset_index(drop=True)


def build_daily_distribution(hourly: pd.DataFrame) -> pd.DataFrame:
    if hourly.empty:
        return pd.DataFrame()

    clean = hourly[
        hourly["is_complete_partition"] & hourly["passes_sum_filter"] & ~hourly["is_warmup"]
    ].copy()
    if clean.empty:
        return clean

    clean["date"] = pd.to_datetime(clean["timestamp"], utc=True).dt.date.astype(str)
    selected_ts = clean.groupby(["event_id", "date"])["timestamp"].max().reset_index()
    daily = clean.merge(selected_ts, on=["event_id", "date", "timestamp"], how="inner")
    return daily.sort_values(["event_id", "date", "sort_key"]).reset_index(drop=True)


def hourly_quality_summary(hourly: pd.DataFrame) -> list[dict[str, Any]]:
    if hourly.empty:
        return []

    bars = hourly.groupby(["event_id", "timestamp"], as_index=False).agg(
        event_probability_sum=("probability_raw", "sum"),
        is_warmup=("is_warmup", "max"),
        is_complete_partition=("is_complete_partition", "max"),
        passes_sum_filter=("passes_sum_filter", "max"),
    )
    nonwarm_complete = bars[~bars["is_warmup"] & bars["is_complete_partition"]].copy()
    if nonwarm_complete.empty:
        return []

    summary = nonwarm_complete.groupby("event_id").agg(
        nonwarm_complete_bars=("timestamp", "count"),
        pass_sum_filter_share=("passes_sum_filter", "mean"),
        min_probability_sum=("event_probability_sum", "min"),
        max_probability_sum=("event_probability_sum", "max"),
        mean_probability_sum=("event_probability_sum", "mean"),
    )
    return [
        {
            "event_id": int(event_id),
            "nonwarm_complete_bars": int(row["nonwarm_complete_bars"]),
            "pass_sum_filter_share": float(row["pass_sum_filter_share"]),
            "min_probability_sum": float(row["min_probability_sum"]),
            "max_probability_sum": float(row["max_probability_sum"]),
            "mean_probability_sum": float(row["mean_probability_sum"]),
        }
        for event_id, row in summary.iterrows()
    ]


def select_events(event_universe: pd.DataFrame, event_id: int | None, max_events: int | None) -> pd.DataFrame:
    events = event_universe[event_universe["trackB_eligible"]].copy()
    if event_id is not None:
        events = events[events["event_id"] == event_id].copy()
    events = events.sort_values(["event_id"])
    if max_events is not None:
        events = events.head(max_events)
    if events.empty:
        raise RuntimeError("No events selected.")
    return events.reset_index(drop=True)


def write_panel(df: pd.DataFrame, stem: str) -> None:
    csv_path = PROCESSED_DIR / f"{stem}.csv"
    parquet_path = PROCESSED_DIR / f"{stem}.parquet"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_parquet(parquet_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", type=int, default=None, help="Optional single-event run for validation.")
    parser.add_argument("--max-events", type=int, default=None, help="Optional first-N event cap after sorting.")
    parser.add_argument("--force-download", action="store_true", help="Re-download even if raw event history exists.")
    parser.add_argument("--fidelity", type=int, default=60)
    parser.add_argument("--chunk-hours", type=int, default=48)
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--warmup-hours", type=int, default=3)
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    event_universe = pd.read_parquet(EVENT_UNIVERSE)
    cells = pd.read_parquet(EVENT_CELLS)
    events = select_events(event_universe, args.event_id, args.max_events)

    history, download_meta = load_or_download_histories(events, cells, args)
    hourly = build_hourly_distribution(history, events, cells, warmup_hours=args.warmup_hours)
    daily = build_daily_distribution(hourly)

    write_panel(hourly, "polymarket_distribution_hourly")
    write_panel(daily, "polymarket_distribution_daily")

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_endpoint": f"{CLOB}/prices-history",
        "script_name": "scripts/P1_pipeline/build_polymarket_history_panels.py",
        "git_commit": git_commit(),
        "event_universe_version": str(EVENT_UNIVERSE.relative_to(PROJECT_ROOT)),
        "filter_rules": {
            "download_sample": "trackB eligible events; optionally restricted by --event-id or --max-events",
            "distribution_panel_sample": "bucket_distribution events only",
            "timestamp_alignment": "processed hourly timestamp is observed_timestamp floored to the UTC hour",
            "sum_filter": "event_probability_sum in [0.9, 1.1]",
            "warmup_flag": f"first {args.warmup_hours} hours after event_start_time",
            "update_proxy": "has_real_update is a price-change proxy from sampled prices-history observations, not raw CLOB message activity",
        },
        "row_counts": {
            "selected_events": int(len(events)),
            "raw_history_rows_loaded": int(len(history)),
            "hourly_panel_rows": int(len(hourly)),
            "daily_panel_rows": int(len(daily)),
            "hourly_event_count": int(hourly["event_id"].nunique()) if not hourly.empty else 0,
            "daily_event_count": int(daily["event_id"].nunique()) if not daily.empty else 0,
        },
        "hourly_quality_summary": hourly_quality_summary(hourly),
        "known_caveats": [
            "Polymarket prices-history provides sampled price history; true order-book update counts require a different data source.",
            "Daily panel uses the last clean hourly observation per UTC day.",
            "Point-threshold event histories are downloaded for later Track B survival work but are not included in the distribution panels.",
        ],
        **download_meta,
    }
    (PROCESSED_DIR / "polymarket_history_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Polymarket history panels built ===")
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value:,}")
    if not hourly.empty:
        bars = hourly.drop_duplicates(["event_id", "timestamp"])
        event_sums = bars.groupby("event_id")["event_probability_sum"].agg(["count", "mean", "min", "max"])
        print("\nHourly probability sum by event bar:")
        print(event_sums.to_string())
    print("\nOutputs:")
    print(f"- {PROCESSED_DIR / 'polymarket_distribution_hourly.parquet'}")
    print(f"- {PROCESSED_DIR / 'polymarket_distribution_daily.parquet'}")
    print(f"- {PROCESSED_DIR / 'polymarket_history_metadata.json'}")


if __name__ == "__main__":
    main()
