"""Pure classification helpers for the P3 Polymarket feasibility audit."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


AMOUNT_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*([kKmM]?)")
PATH_TERMS = (
    "reach",
    "hit",
    "touch",
    "anytime",
    "any time",
    "before",
    "dip to",
    "fall to",
    "drop to",
    "climb to",
    "rise to",
)
LEFT_TERMS = ("below", "less than", "under")
RIGHT_TERMS = ("above", "greater than", "over", "exceed", "at least")


@dataclass(frozen=True)
class MarketClassification:
    asset: str | None
    classification: str
    cell_low: float | None
    cell_high: float | None
    reason_code: str | None


def _asset_in_question(
    question: str,
    asset_aliases: Mapping[str, tuple[str, ...]],
) -> str | None:
    lowered = question.lower()
    for asset, aliases in asset_aliases.items():
        if any(re.search(rf"\b{re.escape(alias.lower())}\b", lowered) for alias in aliases):
            return asset
    return None


def _amounts(question: str) -> list[float]:
    amounts = []
    for number, suffix in AMOUNT_RE.findall(question):
        value = float(number.replace(",", ""))
        if suffix.lower() == "k":
            value *= 1_000
        elif suffix.lower() == "m":
            value *= 1_000_000
        amounts.append(value)
    return amounts


def classify_market(
    question: str,
    asset_aliases: Mapping[str, tuple[str, ...]],
) -> MarketClassification:
    asset = _asset_in_question(question, asset_aliases)
    if asset is None:
        return MarketClassification(None, "unsupported", None, None, "asset_not_in_scope")

    lowered = question.lower()
    amounts = _amounts(question)
    if any(term in lowered for term in PATH_TERMS):
        return MarketClassification(asset, "path_dependent", None, None, "path_dependent")

    if "between" in lowered and len(amounts) >= 2:
        low, high = sorted(amounts[:2])
        return MarketClassification(asset, "terminal_bucket", low, high, None)

    if any(term in lowered for term in LEFT_TERMS) and amounts:
        return MarketClassification(asset, "terminal_left_tail", -math.inf, amounts[0], None)

    if any(term in lowered for term in RIGHT_TERMS) and amounts:
        return MarketClassification(asset, "terminal_right_tail", amounts[0], math.inf, None)

    return MarketClassification(
        asset,
        "unsupported",
        None,
        None,
        "unsupported_terminal_definition",
    )


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    return []


def canonicalize_cells(
    markets: Sequence[Mapping[str, Any]],
    asset_aliases: Mapping[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    rows = []
    type_map = {
        "terminal_left_tail": "left_tail",
        "terminal_bucket": "bucket",
        "terminal_right_tail": "right_tail",
    }
    for market in markets:
        question = str(market.get("question") or "")
        parsed = classify_market(question, asset_aliases)
        if parsed.classification not in type_map:
            continue
        token_ids = _json_list(market.get("clobTokenIds"))
        rows.append(
            {
                "market_id": str(market.get("id") or market.get("conditionId") or ""),
                "question": question,
                "asset": parsed.asset,
                "cell_type": type_map[parsed.classification],
                "cell_low": parsed.cell_low,
                "cell_high": parsed.cell_high,
                "yes_token_id": str(token_ids[0]) if token_ids else None,
            }
        )
    return sorted(rows, key=lambda row: (float(row["cell_low"]), float(row["cell_high"])))


def assess_partition(cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(cells, key=lambda row: (float(row["cell_low"]), float(row["cell_high"])))
    has_left_tail = bool(ordered) and math.isinf(float(ordered[0]["cell_low"])) and float(ordered[0]["cell_low"]) < 0
    has_right_tail = bool(ordered) and math.isinf(float(ordered[-1]["cell_high"])) and float(ordered[-1]["cell_high"]) > 0
    has_overlap = False
    has_gap = False
    for left, right in zip(ordered, ordered[1:]):
        left_high = float(left["cell_high"])
        right_low = float(right["cell_low"])
        if right_low < left_high - 1e-9:
            has_overlap = True
        elif right_low > left_high + 1e-9:
            has_gap = True

    reason_codes = []
    if not has_left_tail:
        reason_codes.append("missing_left_tail")
    if not has_right_tail:
        reason_codes.append("missing_right_tail")
    if has_overlap:
        reason_codes.append("partition_overlap")
    if has_gap:
        reason_codes.append("partition_gap")

    return {
        "number_of_cells": len(ordered),
        "has_left_tail": has_left_tail,
        "has_right_tail": has_right_tail,
        "has_overlap": has_overlap,
        "has_gap": has_gap,
        "is_complete_partition": len(ordered) >= 4 and not reason_codes,
        "reason_codes": reason_codes,
    }
