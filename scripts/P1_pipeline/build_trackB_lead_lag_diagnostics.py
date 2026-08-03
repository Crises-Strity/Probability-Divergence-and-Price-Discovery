"""
Run Track B pooled lead-lag diagnostics on the 6h joined survival panel.

This is a deliberately downgraded Track B test: it is not Hasbrouck
information share and it is not a per-event VECM. It tests whether changes in
one market predict next-block changes in the other market after event fixed
effects, using event-clustered standard errors.

Inputs:
- data/processed/panels/lead_lag_survival_panel_6h.parquet

Outputs:
- data/processed/panels/trackB_lead_lag_diagnostics_summary.json
- paper/tables/tab_trackB_cross_correlation_6h.{csv,tex}
- paper/tables/tab_trackB_pooled_lead_lag_6h.{csv,tex}
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
import statsmodels.formula.api as smf


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
PANELS_DIR = PROJECT_ROOT / "data" / "processed" / "panels"
TABLES_DIR = PROJECT_ROOT / "paper" / "tables"

JOINED_6H = PANELS_DIR / "lead_lag_survival_panel_6h.parquet"
BAR_HOURS = 6


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


def write_table(df: pd.DataFrame, stem: str, caption: str, label: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES_DIR / f"{stem}.csv", index=False, encoding="utf-8-sig")
    tex = df.to_latex(index=False, escape=True, caption=caption, label=label, float_format="%.4f")
    (TABLES_DIR / f"{stem}.tex").write_text(tex, encoding="utf-8")


def informative_sample(panel: pd.DataFrame) -> pd.DataFrame:
    sample = panel[panel["both_sides_informative_candidate"]].copy()
    sample["timestamp"] = pd.to_datetime(sample["timestamp"], utc=True)
    sample = sample.sort_values(["event_id", "timestamp"]).reset_index(drop=True)
    return sample


def cross_correlation_table(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    base = sample[["event_id", "timestamp", "pm_change_joined_grid", "deribit_change_joined_grid"]].dropna().copy()
    for lag_hours in [-12, -6, 0, 6, 12]:
        shifted = base[["event_id", "timestamp", "deribit_change_joined_grid"]].copy()
        shifted["timestamp"] = shifted["timestamp"] - pd.Timedelta(hours=lag_hours)
        paired = base[["event_id", "timestamp", "pm_change_joined_grid"]].merge(
            shifted,
            on=["event_id", "timestamp"],
            how="inner",
        )
        rows.append(
            {
                "lag_hours_deribit_relative_to_pm": lag_hours,
                "interpretation": "PM leads Deribit" if lag_hours > 0 else ("Deribit leads PM" if lag_hours < 0 else "contemporaneous"),
                "pairs": int(len(paired)),
                "corr_pm_t_deribit_t_plus_lag": float(paired["pm_change_joined_grid"].corr(paired["deribit_change_joined_grid"])) if len(paired) >= 3 else float("nan"),
                "events": int(paired["event_id"].nunique()) if len(paired) else 0,
            }
        )
    return pd.DataFrame(rows)


def regression_sample(sample: pd.DataFrame) -> pd.DataFrame:
    work = sample.copy()
    work["previous_timestamp"] = work.groupby("event_id")["timestamp"].shift(1)
    work["lag_gap_hours"] = (work["timestamp"] - work["previous_timestamp"]).dt.total_seconds() / 3600.0
    work["pm_change_lag1"] = work.groupby("event_id")["pm_change_joined_grid"].shift(1)
    work["deribit_change_lag1"] = work.groupby("event_id")["deribit_change_joined_grid"].shift(1)
    work = work[
        work["lag_gap_hours"].eq(float(BAR_HOURS))
        & work["pm_change_joined_grid"].notna()
        & work["deribit_change_joined_grid"].notna()
        & work["pm_change_lag1"].notna()
        & work["deribit_change_lag1"].notna()
    ].copy()
    work["event_id_fe"] = work["event_id"].astype(str)
    return work.reset_index(drop=True)


def tidy_model(result: Any, model_name: str, formula: str, sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    keep_terms = ["pm_change_lag1", "deribit_change_lag1"]
    for term in keep_terms:
        if term not in result.params:
            continue
        rows.append(
            {
                "model": model_name,
                "formula": formula,
                "term": term,
                "coef": float(result.params[term]),
                "std_error_event_cluster": float(result.bse[term]),
                "t_stat": float(result.tvalues[term]),
                "p_value": float(result.pvalues[term]),
                "n_obs": int(result.nobs),
                "n_events": int(sample["event_id"].nunique()),
                "r_squared": float(result.rsquared),
            }
        )
    return pd.DataFrame(rows)


def pooled_regressions(sample: pd.DataFrame) -> pd.DataFrame:
    specs = [
        {
            "model": "pm_change_equation_deribit_leads",
            "formula": "pm_change_joined_grid ~ deribit_change_lag1 + pm_change_lag1 + C(event_id_fe)",
        },
        {
            "model": "deribit_change_equation_pm_leads",
            "formula": "deribit_change_joined_grid ~ pm_change_lag1 + deribit_change_lag1 + C(event_id_fe)",
        },
    ]
    frames = []
    for spec in specs:
        result = smf.ols(spec["formula"], data=sample).fit(
            cov_type="cluster",
            cov_kwds={"groups": sample["event_id"], "use_correction": True},
        )
        frames.append(tidy_model(result, spec["model"], spec["formula"], sample))
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    panel = pd.read_parquet(JOINED_6H)
    sample = informative_sample(panel)
    corr = cross_correlation_table(sample)
    reg_sample = regression_sample(sample)
    regressions = pooled_regressions(reg_sample) if not reg_sample.empty else pd.DataFrame()

    write_table(corr, "tab_trackB_cross_correlation_6h", "Track B 6h cross-correlation of survival-probability changes.", "tab:trackB_cross_correlation_6h")
    write_table(regressions, "tab_trackB_pooled_lead_lag_6h", "Track B 6h pooled lead-lag regressions with event fixed effects.", "tab:trackB_pooled_lead_lag_6h")

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py",
        "git_commit": git_commit(),
        "inputs": {
            "joined_6h": str(JOINED_6H.relative_to(PROJECT_ROOT)),
        },
        "filter_rules": {
            "sample": "both_sides_informative_candidate rows from 6h joined panel",
            "regression_sample": "requires consecutive 6h informative observations within event and non-missing current and lagged changes",
            "inference": "event-clustered standard errors; wild cluster bootstrap not yet implemented",
        },
        "row_counts": {
            "informative_rows": int(len(sample)),
            "informative_events": int(sample["event_id"].nunique()) if not sample.empty else 0,
            "regression_rows": int(len(reg_sample)),
            "regression_events": int(reg_sample["event_id"].nunique()) if not reg_sample.empty else 0,
            "cross_correlation_rows": int(len(corr)),
            "regression_terms": int(len(regressions)),
        },
        "cross_correlation": corr.to_dict(orient="records"),
        "pooled_regressions": regressions.to_dict(orient="records"),
        "known_caveats": [
            "This is a pooled 6h Granger-style diagnostic, not Hasbrouck information share.",
            "6h aggregation reduces Deribit microstructure noise but cannot identify sub-6h price discovery.",
            "Event-clustered standard errors are descriptive until a wild cluster bootstrap is added.",
        ],
    }
    (PANELS_DIR / "trackB_lead_lag_diagnostics_summary.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Track B 6h lead-lag diagnostics ===")
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value:,}")
    print("\nCross-correlations:")
    print(corr.to_string(index=False))
    print("\nPooled regressions:")
    print(regressions.to_string(index=False) if not regressions.empty else "empty")
    print("\nOutputs:")
    print(f"- {PANELS_DIR / 'trackB_lead_lag_diagnostics_summary.json'}")
    print(f"- {TABLES_DIR / 'tab_trackB_cross_correlation_6h.tex'}")
    print(f"- {TABLES_DIR / 'tab_trackB_pooled_lead_lag_6h.tex'}")


if __name__ == "__main__":
    main()
