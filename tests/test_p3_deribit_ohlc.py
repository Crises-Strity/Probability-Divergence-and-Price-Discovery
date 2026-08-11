from __future__ import annotations

import math

import pandas as pd
import pytest
import requests

from scripts.P3_asset_extension.deribit_ohlc_feasibility import (
    build_bar_quality,
    build_event_probe_grid,
    build_probe_grid,
    download_probe_grid,
    probe_cache_key,
    select_smoke_event_ids,
)


class FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self) -> dict[str, object]:
        return self.payload


class FakeChartClient:
    def __init__(self, payloads: dict[str, dict[str, object]], status_codes: dict[str, int] | None = None) -> None:
        self.payloads = payloads
        self.status_codes = status_codes or {}
        self.requested_names: list[str] = []

    def get(self, url: str, params: dict[str, object], headers: dict[str, str], timeout: int) -> FakeResponse:
        name = str(params["instrument_name"])
        self.requested_names.append(name)
        return FakeResponse(self.payloads[name], self.status_codes.get(name, 200))


def test_select_smoke_event_ids_spans_exact_expiry_history() -> None:
    matches = pd.DataFrame(
        [
            {"event_id": "a", "deribit_expiry_timestamp": "2025-01-01T08:00:00Z", "mapping_quality": "exact"},
            {"event_id": "b", "deribit_expiry_timestamp": "2025-02-01T08:00:00Z", "mapping_quality": "close"},
            {"event_id": "c", "deribit_expiry_timestamp": "2025-03-01T08:00:00Z", "mapping_quality": "exact"},
            {"event_id": "d", "deribit_expiry_timestamp": "2025-04-01T08:00:00Z", "mapping_quality": "exact"},
            {"event_id": "e", "deribit_expiry_timestamp": "2025-05-01T08:00:00Z", "mapping_quality": "exact"},
        ]
    )

    assert select_smoke_event_ids(matches, sample_size=3) == ("a", "d", "e")


def test_build_event_probe_grid_uses_finite_cell_bounds_and_p1_extensions() -> None:
    event = pd.Series(
        {
            "event_id": "25536",
            "event_start_time": "2025-05-30T13:22:29Z",
            "finite_bucket_width": 10.0,
        }
    )
    cells = pd.DataFrame(
        [
            {"event_id": "25536", "cell_type": "left_tail", "cell_low": -math.inf, "cell_high": 150.0},
            {"event_id": "25536", "cell_type": "bucket", "cell_low": 150.0, "cell_high": 160.0},
            {"event_id": "25536", "cell_type": "right_tail", "cell_low": 160.0, "cell_high": math.inf},
        ]
    )
    match = pd.Series(
        {
            "event_id": "25536",
            "deribit_expiry_timestamp": "2025-06-06T08:00:00Z",
            "mapping_quality": "exact",
        }
    )

    grid = build_event_probe_grid(event, cells, match, extension_steps=6)

    assert grid["strike"].drop_duplicates().tolist() == [
        90.0,
        100.0,
        110.0,
        120.0,
        130.0,
        140.0,
        150.0,
        160.0,
        170.0,
        180.0,
        190.0,
        200.0,
        210.0,
        220.0,
    ]
    assert len(grid) == 28
    assert set(grid["option_type"]) == {"call", "put"}
    assert grid["start_timestamp"].nunique() == 1
    assert grid["start_timestamp"].iloc[0] == pd.Timestamp("2025-05-30T13:22:29Z")
    assert grid["end_timestamp"].iloc[0] == pd.Timestamp("2025-06-06T08:00:00Z")
    assert grid.loc[grid["strike"].eq(150.0) & grid["option_type"].eq("call"), "instrument_name"].iloc[0] == (
        "SOL_USDC-6JUN25-150-C"
    )


