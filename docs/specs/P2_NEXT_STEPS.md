# P2 Next Steps After P1 Freeze

Purpose: define what to do after the P1 empirical freeze without reopening settled P1 decisions.

Current status:

```text
P1 Track A empirical identification: frozen
P1 Track B empirical identification: frozen
P1 paper table provenance: generated in paper/tables/table_source_metadata.{json,md}
P2 reference-basis audit: generated in data/processed/panels/reference_basis_audit.{csv,parquet}
P2 freeze runner: scripts/P2_diagnostics/run_p1_freeze.py
P2 Python environment: Python 3.11 project environment declared in pyproject.toml and locked by uv.lock
P2 frozen inputs: 11 compact Parquet files documented in data/processed/frozen_input_manifest.json
P2 full runner: rebuilds Track A, reference audit, all Track B hourly/6h tables, and provenance
Git status: repository exists; Commit A is pending before the final freeze replay
```

## 1. Claude Decision Checklist

### 1. Track A smooth_weight grid regression robustness

Status:

```text
Done.
```

Evidence:

```text
script: scripts/P1_pipeline/build_trackA_regression_diagnostics.py
table: paper/tables/tab_trackA_smoothness_regression_robustness.{csv,tex}
table: paper/tables/tab_trackA_smoothness_fit_quality.{csv,tex}
table: paper/tables/tab_trackA_smoothness_moment_grid.{csv,tex}
metadata: data/processed/panels/trackA_regression_diagnostics_summary.json
```

Current result:

```text
common-sample smooth_weight 0.00: option RMSE mean 0.005925, PM wider share 0.907850, median spread diff 0.009556
common-sample smooth_weight 0.05: option RMSE mean 0.006166, PM wider share 0.812287, median spread diff 0.006791
common-sample smooth_weight 0.10: option RMSE mean 0.006351, PM wider share 0.706485, median spread diff 0.003968
common-sample smooth_weight 0.20: option RMSE mean 0.006669, PM wider share 0.525597, median spread diff 0.000843
```

Recommendation:

```text
Do not write the spread sign as hard. The fit-quality table does not justify excluding smooth_weight 0.20, so the defensible Ch5 wording is: PM is wider under low-to-moderate smoothing, but the spread wedge attenuates under heavy smoothing.
```

### 2. Decide whether to upgrade RND to lognormal mixture

Recommendation:

```text
Do not upgrade for the P1 primary result.
```

Reason:

```text
The dissertation's defensible Track A headline is moment-level but layered: center alignment is robust, tail-relative divergence remains material, and the spread wedge is smoothing-conditional. Cell-level L1/L2 magnitude is secondary and explicitly smoothness-sensitive. A lognormal-mixture RND would mainly defend hard spread/cell-level shape claims, not the current conservative finding.
```

When to reconsider:

```text
Only upgrade if the paper later makes cell-level L1/L2 or hard spread magnitude a headline quantitative result, or if a supervisor specifically asks for a parametric RND robustness check.
```

Cost/risk:

```text
Cost: estimator implementation, convergence diagnostics, new model-risk section.
Risk: shifts the dissertation from a transparent empirical design to a model-comparison exercise.
```

Decision for now:

```text
Freeze current smoothed / shape-constrained RND. Mention lognormal mixture as optional robustness or future work, not a blocker.
```

### 3. Fill `deribit_index_reference` / `settlement_reference`

Status:

```text
Done at audit-table level.
```

Evidence:

```text
script: scripts/P2_diagnostics/build_reference_basis_audit.py
panel: data/processed/panels/reference_basis_audit.{csv,parquet}
metadata: data/processed/panels/reference_basis_audit_metadata.json
table: paper/tables/tab_reference_basis_audit_summary.{csv,tex}
provenance: paper/tables/table_source_metadata.{json,md}
```

Current result:

```text
audit rows: 124
reference_basis_status: proxy_assumed for 124 / 124 events
BTC: 60 events, 39 Track A eligible, 60 Track B eligible
ETH: 64 events, 40 Track A eligible, 64 Track B eligible
resolution_text_available_share: 1.0
reference_basis_mismatch_share: 1.0
```

Interpretation:

```text
Local textual fields are populated, but they document a systematic reference-basis mismatch:
Polymarket settlement text points to Binance BTCUSDT/ETHUSDT 1m close at 12:00 ET,
while Deribit uses btc_usd / eth_usd indexes. This supports a proxy/limitation claim,
not an exact-reference claim.
```

Decision:

```text
Do not rerun Track A or Track B because this audit changes provenance/interpretation, not the numerical price/index mapping used in the frozen panels.
```

### 4. Track A x Track B integration narrative

Status:

```text
Done at memo level.
```

Primary location:

