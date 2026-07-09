"""
Single-expiry Deribit strike-grid feasibility spike.

Purpose:
- Do not build the full Deribit pipeline yet.
- For one high-liquidity Polymarket clean event, construct a wide Deribit
  option strike grid and pull daily OHLC via public/get_tradingview_chart_data.
- Check whether each day has enough non-stale traded strikes to fit an IV smile.

Outputs:
- data/processed/deribit_spike/deribit_grid_ohlc_event_<event_id>.parquet
- data/processed/deribit_spike/deribit_grid_ohlc_event_<event_id>.csv
- data/processed/deribit_spike/deribit_grid_bar_quality_event_<event_id>_<resolution>.csv
- data/processed/deribit_spike/deribit_grid_spike_metadata_event_<event_id>.json
"""

from __future__ import annotations

import argparse
import json
import math
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
EVENT_QUALITY_PATH = PROJECT_ROOT / "data" / "processed" / "polymarket" / "event_distribution_quality.csv"
CANDIDATE_PATH = PROJECT_ROOT / "data" / "processed" / "polymarket" / "market_pair_candidate_inventory.csv"
OUT_DIR = PROJECT_ROOT / "data" / "processed" / "deribit_spike"

DERIBIT = "https://www.deribit.com/api/v2"
HEADERS = {"User-Agent": "ucl-dissertation-research/0.1"}


