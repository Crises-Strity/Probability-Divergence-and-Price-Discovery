# P1 Pipeline Spec: Probability Divergence and Price Discovery

Date: 2026-06-30

> P2 freeze decision (2026-08-03): wild cluster bootstrap was not implemented.
> Event-clustered standard errors and p-values are retained as descriptive
> diagnostics and do not identify causal or directional price discovery. This
> decision supersedes the earlier primary-inference target below while
> preserving it as part of the design history.

## 1. Scope

P1 turns the P0 feasibility work into reproducible datasets and first-pass empirical diagnostics.

The pipeline has two tracks:

```text
Track A: daily full-distribution divergence / P-Q wedge measurement
Track B: hourly/local survival-probability lead-lag
```

The pipeline should not attempt historical order-book replay. Deribit historical order book and expired-option mark history are not available through the tested public endpoints.

Primary interpretation rule:

```text
Track A raw level differences are not pure mispricing. They include physical-vs-risk-neutral probability wedges, liquidity premia, tail premia, and market-specific biases.
Track B lead-lag tests are not valid until stale-price and non-synchronous trading diagnostics pass.
```

## 2. Primary Specification Freeze

P1 should produce enough diagnostics to freeze the primary specification before broad regressions. The default table is:

```text
Track A primary has two separate specifications:

Track A1: wedge explanation / RQ1
    sample = BTC+ETH pooled, clean bucket-distribution events, exact+close mapping
    frequency = daily
    Polymarket = complete partition probabilities after warm-up and sum filters
    Deribit = daily OHLC-implied bucket probabilities from smoothed / shape-constrained option curve
    LHS = event-day aggregate distribution distance, or cell-day raw divergence
    FE = asset FE; cell/moneyness FE if LHS is cell-day divergence; no event FE
    estimand = observable drivers of P-vs-Q wedge
    controls = time-to-expiry, horizon gap, settlement/reference mismatch, mapping quality,
               liquidity/staleness controls, tail-cell indicator, cross-strike trade-time spread

Track A2: within-event dynamics / RQ2
    sample = same clean bucket-distribution events
    frequency = daily
    LHS = change in unexplained wedge component / residual divergence proxy
    FE = event FE, with optional cell/moneyness FE
    estimand = residual dynamics / weak evidence of active adjustment
    controls = time-varying controls only, e.g. time-to-expiry, liquidity/staleness, curve quality
    omitted by design = horizon gap, settlement/reference mismatch, mapping quality, asset FE

Track B primary:
    sample = clean bucket-distribution events passing hourly local-survival coverage filters
    frequency = hourly
    K* = rule-selected boundary for bucket-distribution events
    Polymarket = P_PM(S_T > K*) from cell sums for bucket events
    Deribit = P_DER(S_T > K*) from local/ATM option information
    estimand = lead-lag in survival-probability changes
    mandatory checks = update/trade frequency, time since last update/trade,
                       both-sides-real-update bars, low-stale subsample, K* source and initial moneyness controls
    inference = event-level wild cluster bootstrap as primary; clustered SE as descriptive

Track B extension:
    point-threshold events may be analyzed only as an explicitly separated extension
    after saturation and informative-hour filters. They are not part of the primary
    lead-lag sample because many selected threshold series are saturated and provide
    weak time-series variation.
```

Everything else is robustness or exploratory until explicitly promoted:

```text
BTC-only / ETH-only
exact-only
4h / 6h / 12h aggregation
alternative K* rules
alternative Deribit smoothing methods
trading signal tests
```

## 3. Directory Targets

Raw data:

```text
data/raw/polymarket/
data/raw/deribit/
```

Processed data:

```text
data/processed/polymarket/
data/processed/deribit/
data/processed/panels/
```

Figures and tables:

```text
paper/figures/
paper/tables/
```

Metadata:

```text
data/processed/*/metadata.json
```

Every generated dataset should include:

```text
source endpoint
pull timestamp
script name
event universe version
filter rules
row counts
known caveats
```

## 4. Existing P0 Scripts

Current scripts:

