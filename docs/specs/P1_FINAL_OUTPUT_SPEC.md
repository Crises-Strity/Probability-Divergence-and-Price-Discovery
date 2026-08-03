# P1 Final Table and Figure Specification

Purpose: freeze the paper-facing metric definitions, sample gates, and units before writing. If any item below changes, rerun the full affected script chain and regenerate `paper/tables/table_source_metadata.{json,md}`.

Historical artifact note: the original frozen outputs predated repository
initialisation. P2 regenerates them after Commit A so metadata records a real
code hash.

## 1. Global Rules

Number formatting:

```text
probabilities: decimals in [0, 1], usually 3 decimals in text and 4 decimals in tables
percentage-point interpretation: multiply probability differences by 100 only in prose when clarity helps
p-values: scientific notation if <0.001
sample size: always report event-days and events together for Track A; rows and events together for Track B
```

Do not mix:

```text
raw absolute probability divergence with relative/log-odds tail divergence
hourly feasibility diagnostics with 6h primary integration results
point-threshold extension with bucket-distribution primary Track B
```

## 2. Main Text Tables

### Table A1: Track A sample funnel

Use:

```text
paper/tables/tab_trackA_sample_funnel.tex
```

Purpose:

```text
Show how Track A reaches 294 event-days / 61 events / 3,114 cell-day rows.
```

Metric and gate:

```text
main comparison = trackA_comparison_main_candidate
unit = event-days, events, and cell-day rows
```

Source:

```text
script: scripts/P1_pipeline/build_trackA_diagnostics.py
metadata: data/processed/panels/trackA_diagnostics_summary.json
```

### Table A2: Track A distribution and moment diagnostics

Use:

```text
paper/tables/tab_trackA_divergence_overall.tex
paper/tables/tab_trackA_tail_relative_wedge.tex
```

Purpose:

```text
Report L1/L2 as secondary shape distance; report location and tail-relative metrics as the most robust Track A moments; report spread as smoothing-conditional.
```

Metric and gate:

```text
sample gate = trackA_comparison_main_candidate
L1/L2 = normalized distribution distance on event bucket grid
spread = moment-style terminal distribution width on the bucket grid
tail relative divergence = tail absolute divergence scaled by tail probability size
unit = probability mass / normalized probability distance
```

### Table A3: Track A spread controls

Use:

```text
paper/tables/tab_trackA_spread_regressions.tex
```

Purpose:

```text
Show spread wedge survives horizon-gap, TTE, and asset controls.
```

Metric and gate:

```text
LHS = spread_diff_pm_minus_deribit
sample gate = trackA_comparison_main_candidate
formula = spread_diff_pm_minus_deribit ~ C(horizon_gap_bin, Treatment(reference='-8h')) + time_to_expiry_days + C(asset)
inference = event-clustered standard errors
unit = probability distribution width difference
```

Interpretation lock:

```text
Gap terms are composition controls, not causal maturity effects.
```

### Table A4: Track A robustness and smoothness sensitivity

Use:

```text
paper/tables/tab_trackA_tail_midpoint_robustness.tex
paper/tables/tab_trackA_state_grid_truncation.tex
paper/tables/tab_trackA_smoothness_regression_robustness.tex
paper/tables/tab_trackA_smoothness_fit_quality.tex
paper/tables/tab_trackA_smoothness_moment_grid.tex
```

Purpose:

```text
Show which Track A moments survive open-tail choice, state-grid truncation, and RND smoothness. In the current freeze, the spread sign is not hard under heavy smoothing.
```

Metric and gate:

```text
tail multiplier = open-tail midpoint extension in bucket widths
edge probability = Deribit probability mass in the two outermost state-grid cells
smooth_weight = RND smoothness penalty parameter
smoothness fit quality = option_reprice_rmse_coin on common event-days
smoothness moment grid = location / spread / tail metrics on common event-days
sample gate = Track A main comparison sample inside each spec
```

Placement:

```text
Main text: include the smoothness fit-quality and moment-grid takeaway because it qualifies the spread headline.
Appendix: full smoothness-regression table if space is tight.
```

### Table B1: Track B PM-side quality and saturation

Use:

```text
paper/tables/tab_trackB_pm_survival_summary.tex
paper/tables/tab_trackB_pm_informative_event_summary.tex
```

Purpose:

```text
Justify bucket-distribution primary sample and point-threshold exclusion.
```

Metric and gate:

```text
PM informative candidate = pass quality AND real update AND survival in (0.05, 0.95)
event_type_for_trackB = bucket_distribution vs point_threshold
unit = hours and events
```

Interpretation lock:

```text
point_threshold is extension only, not robustness and not primary.
```

### Table B2: Track B Deribit and joined coverage

Use:

```text
paper/tables/tab_trackB_deribit_survival_summary_6h.tex
paper/tables/tab_trackB_joint_survival_coverage_6h.tex
paper/tables/tab_trackB_frequency_diagnostics_6h.tex
```

Purpose:

```text
Show 6h feasibility and measurable co-movement.
```

Metric and gate:

```text
Deribit survival = local call-spread digital around K*
Track B primary sample = bucket_distribution events only
joint informative = PM informative AND Deribit informative after event-time join
frequency = 6h
unit = event-6h rows, events, correlations, standard-deviation ratio, autocorrelation
```

### Table B3: Track B direction diagnostics

Use:

```text
paper/tables/tab_trackB_cross_correlation_6h.tex
paper/tables/tab_trackB_pooled_lead_lag_6h.tex
```

Purpose:

```text
Report why direction is unidentified.
```

Metric and gate:

```text
cross-correlation = symmetric lag correlation of PM and Deribit survival changes
pooled regression = change_t on lagged changes plus event fixed effects
sample = both_sides_informative_candidate with consecutive non-missing changes
frequency = 6h
```

Interpretation lock:

```text
The pooled PM_lag -> Deribit coefficient is not a PM-lead finding because Deribit RHS measurement error attenuates the opposite equation.
```

## 3. Figures

### Figure A1: Example distribution comparison

Use:

```text
paper/figures/fig_trackA_distribution_comparison_example.pdf
```

Purpose:

```text
Show one representative event-day closest to median L1.
```

Final caption facts:

```text
event_id = 86290
date = 2025-11-24
asset = ETH
selection rule = closest event-day to median Track A L1 among main comparison days
```

### Figure A2: L1 distribution

Use:

```text
paper/figures/fig_trackA_l1_distribution.pdf
```

Purpose:

```text
Visualize shape-distance distribution.
```

Interpretation lock:

```text
Diagnostic / secondary, not headline magnitude.
```

### Figure A3: Spread wedge by signed gap

Use:

```text
paper/figures/fig_trackA_spread_diff_by_gap.pdf
```

Purpose:

```text
Show spread wedge varies with calendar/expiry-alignment bins.
```

Interpretation lock:

```text
Composition gradient, not causal maturity effect.
```

### Figure A4: Spread wedge vs TTE

Use:

```text
paper/figures/fig_trackA_spread_diff_vs_tte.pdf
```

Purpose:

```text
Show spread wedge across time-to-expiry, supporting control choice.
```

### Figure A5: Curve quality diagnostics

Use:

```text
paper/figures/fig_trackA_curve_fit_quality.pdf
```

Purpose:

```text
Appendix or data-quality section only.
```

### Figure A6: Cell divergence by type

Use:

```text
paper/figures/fig_trackA_cell_divergence_by_type.pdf
```

Purpose:

```text
Appendix figure for tail/body divergence; main text should use tail relative/log-odds table language.
```

## 4. Not Final Main-Text Figures Yet

Track B currently has no generated final PDF figures. If a Track B figure is needed, create exactly one:

```text
fig_trackB_survival_integration_6h.pdf
```

Required content:

```text
left panel: PM vs Deribit 6h survival levels, both_sides_informative_candidate rows
right panel: cross-correlation by lag from tab_trackB_cross_correlation_6h
caption must state: direction unidentified; contemporaneous correlation dominates lead/lag correlations
```

Do not create:

```text
a figure implying PM leads Deribit
a figure pooling point-threshold with bucket-distribution primary events
a figure based on relaxed hourly Deribit estimator
```

## 5. Rebuild Rule

If any table or figure is regenerated:

```text
1. rerun the producing script
2. rerun scripts/P2_diagnostics/build_p1_table_provenance.py
3. update docs/decision_logs/P1_PAPER_CONCLUSIONS.md only if the numeric output changed
4. record the reason in docs/decision_logs/P1_DECISION_LOG.md
```
