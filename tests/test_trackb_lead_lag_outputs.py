from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "P1_pipeline" / "build_trackB_lead_lag_panel.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_trackB_lead_lag_panel", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_join_panel_writes_only_frozen_coverage_table(tmp_path: Path) -> None:
    module = load_module()
    summary = pd.DataFrame({"events": [79], "total_joined_hours": [10739]})

    with patch.object(module, "TABLES_DIR", tmp_path):
        module.write_paper_tables(summary, bar_hours=1)

    assert (tmp_path / "tab_trackB_joint_survival_coverage.csv").exists()
    assert (tmp_path / "tab_trackB_joint_survival_coverage.tex").exists()
    assert not (tmp_path / "tab_trackB_frequency_diagnostics.csv").exists()
    assert not (tmp_path / "tab_trackB_frequency_diagnostics.tex").exists()
