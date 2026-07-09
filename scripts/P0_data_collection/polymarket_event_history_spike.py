"""
Polymarket prices-history spike for one complete price-distribution event.

Purpose:
- Verify that a resolved Polymarket event has usable in-life probability
  distributions, not only one-hot settlement snapshots.
- Pull hourly YES prices for all markets in one event from CLOB prices-history.
- Reconstruct hourly distribution cells: left tail, middle buckets, right tail.
- Check whether the cell probabilities sum close to one during the event life.

Outputs:
- data/processed/polymarket_spike/polymarket_history_event_<event_id>.csv
- data/processed/polymarket_spike/polymarket_hourly_distribution_event_<event_id>.csv
- data/processed/polymarket_spike/polymarket_snapshot_distribution_event_<event_id>_<date>.csv
- data/processed/polymarket_spike/polymarket_event_history_metadata_<event_id>.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
RAW_EVENTS = PROJECT_ROOT / "data" / "raw" / "polymarket" / "polymarket_public_search_events.json"
OUT_DIR = PROJECT_ROOT / "data" / "processed" / "polymarket_spike"

CLOB = "https://clob.polymarket.com"
HEADERS = {"User-Agent": "ucl-dissertation-research/0.1"}


def parse_json_field(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def load_event(event_id: int) -> dict[str, Any]:
    events = json.loads(RAW_EVENTS.read_text(encoding="utf-8"))
    for event in events:
        if str(event.get("id")) == str(event_id):
            return event
    raise RuntimeError(f"event_id={event_id} not found in {RAW_EVENTS}")


def market_cell(market: dict[str, Any]) -> dict[str, Any]:
    question = market.get("question", "")
    q = question.lower()
    token_ids = parse_json_field(market.get("clobTokenIds"))
    yes_token_id = token_ids[0] if token_ids else None

    # Reuse structured parsing from the inventory script to avoid divergent rules.
    from scripts.P0_data_collection.build_polymarket_inventory import classify_question

    parsed = classify_question(question)
    if parsed is None:
        raise RuntimeError(f"Could not classify market question: {question}")

    if parsed["qtype"] == "terminal_bucket":
        cell_type = "bucket"
        cell_low = parsed["strike_low"]
        cell_high = parsed["strike_high"]
        sort_key = cell_low
    elif parsed["qtype"] == "terminal_point" and parsed["direction"] == "below":
        cell_type = "left_tail"
        cell_low = -math.inf
        cell_high = parsed["strike_low"]
        sort_key = parsed["strike_low"] - 1e12
    elif parsed["qtype"] == "terminal_point" and parsed["direction"] == "above":
        cell_type = "right_tail"
        cell_low = parsed["strike_low"]
        cell_high = math.inf
        sort_key = parsed["strike_low"] + 1e12
    else:
        raise RuntimeError(f"Unsupported market for distribution cell: {question}")

    return {
        "market_id": market.get("id") or market.get("conditionId"),
        "condition_id": market.get("conditionId"),
        "question": question,
        "cell_type": cell_type,
        "cell_low": cell_low,
        "cell_high": cell_high,
        "sort_key": sort_key,
        "yes_token_id": yes_token_id,
        "start_date": market.get("startDate"),
        "end_date": market.get("endDate"),
        "closed_time": market.get("closedTime"),
        "volume": float(market.get("volumeNum") or market.get("volume") or 0),
    }


def event_cells(event: dict[str, Any]) -> pd.DataFrame:
    rows = [market_cell(market) for market in event.get("markets", [])]
    cells = pd.DataFrame(rows).sort_values("sort_key").reset_index(drop=True)
    return cells


def fetch_price_history(token_id: str, start: pd.Timestamp, end: pd.Timestamp, fidelity: int, sleep_seconds: float) -> list[dict[str, Any]]:
    response = requests.get(
        f"{CLOB}/prices-history",
        params={
            "market": token_id,
            "startTs": int(start.timestamp()),
            "endTs": int(end.timestamp()),
            "fidelity": fidelity,
        },
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    time.sleep(sleep_seconds)
    return payload.get("history", [])


def pull_event_history(cells: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, fidelity: int, sleep_seconds: float) -> pd.DataFrame:
    rows = []
    for _, cell in cells.iterrows():
        history = fetch_price_history(str(cell["yes_token_id"]), start, end, fidelity, sleep_seconds)
        for point in history:
            ts = datetime.fromtimestamp(point["t"], tz=timezone.utc)
            rows.append(
                {
                    "timestamp": ts,
                    "date": ts.date(),
                    "market_id": cell["market_id"],
                    "question": cell["question"],
                    "cell_type": cell["cell_type"],
                    "cell_low": cell["cell_low"],
                    "cell_high": cell["cell_high"],
                    "sort_key": cell["sort_key"],
                    "yes_token_id": cell["yes_token_id"],
                    "probability": float(point["p"]),
                }
            )
    return pd.DataFrame(rows)


def build_hourly_distribution(history: pd.DataFrame, n_cells: int) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame()

    dist = (
        history.groupby("timestamp", as_index=False)
        .agg(
            n_cells=("probability", "count"),
            probability_sum=("probability", "sum"),
            max_probability=("probability", "max"),
        )
        .sort_values("timestamp")
    )
    dist["missing_cells"] = n_cells - dist["n_cells"]
    dist["abs_sum_error"] = (dist["probability_sum"] - 1.0).abs()
    dist["sum_in_0p9_1p1"] = dist["probability_sum"].between(0.9, 1.1)
    return dist


def snapshot_distribution(history: pd.DataFrame, snapshot_time: pd.Timestamp | None, snapshot_date: str | None) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    if history.empty:
        return pd.DataFrame(), None

    if snapshot_time is not None:
        target = pd.Timestamp(snapshot_time).tz_convert("UTC")
        history = history.copy()
        history["distance_seconds"] = (pd.to_datetime(history["timestamp"], utc=True) - target).abs().dt.total_seconds()
        idx = history.groupby("market_id")["distance_seconds"].idxmin()
        snap = history.loc[idx].copy()
        selected_time = target
    else:
        if snapshot_date is None:
            snapshot_date = str(history["date"].max())
        day = history[history["date"].astype(str) == snapshot_date].copy()
        if day.empty:
            return pd.DataFrame(), None
        idx = day.groupby("market_id")["timestamp"].idxmax()
        snap = day.loc[idx].copy()
        selected_time = pd.Timestamp(day["timestamp"].max())

    snap = snap.sort_values("sort_key").reset_index(drop=True)
    snap["probability_sum"] = snap["probability"].sum()
    snap["normalized_probability"] = snap["probability"] / snap["probability_sum"] if snap["probability_sum"].iloc[0] else math.nan
    return snap, selected_time


def count_modes(probabilities: list[float]) -> int:
    if len(probabilities) < 3:
        return 0
    max_value = max(probabilities)
    return int(sum(abs(p - max_value) < 1e-12 for p in probabilities))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", type=int, default=21348)
    parser.add_argument("--start", type=str, default=None, help="UTC ISO start. Defaults to event start date.")
    parser.add_argument("--end", type=str, default=None, help="UTC ISO end. Defaults to event end date.")
    parser.add_argument("--snapshot-date", type=str, default="2025-03-25")
    parser.add_argument("--snapshot-time", type=str, default=None, help="UTC ISO timestamp. If supplied, choose nearest point per market.")
    parser.add_argument("--fidelity", type=int, default=60)
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    event = load_event(args.event_id)
    cells = event_cells(event)

    event_start = pd.to_datetime(event.get("startDate"), utc=True)
    event_end = pd.to_datetime(event.get("endDate"), utc=True)
    start = pd.to_datetime(args.start, utc=True) if args.start else event_start.floor("D")
    end = pd.to_datetime(args.end, utc=True) if args.end else event_end.ceil("D") - pd.Timedelta(seconds=1)
    snapshot_time = pd.to_datetime(args.snapshot_time, utc=True) if args.snapshot_time else None

    history = pull_event_history(cells, start, end, args.fidelity, args.sleep_seconds)
    hourly = build_hourly_distribution(history, len(cells))
    snapshot, selected_time = snapshot_distribution(history, snapshot_time, args.snapshot_date)

    event_id = int(event["id"])
    history_csv = OUT_DIR / f"polymarket_history_event_{event_id}.csv"
    hourly_csv = OUT_DIR / f"polymarket_hourly_distribution_event_{event_id}.csv"
    snapshot_label = (args.snapshot_time or args.snapshot_date or "latest").replace(":", "").replace("-", "").replace("+", "")
    snapshot_csv = OUT_DIR / f"polymarket_snapshot_distribution_event_{event_id}_{snapshot_label}.csv"
    metadata_json = OUT_DIR / f"polymarket_event_history_metadata_{event_id}.json"

    history.to_csv(history_csv, index=False, encoding="utf-8-sig")
    hourly.to_csv(hourly_csv, index=False, encoding="utf-8-sig")
    snapshot.to_csv(snapshot_csv, index=False, encoding="utf-8-sig")

    probs = snapshot["probability"].tolist() if not snapshot.empty else []
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_id": event_id,
        "event_title": event.get("title"),
        "event_start": str(event_start),
        "event_end": str(event_end),
        "pull_start": str(start),
        "pull_end": str(end),
        "fidelity_minutes": args.fidelity,
        "n_cells": len(cells),
        "history_rows": len(history),
        "hourly_rows": len(hourly),
        "snapshot_requested_date": args.snapshot_date,
        "snapshot_requested_time": args.snapshot_time,
        "snapshot_selected_time": str(selected_time) if selected_time is not None else None,
        "snapshot_probability_sum": float(sum(probs)) if probs else None,
        "snapshot_abs_sum_error": float(abs(sum(probs) - 1.0)) if probs else None,
        "snapshot_mode_count": count_modes(probs),
        "hourly_sum_in_0p9_1p1_share": float(hourly["sum_in_0p9_1p1"].mean()) if not hourly.empty else None,
        "cells": cells.to_dict("records"),
    }
    metadata_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== Polymarket event history spike ===")
    print(f"event: {event_id} | {event.get('title')}")
    print(f"event life: {event_start} to {event_end}")
    print(f"pull window: {start} to {end}")
    print(f"cells: {len(cells)}")
    print(f"history rows: {len(history):,}")
    if not hourly.empty:
        print("\n=== hourly probability sum ===")
        print(hourly[["timestamp", "n_cells", "probability_sum", "abs_sum_error", "sum_in_0p9_1p1"]].head(10).to_string(index=False))
        print("...")
        print(hourly[["timestamp", "n_cells", "probability_sum", "abs_sum_error", "sum_in_0p9_1p1"]].tail(10).to_string(index=False))
        print("\nSummary:")
        print(hourly[["n_cells", "probability_sum", "abs_sum_error"]].describe().to_string())
    print("\n=== snapshot distribution ===")
    if snapshot.empty:
        print("No snapshot available.")
    else:
        print(f"selected time: {selected_time}")
        print(snapshot[["cell_type", "cell_low", "cell_high", "probability", "normalized_probability", "question"]].to_string(index=False))
        print(f"sum: {snapshot['probability'].sum():.6f}")
    print("\nOutputs:")
    print(f"- {history_csv}")
    print(f"- {hourly_csv}")
    print(f"- {snapshot_csv}")
    print(f"- {metadata_json}")


if __name__ == "__main__":
    main()
