# Probability Divergence and Price Discovery

This repository contains the reproducible empirical pipeline and frozen research outputs for a UCL MSc FinTech dissertation project on cross-market probability pricing in crypto markets.

Project title:

```text
Probability Divergence and Price Discovery between Polymarket BTC/ETH Price Events and Deribit Crypto Options
```

The project compares probabilities implied by Polymarket terminal BTC/ETH price-event markets with probabilities inferred from Deribit crypto option data. The focus is empirical measurement and price discovery, not a standalone trading-strategy claim.

## Research Objective

The core question is whether two market venues price similar terminal crypto price outcomes consistently:

```text
Polymarket event-implied probability
vs
Deribit option-implied risk-neutral probability
```

The comparison is intentionally conservative. A raw difference between the two markets is not treated as pure arbitrage or pure mispricing, because the two probability measures are conceptually different and the data are subject to liquidity, settlement, and timing frictions.

## Project Design

The empirical design is organized around two tracks.

### Track A: Probability Divergence

Track A compares full event probability distributions at a lower frequency.

Main idea:

- reconstruct Polymarket terminal price-event probability buckets;
- infer Deribit option-implied risk-neutral probabilities from option OHLC data;
- compare matched event-day distributions across BTC and ETH;
- document where divergence is larger, especially by tail/body cell, time to expiry, liquidity, and matching quality.

This track answers:

```text
How different are the two markets' implied probability distributions?
```

### Track B: Price Discovery / Lead-Lag

Track B studies whether one market reacts before the other.

Main idea:

- avoid high-frequency full-distribution reconstruction at the start;
- use local survival probabilities such as `P(S_T > K*)`;
- compare changes in Polymarket and Deribit probability series;
- control for stale prices and non-synchronous trading before interpreting any lead-lag result.

This track answers:

```text
Which market incorporates information first?
```

## Repository Structure

```text
.
├── data/
│   ├── raw/                  # raw API snapshots and downloaded market data
│   └── processed/            # cleaned panels, diagnostics, and metadata
├── docs/
│   ├── roadmap/              # topic outline and project roadmap
│   ├── specs/                # pipeline specifications and implementation notes
│   └── decision_logs/        # empirical freeze and decision records
├── paper/
│   ├── figures/              # final dissertation figures
│   └── tables/               # final dissertation tables
├── result/                   # exploratory and intermediate research outputs
├── scripts/
│   ├── P0_data_collection/   # API exploration and feasibility scripts
│   ├── P1_pipeline/          # main empirical pipeline scripts
│   └── P2_diagnostics/       # robustness, audit, and provenance scripts
└── tests/                    # regression and diagnostic tests
```

Large raw and processed data files should not be committed to Git unless they are deliberately reduced sample files.

## Stage Definitions

### P0: Data Collection and API Feasibility

Purpose:

- explore Polymarket public APIs;
- explore Deribit public option APIs;
- check whether market metadata, historical prices, and option OHLC data are accessible;
- identify data limitations before committing to an empirical specification.

Key scripts:

```text
scripts/P0_data_collection/build_polymarket_inventory.py
scripts/P0_data_collection/check_deribit_availability.py
scripts/P0_data_collection/polymarket_event_history_spike.py
scripts/P0_data_collection/deribit_single_expiry_grid_spike.py
```

### P1: Main Empirical Pipeline

Purpose:

- build canonical event/cell tables;
- download and process Polymarket history panels;
- download and process Deribit option OHLC panels;
- build Track A distribution-divergence diagnostics;
- build Track B local-survival and lead-lag panels.

Key script groups:

```text
scripts/P1_pipeline/build_polymarket_*.py
scripts/P1_pipeline/build_deribit_*.py
scripts/P1_pipeline/build_trackA_*.py
scripts/P1_pipeline/build_trackB_*.py
```

### P2: Diagnostics, Robustness, and Freeze Checks

Purpose:

- audit reference-basis and settlement mismatches;
- generate table provenance;
- run robustness checks around the frozen empirical result set;
- make the result set defensible for dissertation writing.

