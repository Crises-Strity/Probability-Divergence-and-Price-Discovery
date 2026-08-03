"""
Summarize Track A RND smoothing/mean-constraint sensitivity runs.

Inputs are the baseline and labelled outputs produced by:
- scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py
- scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py --smooth-weight 0.05 --output-label smooth005
- scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py --smooth-weight 0.2 --output-label smooth02
- scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py --smooth-weight 0 --output-label smooth0
- scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py --mean-weight 0 --output-label mean0
- scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py --smooth-weight 0 --mean-weight 0 --output-label nopenalty

Outputs:
- data/processed/panels/trackA_sensitivity_summary.json
- paper/tables/tab_trackA_rnd_sensitivity.{csv,tex}
- paper/tables/tab_trackA_rnd_sensitivity_common_days.{csv,tex}
- paper/figures/fig_trackA_rnd_sensitivity_l1.pdf
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

import matplotlib.pyplot as plt
import pandas as pd


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
PANELS_DIR = PROJECT_ROOT / "data" / "processed" / "panels"
DERIBIT_DIR = PROJECT_ROOT / "data" / "processed" / "deribit"
TABLES_DIR = PROJECT_ROOT / "paper" / "tables"
FIGURES_DIR = PROJECT_ROOT / "paper" / "figures"

SPECS = [
    {"name": "baseline", "label": None, "smooth_weight": 0.1, "mean_weight": 10.0},
    {"name": "smooth005", "label": "smooth005", "smooth_weight": 0.05, "mean_weight": 10.0},
    {"name": "smooth02", "label": "smooth02", "smooth_weight": 0.2, "mean_weight": 10.0},
    {"name": "smooth0", "label": "smooth0", "smooth_weight": 0.0, "mean_weight": 10.0},
    {"name": "mean0", "label": "mean0", "smooth_weight": 0.1, "mean_weight": 0.0},
    {"name": "nopenalty", "label": "nopenalty", "smooth_weight": 0.0, "mean_weight": 0.0},
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


def stem(base: str, label: str | None) -> str:
    return base if not label else f"{base}_{label}"


def read_outputs(spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    divergence = pd.read_parquet(PANELS_DIR / f"{stem('trackA_event_day_divergence', spec['label'])}.parquet")
    fits = pd.read_parquet(DERIBIT_DIR / f"{stem('deribit_curve_fits', spec['label'])}.parquet")
    return divergence, fits


def summarize_spec(spec: dict[str, Any], divergence: pd.DataFrame, fits: pd.DataFrame, common_keys: set[tuple[int, str]] | None = None) -> dict[str, Any]:
    main = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    if common_keys is not None:
        keys = list(zip(main["event_id"].astype(int), main["date"].astype(str)))
        main = main[[key in common_keys for key in keys]].copy()
    pass_days = int(len(main))
    return {
        "spec": spec["name"],
        "smooth_weight": spec["smooth_weight"],
        "mean_weight": spec["mean_weight"],
        "pass_days": pass_days,
        "pass_events": int(main["event_id"].nunique()) if pass_days else 0,
        "fit_fail_sanity_days": int((fits["deribit_curve_quality"] != "pass").sum()),
        "l1_mean": float(main["l1_normalized_divergence"].mean()) if pass_days else float("nan"),
        "l1_median": float(main["l1_normalized_divergence"].median()) if pass_days else float("nan"),
        "l2_median": float(main["l2_normalized_divergence"].median()) if pass_days else float("nan"),
        "pm_spread_median": float(main["pm_spread"].median()) if pass_days else float("nan"),
        "deribit_spread_median": float(main["deribit_spread"].median()) if pass_days else float("nan"),
        "spread_diff_pm_minus_deribit_median": float(main["spread_diff_pm_minus_deribit"].median()) if pass_days else float("nan"),
        "pm_wider_share": float((main["pm_spread"] > main["deribit_spread"]).mean()) if pass_days else float("nan"),
        "rmse_coin_mean": float(main["option_reprice_rmse_coin"].mean()) if pass_days else float("nan"),
        "forward_rel_error_abs_median": float(main["fitted_forward_rel_error"].abs().median()) if pass_days else float("nan"),
    }


def write_table(df: pd.DataFrame, stem_name: str, caption: str, label: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES_DIR / f"{stem_name}.csv", index=False, encoding="utf-8-sig")
    tex = df.to_latex(index=False, escape=True, caption=caption, label=label, float_format="%.4f")
    (TABLES_DIR / f"{stem_name}.tex").write_text(tex, encoding="utf-8")


def save_l1_figure(summary: pd.DataFrame) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    palette = ["#4c78a8", "#72b7b2", "#b279a2", "#e45756", "#59a14f", "#f58518"]
    ax.bar(summary["spec"], summary["l1_median"], color=palette[: len(summary)])
    ax.set_xlabel("RND fit specification")
    ax.set_ylabel("Median L1 normalized divergence")
    ax.set_title("Track A Sensitivity to RND Fit Penalties")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#d9d9d9", linewidth=0.7, alpha=0.8)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_trackA_rnd_sensitivity_l1.pdf")
    plt.close(fig)


def main() -> None:
    loaded = []
    for spec in SPECS:
        divergence, fits = read_outputs(spec)
        loaded.append((spec, divergence, fits))

    pass_key_sets = []
    for _spec, divergence, _fits in loaded:
        main = divergence[divergence["trackA_comparison_main_candidate"]]
        pass_key_sets.append(set(zip(main["event_id"].astype(int), main["date"].astype(str))))
    common_keys = set.intersection(*pass_key_sets)

    summary = pd.DataFrame([summarize_spec(spec, divergence, fits) for spec, divergence, fits in loaded])
    common = pd.DataFrame([summarize_spec(spec, divergence, fits, common_keys) for spec, divergence, fits in loaded])

    write_table(summary, "tab_trackA_rnd_sensitivity", "Track A RND fit sensitivity across all passing days per specification.", "tab:trackA_rnd_sensitivity")
    write_table(common, "tab_trackA_rnd_sensitivity_common_days", "Track A RND fit sensitivity on common passing event-days.", "tab:trackA_rnd_sensitivity_common_days")
    save_l1_figure(summary)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_trackA_sensitivity_diagnostics.py",
        "git_commit": git_commit(),
        "specs": SPECS,
        "common_pass_days": len(common_keys),
        "row_counts": {
            "specs": len(SPECS),
            "summary_rows": int(len(summary)),
            "common_rows": int(len(common)),
        },
        "headline": {
            "baseline_l1_median": float(summary.loc[summary["spec"] == "baseline", "l1_median"].iloc[0]),
            "smooth005_l1_median": float(summary.loc[summary["spec"] == "smooth005", "l1_median"].iloc[0]),
            "smooth02_l1_median": float(summary.loc[summary["spec"] == "smooth02", "l1_median"].iloc[0]),
            "smooth0_l1_median": float(summary.loc[summary["spec"] == "smooth0", "l1_median"].iloc[0]),
            "mean0_l1_median": float(summary.loc[summary["spec"] == "mean0", "l1_median"].iloc[0]),
            "nopenalty_l1_median": float(summary.loc[summary["spec"] == "nopenalty", "l1_median"].iloc[0]),
        },
        "known_caveats": [
            "The no-smoothing specifications are diagnostic stress tests; sparse state-price fits can become spiky even when repricing error is low.",
            "A large change in L1 after removing smoothness means headline magnitude is smoothing-sensitive and should not be overinterpreted without a shape-regularized primary specification.",
        ],
    }
    (PANELS_DIR / "trackA_sensitivity_summary.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Track A RND sensitivity ===")
    print(summary.to_string(index=False))
    print(f"\nCommon pass days: {len(common_keys):,}")
    print("\nOutputs:")
    print(f"- {PANELS_DIR / 'trackA_sensitivity_summary.json'}")
    print(f"- {TABLES_DIR / 'tab_trackA_rnd_sensitivity.tex'}")
    print(f"- {TABLES_DIR / 'tab_trackA_rnd_sensitivity_common_days.tex'}")
    print(f"- {FIGURES_DIR / 'fig_trackA_rnd_sensitivity_l1.pdf'}")


if __name__ == "__main__":
    main()
