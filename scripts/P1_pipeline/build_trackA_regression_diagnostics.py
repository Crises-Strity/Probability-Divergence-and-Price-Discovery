"""
Build Track A moment-regression and robustness diagnostics.

This script is deliberately narrow: it does not claim causal identification.
It checks whether the spread wedge survives asset and Deribit time-to-expiry
controls, and whether the moment-layer spread sign is robust to open-tail
midpoint conventions.

Inputs:
- data/processed/panels/trackA_event_day_divergence.parquet
- data/processed/panels/daily_distribution_comparison.parquet
- data/processed/deribit/deribit_state_price_grid.parquet
- optional labelled trackA_event_day_divergence files for smoothness robustness

Outputs:
- data/processed/panels/trackA_regression_diagnostics_summary.json
- paper/tables/tab_trackA_spread_regressions.{csv,tex}
- paper/tables/tab_trackA_partial_spearman.{csv,tex}
- paper/tables/tab_trackA_tail_midpoint_robustness.{csv,tex}
- paper/tables/tab_trackA_state_grid_truncation.{csv,tex}
- paper/tables/tab_trackA_state_grid_truncation_top.{csv,tex}
- paper/tables/tab_trackA_smoothness_regression_robustness.{csv,tex}
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", str(Path("/private/tmp") / "matplotlib-codex"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path("/private/tmp") / "codex-cache"))

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import spearmanr


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
PANELS_DIR = PROJECT_ROOT / "data" / "processed" / "panels"
DERIBIT_DIR = PROJECT_ROOT / "data" / "processed" / "deribit"
TABLES_DIR = PROJECT_ROOT / "paper" / "tables"

EVENT_DAY_DIVERGENCE = PANELS_DIR / "trackA_event_day_divergence.parquet"
DAILY_COMPARISON = PANELS_DIR / "daily_distribution_comparison.parquet"
STATE_PRICE_GRID = DERIBIT_DIR / "deribit_state_price_grid.parquet"

GAP_ORDER = ["-32h", "-8h", "+16h", "+40h"]
SMOOTHNESS_REGRESSION_SPECS = [
    {"spec": "smooth005", "label": "smooth005", "smooth_weight": 0.05},
    {"spec": "baseline", "label": None, "smooth_weight": 0.10},
    {"spec": "smooth02", "label": "smooth02", "smooth_weight": 0.20},
]

SMOOTHNESS_GRID_SPECS = [
    {"spec": "smooth0", "label": "smooth0", "smooth_weight": 0.00},
    {"spec": "smooth005", "label": "smooth005", "smooth_weight": 0.05},
    {"spec": "baseline", "label": None, "smooth_weight": 0.10},
    {"spec": "smooth02", "label": "smooth02", "smooth_weight": 0.20},
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


def write_table(df: pd.DataFrame, stem: str, caption: str, label: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES_DIR / f"{stem}.csv", index=False, encoding="utf-8-sig")
    tex = df.to_latex(index=False, escape=True, caption=caption, label=label, float_format="%.4f")
    (TABLES_DIR / f"{stem}.tex").write_text(tex, encoding="utf-8")


def labelled_panel_path(base: str, label: str | None) -> Path:
    if label is None:
        return PANELS_DIR / f"{base}.parquet"
    return PANELS_DIR / f"{base}_{label}.parquet"


def main_sample(divergence: pd.DataFrame) -> pd.DataFrame:
    sample = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    sample["horizon_gap_bin"] = pd.Categorical(sample["horizon_gap_bin"], categories=GAP_ORDER, ordered=False)
    sample["asset"] = pd.Categorical(sample["asset"])
    sample["time_to_expiry_days"] = sample["time_to_expiry_hours"] / 24.0
    return sample.reset_index(drop=True)


def fit_clustered(formula: str, data: pd.DataFrame):
    model = smf.ols(formula=formula, data=data)
    return model.fit(cov_type="cluster", cov_kwds={"groups": data["event_id"], "use_correction": True})


def primary_spread_formula() -> str:
    return "spread_diff_pm_minus_deribit ~ C(horizon_gap_bin, Treatment(reference='-8h')) + time_to_expiry_days + C(asset)"


def tidy_model(result: Any, model_name: str, formula: str, sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for term in result.params.index:
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


def build_regression_table(sample: pd.DataFrame) -> pd.DataFrame:
    specs = [
        {
            "model": "spread_continuous_tte",
            "formula": primary_spread_formula(),
        },
        {
            "model": "spread_tte_fe",
            "formula": "spread_diff_pm_minus_deribit ~ C(horizon_gap_bin, Treatment(reference='-8h')) + C(time_to_expiry_hours) + C(asset)",
        },
        {
            "model": "location_continuous_tte",
            "formula": "location_diff_pm_minus_deribit ~ C(horizon_gap_bin, Treatment(reference='-8h')) + time_to_expiry_days + C(asset)",
        },
        {
            "model": "skew_continuous_tte",
            "formula": "skew_diff_pm_minus_deribit ~ C(horizon_gap_bin, Treatment(reference='-8h')) + time_to_expiry_days + C(asset)",
        },
    ]
    frames = []
    for spec in specs:
        result = fit_clustered(spec["formula"], sample)
        frames.append(tidy_model(result, spec["model"], spec["formula"], sample))
    return pd.concat(frames, ignore_index=True)


def residualize_rank(values: pd.Series, controls: pd.DataFrame) -> pd.Series:
    work = controls.copy()
    work["rank_value"] = values.rank(method="average")
    formula = "rank_value ~ C(asset) + C(time_to_expiry_hours)"
    result = smf.ols(formula=formula, data=work).fit()
    return pd.Series(result.resid, index=work.index)


def partial_spearman_table(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    variables = [
        "spread_diff_pm_minus_deribit",
        "spread_diff_deribit_minus_pm",
        "location_diff_pm_minus_deribit",
        "skew_diff_pm_minus_deribit",
        "l1_normalized_divergence",
    ]
    for variable in variables:
        valid = sample[["signed_gap_hours", variable, "asset", "time_to_expiry_hours"]].dropna().copy()
        gap_resid = residualize_rank(valid["signed_gap_hours"], valid[["asset", "time_to_expiry_hours"]])
        value_resid = residualize_rank(valid[variable], valid[["asset", "time_to_expiry_hours"]])
        rho, p_value = spearmanr(gap_resid, value_resid)
        rows.append(
            {
                "scope": "partial_asset_tte",
                "variable": variable,
                "asset": "pooled",
                "n": int(len(valid)),
                "spearman_rho": float(rho),
                "p_value": float(p_value),
            }
        )

    for asset, group in sample.groupby("asset", observed=True):
        for variable in variables:
            valid = group[["signed_gap_hours", variable]].dropna()
            rho, p_value = spearmanr(valid["signed_gap_hours"], valid[variable])
            rows.append(
                {
                    "scope": "within_asset",
                    "variable": variable,
                    "asset": str(asset),
                    "n": int(len(valid)),
                    "spearman_rho": float(rho),
                    "p_value": float(p_value),
                }
            )
    return pd.DataFrame(rows)


def finite_bucket_width(cells: pd.DataFrame) -> float:
    finite = cells[np.isfinite(cells["cell_low"]) & np.isfinite(cells["cell_high"])].copy()
    widths = (finite["cell_high"] - finite["cell_low"]).replace([np.inf, -np.inf], np.nan).dropna()
    if widths.empty:
        return math.nan
    return float(widths.median())


def cell_midpoint(low: float, high: float, width: float, tail_multiplier: float) -> float:
    if math.isfinite(low) and math.isfinite(high):
        return float((low + high) / 2.0)
    if math.isfinite(high) and math.isfinite(width):
        return float(high - tail_multiplier * width)
    if math.isfinite(low) and math.isfinite(width):
        return float(low + tail_multiplier * width)
    return math.nan


def moments_for_probability(group: pd.DataFrame, probability_col: str) -> dict[str, float]:
    probabilities = group[probability_col].to_numpy(dtype=float)
    x = group["tail_robust_moneyness"].to_numpy(dtype=float)
    valid = np.isfinite(probabilities) & np.isfinite(x)
    probabilities = probabilities[valid]
    x = x[valid]
    total = float(probabilities.sum())
    if total <= 0:
        return {"location": math.nan, "spread": math.nan, "skew": math.nan}
    probabilities = probabilities / total
    location = float(np.sum(probabilities * x))
    variance = float(np.sum(probabilities * (x - location) ** 2))
    spread = float(math.sqrt(max(variance, 0.0)))
    skew = float(np.sum(probabilities * (x - location) ** 3) / (spread**3)) if spread > 0 else math.nan
    return {"location": location, "spread": spread, "skew": skew}


def moment_panel_with_tail_multiplier(comparison: pd.DataFrame, tail_multiplier: float) -> pd.DataFrame:
    main = comparison[comparison["trackA_comparison_main_candidate"]].copy()
    rows = []
    for (event_id, date), group in main.groupby(["event_id", "date"], sort=True):
        group = group.sort_values("cell_id").copy()
        width = finite_bucket_width(group)
        midpoints = [
            cell_midpoint(float(row["cell_low"]), float(row["cell_high"]), width, tail_multiplier)
            for _, row in group.iterrows()
        ]
        group["tail_robust_mid"] = midpoints
        group["tail_robust_moneyness"] = group["tail_robust_mid"] / group["parity_implied_spot"] - 1.0
        pm = moments_for_probability(group, "pm_probability_normalized")
        deribit = moments_for_probability(group, "deribit_probability")
        rows.append(
            {
                "event_id": int(event_id),
                "date": str(date),
                "asset": group["asset"].iloc[0],
                "horizon_gap_bin": group["horizon_gap_bin"].iloc[0],
                "signed_gap_hours": float(group["signed_gap_hours"].iloc[0]),
                "time_to_expiry_hours": float(group["time_to_expiry_hours"].iloc[0]),
                "tail_multiplier": tail_multiplier,
                "pm_spread": pm["spread"],
                "deribit_spread": deribit["spread"],
                "spread_diff_pm_minus_deribit": pm["spread"] - deribit["spread"],
                "pm_wider_than_deribit": pm["spread"] > deribit["spread"],
                "pm_location": pm["location"],
                "deribit_location": deribit["location"],
                "location_diff_pm_minus_deribit": pm["location"] - deribit["location"],
                "pm_skew": pm["skew"],
                "deribit_skew": deribit["skew"],
                "skew_diff_pm_minus_deribit": pm["skew"] - deribit["skew"],
            }
        )
    return pd.DataFrame(rows)


def tail_midpoint_robustness_table(comparison: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    panels = [moment_panel_with_tail_multiplier(comparison, multiplier) for multiplier in [0.5, 1.0]]
    combined = pd.concat(panels, ignore_index=True)
    rows = []
    for multiplier, group in combined.groupby("tail_multiplier"):
        rho, p_value = spearmanr(group["signed_gap_hours"], group["spread_diff_pm_minus_deribit"])
        rows.append(
            {
                "tail_multiplier": float(multiplier),
                "event_days": int(len(group)),
                "events": int(group["event_id"].nunique()),
                "pm_spread_median": float(group["pm_spread"].median()),
                "deribit_spread_median": float(group["deribit_spread"].median()),
                "spread_diff_pm_minus_deribit_median": float(group["spread_diff_pm_minus_deribit"].median()),
                "pm_wider_share": float(group["pm_wider_than_deribit"].mean()),
                "spearman_gap_spread_diff": float(rho),
                "spearman_p_value": float(p_value),
            }
        )
    return pd.DataFrame(rows), combined


def state_grid_truncation_tables(sample: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    grid = pd.read_parquet(STATE_PRICE_GRID)
    key_columns = ["event_id", "date"]
    main_keys = sample[key_columns + ["asset", "horizon_gap_bin", "signed_gap_hours", "time_to_expiry_hours", "spread_diff_pm_minus_deribit"]].copy()
    main_keys["date"] = main_keys["date"].astype(str)

    rows = []
    grid["date"] = grid["date"].astype(str)
    for (event_id, date), group in grid.groupby(key_columns, sort=True):
        group = group.sort_values("state_id")
        rows.append(
            {
                "event_id": int(event_id),
                "date": str(date),
                "left_edge_probability": float(group["probability"].iloc[0]),
                "right_edge_probability": float(group["probability"].iloc[-1]),
                "edge_probability": float(group["probability"].iloc[0] + group["probability"].iloc[-1]),
                "n_state_intervals": int(len(group)),
                "state_lower_bound": float(group["state_left"].iloc[0]),
                "state_upper_bound": float(group["state_right"].iloc[-1]),
            }
        )
    edge_panel = pd.DataFrame(rows).merge(main_keys, on=key_columns, how="inner")
    edge_panel = edge_panel.sort_values(["event_id", "date"]).reset_index(drop=True)

    probabilities = edge_panel["edge_probability"]
    summary = pd.DataFrame(
        [
            {
                "event_days": int(len(edge_panel)),
                "events": int(edge_panel["event_id"].nunique()),
                "edge_probability_mean": float(probabilities.mean()),
                "edge_probability_median": float(probabilities.median()),
                "edge_probability_p90": float(probabilities.quantile(0.90)),
                "edge_probability_p95": float(probabilities.quantile(0.95)),
                "edge_probability_p99": float(probabilities.quantile(0.99)),
                "edge_probability_max": float(probabilities.max()),
                "days_edge_probability_gt_5pct": int((probabilities > 0.05).sum()),
                "share_edge_probability_gt_5pct": float((probabilities > 0.05).mean()),
            }
        ]
    )
    top = edge_panel.sort_values("edge_probability", ascending=False).head(10).reset_index(drop=True)
    return summary, top, edge_panel


def smoothness_regression_robustness_table() -> pd.DataFrame:
    rows = []
    formula = primary_spread_formula()
    keep_terms = [
        "C(horizon_gap_bin, Treatment(reference='-8h'))[T.-32h]",
        "C(horizon_gap_bin, Treatment(reference='-8h'))[T.+16h]",
        "C(horizon_gap_bin, Treatment(reference='-8h'))[T.+40h]",
        "C(asset)[T.ETH]",
        "time_to_expiry_days",
    ]
    for spec in SMOOTHNESS_REGRESSION_SPECS:
        path = labelled_panel_path("trackA_event_day_divergence", spec["label"])
        divergence = pd.read_parquet(path)
        sample = main_sample(divergence)
        result = fit_clustered(formula, sample)
        for term in keep_terms:
            rows.append(
                {
                    "spec": spec["spec"],
                    "smooth_weight": spec["smooth_weight"],
                    "term": term,
                    "coef": float(result.params[term]),
                    "std_error_event_cluster": float(result.bse[term]),
                    "p_value": float(result.pvalues[term]),
                    "n_obs": int(result.nobs),
                    "n_events": int(sample["event_id"].nunique()),
                    "r_squared": float(result.rsquared),
                    "pm_wider_share": float((sample["pm_spread"] > sample["deribit_spread"]).mean()),
                    "spread_diff_pm_minus_deribit_median": float(sample["spread_diff_pm_minus_deribit"].median()),
                }
            )
    return pd.DataFrame(rows)


def smoothness_common_keys() -> set[tuple[int, str]]:
    common: set[tuple[int, str]] | None = None
    for spec in SMOOTHNESS_GRID_SPECS:
        path = labelled_panel_path("trackA_event_day_divergence", spec["label"])
        divergence = pd.read_parquet(path)
        sample = divergence[divergence["trackA_comparison_main_candidate"]].copy()
        keys = set(zip(sample["event_id"].astype(int), sample["date"].astype(str)))
        common = keys if common is None else common & keys
    return common or set()


def smoothness_sample(spec: dict[str, object], common_keys: set[tuple[int, str]]) -> pd.DataFrame:
    path = labelled_panel_path("trackA_event_day_divergence", spec["label"])
    divergence = pd.read_parquet(path)
    sample = divergence[divergence["trackA_comparison_main_candidate"]].copy()
    sample["_smoothness_key"] = list(zip(sample["event_id"].astype(int), sample["date"].astype(str)))
    return sample[sample["_smoothness_key"].isin(common_keys)].copy().reset_index(drop=True)


def smoothness_fit_quality_table() -> pd.DataFrame:
    common_keys = smoothness_common_keys()
    rows = []
    for spec in SMOOTHNESS_GRID_SPECS:
        sample = smoothness_sample(spec, common_keys)
        rows.append(
            {
                "spec": spec["spec"],
                "smooth_weight": spec["smooth_weight"],
                "event_days_common": int(len(sample)),
                "events_common": int(sample["event_id"].nunique()),
                "option_reprice_rmse_coin_mean": float(sample["option_reprice_rmse_coin"].mean()),
                "option_reprice_rmse_coin_median": float(sample["option_reprice_rmse_coin"].median()),
                "option_reprice_rmse_coin_p90": float(sample["option_reprice_rmse_coin"].quantile(0.90)),
                "option_reprice_rmse_coin_p95": float(sample["option_reprice_rmse_coin"].quantile(0.95)),
                "option_reprice_rmse_coin_max": float(sample["option_reprice_rmse_coin"].max()),
                "fitted_forward_abs_rel_error_mean": float(sample["fitted_forward_rel_error"].abs().mean()),
            }
        )
    return pd.DataFrame(rows)


def smoothness_moment_grid_table() -> pd.DataFrame:
    common_keys = smoothness_common_keys()
    rows = []
    for spec in SMOOTHNESS_GRID_SPECS:
        sample = smoothness_sample(spec, common_keys)
        rows.append(
            {
                "spec": spec["spec"],
                "smooth_weight": spec["smooth_weight"],
                "event_days_common": int(len(sample)),
                "events_common": int(sample["event_id"].nunique()),
                "l1_median": float(sample["l1_normalized_divergence"].median()),
                "location_diff_median": float(sample["location_diff_pm_minus_deribit"].median()),
                "location_abs_diff_median": float(sample["location_diff_pm_minus_deribit"].abs().median()),
                "pm_higher_location_share": float((sample["location_diff_pm_minus_deribit"] > 0).mean()),
                "pm_spread_median": float(sample["pm_spread"].median()),
                "deribit_spread_median": float(sample["deribit_spread"].median()),
                "spread_diff_pm_minus_deribit_median": float(sample["spread_diff_pm_minus_deribit"].median()),
                "pm_wider_share": float((sample["spread_diff_pm_minus_deribit"] > 0).mean()),
                "tail_relative_abs_divergence_mean": float(sample["tail_relative_abs_divergence_mean"].mean()),
                "body_relative_abs_divergence_mean": float(sample["body_relative_abs_divergence_mean"].mean()),
                "tail_log_odds_divergence_mean": float(sample["tail_log_odds_divergence_mean"].mean()),
                "body_log_odds_divergence_mean": float(sample["body_log_odds_divergence_mean"].mean()),
                "tail_normalized_divergence_median": float(sample["tail_normalized_divergence"].median()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    divergence = pd.read_parquet(EVENT_DAY_DIVERGENCE)
    comparison = pd.read_parquet(DAILY_COMPARISON)
    sample = main_sample(divergence)

    regression = build_regression_table(sample)
    partial = partial_spearman_table(sample)
    tail_robust, tail_panel = tail_midpoint_robustness_table(comparison)
    truncation, truncation_top, truncation_panel = state_grid_truncation_tables(sample)
    smoothness_regression = smoothness_regression_robustness_table()
    smoothness_fit_quality = smoothness_fit_quality_table()
    smoothness_moment_grid = smoothness_moment_grid_table()

    write_table(regression, "tab_trackA_spread_regressions", "Track A moment regressions with event-clustered standard errors.", "tab:trackA_spread_regressions")
    write_table(partial, "tab_trackA_partial_spearman", "Track A partial and within-asset Spearman diagnostics.", "tab:trackA_partial_spearman")
    write_table(tail_robust, "tab_trackA_tail_midpoint_robustness", "Track A spread robustness to open-tail midpoint conventions.", "tab:trackA_tail_midpoint_robustness")
    write_table(truncation, "tab_trackA_state_grid_truncation", "Track A Deribit state-grid edge probability diagnostics.", "tab:trackA_state_grid_truncation")
    write_table(truncation_top, "tab_trackA_state_grid_truncation_top", "Largest Track A Deribit state-grid edge probabilities.", "tab:trackA_state_grid_truncation_top")
    write_table(smoothness_regression, "tab_trackA_smoothness_regression_robustness", "Track A spread-regression robustness to RND smoothness weight.", "tab:trackA_smoothness_regression_robustness")
    write_table(smoothness_fit_quality, "tab_trackA_smoothness_fit_quality", "Track A option repricing fit quality by RND smoothness weight.", "tab:trackA_smoothness_fit_quality")
    write_table(smoothness_moment_grid, "tab_trackA_smoothness_moment_grid", "Track A location, spread, and tail diagnostics by RND smoothness weight.", "tab:trackA_smoothness_moment_grid")
    tail_panel.to_csv(PANELS_DIR / "trackA_tail_midpoint_moment_panel.csv", index=False, encoding="utf-8-sig")
    tail_panel.to_parquet(PANELS_DIR / "trackA_tail_midpoint_moment_panel.parquet", index=False)
    truncation_panel.to_csv(PANELS_DIR / "trackA_state_grid_truncation.csv", index=False, encoding="utf-8-sig")
    truncation_panel.to_parquet(PANELS_DIR / "trackA_state_grid_truncation.parquet", index=False)

    spread_terms = regression[
        (regression["model"].isin(["spread_continuous_tte", "spread_tte_fe"]))
        & regression["term"].str.contains("horizon_gap_bin", regex=False)
    ].copy()
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_trackA_regression_diagnostics.py",
        "git_commit": git_commit(),
        "inputs": {
            "event_day_divergence": str(EVENT_DAY_DIVERGENCE.relative_to(PROJECT_ROOT)),
            "daily_comparison": str(DAILY_COMPARISON.relative_to(PROJECT_ROOT)),
        },
        "row_counts": {
            "main_event_days": int(len(sample)),
            "main_events": int(sample["event_id"].nunique()),
            "regression_rows": int(len(regression)),
            "partial_spearman_rows": int(len(partial)),
            "tail_midpoint_rows": int(len(tail_robust)),
            "truncation_rows": int(len(truncation)),
            "truncation_panel_rows": int(len(truncation_panel)),
            "smoothness_regression_rows": int(len(smoothness_regression)),
            "smoothness_fit_quality_rows": int(len(smoothness_fit_quality)),
            "smoothness_moment_grid_rows": int(len(smoothness_moment_grid)),
        },
        "primary_formula": primary_spread_formula(),
        "headline": {
            "spread_gap_terms": spread_terms[["model", "term", "coef", "std_error_event_cluster", "p_value"]].to_dict(orient="records"),
            "tail_midpoint_robustness": tail_robust.to_dict(orient="records"),
            "state_grid_truncation": truncation.to_dict(orient="records"),
            "smoothness_regression_robustness": smoothness_regression.to_dict(orient="records"),
            "smoothness_fit_quality": smoothness_fit_quality.to_dict(orient="records"),
            "smoothness_moment_grid": smoothness_moment_grid.to_dict(orient="records"),
        },
        "known_caveats": [
            "These regressions are diagnostic controls for observed composition, not causal maturity estimates.",
            "Event-clustered standard errors use 61 event clusters; sub-sample slices should not be promoted over the pooled controlled specification.",
            "Open-tail midpoint conventions affect spread magnitudes, so spread sign and comparative robustness are safer than a single point estimate.",
            "The generated-regressor spread level depends on the RND smoothness penalty; smoothness robustness checks show that heavy smoothing attenuates the unconditional PM-wider spread sign.",
        ],
    }
    (PANELS_DIR / "trackA_regression_diagnostics_summary.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Track A regression diagnostics ===")
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value:,}")
    print("\nPrimary spread gap terms:")
    print(spread_terms[["model", "term", "coef", "std_error_event_cluster", "p_value"]].to_string(index=False))
    print("\nTail midpoint robustness:")
    print(tail_robust.to_string(index=False))
    print("\nState-grid truncation:")
    print(truncation.to_string(index=False))
    print("\nSmoothness regression robustness:")
    print(smoothness_regression.to_string(index=False))
    print("\nSmoothness fit quality:")
    print(smoothness_fit_quality.to_string(index=False))
    print("\nSmoothness moment grid:")
    print(smoothness_moment_grid.to_string(index=False))
    print("\nOutputs:")
    print(f"- {PANELS_DIR / 'trackA_regression_diagnostics_summary.json'}")
    print(f"- {TABLES_DIR / 'tab_trackA_spread_regressions.tex'}")
    print(f"- {TABLES_DIR / 'tab_trackA_partial_spearman.tex'}")
    print(f"- {TABLES_DIR / 'tab_trackA_tail_midpoint_robustness.tex'}")
    print(f"- {TABLES_DIR / 'tab_trackA_state_grid_truncation.tex'}")
    print(f"- {TABLES_DIR / 'tab_trackA_smoothness_regression_robustness.tex'}")
    print(f"- {TABLES_DIR / 'tab_trackA_smoothness_fit_quality.tex'}")
    print(f"- {TABLES_DIR / 'tab_trackA_smoothness_moment_grid.tex'}")


if __name__ == "__main__":
    main()