```text
scripts/P0_data_collection/build_polymarket_inventory.py
scripts/P0_data_collection/check_deribit_availability.py
scripts/P0_data_collection/deribit_single_expiry_grid_spike.py
scripts/P0_data_collection/polymarket_event_history_spike.py
```

These are P0/probe scripts. P1 should either refactor them into reusable modules or create new production scripts with narrower responsibilities.

## 5. Canonical Event Universe

Input:

```text
data/processed/polymarket/event_distribution_quality.csv
data/processed/polymarket/market_pair_candidate_inventory.csv
data/raw/polymarket/polymarket_public_search_events.json
```

Main event sets:

```text
distribution_events:
    distribution_quality == clean_bucket_distribution
    mapping_quality in {exact, close}

point_threshold_events:
    distribution_quality == usable_point_thresholds
    mapping_quality in {exact, close}
```

Current expected counts:

```text
distribution_events: 79
point_threshold_events: 45
total target events: 124
```

Required event fields:

```text
event_id
event_title
asset
event_start_time
event_end_time
nearest_deribit_expiry
time_gap_hours
settlement_reference
deribit_index_reference
reference_basis_mismatch
mapping_quality
distribution_quality
min_strike
max_strike
cell definitions
trackA_eligible
trackB_eligible
event_type_for_trackB       # bucket_distribution or point_threshold
```

## 6. Polymarket P1 Data

### 6.1 Cell Definition Table

Create:

```text
data/processed/polymarket/event_cells.parquet
```

One row per event cell:

```text
event_id
market_id
condition_id
question
cell_type            # left_tail, bucket, right_tail, point_above, point_below
cell_low
cell_high
sort_key
yes_token_id
no_token_id
start_time
end_time
volume
```

For `clean_bucket_distribution` events, cells should form:

```text
left_tail + ordered middle buckets + right_tail
```

### 6.2 Prices-History Download

Endpoint:

```text
https://clob.polymarket.com/prices-history
```

Parameters:

```text
market=<YES token id>
startTs=<unix seconds>
endTs=<unix seconds>
fidelity=60
```

Important:

```text
The endpoint rejects overly long intervals. Pull per event or in short windows.
```

Output:

```text
data/raw/polymarket/prices_history_<event_id>.parquet
```

Fields:

```text
event_id
market_id
yes_token_id
timestamp
price
cell_type
cell_low
cell_high
```

### 6.3 Polymarket Distribution Panel

Create:

```text
data/processed/polymarket/polymarket_distribution_hourly.parquet
data/processed/polymarket/polymarket_distribution_daily.parquet
```

Hourly panel:

```text
event_id
timestamp
cell_id / market_id
cell_low
cell_high
probability_raw
event_probability_sum
probability_normalized
sum_error
is_complete_partition
is_warmup
passes_sum_filter
has_real_update
time_since_last_update_minutes
update_count_in_bar
```

Filters:

```text
drop first 1-3 hours after event start
require all cells present
record raw probability sum
main quality filter: event_probability_sum in [0.9, 1.1]
normalize only after storing raw sum error
```

Daily panel:

```text
use last available clean hourly observation per UTC day
or fixed time snapshot if coverage is sufficient
```

## 7. Deribit P1 Data

### 7.1 Instrument Grid Construction

Do not rely on:

```text
public/get_instruments(expired=true)
```

It does not enumerate the full historical universe.

Instead construct option names:

```text
BTC-28MAR25-84000-C
BTC-28MAR25-84000-P
ETH-25APR25-1600-C
```

For each event:

```text
currency = BTC or ETH
expiry = nearest_deribit_expiry
strike grid = Polymarket min/max plus extensions
option_type = C/P
```

Grid rule:

```text
BTC: use event bucket width or 2,000 as baseline
ETH: use event bucket width or 100 as baseline
extend beyond Polymarket range by several steps
```

P1 should record failed instruments explicitly.

### 7.2 Deribit OHLC Download

Endpoint:

```text
https://www.deribit.com/api/v2/public/get_tradingview_chart_data
```

Parameters:

```text
instrument_name
start_timestamp
end_timestamp
resolution
```

Required resolutions:

```text
1D for Track A
60 for Track B
120 or 240 optional robustness if supported / constructable
```

