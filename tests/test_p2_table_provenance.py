from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "P2_diagnostics" / "build_p1_table_provenance.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_p1_table_provenance", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_script_command_separates_path_and_arguments() -> None:
    module = load_module()

    script, args = module.parse_script_command(
        "scripts/P1_pipeline/build_trackB_deribit_survival_panel.py --bar-hours 6"
    )

    assert script == "scripts/P1_pipeline/build_trackB_deribit_survival_panel.py"
    assert args == ["--bar-hours", "6"]


def test_build_entries_records_real_artifact_existence(tmp_path: Path) -> None:
    module = load_module()
    tables_dir = tmp_path / "paper" / "tables"
    script_path = tmp_path / "scripts" / "P1_pipeline" / "build_demo.py"
    input_path = tmp_path / "data" / "processed" / "demo.parquet"
    metadata_path = tmp_path / "data" / "processed" / "demo_metadata.json"
    tables_dir.mkdir(parents=True)
    script_path.parent.mkdir(parents=True)
    input_path.parent.mkdir(parents=True)
    (tables_dir / "tab_demo.csv").write_text("name,value\na,1\nb,2\n", encoding="utf-8-sig")
    (tables_dir / "tab_demo.tex").write_text("table", encoding="utf-8")
    script_path.write_text("print('demo')\n", encoding="utf-8")
    input_path.write_bytes(b"parquet fixture")
    metadata_path.write_text("{}\n", encoding="utf-8")
    source_groups = [
        {
            "prefixes": ["tab_demo"],
            "script": "scripts/P1_pipeline/build_demo.py --mode frozen",
            "inputs": ["data/processed/demo.parquet"],
            "metadata": "data/processed/demo_metadata.json",
            "paper_use": "fixture",
            "sample_gate": "fixture",
        }
    ]

    with (
        patch.object(module, "PROJECT_ROOT", tmp_path),
        patch.object(module, "TABLES_DIR", tables_dir),
        patch.object(module, "SOURCE_GROUPS", source_groups),
    ):
        entry = module.build_entries()[0]

    assert entry["rows"] == 2
    assert entry["script_file"] == "scripts/P1_pipeline/build_demo.py"
    assert entry["script_args"] == ["--mode", "frozen"]
    assert entry["script_file_exists"] is True
    assert entry["input_files"] == [
        {"path": "data/processed/demo.parquet", "exists": True}
    ]
    assert entry["metadata_file_exists"] is True
    assert entry["tex_file_exists"] is True
