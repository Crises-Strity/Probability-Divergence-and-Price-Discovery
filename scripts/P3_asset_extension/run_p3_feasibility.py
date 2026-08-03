"""Run bounded P3 feasibility collection stages without estimating Track A."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


IMPORT_ROOT = Path(__file__).resolve().parents[2]
if str(IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(IMPORT_ROOT))

from scripts.P3_asset_extension.p3_config import DEFAULT_CONFIG, PROJECT_ROOT, load_config, validate_config
from scripts.P3_asset_extension.deribit_feasibility import (
    DERIBIT_GET_INSTRUMENT,
    build_expiry_match_tables,
)
from scripts.P3_asset_extension.polymarket_feasibility import (
    build_event_inventory,
    discover_events,
    write_polymarket_artifacts,
)


def run_polymarket(config_path: Path, max_pages: int | None) -> None:
    config = load_config(config_path)
    validate_config(config)
    search_terms = tuple(config["discovery"]["search_terms"])
    configured_limit = config["p3_feasibility_overrides"]["small_probe_limits"]["polymarket_max_pages_per_term"]
    page_limit = max_pages if max_pages is not None else configured_limit
    if page_limit > configured_limit:
        raise ValueError(f"max_pages cannot exceed frozen preparation limit {configured_limit}.")

    events, raw_pages = discover_events(search_terms, page_limit)
    inventory, cells = build_event_inventory(events)
    outputs = config["output_paths"]
    metadata = write_polymarket_artifacts(
        raw_pages=raw_pages,
        inventory=inventory,
        cells=cells,
        raw_dir=PROJECT_ROOT / outputs["raw_dir"],
        processed_dir=PROJECT_ROOT / outputs["processed_dir"],
        snapshot_utc=datetime.now(timezone.utc).isoformat(),
        search_terms=search_terms,
        max_pages=page_limit,
    )
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value}")


def run_deribit(config_path: Path, max_abs_days: int) -> None:
    config = load_config(config_path)
    validate_config(config)
    processed_dir = PROJECT_ROOT / config["output_paths"]["processed_dir"]
    events = pd.read_parquet(processed_dir / "polymarket_event_inventory.parquet")
    cells = pd.read_parquet(processed_dir / "polymarket_event_cells.parquet")
    matches, instruments = build_expiry_match_tables(
        events=events,
        cells=cells,
        max_abs_days=max_abs_days,
    )

    matches.to_csv(processed_dir / "deribit_expiry_match.csv", index=False, encoding="utf-8-sig")
    matches.to_parquet(processed_dir / "deribit_expiry_match.parquet", index=False)
    instruments.to_csv(processed_dir / "deribit_instrument_inventory.csv", index=False, encoding="utf-8-sig")
    if not instruments.empty:
        instruments.to_parquet(processed_dir / "deribit_instrument_inventory.parquet", index=False)

    matched = matches[matches["match_status"] == "matched_verified_metadata"]
    metadata = {
        "data_snapshot_utc": datetime.now(timezone.utc).isoformat(),
        "source_endpoint": DERIBIT_GET_INSTRUMENT,
        "parameters": {
            "max_abs_days": max_abs_days,
            "representative_strikes_per_event": 3,
            "option_sides": ["call", "put"],
        },
        "row_counts": {
            "candidate_events": int(len(matches)),
            "matched_events": int(len(matched)),
            "matched_expiries": int(matched["deribit_expiry_timestamp"].nunique()) if not matched.empty else 0,
            "exact_or_close_events": int(matched["mapping_quality"].isin(["exact", "close"]).sum()) if not matched.empty else 0,
            "loose_events": int((matched["mapping_quality"] == "loose").sum()) if not matched.empty else 0,
            "unmatched_or_unmappable_events": int((matches["mapping_quality"] == "unmappable").sum()),
            "api_requests": int(matches["probe_request_count"].sum()),
            "instrument_rows": int(len(instruments)),
        },
        "contract_units_verified_for_all_matches": bool(matched["contract_units_verified"].all()) if not matched.empty else False,
        "outputs": {
            "expiry_match": "data/processed/p3_sol/deribit_expiry_match.parquet",
            "instrument_inventory": "data/processed/p3_sol/deribit_instrument_inventory.parquet",
        },
        "remaining_gate": "Historical OHLC and full cross-strike freshness must pass before estimator implementation.",
    }
    (processed_dir / "deribit_feasibility_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded P3 feasibility stages.")
    parser.add_argument("--stage", choices=("polymarket", "deribit"), required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--max-abs-days", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.stage == "polymarket":
        run_polymarket(args.config, args.max_pages)
    elif args.stage == "deribit":
        run_deribit(args.config, args.max_abs_days)


if __name__ == "__main__":
    main()
