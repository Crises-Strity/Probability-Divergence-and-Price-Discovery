# P1 Paper-Ready Conclusions

Generated status: P1 empirical freeze.

Historical artifact note: the original P1 table metadata predated repository
initialisation and therefore had no Git hash. The P2 freeze regenerates the
metadata after Commit A rather than fabricating provenance.

Core source index:

```text
All paper table provenance: paper/tables/table_source_metadata.{json,md}
Track A headline diagnostics: data/processed/panels/trackA_diagnostics_summary.json
Track A regression robustness: data/processed/panels/trackA_regression_diagnostics_summary.json
Track B lead-lag diagnostics: data/processed/panels/trackB_lead_lag_diagnostics_summary.json
Track B 6h joined panel: data/processed/panels/lead_lag_survival_panel_6h.parquet
```

## 1. One-Sentence Thesis Claim

Polymarket and Deribit are strongly integrated around the same BTC/ETH terminal price events, but the integration is asymmetric across objects: distribution centers align, Polymarket shows wider terminal distributions under low-to-moderate RND smoothing, tail relative divergence remains material, and high-frequency directional price discovery is not identifiable with the current Deribit OHLC liquidity.

Write this as:

```text
The evidence supports cross-market probability divergence with frequency-bounded integration, not a mechanical arbitrage or one-sided leadership result.
```

## 2. Track A: Distribution Divergence

### Paper-ready finding A1: sample and comparison object

Track A's final comparison sample contains `294` event-days from `61` events and `3,114` cell-day rows.

Provenance:

```text
script: scripts/P1_pipeline/build_trackA_diagnostics.py
metadata: data/processed/panels/trackA_diagnostics_summary.json
fields: row_counts.main_comparison_event_days, row_counts.main_comparison_events, row_counts.main_comparison_cell_rows
tables: paper/tables/tab_trackA_sample_funnel.{csv,tex}
```

### Paper-ready finding A2: center agreement

The two markets do not show a robust disagreement in the center of the terminal distribution. The clean Track A narrative should not be "Polymarket is simply more bullish/bearish"; it should be "center aligned, width/tail disagreement."

Use with:

```text
location_diff intercept is close to zero and statistically insignificant; gap, asset, and time-to-expiry controls are also insignificant.
```

Provenance:

```text
script: scripts/P1_pipeline/build_trackA_diagnostics.py
tables: paper/tables/tab_trackA_gap_confound_diagnostics.{csv,tex}, paper/tables/tab_trackA_moments_by_gap.{csv,tex}
supporting script: scripts/P1_pipeline/build_trackA_regression_diagnostics.py
table: paper/tables/tab_trackA_spread_regressions.{csv,tex}
current location intercept: 0.000572, p=0.801546
```

### Paper-ready finding A3: PM spread wedge is smoothing-conditional

In the baseline Track A sample (`smooth_weight = 0.10`):

```text
Polymarket spread median: 0.051511
Deribit spread median: 0.045570
median(PM spread - Deribit spread): 0.004022
share(PM spread > Deribit spread): 0.707483
```

Interpretation:

```text
Polymarket terminal distributions are wider than Deribit-implied distributions under the baseline and low-to-moderate smoothness settings, but the spread wedge attenuates under heavy smoothing. This is a conditional result, not a hard sign-invariant headline.
```

Provenance:

```text
script: scripts/P1_pipeline/build_trackA_diagnostics.py
metadata: data/processed/panels/trackA_diagnostics_summary.json
fields: headline_diagnostics.pm_spread_median, headline_diagnostics.deribit_spread_median, headline_diagnostics.spread_diff_pm_minus_deribit_median, headline_diagnostics.pm_wider_than_deribit_share
table: paper/tables/tab_trackA_divergence_overall.{csv,tex}
robustness:
  paper/tables/tab_trackA_tail_midpoint_robustness.{csv,tex}
  paper/tables/tab_trackA_smoothness_fit_quality.{csv,tex}
  paper/tables/tab_trackA_smoothness_moment_grid.{csv,tex}
```

### Paper-ready finding A4: shape distance exists, but is secondary

The baseline normalized distribution distance is:

```text
L1 median: 0.235481
L1 mean: 0.288458
L2 median: 0.090428
```

Interpretation discipline:

```text
L1/L2 show non-trivial shape distance, but they should not be the headline magnitude because cell-level distances are sensitive to the RND smoothness penalty.
```

Provenance:

```text
script: scripts/P1_pipeline/build_trackA_diagnostics.py
metadata: data/processed/panels/trackA_diagnostics_summary.json
fields: headline_diagnostics.l1_median, l1_mean, l2_median
tables: paper/tables/tab_trackA_divergence_overall.{csv,tex}, paper/tables/tab_trackA_smoothness_moment_grid.{csv,tex}
```

### Paper-ready finding A5: tails are relatively more divergent

Tail relative absolute divergence exceeds body relative absolute divergence:

```text
tail relative abs divergence mean: 0.857979
body relative abs divergence mean: 0.570604
```

Interpretation:

```text
Tail wedge should be reported using relative or log-odds style metrics, not raw absolute probability only, because raw tail probabilities are mechanically small.
```

