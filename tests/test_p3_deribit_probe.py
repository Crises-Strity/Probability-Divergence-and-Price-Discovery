from datetime import date

import requests

from scripts.P3_asset_extension.deribit_feasibility import (
    build_expiry_match_tables,
    candidate_expiry_dates,
    deribit_option_name,
    match_event_expiry,
)
import pandas as pd


class FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self) -> dict[str, object]:
        return self.payload


class FakeClient:
    def __init__(self, instruments: dict[str, dict[str, object]]) -> None:
        self.instruments = instruments
        self.requested_names: list[str] = []

    def get(self, url: str, params: dict[str, object], headers: dict[str, str], timeout: int) -> FakeResponse:
        name = str(params["instrument_name"])
        self.requested_names.append(name)
        if name in self.instruments:
            return FakeResponse({"jsonrpc": "2.0", "result": self.instruments[name]})
        return FakeResponse(
            {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "data": {"reason": "instrument not found", "param": "instrument_name"},
                    "message": "Invalid params",
                },
            },
            status_code=400,
        )


def instrument(name: str, expiration_timestamp: int) -> dict[str, object]:
    return {
        "instrument_name": name,
        "instrument_type": "linear",
        "base_currency": "SOL",
        "quote_currency": "USDC",
        "settlement_currency": "USDC",
        "contract_size": 10,
        "price_index": "sol_usdc",
        "strike": 100.0,
        "option_type": "call",
        "expiration_timestamp": expiration_timestamp,
        "state": "archivized",
    }


def test_deribit_linear_option_name() -> None:
    assert deribit_option_name(date(2025, 10, 10), 100.0, "call") == "SOL_USDC-10OCT25-100-C"
    assert deribit_option_name(date(2025, 10, 10), 95.5, "put") == "SOL_USDC-10OCT25-95.5-P"


def test_candidate_dates_are_ordered_by_absolute_horizon_gap() -> None:
    dates = candidate_expiry_dates("2025-10-12T16:00:00+00:00", max_abs_days=3)

    assert dates[:3] == [date(2025, 10, 12), date(2025, 10, 13), date(2025, 10, 11)]
    assert len(dates) == 7


def test_match_event_expiry_uses_verified_metadata_not_calendar_inference() -> None:
    name = "SOL_USDC-10OCT25-100-C"
    client = FakeClient({name: instrument(name, 1760083200000)})

    result = match_event_expiry(
        settlement_timestamp="2025-10-10T16:00:00+00:00",
        strikes=(90.0, 100.0, 110.0),
        max_abs_days=3,
        client=client,
    )

    assert result["match_status"] == "matched_verified_metadata"
    assert result["instrument_name"] == name
    assert result["deribit_expiry_timestamp"] == "2025-10-10T08:00:00+00:00"
    assert result["signed_horizon_gap_hours"] == 8.0
    assert result["mapping_quality"] == "exact"
    assert result["contract_units_verified"] is True


def test_match_event_expiry_retains_unmatched_evidence() -> None:
    client = FakeClient({})

    result = match_event_expiry(
        settlement_timestamp="2025-10-10T16:00:00+00:00",
        strikes=(90.0, 100.0, 110.0),
        max_abs_days=1,
        client=client,
    )

    assert result["match_status"] == "unmatched"
    assert result["mapping_quality"] == "unmappable"
    assert result["probe_request_count"] == 18
    assert len(client.requested_names) == 18


def test_build_expiry_match_tables_retains_event_and_contract_evidence() -> None:
    name = "SOL_USDC-10OCT25-100-C"
    client = FakeClient({name: instrument(name, 1760083200000)})
    events = pd.DataFrame(
        [
            {
                "event_id": "e1",
                "event_title": "Solana price on October 10?",
                "settlement_timestamp": "2025-10-10T16:00:00+00:00",
                "is_candidate_partition": True,
            }
        ]
    )
    cells = pd.DataFrame(
        [
            {"event_id": "e1", "cell_low": float("-inf"), "cell_high": 90.0},
            {"event_id": "e1", "cell_low": 90.0, "cell_high": 100.0},
            {"event_id": "e1", "cell_low": 100.0, "cell_high": 110.0},
            {"event_id": "e1", "cell_low": 110.0, "cell_high": float("inf")},
        ]
    )

    matches, instruments = build_expiry_match_tables(events, cells, max_abs_days=3, client=client)

    assert matches.loc[0, "event_id"] == "e1"
    assert matches.loc[0, "mapping_quality"] == "exact"
    assert matches.loc[0, "representative_strikes"] == "90,100,110"
    assert instruments.loc[0, "instrument_name"] == name
    assert instruments.loc[0, "contract_size"] == 10
