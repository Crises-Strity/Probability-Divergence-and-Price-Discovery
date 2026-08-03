import math

import pytest

from scripts.P3_asset_extension.polymarket_feasibility import (
    assess_partition,
    canonicalize_cells,
    classify_market,
)


ALIASES = {"SOL": ("sol", "solana")}


@pytest.mark.parametrize(
    ("question", "expected_type", "low", "high"),
    [
        ("Will Solana be below $100 on August 30?", "terminal_left_tail", -math.inf, 100.0),
        ("Will the SOL price be between $100 and $120 on August 30?", "terminal_bucket", 100.0, 120.0),
        ("Will Solana be above $140 on August 30?", "terminal_right_tail", 140.0, math.inf),
        ("Will SOL reach $200 before August 30?", "path_dependent", None, None),
    ],
)
def test_classify_sol_market(
    question: str,
    expected_type: str,
    low: float | None,
    high: float | None,
) -> None:
    result = classify_market(question, ALIASES)

    assert result.classification == expected_type
    assert result.asset == "SOL"
    assert result.cell_low == low
    assert result.cell_high == high


def test_classify_market_rejects_non_sol_and_unsupported_question() -> None:
    non_sol = classify_market("Will Bitcoin be above $100,000 on August 30?", ALIASES)
    unsupported = classify_market("What will Solana volatility be in August?", ALIASES)

    assert non_sol.classification == "unsupported"
    assert non_sol.reason_code == "asset_not_in_scope"
    assert unsupported.classification == "unsupported"
    assert unsupported.reason_code == "unsupported_terminal_definition"


def test_complete_partition_has_ordered_cells_and_both_open_tails() -> None:
    markets = [
        {"id": "right", "question": "Will Solana be above $140 on August 30?", "clobTokenIds": '["yes-right", "no-right"]'},
        {"id": "middle-2", "question": "Will SOL be between $120 and $140 on August 30?", "clobTokenIds": '["yes-2", "no-2"]'},
        {"id": "left", "question": "Will Solana be below $100 on August 30?", "clobTokenIds": '["yes-left", "no-left"]'},
        {"id": "middle-1", "question": "Will SOL be between $100 and $120 on August 30?", "clobTokenIds": '["yes-1", "no-1"]'},
    ]

    cells = canonicalize_cells(markets, asset_aliases=ALIASES)
    assessment = assess_partition(cells)

    assert [cell["market_id"] for cell in cells] == ["left", "middle-1", "middle-2", "right"]
    assert cells[0]["yes_token_id"] == "yes-left"
    assert assessment == {
        "number_of_cells": 4,
        "has_left_tail": True,
        "has_right_tail": True,
        "has_overlap": False,
        "has_gap": False,
        "is_complete_partition": True,
        "reason_codes": [],
    }


def test_partition_reports_gap_and_missing_tail() -> None:
    cells = [
        {"cell_low": -math.inf, "cell_high": 100.0},
        {"cell_low": 110.0, "cell_high": 120.0},
    ]

    assessment = assess_partition(cells)

    assert assessment["has_gap"] is True
    assert assessment["has_right_tail"] is False
    assert assessment["is_complete_partition"] is False
    assert assessment["reason_codes"] == ["missing_right_tail", "partition_gap"]


def test_partition_reports_overlap() -> None:
    cells = [
        {"cell_low": -math.inf, "cell_high": 100.0},
        {"cell_low": 90.0, "cell_high": 120.0},
        {"cell_low": 120.0, "cell_high": math.inf},
    ]

    assessment = assess_partition(cells)

    assert assessment["has_overlap"] is True
    assert assessment["is_complete_partition"] is False
    assert assessment["reason_codes"] == ["partition_overlap"]

