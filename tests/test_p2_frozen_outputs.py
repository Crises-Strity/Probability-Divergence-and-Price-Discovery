from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "P2_diagnostics" / "verify_p2_freeze.py"
COMMIT = "a" * 40


def load_module():
    spec = importlib.util.spec_from_file_location("verify_p2_freeze", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def build_complete_fixture(root: Path) -> None:
    tables_dir = root / "paper" / "tables"
    script_path = root / "scripts" / "P1_pipeline" / "build_fixture.py"
    input_path = root / "data" / "processed" / "fixture_input.parquet"
    tables_dir.mkdir(parents=True)
    script_path.parent.mkdir(parents=True)
    input_path.parent.mkdir(parents=True)
    script_path.write_text("print('fixture')\n", encoding="utf-8")
    pd.DataFrame({"value": [1]}).to_parquet(input_path, index=False)

    track_a_metadata = "data/processed/panels/trackA_diagnostics_summary.json"
    track_b_metadata = "data/processed/panels/trackB_lead_lag_diagnostics_summary.json"
    reference_metadata = "data/processed/panels/reference_basis_audit_metadata.json"
    write_json(
        root / track_a_metadata,
        {
            "git_commit": COMMIT,
            "row_counts": {
                "main_comparison_event_days": 294,
                "main_comparison_events": 61,
            },
        },
    )
    write_json(
        root / track_b_metadata,
        {
            "git_commit": COMMIT,
            "row_counts": {
                "informative_rows": 1121,
                "regression_rows": 703,
            },
        },
    )
    write_json(
        root / reference_metadata,
        {
            "git_commit": COMMIT,
            "row_counts": {"audit_rows": 124},
            "status_counts": {"proxy_assumed": 124},
        },
    )

    entries = []
    metadata_cycle = [track_a_metadata, track_b_metadata, reference_metadata]
    for index in range(30):
        stem = f"tab_fixture_{index:02d}"
        csv_relative = f"paper/tables/{stem}.csv"
        tex_relative = f"paper/tables/{stem}.tex"
        (root / csv_relative).write_text("name,value\na,1\n", encoding="utf-8-sig")
        (root / tex_relative).write_text("table\n", encoding="utf-8")
        entries.append(
            {
                "table_stem": stem,
                "csv": csv_relative,
                "tex": tex_relative,
                "tex_file_exists": True,
                "rows": 1,
                "script": "scripts/P1_pipeline/build_fixture.py",
                "script_file": "scripts/P1_pipeline/build_fixture.py",
                "script_args": [],
                "script_file_exists": True,
                "input_files": [
                    {"path": "data/processed/fixture_input.parquet", "exists": True}
                ],
                "metadata_file": metadata_cycle[index % len(metadata_cycle)],
                "metadata_file_exists": True,
            }
        )
    write_json(
        tables_dir / "table_source_metadata.json",
        {"git_commit": COMMIT, "table_count": 30, "entries": entries},
    )

    manifest_files = []
    for index in range(11):
        relative = f"data/processed/frozen/input_{index:02d}.parquet"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"event_id": [index], "value": [index / 10]}).to_parquet(path, index=False)
        manifest_files.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
                "rows": 1,
                "columns": ["event_id", "value"],
            }
        )
    write_json(
        root / "data" / "processed" / "frozen_input_manifest.json",
        {"file_count": 11, "files": manifest_files},
    )


def test_validate_freeze_accepts_complete_fixture(tmp_path: Path) -> None:
    module = load_module()
    build_complete_fixture(tmp_path)

    assert module.validate_freeze(tmp_path, expected_git_commit=COMMIT) == []


def test_validate_freeze_reports_independent_failures_together(tmp_path: Path) -> None:
    module = load_module()
    build_complete_fixture(tmp_path)
    provenance_path = tmp_path / "paper" / "tables" / "table_source_metadata.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["table_count"] = 29
    provenance["entries"][0]["script_file"] = "scripts/build_fixture.py"
    provenance["entries"][1]["rows"] = 99
    write_json(provenance_path, provenance)
    track_b_path = (
        tmp_path / "data" / "processed" / "panels" / "trackB_lead_lag_diagnostics_summary.json"
    )
    track_b = json.loads(track_b_path.read_text(encoding="utf-8"))
    track_b["row_counts"]["regression_rows"] = 702
    write_json(track_b_path, track_b)

    errors = module.validate_freeze(tmp_path, expected_git_commit="bad-hash")

    assert any("table_count" in error for error in errors)
    assert any("legacy script path" in error for error in errors)
    assert any("row count" in error for error in errors)
    assert any("regression_rows" in error for error in errors)
    assert any("40-character" in error for error in errors)


def test_table_hashes_change_when_a_table_changes(tmp_path: Path) -> None:
    module = load_module()
    tables_dir = tmp_path / "paper" / "tables"
    tables_dir.mkdir(parents=True)
    table_path = tables_dir / "tab_example.csv"
    table_path.write_text("value\n1\n", encoding="utf-8-sig")
    first = module.table_hashes(tmp_path)

    table_path.write_text("value\n2\n", encoding="utf-8-sig")
    second = module.table_hashes(tmp_path)

    assert first != second
