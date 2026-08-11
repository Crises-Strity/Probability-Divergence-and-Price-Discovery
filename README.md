# Probability Divergence and Price Discovery

Frozen empirical project for the UCL MSc FinTech dissertation:

```text
Probability Divergence and Price Discovery between Polymarket BTC/ETH Price Events and Deribit Crypto Options
```

The repository measures whether Polymarket terminal price-event probabilities
and Deribit option-implied risk-neutral probabilities price comparable BTC/ETH
outcomes consistently. It is a reproducible measurement project, not a claim
of executable arbitrage or a deployable trading strategy.

## Project Status

The empirical specification and conclusions are frozen.

| Stage | Purpose | Final status |
|---|---|---|
| P0 | API and data feasibility | Complete |
| P1 | Track A distribution divergence and Track B lead-lag analysis | Complete and empirically frozen |
| P2 | Robustness, provenance, environment lock, and freeze verification | Complete |
| P3 | SOL Track A feasibility extension | `FAIL` -- stopped before estimator construction |

P3 confirmed that SOL instruments and contract-unit adaptation were
technically accessible, but a mechanically selected three-expiry OHLC smoke
probe produced zero event-days passing the frozen P1 cross-strike quality
gates. The project therefore stopped rather than relax filters after observing
liquidity or construct an RND from sparse strike updates.

## Frozen Conclusions

### Track A: distribution divergence

The final sample contains 294 event-days across 61 events and 3,114 cell-day
rows.

- Distribution centers align: the location-difference intercept is `0.000572`
  with `p = 0.801546`.
- Under the baseline RND smoothing weight (`0.10`), the median Polymarket minus
  Deribit spread difference is `0.004022`, and Polymarket is wider on
  `0.707483` of event-days.
- The width result is smoothing-conditional. At smoothing weight `0.20`, the
  common-sample median spread difference falls to `0.000843` and the
  Polymarket-wider share to `0.525597`.
- Mean relative absolute divergence is larger in tails than in body cells:
  `0.857979` versus `0.570604`.

The defensible Track A conclusion is center alignment with material relative
tail divergence. A consistently wider Polymarket distribution is not a
sign-invariant result.

### Track B: integration and price discovery

At six-hour frequency, the frozen sample contains 1,121 jointly informative
rows and 703 regression rows. Level correlation is `0.911992`, while the
contemporaneous change correlation is `0.534829`.

Cross-market integration and contemporaneous co-movement are supported.
Directional leadership is not identified: the Deribit OHLC change series
remains noisier and negatively autocorrelated, symmetric lead correlations are
small, and sub-six-hour lead-lag is not measurable with the available
liquidity.

The paper-facing source of truth is
[`docs/decision_logs/P1_PAPER_CONCLUSIONS.md`](docs/decision_logs/P1_PAPER_CONCLUSIONS.md).
The frozen interpretation and P3 stop decision are recorded in
[`docs/decision_logs/P1_EMPIRICAL_FREEZE.md`](docs/decision_logs/P1_EMPIRICAL_FREEZE.md)
and
[`docs/decision_logs/P3_SOL_FEASIBILITY_DECISION.md`](docs/decision_logs/P3_SOL_FEASIBILITY_DECISION.md).

## Research Design

Track A reconstructs lower-frequency Polymarket terminal distributions and
compares them with Deribit risk-neutral distributions inferred from option
OHLC data. Track B uses local survival probabilities, such as
`P(S_T > K*)`, to study convergence and lead-lag without repeatedly fitting a
full high-frequency distribution.

The comparison is deliberately conservative. Polymarket probabilities and
Deribit risk-neutral probabilities are different economic objects, and the
venues also differ in settlement reference, horizon, liquidity, and price
staleness.

## Repository Structure

