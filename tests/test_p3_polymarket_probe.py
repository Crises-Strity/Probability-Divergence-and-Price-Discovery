import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from scripts.P3_asset_extension.polymarket_feasibility import (
    build_event_inventory,
    discover_events,
    write_polymarket_artifacts,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class FakeClient:
    def __init__(self, pages: dict[tuple[str, int], dict[str, object]]) -> None:
        self.pages = pages
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        params: dict[str, object],
        headers: dict[str, str],
        timeout: int,
    ) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        key = (str(params["q"]), int(params["page"]))
        return FakeResponse(self.pages.get(key, {"events": [], "pagination": {"hasMore": False}}))


def complete_event(event_id: str, title: str = "Solana price on August 4?") -> dict[str, object]:
    questions = [
        ("left", "Will Solana be less than $80 on August 4?", '["yes-left", "no-left"]'),
        ("b1", "Will Solana be between $80 and $90 on August 4?", '["yes-b1", "no-b1"]'),
        ("b2", "Will Solana be between $90 and $100 on August 4?", '["yes-b2", "no-b2"]'),
        ("right", "Will Solana be greater than $100 on August 4?", '["yes-right", "no-right"]'),
    ]
    return {
        "id": event_id,
        "title": title,
        "startDate": "2026-08-01T00:00:00Z",
        "endDate": "2026-08-04T16:00:00Z",
        "closed": True,
        "resolutionSource": "https://www.binance.com/en/price/solana",
        "description": (
            "This market will resolve according to the final Close price of the Binance "
            "1 minute candle for SOL/USDT 12:00 in the ET timezone (noon) on the date "
            "specified in the title."
        ),
        "markets": [
            {
                "id": market_id,
                "question": question,
                "clobTokenIds": token_ids,
                "outcomePrices": '["1", "0"]',
            }
            for market_id, question, token_ids in questions
        ],
    }


def test_discover_events_bounds_pages_and_deduplicates_event_ids() -> None:
    event = complete_event("1")
    client = FakeClient(
        {
            ("solana", 0): {"events": [event], "pagination": {"hasMore": True}},
            ("solana", 1): {"events": [event], "pagination": {"hasMore": False}},
            ("sol price", 0): {"events": [complete_event("2")], "pagination": {"hasMore": False}},
        }
    )

    events, raw_pages = discover_events(
        search_terms=("solana", "sol price"),
        max_pages=2,
        client=client,
    )

    assert [event["id"] for event in events] == ["1", "2"]
    assert len(raw_pages) == 3
    assert len(client.calls) == 3
    assert all(call["timeout"] == 30 for call in client.calls)


def test_build_event_inventory_retains_complete_and_excluded_events() -> None:
    complete = complete_event("1")
    path_event = {
        **complete_event("2", "What price will Solana hit in August?"),
        "markets": [
            {
                "id": "hit",
                "question": "Will Solana reach $160 in August?",
                "clobTokenIds": '["yes-hit", "no-hit"]',
            }
        ],
    }

    inventory, cells = build_event_inventory([complete, path_event])

    passing = inventory.set_index("event_id").loc["1"]
    excluded = inventory.set_index("event_id").loc["2"]
    assert passing["event_type"] == "terminal_bucket_distribution"
    assert bool(passing["is_candidate_partition"]) is True
    assert passing["number_of_cells"] == 4
    assert passing["finite_bucket_width"] == 10.0
    assert passing["settlement_timestamp"] == "2026-08-04T16:00:00+00:00"
    assert passing["settlement_reference"] == "Binance SOL/USDT 1m close"
    assert passing["settlement_time_status"] == "verified_from_rules"
    assert passing["exclusion_reason"] == ""
    assert excluded["event_type"] == "path_dependent_or_unsupported"
    assert bool(excluded["is_candidate_partition"]) is False
    assert excluded["exclusion_reason"] == "no_terminal_partition_cells"
    assert set(cells["event_id"]) == {"1"}
    assert set(cells["yes_token_id"]) == {"yes-left", "yes-b1", "yes-b2", "yes-right"}


def test_rules_override_inconsistent_event_end_time() -> None:
    event = complete_event("3", "Solana price on June 6?")
    event["endDate"] = "2025-06-06T12:00:00Z"

    inventory, _ = build_event_inventory([event])
    row = inventory.iloc[0]

    assert row["event_end_time"] == "2025-06-06T12:00:00Z"
    assert row["settlement_timestamp"] == "2025-06-06T16:00:00+00:00"
    assert row["settlement_time_gap_from_event_end_hours"] == 4.0
    assert bool(row["is_candidate_partition"]) is True


def test_write_artifacts_preserves_raw_pages_and_machine_readable_outputs(tmp_path: Path) -> None:
    events = [complete_event("1")]
    inventory, cells = build_event_inventory(events)
    raw_pages = [{"search_term": "solana", "page": 0, "payload": {"events": events}}]

    metadata = write_polymarket_artifacts(
        raw_pages=raw_pages,
        inventory=inventory,
        cells=cells,
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        snapshot_utc="2026-08-03T18:00:00Z",
        search_terms=("solana",),
        max_pages=2,
    )

    raw_path = tmp_path / "raw" / "polymarket_search_solana_page_0.json"
    assert json.loads(raw_path.read_text(encoding="utf-8"))["events"][0]["id"] == "1"
    assert pd.read_parquet(tmp_path / "processed" / "polymarket_event_inventory.parquet").shape[0] == 1
    assert pd.read_parquet(tmp_path / "processed" / "polymarket_event_cells.parquet").shape[0] == 4
    assert (tmp_path / "processed" / "polymarket_event_inventory.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert metadata["row_counts"]["candidate_events"] == 1
    assert metadata["request"]["max_pages_per_term"] == 2


def test_runner_can_be_executed_by_file_path() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/P3_asset_extension/run_p3_feasibility.py",
            "--help",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Run bounded P3 feasibility stages" in result.stdout
    assert "deribit-ohlc" in result.stdout
