from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pandas as pd
import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "P2_diagnostics"
    / "build_frozen_input_manifest.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("build_frozen_input_manifest", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_file_record_captures_content_and_schema(tmp_path: Path) -> None:
    module = load_module()
    parquet_path = tmp_path / "sample.parquet"
    pd.DataFrame({"event_id": [1, 2], "value": [0.25, 0.75]}).to_parquet(parquet_path, index=False)

    record = module.file_record(parquet_path)

    assert record["sha256"] == hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    assert record["bytes"] == parquet_path.stat().st_size
    assert record["rows"] == 2
    assert record["columns"] == ["event_id", "value"]


def test_frozen_input_list_contains_every_freeze_dependency() -> None:
    module = load_module()

    assert module.FROZEN_INPUTS == (
        "data/processed/panels/trackA_event_day_quality.parquet",
        "data/processed/panels/trackA_event_day_divergence.parquet",
        "data/processed/panels/daily_distribution_comparison.parquet",
        "data/processed/panels/trackA_event_day_divergence_smooth005.parquet",
        "data/processed/panels/trackA_event_day_divergence_smooth02.parquet",
        "data/processed/deribit/deribit_curve_fits.parquet",
        "data/processed/deribit/deribit_state_price_grid.parquet",
        "data/processed/deribit/deribit_bar_quality_60.parquet",
        "data/processed/polymarket/event_universe.parquet",
        "data/processed/polymarket/event_cells.parquet",
        "data/processed/polymarket/polymarket_distribution_hourly.parquet",
    )


def test_build_manifest_reports_all_missing_inputs(tmp_path: Path) -> None:
    module = load_module()

    with pytest.raises(FileNotFoundError) as exc_info:
        module.build_manifest(tmp_path)

    message = str(exc_info.value)
    assert module.FROZEN_INPUTS[0] in message
    assert module.FROZEN_INPUTS[-1] in message
