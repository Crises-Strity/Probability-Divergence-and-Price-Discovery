"""
Build Track B Deribit hourly local survival-probability panel.

The estimator is deliberately local. It does not fit a full hourly RND.
For each event-hour, it:
1. keeps fresh traded option rows in the 60-minute OHLC candle;
2. infers a same-hour parity spot from traded call/put pairs;
3. converts two traded calls bracketing K* into USD call values;
4. estimates P(S_T > K*) with a local call-spread digital.

Timestamp convention:
- Deribit TradingView 60-minute ticks are treated as hour-bucket labels.
- The close value is interpreted as the last OHLC value inside that hour bucket.
- This aligns with pm_survival_hourly.timestamp, which is the floored hour of the
  last sampled Polymarket observation in that hour. Residual non-synchronicity
  remains a limitation until trades-level timestamps are available.

Inputs:
- data/processed/panels/trackB_kstar_panel.parquet
- data/raw/deribit/ohlc_<event_id>_60.parquet

Outputs:
- data/processed/panels/deribit_survival_hourly.{csv,parquet}
- data/processed/panels/deribit_survival_<Nh>.{csv,parquet}
- data/processed/panels/trackB_deribit_survival_metadata[_<Nh>].json
- paper/tables/tab_trackB_deribit_survival_summary.{csv,tex}
"""

from __future__ import annotations

import argparse
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


def find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists() and (parent / ".git").exists():
            return parent
    raise RuntimeError("Could not locate project root.")


PROJECT_ROOT = find_project_root()
RAW_DERIBIT_DIR = PROJECT_ROOT / "data" / "raw" / "deribit"
PANELS_DIR = PROJECT_ROOT / "data" / "processed" / "panels"
TABLES_DIR = PROJECT_ROOT / "paper" / "tables"

KSTAR_PANEL = PANELS_DIR / "trackB_kstar_panel.parquet"
RESOLUTION = "60"


class SurvivalError(RuntimeError):
    """Raised when an event-hour cannot produce a local Deribit survival estimate."""


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


def raw_ohlc_path(event_id: int, resolution: str = RESOLUTION) -> Path:
    label = str(resolution).replace("/", "_")
    return RAW_DERIBIT_DIR / f"ohlc_{event_id}_{label}.parquet"


def output_suffix(bar_hours: int) -> str:
    return "" if bar_hours == 1 else f"_{bar_hours}h"


def output_stem(base: str, bar_hours: int) -> str:
    return f"{base}{output_suffix(bar_hours)}"


def aggregate_to_blocks(ohlc: pd.DataFrame, bar_hours: int) -> pd.DataFrame:
    if bar_hours == 1 or ohlc.empty:
        return ohlc

    work = ohlc.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True)
    work["source_hour_timestamp"] = work["timestamp"]
    work["timestamp"] = work["timestamp"].dt.floor(f"{bar_hours}h")
    traded = work[work["has_real_trade"] & work["close"].fillna(0).gt(0)].copy()
    if traded.empty:
        return work.iloc[0:0].copy()

    keys = ["event_id", "currency", "expiry", "instrument_name", "option_type", "strike", "timestamp"]
    last_traded = (
        traded.sort_values(keys + ["source_hour_timestamp"])
        .groupby(keys, as_index=False)
        .tail(1)
        .copy()
    )
    volume = traded.groupby(keys, as_index=False).agg(
        volume=("volume", "sum"),
        cost=("cost", "sum"),
        block_trade_hours=("source_hour_timestamp", "nunique"),
        first_trade_hour=("source_hour_timestamp", "min"),
        last_trade_hour=("source_hour_timestamp", "max"),
    )
    aggregated = last_traded.drop(columns=["volume", "cost"], errors="ignore").merge(volume, on=keys, how="left")
    aggregated["has_real_trade"] = True
    aggregated["trade_timestamp_used"] = aggregated["last_trade_hour"]
    aggregated["target_snapshot_timestamp"] = aggregated["timestamp"]
    aggregated["minutes_from_target_snapshot"] = (
        pd.to_datetime(aggregated["last_trade_hour"], utc=True) - pd.to_datetime(aggregated["timestamp"], utc=True)
    ).dt.total_seconds() / 60.0
    aggregated["time_since_last_trade_minutes"] = (bar_hours * 60.0) - aggregated["minutes_from_target_snapshot"]
    aggregated["bar_stale_flag"] = False
    return aggregated.sort_values(["event_id", "timestamp", "strike", "option_type"]).reset_index(drop=True)


