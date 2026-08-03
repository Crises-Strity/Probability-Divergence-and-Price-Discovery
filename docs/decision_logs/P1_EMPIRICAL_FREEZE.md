# P1 Empirical Freeze

Date: 2026-07-06

This document freezes the P1 empirical interpretation. Later writing should use
these results as the source of truth unless a new script explicitly supersedes
one of the outputs below.

## Scope

P1 is complete as a measurement and feasibility stage.

```text
Track A = daily full-distribution probability divergence / P-vs-Q wedge
Track B = hourly-to-6h local survival convergence and lead-lag feasibility
```

Do not promote P1 results into trading claims. P1 supports dissertation results
and limitations, not an executable strategy.

## Track A Freeze

Primary sample:

```text
event-days = 294
events = 61
sample = Track A passing comparison event-days after stale/fresh and RND sanity gates
```

Main findings:

```text
1. Location / center:
   PM and Deribit distributions agree near the center.
   Location intercept ~= 0.000572 with p ~= 0.8015; gap/asset/TTE terms are not significant.

2. Spread / width:
   PM is wider than Deribit in the baseline and low-to-moderate smoothing moment layer,
   but the sign attenuates under heavy smoothing.
   Baseline PM wider share = 0.707483.
   Baseline median PM - Deribit spread = 0.004022.
   Common-sample smooth_weight 0.20 PM wider share = 0.525597.
   Common-sample smooth_weight 0.20 median PM - Deribit spread = 0.000843.

3. Tail:
   Tail divergence is much clearer in relative / log-odds metrics than in raw absolute cell differences.

4. Composition:
   Horizon-gap, asset, and TTE controls explain a large share of spread variation.
   Gap coefficients are not causal maturity effects.
```

Robustness status:

```text
state-grid truncation:
    edge probability mean = 0.004393
    median = 0.001388
    p95 = 0.023281
    max = 0.058489
    days > 5% edge mass = 1 / 294

tail midpoint:
    ±0.5w median spread diff = 0.004022, PM wider share = 0.707483
    ±1.0w median spread diff = 0.004735, PM wider share = 0.717687

smoothness:
    smooth_weight in {0.05, 0.10, 0.20} keeps controlled gap-gradient signs.
    Spread magnitude and PM-wider share move strongly with smooth_weight.
    Heavy smoothing (0.20) nearly eliminates the unconditional PM-wider share,
    and option repricing RMSE does not worsen enough to reject 0.20 outright.
```

Interpretation discipline:

```text
Headline Track A on center alignment and tail-relative divergence.
Write spread as smoothing-conditional, not hard sign-invariant.
Do not headline L1/L2 magnitude; cell-level distances are smoothing-sensitive.
Do not call spread-gap coefficients causal maturity effects.
Do not call the wedge arbitrage.
```

Core outputs:

```text
paper/tables/tab_trackA_spread_regressions.csv
paper/tables/tab_trackA_tail_relative_wedge.csv
paper/tables/tab_trackA_state_grid_truncation.csv
paper/tables/tab_trackA_smoothness_regression_robustness.csv
paper/tables/tab_trackA_smoothness_fit_quality.csv
paper/tables/tab_trackA_smoothness_moment_grid.csv
data/processed/panels/trackA_regression_diagnostics_summary.json
```

## Track B Freeze

Primary sample:

```text
sample = bucket_distribution events only
events = 79
point_threshold events = extension only, excluded from primary
```

Reason point-threshold events are excluded from primary:

```text
point_threshold pass-quality saturated share = 0.421044
point_threshold informative hours = 3,129
point_threshold events with >=72 informative hours = 25 / 45
point_threshold events with 0 informative hours = 4 / 45
```

PM-side primary feasibility:

```text
bucket events = 79
PM informative hours = 9,280
median informative hours per event = 125
events with >=72 informative hours = 73
events with >=48 informative hours = 77
events with 0 informative hours = 0
```

Hourly Deribit bottleneck:

```text
1h joint informative rows = 2,973
1h level corr(PM, Deribit survival) = 0.900819
1h median absolute survival wedge = 0.057376
1h corr(Delta PM, Delta Deribit) = 0.040374
1h Deribit / PM change std ratio = 2.728357
1h Deribit lag-1 autocorr = -0.449059
```

Interpretation:

```text
Hourly levels agree, but hourly changes are dominated by Deribit microstructure noise.
Hourly lead-lag / information share is not feasible.
```

6h feasibility:

```text
6h joint informative rows = 1,121
6h change-pair rows = 889
6h corr(Delta PM, Delta Deribit) = 0.534829
6h Deribit / PM change std ratio = 1.592076
6h Deribit lag-1 autocorr = -0.248387
median max consecutive joint-informative run = 48h
events with >=24h consecutive joint-informative run = 72
events with >=48h consecutive joint-informative run = 43
```

6h level convergence:

```text
6h level corr(PM survival, Deribit survival) = 0.911992
6h median absolute survival wedge = 0.049052
6h median signed PM - Deribit survival wedge = -0.010667
```

6h lead-lag diagnostics:

```text
cross-correlation:
    Deribit leads PM by 12h = -0.023301
    Deribit leads PM by 6h  =  0.073590
    contemporaneous         =  0.534829
    PM leads Deribit by 6h  =  0.025272
    PM leads Deribit by 12h =  0.057311

pooled event-FE regression:
    Deribit lag -> PM change:
        coef = 0.057729, p = 0.061500
    PM lag -> Deribit change:
        coef = 0.329746, p = 0.000053
    Deribit own lag:
        coef = -0.400558, p ~= 0
```

Interpretation discipline:

```text
The asymmetric pooled regression coefficients do not identify PM leadership.
They are consistent with an errors-in-variables asymmetry because Deribit changes
remain noisier and negatively autocorrelated. The symmetric cross-correlation
diagnostics show no robust directional lead; both lead correlations are below
0.08 and are dominated by contemporaneous co-movement.

Final Track B finding:
    cross-market integration / level convergence: supported
    6h contemporaneous co-movement: supported
    directional price-discovery ranking: unidentified
    sub-6h lead-lag: not measurable with current Deribit OHLC liquidity
```

Core outputs:

```text
paper/tables/tab_trackB_pm_informative_event_summary.csv
paper/tables/tab_trackB_deribit_survival_summary_6h.csv
paper/tables/tab_trackB_joint_survival_coverage_6h.csv
paper/tables/tab_trackB_frequency_diagnostics_6h.csv
paper/tables/tab_trackB_cross_correlation_6h.csv
paper/tables/tab_trackB_pooled_lead_lag_6h.csv
data/processed/panels/trackB_lead_lag_diagnostics_summary.json
```

## P1 Status

P1 Track A and Track B are complete.

Do next:

```text
1. Write Ch5 empirical results using this freeze document.
2. Write Ch7 limitations around reference mismatch, Deribit microstructure noise,
   smoothing sensitivity, and sub-6h unidentified price discovery.
3. Only after Ch5/Ch7 drafts are stable, decide whether P2 is needed.
```

Do not do next:

```text
Do not add relaxed hourly Deribit estimators to rescue lead-lag direction.
Do not claim PM leads Deribit from the pooled 6h regression.
Do not run Hasbrouck information share on these panels.
```
