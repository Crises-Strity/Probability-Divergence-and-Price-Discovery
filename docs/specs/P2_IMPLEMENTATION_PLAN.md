# P2 Code Completion Plan

Basis: `docs/specs/P2_NEXT_STEPS.md`, P1 frozen scripts, local processed panels, and `paper/tables/table_source_metadata.{json,md}`.

This file is code/repo focused. Dissertation chapter writing is out of scope for this P2 pass.

## 1. Current Code Status

Completed before this pass:

```text
Track A smoothness / tail-midpoint / state-grid robustness:
  scripts/P1_pipeline/build_trackA_regression_diagnostics.py
  paper/tables/tab_trackA_smoothness_regression_robustness.{csv,tex}
  paper/tables/tab_trackA_smoothness_fit_quality.{csv,tex}
  paper/tables/tab_trackA_smoothness_moment_grid.{csv,tex}
  paper/tables/tab_trackA_tail_midpoint_robustness.{csv,tex}
  paper/tables/tab_trackA_state_grid_truncation.{csv,tex}

Track B 6h diagnostics:
  scripts/P1_pipeline/build_trackB_deribit_survival_panel.py --bar-hours 6
  scripts/P1_pipeline/build_trackB_lead_lag_panel.py --bar-hours 6
  scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py
  paper/tables/tab_trackB_*_6h.{csv,tex}
```

Completed in this pass:

```text
Reference-basis audit:
  scripts/P2_diagnostics/build_reference_basis_audit.py
  data/processed/panels/reference_basis_audit.{csv,parquet}
  data/processed/panels/reference_basis_audit_metadata.json
  paper/tables/tab_reference_basis_audit_summary.{csv,tex}

Freeze runner:
  scripts/P2_diagnostics/run_p1_freeze.py

Tests:
  tests/test_p2_reference_basis_audit.py
  tests/test_p2_freeze_runner.py

Provenance mapping:
  scripts/P2_diagnostics/build_p1_table_provenance.py maps tab_reference_basis_audit_summary
  paper/tables/table_source_metadata.{json,md} regenerated
```

Remaining repository gate:

```text
The repository exists. Create Commit A before the final replay so regenerated
metadata records the exact frozen code hash; Commit B then contains outputs.
```

## 2. Verified Reference-Basis Audit Result

Local event metadata is fully populated:

```text
audit rows: 124
reference_basis_status:
  proxy_assumed: 124

BTC:
  events: 60
  Track A eligible: 39
  Track B eligible: 60

ETH:
  events: 64
  Track A eligible: 40
  Track B eligible: 64

resolution_text_available_share: 1.0
reference_basis_mismatch_share: 1.0
```

Interpretation:

```text
This is not a missing-data issue. It is a documented reference-basis mismatch:
Polymarket settlement text points to Binance BTCUSDT/ETHUSDT 1m close at 12:00 ET,
while Deribit uses btc_usd / eth_usd indexes.
```

## 3. Verified Reproducibility Commands

Default P1 freeze runner:

```bash
uv run python scripts/P2_diagnostics/run_p1_freeze.py
```

Runs:

```text
scripts/P1_pipeline/build_trackA_diagnostics.py
scripts/P1_pipeline/build_trackA_regression_diagnostics.py
scripts/P2_diagnostics/build_reference_basis_audit.py
scripts/P2_diagnostics/build_p1_table_provenance.py
```

Full local replay including Track B:

```bash
uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b
```

Runs the default sequence plus:

```text
scripts/P1_pipeline/build_trackB_kstar_panel.py
scripts/P1_pipeline/build_trackB_pm_survival_panel.py
scripts/P1_pipeline/build_trackB_deribit_survival_panel.py
scripts/P1_pipeline/build_trackB_lead_lag_panel.py
scripts/P1_pipeline/build_trackB_deribit_survival_panel.py --bar-hours 6
scripts/P1_pipeline/build_trackB_lead_lag_panel.py --bar-hours 6
scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py
```

Verified outputs from full replay:

```text
Track A main comparison: 294 event-days, 61 events, 3,114 cell-day rows
Track A smoothness fit-quality rows: 4
Track A smoothness moment-grid rows: 4
Reference audit: 124 rows, 124 proxy_assumed
Track B 6h Deribit survival: 2,226 rows, 1,569 informative rows
Track B 6h joined panel: 1,121 joint-informative rows
Track B 6h diagnostics: 703 regression rows, 77 regression events
Provenance: 30 paper tables documented
```

## 4. Verification Commands

Unit tests:

```bash
uv run pytest -q
```

Required P2 file check:

```bash
uv run python -c "from pathlib import Path; required=['scripts/P2_diagnostics/build_reference_basis_audit.py','scripts/P2_diagnostics/run_p1_freeze.py','scripts/P2_diagnostics/verify_p2_freeze.py','data/processed/frozen_input_manifest.json','paper/tables/table_source_metadata.json']; print([p for p in required if not Path(p).exists()])"
```

Expected:

```text
[]
```

## 5. Remaining Code-Side Items

Required after Commit A:

```text
1. rerun uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b twice
2. compare table CSV manifests with scripts/P2_diagnostics/verify_p2_freeze.py
3. confirm paper/tables/table_source_metadata.json records Commit A
4. create Commit B containing only frozen outputs and required metadata
```

Optional, not required for P2 code completion:

```text
paper/figures/fig_trackB_survival_integration_6h.pdf
lognormal-mixture RND robustness
```

Do not reopen unless explicitly requested:

```text
Track A -8h headline sample
Track B point-threshold primary pooling
relaxed hourly Deribit estimator
Hasbrouck / per-event VECM on current 6h panel
PM-leads-Deribit interpretation
cell-level L1 as primary headline
```