def infer_spot_from_put_call_parity(traded: pd.DataFrame) -> dict[str, float]:
    pivot = traded.pivot_table(index="strike", columns="option_type", values="close", aggfunc="last")
    if not {"call", "put"}.issubset(pivot.columns):
        raise SurvivalError("missing_call_put_pair_for_parity")

    paired = pivot[["call", "put"]].dropna().copy()
    paired["denominator"] = 1.0 - (paired["call"] - paired["put"])
    paired["parity_spot"] = paired.index.astype(float) / paired["denominator"]
    valid = paired[
        paired["denominator"].between(0.2, 2.0)
        & np.isfinite(paired["parity_spot"])
        & (paired["parity_spot"] > 0)
    ].copy()
    if valid.empty:
        raise SurvivalError("no_valid_parity_pair")

    q25, q75 = valid["parity_spot"].quantile([0.25, 0.75])
    spot = float(valid["parity_spot"].median())
    return {
        "parity_implied_spot": spot,
        "n_parity_pairs": int(len(valid)),
        "parity_spot_iqr": float(q75 - q25),
        "parity_spot_rel_iqr": float((q75 - q25) / spot) if spot > 0 else math.nan,
    }


def choose_bracketing_calls(calls: pd.DataFrame, k_star: float) -> tuple[pd.Series, pd.Series]:
    calls = calls.sort_values("strike").copy()
    below = calls[calls["strike"].astype(float) < k_star]
    above = calls[calls["strike"].astype(float) > k_star]
    if below.empty or above.empty:
        raise SurvivalError("missing_fresh_call_strikes_bracketing_kstar")
    low = below.iloc[-1]
    high = above.iloc[0]
    if float(high["strike"]) <= float(low["strike"]):
        raise SurvivalError("invalid_call_strike_bracket")
    return low, high


def estimate_event_hour(event: pd.Series, hour: pd.Timestamp, group: pd.DataFrame) -> dict[str, Any]:
    event_id = int(event["event_id"])
    k_star = float(event["K_star"])
    traded = group[group["has_real_trade"] & group["close"].fillna(0).gt(0)].copy()
    if traded.empty:
        raise SurvivalError("no_fresh_traded_options")

    spot_info = infer_spot_from_put_call_parity(traded)
    spot = spot_info["parity_implied_spot"]
    calls = traded[traded["option_type"].eq("call")].copy()
    low_call, high_call = choose_bracketing_calls(calls, k_star)

    low_strike = float(low_call["strike"])
    high_strike = float(high_call["strike"])
    low_call_usd = float(low_call["close"]) * spot
    high_call_usd = float(high_call["close"]) * spot
    raw_survival = -(high_call_usd - low_call_usd) / (high_strike - low_strike)
    clipped_survival = min(max(raw_survival, 0.0), 1.0)
    clipped = abs(clipped_survival - raw_survival) > 1e-12

    return {
        "event_id": event_id,
        "timestamp": hour,
        "asset": event["asset"],
        "event_type_for_trackB": event["event_type_for_trackB"],
        "K_star": k_star,
        "K_star_source": event["K_star_source"],
        "deribit_survival": float(clipped_survival),
        "deribit_survival_raw": float(raw_survival),
        "deribit_survival_clipped": bool(clipped),
        "deribit_survival_status": "pass",
        "failure_reason": None,
        "deribit_survival_source": "local_call_spread_digital",
        "timestamp_alignment": "hour_bucket_floor_close_aligned",
        "parity_implied_spot": spot,
        "n_parity_pairs": spot_info["n_parity_pairs"],
        "parity_spot_iqr": spot_info["parity_spot_iqr"],
        "parity_spot_rel_iqr": spot_info["parity_spot_rel_iqr"],
        "kstar_moneyness": k_star / spot - 1.0 if spot > 0 else math.nan,
        "lower_call_strike": low_strike,
        "upper_call_strike": high_strike,
        "call_bracket_width": high_strike - low_strike,
        "lower_call_close_coin": float(low_call["close"]),
        "upper_call_close_coin": float(high_call["close"]),
        "lower_call_volume": float(low_call["volume"]),
        "upper_call_volume": float(high_call["volume"]),
        "n_fresh_option_rows": int(len(traded)),
        "n_fresh_call_strikes": int(calls["strike"].nunique()),
        "n_fresh_put_strikes": int(traded.loc[traded["option_type"].eq("put"), "strike"].nunique()),
        "deribit_total_volume": float(traded["volume"].sum(skipna=True)),
        "deribit_has_real_trade": True,
        "deribit_local_bracket_ok": True,
    }


