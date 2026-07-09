"""
Build a strict Polymarket crypto price-event inventory.

Outputs are written inside this project:
- data/raw/polymarket/polymarket_public_search_events.json
- data/raw/polymarket/polymarket_market_inventory.{csv,parquet}
- data/processed/polymarket/market_pair_candidate_inventory.{csv,parquet}
- data/processed/polymarket/event_distribution_quality.csv
- data/processed/polymarket/phase0_metadata.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import time
from calendar import monthrange
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dateutil.relativedelta import relativedelta


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "polymarket"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "polymarket"

GAMMA = "https://gamma-api.polymarket.com"
HEADERS = {"User-Agent": "ucl-dissertation-research/0.2"}
SEARCH_KEYWORDS = ("bitcoin", "ethereum", "bitcoin price", "ethereum price")

MONTHS = {
    name.lower(): i
    for i, name in enumerate(
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        start=1,
    )
}

AMOUNT_RE = re.compile(r"\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*([kK])?")
DATE_RE = re.compile(
    r"\bon\s+("
    r"January|February|March|April|May|June|July|August|September|October|November|December"
    r")\s+(\d{1,2})\b",
    re.IGNORECASE,
)
INTRADAY_RE = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s*(?:AM|PM)\s*ET\b"
    r"|\b\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}\s*(?:AM|PM)?\s*ET\b",
    re.IGNORECASE,
)
BUCKET_RE = re.compile(
    r"between\s+\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*([kK])?\s*"
    r"(?:and|to|-|–|—)\s*"
    r"\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*([kK])?",
    re.IGNORECASE,
)


def fetch_events(keyword: str, limit: int, max_pages: int, sleep_seconds: float) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for page in range(max_pages):
        response = requests.get(
            f"{GAMMA}/public-search",
            params={"q": keyword, "limit_per_type": limit, "page": page},
            headers=HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        page_events = payload.get("events", [])
        if not page_events:
            break

        events.extend(page_events)
        pagination = payload.get("pagination", {})
        if not pagination.get("hasMore", False):
            break
        time.sleep(sleep_seconds)

    return events


def json_load(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def as_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return math.nan
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_amount(value: str, suffix: str | None) -> float:
    amount = float(value.replace(",", ""))
    if suffix and suffix.lower() == "k":
        amount *= 1_000
    return amount


def money_amounts(question: str) -> list[float]:
    values: list[float] = []
    for match in AMOUNT_RE.finditer(question):
        value = parse_amount(match.group(1), match.group(2))
        if value >= 1_000:
            values.append(value)
    return values


def parse_question_date(question: str, settlement_time: datetime | None) -> tuple[datetime | None, int | None, int | None]:
    match = DATE_RE.search(question)
    if not match:
        return None, None, None

    month = MONTHS[match.group(1).lower()]
    day = int(match.group(2))
    if settlement_time is None:
        return None, month, day

    candidates = []
    for year in [settlement_time.year - 1, settlement_time.year, settlement_time.year + 1]:
        try:
            candidate = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            continue
        distance = abs((settlement_time.date() - candidate.date()).days)
        candidates.append((distance, candidate))

    if not candidates:
        return None, month, day
    return min(candidates, key=lambda x: x[0])[1], month, day


def last_friday_monthly_expiry(year: int, month: int) -> datetime:
    last_day = monthrange(year, month)[1]
    expiry = datetime(year, month, last_day, 8, 0, tzinfo=timezone.utc)
    while expiry.weekday() != 4:
        expiry -= relativedelta(days=1)
    return expiry


def nearby_months(dt: datetime, months_each_side: int = 2) -> list[tuple[int, int]]:
    months = []
    base = datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)
    for offset in range(-months_each_side, months_each_side + 1):
        shifted = base + relativedelta(months=offset)
        months.append((shifted.year, shifted.month))
    return months


def nearest_deribit_monthly_expiry(settlement_time: datetime | None) -> tuple[datetime | None, float, float, int | None, str]:
    if settlement_time is None:
        return None, math.nan, math.nan, None, "unmappable"

    expiries = [last_friday_monthly_expiry(year, month) for year, month in nearby_months(settlement_time)]
    nearest = min(expiries, key=lambda expiry: abs((settlement_time - expiry).total_seconds()))
    gap_hours = (settlement_time - nearest).total_seconds() / 3600
    abs_gap_hours = abs(gap_hours)
    calendar_gap_days = (settlement_time.date() - nearest.date()).days

    if abs(calendar_gap_days) == 0:
        quality = "exact"
    elif abs_gap_hours <= 48:
        quality = "close"
    elif abs_gap_hours <= 120:
        quality = "loose"
    else:
        quality = "unmappable"
    return nearest, gap_hours, abs_gap_hours, calendar_gap_days, quality


def classify_question(question: str) -> dict[str, Any] | None:
    q = question.lower()
    is_btc = ("bitcoin" in q) or re.search(r"\bbtc\b", q) is not None
    is_eth = ("ethereum" in q) or re.search(r"\beth\b", q) is not None
    asset = "BTC" if is_btc else ("ETH" if is_eth else None)
    if asset is None:
        return None

    has_intraday_time = INTRADAY_RE.search(question) is not None
    if "up or down" in q:
        qtype = "intraday_binary"
    else:
        touch_terms = [
            "reach",
            "hit",
            "touch",
            "dip to",
            "fall to",
            "drop to",
            "climb to",
            "rise to",
            "anytime",
            "ever",
        ]
        is_touch = any(term in q for term in touch_terms)
        is_bucket = ("between" in q) or (BUCKET_RE.search(question) is not None)
        is_point = any(
            term in q
            for term in [
                "above",
                "below",
                "greater than",
                "less than",
                "be at",
                "exceed",
                "close above",
                "close below",
            ]
        )
        if is_touch:
            qtype = "touch_barrier"
        elif is_bucket:
            qtype = "terminal_bucket"
        elif is_point:
            qtype = "terminal_point"
        else:
            qtype = "unknown"

    direction = None
    if qtype == "terminal_point":
        if any(term in q for term in ["above", "greater than", "exceed", "close above"]):
            direction = "above"
        elif any(term in q for term in ["below", "less than", "close below"]):
            direction = "below"

    strike_low = math.nan
    strike_high = math.nan
    bucket_width = math.nan
    parse_status = "ok"

    if qtype == "terminal_bucket":
        bucket_match = BUCKET_RE.search(question)
        if bucket_match:
            strike_low = parse_amount(bucket_match.group(1), bucket_match.group(2))
            strike_high = parse_amount(bucket_match.group(3), bucket_match.group(4))
            if strike_high < strike_low:
                strike_low, strike_high = strike_high, strike_low
            bucket_width = strike_high - strike_low
        else:
            amounts = money_amounts(question)
            if len(amounts) >= 2:
                strike_low = min(amounts[:2])
                strike_high = max(amounts[:2])
                bucket_width = strike_high - strike_low
            else:
                parse_status = "missing_bucket_bounds"
    elif qtype in {"terminal_point", "touch_barrier"}:
        amounts = money_amounts(question)
        if amounts:
            strike_low = amounts[0]
            strike_high = amounts[0]
            bucket_width = 0.0
        else:
            parse_status = "missing_strike"

    return {
        "asset": asset,
        "qtype": qtype,
        "direction": direction,
        "strike_low": strike_low,
        "strike_high": strike_high,
        "bucket_width": bucket_width,
        "has_intraday_time": has_intraday_time,
        "parse_status": parse_status,
    }


def outcome_price(outcome_prices: Any, index: int) -> float:
    prices = json_load(outcome_prices)
    if isinstance(prices, list) and len(prices) > index:
        return as_float(prices[index])
    return math.nan


def build_market_rows(events: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen_market_ids: set[str] = set()

    for event in events:
        event_id = event.get("id")
        event_title = event.get("title")
        event_slug = event.get("slug")

        for market in event.get("markets", []):
            market_id = market.get("id") or market.get("conditionId")
            if not market_id or market_id in seen_market_ids:
                continue
            seen_market_ids.add(str(market_id))

            question = market.get("question") or ""
            classified = classify_question(question)
            if classified is None:
                continue

            settlement_time = parse_dt(market.get("endDateIso") or market.get("endDate"))
            question_date, question_month, question_day = parse_question_date(question, settlement_time)
            expiry, gap_hours, abs_gap_hours, calendar_gap_days, mapping_quality = nearest_deribit_monthly_expiry(
                settlement_time
            )

            yes_price = outcome_price(market.get("outcomePrices"), 0)
            no_price = outcome_price(market.get("outcomePrices"), 1)
            yes_no_sum = yes_price + no_price if not math.isnan(yes_price) and not math.isnan(no_price) else math.nan

            rows.append(
                {
                    "event_id": event_id,
                    "event_title": event_title,
                    "event_slug": event_slug,
                    "market_id": market_id,
                    "condition_id": market.get("conditionId"),
                    "question": question,
                    **classified,
                    "question_date": question_date,
                    "question_month": question_month,
                    "question_day": question_day,
                    "settlement_time": settlement_time,
                    "settlement_date": settlement_time.date() if settlement_time else None,
                    "nearest_deribit_monthly_expiry": expiry,
                    "time_gap_hours": gap_hours,
                    "abs_time_gap_hours": abs_gap_hours,
                    "calendar_gap_days": calendar_gap_days,
                    "mapping_quality": mapping_quality,
                    "closed": as_bool(market.get("closed")),
                    "volume": as_float(market.get("volumeNum") or market.get("volume")),
                    "liquidity": as_float(market.get("liquidityNum") or market.get("liquidity")),
                    "spread": as_float(market.get("spread")),
                    "best_bid": as_float(market.get("bestBid")),
                    "best_ask": as_float(market.get("bestAsk")),
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "yes_no_price_sum": yes_no_sum,
                    "yes_no_parity_gap": 1.0 - yes_no_sum if not math.isnan(yes_no_sum) else math.nan,
                    "outcomes": market.get("outcomes"),
                    "outcome_prices": market.get("outcomePrices"),
                }
            )

    return pd.DataFrame(rows)


def dedupe_buckets(bucket_df: pd.DataFrame) -> pd.DataFrame:
    if bucket_df.empty:
        return bucket_df
    cols = ["strike_low", "strike_high"]
    return (
        bucket_df.sort_values(["strike_low", "strike_high", "volume"], ascending=[True, True, False])
        .groupby(cols, as_index=False)
        .agg(
            yes_price=("yes_price", "mean"),
            volume=("volume", "sum"),
            spread=("spread", "median"),
            bucket_width=("bucket_width", "median"),
        )
        .sort_values(["strike_low", "strike_high"])
    )


def point_monotonicity_violations(point_df: pd.DataFrame, direction: str) -> int:
    sub = point_df[(point_df["direction"] == direction) & point_df["yes_price"].notna()].copy()
    if len(sub) < 2:
        return 0
    sub = sub.sort_values("strike_low")
    probs = sub["yes_price"].to_numpy()
    tolerance = 1e-6
    if direction == "above":
        return int(sum((probs[i + 1] - probs[i]) > tolerance for i in range(len(probs) - 1)))
    if direction == "below":
        return int(sum((probs[i] - probs[i + 1]) > tolerance for i in range(len(probs) - 1)))
    return 0


def build_event_quality(candidates: pd.DataFrame) -> pd.DataFrame:
    terminal = candidates[
        candidates["qtype"].isin(["terminal_point", "terminal_bucket"]) & ~candidates["has_intraday_time"]
    ].copy()
    rows: list[dict[str, Any]] = []

    for event_id, group in terminal.groupby("event_id", dropna=False):
        bucket = group[group["qtype"] == "terminal_bucket"].copy()
        point = group[group["qtype"] == "terminal_point"].copy()
        bucket_unique = dedupe_buckets(bucket)

        n_gaps = 0
        n_overlaps = 0
        if len(bucket_unique) >= 2:
            lows = bucket_unique["strike_low"].to_list()
            highs = bucket_unique["strike_high"].to_list()
            for i in range(len(bucket_unique) - 1):
                if lows[i + 1] > highs[i] + 1e-6:
                    n_gaps += 1
                elif lows[i + 1] < highs[i] - 1e-6:
                    n_overlaps += 1

        n_buckets = len(bucket_unique)
        bucket_price_sum = bucket_unique["yes_price"].sum(skipna=True) if n_buckets else math.nan
        bucket_widths = bucket_unique["bucket_width"].dropna()

        mapping_order = {"exact": 0, "close": 1, "loose": 2, "unmappable": 3}
        group_quality = group["mapping_quality"].dropna()
        best_quality = (
            min(group_quality, key=lambda value: mapping_order.get(str(value), 99)) if len(group_quality) else None
        )

        above_violations = point_monotonicity_violations(point, "above")
        below_violations = point_monotonicity_violations(point, "below")
        point_violations = above_violations + below_violations

        if best_quality in {"exact", "close"} and n_buckets >= 5 and n_gaps == 0 and n_overlaps == 0:
            distribution_quality = "clean_bucket_distribution"
        elif best_quality in {"exact", "close"} and len(point) >= 5 and point_violations == 0:
            distribution_quality = "usable_point_thresholds"
        elif best_quality in {"exact", "close", "loose"}:
            distribution_quality = "partial_or_weak"
        else:
            distribution_quality = "unmappable"

        rows.append(
            {
                "event_id": event_id,
                "event_title": group["event_title"].iloc[0],
                "asset": group["asset"].mode().iloc[0] if not group["asset"].mode().empty else None,
                "settlement_time": group["settlement_time"].iloc[0],
                "nearest_deribit_monthly_expiry": group["nearest_deribit_monthly_expiry"].iloc[0],
                "time_gap_hours": group["time_gap_hours"].median(),
                "abs_time_gap_hours": group["abs_time_gap_hours"].median(),
                "calendar_gap_days": group["calendar_gap_days"].median(),
                "mapping_quality": best_quality,
                "n_terminal_markets": len(group),
                "n_terminal_point": len(point),
                "n_terminal_bucket": len(bucket),
                "n_unique_buckets": n_buckets,
                "n_bucket_duplicates": max(len(bucket) - n_buckets, 0),
                "min_strike": group["strike_low"].min(skipna=True),
                "max_strike": group["strike_high"].max(skipna=True),
                "median_bucket_width": bucket_widths.median() if len(bucket_widths) else math.nan,
                "n_bucket_gaps": n_gaps,
                "n_bucket_overlaps": n_overlaps,
                "has_strike_gap": n_gaps > 0,
                "bucket_price_sum": bucket_price_sum,
                "bucket_price_sum_in_0p9_1p1": 0.9 <= bucket_price_sum <= 1.1 if not math.isnan(bucket_price_sum) else False,
                "point_monotonicity_violations": point_violations,
                "total_volume": group["volume"].sum(skipna=True),
                "median_spread": group["spread"].median(skipna=True),
                "distribution_quality": distribution_quality,
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["distribution_quality", "mapping_quality", "total_volume"],
        ascending=[True, True, False],
    )


def save_table(df: pd.DataFrame, csv_path: Path, parquet_path: Path | None = None) -> None:
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    if parquet_path is not None:
        df.to_parquet(parquet_path, index=False)


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


def write_metadata(events: list[dict[str, Any]], market_df: pd.DataFrame, event_quality: pd.DataFrame) -> None:
    terminal_mask = market_df["qtype"].isin(["terminal_point", "terminal_bucket"])
    terminal_intraday_mask = terminal_mask & market_df["has_intraday_time"]
    terminal_no_intraday_mask = terminal_mask & ~market_df["has_intraday_time"]
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": f"{GAMMA}/public-search",
        "search_keywords": list(SEARCH_KEYWORDS),
        "git_commit": git_commit(),
        "raw_event_count": len(events),
        "market_inventory_rows": len(market_df),
        "terminal_rows": int(terminal_mask.sum()),
        "terminal_intraday_rows": int(terminal_intraday_mask.sum()),
        "terminal_no_intraday_rows": int(terminal_no_intraday_mask.sum()),
        "terminal_intraday_rows_by_qtype": (
            market_df.loc[terminal_intraday_mask, "qtype"].value_counts(dropna=False).to_dict()
        ),
        "candidate_rows": int(terminal_no_intraday_mask.sum()),
        "event_quality_rows": len(event_quality),
        "mapping_quality_counts": market_df["mapping_quality"].value_counts(dropna=False).to_dict(),
        "qtype_counts": market_df["qtype"].value_counts(dropna=False).to_dict(),
        "notes": [
            "Deribit monthly expiry is approximated as last Friday 08:00 UTC until real Deribit instrument expiries are pulled.",
            "mapping_quality is based on Polymarket settlement_time versus nearest monthly Deribit expiry.",
            "bucket_price_sum is diagnostic only; it should be interpreted only for mutually exclusive and near-exhaustive bucket sets.",
        ],
    }
    (PROCESSED_DIR / "phase0_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--sleep-seconds", type=float, default=0.3)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    all_events: list[dict[str, Any]] = []
    for keyword in SEARCH_KEYWORDS:
        all_events.extend(fetch_events(keyword, args.limit, args.max_pages, args.sleep_seconds))

    events_by_id: dict[Any, dict[str, Any]] = {}
    for event in all_events:
        event_id = event.get("id")
        if event_id is not None and event_id not in events_by_id:
            events_by_id[event_id] = event
    events = list(events_by_id.values())

    (RAW_DIR / "polymarket_public_search_events.json").write_text(
        json.dumps(events, ensure_ascii=False),
        encoding="utf-8",
    )

    market_df = build_market_rows(events)
    if market_df.empty:
        raise RuntimeError("No BTC/ETH crypto price markets were parsed from Polymarket public-search.")

    terminal_candidate = market_df[
        market_df["qtype"].isin(["terminal_point", "terminal_bucket"]) & ~market_df["has_intraday_time"]
    ].copy()
    event_quality = build_event_quality(market_df)

    save_table(
        market_df,
        RAW_DIR / "polymarket_market_inventory.csv",
        RAW_DIR / "polymarket_market_inventory.parquet",
    )
    save_table(
        terminal_candidate,
        PROCESSED_DIR / "market_pair_candidate_inventory.csv",
        PROCESSED_DIR / "market_pair_candidate_inventory.parquet",
    )
    event_quality.to_csv(PROCESSED_DIR / "event_distribution_quality.csv", index=False, encoding="utf-8-sig")
    write_metadata(events, market_df, event_quality)

    print("\n=== Polymarket inventory built ===")
    print(f"raw events: {len(events):,}")
    print(f"market rows: {len(market_df):,}")
    print("\n=== qtype counts ===")
    print(market_df["qtype"].value_counts(dropna=False).to_string())
    print("\n=== mapping quality counts: terminal candidates only ===")
    print(terminal_candidate["mapping_quality"].value_counts(dropna=False).to_string())
    print("\n=== event distribution quality ===")
    print(event_quality["distribution_quality"].value_counts(dropna=False).to_string())
    print("\nOutputs:")
    print(f"- {RAW_DIR / 'polymarket_market_inventory.csv'}")
    print(f"- {PROCESSED_DIR / 'market_pair_candidate_inventory.csv'}")
    print(f"- {PROCESSED_DIR / 'event_distribution_quality.csv'}")


if __name__ == "__main__":
    main()
