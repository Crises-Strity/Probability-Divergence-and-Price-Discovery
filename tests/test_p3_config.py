import json
from pathlib import Path

import pytest

from scripts.P3_asset_extension.p3_config import (
    build_run_snapshot,
    load_config,
    validate_config,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "p3_track_a_extension.json"


def test_p3_config_inherits_frozen_track_a_parameters() -> None:
    config = load_config(CONFIG_PATH)

    inherited = config["inherited_track_a_parameters"]
    assert inherited["resolution"] == "1D"
    assert inherited["smooth_weight"] == 0.10
    assert inherited["minimum_fresh_strikes"] == 8
    assert inherited["maximum_stale_bar_share"] == 0.30
    assert inherited["state_grid_lower_multiplier"] == 0.5
    assert inherited["state_grid_upper_multiplier"] == 1.5
    assert inherited["open_tail_midpoint_widths"] == 0.5


def test_p3_config_freezes_candidate_and_final_gates() -> None:
    config = load_config(CONFIG_PATH)

    overrides = config["p3_feasibility_overrides"]
    assert overrides["primary_candidate"] == "SOL"
    assert overrides["backup_candidate"] == "XRP"
    assert overrides["candidate_panel_gates"] == {
        "pass_min_events": 10,
        "pass_min_expiries": 3,
        "limited_pass_min_events": 5,
        "limited_pass_min_expiries": 2,
    }
    assert overrides["final_panel_gates"] == {
        "pass_min_event_days": 30,
        "pass_min_events": 10,
        "pass_min_expiries": 3,
        "limited_pass_min_event_days": 15,
        "limited_pass_min_events": 5,
        "limited_pass_min_expiries": 2,
        "maximum_single_event_share": 0.25,
    }


def test_p3_config_does_not_activate_coin_rmse_for_sol() -> None:
    config = load_config(CONFIG_PATH)

    assert config["contract_fit_tolerance"]["status"] == "deferred"
    assert config["contract_fit_tolerance"]["unit"] is None
    assert config["contract_fit_tolerance"]["value"] is None
    validate_config(config)


def test_validator_rejects_coin_rmse_for_sol() -> None:
    config = load_config(CONFIG_PATH)
    config["contract_fit_tolerance"] = {
        "status": "active",
        "unit": "coin",
        "value": 0.02,
    }

    with pytest.raises(ValueError, match="coin-denominated RMSE"):
        validate_config(config)


def test_run_snapshot_records_provenance_without_mutating_source() -> None:
    config = load_config(CONFIG_PATH)
    before = json.loads(json.dumps(config))

    snapshot = build_run_snapshot(
        config,
        project_root=PROJECT_ROOT,
        snapshot_utc="2026-08-03T12:00:00Z",
    )

    assert config == before
    assert snapshot["data_snapshot_utc"] == "2026-08-03T12:00:00Z"
    assert len(snapshot["git_commit"]) == 40
    assert snapshot["deterministic"] is True
    assert snapshot["p3_feasibility_overrides"]["primary_candidate"] == "SOL"
    assert snapshot["output_paths"]["processed_dir"] == "data/processed/p3_sol"