def failure_row(event: pd.Series, hour: pd.Timestamp, group: pd.DataFrame, reason: str) -> dict[str, Any]:
    traded = group[group["has_real_trade"] & group["close"].fillna(0).gt(0)].copy()
    return {
        "event_id": int(event["event_id"]),
        "timestamp": hour,
        "asset": event["asset"],
        "event_type_for_trackB": event["event_type_for_trackB"],
        "K_star": float(event["K_star"]),
        "K_star_source": event["K_star_source"],
        "deribit_survival": math.nan,
        "deribit_survival_raw": math.nan,
        "deribit_survival_clipped": pd.NA,
        "deribit_survival_status": "fail",
        "failure_reason": reason,
        "deribit_survival_source": "local_call_spread_digital",
        "timestamp_alignment": "hour_bucket_floor_close_aligned",
        "parity_implied_spot": math.nan,
        "n_parity_pairs": 0,
        "parity_spot_iqr": math.nan,
        "parity_spot_rel_iqr": math.nan,
        "kstar_moneyness": math.nan,
        "lower_call_strike": math.nan,
        "upper_call_strike": math.nan,
        "call_bracket_width": math.nan,
        "lower_call_close_coin": math.nan,
        "upper_call_close_coin": math.nan,
        "lower_call_volume": math.nan,
        "upper_call_volume": math.nan,
        "n_fresh_option_rows": int(len(traded)),
        "n_fresh_call_strikes": int(traded.loc[traded["option_type"].eq("call"), "strike"].nunique()) if not traded.empty else 0,
        "n_fresh_put_strikes": int(traded.loc[traded["option_type"].eq("put"), "strike"].nunique()) if not traded.empty else 0,
        "deribit_total_volume": float(traded["volume"].sum(skipna=True)) if not traded.empty else 0.0,
        "deribit_has_real_trade": bool(not traded.empty),
        "deribit_local_bracket_ok": False,
    }


def build_event_survival(event: pd.Series, bar_hours: int) -> pd.DataFrame:
    path = raw_ohlc_path(int(event["event_id"]))
    if not path.exists():
        return pd.DataFrame(
            [
                failure_row(
                    event,
                    pd.NaT,
                    pd.DataFrame(columns=["has_real_trade", "close", "option_type", "strike", "volume"]),
                    "missing_60min_ohlc_file",
                )
            ]
        )

    ohlc = pd.read_parquet(path)
    if ohlc.empty:
        return pd.DataFrame(
            [
                failure_row(
                    event,
                    pd.NaT,
                    pd.DataFrame(columns=["has_real_trade", "close", "option_type", "strike", "volume"]),
                    "empty_60min_ohlc_file",
                )
            ]
        )
    ohlc["timestamp"] = pd.to_datetime(ohlc["timestamp"], utc=True)
    ohlc = aggregate_to_blocks(ohlc, bar_hours)

    rows = []
    for hour, group in ohlc.groupby("timestamp", sort=True):
        try:
            rows.append(estimate_event_hour(event, hour, group))
        except SurvivalError as exc:
            rows.append(failure_row(event, hour, group, str(exc)))
    return pd.DataFrame(rows)


def finalize_panel(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return panel
    panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True, errors="coerce")
    panel = panel.sort_values(["event_id", "timestamp"]).reset_index(drop=True)
    panel["deribit_survival_change"] = panel.groupby("event_id")["deribit_survival"].diff()
    panel["deribit_survival_abs_change"] = panel["deribit_survival_change"].abs()
    panel["trackB_deribit_informative_candidate"] = (
        panel["deribit_survival_status"].eq("pass")
        & panel["deribit_survival"].notna()
        & panel["deribit_survival"].gt(0.05)
        & panel["deribit_survival"].lt(0.95)
        & panel["deribit_has_real_trade"].fillna(False)
        & panel["deribit_local_bracket_ok"].fillna(False)
    )
    return panel


def write_table(df: pd.DataFrame, stem: str, caption: str, label: str) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TABLES_DIR / f"{stem}.csv", index=False, encoding="utf-8-sig")
    tex = df.to_latex(index=False, escape=True, caption=caption, label=label, float_format="%.4f")
    (TABLES_DIR / f"{stem}.tex").write_text(tex, encoding="utf-8")