Key scripts:

```text
scripts/P2_diagnostics/build_reference_basis_audit.py
scripts/P2_diagnostics/build_frozen_input_manifest.py
scripts/P2_diagnostics/build_p1_table_provenance.py
scripts/P2_diagnostics/run_p1_freeze.py
scripts/P2_diagnostics/verify_p2_freeze.py
```

## Data Sources

The current project uses public API exploration around:

- Polymarket Gamma / public-search API for event and market metadata;
- Polymarket CLOB price-history style endpoints for event price histories;
- Deribit public option endpoints for option instruments and historical OHLC-style data.

Known data constraints:

- Polymarket and Deribit expiries may not match exactly.
- Settlement references may differ across venues.
- Historical Deribit order books for expired options are not straightforwardly available through the tested public endpoints.
- Option OHLC data may be based on last trades, so cross-strike prices are not guaranteed to be synchronous.
- Polymarket event prices and Deribit risk-neutral probabilities are related but not identical probability concepts.

## Frozen Empirical Snapshot

The current P2 freeze is generated from the tracked compact inputs and contains:

- Track A: 294 matched event-days across 61 events, with 3,114 comparison-cell rows;
- Track B: 1,121 jointly informative six-hour rows;
- Track B lead-lag regressions: 703 rows across 77 events;
- reference-basis audit: 124 events;
- paper-facing outputs: 30 CSV tables, matching LaTeX tables, and 8 PDF figures;
- automated checks: 17 tests plus a strict freeze verifier.

These counts are regression-tested. They describe the frozen sample rather than targets to be achieved by changing filters.

## Environment

The frozen project environment uses Python 3.11 and is locked by `uv.lock`:

```bash
uv sync --python 3.11
uv run pytest -q
```

The empirical scripts must run through this environment so that pandas,
SciPy, statsmodels, pyarrow, and matplotlib versions remain fixed.

## Running Scripts

Use the project root as the working directory:

```bash
cd /path/to/Probability-Divergence-and-Price-Discovery
```

Example P0 runs:

```bash
uv run python scripts/P0_data_collection/build_polymarket_inventory.py
uv run python scripts/P0_data_collection/check_deribit_availability.py
uv run python scripts/P0_data_collection/polymarket_event_history_spike.py
uv run python scripts/P0_data_collection/deribit_single_expiry_grid_spike.py
```

Some scripts call external market APIs and can take time. Run them deliberately, keep metadata outputs, and record the data snapshot date.

Rebuild the frozen paper-facing outputs from the tracked compact inputs with:

```bash
uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b
uv run python scripts/P2_diagnostics/verify_p2_freeze.py
uv run pytest -q
```

The freeze runner regenerates Track A and Track B diagnostics, the reference-basis audit, final tables and figures, and table-level provenance. The verifier rejects missing outputs, obsolete script paths, incorrect row counts, and unexpected changes to the frozen sample.

## Output Policy

Expected output locations:

```text
data/raw/                 raw API snapshots and downloaded market data
data/processed/           cleaned panels and metadata
result/                   intermediate or exploratory outputs
paper/figures/            final dissertation figures
paper/tables/             final dissertation tables
```

Research-output discipline:

- do not fabricate empirical results;
- keep raw data and large generated files out of Git;
- save metadata with generated datasets;
- distinguish exploratory diagnostics from frozen dissertation outputs;
- avoid interpreting probability divergence as arbitrage unless trading costs, timing, and execution constraints are explicitly handled.

## Current Status

P0 data feasibility, the P1 empirical pipeline, and the P2 engineering freeze are complete for the current BTC/ETH specification. The repository now includes a Python 3.11 lockfile, compact reproducibility inputs, table-level provenance, frozen-output regression tests, a reference-basis audit, and one-command regeneration of the paper-facing results.

The frozen results should still be interpreted conservatively. Cross-venue probability differences are not direct arbitrage estimates, clustered p-values do not establish causal price discovery, and settlement-reference mismatches and non-synchronous option OHLC observations remain material limitations.
