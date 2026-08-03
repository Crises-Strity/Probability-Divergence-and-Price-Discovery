"""
Build P1 canonical event universe and Polymarket cell definitions.

Inputs:
- data/processed/polymarket/event_distribution_quality.csv
- data/processed/polymarket/market_pair_candidate_inventory.csv
- data/raw/polymarket/polymarket_public_search_events.json

Outputs:
- data/processed/polymarket/event_universe.{csv,parquet}
- data/processed/polymarket/event_cells.{csv,parquet}
- data/processed/polymarket/p1_event_cells_metadata.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
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
RAW_EVENTS = PROJECT_ROOT / "data" / "raw" / "polymarket" / "polymarket_public_search_events.json"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "polymarket"
EVENT_QUALITY = PROCESSED_DIR / "event_distribution_quality.csv"
MARKET_INVENTORY = PROCESSED_DIR / "market_pair_candidate_inventory.csv"

TARGET_QUALITIES = {"clean_bucket_distribution", "usable_point_thresholds"}
MAIN_MAPPING_QUALITIES = {"exact", "close"}

PAIR_RE = re.compile(r"\b(BTC|ETH)\s*/?\s*USDT\b", re.IGNORECASE)
RESOLUTION_TIME_RE = re.compile(r"\b12:00\b|\bnoon\b", re.IGNORECASE)


def deribit_index_reference(asset: str) -> str | None:
    if asset == "BTC":
        return "btc_usd"
    if asset == "ETH":
        return "eth_usd"
    return None


def settlement_reference_from_description(event: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if event is None:
        return None, None

    descriptions = [event.get("description") or ""]
    for market in event.get("markets", []):
        desc = market.get("description") or ""
        if desc:
            descriptions.append(desc)

    text = "\n".join(descriptions)
    pair_match = PAIR_RE.search(text)
    pair = pair_match.group(0).upper().replace("/", "") if pair_match else None
    source = "Binance" if "binance" in text.lower() else None
    price_field = "close" if re.search(r"\bclose\b", text, flags=re.IGNORECASE) else None
    candle = "1m" if re.search(r"\b1\s*minute\b|\b1m\b", text, flags=re.IGNORECASE) else None
    time_ref = "12:00 ET" if RESOLUTION_TIME_RE.search(text) and "ET" in text else None

    parts = [source, pair, candle, price_field, time_ref]
    compact = "_".join(str(part).lower().replace(" ", "_") for part in parts if part)
    detail = "; ".join(f"{name}={value}" for name, value in [
        ("source", source),
        ("pair", pair),
        ("candle", candle),
        ("price_field", price_field),
        ("time_reference", time_ref),
    ] if value)
    return compact or None, detail or None


def parse_json_field(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def as_float(value: Any) -> float:
    if value is None or value == "":
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def iso_or_none(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.isoformat()


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


def load_raw_events() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    events = json.loads(RAW_EVENTS.read_text(encoding="utf-8"))
    event_lookup: dict[str, dict[str, Any]] = {}
    market_lookup: dict[str, dict[str, Any]] = {}

    for event in events:
        event_id = str(event.get("id"))
        event_lookup[event_id] = event
        for market in event.get("markets", []):
            keys = [market.get("id"), market.get("conditionId")]
            for key in keys:
                if key is not None:
                    market_lookup[str(key)] = market

    return event_lookup, market_lookup


def market_tokens(market: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if market is None:
        return None, None
    token_ids = parse_json_field(market.get("clobTokenIds"))
    if not isinstance(token_ids, list):
        return None, None
    yes_token_id = str(token_ids[0]) if len(token_ids) >= 1 and token_ids[0] is not None else None
    no_token_id = str(token_ids[1]) if len(token_ids) >= 2 and token_ids[1] is not None else None
    return yes_token_id, no_token_id


def choose_event_start(event: dict[str, Any] | None, group: pd.DataFrame) -> str | None:
    if event is not None:
        for key in ["startDate", "creationDate", "createdAt"]:
            value = iso_or_none(event.get(key))
            if value is not None:
                return value
    if "settlement_time" in group:
        return iso_or_none(group["settlement_time"].min())
    return None


def choose_event_end(event: dict[str, Any] | None, row: pd.Series) -> str | None:
    for key in ["settlement_time", "event_end_time", "endDate"]:
        if key in row:
            value = iso_or_none(row[key])
            if value is not None:
                return value
    if event is not None:
        for key in ["endDate", "closedTime"]:
            value = iso_or_none(event.get(key))
            if value is not None:
                return value
    return None


def track_b_type(distribution_quality: str) -> str:
    if distribution_quality == "clean_bucket_distribution":
        return "bucket_distribution"
    if distribution_quality == "usable_point_thresholds":
        return "point_threshold"
    return "excluded"


def build_event_universe(
    event_quality: pd.DataFrame,
    market_inventory: pd.DataFrame,
    event_lookup: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    target = event_quality[
        event_quality["distribution_quality"].isin(TARGET_QUALITIES)
        & event_quality["mapping_quality"].isin(MAIN_MAPPING_QUALITIES)
    ].copy()

    rows: list[dict[str, Any]] = []
    for _, quality_row in target.iterrows():
        event_id = str(int(quality_row["event_id"]))
        event = event_lookup.get(event_id)
        group = market_inventory[market_inventory["event_id"].astype(str) == event_id]
        distribution_quality = str(quality_row["distribution_quality"])
        min_strike = as_float(quality_row["min_strike"])
        max_strike = as_float(quality_row["max_strike"])
        settlement_reference, settlement_reference_detail = settlement_reference_from_description(event)
        deribit_reference = deribit_index_reference(str(quality_row["asset"]))

        rows.append(
            {
                "event_id": int(event_id),
                "event_title": quality_row["event_title"],
                "event_slug": event.get("slug") if event is not None else None,
                "asset": quality_row["asset"],
                "event_start_time": choose_event_start(event, group),
                "event_end_time": choose_event_end(event, quality_row),
                "nearest_deribit_expiry": iso_or_none(quality_row["nearest_deribit_monthly_expiry"]),
                "time_gap_hours": as_float(quality_row["time_gap_hours"]),
                "abs_time_gap_hours": as_float(quality_row["abs_time_gap_hours"]),
                "calendar_gap_days": as_float(quality_row["calendar_gap_days"]),
                "settlement_reference": settlement_reference,
                "settlement_reference_detail": settlement_reference_detail,
                "deribit_index_reference": deribit_reference,
                "reference_basis_mismatch": settlement_reference is not None
                and deribit_reference is not None
                and "binance" in settlement_reference
                and deribit_reference not in settlement_reference,
                "mapping_quality": quality_row["mapping_quality"],
                "distribution_quality": distribution_quality,
                "min_strike": min_strike,
                "max_strike": max_strike,
                "median_bucket_width": as_float(quality_row["median_bucket_width"]),
                "n_terminal_markets": int(quality_row["n_terminal_markets"]),
                "n_terminal_point": int(quality_row["n_terminal_point"]),
                "n_terminal_bucket": int(quality_row["n_terminal_bucket"]),
                "n_unique_buckets": int(quality_row["n_unique_buckets"]),
                "total_volume": as_float(quality_row["total_volume"]),
                "median_spread": as_float(quality_row["median_spread"]),
                "trackA_eligible": distribution_quality == "clean_bucket_distribution",
                "trackB_eligible": distribution_quality in TARGET_QUALITIES,
                "event_type_for_trackB": track_b_type(distribution_quality),
            }
        )

    return pd.DataFrame(rows).sort_values(["event_id"]).reset_index(drop=True)


def cell_type(row: pd.Series, event_type_for_track_b: str) -> str:
    qtype = row["qtype"]
    direction = row["direction"]
    if event_type_for_track_b == "point_threshold":
        if qtype == "terminal_point" and direction == "above":
            return "point_above"
        if qtype == "terminal_point" and direction == "below":
            return "point_below"
        return "point_threshold"

    if qtype == "terminal_bucket":
        return "bucket"
    if qtype == "terminal_point" and direction == "below":
        return "left_tail"
    if qtype == "terminal_point" and direction == "above":
        return "right_tail"
    return "point_threshold"


def sort_key_for_cell(row: pd.Series) -> float:
    ctype = row["cell_type"]
    strike_low = as_float(row["strike_low"])
    if ctype == "left_tail":
        return strike_low - 1e12
    if ctype == "right_tail":
        return strike_low + 1e12
    return strike_low


def bounds_for_cell(row: pd.Series, event_type_for_track_b: str) -> tuple[float, float]:
    qtype = row["qtype"]
    direction = row["direction"]
    strike_low = as_float(row["strike_low"])
    strike_high = as_float(row["strike_high"])

    if event_type_for_track_b == "bucket_distribution":
        if qtype == "terminal_bucket":
            return strike_low, strike_high
        if qtype == "terminal_point" and direction == "below":
            return -math.inf, strike_low
        if qtype == "terminal_point" and direction == "above":
            return strike_low, math.inf

    if qtype == "terminal_point":
        return strike_low, strike_high

    return strike_low, strike_high


def build_event_cells(
    event_universe: pd.DataFrame,
    market_inventory: pd.DataFrame,
    market_lookup: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    event_meta = event_universe.set_index("event_id")
    rows: list[dict[str, Any]] = []

    target_market_rows = market_inventory[
        market_inventory["event_id"].isin(event_universe["event_id"])
        & market_inventory["mapping_quality"].isin(MAIN_MAPPING_QUALITIES)
    ].copy()

    for _, market_row in target_market_rows.iterrows():
        event_id = int(market_row["event_id"])
        meta = event_meta.loc[event_id]
        event_type_for_track_b = str(meta["event_type_for_trackB"])

        if event_type_for_track_b == "bucket_distribution":
            keep = market_row["qtype"] in {"terminal_bucket", "terminal_point"}
        else:
            keep = market_row["qtype"] == "terminal_point"
        if not keep:
            continue

        market_key = str(market_row["market_id"])
        condition_key = str(market_row["condition_id"])
        raw_market = market_lookup.get(market_key) or market_lookup.get(condition_key)
        yes_token_id, no_token_id = market_tokens(raw_market)

        work = market_row.copy()
        work["cell_type"] = cell_type(work, event_type_for_track_b)
        cell_low, cell_high = bounds_for_cell(work, event_type_for_track_b)
        sort_key = sort_key_for_cell(work)

        rows.append(
            {
                "event_id": event_id,
                "event_type_for_trackB": event_type_for_track_b,
                "market_id": market_row["market_id"],
                "condition_id": market_row["condition_id"],
                "question": market_row["question"],
                "cell_type": work["cell_type"],
                "cell_low": cell_low,
                "cell_high": cell_high,
                "sort_key": sort_key,
                "yes_token_id": yes_token_id,
                "no_token_id": no_token_id,
                "start_time": raw_market.get("startDate") if raw_market is not None else None,
                "end_time": raw_market.get("endDate") if raw_market is not None else iso_or_none(market_row["settlement_time"]),
                "volume": as_float(market_row["volume"]),
                "liquidity": as_float(market_row["liquidity"]),
                "spread": as_float(market_row["spread"]),
                "best_bid": as_float(market_row["best_bid"]),
                "best_ask": as_float(market_row["best_ask"]),
                "yes_price_snapshot": as_float(market_row["yes_price"]),
                "qtype": market_row["qtype"],
                "direction": market_row["direction"],
                "strike_low": as_float(market_row["strike_low"]),
                "strike_high": as_float(market_row["strike_high"]),
            }
        )

    cells = pd.DataFrame(rows)
    if cells.empty:
        return cells

    cells = cells.sort_values(["event_id", "sort_key", "market_id"]).reset_index(drop=True)
    cells.insert(0, "cell_id", cells.groupby("event_id").cumcount() + 1)
    return cells


def validate_outputs(event_universe: pd.DataFrame, cells: pd.DataFrame, strict_counts: bool) -> dict[str, Any]:
    counts = {
        "event_universe_rows": int(len(event_universe)),
        "trackA_events": int(event_universe["trackA_eligible"].sum()),
        "trackB_events": int(event_universe["trackB_eligible"].sum()),
        "bucket_distribution_events": int((event_universe["event_type_for_trackB"] == "bucket_distribution").sum()),
        "point_threshold_events": int((event_universe["event_type_for_trackB"] == "point_threshold").sum()),
        "event_cells_rows": int(len(cells)),
        "missing_yes_token_id_rows": int(cells["yes_token_id"].isna().sum()) if not cells.empty else 0,
    }

    if strict_counts:
        expected = {
            "event_universe_rows": 124,
            "trackA_events": 79,
            "trackB_events": 124,
            "bucket_distribution_events": 79,
            "point_threshold_events": 45,
        }
        mismatches = {k: (counts[k], v) for k, v in expected.items() if counts[k] != v}
        if mismatches:
            raise RuntimeError(f"Unexpected P1 target counts: {mismatches}")

    if counts["missing_yes_token_id_rows"] > 0:
        raise RuntimeError(f"Missing YES token ids: {counts['missing_yes_token_id_rows']} rows")

    bucket_event_ids = event_universe.loc[
        event_universe["event_type_for_trackB"] == "bucket_distribution", "event_id"
    ].tolist()
    bucket_cells = cells[cells["event_id"].isin(bucket_event_ids)]
    bad_events: list[int] = []
    for event_id, group in bucket_cells.groupby("event_id"):
        types = set(group["cell_type"])
        if not {"left_tail", "bucket", "right_tail"}.issubset(types):
            bad_events.append(int(event_id))
            continue
        ordered = group.sort_values("sort_key")
        finite = ordered[ordered["cell_type"] == "bucket"]
        lows = finite["cell_low"].tolist()
        highs = finite["cell_high"].tolist()
        for idx in range(len(finite) - 1):
            if abs(highs[idx] - lows[idx + 1]) > 1e-6:
                bad_events.append(int(event_id))
                break
    if bad_events:
        raise RuntimeError(f"Bucket partition validation failed for event_ids={bad_events[:10]}")

    return counts


def write_outputs(event_universe: pd.DataFrame, cells: pd.DataFrame, metadata: dict[str, Any]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    event_universe_csv = PROCESSED_DIR / "event_universe.csv"
    event_universe_parquet = PROCESSED_DIR / "event_universe.parquet"
    event_cells_csv = PROCESSED_DIR / "event_cells.csv"
    event_cells_parquet = PROCESSED_DIR / "event_cells.parquet"
    metadata_json = PROCESSED_DIR / "p1_event_cells_metadata.json"

    event_universe.to_csv(event_universe_csv, index=False, encoding="utf-8-sig")
    event_universe.to_parquet(event_universe_parquet, index=False)
    cells.to_csv(event_cells_csv, index=False, encoding="utf-8-sig")
    cells.to_parquet(event_cells_parquet, index=False)
    metadata_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-strict-counts", action="store_true", help="Do not enforce the P0-frozen 79/45/124 counts.")
    args = parser.parse_args()

    event_lookup, market_lookup = load_raw_events()
    event_quality = pd.read_csv(EVENT_QUALITY)
    market_inventory = pd.read_csv(MARKET_INVENTORY)

    event_universe = build_event_universe(event_quality, market_inventory, event_lookup)
    cells = build_event_cells(event_universe, market_inventory, market_lookup)
    counts = validate_outputs(event_universe, cells, strict_counts=not args.no_strict_counts)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_p1_event_cells.py",
        "git_commit": git_commit(),
        "inputs": {
            "event_distribution_quality": str(EVENT_QUALITY.relative_to(PROJECT_ROOT)),
            "market_pair_candidate_inventory": str(MARKET_INVENTORY.relative_to(PROJECT_ROOT)),
            "polymarket_public_search_events": str(RAW_EVENTS.relative_to(PROJECT_ROOT)),
        },
        "filter_rules": {
            "target_distribution_quality": sorted(TARGET_QUALITIES),
            "mapping_quality": sorted(MAIN_MAPPING_QUALITIES),
            "trackA_eligible": "clean_bucket_distribution only",
            "trackB_eligible": "clean_bucket_distribution plus usable_point_thresholds",
        },
        "row_counts": counts,
        "known_caveats": [
            "deribit_index_reference uses Deribit public/get_index_price_names identifiers verified on 2026-07-04.",
            "settlement_reference is parsed from Polymarket event/market descriptions and should be treated as a structured diagnostic, not a legal interpretation of market rules.",
            "CSV outputs are inspection copies; parquet outputs are the canonical machine-readable inputs for later P1 steps.",
            "git_commit is null when this project directory is not a git repository.",
        ],
    }
    write_outputs(event_universe, cells, metadata)

    print("\n=== P1 event universe and cells built ===")
    for key, value in counts.items():
        print(f"{key}: {value:,}")
    print("\nOutputs:")
    print(f"- {PROCESSED_DIR / 'event_universe.parquet'}")
    print(f"- {PROCESSED_DIR / 'event_cells.parquet'}")
    print(f"- {PROCESSED_DIR / 'p1_event_cells_metadata.json'}")


if __name__ == "__main__":
    main()