Output:

```text
data/raw/deribit/ohlc_<event_id>_<resolution>.parquet
```

Fields:

```text
event_id
currency
expiry
instrument_name
option_type
strike
timestamp
open
high
low
close
volume
cost
status
has_real_trade
target_snapshot_timestamp
trade_timestamp_used
minutes_from_target_snapshot
time_since_last_trade_minutes
bar_stale_flag
```

### 7.3 Deribit Quality Panel

Create:

```text
data/processed/deribit/deribit_bar_quality.parquet
```

Fields:

```text
event_id
timestamp
n_distinct_traded_strikes
n_call_traded_strikes
n_put_traded_strikes
min_traded_strike
max_traded_strike
total_volume
can_fit_full_curve_min6
can_fit_full_curve_min8
atm_local_coverage
curve_target_timestamp
intraday_trade_time_diagnostics_available
cross_strike_trade_time_min
cross_strike_trade_time_max
cross_strike_trade_time_spread_minutes
max_abs_minutes_from_target_snapshot
median_time_since_last_trade_minutes
stale_bar_share
both_sides_real_update_candidate
```

Important limitation for the current 1D OHLC pull:

```text
cross_strike_trade_time_* fields are not valid non-synchronicity diagnostics in 1D bars.
They must not be used as quality gates unless rebuilt from intraday/trades-level data.
Use stale_bar_share and traded-strike counts as the current daily freshness gates.
```

For Track A:

```text
daily full curve requires enough fresh traded strikes and stale_bar_share <= 0.30
```

For Track B:

```text
hourly lead-lag uses local ATM survival probability, not full curve
```

## 8. Track A: Daily Distribution Divergence / P-Q Wedge Measurement

Track A should be written as a measurement of cross-market probability-measure divergence. The raw difference between Polymarket and Deribit is not enough to identify mispricing.

### 8.1 Deribit Bucket Probabilities

For each event-day:

```text
1. choose valid option observations
2. choose a fixed target snapshot time, e.g. Deribit expiry-aligned 08:00 UTC
3. select trades within a pre-specified window around the target time, e.g. +/- 1 hour
4. record each strike's actual trade time and distance from target time
5. clean stale/zero-volume instruments
6. fit smooth call curve or implied-vol smile
7. enforce monotonicity/convexity where possible
8. integrate probability mass over Polymarket cells
```

Current implemented first-pass method:

```text
script: scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py

1. keep event-days with trackA_curve_input_candidate == True
2. infer same-day spot/forward from traded call-put pairs:
       spot ~= median K / (1 - (call_close - put_close))
3. fit non-negative state probabilities by constrained least squares to traded calls and puts
4. add soft constraints for probability sum, fitted forward, and second-difference smoothness
5. integrate fitted state probabilities over Polymarket cells
6. compute event-day location / spread / skew decomposition from matched PM and Deribit cell probabilities
7. mark main comparison rows only when deribit_curve_quality == pass
```

This is not yet an IV/SVI production model. It is a shape-constrained first pass
that prevents negative density and records repricing error explicitly.
No-smoothing runs are stress tests, not preferred estimates, because sparse
state-price fits become spiky even when repricing error is low.

Output:

```text
data/processed/panels/daily_distribution_comparison.parquet
data/processed/panels/trackA_event_day_divergence.parquet
data/processed/deribit/deribit_curve_fits.parquet
data/processed/deribit/deribit_state_price_grid.parquet
```

Fields:

```text
event_id
date
cell_low
cell_high
pm_probability
deribit_probability
raw_divergence
normalized_divergence
relative_abs_normalized_divergence
log_odds_divergence
pm_sum_error
deribit_sum_error
deribit_curve_quality
target_snapshot_timestamp
cross_strike_trade_time_spread_minutes      # only valid if rebuilt from intraday/trades-level data
max_abs_minutes_from_target_snapshot        # only valid if rebuilt from intraday/trades-level data
time_to_expiry_hours
horizon_gap_bin
signed_gap_hours
settlement_reference
deribit_index_reference
reference_basis_mismatch
tail_cell_flag
cell_mid
cell_moneyness
moneyness_bucket
pm_liquidity
deribit_liquidity
```

