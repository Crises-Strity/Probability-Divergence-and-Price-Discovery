"""Verify the frozen P2 result set and deterministic table outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


EXPECTED_TABLE_COUNT = 30
EXPECTED_FROZEN_INPUT_COUNT = 11
EXPECTED_TRACK_A_EVENT_DAYS = 294
EXPECTED_TRACK_A_EVENTS = 61
EXPECTED_TRACK_B_JOINT_INFORMATIVE_ROWS = 1121
EXPECTED_TRACK_B_REGRESSION_ROWS = 703
EXPECTED_REFERENCE_AUDIT_ROWS = 124
EXPECTED_REFERENCE_PROXY_ROWS = 124
GIT_HASH_PATTERN = re.compile(r"[0-9a-f]{40}")
ALLOWED_SCRIPT_PREFIXES = ("scripts/P1_pipeline/", "scripts/P2_diagnostics/")


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


def load_json(path: Path, errors: list[str], label: str) -> dict[str, Any] | None:
    if not path.exists():
        errors.append(f"missing {label}: {path}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        errors.append(f"invalid {label}: {path}: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"invalid {label}: expected JSON object at {path}")
        return None
    return payload


def csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def table_hashes(project_root: Path) -> dict[str, str]:
    tables_dir = project_root / "paper" / "tables"
    return {
        str(path.relative_to(project_root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(tables_dir.glob("tab_*.csv"))
    }


def validate_input_manifest(project_root: Path, errors: list[str]) -> None:
    manifest_path = project_root / "data" / "processed" / "frozen_input_manifest.json"
    manifest = load_json(manifest_path, errors, "frozen input manifest")
    if manifest is None:
        return

    files = manifest.get("files", [])
    if manifest.get("file_count") != EXPECTED_FROZEN_INPUT_COUNT or len(files) != EXPECTED_FROZEN_INPUT_COUNT:
        errors.append(
            "frozen input file_count mismatch: "
            f"expected {EXPECTED_FROZEN_INPUT_COUNT}, got {manifest.get('file_count')} / {len(files)} records"
        )
    for record in files:
        relative = record.get("path")
        if not isinstance(relative, str):
            errors.append("frozen input record has no valid path")
            continue
        path = project_root / relative
        if not path.exists():
            errors.append(f"missing frozen input: {relative}")
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if record.get("sha256") != actual_hash:
            errors.append(f"frozen input SHA-256 mismatch: {relative}")
        if record.get("bytes") != path.stat().st_size:
            errors.append(f"frozen input byte-size mismatch: {relative}")
        try:
            frame = pd.read_parquet(path)
        except Exception as exc:
            errors.append(f"unreadable frozen input: {relative}: {exc}")
            continue
        if record.get("rows") != len(frame):
            errors.append(f"frozen input row count mismatch: {relative}")
        if record.get("columns") != list(frame.columns):
            errors.append(f"frozen input column mismatch: {relative}")


def check_count(
    payload: dict[str, Any] | None,
    key: str,
    expected: int,
    label: str,
    errors: list[str],
) -> None:
    if payload is None:
        return
    actual = payload.get("row_counts", {}).get(key)
    if actual != expected:
        errors.append(f"{label} {key} mismatch: expected {expected}, got {actual}")


def validate_freeze(project_root: Path, expected_git_commit: str | None) -> list[str]:
    errors: list[str] = []
    provenance_path = project_root / "paper" / "tables" / "table_source_metadata.json"
    provenance = load_json(provenance_path, errors, "table provenance")
    referenced_metadata: set[str] = set()

    valid_expected_hash = expected_git_commit is None or bool(
        GIT_HASH_PATTERN.fullmatch(expected_git_commit)
    )
    if not valid_expected_hash:
        errors.append("expected Git commit must be a 40-character lowercase hexadecimal hash")

    if provenance is not None:
        entries = provenance.get("entries", [])
        if provenance.get("table_count") != EXPECTED_TABLE_COUNT:
            errors.append(
                f"table_count mismatch: expected {EXPECTED_TABLE_COUNT}, got {provenance.get('table_count')}"
            )
        if len(entries) != EXPECTED_TABLE_COUNT:
            errors.append(
                f"provenance entry count mismatch: expected {EXPECTED_TABLE_COUNT}, got {len(entries)}"
            )
        if expected_git_commit is not None and valid_expected_hash:
            if provenance.get("git_commit") != expected_git_commit:
                errors.append("table provenance Git commit does not match Commit A")

        for entry in entries:
            stem = entry.get("table_stem", "unknown")
            script_file = entry.get("script_file", "")
            if script_file.startswith("scripts/build_"):
                errors.append(f"legacy script path for {stem}: {script_file}")
            elif not script_file.startswith(ALLOWED_SCRIPT_PREFIXES):
                errors.append(f"invalid script path for {stem}: {script_file}")
            if not script_file or not (project_root / script_file).exists():
                errors.append(f"missing script for {stem}: {script_file}")

            for input_record in entry.get("input_files", []):
                relative = input_record.get("path") if isinstance(input_record, dict) else input_record
                if not relative or not (project_root / relative).exists():
                    errors.append(f"missing input for {stem}: {relative}")

            metadata_file = entry.get("metadata_file")
            if metadata_file:
                referenced_metadata.add(metadata_file)
                if not (project_root / metadata_file).exists():
                    errors.append(f"missing metadata for {stem}: {metadata_file}")
            else:
                errors.append(f"missing metadata mapping for {stem}")

            csv_relative = entry.get("csv")
            csv_path = project_root / csv_relative if csv_relative else None
            if csv_path is None or not csv_path.exists():
                errors.append(f"missing CSV for {stem}: {csv_relative}")
            else:
                actual_rows = csv_rows(csv_path)
                if entry.get("rows") != actual_rows:
                    errors.append(
                        f"CSV row count mismatch for {stem}: expected {entry.get('rows')}, got {actual_rows}"
                    )

            tex_relative = entry.get("tex")
            if not tex_relative or not (project_root / tex_relative).exists():
                errors.append(f"missing TeX for {stem}: {tex_relative}")

    track_a = load_json(
        project_root / "data/processed/panels/trackA_diagnostics_summary.json",
        errors,
        "Track A summary",
    )
    track_b = load_json(
        project_root / "data/processed/panels/trackB_lead_lag_diagnostics_summary.json",
        errors,
        "Track B summary",
    )
    reference = load_json(
        project_root / "data/processed/panels/reference_basis_audit_metadata.json",
        errors,
        "reference audit metadata",
    )
    check_count(
        track_a,
        "main_comparison_event_days",
        EXPECTED_TRACK_A_EVENT_DAYS,
        "Track A",
        errors,
    )
    check_count(track_a, "main_comparison_events", EXPECTED_TRACK_A_EVENTS, "Track A", errors)
    check_count(
        track_b,
        "informative_rows",
        EXPECTED_TRACK_B_JOINT_INFORMATIVE_ROWS,
        "Track B",
        errors,
    )
    check_count(
        track_b,
        "regression_rows",
        EXPECTED_TRACK_B_REGRESSION_ROWS,
        "Track B",
        errors,
    )
    check_count(reference, "audit_rows", EXPECTED_REFERENCE_AUDIT_ROWS, "reference audit", errors)
    if reference is not None:
        proxy_rows = reference.get("status_counts", {}).get("proxy_assumed")
        if proxy_rows != EXPECTED_REFERENCE_PROXY_ROWS:
            errors.append(
                "reference audit proxy_assumed mismatch: "
                f"expected {EXPECTED_REFERENCE_PROXY_ROWS}, got {proxy_rows}"
            )

    validate_input_manifest(project_root, errors)

    if expected_git_commit is not None and valid_expected_hash:
        for relative in sorted(referenced_metadata):
            metadata = load_json(project_root / relative, errors, f"metadata {relative}")
            if metadata is not None and metadata.get("git_commit") != expected_git_commit:
                errors.append(f"metadata Git commit does not match Commit A: {relative}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the frozen P2 output set.")
    parser.add_argument("--expected-git-commit")
    parser.add_argument("--write-table-manifest", type=Path)
    parser.add_argument("--compare-table-manifest", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = find_project_root()
    errors = validate_freeze(project_root, args.expected_git_commit)
    hashes = table_hashes(project_root)

    if args.compare_table_manifest:
        expected = load_json(args.compare_table_manifest, errors, "comparison table manifest")
        if expected is not None and expected.get("tables") != hashes:
            errors.append("table CSV hashes differ from the comparison manifest")

    if args.write_table_manifest:
        payload = {"table_count": len(hashes), "tables": hashes}
        args.write_table_manifest.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if errors:
        print("P2 freeze verification failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print(f"P2 freeze verification passed: {len(hashes)} table CSV files")


if __name__ == "__main__":
    main()