Provenance:

```text
script: scripts/P1_pipeline/build_trackA_diagnostics.py
metadata: data/processed/panels/trackA_diagnostics_summary.json
fields: headline_diagnostics.tail_relative_abs_divergence_mean, headline_diagnostics.body_relative_abs_divergence_mean
table: paper/tables/tab_trackA_tail_relative_wedge.{csv,tex}
```

### Paper-ready finding A6: gap gradient is a control, not a causal maturity effect

The spread wedge varies strongly with the signed horizon-gap bins. Baseline spread-regression terms relative to `-8h`:

```text
-32h coefficient: -0.004105, event-cluster SE 0.001107, p=0.000209
+16h coefficient:  0.006737, event-cluster SE 0.001496, p=0.00000671
+40h coefficient:  0.009367, event-cluster SE 0.001362, p=0.00000000000607
ETH coefficient:   0.005407, event-cluster SE 0.000987, p=0.0000000435
time-to-expiry coefficient: 0.001126, event-cluster SE 0.000298, p=0.000156
R-squared: 0.468298
```

Interpretation discipline:

```text
Do not call the gap coefficient a causal maturity effect. Its sign is inconsistent with a simple diffusion horizon story and likely captures calendar/expiry-alignment composition.
```

Provenance:

```text
script: scripts/P1_pipeline/build_trackA_regression_diagnostics.py
metadata: data/processed/panels/trackA_regression_diagnostics_summary.json
formula: spread_diff_pm_minus_deribit ~ C(horizon_gap_bin, Treatment(reference='-8h')) + time_to_expiry_days + C(asset)
table: paper/tables/tab_trackA_spread_regressions.{csv,tex}
```

### Paper-ready finding A7: robustness checks qualify the spread sign

Open-tail midpoint robustness:

```text
tail multiplier 0.5: median spread diff 0.004022, PM wider share 0.707483
tail multiplier 1.0: median spread diff 0.004735, PM wider share 0.717687
```

State-grid truncation:

```text
edge probability mean: 0.004393
edge probability median: 0.001388
edge probability p95: 0.023281
edge probability max: 0.058489
days above 5% edge probability: 1 / 294
```

Smoothness regression robustness:

```text
common event-days: 293
smooth_weight 0.00: option RMSE mean 0.005925, PM wider share 0.907850, median spread diff 0.009556
smooth_weight 0.05: PM wider share 0.810811, median spread diff 0.006794
smooth_weight 0.10: PM wider share 0.707483, median spread diff 0.004022
smooth_weight 0.20: PM wider share 0.525597, median spread diff 0.000843
smooth_weight 0.20 option RMSE mean: 0.006669
```

Interpretation:

```text
Open-tail and truncation checks do not overturn the baseline sign, but the smoothness grid does: heavy smoothing nearly eliminates the unconditional PM-wider share without producing a large repricing-RMSE penalty. Report the spread wedge as smoothing-conditional. Do not call the spread sign hard.
```

Location and tail across the smoothness grid:

```text
location_diff_median remains close to zero: 0.000941, 0.000949, 0.000986, 0.000827 for smooth_weight 0.00, 0.05, 0.10, 0.20.
tail relative abs divergence remains above body relative abs divergence in the smoothed specs: at 0.10, 0.857495 vs 0.570561; at 0.20, 0.944100 vs 0.754353.
```

Provenance:

```text
script: scripts/P1_pipeline/build_trackA_regression_diagnostics.py
metadata: data/processed/panels/trackA_regression_diagnostics_summary.json
tables:
  paper/tables/tab_trackA_tail_midpoint_robustness.{csv,tex}
  paper/tables/tab_trackA_state_grid_truncation.{csv,tex}
  paper/tables/tab_trackA_smoothness_regression_robustness.{csv,tex}
  paper/tables/tab_trackA_smoothness_fit_quality.{csv,tex}
  paper/tables/tab_trackA_smoothness_moment_grid.{csv,tex}
```

## 3. Track B: Local Survival Integration

### Paper-ready finding B1: point-threshold events are not primary

Track B primary uses bucket-distribution events only. Point-threshold events are excluded from the primary Track B sample because saturation removes useful time-series variation.

Write this as:

```text
The point-threshold markets pass superficial quality filters, but their survival series are frequently saturated. They are therefore unsuitable for primary lead-lag identification and are kept only as an extension / limitation.
```

Provenance:

```text
script: scripts/P1_pipeline/build_trackB_pm_survival_panel.py
metadata: data/processed/panels/trackB_pm_survival_metadata.json
tables: paper/tables/tab_trackB_pm_survival_summary.{csv,tex}, paper/tables/tab_trackB_pm_informative_event_summary.{csv,tex}
```

### Paper-ready finding B2: hourly is not measurable for lead-lag

Hourly local-survival levels agree, but hourly changes are dominated by Deribit measurement noise.

Use current frozen language:

```text
Hourly data are useful as a feasibility diagnostic, not as the primary directional price-discovery frequency.
```

Provenance:

```text
scripts:
  scripts/P1_pipeline/build_trackB_deribit_survival_panel.py
  scripts/P1_pipeline/build_trackB_lead_lag_panel.py
artifacts:
  data/processed/panels/deribit_survival_hourly.parquet
  data/processed/panels/lead_lag_survival_panel.parquet
  data/processed/panels/trackB_lead_lag_panel_metadata.json
tables:
  paper/tables/tab_trackB_deribit_survival_summary.{csv,tex}
  paper/tables/tab_trackB_joint_survival_coverage.{csv,tex}
```

### Paper-ready finding B3: 6h co-movement is strong

At the 6h frequency:

```text
joint informative rows: 1,121
informative events: 79
regression rows: 703
regression events: 77
change-pair contemporaneous correlation: 0.534829
level correlation: 0.911992
median absolute survival wedge: 0.049052
median signed PM-Deribit survival wedge: -0.010667
Deribit/PM change standard-deviation ratio: 1.592076
Deribit change lag-1 autocorrelation: -0.248387
median longest continuous joint run: 48h
```

Interpretation:

```text
The two markets are integrated at 6h frequency: levels are highly aligned and survival-probability changes have strong contemporaneous co-movement.
```

Provenance:

```text
scripts:
  scripts/P1_pipeline/build_trackB_deribit_survival_panel.py --bar-hours 6
  scripts/P1_pipeline/build_trackB_lead_lag_panel.py --bar-hours 6
  scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py
metadata:
  data/processed/panels/trackB_deribit_survival_metadata_6h.json
  data/processed/panels/trackB_lead_lag_panel_metadata_6h.json
  data/processed/panels/trackB_lead_lag_diagnostics_summary.json
panel for level correlation:
  data/processed/panels/lead_lag_survival_panel_6h.parquet
tables:
  paper/tables/tab_trackB_frequency_diagnostics_6h.{csv,tex}
  paper/tables/tab_trackB_joint_survival_coverage_6h.{csv,tex}
```

### Paper-ready finding B4: directional leadership is unidentified

Symmetric 6h cross-correlation:

```text
Deribit leads PM by 6h: 0.073590
contemporaneous: 0.534829
PM leads Deribit by 6h: 0.025272
```

Pooled lag regressions:

```text
Deribit_lag -> PM: coefficient 0.057729, event-cluster SE 0.030873, p=0.061500
PM_lag -> Deribit: coefficient 0.329746, event-cluster SE 0.081556, p=0.0000527
Deribit own lag: coefficient -0.400558, event-cluster SE 0.036351, p=3.09e-28
```

Interpretation discipline:

```text
Do not interpret the large PM_lag -> Deribit coefficient as PM leadership. Deribit changes are noisier and negatively autocorrelated; when noisy Deribit changes are on the right-hand side, errors-in-variables attenuation mechanically shrinks the Deribit_lag -> PM coefficient. The symmetric cross-correlation does not show a robust directional lead.
```

Final RQ3 conclusion:

```text
Track B supports cross-market integration and 6h contemporaneous co-movement. Directional price-discovery ranking is unidentified; sub-6h leadership is not measurable with current Deribit OHLC liquidity.
```

Provenance:

```text
script: scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py
metadata: data/processed/panels/trackB_lead_lag_diagnostics_summary.json
tables:
  paper/tables/tab_trackB_cross_correlation_6h.{csv,tex}
  paper/tables/tab_trackB_pooled_lead_lag_6h.{csv,tex}
```

## 4. Unified Track A x Track B Narrative

Use this project-level synthesis:

```text
Daily Track A shows that the two markets do not simply disagree about the center of the BTC/ETH terminal distribution. Instead, the robust evidence is a tail-relative divergence, while the spread wedge is present under low-to-moderate RND smoothing and attenuates under heavy smoothing. Track B then shows that this is not because the two markets are completely disconnected. Around a local ATM threshold, Polymarket and Deribit survival probabilities are highly aligned in levels and co-move strongly at 6h frequency. The remaining wedge is therefore best framed as a probability-measure / tail-risk / market-structure wedge under liquidity constraints, not as a clean lead-lag arbitrage.
```

Do not write:

```text
Polymarket leads Deribit.
Deribit leads Polymarket.
The spread wedge is a causal maturity-gap effect.
The divergence is an arbitrage.
```

## 5. Paper Section Placement

Chapter 4 Data:

```text
Use Track A sample funnel, Track B K* summary, PM saturation diagnostics, Deribit 1h/6h feasibility diagnostics.
```

Chapter 5 Results:

```text
Track A: center aligned, spread/tail wedge, robustness.
Track B: level convergence, 6h contemporaneous co-movement, no robust directional lead-lag.
```

Chapter 6 Discussion:

```text
Interpret tail-relative wedge and smoothing-conditional spread wedge as P-vs-Q plus market-structure wedge; discuss smoothness-sensitive magnitude.
```

Chapter 7 Limitations:

```text
No historical order book, daily OHLC non-synchronicity, reference-basis uncertainty, generated-regressor smoothness sensitivity, hourly Deribit measurement error, no sub-6h leadership identification.
```