def test_build_probe_grid_joins_canonical_p3_schemas_by_event_id() -> None:
    events = pd.DataFrame(
        [
            {
                "event_id": "e1",
                "event_start_time": "2025-05-30T13:22:29Z",
                "finite_bucket_width": 10.0,
            }
        ]
    )
    cells = pd.DataFrame(
        [
            {"event_id": "e1", "cell_type": "left_tail", "cell_low": -math.inf, "cell_high": 150.0},
            {"event_id": "e1", "cell_type": "bucket", "cell_low": 150.0, "cell_high": 160.0},
            {"event_id": "e1", "cell_type": "right_tail", "cell_low": 160.0, "cell_high": math.inf},
        ]
    )
    matches = pd.DataFrame(
        [
            {
                "event_id": "e1",
                "deribit_expiry_timestamp": "2025-06-06T08:00:00Z",
                "mapping_quality": "exact",
            }
        ]
    )

    grid = build_probe_grid(events, cells, matches, event_ids=("e1",), extension_steps=0)

    assert grid[["event_id", "strike", "option_type"]].to_dict("records") == [
        {"event_id": "e1", "strike": 150.0, "option_type": "call"},
        {"event_id": "e1", "strike": 150.0, "option_type": "put"},
        {"event_id": "e1", "strike": 160.0, "option_type": "call"},
        {"event_id": "e1", "strike": 160.0, "option_type": "put"},
    ]


def test_build_bar_quality_counts_fresh_distinct_strikes_and_full_grid_staleness() -> None:
    timestamp = pd.Timestamp("2025-06-01T00:00:00Z")
    rows = []
    for strike in (140.0, 150.0, 160.0, 170.0):
        for option_type in ("call", "put"):
            rows.append(
                {
                    "event_id": "25536",
                    "timestamp": timestamp,
                    "strike": strike,
                    "option_type": option_type,
                    "close": 2.0,
                    "volume": 1.0,
                }
            )
    rows.extend(
        [
            {
                "event_id": "25536",
                "timestamp": timestamp,
                "strike": 180.0,
                "option_type": "call",
                "close": 3.0,
                "volume": 0.0,
            },
            {
                "event_id": "25536",
                "timestamp": timestamp,
                "strike": 180.0,
                "option_type": "put",
                "close": 0.0,
                "volume": 2.0,
            },
        ]
    )

    quality = build_bar_quality(pd.DataFrame(rows), minimum_fresh_strikes=4, maximum_stale_bar_share=0.30)

    record = quality.to_dict("records")[0]
    assert record.pop("stale_bar_share") == pytest.approx(0.2)
    assert record == {
        "event_id": "25536",
        "timestamp": timestamp,
        "n_rows": 10,
        "n_fresh_rows": 8,
        "n_distinct_fresh_strikes": 4,
        "n_fresh_call_strikes": 4,
        "n_fresh_put_strikes": 4,
        "total_fresh_volume": 8.0,
        "both_sides_fresh": True,
        "minimum_fresh_strikes_pass": True,
        "maximum_stale_share_pass": True,
        "curve_quality_pass": True,
    }


def test_download_probe_grid_parses_real_trade_and_retains_no_data_instrument() -> None:
    grid = pd.DataFrame(
        [
            {
                "event_id": "e1",
                "instrument_name": "SOL_USDC-6JUN25-150-C",
                "strike": 150.0,
                "option_type": "call",
                "start_timestamp": pd.Timestamp("2025-05-30T00:00:00Z"),
                "end_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "expiry_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "mapping_quality": "exact",
            },
            {
                "event_id": "e1",
                "instrument_name": "SOL_USDC-6JUN25-150-P",
                "strike": 150.0,
                "option_type": "put",
                "start_timestamp": pd.Timestamp("2025-05-30T00:00:00Z"),
                "end_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "expiry_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "mapping_quality": "exact",
            },
        ]
    )
    client = FakeChartClient(
        {
            "SOL_USDC-6JUN25-150-C": {
                "result": {
                    "status": "ok",
                    "ticks": [1748736000000],
                    "open": [2.5],
                    "high": [3.5],
                    "low": [2.0],
                    "close": [3.0],
                    "volume": [2.0],
                    "cost": [60.0],
                }
            },
            "SOL_USDC-6JUN25-150-P": {
                "result": {"status": "no_data", "ticks": []}
            },
        }
    )

    ohlc, diagnostics = download_probe_grid(grid, client=client, max_instruments=2)

    assert client.requested_names == ["SOL_USDC-6JUN25-150-C", "SOL_USDC-6JUN25-150-P"]
    assert ohlc[["instrument_name", "close", "volume", "has_real_trade"]].to_dict("records") == [
        {
            "instrument_name": "SOL_USDC-6JUN25-150-C",
            "close": 3.0,
            "volume": 2.0,
            "has_real_trade": True,
        }
    ]
    assert diagnostics[["instrument_name", "chart_status", "ohlc_rows", "real_trade_rows"]].to_dict(
        "records"
    ) == [
        {
            "instrument_name": "SOL_USDC-6JUN25-150-C",
            "chart_status": "ok",
            "ohlc_rows": 1,
            "real_trade_rows": 1,
        },
        {
            "instrument_name": "SOL_USDC-6JUN25-150-P",
            "chart_status": "no_data",
            "ohlc_rows": 0,
            "real_trade_rows": 0,
        },
    ]


