# P1 Decision Log

Purpose: record why core empirical decisions were made now, while the diagnostics are fresh. These notes should feed Chapter 3 methodology and Chapter 7 limitations.

Historical artifact note: the original P1 outputs predated repository
initialisation. P2 regenerates them after Commit A with real Git provenance.

## D1. Track A does not use raw discrete Breeden-Litzenberger as the main estimator

Decision:

```text
Do not take second differences directly on raw discrete option prices. Use a smoothed / shape-constrained option curve and then derive state probabilities on the event bucket grid.
```

Reason:

```text
Deribit option OHLC is sparse and stale at the strike level. Raw finite differences of call prices would turn bid-ask bounce, stale last trades, and non-convex raw prices into negative or spiky densities. The inverse problem is close to underdetermined: roughly 19 state buckets are inferred from around 17 usable strikes. Smoothness is therefore load-bearing, not cosmetic.
```

Paper wording:

```text
The estimator follows the Breeden-Litzenberger logic only after curve smoothing and no-arbitrage discipline; raw discrete BL is rejected as a primary estimator.
```

Provenance:

```text
scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py
scripts/P1_pipeline/build_trackA_diagnostics.py
scripts/P1_pipeline/build_trackA_regression_diagnostics.py
data/processed/panels/trackA_diagnostics_summary.json
paper/tables/tab_trackA_smoothness_regression_robustness.{csv,tex}
```

## D2. Track A headline is moment-level, but spread is smoothing-conditional

Decision:

```text
Headline Track A around location and tail-relative moments. Report spread as a smoothing-conditional moment result. Report L1/L2 as secondary shape-distance diagnostics.
```

Reason:

```text
Location alignment is stable and the tail-relative wedge remains material under smoothed specifications. The PM-wider spread sign is present under low-to-moderate smoothing but attenuates under heavy smoothing. Cell-level L1/L2 magnitudes are also sensitive to smoothness. Therefore the spread result should not be written as a hard sign-invariant headline.
```

Current support:

```text
common-sample smooth_weight 0.00: option RMSE mean 0.005925, PM wider share 0.907850, median spread diff 0.009556
common-sample smooth_weight 0.05: option RMSE mean 0.006166, PM wider share 0.812287, median spread diff 0.006791
common-sample smooth_weight 0.10: option RMSE mean 0.006351, PM wider share 0.706485, median spread diff 0.003968
common-sample smooth_weight 0.20: option RMSE mean 0.006669, PM wider share 0.525597, median spread diff 0.000843
location_diff_median stays near zero across the same grid.
tail_relative_abs_divergence_mean remains above body_relative_abs_divergence_mean for smoothed specs.
```

Implication:

```text
No lognormal-mixture RND upgrade is required for P1 if spread is written as conditional and cell-level L1 remains secondary. A parametric RND becomes more useful only if the dissertation needs a hard spread magnitude or cell-level shape-distance headline.
```

## D3. `-8h` is not a clean headline subsample

Decision:

```text
Do not make `signed_gap_hours == -8` the Track A headline sample.
```

Reason:

```text
The signed horizon gap is not a clean maturity shock. Gap bins are tied to calendar/expiry matching structure, and the observed spread-gradient sign is inconsistent with a simple diffusion horizon story. Restricting to -8h would also reduce event clusters and lower inference quality.
```

Final use:

```text
Use full Track A comparison sample with signed horizon-gap categories, time-to-expiry, and asset controls. Treat gap coefficients as observed composition controls, not causal maturity effects.
```

Provenance:

```text
paper/tables/tab_trackA_spread_regressions.{csv,tex}
paper/tables/tab_trackA_gap_confound_diagnostics.{csv,tex}
data/processed/panels/trackA_regression_diagnostics_summary.json
```

## D4. Track A settlement/reference basis remains a limitation unless filled from rules

Decision:

```text
Do not claim reference-basis cleanliness. Current P1 can proceed with a limitation, but Chapter 4 should either fill textual settlement_reference / deribit_index_reference fields or explicitly state that the empirical proxy assumes comparable BTC/ETH reference baskets.
```

Reason:

```text
Time-gap cleanliness does not solve reference-basis mismatch. Polymarket resolution rules and Deribit index construction may differ even when timestamps align.
```

Recommended next action:

```text
Low-cost writing cleanup: fill event-level textual reference fields where the Polymarket rule text is available. Do not rerun the full empirical pipeline unless this changes the numerical price/index mapping.
```

## D5. Point-threshold markets are excluded from primary Track B

Decision:

```text
Track B primary sample = bucket-distribution events only.
```

Reason:

```text
Point-threshold markets pass superficial quality filters but are frequently saturated near 0/1. A lead-lag test needs time-series variation in both markets. High saturation creates weak identification even if event-level coverage looks good.
```

Paper wording:

```text
Point-threshold markets are treated as an extension / external-validity slice, not pooled into the primary Track B lead-lag sample.
```

Provenance:

```text
scripts/P1_pipeline/build_trackB_pm_survival_panel.py
data/processed/panels/trackB_pm_survival_metadata.json
paper/tables/tab_trackB_pm_survival_summary.{csv,tex}
paper/tables/tab_trackB_pm_informative_event_summary.{csv,tex}
```

## D6. Track B is downgraded from Hasbrouck/VECM to pooled 6h diagnostics

Decision:

```text
Do not run per-event VECM / Hasbrouck information share in P1. Use 6h local-survival convergence, symmetric cross-correlation, and pooled lead-lag regressions with event fixed effects.
```

Reason:

```text
At hourly frequency, Deribit local-survival changes are noisy and negatively autocorrelated. At 6h frequency, co-movement becomes measurable, but the effective frequency is too coarse to identify sub-6h leadership. Per-event continuous runs and measurement quality do not support Hasbrouck-style decomposition.
```

Current support:

```text
6h contemporaneous change correlation: 0.534829
6h level correlation: 0.911992
6h Deribit/PM change std ratio: 1.592076
6h Deribit lag-1 autocorrelation: -0.248387
```

Provenance:

```text
scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py
data/processed/panels/trackB_lead_lag_diagnostics_summary.json
data/processed/panels/lead_lag_survival_panel_6h.parquet
paper/tables/tab_trackB_frequency_diagnostics_6h.{csv,tex}
```

## D7. Do not interpret `PM_lag -> Deribit` as PM leadership

Decision:

```text
The pooled regression asymmetry is not a directional price-discovery result.
```

Reason:

```text
Deribit changes are noisier. When noisy Deribit changes are the RHS regressor, errors-in-variables attenuation can mechanically shrink the Deribit_lag -> PM coefficient. When PM changes are the RHS regressor and noisy Deribit changes are the LHS, the coefficient is not attenuated in the same way. This produces an apparent PM_lag -> Deribit asymmetry even without true PM leadership.
```

Current support:

```text
Deribit_lag -> PM coefficient: 0.057729, p=0.061500
PM_lag -> Deribit coefficient: 0.329746, p=0.0000527
Deribit leads PM by 6h cross-corr: 0.073590
PM leads Deribit by 6h cross-corr: 0.025272
contemporaneous cross-corr: 0.534829
```

Final wording:

```text
Direction is unidentified; the robust result is contemporaneous integration at 6h frequency.
```

## D8. End-to-end reproducibility is not fully solved until the project is under git

Decision:

```text
The original table metadata recorded scripts and inputs but predated repository
initialisation. The P2 freeze replaces it after Commit A with current paths and
the real Commit A hash.
```

Reason:

```text
Metadata without a commit hash is still useful for provenance but not enough for final dissertation reproducibility.
```

Next action before final submission:

```text
Initialize or move into a git repo, rerun P1 freeze scripts, and regenerate paper/tables/table_source_metadata.json so each table has a real commit hash.
```
