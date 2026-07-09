# Probability Divergence and Price Discovery

This repository contains the code and research materials for a UCL MSc FinTech dissertation project on cross-market probability pricing in crypto markets.

Working topic:

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
├── dissertation/             # dissertation chapter drafts and bibliography
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
scripts/P2_diagnostics/build_p1_table_provenance.py
scripts/P2_diagnostics/run_p1_freeze.py
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

## Running Scripts

Use the project root as the working directory:

```bash
cd /path/to/Probability-Divergence-and-Price-Discovery
```

Example P0 runs:

```bash
python scripts/P0_data_collection/build_polymarket_inventory.py
python scripts/P0_data_collection/check_deribit_availability.py
python scripts/P0_data_collection/polymarket_event_history_spike.py
python scripts/P0_data_collection/deribit_single_expiry_grid_spike.py
```

Some scripts call external market APIs and can take time. Run them deliberately, keep metadata outputs, and record the data snapshot date.

## Environment

The repository currently assumes a local Python data-science environment with common packages such as:

```text
pandas
numpy
scipy
statsmodels
matplotlib
pyarrow
requests
python-dateutil
```

A fully frozen environment file is still a TODO. Until then, avoid relying on unstated package versions for final dissertation results.

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

The project is organized around the two-track design above. Initial API exploration and pipeline scripts exist, and the repository structure has been separated into P0 data collection, P1 main pipeline, and P2 diagnostics. The next engineering priority is to keep the pipeline reproducible as the dissertation specification is narrowed.