```text
docs/decision_logs/P1_PAPER_CONCLUSIONS.md
section: Unified Track A x Track B Narrative
```

Core narrative:

```text
Track A shows spread/tail divergence rather than center disagreement. Track B shows the markets are not disconnected: local survival levels align and 6h changes co-move. The project therefore studies a probability-measure / tail-risk / market-structure wedge under liquidity constraints, not a simple lead-lag arbitrage.
```

Next action:

```text
Turn this into the opening paragraph of Ch5 Results and the closing paragraph of Ch6 Discussion.
```

### 5. End-to-end reproducibility run, fixed seed, frozen parquet/table/figure outputs

Status:

```text
The runner and Python 3.11 environment are implemented. The final replay must
run after Commit A so generated metadata can record that exact code hash.
```

Evidence:

```text
script: scripts/P2_diagnostics/run_p1_freeze.py
environment: uv sync --python 3.11
tests: uv run pytest -q
full replay: uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b
strict verification: scripts/P2_diagnostics/verify_p2_freeze.py
```

Default runner sequence:

```text
scripts/P1_pipeline/build_trackA_diagnostics.py
scripts/P1_pipeline/build_trackA_regression_diagnostics.py
scripts/P2_diagnostics/build_reference_basis_audit.py
scripts/P2_diagnostics/build_p1_table_provenance.py
```

Optional full replay sequence with `--include-track-b`:

```text
scripts/P1_pipeline/build_trackB_kstar_panel.py
scripts/P1_pipeline/build_trackB_pm_survival_panel.py
scripts/P1_pipeline/build_trackB_deribit_survival_panel.py
scripts/P1_pipeline/build_trackB_lead_lag_panel.py
scripts/P1_pipeline/build_trackB_deribit_survival_panel.py --bar-hours 6
scripts/P1_pipeline/build_trackB_lead_lag_panel.py --bar-hours 6
scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py
scripts/P2_diagnostics/build_p1_table_provenance.py
```

Remaining action:

```text
Create and push Commit A, rerun the full freeze twice under uv, verify identical
table CSV hashes, then create Commit B for final tables, figures, provenance,
and required metadata. Commit B intentionally records Commit A in metadata.
```

Seed note:

```text
Most current P1 scripts are deterministic data transforms/regressions. If any bootstrap or randomized estimator is added later, set a fixed seed and record it in metadata.
```

## 2. P2 Work Plan

### P2.1 Writing package for P1 results

Deliverables:

```text
Ch4 Data subsection draft: sample construction and quality gates
Ch5 Results subsection draft: Track A and Track B results
Ch7 Limitations subsection draft: measurement caveats and unidentified direction
```

Inputs:

```text
docs/decision_logs/P1_PAPER_CONCLUSIONS.md
docs/decision_logs/P1_DECISION_LOG.md
docs/specs/P1_FINAL_OUTPUT_SPEC.md
paper/tables/table_source_metadata.md
```

### P2.2 Reference-basis audit

Status:

```text
Done.
```

Deliverable:

```text
data/processed/panels/reference_basis_audit.{csv,parquet}
data/processed/panels/reference_basis_audit_metadata.json
paper/tables/tab_reference_basis_audit_summary.{csv,tex}
```

Decision rule:

```text
Current local result is fully filled but systematically mismatched, so report proxy assumption and limitation.
```

### P2.3 Reproducibility hardening

Status:

```text
Implementation complete through the Commit A gate. Final replay and real hash
verification follow Commit A.
```

Deliverables:

```text
scripts/P2_diagnostics/run_p1_freeze.py
paper/tables/table_source_metadata.json regenerated after verified local replay
metadata with real git commit hash after project is under git
```

Do not do:

```text
Do not refactor the whole pipeline.
Do not add new dependencies unless required.
Do not redownload data unless a specific missing/provenance issue requires it.
```

### P2.4 Optional Track B figure

Deliverable if needed:

```text
paper/figures/fig_trackB_survival_integration_6h.pdf
```

Required interpretation:

```text
The figure must show integration, not leadership.
```

### P2.5 Optional parametric RND robustness

Default:

```text
Skip.
```

Trigger:

```text
Only do this if the dissertation needs a headline cell-level L1 result or supervisor explicitly requests parametric RND validation.
```

## 3. What Not To Reopen

Do not reopen these unless new data arrive:

```text
Track A -8h clean headline sample
Track B point-threshold pooled primary sample
Track B relaxed hourly Deribit estimator
Track B PM-leads-Deribit interpretation
Hasbrouck / per-event VECM on current 6h panel
cell-level L1 as the primary Track A claim
```

## 4. Immediate Next Command Sequence

Current local code-side finalization sequence is:

```text
uv run python scripts/P2_diagnostics/run_p1_freeze.py
```

For full Track B replay:

```text
uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b
```
