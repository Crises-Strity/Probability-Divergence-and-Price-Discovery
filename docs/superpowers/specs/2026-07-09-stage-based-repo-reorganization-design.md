# Stage-Based Repo Reorganization Design

Date: 2026-07-09

## Goal

Make the dissertation folder readable by research stage. A reader should be able to open `scripts/`, `data/`, and `result/` and immediately understand which files belong to P0 data collection, P1 main empirical pipeline, and P2 diagnostics or robustness work.

## Scope

This pass reorganizes file placement and lightweight documentation only. It does not change empirical methods, rerun market-data downloads, refactor scripts into `src/`, or move large raw/processed datasets into new physical paths.

## Stage Definitions

- `P0`: data collection, API feasibility, initial inventories, and one-off market-history spikes.
- `P1`: main reproducible pipeline for canonical event cells, Polymarket/Deribit panels, Track A distribution divergence, Track B survival/lead-lag panels, and paper-facing outputs.
- `P2`: diagnostics, robustness, reference-basis audit, provenance, freeze runner, and tests around the frozen P1 result set.

## Target Structure

```text
scripts/
  P0_data_collection/
  P1_pipeline/
  P2_diagnostics/

data/
  README.md
  raw/
  processed/

result/
  README.md
  P0_data_audit/
  P1_main_results/
  P2_robustness/

docs/
  README.md
  roadmap/
  specs/
  decision_logs/
  superpowers/
```

`paper/figures` and `paper/tables` remain the final paper-facing artifact directories. `result/` remains the exploratory or intermediate result directory.

## Path Strategy

Scripts will move into stage subdirectories. Their root detection must change from `Path(__file__).resolve().parents[1]` to a helper that walks upward until it finds `AGENTS.md` and `.git`. This keeps old `data/raw`, `data/processed`, `paper/tables`, and `paper/figures` paths stable.

Existing datasets stay in place for this pass because many scripts and provenance files already reference `data/raw`, `data/processed`, and `paper/tables`. Moving them now would create unnecessary breakage.

## Documentation Strategy

Add README files that explain:

- what each stage means;
- where raw data, processed panels, paper-ready outputs, and exploratory results belong;
- why `paper/` and `result/` are separate;
- which scripts are entry points for P0, P1, and P2.

## Validation

Validation must include:

- existing pytest suite: `/Users/wanghaozhe/anaconda3/bin/python -m pytest tests -q`;
- freeze-runner dry run from its new path;
- import checks for tests that load moved scripts;
- `rg` checks for stale old script paths.
