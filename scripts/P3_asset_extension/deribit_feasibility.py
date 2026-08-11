"""Verified Deribit expiry matching for the P3 SOL feasibility audit."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import pandas as pd
import requests


DERIBIT_GET_INSTRUMENT = "https://www.deribit.com/api/v2/public/get_instrument"
HEADERS = {"User-Agent": "ucl-dissertation-research/0.3"}


def _format_strike(strike: float) -> str:
    value = float(strike)
    if value.is_integer():
        return str(int(value))
    return f"{value:.8f}".rstrip("0").rstrip(".")


def deribit_option_name(expiry_date: date, strike: float, option_type: str) -> str:
    side = {"call": "C", "put": "P"}.get(option_type)
    if side is None:
        raise ValueError("option_type must be call or put.")
    expiry_code = f"{expiry_date.day}{expiry_date.strftime('%b').upper()}{expiry_date.strftime('%y')}"
    return f"SOL_USDC-{expiry_code}-{_format_strike(strike)}-{side}"


def candidate_expiry_dates(settlement_timestamp: str, max_abs_days: int) -> list[date]:
    if max_abs_days < 0:
        raise ValueError("max_abs_days cannot be negative.")
    settlement = pd.Timestamp(settlement_timestamp)
    if settlement.tzinfo is None:
        raise ValueError("settlement_timestamp must be timezone-aware.")
    settlement = settlement.tz_convert("UTC")
    candidates = [settlement.date() + timedelta(days=offset) for offset in range(-max_abs_days, max_abs_days + 1)]
    return sorted(
        candidates,
        key=lambda candidate: abs(
            (
                settlement.to_pydatetime()
                - datetime.combine(candidate, time(hour=8), tzinfo=timezone.utc)
            ).total_seconds()
        ),
    )


def _mapping_quality(settlement: datetime, expiry: datetime) -> str:
    gap_hours = abs((settlement - expiry).total_seconds() / 3600)
    calendar_days = abs((settlement.date() - expiry.date()).days)
    if calendar_days == 0:
        return "exact"
    if gap_hours <= 48:
        return "close"
    if gap_hours <= 120:
        return "loose"
    return "unmappable"


def _valid_sol_linear_instrument(metadata: dict[str, Any]) -> bool:
    return (
        metadata.get("instrument_type") == "linear"
        and metadata.get("base_currency") == "SOL"
        and metadata.get("quote_currency") == "USDC"
        and metadata.get("settlement_currency") == "USDC"
        and float(metadata.get("contract_size") or 0) == 10
        and metadata.get("price_index") == "sol_usdc"
    )


def match_event_expiry(
    settlement_timestamp: str,
    strikes: tuple[float, ...],
    max_abs_days: int,
    client: Any = requests,
) -> dict[str, Any]:
    if not strikes:
        raise ValueError("At least one strike is required for metadata probing.")
    settlement = pd.Timestamp(settlement_timestamp)
    if settlement.tzinfo is None:
        raise ValueError("settlement_timestamp must be timezone-aware.")
    settlement_dt = settlement.tz_convert("UTC").to_pydatetime()
    center = float(pd.Series(strikes).median())
    ordered_strikes = sorted(set(float(value) for value in strikes), key=lambda value: (abs(value - center), value))

    request_count = 0
    for expiry_date in candidate_expiry_dates(settlement_timestamp, max_abs_days):
        for strike in ordered_strikes:
            for option_type in ("call", "put"):
                name = deribit_option_name(expiry_date, strike, option_type)
                response = client.get(
                    DERIBIT_GET_INSTRUMENT,
                    params={"instrument_name": name},
                    headers=HEADERS,
                    timeout=30,
                )
                request_count += 1
                payload = response.json()
                error = payload.get("error") if isinstance(payload, dict) else None
                error_data = error.get("data", {}) if isinstance(error, dict) else {}
                if str(error_data.get("reason", "")).lower() == "instrument not found":
                    continue
                response.raise_for_status()
                metadata = payload.get("result")
                if not isinstance(metadata, dict):
                    continue
                expiry_ms = metadata.get("expiration_timestamp")
                if expiry_ms is None:
                    continue
                expiry_dt = datetime.fromtimestamp(float(expiry_ms) / 1000, tz=timezone.utc)
                if not _valid_sol_linear_instrument(metadata):
                    continue
                signed_gap = (settlement_dt - expiry_dt).total_seconds() / 3600
                return {
                    "match_status": "matched_verified_metadata",
                    "instrument_name": name,
                    "deribit_expiry_timestamp": expiry_dt.isoformat(),
                    "signed_horizon_gap_hours": signed_gap,
                    "absolute_horizon_gap_hours": abs(signed_gap),
                    "calendar_gap_days": (settlement_dt.date() - expiry_dt.date()).days,
                    "mapping_quality": _mapping_quality(settlement_dt, expiry_dt),
                    "contract_units_verified": True,
                    "probe_request_count": request_count,
                    "instrument_metadata": metadata,
                }

    return {
        "match_status": "unmatched",
        "instrument_name": None,
        "deribit_expiry_timestamp": None,
        "signed_horizon_gap_hours": None,
        "absolute_horizon_gap_hours": None,
        "calendar_gap_days": None,
        "mapping_quality": "unmappable",
        "contract_units_verified": False,
        "probe_request_count": request_count,
        "instrument_metadata": None,
    }


def _representative_strikes(event_cells: pd.DataFrame) -> tuple[float, ...]:
    values = []
    for column in ("cell_low", "cell_high"):
        values.extend(float(value) for value in event_cells[column].dropna() if pd.notna(value))
    finite = sorted(set(value for value in values if pd.notna(value) and abs(value) != float("inf")))
    if len(finite) <= 3:
        return tuple(finite)
    return (finite[0], finite[len(finite) // 2], finite[-1])


def _strike_list_text(strikes: tuple[float, ...]) -> str:
    return ",".join(_format_strike(value) for value in strikes)


def build_expiry_match_tables(
    events: pd.DataFrame,
    cells: pd.DataFrame,
    max_abs_days: int,
    client: Any = requests,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    match_rows = []
    instrument_rows = []
    candidates = events[events["is_candidate_partition"]].copy()
    for _, event in candidates.iterrows():
        event_id = str(event["event_id"])
        event_cells = cells[cells["event_id"].astype(str) == event_id]
        strikes = _representative_strikes(event_cells)
        result = match_event_expiry(
            settlement_timestamp=str(event["settlement_timestamp"]),
            strikes=strikes,
            max_abs_days=max_abs_days,
            client=client,
        )
        metadata = result.pop("instrument_metadata")
        match_rows.append(
            {
                "event_id": event_id,
                "event_title": event["event_title"],
                "polymarket_settlement_timestamp": event["settlement_timestamp"],
                "representative_strikes": _strike_list_text(strikes),
                **result,
            }
        )
        if metadata is not None:
            instrument_rows.append(
                {
                    "event_id": event_id,
                    "probe_role": "expiry_verification",
                    **metadata,
                }
            )
    return pd.DataFrame(match_rows), pd.DataFrame(instrument_rows)
