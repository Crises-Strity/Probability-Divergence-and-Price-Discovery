"""Pure classification helpers for the P3 Polymarket feasibility audit."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests


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


GAMMA_SEARCH_URL = "https://gamma-api.polymarket.com/public-search"
HEADERS = {"User-Agent": "ucl-dissertation-research/0.3"}
SOL_ALIASES = {"SOL": ("sol", "solana")}


def discover_events(
    search_terms: tuple[str, ...],
    max_pages: int,
    client: Any = requests,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if max_pages < 1:
        raise ValueError("max_pages must be at least one.")

    events_by_id: dict[str, dict[str, Any]] = {}
    raw_pages = []
    for search_term in search_terms:
        for page in range(max_pages):
            response = client.get(
                GAMMA_SEARCH_URL,
                params={
                    "q": search_term,
                    "limit_per_type": 100,
                    "page": page,
                },
                headers=HEADERS,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            raw_pages.append(
                {
                    "search_term": search_term,
                    "page": page,
                    "payload": payload,
                }
            )
            page_events = payload.get("events", [])
            for event in page_events:
                event_id = str(event.get("id") or "")
                if event_id:
                    events_by_id.setdefault(event_id, event)

            pagination = payload.get("pagination", {})
            if not page_events or not pagination.get("hasMore", False):
                break

    return list(events_by_id.values()), raw_pages


def _parsed_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _finite_bucket_width(cells: list[dict[str, Any]]) -> float | None:
    widths = [
        float(cell["cell_high"]) - float(cell["cell_low"])
        for cell in cells
        if math.isfinite(float(cell["cell_low"])) and math.isfinite(float(cell["cell_high"]))
    ]
    if not widths:
        return None
    if max(widths) - min(widths) > 1e-9:
        return None
    return widths[0]


def _settlement_fields(event: Mapping[str, Any]) -> dict[str, Any]:
    markets = event.get("markets", []) or []
    descriptions = [
        str(event.get("description") or ""),
        *[str(market.get("description") or "") for market in markets],
    ]
    rules_text = next((text for text in descriptions if text.strip()), "")
    lowered = rules_text.lower()
    reference_verified = (
        "binance" in lowered
        and ("sol/usdt" in lowered or "solusdt" in lowered)
        and "1 minute candle" in lowered
    )
    noon_et_verified = (
        ("12:00" in lowered or "noon" in lowered)
        and ("et timezone" in lowered or "et time zone" in lowered)
    )

    raw_end = event.get("endDate")
    derived_timestamp = raw_end
    time_status = "unverified"
    time_gap_hours = None
    if reference_verified and noon_et_verified and raw_end:
        end_timestamp = pd.to_datetime(raw_end, errors="coerce", utc=True)
        if pd.notna(end_timestamp):
            local_noon = datetime.combine(
                end_timestamp.date(),
                time(hour=12),
                tzinfo=ZoneInfo("America/New_York"),
            )
            settlement_utc = local_noon.astimezone(timezone.utc)
            derived_timestamp = settlement_utc.isoformat()
            time_status = "verified_from_rules"
            time_gap_hours = (
                settlement_utc - end_timestamp.to_pydatetime()
            ).total_seconds() / 3600

    return {
        "settlement_timestamp": derived_timestamp,
        "settlement_reference": "Binance SOL/USDT 1m close" if reference_verified else None,
        "settlement_reference_detail": rules_text or None,
        "settlement_time_status": time_status,
        "settlement_time_gap_from_event_end_hours": time_gap_hours,
    }


def build_event_inventory(
    events: Sequence[Mapping[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_rows = []
    cell_rows = []
    for event in events:
        event_id = str(event.get("id") or "")
        markets = event.get("markets", []) or []
        cells = canonicalize_cells(markets, asset_aliases=SOL_ALIASES)
        partition = assess_partition(cells)
        classifications = [
            classify_market(str(market.get("question") or ""), SOL_ALIASES).classification
            for market in markets
        ]
        settlement = _settlement_fields(event)
        if cells:
            event_type = "terminal_bucket_distribution"
        elif "path_dependent" in classifications:
            event_type = "path_dependent_or_unsupported"
        else:
            event_type = "unsupported"

        is_resolved = bool(event.get("closed"))
        settlement_verified = (
            settlement["settlement_reference"] is not None
            and settlement["settlement_time_status"] == "verified_from_rules"
        )
        is_candidate = bool(partition["is_complete_partition"] and is_resolved and settlement_verified)
        if not cells:
            exclusion_reason = "no_terminal_partition_cells"
        elif not is_resolved:
            exclusion_reason = "event_not_resolved"
        elif not settlement_verified:
            exclusion_reason = "settlement_rules_unverified"
        else:
            exclusion_reason = ";".join(partition["reason_codes"])

        market_by_id = {
            str(market.get("id") or market.get("conditionId") or ""): market
            for market in markets
        }
        raw_prices_available = True
        for sort_key, cell in enumerate(cells):
            market = market_by_id.get(str(cell["market_id"]), {})
            outcome_prices = _parsed_json_list(market.get("outcomePrices"))
            if not outcome_prices:
                raw_prices_available = False
            cell_rows.append(
                {
                    "event_id": event_id,
                    "cell_id": f"{event_id}_{sort_key:02d}",
                    "market_id": cell["market_id"],
                    "yes_token_id": cell["yes_token_id"],
                    "cell_type": cell["cell_type"],
                    "cell_low": cell["cell_low"],
                    "cell_high": cell["cell_high"],
                    "sort_key": sort_key,
                    "question": cell["question"],
                }
            )

        event_rows.append(
            {
                "event_id": event_id,
                "event_title": str(event.get("title") or ""),
                "asset": "SOL",
                "event_type": event_type,
                "event_start_time": event.get("startDate"),
                "event_end_time": event.get("endDate"),
                **settlement,
                "resolution_status": "resolved" if is_resolved else "unresolved",
                "number_of_cells": partition["number_of_cells"],
                "finite_bucket_width": _finite_bucket_width(cells),
                "has_left_tail": partition["has_left_tail"],
                "has_right_tail": partition["has_right_tail"],
                "has_overlap": partition["has_overlap"],
                "has_gap": partition["has_gap"],
                "raw_probability_sum_available": raw_prices_available if cells else False,
                "is_candidate_partition": is_candidate,
                "exclusion_reason": exclusion_reason,
                "manual_review_status": "pending" if is_candidate else "not_required",
            }
        )

    inventory = pd.DataFrame(event_rows)
    cells_frame = pd.DataFrame(cell_rows)
    if not inventory.empty:
        inventory = inventory.sort_values(["event_end_time", "event_id"], na_position="last").reset_index(drop=True)
    if not cells_frame.empty:
        cells_frame = cells_frame.sort_values(["event_id", "sort_key"]).reset_index(drop=True)
    return inventory, cells_frame


def _safe_term(search_term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", search_term.lower()).strip("_")


def write_polymarket_artifacts(
    raw_pages: Sequence[Mapping[str, Any]],
    inventory: pd.DataFrame,
    cells: pd.DataFrame,
    raw_dir: Path,
    processed_dir: Path,
    snapshot_utc: str,
    search_terms: tuple[str, ...],
    max_pages: int,
) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    for page in raw_pages:
        path = raw_dir / f"polymarket_search_{_safe_term(str(page['search_term']))}_page_{page['page']}.json"
        path.write_text(
            json.dumps(page["payload"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    inventory.to_csv(processed_dir / "polymarket_event_inventory.csv", index=False, encoding="utf-8-sig")
    inventory.to_parquet(processed_dir / "polymarket_event_inventory.parquet", index=False)
    cells.to_csv(processed_dir / "polymarket_event_cells.csv", index=False, encoding="utf-8-sig")
    cells.to_parquet(processed_dir / "polymarket_event_cells.parquet", index=False)

    candidate = inventory[inventory["is_candidate_partition"]] if not inventory.empty else inventory
    metadata = {
        "data_snapshot_utc": snapshot_utc,
        "source_endpoint": GAMMA_SEARCH_URL,
        "request": {
            "search_terms": list(search_terms),
            "max_pages_per_term": max_pages,
            "limit_per_type": 100,
        },
        "row_counts": {
            "raw_pages": len(raw_pages),
            "discovered_events": int(len(inventory)),
            "candidate_events": int(len(candidate)),
            "candidate_expiries": int(candidate["settlement_timestamp"].nunique()) if not candidate.empty else 0,
            "cell_rows": int(len(cells)),
        },
        "classification_status": "automated_pending_manual_review",
        "outputs": {
            "event_inventory": "data/processed/p3_sol/polymarket_event_inventory.parquet",
            "event_cells": "data/processed/p3_sol/polymarket_event_cells.parquet",
        },
    }
    (processed_dir / "polymarket_feasibility_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metadata
