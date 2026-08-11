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
from scripts.P3_asset_extension.deribit_ohlc_feasibility import (
    DERIBIT_CHART,
    build_bar_quality,
    build_probe_grid,
    download_probe_grid,
    probe_cache_key,
    select_smoke_event_ids,
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


def run_deribit_ohlc(
    config_path: Path,
    smoke_events: int,
    extension_steps: int,
    max_instruments: int | None,
    force_download: bool,
) -> None:
    config = load_config(config_path)
    validate_config(config)
    processed_dir = PROJECT_ROOT / config["output_paths"]["processed_dir"]
    raw_dir = PROJECT_ROOT / config["output_paths"]["raw_dir"]
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    events = pd.read_parquet(processed_dir / "polymarket_event_inventory.parquet")
    cells = pd.read_parquet(processed_dir / "polymarket_event_cells.parquet")
    matches = pd.read_parquet(processed_dir / "deribit_expiry_match.parquet")
    event_ids = select_smoke_event_ids(matches, sample_size=smoke_events)
    grid = build_probe_grid(events, cells, matches, event_ids, extension_steps=extension_steps)
    inherited = config["inherited_track_a_parameters"]
    resolution = str(inherited["resolution"])
    cache_key = probe_cache_key(grid, resolution=resolution, max_instruments=max_instruments)
    requested_grid = grid if max_instruments is None else grid.head(max_instruments)

    raw_ohlc_path = raw_dir / f"deribit_ohlc_smoke_{cache_key}.parquet"
    raw_diagnostics_path = raw_dir / f"deribit_ohlc_instrument_diagnostics_{cache_key}.parquet"
    cache_manifest_path = raw_dir / f"deribit_ohlc_smoke_{cache_key}_manifest.json"
    diagnostics_path = processed_dir / "deribit_ohlc_instrument_diagnostics.parquet"
    cache_complete = raw_ohlc_path.exists() and raw_diagnostics_path.exists() and cache_manifest_path.exists()
    if cache_complete and not force_download:
        ohlc = pd.read_parquet(raw_ohlc_path)
        diagnostics = pd.read_parquet(raw_diagnostics_path)
        source = "cached"
    else:
        ohlc, diagnostics = download_probe_grid(
            grid,
            max_instruments=max_instruments,
            resolution=resolution,
        )
        ohlc.to_parquet(raw_ohlc_path, index=False)
        diagnostics.to_parquet(raw_diagnostics_path, index=False)
        cache_manifest_path.write_text(
            json.dumps(
                {
                    "cache_key": cache_key,
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "resolution": resolution,
                    "extension_steps": extension_steps,
                    "max_instruments": max_instruments,
                    "selected_event_ids": list(event_ids),
                    "requested_instrument_names": requested_grid["instrument_name"].tolist(),
                    "raw_ohlc_path": str(raw_ohlc_path.relative_to(PROJECT_ROOT)),
                    "raw_diagnostics_path": str(raw_diagnostics_path.relative_to(PROJECT_ROOT)),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        source = "downloaded"

    quality = build_bar_quality(
        ohlc,
        minimum_fresh_strikes=int(inherited["minimum_fresh_strikes"]),
        maximum_stale_bar_share=float(inherited["maximum_stale_bar_share"]),
    )
    ohlc.to_csv(processed_dir / "deribit_ohlc_probe.csv", index=False, encoding="utf-8-sig")
    if not ohlc.empty:
        ohlc.to_parquet(processed_dir / "deribit_ohlc_probe.parquet", index=False)
    diagnostics.to_csv(
        processed_dir / "deribit_ohlc_instrument_diagnostics.csv", index=False, encoding="utf-8-sig"
    )
    diagnostics.to_parquet(diagnostics_path, index=False)
    quality.to_csv(processed_dir / "deribit_bar_quality.csv", index=False, encoding="utf-8-sig")
    if not quality.empty:
        quality.to_parquet(processed_dir / "deribit_bar_quality.parquet", index=False)

    metadata_path = processed_dir / "deribit_feasibility_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    passing = quality[quality["curve_quality_pass"]] if not quality.empty else quality
    metadata["historical_ohlc_probe"] = {
        "data_snapshot_utc": datetime.now(timezone.utc).isoformat(),
        "source_endpoint": DERIBIT_CHART,
        "source": source,
        "parameters": {
            "scope": "smoke",
            "resolution": resolution,
            "extension_steps": extension_steps,
            "selected_event_ids": list(event_ids),
            "selection_rule": "earliest/middle/latest exact expiry matches",
            "max_instruments": max_instruments,
            "cache_key": cache_key,
            "cache_manifest": str(cache_manifest_path.relative_to(PROJECT_ROOT)),
        },
        "row_counts": {
            "grid_instruments": int(len(grid)),
            "requested_instruments": int(len(diagnostics)),
            "requested_expiries": int(requested_grid["expiry_timestamp"].nunique()),
            "instruments_with_ohlc": int((diagnostics["ohlc_rows"] > 0).sum()),
            "instruments_with_real_trades": int((diagnostics["real_trade_rows"] > 0).sum()),
            "instrument_not_found": int(diagnostics["chart_status"].eq("instrument_not_found").sum()),
            "instruments_with_no_data": int(diagnostics["chart_status"].eq("no_data").sum()),
            "ohlc_rows": int(len(ohlc)),
            "event_days_observed": int(len(quality)),
            "passing_event_days": int(len(passing)),
            "passing_events": int(passing["event_id"].nunique()) if not passing.empty else 0,
            "passing_expiries": int(
                ohlc[ohlc["event_id"].astype(str).isin(passing["event_id"].astype(str))][
                    "expiry_timestamp"
                ].nunique()
            )
            if not passing.empty
            else 0,
        },
        "quality_gate": {
            "minimum_fresh_strikes": inherited["minimum_fresh_strikes"],
            "maximum_stale_bar_share": inherited["maximum_stale_bar_share"],
            "requires_fresh_calls_and_puts": True,
        },
        "known_caveats": [
            "Daily bars establish within-day trading but do not expose exact cross-strike trade timestamps.",
            "The three-event smoke sample is selected mechanically and is not the final all-candidate panel.",
            "Instrument-level API failures remain in deribit_ohlc_instrument_diagnostics instead of being dropped.",
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"selected_event_ids: {','.join(event_ids)}")
    for key, value in metadata["historical_ohlc_probe"]["row_counts"].items():
        print(f"{key}: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded P3 feasibility stages.")
    parser.add_argument("--stage", choices=("polymarket", "deribit", "deribit-ohlc"), required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--max-abs-days", type=int, default=3)
    parser.add_argument("--smoke-events", type=int, default=3)
    parser.add_argument("--extension-steps", type=int, default=6)
    parser.add_argument("--max-instruments", type=int, default=None)
    parser.add_argument("--force-download", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.stage == "polymarket":
        run_polymarket(args.config, args.max_pages)
    elif args.stage == "deribit":
        run_deribit(args.config, args.max_abs_days)
    elif args.stage == "deribit-ohlc":
        run_deribit_ohlc(
            args.config,
            smoke_events=args.smoke_events,
            extension_steps=args.extension_steps,
            max_instruments=args.max_instruments,
            force_download=args.force_download,
        )


if __name__ == "__main__":
    main()