Diagnostics:

```text
probability mass non-negative
bucket probabilities sum near 1
negative density share
convexity violation count before smoothing
number of strikes used
last-trade staleness share
cross-strike trade-time spread if intraday/trades-level data is available
maximum distance from target snapshot time if intraday/trades-level data is available
settlement/reference mismatch flag
location / spread / skew differences
tail relative and log-odds divergence
time-to-expiry by horizon-gap composition
smooth_weight and mean_weight sensitivity
state-grid edge-mass truncation check
smooth_weight regression robustness
```

### 8.2 Divergence Metrics

Compute:

```text
L1 distance
L2 distance
largest cell divergence
tail divergence
mean / median bucket divergence
location proxy difference
```

Do not interpret raw difference as pure mispricing because:

```text
Polymarket ~= physical/event probability
Deribit = risk-neutral probability
```

Track A uses two different regressions because event fixed effects absorb event-invariant variables such as horizon gap, settlement/reference mismatch, mapping quality, and asset.

Spec A1: wedge explanation / RQ1:

```text
LHS:
    event-day aggregate distribution distance, e.g. L1/L2
    or cell-day raw divergence if cell-level structure is needed

Fixed effects:
    asset FE
    cell / moneyness FE only for cell-day LHS
    no event FE

Controls that can be estimated:
    time-to-expiry
    signed_gap_hours or horizon_gap_bin fixed effects
    settlement/reference mismatch indicator or distance proxy
    mapping quality
    Polymarket liquidity and spread proxies
    Deribit volume / strike coverage / staleness proxies
    cross-strike trade-time spread only if rebuilt from intraday/trades-level data
    tail-cell indicator for cell-day LHS
```

Do not use `abs_time_gap_hours` as a linear control. In the current event universe,
each absolute gap maps to one sign, and the mechanical maturity effect alternates
direction across `-32h`, `-8h`, `+16h`, and `+40h`. Use `signed_gap_hours` or
the four-level `horizon_gap_bin` fixed effect.

For component-level Track A results:

```text
location wedge:
    primary = full passing comparison sample with horizon-bin, asset, and time-to-expiry controls
    current diagnostic result = center/location differences are near zero and composition-invariant

spread wedge:
    primary = full passing comparison sample with horizon-bin, asset, and time-to-expiry controls
    signed_gap_hours == -8 is only a descriptive slice / robustness view, not a clean headline sample
    current diagnostic result = PM is wider than Deribit in the baseline moment layer, but magnitude is generated-regressor sensitive

skew wedge:
    full curve-input sample with signed-gap / horizon-bin controls plus robustness
    current diagnostic result = low-confidence; do not headline without stronger evidence
```

Current frozen Track A diagnostic results:

```text
baseline comparison sample:
    event-days = 294
    events = 61
    median L1 normalized divergence = 0.235481
    median PM spread = 0.051511
    median Deribit spread = 0.045570
    median PM - Deribit spread = 0.004022
    PM wider share = 0.707483

location regression:
    R^2 ~= 0.011
    horizon gap, asset, and time-to-expiry are not significant in the current diagnostic table

spread regression:
    primary formula = spread_diff_pm_minus_deribit ~ C(horizon_gap_bin, ref=-8h) + time_to_expiry_days + C(asset)
    event-clustered SE by event
    R^2 ~= 0.468
    -32h coefficient = -0.004105
    +16h coefficient = +0.006737
    +40h coefficient = +0.009367
    ETH coefficient = +0.005407

skew regression:
    R^2 ~= 0.022
    no current headline result

tail divergence:
    tail log-odds divergence is much larger than body log-odds divergence
    use relative / log-odds metrics for tail discussion, not only absolute cell differences

state-grid truncation:
    edge probability mean = 0.004393
    median = 0.001388
    p95 = 0.023281
    max = 0.058489
    days with edge probability > 5% = 1 / 294

smoothness regression robustness:
    smooth_weight in {0.05, 0.10, 0.20} keeps the controlled horizon-gap gradient signs:
        -32h negative
        +16h positive
        +40h positive
    global PM-wider share and spread magnitude still move with smooth_weight, so report sign more strongly than magnitude
```

