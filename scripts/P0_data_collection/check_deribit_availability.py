"""
Probe Deribit public API availability for the Polymarket-aligned monthly events.

This is a feasibility gate, not the final Deribit data pipeline. It checks:
- current/expired option instrument metadata availability;
- whether Polymarket target monthly expiries are present in Deribit instruments;
- strike coverage by currency and expiry;
- whether public mark-price history returns non-empty data for sample options.

Outputs:
- data/processed/deribit/deribit_instrument_expiry_summary.csv
- data/processed/deribit/deribit_polymarket_expiry_match.csv
- data/processed/deribit/deribit_mark_history_probe.csv
- data/processed/deribit/deribit_chart_history_probe.csv
- data/processed/deribit/deribit_availability_metadata.json
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
POLY_EVENT_QUALITY = PROJECT_ROOT / "data" / "processed" / "polymarket" / "event_distribution_quality.csv"
OUT_DIR = PROJECT_ROOT / "data" / "processed" / "deribit"

DERIBIT = "https://www.deribit.com/api/v2"
HEADERS = {"User-Agent": "ucl-dissertation-research/0.1"}


def deribit_get(method: str, params: dict[str, Any], sleep_seconds: float) -> dict[str, Any]:
    url = f"{DERIBIT}/{method}"
    response = requests.get(url, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Deribit error for {method}: {payload['error']}")
    time.sleep(sleep_seconds)
    return payload["result"]


def fetch_instruments(currency: str, expired: bool, sleep_seconds: float) -> pd.DataFrame:
    result = deribit_get(
        "public/get_instruments",
        {"currency": currency, "kind": "option", "expired": str(expired).lower()},
        sleep_seconds,
    )
    rows = []
    for item in result:
        rows.append(
            {
                "currency": currency,
                "instrument_name": item.get("instrument_name"),
                "kind": item.get("kind"),
                "option_type": item.get("option_type"),
                "strike": item.get("strike"),
                "expiration_timestamp": item.get("expiration_timestamp"),
                "expiration_time": datetime.fromtimestamp(
                    item["expiration_timestamp"] / 1000, tz=timezone.utc
                )
                if item.get("expiration_timestamp")
                else None,
                "is_active": item.get("is_active"),
                "expired_query": expired,
            }
        )
    return pd.DataFrame(rows)


def load_polymarket_target_events() -> pd.DataFrame:
    events = pd.read_csv(POLY_EVENT_QUALITY)
    events["nearest_deribit_monthly_expiry"] = pd.to_datetime(
        events["nearest_deribit_monthly_expiry"], errors="coerce", utc=True
    )
    keep = events[
        events["distribution_quality"].isin(["clean_bucket_distribution", "usable_point_thresholds"])
        & events["mapping_quality"].isin(["exact", "close"])
    ].copy()
    return keep


def summarize_instruments(instruments: pd.DataFrame) -> pd.DataFrame:
    if instruments.empty:
        return pd.DataFrame()
    return (
        instruments.groupby(["currency", "expiration_time"], dropna=False)
        .agg(
            n_instruments=("instrument_name", "count"),
            n_calls=("option_type", lambda s: int((s == "call").sum())),
            n_puts=("option_type", lambda s: int((s == "put").sum())),
            min_strike=("strike", "min"),
            max_strike=("strike", "max"),
            n_strikes=("strike", "nunique"),
            any_active=("is_active", "any"),
            from_expired_query=("expired_query", "any"),
        )
        .reset_index()
        .sort_values(["currency", "expiration_time"])
    )


def match_polymarket_expiries(events: pd.DataFrame, expiry_summary: pd.DataFrame) -> pd.DataFrame:
    targets = (
        events.groupby(["asset", "nearest_deribit_monthly_expiry"], dropna=False)
        .agg(
            n_poly_events=("event_id", "count"),
            n_clean_bucket=("distribution_quality", lambda s: int((s == "clean_bucket_distribution").sum())),
            n_usable_point=("distribution_quality", lambda s: int((s == "usable_point_thresholds").sum())),
            min_poly_strike=("min_strike", "min"),
            max_poly_strike=("max_strike", "max"),
            total_poly_volume=("total_volume", "sum"),
        )
        .reset_index()
        .rename(columns={"asset": "currency", "nearest_deribit_monthly_expiry": "target_expiry"})
    )

    summary = expiry_summary.rename(columns={"expiration_time": "target_expiry"})
    merged = targets.merge(summary, on=["currency", "target_expiry"], how="left")
    merged["has_deribit_instruments"] = merged["n_instruments"].notna()
    merged["strike_floor_covered"] = merged["min_strike"] <= merged["min_poly_strike"]
    merged["strike_ceiling_covered"] = merged["max_strike"] >= merged["max_poly_strike"]
    merged["poly_strike_range_covered"] = merged["strike_floor_covered"] & merged["strike_ceiling_covered"]
    return merged.sort_values(["currency", "target_expiry"])


def choose_probe_instruments(events: pd.DataFrame, instruments: pd.DataFrame, max_probes: int) -> pd.DataFrame:
    rows = []
    targets = events.sort_values("total_volume", ascending=False)
    for _, event in targets.iterrows():
        currency = event["asset"]
        expiry = event["nearest_deribit_monthly_expiry"]
        expiry_instruments = instruments[
            (instruments["currency"] == currency) & (instruments["expiration_time"] == expiry)
        ].copy()
        if expiry_instruments.empty:
            continue
        mid_strike = (float(event["min_strike"]) + float(event["max_strike"])) / 2
        expiry_instruments["distance_to_mid_poly_strike"] = (expiry_instruments["strike"] - mid_strike).abs()
        sample = expiry_instruments.sort_values(["distance_to_mid_poly_strike", "option_type"]).head(2)
        for _, instrument in sample.iterrows():
            rows.append(
                {
                    "event_id": event["event_id"],
                    "event_title": event["event_title"],
                    "currency": currency,
                    "target_expiry": expiry,
                    "instrument_name": instrument["instrument_name"],
                    "option_type": instrument["option_type"],
                    "strike": instrument["strike"],
                    "poly_min_strike": event["min_strike"],
                    "poly_max_strike": event["max_strike"],
                }
            )
        if len(rows) >= max_probes:
            break
    return pd.DataFrame(rows[:max_probes])


def mark_price_history_probe(probes: pd.DataFrame, sleep_seconds: float) -> pd.DataFrame:
    rows = []
    for _, probe in probes.iterrows():
        expiry = pd.Timestamp(probe["target_expiry"]).to_pydatetime()
        start = expiry - pd.Timedelta(days=30)
        end = expiry
        try:
            result = deribit_get(
                "public/get_mark_price_history",
                {
                    "instrument_name": probe["instrument_name"],
                    "start_timestamp": int(start.timestamp() * 1000),
                    "end_timestamp": int(end.timestamp() * 1000),
                },
                sleep_seconds,
            )
            if isinstance(result, dict):
                n_points = len(result.get("timestamps", []) or result.get("data", []) or [])
                keys = ",".join(sorted(result.keys()))
            elif isinstance(result, list):
                n_points = len(result)
                keys = "list"
            else:
                n_points = 0
                keys = type(result).__name__
            error = None
        except Exception as exc:  # noqa: BLE001 - this is a feasibility probe.
            n_points = 0
            keys = None
            error = f"{type(exc).__name__}: {exc}"

        rows.append(
            {
                **probe.to_dict(),
                "probe_start": start,
                "probe_end": end,
                "mark_history_points": n_points,
                "result_keys": keys,
                "error": error,
            }
        )
    return pd.DataFrame(rows)


def deribit_expiry_code(expiry: pd.Timestamp) -> str:
    dt = pd.Timestamp(expiry).to_pydatetime()
    return f"{dt.day}{dt.strftime('%b').upper()}{dt.strftime('%y')}"


def format_strike(strike: float) -> str:
    value = float(strike)
    if value.is_integer():
        return str(int(value))
    return f"{value:.8f}".rstrip("0").rstrip(".")


def deribit_option_name(currency: str, expiry: pd.Timestamp, strike: float, option_type: str) -> str:
    suffix = "C" if option_type == "call" else "P"
    return f"{currency}-{deribit_expiry_code(expiry)}-{format_strike(strike)}-{suffix}"


def choose_chart_probes(expiry_match: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, target in expiry_match.iterrows():
        currency = target["currency"]
        expiry = pd.Timestamp(target["target_expiry"])
        min_strike = float(target["min_poly_strike"])
        max_strike = float(target["max_poly_strike"])
        midpoint = (min_strike + max_strike) / 2
        strikes = [min_strike, midpoint, max_strike]
        for strike_role, strike in zip(["poly_min", "poly_mid", "poly_max"], strikes):
            for option_type in ["call", "put"]:
                rows.append(
                    {
                        "currency": currency,
                        "target_expiry": expiry,
                        "strike_role": strike_role,
                        "strike": strike,
                        "option_type": option_type,
                        "instrument_name": deribit_option_name(currency, expiry, strike, option_type),
                        "n_poly_events": target["n_poly_events"],
                        "min_poly_strike": min_strike,
                        "max_poly_strike": max_strike,
                    }
                )
    return pd.DataFrame(rows)


def chart_history_probe(probes: pd.DataFrame, sleep_seconds: float) -> pd.DataFrame:
    rows = []
    for _, probe in probes.iterrows():
        expiry = pd.Timestamp(probe["target_expiry"]).to_pydatetime()
        start = expiry - pd.Timedelta(days=30)
        end = expiry
        try:
            result = deribit_get(
                "public/get_tradingview_chart_data",
                {
                    "instrument_name": probe["instrument_name"],
                    "start_timestamp": int(start.timestamp() * 1000),
                    "end_timestamp": int(end.timestamp() * 1000),
                    "resolution": "1D",
                },
                sleep_seconds,
            )
            closes = result.get("close", []) if isinstance(result, dict) else []
            volumes = result.get("volume", []) if isinstance(result, dict) else []
            ticks = result.get("ticks", []) if isinstance(result, dict) else []
            numeric_volumes = [v for v in volumes if isinstance(v, (int, float))]
            n_points = len(closes)
            volume_sum = float(sum(numeric_volumes)) if numeric_volumes else 0.0
            nonzero_volume_days = int(sum(v > 0 for v in numeric_volumes))
            first_close = closes[0] if closes else math.nan
            last_close = closes[-1] if closes else math.nan
            status = result.get("status") if isinstance(result, dict) else None
            error = None
            has_chart_data = n_points > 0
        except Exception as exc:  # noqa: BLE001 - this is a feasibility probe.
            n_points = 0
            volume_sum = 0.0
            nonzero_volume_days = 0
            first_close = math.nan
            last_close = math.nan
            status = None
            error = f"{type(exc).__name__}: {exc}"
            has_chart_data = False
            ticks = []

        rows.append(
            {
                **probe.to_dict(),
                "probe_start": start,
                "probe_end": end,
                "chart_status": status,
                "chart_points": n_points,
                "first_tick": datetime.fromtimestamp(ticks[0] / 1000, tz=timezone.utc) if ticks else None,
                "last_tick": datetime.fromtimestamp(ticks[-1] / 1000, tz=timezone.utc) if ticks else None,
                "volume_sum": volume_sum,
                "nonzero_volume_days": nonzero_volume_days,
                "first_close": first_close,
                "last_close": last_close,
                "has_chart_data": has_chart_data,
                "error": error,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--max-probes", type=int, default=12)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    events = load_polymarket_target_events()
    instrument_frames = []
    for currency in ["BTC", "ETH"]:
        for expired in [False, True]:
            instrument_frames.append(fetch_instruments(currency, expired, args.sleep_seconds))
    instruments = pd.concat(instrument_frames, ignore_index=True)

    expiry_summary = summarize_instruments(instruments)
    expiry_match = match_polymarket_expiries(events, expiry_summary)
    probes = choose_probe_instruments(events, instruments, args.max_probes)
    mark_probe = mark_price_history_probe(probes, args.sleep_seconds) if not probes.empty else pd.DataFrame()
    chart_probes = choose_chart_probes(expiry_match)
    chart_probe = chart_history_probe(chart_probes, args.sleep_seconds) if not chart_probes.empty else pd.DataFrame()

    expiry_summary.to_csv(OUT_DIR / "deribit_instrument_expiry_summary.csv", index=False, encoding="utf-8-sig")
    expiry_match.to_csv(OUT_DIR / "deribit_polymarket_expiry_match.csv", index=False, encoding="utf-8-sig")
    mark_probe.to_csv(OUT_DIR / "deribit_mark_history_probe.csv", index=False, encoding="utf-8-sig")
    chart_probe.to_csv(OUT_DIR / "deribit_chart_history_probe.csv", index=False, encoding="utf-8-sig")

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "deribit_api_base": DERIBIT,
        "polymarket_event_quality_source": str(POLY_EVENT_QUALITY),
        "target_event_rows": len(events),
        "instrument_rows": len(instruments),
        "expiry_summary_rows": len(expiry_summary),
        "expiry_match_rows": len(expiry_match),
        "mark_history_probe_rows": len(mark_probe),
        "chart_history_probe_rows": len(chart_probe),
        "chart_history_has_data_rows": int(chart_probe["has_chart_data"].sum()) if not chart_probe.empty else 0,
        "notes": [
            "get_instruments was queried for current and expired option instruments.",
            "mark history probes use public/get_mark_price_history for the 30 days before expiry.",
            "chart history probes construct expired option names and use public/get_tradingview_chart_data for the 30 days before expiry.",
            "A non-empty instrument match does not by itself prove historical chain snapshots are available.",
        ],
    }
    (OUT_DIR / "deribit_availability_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Deribit availability probe ===")
    print(f"target Polymarket events: {len(events):,}")
    print(f"Deribit option instruments: {len(instruments):,}")
    print("\n=== target expiry match ===")
    print(expiry_match["has_deribit_instruments"].value_counts(dropna=False).to_string())
    if "poly_strike_range_covered" in expiry_match:
        print("\n=== strike range covered among matched expiries ===")
        print(expiry_match["poly_strike_range_covered"].value_counts(dropna=False).to_string())
    print("\n=== mark history probe ===")
    if mark_probe.empty:
        print("No probe instruments found.")
    else:
        print(mark_probe[["instrument_name", "mark_history_points", "error"]].to_string(index=False))
    print("\n=== chart history probe ===")
    if chart_probe.empty:
        print("No chart probes found.")
    else:
        print(chart_probe["has_chart_data"].value_counts(dropna=False).to_string())
        print(chart_probe[["instrument_name", "chart_points", "volume_sum", "error"]].head(20).to_string(index=False))
    print("\nOutputs:")
    print(f"- {OUT_DIR / 'deribit_instrument_expiry_summary.csv'}")
    print(f"- {OUT_DIR / 'deribit_polymarket_expiry_match.csv'}")
    print(f"- {OUT_DIR / 'deribit_mark_history_probe.csv'}")
    print(f"- {OUT_DIR / 'deribit_chart_history_probe.csv'}")


if __name__ == "__main__":
    main()
