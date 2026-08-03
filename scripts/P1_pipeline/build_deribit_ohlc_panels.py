"""
Download Deribit option OHLC grids and build bar-quality diagnostics.

Inputs:
- data/processed/polymarket/event_universe.parquet
- data/processed/polymarket/polymarket_quality_diagnostics.parquet

Outputs:
- data/raw/deribit/ohlc_<event_id>_<resolution>.parquet
- data/raw/deribit/ohlc_<event_id>_<resolution>_errors.csv
- data/processed/deribit/deribit_bar_quality[_<resolution>].{csv,parquet}
- data/processed/deribit/deribit_ohlc_metadata[_<resolution>].json
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
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "deribit"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "deribit"
POLY_DIR = PROJECT_ROOT / "data" / "processed" / "polymarket"

EVENT_UNIVERSE = POLY_DIR / "event_universe.parquet"
PM_QUALITY = POLY_DIR / "polymarket_quality_diagnostics.parquet"

DERIBIT = "https://www.deribit.com/api/v2"
HEADERS = {"User-Agent": "ucl-dissertation-research/0.4"}


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


def deribit_get(session: requests.Session, method: str, params: dict[str, Any], timeout: int) -> dict[str, Any]:
    response = session.get(f"{DERIBIT}/{method}", params=params, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(f"Deribit error for {method}: {payload['error']}")
    return payload["result"]


def deribit_expiry_code(expiry: pd.Timestamp) -> str:
    dt = pd.Timestamp(expiry).to_pydatetime()
    return f"{dt.day}{dt.strftime('%b').upper()}{dt.strftime('%y')}"


def format_strike(strike: float) -> str:
    value = float(strike)
    if value.is_integer():
        return str(int(value))
    return f"{value:.8f}".rstrip("0").rstrip(".")


def option_name(currency: str, expiry: pd.Timestamp, strike: float, option_type: str) -> str:
    suffix = "C" if option_type == "call" else "P"
    return f"{currency}-{deribit_expiry_code(expiry)}-{format_strike(strike)}-{suffix}"


def safe_idx(values: list[Any], index: int) -> Any:
    return values[index] if isinstance(values, list) and index < len(values) else math.nan


def grid_step(asset: str, median_bucket_width: float) -> float:
    if not math.isnan(median_bucket_width) and median_bucket_width > 0:
        return float(median_bucket_width)
    return 2000.0 if asset == "BTC" else 100.0


def strike_grid(min_strike: float, max_strike: float, step: float, extension_steps: int) -> list[float]:
    lower = math.floor(min_strike / step) * step - extension_steps * step
    upper = math.ceil(max_strike / step) * step + extension_steps * step
    values = []
    current = lower
    while current <= upper + 1e-9:
        if current > 0:
            values.append(float(current))
        current += step
    return values


def fetch_chart(
    session: requests.Session,
    instrument_name: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    resolution: str,
    timeout: int,
) -> list[dict[str, Any]]:
    result = deribit_get(
        session,
        "public/get_tradingview_chart_data",
        {
            "instrument_name": instrument_name,
            "start_timestamp": int(start.timestamp() * 1000),
            "end_timestamp": int(end.timestamp() * 1000),
            "resolution": resolution,
        },
        timeout,
    )
    if not isinstance(result, dict):
        return []

    rows = []
    ticks = result.get("ticks", [])
    for idx, tick in enumerate(ticks):
        rows.append(
            {
                "timestamp": datetime.fromtimestamp(tick / 1000, tz=timezone.utc),
                "open": safe_idx(result.get("open", []), idx),
                "high": safe_idx(result.get("high", []), idx),
                "low": safe_idx(result.get("low", []), idx),
                "close": safe_idx(result.get("close", []), idx),
                "volume": safe_idx(result.get("volume", []), idx),
                "cost": safe_idx(result.get("cost", []), idx),
                "status": result.get("status"),
            }
        )
    return rows


def raw_ohlc_path(event_id: int, resolution: str) -> Path:
    label = str(resolution).replace("/", "_")
    return RAW_DIR / f"ohlc_{event_id}_{label}.parquet"


def raw_error_path(event_id: int, resolution: str) -> Path:
    label = str(resolution).replace("/", "_")
    return RAW_DIR / f"ohlc_{event_id}_{label}_errors.csv"


def resolution_label(resolution: str) -> str:
    return str(resolution).replace("/", "_")


def processed_stem(base: str, resolution: str) -> str:
    label = resolution_label(resolution)
    return base if label == "1D" else f"{base}_{label}"


def read_error_file(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def event_window(event: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = parse_utc(event["event_start_time"]).floor("D")
    expiry = parse_utc(event["nearest_deribit_expiry"])
    end = expiry
    return start, end


def download_event_ohlc(
    event: pd.Series,
    resolution: str,
    extension_steps: int,
    sleep_seconds: float,
    timeout: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    event_id = int(event["event_id"])
    currency = str(event["asset"])
    expiry = parse_utc(event["nearest_deribit_expiry"])
    start, end = event_window(event)
    step = grid_step(currency, float(event["median_bucket_width"]))
    strikes = strike_grid(float(event["min_strike"]), float(event["max_strike"]), step, extension_steps)

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    session = requests.Session()

    for strike in strikes:
        for option_type in ["call", "put"]:
            instrument = option_name(currency, expiry, strike, option_type)
            try:
                chart_rows = fetch_chart(session, instrument, start, end, resolution, timeout)
                for row in chart_rows:
                    rows.append(
                        {
                            "event_id": event_id,
                            "currency": currency,
                            "expiry": expiry,
                            "instrument_name": instrument,
                            "option_type": option_type,
                            "strike": strike,
                            "target_snapshot_timestamp": pd.NaT,
                            "trade_timestamp_used": row["timestamp"],
                            "minutes_from_target_snapshot": math.nan,
                            "time_since_last_trade_minutes": math.nan,
                            "bar_stale_flag": False,
                            **row,
                        }
                    )
            except Exception as exc:  # noqa: BLE001 - record failed instruments explicitly.
                errors.append(
                    {
                        "event_id": event_id,
                        "instrument_name": instrument,
                        "option_type": option_type,
                        "strike": strike,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
            time.sleep(sleep_seconds)

    ohlc = pd.DataFrame(rows)
    errors_df = pd.DataFrame(errors)
    if not ohlc.empty:
        ohlc["has_real_trade"] = (ohlc["volume"].fillna(0) > 0) & (ohlc["close"].fillna(0) > 0)
        ohlc = ohlc.sort_values(["event_id", "timestamp", "strike", "option_type"]).reset_index(drop=True)

    stats = {
        "event_id": event_id,
        "currency": currency,
        "resolution": resolution,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "expiry": expiry.isoformat(),
        "strike_step": step,
        "strike_count": len(strikes),
        "instrument_count": len(strikes) * 2,
        "ohlc_rows": int(len(ohlc)),
        "error_count": int(len(errors_df)),
    }
    return ohlc, errors_df, stats


def load_or_download_event(
    event: pd.Series,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    event_id = int(event["event_id"])
    ohlc_path = raw_ohlc_path(event_id, args.resolution)
    errors_path = raw_error_path(event_id, args.resolution)

    if ohlc_path.exists() and not args.force_download:
        ohlc = pd.read_parquet(ohlc_path)
        errors = read_error_file(errors_path)
        source = "cached"
        stats = {
            "event_id": event_id,
            "currency": str(event["asset"]),
            "resolution": args.resolution,
            "ohlc_rows": int(len(ohlc)),
            "error_count": int(len(errors)),
        }
    else:
        ohlc, errors, stats = download_event_ohlc(
            event,
            args.resolution,
            args.extension_steps,
            args.sleep_seconds,
            args.timeout,
        )
        ohlc.to_parquet(ohlc_path, index=False)
        errors.to_csv(errors_path, index=False, encoding="utf-8-sig")
        source = "downloaded"

    stats["source"] = source
    stats["raw_ohlc_path"] = str(ohlc_path.relative_to(PROJECT_ROOT))
    stats["raw_error_path"] = str(errors_path.relative_to(PROJECT_ROOT))
    print(f"event_id={event_id} source={source} rows={len(ohlc):,} errors={len(errors):,}")
    return ohlc, errors, stats


def build_bar_quality(ohlc: pd.DataFrame, event_universe: pd.DataFrame) -> pd.DataFrame:
    if ohlc.empty:
        return pd.DataFrame()

    event_meta = event_universe.set_index("event_id")
    rows: list[dict[str, Any]] = []
    for (event_id, timestamp), group in ohlc.groupby(["event_id", "timestamp"]):
        traded = group[group["has_real_trade"]].copy()
        calls = traded[traded["option_type"] == "call"]
        puts = traded[traded["option_type"] == "put"]
        traded_strikes = sorted(traded["strike"].dropna().unique())
        call_strikes = sorted(calls["strike"].dropna().unique())
        put_strikes = sorted(puts["strike"].dropna().unique())
        meta = event_meta.loc[int(event_id)]
        poly_mid = (float(meta["min_strike"]) + float(meta["max_strike"])) / 2
        step = grid_step(str(meta["asset"]), float(meta["median_bucket_width"]))
        local_lower = poly_mid - step
        local_upper = poly_mid + step
        local = traded[traded["strike"].between(local_lower, local_upper)]

        rows.append(
            {
                "event_id": int(event_id),
                "timestamp": timestamp,
                "date": pd.Timestamp(timestamp).date().isoformat(),
                "currency": meta["asset"],
                "expiry": meta["nearest_deribit_expiry"],
                "n_rows": int(len(group)),
                "n_traded_rows": int(len(traded)),
                "n_distinct_traded_strikes": int(len(traded_strikes)),
                "n_call_traded_strikes": int(len(call_strikes)),
                "n_put_traded_strikes": int(len(put_strikes)),
                "min_traded_strike": min(traded_strikes) if traded_strikes else math.nan,
                "max_traded_strike": max(traded_strikes) if traded_strikes else math.nan,
                "total_volume": float(traded["volume"].sum(skipna=True)),
                "can_fit_full_curve_min6": len(traded_strikes) >= 6,
                "can_fit_full_curve_min8": len(traded_strikes) >= 8,
                "atm_local_coverage": bool(local["strike"].nunique() >= 2),
                "curve_target_timestamp": timestamp,
                "intraday_trade_time_diagnostics_available": False,
                "cross_strike_trade_time_min": pd.NaT,
                "cross_strike_trade_time_max": pd.NaT,
                "cross_strike_trade_time_spread_minutes": math.nan,
                "max_abs_minutes_from_target_snapshot": math.nan,
                "median_time_since_last_trade_minutes": math.nan,
                "stale_bar_share": float(1.0 - group["has_real_trade"].mean()) if len(group) else math.nan,
                "both_sides_real_update_candidate": bool(len(call_strikes) > 0 and len(put_strikes) > 0),
            }
        )
    return pd.DataFrame(rows).sort_values(["event_id", "timestamp"]).reset_index(drop=True)


def select_events(event_universe: pd.DataFrame, pm_quality: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    events = event_universe[event_universe["trackA_eligible"]].copy()
    if args.pm_main_only:
        main_ids = set(pm_quality.loc[pm_quality["pm_trackA_main_candidate"], "event_id"].astype(int))
        events = events[events["event_id"].astype(int).isin(main_ids)].copy()
    if args.event_id is not None:
        events = events[events["event_id"].astype(int) == args.event_id].copy()
    events = events.sort_values(["event_id"])
    if args.max_events is not None:
        events = events.head(args.max_events)
    if events.empty:
        raise RuntimeError("No Deribit events selected.")
    return events.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", type=int, default=None)
    parser.add_argument("--max-events", type=int, default=None)
    parser.add_argument("--resolution", type=str, default="1D")
    parser.add_argument("--extension-steps", type=int, default=6)
    parser.add_argument("--pm-main-only", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    event_universe = pd.read_parquet(EVENT_UNIVERSE)
    pm_quality = pd.read_parquet(PM_QUALITY)
    events = select_events(event_universe, pm_quality, args)

    ohlc_frames: list[pd.DataFrame] = []
    event_stats: list[dict[str, Any]] = []
    for _, event in events.iterrows():
        ohlc, _errors, stats = load_or_download_event(event, args)
        ohlc_frames.append(ohlc)
        event_stats.append(stats)

    all_ohlc = pd.concat(ohlc_frames, ignore_index=True) if ohlc_frames else pd.DataFrame()
    quality = build_bar_quality(all_ohlc, event_universe)
    quality_stem = processed_stem("deribit_bar_quality", args.resolution)
    metadata_stem = processed_stem("deribit_ohlc_metadata", args.resolution)
    quality_csv = PROCESSED_DIR / f"{quality_stem}.csv"
    quality_parquet = PROCESSED_DIR / f"{quality_stem}.parquet"
    quality.to_csv(quality_csv, index=False, encoding="utf-8-sig")
    quality.to_parquet(quality_parquet, index=False)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_endpoint": f"{DERIBIT}/public/get_tradingview_chart_data",
        "script_name": "scripts/P1_pipeline/build_deribit_ohlc_panels.py",
        "git_commit": git_commit(),
        "resolution": args.resolution,
        "event_filter": {
            "trackA_eligible": True,
            "pm_main_only": bool(args.pm_main_only),
            "event_id": args.event_id,
            "max_events": args.max_events,
        },
        "row_counts": {
            "selected_events": int(len(events)),
            "ohlc_rows_loaded": int(len(all_ohlc)),
            "bar_quality_rows": int(len(quality)),
            "bar_quality_event_count": int(quality["event_id"].nunique()) if not quality.empty else 0,
        },
        "event_stats": event_stats,
        "known_caveats": [
            "Daily bars identify whether an instrument traded within the daily candle; exact cross-strike trade-time spread is unavailable from daily OHLC alone.",
            "intraday_trade_time_diagnostics_available is false for the 1D panel; cross_strike_trade_time_* and target-distance fields are intentionally null.",
            "atm_local_coverage is a coarse midpoint-local strike coverage proxy until K* selection is implemented.",
            "Failed constructed instruments are saved explicitly in per-event error CSV files.",
        ],
    }
    metadata_path = PROCESSED_DIR / f"{metadata_stem}.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Deribit OHLC panels built ===")
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value:,}")
    if not quality.empty:
        coverage = quality.groupby("event_id").agg(
            days=("timestamp", "count"),
            min6_share=("can_fit_full_curve_min6", "mean"),
            min8_share=("can_fit_full_curve_min8", "mean"),
            median_traded_strikes=("n_distinct_traded_strikes", "median"),
            total_volume=("total_volume", "sum"),
        )
        print("\nDaily curve coverage by event:")
        print(coverage.to_string())
    print("\nOutputs:")
    print(f"- {quality_parquet}")
    print(f"- {metadata_path}")


if __name__ == "__main__":
    main()
