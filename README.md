# UCL MSc FinTech Dissertation Repo

Topic: cross-market probability divergence and price discovery between Polymarket BTC/ETH terminal price events and Deribit crypto options.

## Folder Map

```text
scripts/
  P0_data_collection/   API collection, feasibility checks, initial inventories
  P1_pipeline/          main empirical pipeline and Track A/B result builders
  P2_diagnostics/       robustness, audit, provenance, and freeze checks

data/
  raw/                  raw API snapshots and downloaded market data
  processed/            cleaned panels, diagnostics, and metadata

result/
  P0_data_audit/        early inventory and data-quality outputs
  P1_main_results/      exploratory main-result tables and figures
  P2_robustness/        robustness and audit outputs

paper/
  figures/              final dissertation figures
  tables/               final dissertation tables

docs/
  roadmap/              project roadmap and topic outline
  specs/                pipeline and output specifications
  decision_logs/        empirical freeze notes and decision records
```

## Stage Definitions

- `P0`: get the basic data and prove the APIs/data coverage are usable.
- `P1`: build the main reproducible empirical panels and paper-facing results.
- `P2`: audit, robustness-check, and freeze the result set for dissertation writing.

Large data outputs are not tracked by git. Keep final paper artifacts in `paper/`; use `result/` for intermediate or exploratory outputs.