Spec A2: within-event residual dynamics / RQ2:

```text
LHS:
    change in unexplained wedge component / residual divergence proxy

Fixed effects:
    event FE
    optional cell / moneyness FE

Controls:
    time-varying controls only, e.g. time-to-expiry, liquidity, staleness, curve quality

Not estimated in this spec:
    horizon gap
    settlement/reference mismatch
    mapping quality
    asset effect
```

Spec A2 does not identify the level residual as mispricing. It only tests whether the unexplained wedge component has within-event dynamics consistent with active adjustment after separating terminal mechanical convergence.

Recommended interpretation hierarchy:

```text
raw divergence = descriptive P-vs-Q / market wedge
controlled residual divergence = unexplained wedge component
unexplained wedge component = unmodeled premium variation + possible cross-market divergence
residual dynamics / mean reversion = only part that can weakly support active adjustment claims
```

## 9. Track B: Hourly Price Discovery

### 9.1 K* Selection

K* must be selected ex ante to avoid look-ahead.

For bucket-distribution events, recommended baseline:

```text
For each event, choose the Polymarket boundary strike closest to the reference underlying price near event start,
subject to minimum Polymarket and Deribit liquidity.
K_star_source = rule_selected
```

For point-threshold events:

```text
K* is the market-defined threshold.
K_star_source = market_defined
```

This is still ex ante in the sense that the threshold is known at event start, but it is not generated by the same rule as bucket-distribution events. Point-threshold markets may have systematically different initial moneyness, because issuers often choose salient or out-of-the-money thresholds. The lead-lag panel must therefore control for initial K* moneyness and report bucket-only robustness.

Bucket-event fallback:

```text
choose the middle event boundary / nearest ATM listed strike using only information available at event start
```

Record:

```text
event_id
K_star
K_star_source
selection_reason
underlying_reference_time
underlying_reference_price
initial_k_star_moneyness
```

Current implemented first-pass method:

```text
script: scripts/P1_pipeline/build_trackB_kstar_panel.py

1. bucket-distribution events:
       select the finite Polymarket boundary whose first clean post-warmup PM survival probability is closest to 0.5
       K_star_source = rule_selected
       selection_reason = pm_start_implied_median_boundary
2. point-threshold events:
       select the market-defined point_above threshold whose first post-warmup YES price is closest to 0.5
       K_star_source = market_defined
       selection_reason = market_defined_threshold_closest_to_start_yes_0p5
```

Current caveat:

```text
No external BTC/ETH event-start index panel is in the repository yet.
Therefore initial_k_star_moneyness is currently null, and bucket K* uses a
Polymarket-implied ex-ante fallback rather than a spot-index ATM rule.
```

### 9.2 Polymarket Survival Probability

For clean bucket-distribution events:

```text
P_PM(S_T > K*) = sum of all cells whose support is above K*
```

For usable point-threshold events:

```text
the YES market is already a threshold probability and can enter Track B if K* is liquid and Deribit-local survival can be estimated
```

Point-threshold events do not have a partition-sum quality check. They need a substitute quality gate:

```text
minimum Polymarket volume / liquidity
minimum real update frequency
maximum stale share
exclude or flag markets whose YES price is saturated outside [0.05, 0.95] for most of the event life
require Deribit local strike coverage around the market-defined threshold
```

For partial cells or boundary mismatch in bucket-distribution events, either:

```text
only choose K* on Polymarket cell boundaries
```

or do not use the event for Track B.

Output:

```text
data/processed/panels/pm_survival_hourly.parquet
```

Current implemented first-pass method:

```text
script: scripts/P1_pipeline/build_trackB_pm_survival_panel.py

bucket-distribution:
    pm_survival = sum normalized probabilities for cells with cell_low >= K_star
    quality gate inherits complete-partition + sum-filter + non-warmup checks

point-threshold:
    pm_survival = YES price for selected point_above K_star market
    no partition-sum gate is available; quality relies on warmup, update-frequency, and saturation diagnostics

low-power flag:
    pm_survival <= 0.05 or pm_survival >= 0.95
```