def deribit_get(method: str, params: dict[str, Any], sleep_seconds: float) -> dict[str, Any]:
    response = requests.get(f"{DERIBIT}/{method}", params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    time.sleep(sleep_seconds)
    return payload["result"]


def deribit_expiry_code(expiry: pd.Timestamp) -> str:
    dt = pd.Timestamp(expiry).to_pydatetime()
    return f"{dt.day}{dt.strftime('%b').upper()}{dt.strftime('%y')}"


def option_name(currency: str, expiry: pd.Timestamp, strike: float, option_type: str) -> str:
    suffix = "C" if option_type == "call" else "P"
    strike_text = str(int(strike)) if float(strike).is_integer() else str(strike)
    return f"{currency}-{deribit_expiry_code(expiry)}-{strike_text}-{suffix}"


def choose_event(event_id: int | None) -> tuple[pd.Series, pd.DataFrame]:
    events = pd.read_csv(EVENT_QUALITY_PATH)
    candidates = pd.read_csv(CANDIDATE_PATH)

    clean = events[
        (events["distribution_quality"] == "clean_bucket_distribution")
        & events["mapping_quality"].isin(["exact", "close"])
        & (events["asset"] == "BTC")
    ].copy()
    if clean.empty:
        raise RuntimeError("No BTC clean_bucket_distribution event found.")

    if event_id is None:
        event = clean.sort_values("total_volume", ascending=False).iloc[0]
    else:
        matched = clean[clean["event_id"] == event_id]
        if matched.empty:
            raise RuntimeError(f"event_id={event_id} is not a BTC clean_bucket_distribution event.")
        event = matched.iloc[0]

    event_markets = candidates[candidates["event_id"] == event["event_id"]].copy()
    return event, event_markets


def build_strike_grid(min_strike: float, max_strike: float, step: float, extension_steps: int) -> list[float]:
    lower = math.floor(min_strike / step) * step - extension_steps * step
    upper = math.ceil(max_strike / step) * step + extension_steps * step
    strikes = []
    value = lower
    while value <= upper + 1e-9:
        if value > 0:
            strikes.append(float(value))
        value += step
    return strikes


def fetch_chart(instrument_name: str, start: pd.Timestamp, end: pd.Timestamp, resolution: str, sleep_seconds: float) -> list[dict[str, Any]]:
    result = deribit_get(
        "public/get_tradingview_chart_data",
        {
            "instrument_name": instrument_name,
            "start_timestamp": int(start.timestamp() * 1000),
            "end_timestamp": int(end.timestamp() * 1000),
            "resolution": resolution,
        },
        sleep_seconds,
    )
    if not isinstance(result, dict):
        return []

    ticks = result.get("ticks", [])
    rows = []
    for i, tick in enumerate(ticks):
        rows.append(
            {
                "date": datetime.fromtimestamp(tick / 1000, tz=timezone.utc).date(),
                "timestamp": datetime.fromtimestamp(tick / 1000, tz=timezone.utc),
                "open": safe_idx(result.get("open", []), i),
                "high": safe_idx(result.get("high", []), i),
                "low": safe_idx(result.get("low", []), i),
                "close": safe_idx(result.get("close", []), i),
                "volume": safe_idx(result.get("volume", []), i),
                "cost": safe_idx(result.get("cost", []), i),
                "status": result.get("status"),
            }
        )
    return rows


def safe_idx(values: list[Any], index: int) -> Any:
    return values[index] if isinstance(values, list) and index < len(values) else math.nan


def build_bar_quality(ohlc: pd.DataFrame) -> pd.DataFrame:
    if ohlc.empty:
        return pd.DataFrame()

    ohlc = ohlc.copy()
    ohlc["has_trade"] = (ohlc["volume"].fillna(0) > 0) & (ohlc["close"].fillna(0) > 0)

    rows = []
    for timestamp, group in ohlc.groupby("timestamp"):
        traded = group[group["has_trade"]].copy()
        call_traded = traded[traded["option_type"] == "call"]
        put_traded = traded[traded["option_type"] == "put"]
        traded_strikes = sorted(traded["strike"].dropna().unique())
        call_strikes = sorted(call_traded["strike"].dropna().unique())
        put_strikes = sorted(put_traded["strike"].dropna().unique())

        rows.append(
            {
                "timestamp": timestamp,
                "date": pd.Timestamp(timestamp).date(),
                "n_rows": len(group),
                "n_traded_rows": len(traded),
                "n_distinct_traded_strikes": len(traded_strikes),
                "n_call_traded_strikes": len(call_strikes),
                "n_put_traded_strikes": len(put_strikes),
                "min_traded_strike": min(traded_strikes) if traded_strikes else math.nan,
                "max_traded_strike": max(traded_strikes) if traded_strikes else math.nan,
                "total_volume": traded["volume"].sum(skipna=True),
                "can_fit_min6": len(traded_strikes) >= 6,
                "can_fit_min8": len(traded_strikes) >= 8,
                "call_can_fit_min6": len(call_strikes) >= 6,
                "put_can_fit_min6": len(put_strikes) >= 6,
            }
        )
    return pd.DataFrame(rows).sort_values("date")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", type=int, default=None)
    parser.add_argument("--strike-step", type=float, default=2000.0)
    parser.add_argument("--extension-steps", type=int, default=6)
    parser.add_argument("--days-before-expiry", type=int, default=30)
    parser.add_argument("--resolution", type=str, default="1D")
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    event, event_markets = choose_event(args.event_id)
    expiry = pd.Timestamp(event["nearest_deribit_monthly_expiry"])
    start = expiry - pd.Timedelta(days=args.days_before_expiry)
    end = expiry
    currency = event["asset"]
    strikes = build_strike_grid(event["min_strike"], event["max_strike"], args.strike_step, args.extension_steps)

    rows = []
    errors = []
    for strike in strikes:
        for opt_type in ["call", "put"]:
            instrument = option_name(currency, expiry, strike, opt_type)
            try:
                chart_rows = fetch_chart(instrument, start, end, args.resolution, args.sleep_seconds)
                for row in chart_rows:
                    rows.append(
                        {
                            "event_id": int(event["event_id"]),
                            "event_title": event["event_title"],
                            "currency": currency,
                            "expiry": expiry,
                            "instrument_name": instrument,
                            "option_type": opt_type,
                            "strike": strike,
                            **row,
                        }
                    )
            except Exception as exc:  # noqa: BLE001 - feasibility spike should keep going.
                errors.append(
                    {
                        "instrument_name": instrument,
                        "option_type": opt_type,
                        "strike": strike,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    ohlc = pd.DataFrame(rows)
    bar_quality = build_bar_quality(ohlc)
    errors_df = pd.DataFrame(errors)

    event_id = int(event["event_id"])
    resolution_label = str(args.resolution).replace("/", "_")
    ohlc_csv = OUT_DIR / f"deribit_grid_ohlc_event_{event_id}_{resolution_label}.csv"
    ohlc_parquet = OUT_DIR / f"deribit_grid_ohlc_event_{event_id}_{resolution_label}.parquet"
    quality_csv = OUT_DIR / f"deribit_grid_bar_quality_event_{event_id}_{resolution_label}.csv"
    errors_csv = OUT_DIR / f"deribit_grid_errors_event_{event_id}_{resolution_label}.csv"
    metadata_json = OUT_DIR / f"deribit_grid_spike_metadata_event_{event_id}_{resolution_label}.json"

    ohlc.to_csv(ohlc_csv, index=False, encoding="utf-8-sig")
    if not ohlc.empty:
        ohlc.to_parquet(ohlc_parquet, index=False)
    bar_quality.to_csv(quality_csv, index=False, encoding="utf-8-sig")
    errors_df.to_csv(errors_csv, index=False, encoding="utf-8-sig")

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_id": event_id,
        "event_title": event["event_title"],
        "currency": currency,
        "polymarket_settlement_time": event["settlement_time"],
        "nearest_deribit_expiry": str(expiry),
        "time_gap_hours": float(event["time_gap_hours"]),
        "polymarket_min_strike": float(event["min_strike"]),
        "polymarket_max_strike": float(event["max_strike"]),
        "strike_step": args.strike_step,
        "extension_steps": args.extension_steps,
        "strike_count": len(strikes),
        "instrument_count": len(strikes) * 2,
        "ohlc_rows": len(ohlc),
        "error_count": len(errors_df),
        "bar_quality_rows": len(bar_quality),
        "bars_can_fit_min6": int(bar_quality["can_fit_min6"].sum()) if not bar_quality.empty else 0,
        "bars_can_fit_min8": int(bar_quality["can_fit_min8"].sum()) if not bar_quality.empty else 0,
        "polymarket_markets": event_markets[
            ["question", "qtype", "direction", "strike_low", "strike_high", "bucket_width", "volume"]
        ].to_dict("records"),
    }
    metadata_json.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== Deribit single-expiry grid spike ===")
    print(f"event: {event_id} | {event['event_title']}")
    print(f"expiry: {expiry}")
    print(f"strike grid: {min(strikes):,.0f} to {max(strikes):,.0f}, n={len(strikes)}")
    print(f"instruments attempted: {len(strikes) * 2}")
    print(f"chart rows: {len(ohlc):,}")
    print(f"errors: {len(errors_df):,}")
    if not bar_quality.empty:
        print("\n=== bar fit coverage ===")
        print(bar_quality[["timestamp", "n_distinct_traded_strikes", "n_call_traded_strikes", "n_put_traded_strikes", "total_volume", "can_fit_min6", "can_fit_min8"]].to_string(index=False))
        print("\nSummary:")
        print(bar_quality[["n_distinct_traded_strikes", "n_call_traded_strikes", "n_put_traded_strikes", "total_volume"]].describe().to_string())
    print("\nOutputs:")
    print(f"- {ohlc_csv}")
    print(f"- {quality_csv}")
    print(f"- {errors_csv}")
    print(f"- {metadata_json}")


if __name__ == "__main__":
    main()
