"""
Fit Track A Deribit daily risk-neutral state-price panels.

Inputs:
- data/raw/deribit/ohlc_<event_id>_1D.parquet
- data/processed/panels/trackA_event_day_quality.parquet
- data/processed/panels/trackA_pm_cell_day_panel.parquet

Outputs:
- data/processed/deribit/deribit_curve_fits.{csv,parquet}
- data/processed/deribit/deribit_state_price_grid.{csv,parquet}
- data/processed/panels/daily_distribution_comparison.{csv,parquet}
- data/processed/panels/trackA_event_day_divergence.{csv,parquet}
- data/processed/panels/trackA_deribit_rnd_metadata.json
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
RAW_DERIBIT_DIR = PROJECT_ROOT / "data" / "raw" / "deribit"
DERIBIT_DIR = PROJECT_ROOT / "data" / "processed" / "deribit"
PANELS_DIR = PROJECT_ROOT / "data" / "processed" / "panels"

EVENT_DAY_QUALITY = PANELS_DIR / "trackA_event_day_quality.parquet"
PM_CELL_DAY = PANELS_DIR / "trackA_pm_cell_day_panel.parquet"


class FitError(RuntimeError):
    """Raised when an event-day cannot produce a usable option-implied fit."""


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


def raw_ohlc_path(event_id: int, resolution: str) -> Path:
    label = str(resolution).replace("/", "_")
    return RAW_DERIBIT_DIR / f"ohlc_{event_id}_{label}.parquet"


def write_table(df: pd.DataFrame, directory: Path, stem: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    df.to_csv(directory / f"{stem}.csv", index=False, encoding="utf-8-sig")
    df.to_parquet(directory / f"{stem}.parquet", index=False)


def output_stem(base: str, label: str | None) -> str:
    if not label:
        return base
    clean = "".join(ch for ch in label if ch.isalnum() or ch in {"_", "-"})
    if clean != label or not clean:
        raise ValueError("output label must contain only letters, numbers, underscores, or hyphens")
    return f"{base}_{clean}"


def finite_list(values: pd.Series) -> list[float]:
    result: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            result.append(number)
    return result


def infer_spot_from_put_call_parity(traded: pd.DataFrame) -> dict[str, float]:
    pivot = traded.pivot_table(index="strike", columns="option_type", values="close", aggfunc="last")
    if not {"call", "put"}.issubset(pivot.columns):
        raise FitError("missing call/put pairs for parity-implied spot")

    paired = pivot[["call", "put"]].dropna().copy()
    paired["denominator"] = 1.0 - (paired["call"] - paired["put"])
    paired["implied_spot"] = paired.index.astype(float) / paired["denominator"]
    valid = paired[
        paired["denominator"].between(0.2, 2.0)
        & np.isfinite(paired["implied_spot"])
        & (paired["implied_spot"] > 0)
    ].copy()
    if len(valid) < 3:
        raise FitError(f"too few valid parity pairs: {len(valid)}")

    q25, q75 = valid["implied_spot"].quantile([0.25, 0.75])
    median = float(valid["implied_spot"].median())
    return {
        "spot": median,
        "n_parity_pairs": int(len(valid)),
        "parity_spot_std": float(valid["implied_spot"].std(ddof=0)),
        "parity_spot_iqr": float(q75 - q25),
        "parity_spot_rel_iqr": float((q75 - q25) / median) if median > 0 else math.nan,
    }


def state_boundaries(traded: pd.DataFrame, cells: pd.DataFrame, spot: float, lower_mult: float, upper_mult: float) -> list[float]:
    traded_strikes = finite_list(traded["strike"])
    cell_bounds = finite_list(cells["cell_low"]) + finite_list(cells["cell_high"])
    anchors = traded_strikes + cell_bounds + [spot]
    if len(anchors) < 4:
        raise FitError("not enough strikes/cell boundaries for state grid")

    lower = max(1.0, min(anchors) * lower_mult)
    upper = max(anchors) * upper_mult
    raw_bounds = sorted(set([lower, upper] + traded_strikes + cell_bounds))

    bounds: list[float] = []
    for value in raw_bounds:
        if not bounds or abs(value - bounds[-1]) > 1e-8:
            bounds.append(float(value))
    if len(bounds) < 4:
        raise FitError("state grid has fewer than 3 intervals")
    return bounds


def option_input_diagnostics(traded: pd.DataFrame, spot: float) -> dict[str, int]:
    calls = traded[traded["option_type"] == "call"].sort_values("strike")
    violations = 0
    convexity_violations = 0
    if len(calls) >= 2:
        call_prices = calls["close"].to_numpy(dtype=float) * spot
        violations = int(np.sum(np.diff(call_prices) > max(1e-8, 1e-6 * spot)))
    if len(calls) >= 3:
        strikes = calls["strike"].to_numpy(dtype=float)
        call_prices = calls["close"].to_numpy(dtype=float) * spot
        slopes = np.diff(call_prices) / np.diff(strikes)
        convexity_violations = int(np.sum(np.diff(slopes) < -1e-5))
    return {
        "input_call_monotonicity_violations": violations,
        "input_call_convexity_violations": convexity_violations,
    }


def fit_state_probabilities(
    traded: pd.DataFrame,
    states: np.ndarray,
    spot: float,
    sum_weight: float,
    mean_weight: float,
    smooth_weight: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    rows: list[np.ndarray] = []
    y: list[float] = []

    for _, row in traded.iterrows():
        strike = float(row["strike"])
        option_price_coin = float(row["close"])
        if row["option_type"] == "call":
            payoff = np.maximum(states - strike, 0.0) / spot
        elif row["option_type"] == "put":
            payoff = np.maximum(strike - states, 0.0) / spot
        else:
            continue
        rows.append(payoff)
        y.append(option_price_coin)

    if len(rows) < 8:
        raise FitError(f"too few option observations for fit: {len(rows)}")

    rows.append(np.ones(len(states)) * sum_weight)
    y.append(sum_weight)
    rows.append((states / spot) * mean_weight)
    y.append(mean_weight)

    if smooth_weight > 0 and len(states) >= 3:
        for idx in range(len(states) - 2):
            row = np.zeros(len(states))
            row[idx] = 1.0
            row[idx + 1] = -2.0
            row[idx + 2] = 1.0
            rows.append(row * smooth_weight)
            y.append(0.0)

    matrix = np.vstack(rows)
    target = np.asarray(y, dtype=float)
    result = lsq_linear(matrix, target, bounds=(0.0, np.inf), tol=1e-10, lsmr_tol="auto", max_iter=1000)
    if not result.success:
        raise FitError(f"lsq_linear failed: {result.message}")

    probabilities = np.asarray(result.x, dtype=float)
    raw_sum = float(probabilities.sum())
    if raw_sum <= 0 or not math.isfinite(raw_sum):
        raise FitError("non-positive fitted probability sum")
    probabilities = probabilities / raw_sum

    predicted: list[float] = []
    actual: list[float] = []
    for _, row in traded.iterrows():
        strike = float(row["strike"])
        if row["option_type"] == "call":
            payoff = np.maximum(states - strike, 0.0) / spot
        else:
            payoff = np.maximum(strike - states, 0.0) / spot
        predicted.append(float(probabilities @ payoff))
        actual.append(float(row["close"]))

    errors = np.asarray(predicted) - np.asarray(actual)
    diagnostics = {
        "optimizer_cost": float(result.cost),
        "probability_sum_raw": raw_sum,
        "probability_sum": float(probabilities.sum()),
        "probability_min": float(probabilities.min()),
        "negative_density_share": float(np.mean(probabilities < -1e-10)),
        "fitted_forward": float(probabilities @ states),
        "fitted_forward_rel_error": float((probabilities @ states) / spot - 1.0),
        "option_reprice_rmse_coin": float(np.sqrt(np.mean(errors**2))),
        "option_reprice_max_abs_coin": float(np.max(np.abs(errors))),
        "option_reprice_rmse_usd": float(np.sqrt(np.mean(errors**2)) * spot),
        "option_reprice_max_abs_usd": float(np.max(np.abs(errors)) * spot),
    }
    return probabilities, diagnostics


def cell_probability(states: np.ndarray, probabilities: np.ndarray, low: float, high: float) -> float:
    mask = np.ones(len(states), dtype=bool)
    if math.isfinite(low):
        mask &= states >= low
    if math.isfinite(high):
        mask &= states < high
    return float(probabilities[mask].sum())


def finite_bucket_width(cells: pd.DataFrame) -> float:
    finite = cells[np.isfinite(cells["cell_low"]) & np.isfinite(cells["cell_high"])].copy()
    widths = (finite["cell_high"] - finite["cell_low"]).replace([np.inf, -np.inf], np.nan).dropna()
    if widths.empty:
        return math.nan
    return float(widths.median())


def cell_midpoint(low: float, high: float, fallback_width: float) -> float:
    if math.isfinite(low) and math.isfinite(high):
        return float((low + high) / 2.0)
    if math.isfinite(high) and math.isfinite(fallback_width):
        return float(high - fallback_width / 2.0)
    if math.isfinite(low) and math.isfinite(fallback_width):
        return float(low + fallback_width / 2.0)
    return math.nan


def safe_logit(probability: float, eps: float = 1e-6) -> float:
    value = min(max(float(probability), eps), 1.0 - eps)
    return float(math.log(value / (1.0 - value)))


def distribution_moments(group: pd.DataFrame, probability_col: str) -> dict[str, float]:
    probabilities = group[probability_col].to_numpy(dtype=float)
    x = group["cell_moneyness"].to_numpy(dtype=float)
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


def moneyness_bucket(low: float, high: float, spot: float) -> str:
    if not math.isfinite(low):
        return "left_tail"
    if not math.isfinite(high):
        return "right_tail"
    midpoint = (low + high) / 2.0
    ratio = midpoint / spot
    if ratio < 0.95:
        return "below_0.95"
    if ratio <= 1.05:
        return "near_0.95_1.05"
    return "above_1.05"


def curve_quality_label(fit_row: dict[str, Any], args: argparse.Namespace) -> str:
    checks = [
        abs(float(fit_row["probability_sum"]) - 1.0) <= args.sum_tolerance,
        float(fit_row["probability_min"]) >= -args.min_probability_tolerance,
        abs(float(fit_row["fitted_forward_rel_error"])) <= args.forward_rel_error_tolerance,
        float(fit_row["option_reprice_rmse_coin"]) <= args.rmse_coin_tolerance,
        float(fit_row["deribit_probability_sum_error_abs"]) <= args.sum_tolerance,
    ]
    return "pass" if all(checks) else "fail_sanity"


def fit_event_day(
    event_day: pd.Series,
    cells: pd.DataFrame,
    ohlc: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    event_id = int(event_day["event_id"])
    date = str(event_day["date"])
    traded = ohlc[
        (ohlc["timestamp"].dt.date.astype(str) == date)
        & (ohlc["has_real_trade"])
        & (ohlc["close"].fillna(0) > 0)
    ].copy()
    if traded.empty:
        raise FitError("no traded option rows for event-day")

    spot_info = infer_spot_from_put_call_parity(traded)
    spot = spot_info["spot"]
    bounds = state_boundaries(traded, cells, spot, args.lower_state_mult, args.upper_state_mult)
    states = np.asarray([(left + right) / 2.0 for left, right in zip(bounds[:-1], bounds[1:])], dtype=float)
    probabilities, fit_diag = fit_state_probabilities(
        traded=traded,
        states=states,
        spot=spot,
        sum_weight=args.sum_weight,
        mean_weight=args.mean_weight,
        smooth_weight=args.smooth_weight,
    )

    comparison_rows: list[dict[str, Any]] = []
    fallback_width = finite_bucket_width(cells)
    for _, cell in cells.sort_values("sort_key").iterrows():
        low = float(cell["cell_low"])
        high = float(cell["cell_high"])
        mid = cell_midpoint(low, high, fallback_width)
        cell_moneyness = mid / spot - 1.0 if math.isfinite(mid) and spot > 0 else math.nan
        deribit_prob = cell_probability(states, probabilities, low, high)
        pm_raw = float(cell["pm_probability_raw"])
        pm_norm = float(cell["pm_probability_normalized"])
        normalized_divergence = pm_norm - deribit_prob
        relative_abs_divergence = abs(normalized_divergence) / pm_norm if pm_norm > 0 else math.nan
        comparison_rows.append(
            {
                "event_id": event_id,
                "date": date,
                "cell_id": int(cell["cell_id"]),
                "market_id": int(cell["market_id"]),
                "cell_type": cell["cell_type"],
                "cell_low": low,
                "cell_high": high,
                "pm_probability_raw": pm_raw,
                "pm_probability_normalized": pm_norm,
                "deribit_probability": deribit_prob,
                "raw_divergence": pm_raw - deribit_prob,
                "normalized_divergence": normalized_divergence,
                "relative_abs_normalized_divergence": relative_abs_divergence,
                "log_odds_divergence": safe_logit(pm_norm) - safe_logit(deribit_prob),
                "pm_sum_error": float(event_day["pm_sum_error"]),
                "asset": event_day["asset"],
                "event_title": event_day["event_title"],
                "pm_snapshot_timestamp": event_day["pm_snapshot_timestamp"],
                "target_snapshot_timestamp": event_day["deribit_bar_timestamp"],
                "time_to_expiry_hours": (
                    pd.Timestamp(event_day["nearest_deribit_expiry"])
                    - pd.Timestamp(event_day["deribit_bar_timestamp"])
                ).total_seconds()
                / 3600.0,
                "signed_gap_hours": float(event_day["signed_gap_hours"]),
                "horizon_gap_bin": event_day["horizon_gap_bin"],
                "settlement_reference": event_day["settlement_reference"],
                "deribit_index_reference": event_day["deribit_index_reference"],
                "reference_basis_mismatch": bool(event_day["reference_basis_mismatch"]),
                "tail_cell_flag": cell["cell_type"] in {"left_tail", "right_tail"},
                "cell_mid": mid,
                "cell_moneyness": cell_moneyness,
                "moneyness_bucket": moneyness_bucket(low, high, spot),
                "pm_trackA_quality_flag": event_day["pm_trackA_quality_flag"],
                "deribit_stale_bar_share": float(event_day["deribit_stale_bar_share"]),
                "deribit_total_volume": float(event_day["deribit_total_volume"]),
                "n_fresh_strikes_after_stale": int(event_day["n_fresh_strikes_after_stale"]),
                "deribit_strike_range_covers_pm": bool(event_day["deribit_strike_range_covers_pm"]),
                "trackA_core_gap_minus8h": bool(event_day["trackA_core_gap_minus8h"]),
                "trackA_near_gap_abs_le_16h": bool(event_day["trackA_near_gap_abs_le_16h"]),
                "trackA_spread_clean": bool(event_day["trackA_spread_clean"]),
            }
        )

    deribit_sum = float(sum(row["deribit_probability"] for row in comparison_rows))
    fit_row = {
        "event_id": event_id,
        "date": date,
        "asset": event_day["asset"],
        "status": "fit_success",
        "failure_reason": None,
        "spot_source": "put_call_parity_median_from_same_day_traded_close",
        "parity_implied_spot": spot,
        **spot_info,
        **option_input_diagnostics(traded, spot),
        **fit_diag,
        "n_option_observations": int(len(traded)),
        "n_call_observations": int((traded["option_type"] == "call").sum()),
        "n_put_observations": int((traded["option_type"] == "put").sum()),
        "n_distinct_strikes_used": int(traded["strike"].nunique()),
        "n_state_intervals": int(len(states)),
        "state_lower_bound": float(bounds[0]),
        "state_upper_bound": float(bounds[-1]),
        "deribit_probability_sum": deribit_sum,
        "deribit_probability_sum_error": deribit_sum - 1.0,
        "deribit_probability_sum_error_abs": abs(deribit_sum - 1.0),
        "pm_sum_error": float(event_day["pm_sum_error"]),
        "pm_event_probability_sum": float(event_day["pm_event_probability_sum"]),
        "target_snapshot_timestamp": event_day["deribit_bar_timestamp"],
        "pm_snapshot_timestamp": event_day["pm_snapshot_timestamp"],
        "signed_gap_hours": float(event_day["signed_gap_hours"]),
        "horizon_gap_bin": event_day["horizon_gap_bin"],
        "reference_basis_mismatch": bool(event_day["reference_basis_mismatch"]),
        "deribit_stale_bar_share": float(event_day["deribit_stale_bar_share"]),
        "deribit_total_volume": float(event_day["deribit_total_volume"]),
        "deribit_intraday_trade_time_diagnostics_available": bool(
            event_day["deribit_intraday_trade_time_diagnostics_available"]
        )
        if pd.notna(event_day["deribit_intraday_trade_time_diagnostics_available"])
        else False,
    }
    fit_row["deribit_curve_quality"] = curve_quality_label(fit_row, args)

    for row in comparison_rows:
        row["deribit_sum_error"] = fit_row["deribit_probability_sum_error"]
        row["deribit_curve_quality"] = fit_row["deribit_curve_quality"]
        row["trackA_comparison_main_candidate"] = fit_row["deribit_curve_quality"] == "pass"
        row["parity_implied_spot"] = spot
        row["option_reprice_rmse_coin"] = fit_row["option_reprice_rmse_coin"]
        row["fitted_forward_rel_error"] = fit_row["fitted_forward_rel_error"]

    state_rows = [
        {
            "event_id": event_id,
            "date": date,
            "state_id": idx + 1,
            "state_left": float(bounds[idx]),
            "state_right": float(bounds[idx + 1]),
            "state_mid": float(states[idx]),
            "probability": float(probabilities[idx]),
            "parity_implied_spot": spot,
            "deribit_curve_quality": fit_row["deribit_curve_quality"],
        }
        for idx in range(len(states))
    ]
    return fit_row, state_rows, comparison_rows


def failed_fit_row(event_day: pd.Series, reason: str) -> dict[str, Any]:
    return {
        "event_id": int(event_day["event_id"]),
        "date": str(event_day["date"]),
        "asset": event_day["asset"],
        "status": "fit_failed",
        "failure_reason": reason,
        "deribit_curve_quality": "fit_failed",
        "pm_sum_error": float(event_day["pm_sum_error"]),
        "pm_event_probability_sum": float(event_day["pm_event_probability_sum"]),
        "target_snapshot_timestamp": event_day["deribit_bar_timestamp"],
        "pm_snapshot_timestamp": event_day["pm_snapshot_timestamp"],
        "signed_gap_hours": float(event_day["signed_gap_hours"]),
        "horizon_gap_bin": event_day["horizon_gap_bin"],
        "reference_basis_mismatch": bool(event_day["reference_basis_mismatch"]),
        "deribit_stale_bar_share": float(event_day["deribit_stale_bar_share"]),
        "deribit_total_volume": float(event_day["deribit_total_volume"]) if pd.notna(event_day["deribit_total_volume"]) else math.nan,
    }


def build_event_day_divergence(comparison: pd.DataFrame) -> pd.DataFrame:
    if comparison.empty:
        return pd.DataFrame()
    rows = []
    for (event_id, date), group in comparison.groupby(["event_id", "date"], sort=True):
        tail = group[group["tail_cell_flag"]]
        body = group[~group["tail_cell_flag"]]
        pm_moments = distribution_moments(group, "pm_probability_normalized")
        deribit_moments = distribution_moments(group, "deribit_probability")
        location_diff = pm_moments["location"] - deribit_moments["location"]
        spread_diff = pm_moments["spread"] - deribit_moments["spread"]
        skew_diff = pm_moments["skew"] - deribit_moments["skew"]
        rows.append(
            {
                "event_id": int(event_id),
                "date": date,
                "asset": group["asset"].iloc[0],
                "deribit_curve_quality": group["deribit_curve_quality"].iloc[0],
                "trackA_comparison_main_candidate": bool(group["trackA_comparison_main_candidate"].iloc[0]),
                "l1_normalized_divergence": float(group["normalized_divergence"].abs().sum()),
                "l2_normalized_divergence": float(np.sqrt(np.square(group["normalized_divergence"]).sum())),
                "max_abs_normalized_divergence": float(group["normalized_divergence"].abs().max()),
                "mean_abs_normalized_divergence": float(group["normalized_divergence"].abs().mean()),
                "tail_normalized_divergence": float(tail["normalized_divergence"].sum()) if not tail.empty else math.nan,
                "tail_abs_normalized_divergence_mean": float(tail["normalized_divergence"].abs().mean()) if not tail.empty else math.nan,
                "body_abs_normalized_divergence_mean": float(body["normalized_divergence"].abs().mean()) if not body.empty else math.nan,
                "tail_relative_abs_divergence_mean": float(tail["relative_abs_normalized_divergence"].mean()) if not tail.empty else math.nan,
                "tail_relative_abs_divergence_median": float(tail["relative_abs_normalized_divergence"].median()) if not tail.empty else math.nan,
                "body_relative_abs_divergence_mean": float(body["relative_abs_normalized_divergence"].mean()) if not body.empty else math.nan,
                "body_relative_abs_divergence_median": float(body["relative_abs_normalized_divergence"].median()) if not body.empty else math.nan,
                "tail_log_odds_divergence_mean": float(tail["log_odds_divergence"].mean()) if not tail.empty else math.nan,
                "body_log_odds_divergence_mean": float(body["log_odds_divergence"].mean()) if not body.empty else math.nan,
                "pm_location": pm_moments["location"],
                "deribit_location": deribit_moments["location"],
                "location_diff_pm_minus_deribit": location_diff,
                "pm_spread": pm_moments["spread"],
                "deribit_spread": deribit_moments["spread"],
                "spread_diff_pm_minus_deribit": spread_diff,
                "spread_diff_deribit_minus_pm": -spread_diff if math.isfinite(spread_diff) else math.nan,
                "pm_skew": pm_moments["skew"],
                "deribit_skew": deribit_moments["skew"],
                "skew_diff_pm_minus_deribit": skew_diff,
                "pm_sum_error": float(group["pm_sum_error"].iloc[0]),
                "deribit_sum_error": float(group["deribit_sum_error"].iloc[0]),
                "time_to_expiry_hours": float(group["time_to_expiry_hours"].iloc[0]),
                "signed_gap_hours": float(group["signed_gap_hours"].iloc[0]),
                "horizon_gap_bin": group["horizon_gap_bin"].iloc[0],
                "reference_basis_mismatch": bool(group["reference_basis_mismatch"].iloc[0]),
                "parity_implied_spot": float(group["parity_implied_spot"].iloc[0]),
                "option_reprice_rmse_coin": float(group["option_reprice_rmse_coin"].iloc[0]),
                "fitted_forward_rel_error": float(group["fitted_forward_rel_error"].iloc[0]),
                "deribit_stale_bar_share": float(group["deribit_stale_bar_share"].iloc[0]),
                "deribit_total_volume": float(group["deribit_total_volume"].iloc[0]),
            }
        )
    return pd.DataFrame(rows).sort_values(["event_id", "date"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolution", default="1D")
    parser.add_argument("--max-event-days", type=int, default=None)
    parser.add_argument("--lower-state-mult", type=float, default=0.5)
    parser.add_argument("--upper-state-mult", type=float, default=1.5)
    parser.add_argument("--sum-weight", type=float, default=20.0)
    parser.add_argument("--mean-weight", type=float, default=10.0)
    parser.add_argument("--smooth-weight", type=float, default=0.1)
    parser.add_argument("--output-label", default=None, help="Optional suffix for sensitivity outputs without overwriting the baseline.")
    parser.add_argument("--sum-tolerance", type=float, default=1e-6)
    parser.add_argument("--min-probability-tolerance", type=float, default=1e-10)
    parser.add_argument("--forward-rel-error-tolerance", type=float, default=0.05)
    parser.add_argument("--rmse-coin-tolerance", type=float, default=0.02)
    args = parser.parse_args()

    event_day = pd.read_parquet(EVENT_DAY_QUALITY)
    cell_day = pd.read_parquet(PM_CELL_DAY)
    candidates = event_day[event_day["trackA_curve_input_candidate"]].copy()
    candidates = candidates.sort_values(["event_id", "date"]).reset_index(drop=True)
    if args.max_event_days is not None:
        candidates = candidates.head(args.max_event_days).copy()

    ohlc_cache: dict[int, pd.DataFrame] = {}
    fit_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []

    for _, day in candidates.iterrows():
        event_id = int(day["event_id"])
        date = str(day["date"])
        if event_id not in ohlc_cache:
            path = raw_ohlc_path(event_id, args.resolution)
            if not path.exists():
                fit_rows.append(failed_fit_row(day, f"missing raw OHLC file: {path}"))
                continue
            ohlc_cache[event_id] = pd.read_parquet(path)

        cells = cell_day[
            (cell_day["event_id"].astype(int) == event_id)
            & (cell_day["date"].astype(str) == date)
            & (cell_day["trackA_curve_input_candidate"])
        ].copy()
        if cells.empty:
            fit_rows.append(failed_fit_row(day, "missing Polymarket cell rows"))
            continue

        try:
            fit_row, day_state_rows, day_comparison_rows = fit_event_day(day, cells, ohlc_cache[event_id], args)
            fit_rows.append(fit_row)
            state_rows.extend(day_state_rows)
            comparison_rows.extend(day_comparison_rows)
        except Exception as exc:  # noqa: BLE001 - persist failed event-day reason for audit.
            fit_rows.append(failed_fit_row(day, f"{type(exc).__name__}: {exc}"))

    fits = pd.DataFrame(fit_rows).sort_values(["event_id", "date"]).reset_index(drop=True)
    states = pd.DataFrame(state_rows).sort_values(["event_id", "date", "state_id"]).reset_index(drop=True)
    comparison = pd.DataFrame(comparison_rows).sort_values(["event_id", "date", "cell_id"]).reset_index(drop=True)
    divergence = build_event_day_divergence(comparison)

    fit_stem = output_stem("deribit_curve_fits", args.output_label)
    state_stem = output_stem("deribit_state_price_grid", args.output_label)
    comparison_stem = output_stem("daily_distribution_comparison", args.output_label)
    divergence_stem = output_stem("trackA_event_day_divergence", args.output_label)
    metadata_stem = output_stem("trackA_deribit_rnd_metadata", args.output_label)

    write_table(fits, DERIBIT_DIR, fit_stem)
    write_table(states, DERIBIT_DIR, state_stem)
    write_table(comparison, PANELS_DIR, comparison_stem)
    write_table(divergence, PANELS_DIR, divergence_stem)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py",
        "git_commit": git_commit(),
        "inputs": {
            "event_day_quality": str(EVENT_DAY_QUALITY.relative_to(PROJECT_ROOT)),
            "pm_cell_day": str(PM_CELL_DAY.relative_to(PROJECT_ROOT)),
            "raw_deribit_ohlc_dir": str(RAW_DERIBIT_DIR.relative_to(PROJECT_ROOT)),
        },
        "method": {
            "price_unit": "Deribit option close is coin-denominated; the script infers same-day spot from call-put parity and fits normalized coin payoffs.",
            "spot_source": "median K / (1 - (call_close - put_close)) across same-day traded call-put pairs.",
            "fit": "non-negative state probabilities fitted by constrained least squares to call and put payoffs, with soft sum, forward, and second-difference smoothness penalties.",
            "main_quality_gate": "deribit_curve_quality == pass",
        },
        "parameters": vars(args),
        "outputs": {
            "curve_fits": str((DERIBIT_DIR / f"{fit_stem}.parquet").relative_to(PROJECT_ROOT)),
            "state_price_grid": str((DERIBIT_DIR / f"{state_stem}.parquet").relative_to(PROJECT_ROOT)),
            "daily_comparison": str((PANELS_DIR / f"{comparison_stem}.parquet").relative_to(PROJECT_ROOT)),
            "event_day_divergence": str((PANELS_DIR / f"{divergence_stem}.parquet").relative_to(PROJECT_ROOT)),
        },
        "row_counts": {
            "candidate_event_days": int(len(candidates)),
            "fit_rows": int(len(fits)),
            "fit_success_days": int((fits["status"] == "fit_success").sum()) if not fits.empty else 0,
            "curve_quality_pass_days": int((fits["deribit_curve_quality"] == "pass").sum()) if not fits.empty else 0,
            "state_rows": int(len(states)),
            "comparison_rows": int(len(comparison)),
            "comparison_event_days": int(comparison[["event_id", "date"]].drop_duplicates().shape[0]) if not comparison.empty else 0,
        },
        "known_caveats": [
            "This is a first-pass shape-constrained state-price fit, not an IV/SVI production model.",
            "Historical Deribit index levels are not stored in the current raw files; same-day call-put parity is used as the USD conversion/forward anchor.",
            "Daily OHLC close is not a simultaneous cross-strike snapshot; intraday trade-time diagnostics remain unavailable in the 1D panel.",
            "reference_basis_mismatch remains true because Polymarket settlement references Binance 1m close while Deribit uses Deribit indexes.",
        ],
    }
    (PANELS_DIR / f"{metadata_stem}.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Track A Deribit RND panel ===")
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value:,}")
    if not fits.empty:
        print("\nCurve quality:")
        print(fits["deribit_curve_quality"].value_counts(dropna=False).to_string())
        print("\nFailure status:")
        print(fits["status"].value_counts(dropna=False).to_string())
    if not divergence.empty:
        print("\nMain divergence summary:")
        main_div = divergence[divergence["trackA_comparison_main_candidate"]]
        print(main_div[["l1_normalized_divergence", "l2_normalized_divergence"]].describe().to_string())
    print("\nOutputs:")
    print(f"- {DERIBIT_DIR / f'{fit_stem}.parquet'}")
    print(f"- {DERIBIT_DIR / f'{state_stem}.parquet'}")
    print(f"- {PANELS_DIR / f'{comparison_stem}.parquet'}")
    print(f"- {PANELS_DIR / f'{divergence_stem}.parquet'}")
    print(f"- {PANELS_DIR / f'{metadata_stem}.json'}")


if __name__ == "__main__":
    main()
