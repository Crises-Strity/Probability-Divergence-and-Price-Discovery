"""
Build Track A first-pass diagnostics, tables, and figures.

Inputs:
- data/processed/panels/trackA_event_day_quality.parquet
- data/processed/panels/trackA_event_day_divergence.parquet
- data/processed/panels/daily_distribution_comparison.parquet
- data/processed/deribit/deribit_curve_fits.parquet

Outputs:
- data/processed/panels/trackA_diagnostics_summary.json
- paper/tables/tab_trackA_*.{csv,tex}
- paper/figures/fig_trackA_*.pdf
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
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
PANELS_DIR = PROJECT_ROOT / "data" / "processed" / "panels"
DERIBIT_DIR = PROJECT_ROOT / "data" / "processed" / "deribit"
FIGURES_DIR = PROJECT_ROOT / "paper" / "figures"
TABLES_DIR = PROJECT_ROOT / "paper" / "tables"

EVENT_DAY_QUALITY = PANELS_DIR / "trackA_event_day_quality.parquet"
EVENT_DAY_DIVERGENCE = PANELS_DIR / "trackA_event_day_divergence.parquet"
DAILY_COMPARISON = PANELS_DIR / "daily_distribution_comparison.parquet"
CURVE_FITS = DERIBIT_DIR / "deribit_curve_fits.parquet"


GAP_ORDER = ["-32h", "-8h", "+16h", "+40h"]
ASSET_COLORS = {"BTC": "#1f77b4", "ETH": "#d62728"}


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


def ensure_dirs() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    PANELS_DIR.mkdir(parents=True, exist_ok=True)


def write_table(df: pd.DataFrame, stem: str, caption: str, label: str) -> None:
    csv_path = TABLES_DIR / f"{stem}.csv"
    tex_path = TABLES_DIR / f"{stem}.tex"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    tex = df.to_latex(index=False, escape=True, caption=caption, label=label, float_format="%.4f")
    tex_path.write_text(tex, encoding="utf-8")


def event_day_count(df: pd.DataFrame, mask: pd.Series) -> int:
    return int(df.loc[mask, ["event_id", "date"]].drop_duplicates().shape[0])


def unique_events(df: pd.DataFrame, mask: pd.Series) -> int:
    return int(df.loc[mask, "event_id"].nunique())


def sample_funnel(event_day: pd.DataFrame, fits: pd.DataFrame, divergence: pd.DataFrame, comparison: pd.DataFrame) -> pd.DataFrame:
    stages = [
        (
            "Track A event-day panel",
            pd.Series(True, index=event_day.index),
            event_day,
            pd.NA,
        ),
        (
            "Legacy PM+Deribit min8 main gate",
            event_day["trackA_event_day_main_candidate_min8"],
            event_day,
            pd.NA,
        ),
        (
            "Curve-input gate: stale<=0.30 and fresh strikes>=8",
            event_day["trackA_curve_input_candidate"],
            event_day,
            pd.NA,
        ),
        (
            "Curve fit success",
            fits["status"].eq("fit_success"),
            fits,
            pd.NA,
        ),
        (
            "Curve quality pass",
            fits["deribit_curve_quality"].eq("pass"),
            fits,
            int(comparison["trackA_comparison_main_candidate"].sum()),
        ),
    ]
    rows: list[dict[str, Any]] = []
    for stage, mask, df, rows_count in stages:
        rows.append(
            {
                "stage": stage,
                "event_days": event_day_count(df, mask),
                "events": unique_events(df, mask),
                "cell_rows": rows_count,
            }
        )
    out = pd.DataFrame(rows)
    out["cell_rows"] = out["cell_rows"].astype("Int64")
    return out


def divergence_overall(divergence: pd.DataFrame) -> pd.DataFrame:
    main = divergence[divergence["trackA_comparison_main_candidate"]]
    metrics = [
        "l1_normalized_divergence",
        "l2_normalized_divergence",
        "max_abs_normalized_divergence",
        "tail_normalized_divergence",
        "tail_relative_abs_divergence_mean",
        "body_relative_abs_divergence_mean",
        "location_diff_pm_minus_deribit",
        "spread_diff_pm_minus_deribit",
        "skew_diff_pm_minus_deribit",
        "deribit_stale_bar_share",
        "option_reprice_rmse_coin",
    ]
    stats = main[metrics].describe(percentiles=[0.25, 0.5, 0.75]).T.reset_index()
    stats = stats.rename(columns={"index": "metric", "50%": "median"})
    return stats[["metric", "count", "mean", "std", "min", "25%", "median", "75%", "max"]]


def divergence_by_group(divergence: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    main = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    grouped = main.groupby(group_cols, dropna=False)
    out = grouped.agg(
        event_days=("event_id", "size"),
        events=("event_id", "nunique"),
        l1_mean=("l1_normalized_divergence", "mean"),
        l1_median=("l1_normalized_divergence", "median"),
        l2_mean=("l2_normalized_divergence", "mean"),
        max_abs_mean=("max_abs_normalized_divergence", "mean"),
        tail_mean=("tail_normalized_divergence", "mean"),
        stale_mean=("deribit_stale_bar_share", "mean"),
        repricing_rmse_mean=("option_reprice_rmse_coin", "mean"),
    ).reset_index()
    if "horizon_gap_bin" in out.columns:
        out["horizon_gap_bin"] = pd.Categorical(out["horizon_gap_bin"], categories=GAP_ORDER, ordered=True)
        out = out.sort_values([c for c in group_cols if c != "asset"] + (["asset"] if "asset" in group_cols else []))
        out["horizon_gap_bin"] = out["horizon_gap_bin"].astype(str)
    return out.reset_index(drop=True)


def curve_quality_table(fits: pd.DataFrame) -> pd.DataFrame:
    grouped = fits.groupby(["asset", "deribit_curve_quality"], dropna=False).agg(
        event_days=("event_id", "size"),
        events=("event_id", "nunique"),
        rmse_coin_mean=("option_reprice_rmse_coin", "mean"),
        rmse_coin_max=("option_reprice_rmse_coin", "max"),
        parity_rel_iqr_mean=("parity_spot_rel_iqr", "mean"),
        forward_rel_error_abs_max=("fitted_forward_rel_error", lambda s: s.abs().max()),
        input_convexity_violations_mean=("input_call_convexity_violations", "mean"),
    )
    return grouped.reset_index()


def cell_divergence_table(comparison: pd.DataFrame) -> pd.DataFrame:
    main = comparison[comparison["trackA_comparison_main_candidate"]].copy()
    rows = []
    for group_name, group in main.groupby(["cell_type", "moneyness_bucket"], dropna=False):
        cell_type, moneyness = group_name
        rows.append(
            {
                "cell_type": cell_type,
                "moneyness_bucket": moneyness,
                "rows": int(len(group)),
                "event_days": int(group[["event_id", "date"]].drop_duplicates().shape[0]),
                "mean_abs_normalized_divergence": float(group["normalized_divergence"].abs().mean()),
                "median_abs_normalized_divergence": float(group["normalized_divergence"].abs().median()),
                "mean_signed_normalized_divergence": float(group["normalized_divergence"].mean()),
                "mean_relative_abs_divergence": float(group["relative_abs_normalized_divergence"].mean()),
                "median_relative_abs_divergence": float(group["relative_abs_normalized_divergence"].median()),
                "mean_log_odds_divergence": float(group["log_odds_divergence"].mean()),
                "pm_probability_mean": float(group["pm_probability_normalized"].mean()),
                "deribit_probability_mean": float(group["deribit_probability"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["cell_type", "moneyness_bucket"]).reset_index(drop=True)


def moment_by_gap_table(divergence: pd.DataFrame) -> pd.DataFrame:
    main = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    out = main.groupby("horizon_gap_bin").agg(
        event_days=("event_id", "size"),
        events=("event_id", "nunique"),
        tte_median=("time_to_expiry_hours", "median"),
        location_diff_median=("location_diff_pm_minus_deribit", "median"),
        spread_diff_pm_minus_deribit_median=("spread_diff_pm_minus_deribit", "median"),
        spread_diff_deribit_minus_pm_median=("spread_diff_deribit_minus_pm", "median"),
        skew_diff_median=("skew_diff_pm_minus_deribit", "median"),
        pm_spread_median=("pm_spread", "median"),
        deribit_spread_median=("deribit_spread", "median"),
    ).reset_index()
    out["horizon_gap_bin"] = pd.Categorical(out["horizon_gap_bin"], categories=GAP_ORDER, ordered=True)
    out = out.sort_values("horizon_gap_bin")
    out["horizon_gap_bin"] = out["horizon_gap_bin"].astype(str)
    return out


def moment_by_tte_gap_table(divergence: pd.DataFrame) -> pd.DataFrame:
    main = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    out = main.groupby(["time_to_expiry_hours", "horizon_gap_bin"]).agg(
        event_days=("event_id", "size"),
        events=("event_id", "nunique"),
        spread_diff_pm_minus_deribit_median=("spread_diff_pm_minus_deribit", "median"),
        location_diff_median=("location_diff_pm_minus_deribit", "median"),
        l1_median=("l1_normalized_divergence", "median"),
    ).reset_index()
    out["horizon_gap_bin"] = pd.Categorical(out["horizon_gap_bin"], categories=GAP_ORDER, ordered=True)
    out = out.sort_values(["time_to_expiry_hours", "horizon_gap_bin"])
    out["horizon_gap_bin"] = out["horizon_gap_bin"].astype(str)
    return out


def tail_relative_table(comparison: pd.DataFrame) -> pd.DataFrame:
    main = comparison[comparison["trackA_comparison_main_candidate"]].copy()
    main["tail_group"] = np.where(main["tail_cell_flag"], "tail", "body")
    rows = []
    for tail_group, group in main.groupby("tail_group"):
        rows.append(
            {
                "tail_group": tail_group,
                "rows": int(len(group)),
                "event_days": int(group[["event_id", "date"]].drop_duplicates().shape[0]),
                "pm_probability_mean": float(group["pm_probability_normalized"].mean()),
                "abs_divergence_mean": float(group["normalized_divergence"].abs().mean()),
                "relative_abs_divergence_mean": float(group["relative_abs_normalized_divergence"].mean()),
                "relative_abs_divergence_median": float(group["relative_abs_normalized_divergence"].median()),
                "log_odds_divergence_mean": float(group["log_odds_divergence"].mean()),
                "log_odds_divergence_median": float(group["log_odds_divergence"].median()),
            }
        )
    return pd.DataFrame(rows).sort_values("tail_group").reset_index(drop=True)


def gap_confound_table(divergence: pd.DataFrame) -> pd.DataFrame:
    main = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    variables = [
        "time_to_expiry_hours",
        "location_diff_pm_minus_deribit",
        "spread_diff_pm_minus_deribit",
        "spread_diff_deribit_minus_pm",
        "skew_diff_pm_minus_deribit",
        "l1_normalized_divergence",
        "deribit_stale_bar_share",
        "option_reprice_rmse_coin",
    ]
    rows = []
    for variable in variables:
        valid = main[["signed_gap_hours", variable]].dropna()
        rho, p_value = spearmanr(valid["signed_gap_hours"], valid[variable])
        rows.append(
            {
                "variable": variable,
                "n": int(len(valid)),
                "spearman_rho_vs_signed_gap": float(rho),
                "p_value": float(p_value),
            }
        )
    return pd.DataFrame(rows)


def set_common_style(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#d9d9d9", linewidth=0.7, alpha=0.8)


def save_l1_distribution(divergence: pd.DataFrame) -> None:
    main = divergence[divergence["trackA_comparison_main_candidate"]]
    values = main["l1_normalized_divergence"]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.hist(values, bins=24, color="#4c78a8", edgecolor="white", alpha=0.9)
    ax.axvline(values.median(), color="#d62728", linewidth=1.6, label=f"Median = {values.median():.3f}")
    ax.set_xlabel("L1 normalized divergence")
    ax.set_ylabel("Event-days")
    ax.set_title("Track A Distribution Wedge")
    ax.legend(frameon=False)
    set_common_style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_trackA_l1_distribution.pdf")
    plt.close(fig)


def save_l1_by_gap(divergence: pd.DataFrame) -> None:
    main = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    data = [main.loc[main["horizon_gap_bin"] == gap, "l1_normalized_divergence"].to_numpy() for gap in GAP_ORDER]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    bp = ax.boxplot(data, tick_labels=GAP_ORDER, patch_artist=True, showfliers=True)
    for patch in bp["boxes"]:
        patch.set(facecolor="#72b7b2", alpha=0.75)
    ax.set_xlabel("Signed horizon gap bin")
    ax.set_ylabel("L1 normalized divergence")
    ax.set_title("Track A Wedge by Horizon Gap")
    set_common_style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_trackA_l1_by_gap.pdf")
    plt.close(fig)


def save_stale_vs_l1(divergence: pd.DataFrame) -> None:
    main = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    for asset, group in main.groupby("asset"):
        ax.scatter(
            group["deribit_stale_bar_share"],
            group["l1_normalized_divergence"],
            s=24,
            alpha=0.72,
            color=ASSET_COLORS.get(asset, "#4c78a8"),
            label=asset,
            edgecolor="none",
        )
    ax.set_xlabel("Deribit stale bar share")
    ax.set_ylabel("L1 normalized divergence")
    ax.set_title("Wedge vs Deribit Staleness")
    ax.legend(frameon=False)
    set_common_style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_trackA_l1_vs_staleness.pdf")
    plt.close(fig)


def save_repricing_quality(fits: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    pass_mask = fits["deribit_curve_quality"].eq("pass")
    ax.scatter(
        fits.loc[pass_mask, "parity_spot_rel_iqr"],
        fits.loc[pass_mask, "option_reprice_rmse_coin"],
        s=24,
        alpha=0.72,
        color="#59a14f",
        edgecolor="none",
        label="pass",
    )
    ax.scatter(
        fits.loc[~pass_mask, "parity_spot_rel_iqr"],
        fits.loc[~pass_mask, "option_reprice_rmse_coin"],
        s=36,
        alpha=0.95,
        color="#d62728",
        edgecolor="none",
        label="fail_sanity",
    )
    ax.axhline(0.02, color="#d62728", linewidth=1.2, linestyle="--", label="RMSE gate")
    ax.set_xlabel("Parity-implied spot relative IQR")
    ax.set_ylabel("Option repricing RMSE (coin)")
    ax.set_title("Curve Fit Sanity Diagnostics")
    ax.legend(frameon=False)
    set_common_style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_trackA_curve_fit_quality.pdf")
    plt.close(fig)


def save_cell_divergence_by_type(comparison: pd.DataFrame) -> None:
    main = comparison[comparison["trackA_comparison_main_candidate"]].copy()
    grouped = main.groupby("cell_type")["normalized_divergence"].apply(lambda s: s.abs().mean())
    order = ["left_tail", "bucket", "right_tail"]
    grouped = grouped.reindex([x for x in order if x in grouped.index])
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.bar(grouped.index, grouped.values, color=["#f58518", "#4c78a8", "#e45756"][: len(grouped)])
    ax.set_xlabel("Cell type")
    ax.set_ylabel("Mean absolute normalized divergence")
    ax.set_title("Cell-Level Wedge by Bucket Type")
    set_common_style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_trackA_cell_divergence_by_type.pdf")
    plt.close(fig)


def save_spread_by_gap(divergence: pd.DataFrame) -> None:
    main = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    data = [main.loc[main["horizon_gap_bin"] == gap, "spread_diff_pm_minus_deribit"].to_numpy() for gap in GAP_ORDER]
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    bp = ax.boxplot(data, tick_labels=GAP_ORDER, patch_artist=True, showfliers=True)
    for patch in bp["boxes"]:
        patch.set(facecolor="#b279a2", alpha=0.75)
    ax.axhline(0.0, color="#555555", linewidth=1.0)
    ax.set_xlabel("Signed horizon gap bin")
    ax.set_ylabel("Spread difference: PM - Deribit")
    ax.set_title("Distribution Spread Difference by Horizon Gap")
    set_common_style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_trackA_spread_diff_by_gap.pdf")
    plt.close(fig)


def save_tte_vs_spread(divergence: pd.DataFrame) -> None:
    main = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    for asset, group in main.groupby("asset"):
        ax.scatter(
            group["time_to_expiry_hours"],
            group["spread_diff_pm_minus_deribit"],
            s=24,
            alpha=0.72,
            color=ASSET_COLORS.get(asset, "#4c78a8"),
            label=asset,
            edgecolor="none",
        )
    ax.axhline(0.0, color="#555555", linewidth=1.0)
    ax.set_xlabel("Deribit time to expiry (hours)")
    ax.set_ylabel("Spread difference: PM - Deribit")
    ax.set_title("Spread Difference vs Time to Expiry")
    ax.legend(frameon=False)
    set_common_style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_trackA_spread_diff_vs_tte.pdf")
    plt.close(fig)


def save_example_distribution(comparison: pd.DataFrame, divergence: pd.DataFrame) -> dict[str, Any]:
    main_div = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    median_l1 = main_div["l1_normalized_divergence"].median()
    idx = (main_div["l1_normalized_divergence"] - median_l1).abs().idxmin()
    chosen = main_div.loc[idx]
    example = comparison[
        (comparison["event_id"] == chosen["event_id"])
        & (comparison["date"] == chosen["date"])
        & (comparison["trackA_comparison_main_candidate"])
    ].sort_values("cell_id")

    labels = []
    for _, row in example.iterrows():
        if row["cell_type"] == "left_tail":
            labels.append(f"<{row['cell_high']:.0f}")
        elif row["cell_type"] == "right_tail":
            labels.append(f">{row['cell_low']:.0f}")
        else:
            labels.append(f"{row['cell_low']:.0f}-{row['cell_high']:.0f}")

    x = np.arange(len(example))
    width = 0.42
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    ax.bar(x - width / 2, example["pm_probability_normalized"], width, label="Polymarket", color="#4c78a8")
    ax.bar(x + width / 2, example["deribit_probability"], width, label="Deribit", color="#f58518")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylabel("Probability")
    ax.set_title(f"Example Distribution Comparison: event {int(chosen['event_id'])}, {chosen['date']}")
    ax.legend(frameon=False)
    set_common_style(ax)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_trackA_distribution_comparison_example.pdf")
    plt.close(fig)

    return {
        "event_id": int(chosen["event_id"]),
        "date": str(chosen["date"]),
        "asset": str(chosen["asset"]),
        "l1_normalized_divergence": float(chosen["l1_normalized_divergence"]),
        "selection_rule": "event-day closest to median L1 among main Track A comparison days",
    }


def main() -> None:
    ensure_dirs()

    event_day = pd.read_parquet(EVENT_DAY_QUALITY)
    divergence = pd.read_parquet(EVENT_DAY_DIVERGENCE)
    comparison = pd.read_parquet(DAILY_COMPARISON)
    fits = pd.read_parquet(CURVE_FITS)

    sample = sample_funnel(event_day, fits, divergence, comparison)
    overall = divergence_overall(divergence)
    by_gap = divergence_by_group(divergence, ["horizon_gap_bin"])
    by_asset = divergence_by_group(divergence, ["asset"])
    by_asset_gap = divergence_by_group(divergence, ["asset", "horizon_gap_bin"])
    curve_quality = curve_quality_table(fits)
    cell_div = cell_divergence_table(comparison)
    moments_by_gap = moment_by_gap_table(divergence)
    moments_by_tte_gap = moment_by_tte_gap_table(divergence)
    tail_relative = tail_relative_table(comparison)
    gap_confounds = gap_confound_table(divergence)

    write_table(sample, "tab_trackA_sample_funnel", "Track A sample funnel.", "tab:trackA_sample_funnel")
    write_table(overall, "tab_trackA_divergence_overall", "Track A event-day divergence summary.", "tab:trackA_divergence_overall")
    write_table(by_gap, "tab_trackA_divergence_by_gap", "Track A divergence by signed horizon gap.", "tab:trackA_divergence_by_gap")
    write_table(by_asset, "tab_trackA_divergence_by_asset", "Track A divergence by asset.", "tab:trackA_divergence_by_asset")
    write_table(by_asset_gap, "tab_trackA_divergence_by_asset_gap", "Track A divergence by asset and signed horizon gap.", "tab:trackA_divergence_by_asset_gap")
    write_table(curve_quality, "tab_trackA_curve_quality", "Track A curve-fit quality diagnostics.", "tab:trackA_curve_quality")
    write_table(cell_div, "tab_trackA_cell_divergence", "Track A cell-level divergence diagnostics.", "tab:trackA_cell_divergence")
    write_table(moments_by_gap, "tab_trackA_moments_by_gap", "Track A location, spread, and skew differences by signed horizon gap.", "tab:trackA_moments_by_gap")
    write_table(moments_by_tte_gap, "tab_trackA_moments_by_tte_gap", "Track A spread diagnostics by time-to-expiry and signed horizon gap.", "tab:trackA_moments_by_tte_gap")
    write_table(tail_relative, "tab_trackA_tail_relative_wedge", "Track A tail and body relative divergence diagnostics.", "tab:trackA_tail_relative_wedge")
    write_table(gap_confounds, "tab_trackA_gap_confound_diagnostics", "Track A signed horizon-gap confound diagnostics.", "tab:trackA_gap_confound_diagnostics")

    save_l1_distribution(divergence)
    save_l1_by_gap(divergence)
    save_stale_vs_l1(divergence)
    save_repricing_quality(fits)
    save_cell_divergence_by_type(comparison)
    save_spread_by_gap(divergence)
    save_tte_vs_spread(divergence)
    example = save_example_distribution(comparison, divergence)

    main_div = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    main_comp = comparison[comparison["trackA_comparison_main_candidate"]].copy()
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_trackA_diagnostics.py",
        "git_commit": git_commit(),
        "inputs": {
            "event_day_quality": str(EVENT_DAY_QUALITY.relative_to(PROJECT_ROOT)),
            "event_day_divergence": str(EVENT_DAY_DIVERGENCE.relative_to(PROJECT_ROOT)),
            "daily_comparison": str(DAILY_COMPARISON.relative_to(PROJECT_ROOT)),
            "curve_fits": str(CURVE_FITS.relative_to(PROJECT_ROOT)),
        },
        "row_counts": {
            "trackA_event_day_panel_rows": int(len(event_day)),
            "curve_input_candidate_days": int(event_day["trackA_curve_input_candidate"].sum()),
            "curve_fit_days": int(len(fits)),
            "curve_quality_pass_days": int((fits["deribit_curve_quality"] == "pass").sum()),
            "main_comparison_event_days": int(main_div[["event_id", "date"]].drop_duplicates().shape[0]),
            "main_comparison_events": int(main_div["event_id"].nunique()),
            "main_comparison_cell_rows": int(len(main_comp)),
        },
        "headline_diagnostics": {
            "l1_mean": float(main_div["l1_normalized_divergence"].mean()),
            "l1_median": float(main_div["l1_normalized_divergence"].median()),
            "l1_p25": float(main_div["l1_normalized_divergence"].quantile(0.25)),
            "l1_p75": float(main_div["l1_normalized_divergence"].quantile(0.75)),
            "l2_mean": float(main_div["l2_normalized_divergence"].mean()),
            "l2_median": float(main_div["l2_normalized_divergence"].median()),
            "tail_divergence_mean": float(main_div["tail_normalized_divergence"].mean()),
            "tail_divergence_median": float(main_div["tail_normalized_divergence"].median()),
            "tail_relative_abs_divergence_mean": float(main_div["tail_relative_abs_divergence_mean"].mean()),
            "body_relative_abs_divergence_mean": float(main_div["body_relative_abs_divergence_mean"].mean()),
            "pm_spread_median": float(main_div["pm_spread"].median()),
            "deribit_spread_median": float(main_div["deribit_spread"].median()),
            "pm_wider_than_deribit_share": float((main_div["pm_spread"] > main_div["deribit_spread"]).mean()),
            "spread_diff_pm_minus_deribit_median": float(main_div["spread_diff_pm_minus_deribit"].median()),
            "option_reprice_rmse_coin_mean": float(main_div["option_reprice_rmse_coin"].mean()),
            "stale_share_mean": float(main_div["deribit_stale_bar_share"].mean()),
        },
        "gap_confound_diagnostics": gap_confounds.to_dict(orient="records"),
        "example_distribution": example,
        "outputs": {
            "tables_dir": str(TABLES_DIR.relative_to(PROJECT_ROOT)),
            "figures_dir": str(FIGURES_DIR.relative_to(PROJECT_ROOT)),
        },
        "known_caveats": [
            "These diagnostics are descriptive first-pass Track A outputs, not causal or tradability results.",
            "Raw Polymarket-Deribit differences mix physical-vs-risk-neutral wedges, horizon gaps, reference-basis mismatch, liquidity, and model error.",
            "Deribit curves use daily OHLC close and parity-implied spot; intraday non-synchronicity remains a limitation.",
        ],
    }
    (PANELS_DIR / "trackA_diagnostics_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Track A diagnostics ===")
    for key, value in summary["row_counts"].items():
        print(f"{key}: {value:,}")
    print("\nHeadline diagnostics:")
    for key, value in summary["headline_diagnostics"].items():
        print(f"{key}: {value:.6f}")
    print("\nExample distribution:")
    print(json.dumps(example, ensure_ascii=False))
    print("\nOutputs:")
    print(f"- {PANELS_DIR / 'trackA_diagnostics_summary.json'}")
    print(f"- {TABLES_DIR}")
    print(f"- {FIGURES_DIR}")


if __name__ == "__main__":
    main()