def summary_table(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    rows = []
    valid = panel[panel["timestamp"].notna()].copy()
    for event_type, group in valid.groupby("event_type_for_trackB", dropna=False):
        passed = group[group["deribit_survival_status"].eq("pass")].copy()
        rows.append(
            {
                "event_type_for_trackB": event_type,
                "events": int(group["event_id"].nunique()),
                "hourly_bars": int(len(group)),
                "pass_bars": int(group["deribit_survival_status"].eq("pass").sum()),
                "pass_share": float(group["deribit_survival_status"].eq("pass").mean()),
                "informative_bars": int(group["trackB_deribit_informative_candidate"].sum()),
                "informative_share": float(group["trackB_deribit_informative_candidate"].mean()),
                "pass_median_survival": float(passed["deribit_survival"].median()) if not passed.empty else math.nan,
                "pass_median_abs_change": float(passed["deribit_survival_abs_change"].median()) if not passed.empty else math.nan,
                "pass_median_fresh_call_strikes": float(passed["n_fresh_call_strikes"].median()) if not passed.empty else math.nan,
                "pass_median_parity_pairs": float(passed["n_parity_pairs"].median()) if not passed.empty else math.nan,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bar-hours", type=int, default=1, help="Block size in hours; 1 uses raw 60-minute bars, 6 aggregates raw 60-minute OHLC to 6h blocks.")
    args = parser.parse_args()
    if args.bar_hours < 1:
        raise ValueError("--bar-hours must be positive")

    kstar = pd.read_parquet(KSTAR_PANEL)
    primary = kstar[
        kstar["kstar_selection_status"].eq("pass")
        & kstar["event_type_for_trackB"].eq("bucket_distribution")
    ].copy()

    frames = [build_event_survival(event, args.bar_hours) for _, event in primary.iterrows()]
    panel = finalize_panel(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame()
    summary = summary_table(panel)

    PANELS_DIR.mkdir(parents=True, exist_ok=True)
    panel_stem = output_stem("deribit_survival_hourly", args.bar_hours) if args.bar_hours == 1 else output_stem("deribit_survival", args.bar_hours)
    metadata_stem = output_stem("trackB_deribit_survival_metadata", args.bar_hours)
    table_stem = output_stem("tab_trackB_deribit_survival_summary", args.bar_hours)
    panel.to_csv(PANELS_DIR / f"{panel_stem}.csv", index=False, encoding="utf-8-sig")
    panel.to_parquet(PANELS_DIR / f"{panel_stem}.parquet", index=False)
    write_table(summary, table_stem, f"Track B Deribit local survival-probability summary ({args.bar_hours}h bars).", f"tab:trackB_deribit_survival_summary{output_suffix(args.bar_hours)}")

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_name": "scripts/P1_pipeline/build_trackB_deribit_survival_panel.py",
        "git_commit": git_commit(),
        "inputs": {
            "kstar_panel": str(KSTAR_PANEL.relative_to(PROJECT_ROOT)),
            "raw_60min_ohlc": "data/raw/deribit/ohlc_<event_id>_60.parquet",
        },
        "filter_rules": {
            "primary_events": "bucket_distribution events with pass K* selection",
            "bar_hours": args.bar_hours,
            "bar_construction": "1h uses raw Deribit 60-minute OHLC; Nh aggregates fresh traded 60-minute rows and uses the last traded close inside the block.",
            "fresh_option_row": "has_real_trade and close > 0 within the Deribit 60-minute OHLC candle",
            "spot_anchor": "median same-hour put-call parity spot from traded call/put pairs",
            "survival_estimator": "local call-spread digital using nearest traded call strikes strictly below and above K*",
            "timestamp_alignment": "Deribit and Polymarket hourly panels are aligned on floored hour-bucket labels; close/last sampled values are interpreted as within-hour endpoints.",
        },
        "row_counts": {
            "selected_events": int(len(primary)),
            "events_with_rows": int(panel.loc[panel["timestamp"].notna(), "event_id"].nunique()) if not panel.empty else 0,
            "rows": int(len(panel)),
            "pass_rows": int(panel["deribit_survival_status"].eq("pass").sum()) if not panel.empty else 0,
            "informative_rows": int(panel["trackB_deribit_informative_candidate"].sum()) if not panel.empty else 0,
        },
        "summary": summary.to_dict(orient="records"),
        "known_caveats": [
            "Deribit TradingView 60-minute OHLC does not expose exact last-trade timestamps inside the candle.",
            "The local call-spread digital is a first-pass estimator; it is sensitive to sparse hourly call strikes around K*.",
            "Bars without same-hour parity pairs or bracketing fresh call strikes fail explicitly and must not enter lead-lag tests.",
        ],
    }
    (PANELS_DIR / f"{metadata_stem}.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n=== Track B Deribit survival panel ===")
    for key, value in metadata["row_counts"].items():
        print(f"{key}: {value:,}")
    print("\nSummary:")
    print(summary.to_string(index=False) if not summary.empty else "empty")
    if not panel.empty:
        failures = panel.loc[panel["deribit_survival_status"].eq("fail"), "failure_reason"].value_counts()
        print("\nFailure reasons:")
        print(failures.to_string() if not failures.empty else "none")
    print("\nOutputs:")
    print(f"- {PANELS_DIR / f'{panel_stem}.parquet'}")
    print(f"- {PANELS_DIR / f'{metadata_stem}.json'}")
    print(f"- {TABLES_DIR / f'{table_stem}.tex'}")


if __name__ == "__main__":
    main()