```text
.
├── configs/                 # version-controlled runtime configuration
├── data/
│   ├── raw/                 # local only; ignored by Git
│   └── processed/           # compact frozen inputs plus local generated data
├── docs/
│   ├── roadmap/             # high-level project roadmap
│   ├── specs/               # P0--P3 pipeline and output specifications
│   ├── decision_logs/       # empirical freezes and stopping decisions
│   └── superpowers/         # repository design and implementation records
├── paper/
│   ├── figures/             # frozen paper-facing figures
│   └── tables/              # frozen CSV and LaTeX tables with provenance
├── result/                  # local exploratory/intermediate outputs; ignored
├── scripts/
│   ├── P0_data_collection/  # API exploration and feasibility
│   ├── P1_pipeline/         # main empirical pipeline
│   ├── P2_diagnostics/      # robustness, audit, provenance, freeze checks
│   └── P3_asset_extension/  # frozen SOL extension feasibility code
└── tests/                   # regression, manifest, and freeze tests
```

The dissertation is intentionally not embedded in this repository.

## Stage Summary

### P0: data feasibility

P0 mapped Polymarket public metadata/history endpoints and Deribit public
instrument/OHLC endpoints, then documented expiry matching, settlement, and
historical-liquidity constraints before fixing the empirical design.

### P1: main empirical pipeline

P1 builds canonical event cells, Polymarket histories, Deribit option panels,
Track A distribution diagnostics, and Track B survival/lead-lag panels.

### P2: engineering and empirical freeze

P2 locks Python dependencies, records compact-input hashes and schemas,
generates table provenance, audits settlement-reference assumptions, and
strictly verifies frozen row counts and paper outputs.

### P3: stopped SOL extension

P3 tests whether the frozen Track A design transfers to SOL. It retains the P1
quality gates and stops before estimator construction because the smoke sample
has zero passing event-days. The JSON under `configs/` is its executable
parameter source, not a planning document.

## Data and Reproducibility Policy

Raw API snapshots, bulk panels, and exploratory results are not committed to
Git. The deliberate exception is a compact processed package of 11 Parquet
inputs, approximately 2.8 MB in total, required to rebuild the frozen tables
and figures.

[`data/processed/frozen_input_manifest.json`](data/processed/frozen_input_manifest.json)
records each tracked input's SHA-256 hash, byte size, row count, and ordered
schema. These files reproduce the frozen empirical outputs; they do not
reproduce the original API collection step because historical public-market
responses can change after the snapshot date.

## Environment and Verification

The project uses Python 3.11 with dependencies locked in `uv.lock`.

```bash
uv sync --python 3.11
uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b
uv run python scripts/P2_diagnostics/verify_p2_freeze.py
uv run pytest -q
```

The freeze runner regenerates the paper-facing diagnostics, tables, figures,
and provenance from the tracked compact inputs. The strict verifier rejects
missing inputs or outputs, changed hashes or schemas, obsolete script paths,
and unexpected frozen-sample counts.

Scripts that call external APIs should be run only for audit or replication,
with their snapshot date recorded. They are not required for the frozen
paper-output rebuild.

## Dissertation Workflow

The dissertation has its own repository:
[UCL-Final-Dissertation](https://github.com/Crises-Strity/UCL-Final-Dissertation).

The source-of-truth flow is:

```text
Overleaf -> dedicated GitHub repository -> standalone local clone
```

Normal writing and compilation happen in Overleaf. Completed checkpoints are
pushed from Overleaf to the dedicated GitHub repository, then pulled into the
standalone local dissertation clone for local inspection. This empirical
project repository neither vendors nor tracks the manuscript.

## Interpretation Boundaries

- Probability differences are not direct arbitrage estimates.
- The spread sign is conditional on RND smoothing.
- Gap coefficients are composition controls, not causal maturity effects.
- Clustered regression significance does not identify a price-discovery
  leader when measurement error is asymmetric.
- Settlement-reference mismatch, non-synchronous option OHLC observations,
  and liquidity remain material limitations.
- P3 is a documented feasibility failure, not evidence that SOL markets or
  instruments do not exist.