Current PM-side Track B diagnostics:

```text
K* selection:
    events = 124
    pass = 124
    bucket_distribution = 79
    point_threshold = 45

PM survival hourly panel:
    rows = 18,225
    events = 124
    pass-quality rows = 16,700

bucket_distribution:
    hourly bars = 11,756
    pass-quality share = 0.881337
    pass-quality real-update share = 0.976740
    pass-quality saturated share = 0.089856
    pass-quality median survival = 0.477407
    pass-quality median abs hourly change = 0.011371

point_threshold:
    hourly bars = 6,469
    pass-quality share = 0.979904
    pass-quality real-update share = 0.765105
    pass-quality saturated share = 0.421044
    pass-quality median survival = 0.510000
    pass-quality median abs hourly change = 0.005000
```

Interpretation:

```text
The PM side is usable for Track B. The primary lead-lag sample should be
bucket_distribution events only. Point-threshold events are much more
saturation-prone and should be treated as a separate extension, not as part of
the main pooled sample.
```

Informative-hour definition:

```text
informative hour = pm_survival_quality_status == pass
                   AND pm_has_real_update
                   AND pm_survival in (0.05, 0.95)
```

Current PM-side informative-hour funnel:

```text
bucket_distribution:
    events = 79
    total informative hours = 9,280
    median informative hours per event = 125
    events with >=72 informative hours = 73
    events with >=48 informative hours = 77
    events with 0 informative hours = 0

point_threshold:
    events = 45
    total informative hours = 3,129
    median informative hours per event = 78
    events with >=72 informative hours = 25
    events with >=48 informative hours = 28
    events with 0 informative hours = 4
```

### 9.3 Deribit Local Survival Probability

Deribit hourly full RND is not the main input.

Use local/ATM option information to estimate:

```text
P_DER(S_T > K*)
```

Candidate methods, from simplest to more rigorous:

```text
1. local digital approximation from call spread around K*
2. local smoothed call curve around K*
3. local IV interpolation near K*
```

Quality filters:

```text
require nearby strikes around K*
require nonzero volume or recent trade in the bar/window
record local strike count
record time since last trade if implemented
```

Output:

```text
data/processed/panels/deribit_survival_hourly.parquet
```

Current implemented first-pass method:

```text
script: scripts/P1_pipeline/build_trackB_deribit_survival_panel.py

1. use 60-minute Deribit OHLC for bucket_distribution events only
2. keep fresh option rows with has_real_trade and close > 0 inside each hourly candle
3. infer same-hour spot from traded call-put parity pairs:
       spot = median K / (1 - (call_close - put_close))
4. choose the nearest traded call strike below K* and nearest traded call strike above K*
5. convert call closes to USD using parity spot
6. estimate local digital:
       P_DER(S_T > K*) ~= -dC/dK
       = - (C_usd_high - C_usd_low) / (K_high - K_low)
7. clip probability to [0, 1], while recording deribit_survival_clipped
```

Timestamp convention:

```text
Deribit 60-minute TradingView ticks and Polymarket sampled prices are both
aligned to the floored hour-bucket label. Deribit close is interpreted as the
within-hour OHLC close, while Polymarket uses the last sampled observation in
that hour. This does not eliminate within-hour non-synchronicity.
```

Current Deribit-side Track B diagnostics:

```text
selected bucket events = 79
hourly bars = 13,119
pass local-survival bars = 4,913
Deribit informative bars = 4,168
pass share = 0.374495
informative share = 0.317707

main failure reasons:
    missing fresh call strikes bracketing K* = 3,990
    no valid same-hour parity pair = 3,412
    missing call-put pair for parity = 646
    no fresh traded options = 158
```

### 9.4 Lead-Lag Panel

Join:

```text
pm_survival_hourly
deribit_survival_hourly
```

Output:

```text
data/processed/panels/lead_lag_survival_panel.parquet
```

Fields:

```text
event_id
timestamp
event_type_for_trackB
K_star
K_star_source
pm_survival
deribit_survival
pm_change
deribit_change
divergence
pm_quality_flags
deribit_quality_flags
pm_has_real_update
deribit_has_real_trade
pm_time_since_last_update_minutes
deribit_time_since_last_trade_minutes
both_sides_real_update
stale_ratio_bucket
initial_k_star_moneyness
k_star_moneyness
survival_low_power_flag
```

Current joined PM-Deribit Track B coverage:

```text
script: scripts/P1_pipeline/build_trackB_lead_lag_panel.py

sample = bucket_distribution only
join = inner join on event_id and floored hourly timestamp

joined rows = 10,739
events = 79
PM informative hours on joined grid = 8,759
Deribit informative hours on joined grid = 3,461
joint informative hours = 2,973
median joined hours per event = 147
median joint informative hours per event = 37
events with >=72 joint informative hours = 2
events with >=48 joint informative hours = 27
events with 0 joint informative hours = 0
median absolute PM-Deribit survival divergence = 0.064183
```

Interpretation:

```text
The Deribit local-survival estimator is the current Track B bottleneck. The
primary bucket sample remains conceptually clean, but lead-lag power is limited
by same-hour parity and bracketing-strike requirements. Do not run or headline
Granger / information-share results until this coverage bottleneck is either
accepted as the primary design constraint or addressed by a pre-specified
relaxed Deribit estimator.
```

Current 6h re-estimated Deribit diagnostic:

```text
script: scripts/P1_pipeline/build_trackB_deribit_survival_panel.py --bar-hours 6

Deribit 6h bars = 2,226
pass local-survival bars = 1,821
Deribit informative bars = 1,569
pass share = 0.818059
informative share = 0.704852

Remaining failure reasons:
    missing fresh call strikes bracketing K* = 369
    no valid same-block parity pair = 36
```

Current 6h joined coverage and frequency diagnostic:

```text
script: scripts/P1_pipeline/build_trackB_lead_lag_panel.py --bar-hours 6

joined rows = 1,869
events = 79
joint informative rows = 1,121
change-pair rows = 889
joint informative rows pass the pre-specified minimum of 600 change pairs

corr(Delta PM, Delta Deribit) = 0.534829
PM change std = 0.091070
Deribit change std = 0.144990
Deribit / PM change std ratio = 1.592076
Deribit change lag-1 autocorr = -0.248387
median max consecutive joint-informative run = 48 hours
max consecutive joint-informative run = 126 hours
events with >=24h consecutive joint-informative run = 72
events with >=48h consecutive joint-informative run = 43
```

Current 6h pooled lead-lag diagnostic:

```text
script: scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py

sample:
    informative rows = 1,121
    regression rows with consecutive 6h lags = 703
    regression events = 77

cross-correlation:
    Deribit leads PM by 12h: -0.023301
    Deribit leads PM by 6h:   0.073590
    contemporaneous:          0.534829
    PM leads Deribit by 6h:   0.025272
    PM leads Deribit by 12h:  0.057311

pooled event-FE regressions:
    PM equation:
        Deribit lag coefficient = 0.057729, p = 0.061500
    Deribit equation:
        PM lag coefficient = 0.329746, p = 0.000053
        Deribit own lag coefficient = -0.400558, p ~= 0
```

Level convergence on the same 6h joint-informative panel:

```text
level corr(PM survival, Deribit survival) = 0.911992
median absolute survival wedge = 0.049052
median signed PM - Deribit survival wedge = -0.010667
```

Interpretation discipline:

```text
6h aggregation makes Track B feasible for pooled diagnostics, but not for
Hasbrouck information share. The cleanest evidence is contemporaneous
cross-market convergence at 6h frequency and high level agreement.

Do not interpret the asymmetric pooled regression coefficients as PM leading
Deribit. Deribit changes remain noisier than PM changes, and the Deribit
own-lag coefficient is strongly negative. This creates an errors-in-variables
asymmetry: noisy Deribit changes are attenuated when placed on the right-hand
side, while PM lagged changes can appear large when Deribit is the noisy left
hand side. The symmetric cross-correlation diagnostics show no robust lead in
either direction; both lead correlations are below 0.08 and are dominated by
the contemporaneous 0.534829 correlation.

Final Track B identification:
    cross-market integration / convergence: supported
    6h contemporaneous co-movement: supported
    directional price-discovery ranking: unidentified
    sub-6h lead-lag: not measurable with current Deribit OHLC liquidity
```

