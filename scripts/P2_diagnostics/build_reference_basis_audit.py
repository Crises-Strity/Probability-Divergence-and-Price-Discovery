"""
Build the P2 reference-basis audit.

This script documents whether Polymarket settlement text and Deribit index
references are textually available and whether they match. It is an audit table,
not an estimator, and it does not rerun Track A or Track B panels.

Inputs:
- data/processed/polymarket/event_universe.parquet

Outputs:
- data/processed/panels/reference_basis_audit.{csv,parquet}
- data/processed/panels/reference_basis_audit_metadata.json
- paper/tables/tab_reference_basis_audit_summary.{csv,tex}
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path("/private/tmp") / "matplotlib-codex"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path("/private/tmp") / "codex-cache"))

import pandas as pd


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
POLYMARKET_DIR = PROJECT_ROOT / "data" / "processed" / "polymarket"
PANELS_DIR = PROJECT_ROOT / "data" / "processed" / "panels"
TABLES_DIR = PROJECT_ROOT / "paper" / "tables"

EVENT_UNIVERSE = POLYMARKET_DIR / "event_universe.parquet"

AUDIT_COLUMNS = [
    "event_id",
    "asset",
    "event_title",
    "event_type_for_trackB",
    "trackA_eligible",
    "trackB_eligible",
    "mapping_quality",
    "nearest_deribit_expiry",
    "time_gap_hours",
    "polymarket_resolution_text_available",
    "settlement_reference_text",
    "settlement_reference_detail",
    "deribit_index_reference_text",
    "reference_basis_mismatch",
    "reference_basis_status",
    "paper_use_recommendation",
]


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


def has_text(value: object) -> bool:
    if value is None or pd.isna(value):
        return False
    return bool(str(value).strip())


def reference_basis_status(
    settlement_reference: object,
    settlement_reference_detail: object,
    deribit_index_reference: object,
    reference_basis_mismatch: object,
) -> str:
    polymarket_text_available = has_text(settlement_reference) or has_text(settlement_reference_detail)
    deribit_text_available = has_text(deribit_index_reference)
    if not polymarket_text_available or not deribit_text_available:
        return "unknown"
    if bool(reference_basis_mismatch):
        return "proxy_assumed"
    return "matched_text"


def paper_use_recommendation(status: str) -> str:
    if status == "matched_text":
        return "Ch4 text-backed matched reference"
    if status == "proxy_assumed":
        return "Ch4 audit plus Ch7 proxy limitation"
    return "Ch7 unknown reference limitation"


def build_audit(event_universe: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in event_universe.to_dict(orient="records"):
        status = reference_basis_status(
            record.get("settlement_reference"),
            record.get("settlement_reference_detail"),
            record.get("deribit_index_reference"),
            record.get("reference_basis_mismatch"),
        )
        rows.append(
            {
                "event_id": record.get("event_id"),
                "asset": record.get("asset"),
                "event_title": record.get("event_title"),
                "event_type_for_trackB": record.get("event_type_for_trackB"),
                "trackA_eligible": bool(record.get("trackA_eligible")),
                "trackB_eligible": bool(record.get("trackB_eligible")),
                "mapping_quality": record.get("mapping_quality"),
                "nearest_deribit_expiry": record.get("nearest_deribit_expiry"),
                "time_gap_hours": record.get("time_gap_hours"),
                "polymarket_resolution_text_available": has_text(record.get("settlement_reference"))
                or has_text(record.get("settlement_reference_detail")),
                "settlement_reference_text": record.get("settlement_reference"),
                "settlement_reference_detail": record.get("settlement_reference_detail"),
                "deribit_index_reference_text": record.get("deribit_index_reference"),
                "reference_basis_mismatch": bool(record.get("reference_basis_mismatch")),
                "reference_basis_status": status,
                "paper_use_recommendation": paper_use_recommendation(status),
            }
        )
    return pd.DataFrame(rows, columns=AUDIT_COLUMNS).sort_values(["asset", "event_id"]).reset_index(drop=True)


def build_summary(audit: pd.DataFrame) -> pd.DataFrame:
    grouped = audit.groupby(["asset", "reference_basis_status"], dropna=False)
    summary = grouped.agg(
        n_events=("event_id", "nunique"),
        n_trackA_eligible=("trackA_eligible", "sum"),
        n_trackB_eligible=("trackB_eligible", "sum"),
        resolution_text_available_share=("polymarket_resolution_text_available", "mean"),
        reference_basis_mismatch_share=("reference_basis_mismatch", "mean"),
    ).reset_index()
    return summary.sort_values(["asset", "reference_basis_status"]).reset_index(drop=True)


def write_table(df: pd.DataFrame) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES_DIR / "tab_reference_basis_audit_summary.csv", index=False, encoding="utf-8-sig")
    tex = df.to_latex(
        index=False,
        escape=True,
        caption="Reference-basis audit summary.",
        label="tab:reference_basis_audit_summary",
        float_format="%.4f",
    )
    (TABLES_DIR / "tab_reference_basis_audit_summary.tex").write_text(tex, encoding="utf-8")


def main() -> None:
    event_universe = pd.read_parquet(EVENT_UNIVERSE)
    audit = build_audit(event_universe)
    summary = build_summary(audit)

    PANELS_DIR.mkdir(parents=True, exist_ok=True)
    audit.to_csv(PANELS_DIR / "reference_basis_audit.csv", index=False, encoding="utf-8-sig")
    audit.to_parquet(PANELS_DIR / "reference_basis_audit.parquet", index=False)
    write_table(summary)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "input_file": str(EVENT_UNIVERSE.relative_to(PROJECT_ROOT)),
        "output_files": [
            "data/processed/panels/reference_basis_audit.csv",
            "data/processed/panels/reference_basis_audit.parquet",
            "paper/tables/tab_reference_basis_audit_summary.csv",
            "paper/tables/tab_reference_basis_audit_summary.tex",
        ],
        "row_counts": {
            "audit_rows": int(len(audit)),
            "summary_rows": int(len(summary)),
            "events": int(audit["event_id"].nunique()),
        },
        "status_counts": audit["reference_basis_status"].value_counts(dropna=False).to_dict(),
        "notes": [
            "reference_basis_status is textual/provenance audit status, not a numerical Track A or Track B sample gate.",
            "proxy_assumed means both references are populated but Polymarket and Deribit reference bases differ.",
        ],
    }
    (PANELS_DIR / "reference_basis_audit_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Reference-basis audit status counts:")
    print(audit["reference_basis_status"].value_counts(dropna=False).to_string())
    print("\nSummary:")
    print(summary.to_string(index=False))
    print("\nOutputs:")
    print(f"- {PANELS_DIR / 'reference_basis_audit.csv'}")
    print(f"- {PANELS_DIR / 'reference_basis_audit.parquet'}")
    print(f"- {PANELS_DIR / 'reference_basis_audit_metadata.json'}")
    print(f"- {TABLES_DIR / 'tab_reference_basis_audit_summary.csv'}")
    print(f"- {TABLES_DIR / 'tab_reference_basis_audit_summary.tex'}")


if __name__ == "__main__":
    main()
