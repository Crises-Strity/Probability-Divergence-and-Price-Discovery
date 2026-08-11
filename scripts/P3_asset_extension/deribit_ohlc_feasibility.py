"""Historical SOL option OHLC feasibility helpers for P3."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from scripts.P3_asset_extension.deribit_feasibility import deribit_option_name


DERIBIT_CHART = "https://www.deribit.com/api/v2/public/get_tradingview_chart_data"
HEADERS = {"User-Agent": "ucl-dissertation-research/0.4"}


def _parse_utc(value: Any) -> pd.Timestamp:
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        raise ValueError(f"Could not parse UTC timestamp: {value}")
    return timestamp


def select_smoke_event_ids(matches: pd.DataFrame, sample_size: int = 3) -> tuple[str, ...]:
    if sample_size < 1:
        raise ValueError("sample_size must be positive.")
    exact = matches[matches["mapping_quality"].eq("exact")].copy()
    exact["deribit_expiry_timestamp"] = pd.to_datetime(exact["deribit_expiry_timestamp"], utc=True)
    exact = exact.sort_values(["deribit_expiry_timestamp", "event_id"]).reset_index(drop=True)
    if len(exact) < sample_size:
        raise ValueError(f"Need {sample_size} exact expiry matches; found {len(exact)}.")
    if sample_size == 1:
        positions = [0]
    else:
        positions = [round(index * (len(exact) - 1) / (sample_size - 1)) for index in range(sample_size)]
    return tuple(exact.iloc[position]["event_id"].__str__() for position in positions)


def _finite_cell_bounds(cells: pd.DataFrame) -> list[float]:
    values = pd.concat([cells["cell_low"], cells["cell_high"]], ignore_index=True)
    return sorted(set(float(value) for value in values if pd.notna(value) and math.isfinite(float(value))))


def build_event_probe_grid(
    event: pd.Series,
    cells: pd.DataFrame,
    match: pd.Series,
    extension_steps: int = 6,
) -> pd.DataFrame:
    if extension_steps < 0:
        raise ValueError("extension_steps cannot be negative.")
    bounds = _finite_cell_bounds(cells)
    if len(bounds) < 2:
        raise ValueError("At least two finite cell bounds are required.")
    step = float(event["finite_bucket_width"])
    if not math.isfinite(step) or step <= 0:
        raise ValueError("finite_bucket_width must be positive and finite.")

    lower = math.floor(min(bounds) / step) * step - extension_steps * step
    upper = math.ceil(max(bounds) / step) * step + extension_steps * step
    strikes: list[float] = []
    strike = lower
    while strike <= upper + 1e-9:
        if strike > 0:
            strikes.append(float(strike))
        strike += step

    start = _parse_utc(event["event_start_time"])
    expiry = _parse_utc(match["deribit_expiry_timestamp"])
    rows = []
    for strike in strikes:
        for option_type in ("call", "put"):
            rows.append(
                {
                    "event_id": str(event["event_id"]),
                    "mapping_quality": str(match["mapping_quality"]),
                    "start_timestamp": start,
                    "end_timestamp": expiry,
                    "expiry_timestamp": expiry,
                    "strike": strike,
                    "option_type": option_type,
                    "instrument_name": deribit_option_name(expiry.date(), strike, option_type),
                }
            )
    return pd.DataFrame(rows)


def build_probe_grid(
    events: pd.DataFrame,
    cells: pd.DataFrame,
    matches: pd.DataFrame,
    event_ids: tuple[str, ...],
    extension_steps: int = 6,
) -> pd.DataFrame:
    event_keys = events["event_id"].astype(str)
    match_keys = matches["event_id"].astype(str)
    cell_keys = cells["event_id"].astype(str)
    frames = []
    for event_id in event_ids:
        event_rows = events[event_keys.eq(str(event_id))]
        match_rows = matches[match_keys.eq(str(event_id))]
        event_cells = cells[cell_keys.eq(str(event_id))]
        if len(event_rows) != 1 or len(match_rows) != 1 or event_cells.empty:
            raise ValueError(f"Incomplete or duplicate P3 inputs for event_id={event_id}.")
        frames.append(
            build_event_probe_grid(
                event_rows.iloc[0],
                event_cells,
                match_rows.iloc[0],
                extension_steps=extension_steps,
            )
        )
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def probe_cache_key(
    grid: pd.DataFrame,
    resolution: str,
    max_instruments: int | None,
) -> str:
    selected = grid if max_instruments is None else grid.head(max_instruments)
    columns = [
        "event_id",
        "instrument_name",
        "strike",
        "option_type",
        "start_timestamp",
        "end_timestamp",
        "expiry_timestamp",
        "mapping_quality",
    ]
    records = []
    for row in selected[columns].sort_values(["event_id", "instrument_name"]).to_dict("records"):
        for timestamp_column in ("start_timestamp", "end_timestamp", "expiry_timestamp"):
            row[timestamp_column] = _parse_utc(row[timestamp_column]).isoformat()
        records.append(row)
    payload = {
        "cache_schema_version": 1,
        "resolution": resolution,
        "max_instruments": max_instruments,
        "grid": records,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_bar_quality(
    ohlc: pd.DataFrame,
    minimum_fresh_strikes: int,
    maximum_stale_bar_share: float,
) -> pd.DataFrame:
    if ohlc.empty:
        return pd.DataFrame()
    frame = ohlc.copy()
    frame["has_real_trade"] = frame["volume"].fillna(0).gt(0) & frame["close"].fillna(0).gt(0)
    rows = []
    for (event_id, timestamp), group in frame.groupby(["event_id", "timestamp"], sort=True):
        fresh = group[group["has_real_trade"]]
        call_strikes = fresh.loc[fresh["option_type"].eq("call"), "strike"].nunique()
        put_strikes = fresh.loc[fresh["option_type"].eq("put"), "strike"].nunique()
        distinct_strikes = fresh["strike"].nunique()
        stale_share = float(1.0 - group["has_real_trade"].mean())
        both_sides = bool(call_strikes > 0 and put_strikes > 0)
        strike_pass = bool(distinct_strikes >= minimum_fresh_strikes)
        stale_pass = bool(stale_share <= maximum_stale_bar_share)
        rows.append(
            {
                "event_id": str(event_id),
                "timestamp": timestamp,
                "n_rows": int(len(group)),
                "n_fresh_rows": int(len(fresh)),
                "n_distinct_fresh_strikes": int(distinct_strikes),
                "n_fresh_call_strikes": int(call_strikes),
                "n_fresh_put_strikes": int(put_strikes),
                "total_fresh_volume": float(fresh["volume"].sum()),
                "stale_bar_share": stale_share,
                "both_sides_fresh": both_sides,
                "minimum_fresh_strikes_pass": strike_pass,
                "maximum_stale_share_pass": stale_pass,
                "curve_quality_pass": bool(both_sides and strike_pass and stale_pass),
            }
        )
    return pd.DataFrame(rows)


def _array_value(values: Any, index: int) -> float:
    if isinstance(values, list) and index < len(values):
        return values[index]
    return math.nan


def download_probe_grid(
    grid: pd.DataFrame,
    client: Any = requests,
    max_instruments: int | None = None,
    timeout: int = 30,
    resolution: str = "1D",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if max_instruments is not None and max_instruments < 1:
        raise ValueError("max_instruments must be positive when supplied.")
    selected = grid if max_instruments is None else grid.head(max_instruments)
    ohlc_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []

    for _, instrument in selected.iterrows():
        params = {
            "instrument_name": instrument["instrument_name"],
            "start_timestamp": int(_parse_utc(instrument["start_timestamp"]).timestamp() * 1000),
            "end_timestamp": int(_parse_utc(instrument["end_timestamp"]).timestamp() * 1000),
            "resolution": resolution,
        }
        try:
            response = client.get(DERIBIT_CHART, params=params, headers=HEADERS, timeout=timeout)
            payload = response.json()
            api_error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(api_error, dict):
                error_data = api_error.get("data", {})
                reason = error_data.get("reason") if isinstance(error_data, dict) else None
                reason_text = str(reason or api_error.get("message") or "unknown error")
                status = "instrument_not_found" if reason_text.lower() == "instrument not found" else "api_error"
                diagnostic_rows.append(
                    {
                        "event_id": str(instrument["event_id"]),
                        "instrument_name": str(instrument["instrument_name"]),
                        "strike": float(instrument["strike"]),
                        "option_type": str(instrument["option_type"]),
                        "chart_status": status,
                        "ohlc_rows": 0,
                        "real_trade_rows": 0,
                        "error": f"Deribit {api_error.get('code')}: {reason_text}",
                    }
                )
                continue
            response.raise_for_status()
            result = payload.get("result", {}) if isinstance(payload, dict) else {}
            if not isinstance(result, dict):
                result = {}
            status = str(result.get("status", "missing_result"))
            ticks = result.get("ticks", [])
            instrument_row_count = 0
            real_trade_count = 0
            for index, tick in enumerate(ticks if isinstance(ticks, list) else []):
                tick_timestamp = pd.Timestamp(datetime.fromtimestamp(float(tick) / 1000, tz=timezone.utc))
                if tick_timestamp < _parse_utc(instrument["start_timestamp"]) or tick_timestamp > _parse_utc(
                    instrument["end_timestamp"]
                ):
                    continue
                close = _array_value(result.get("close"), index)
                volume = _array_value(result.get("volume"), index)
                has_real_trade = bool(pd.notna(close) and pd.notna(volume) and close > 0 and volume > 0)
                instrument_row_count += 1
                real_trade_count += int(has_real_trade)
                ohlc_rows.append(
                    {
                        "event_id": str(instrument["event_id"]),
                        "instrument_name": str(instrument["instrument_name"]),
                        "expiry_timestamp": _parse_utc(instrument["expiry_timestamp"]),
                        "mapping_quality": str(instrument["mapping_quality"]),
                        "strike": float(instrument["strike"]),
                        "option_type": str(instrument["option_type"]),
                        "timestamp": tick_timestamp,
                        "open": _array_value(result.get("open"), index),
                        "high": _array_value(result.get("high"), index),
                        "low": _array_value(result.get("low"), index),
                        "close": close,
                        "volume": volume,
                        "cost": _array_value(result.get("cost"), index),
                        "chart_status": status,
                        "has_real_trade": has_real_trade,
                    }
                )
            error = None
        except Exception as exc:  # noqa: BLE001 - retain per-instrument API failures as evidence.
            status = "error"
            instrument_row_count = 0
            real_trade_count = 0
            error = f"{type(exc).__name__}: {exc}"

        diagnostic_rows.append(
            {
                "event_id": str(instrument["event_id"]),
                "instrument_name": str(instrument["instrument_name"]),
                "strike": float(instrument["strike"]),
                "option_type": str(instrument["option_type"]),
                "chart_status": status,
                "ohlc_rows": instrument_row_count,
                "real_trade_rows": real_trade_count,
                "error": error,
            }
        )

    return pd.DataFrame(ohlc_rows), pd.DataFrame(diagnostic_rows)