def test_download_probe_grid_enforces_instrument_request_bound() -> None:
    grid = pd.DataFrame(
        [
            {
                "event_id": "e1",
                "instrument_name": name,
                "strike": strike,
                "option_type": "call",
                "start_timestamp": pd.Timestamp("2025-05-30T00:00:00Z"),
                "end_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "expiry_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "mapping_quality": "exact",
            }
            for name, strike in (("first", 150.0), ("second", 160.0))
        ]
    )
    client = FakeChartClient(
        {
            "first": {"result": {"status": "no_data", "ticks": []}},
            "second": {"result": {"status": "no_data", "ticks": []}},
        }
    )

    _, diagnostics = download_probe_grid(grid, client=client, max_instruments=1)

    assert client.requested_names == ["first"]
    assert diagnostics["instrument_name"].tolist() == ["first"]


def test_download_probe_grid_excludes_daily_candle_labeled_before_requested_window() -> None:
    grid = pd.DataFrame(
        [
            {
                "event_id": "e1",
                "instrument_name": "one",
                "strike": 150.0,
                "option_type": "call",
                "start_timestamp": pd.Timestamp("2025-05-30T00:00:00Z"),
                "end_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "expiry_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "mapping_quality": "exact",
            }
        ]
    )
    client = FakeChartClient(
        {
            "one": {
                "result": {
                    "status": "ok",
                    "ticks": [1748505600000, 1748592000000],
                    "close": [2.0, 3.0],
                    "volume": [1.0, 1.0],
                }
            }
        }
    )

    ohlc, diagnostics = download_probe_grid(grid, client=client)

    assert ohlc["timestamp"].tolist() == [pd.Timestamp("2025-05-30T08:00:00Z")]
    assert diagnostics.loc[0, "ohlc_rows"] == 1


def test_download_probe_grid_retains_deribit_error_reason_from_http_400() -> None:
    grid = pd.DataFrame(
        [
            {
                "event_id": "e1",
                "instrument_name": "missing",
                "strike": 150.0,
                "option_type": "call",
                "start_timestamp": pd.Timestamp("2025-05-30T00:00:00Z"),
                "end_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "expiry_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "mapping_quality": "exact",
            }
        ]
    )
    client = FakeChartClient(
        {
            "missing": {
                "error": {
                    "code": -32602,
                    "data": {"reason": "instrument not found"},
                    "message": "Invalid params",
                }
            }
        },
        status_codes={"missing": 400},
    )

    _, diagnostics = download_probe_grid(grid, client=client)

    assert diagnostics.loc[0, "chart_status"] == "instrument_not_found"
    assert diagnostics.loc[0, "error"] == "Deribit -32602: instrument not found"


def test_probe_cache_key_changes_with_grid_or_request_bound() -> None:
    grid = pd.DataFrame(
        [
            {
                "event_id": "e1",
                "instrument_name": "one",
                "strike": 150.0,
                "option_type": "call",
                "start_timestamp": pd.Timestamp("2025-05-30T13:22:29Z"),
                "end_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "expiry_timestamp": pd.Timestamp("2025-06-06T08:00:00Z"),
                "mapping_quality": "exact",
            }
        ]
    )
    changed = grid.copy()
    changed.loc[0, "start_timestamp"] = pd.Timestamp("2025-05-31T13:22:29Z")

    baseline = probe_cache_key(grid, resolution="1D", max_instruments=None)

    assert probe_cache_key(grid.copy(), resolution="1D", max_instruments=None) == baseline
    assert probe_cache_key(changed, resolution="1D", max_instruments=None) != baseline
    assert probe_cache_key(grid, resolution="1D", max_instruments=1) != baseline