Tests:

```text
trade/update frequency diagnostics before any lead-lag test
cross-correlation by lag
pooled lead-lag regression on changes, interpreted with measurement-error caveat
symmetry check against cross-correlation before any directional claim
event fixed effects
initial K* moneyness control
wild cluster bootstrap as primary inference
clustered standard errors as descriptive diagnostics
```

Robustness:

```text
both-sides-real-update bars only
low-stale subsample
stale-ratio terciles
compare full sample vs both-sides-real-update sample as a state-dependence result, not a ground-truth test
bucket-distribution events only
bucket-distribution plus point-threshold events
market-defined vs rule-selected K* interaction
exclude or flag saturated survival probabilities outside [0.05, 0.95]
2h aggregation
4h aggregation
different K* rules
stricter liquidity filters
BTC-only / ETH-only
exclude early 2025 sparse events
```

## 10. Backtest Scope

Backtest should come after signal diagnostics.

Do not call it arbitrage. Use:

```text
relative value signal
```

Baseline:

```text
single-leg Polymarket convergence test
```

More complex extension:

```text
Polymarket + Deribit hedged relative value
```

The hedged version must account for:

```text
different settlement horizons
binary Polymarket payoff vs continuous option payoff
margin
execution cost
Deribit option liquidity
basis risk
```

The horizon-mismatched hedged version is structurally incomplete: if Polymarket and Deribit settle at different times, the strategy carries unhedged exposure over the gap period. Even with a statistically significant divergence signal, economic value may be limited by this binary-vs-continuous payoff and non-identical settlement structure, not only by transaction costs.

## 11. P1 Execution Order

1. Build canonical event and cell tables.
2. Download Polymarket prices-history for all target events.
3. Build Polymarket hourly and daily distribution panels.
4. Download Deribit OHLC for all target events at `1D`.
5. Build Track A daily distribution divergence panel.
6. Download or reuse Deribit OHLC at `60`.
7. Select K* per event using ex-ante rule.
8. Build Track B hourly survival probability panel.
9. Run first diagnostics:
   - Polymarket probability sum quality;
   - Deribit strike coverage;
   - ATM survival coverage;
   - Polymarket update frequency and Deribit trade frequency;
   - stale-bar share and time-since-last-trade distribution;
   - cross-strike trade-time spread for daily curves;
   - K* moneyness drift and survival saturation rate;
   - initial K* moneyness by K* source;
   - bucket primary vs point-threshold extension coverage;
   - divergence distribution;
   - location / spread / skew decomposition;
   - tail relative and log-odds divergence;
   - time-to-expiry composition by signed horizon gap;
   - RND smoothness and mean-constraint sensitivity;
   - spread-moment regression with asset and time-to-expiry controls, clustered by event;
   - smoothness regression robustness for generated spread moments;
   - open-tail midpoint robustness for spread moments;
   - state-grid edge-mass truncation check;
   - lead-lag cross-correlation.
10. Freeze the primary-specification vs robustness table before running broad regressions.
11. Only then decide whether to implement trading signal tests.

## 12. Stop Conditions

Abort or downgrade Track A if:

```text
daily Deribit curve fitting fails for too many event-days
bucket probabilities frequently negative after smoothing
Deribit strike coverage does not bracket Polymarket cells
```

Abort or downgrade Track B if:

```text
ATM survival probability has poor hourly coverage in full sample
survival series is dominated by stale prices
lead-lag direction flips across stale-ratio subsamples
lead-lag results flip under 2h/4h aggregation
```

Do not automatically downgrade Track B just because the full-sample result differs from the both-sides-real-update subsample. That difference may be the substantive state-dependent result: price discovery can exist only during jointly active information states.

If Track B fails, the project can still stand as:

```text
daily cross-market distribution divergence study
```

If both Track A and B pass, the full project becomes:

```text
cross-market probability divergence and price discovery study
```
