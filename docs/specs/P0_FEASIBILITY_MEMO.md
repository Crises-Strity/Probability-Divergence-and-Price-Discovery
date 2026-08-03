# P0 Feasibility Memo: Probability Divergence and Price Discovery

Date: 2026-06-30

Status note:

```text
This is a historical P0 feasibility memo. Track B statements that describe
"hourly main" or "2h/4h robustness" were superseded by the P1 empirical freeze:
hourly is now a feasibility diagnostic, 6h is the primary measurable integration
frequency, and directional lead-lag is unidentified.

Current source of truth:
docs/decision_logs/P1_PAPER_CONCLUSIONS.md
docs/decision_logs/P1_DECISION_LOG.md
docs/specs/P1_FINAL_OUTPUT_SPEC.md
docs/specs/P2_NEXT_STEPS.md
```

Naming note: `Order Book Divergence Signal` should be treated as the original project prompt, not the final dissertation title. P0 confirms that historical Deribit order books are not available through the tested public endpoints, so the accurate scope is probability divergence and price discovery using Polymarket CLOB history and Deribit option OHLC.

## 1. Project Objective

This project studies whether crypto prediction markets and crypto option markets price the same terminal BTC/ETH price events consistently.

The core comparison is:

```text
Polymarket event-implied probability
vs
Deribit option-implied risk-neutral probability
```

The project is not a pure arbitrage project. It is a cross-market probability price discovery study with an optional trading signal interpretation. The final design must avoid three known traps:

- treating Polymarket physical/event probabilities and Deribit risk-neutral probabilities as identical;
- mistaking terminal mechanical convergence for active mean reversion;
- using stale or sparse option trades to infer noisy high-frequency RNDs.
- interpreting last-trade lead-lag as information flow without ruling out non-synchronous trading and stale-price effects.

## 2. Final P0 Conclusion

The project is feasible, but only under a two-track design:

```text
Track A: Distribution divergence / P-Q wedge measurement
Frequency: daily
Polymarket: full event partition distribution
Deribit: daily option-OHLC-implied bucket probabilities

Track B: Price discovery / lead-lag
Frequency: hourly main, 2h/4h robustness
Polymarket: survival probability P(S_T > K*) from cell sums
Deribit: local ATM survival probability P(S_T > K*) from liquid strikes
```

The original idea of using hourly full-RND reconstruction for lead-lag should not be the main design. The hourly full RND depends too much on tail strikes and last-trade noise. Lead-lag should use a lower-dimensional ATM survival probability series.

Interpretation discipline:

```text
Track A raw levels measure cross-market P-vs-Q / event-vs-risk-neutral wedges, not pure mispricing.
Track B uses changes in local survival probabilities, so it is less exposed to slow-moving structural wedges but more exposed to stale-price and trading-frequency artifacts.
```

## 3. Polymarket Feasibility

### 3.1 Market Inventory

The Polymarket inventory was built from the Gamma public-search API and saved under:

```text
data/raw/polymarket/
data/processed/polymarket/
```

Key counts:

```text
raw events: 3,758
raw market rows: 22,801
terminal candidates after no-intraday filter: 10,842
event quality rows: 1,040
```

Market type counts:

```text
terminal_bucket: 8,292
terminal_point:  6,959
touch_barrier:   5,724
intraday_binary: 1,813
unknown:            13
```

Only `terminal_bucket` and `terminal_point` are suitable for Deribit terminal option comparison. `touch_barrier` is path-dependent and should stay out of the main sample.

Numerical reconciliation:

```text
terminal_bucket + terminal_point = 15,251
terminal rows with intraday time wording = 4,409
  terminal_bucket with intraday wording = 2,769
  terminal_point with intraday wording = 1,640
terminal candidates after no-intraday filter = 15,251 - 4,409 = 10,842
```

The `4,409` count is an independent `value_counts()` result from `data/raw/polymarket/polymarket_market_inventory.csv`, not a back-solved residual. The `no-intraday filter` is therefore not a deduplication step. It removes terminal-looking markets whose question text contains intraday settlement wording, because those cannot be cleanly matched to a vanilla Deribit terminal expiry.

### 3.2 Clean Event Sample

The usable event-level sample is:

```text
target events: 124
clean bucket-distribution events: 79
usable point-threshold events: 45
BTC events: 60
ETH events: 64
```

The 79 clean bucket-distribution events are the main sample for full distribution comparison. Each event has:

- middle bucket markets;
- left-tail `less than floor` point market;
- right-tail `greater than ceiling` point market;
- close/exact horizon match to nearest Deribit monthly expiry.

This means Polymarket provides a complete terminal price-axis partition:

```text
left tail + middle buckets + right tail
```

The 45 usable point-threshold events should not enter Track A because they do not provide a full distribution. They can enter Track B if their threshold is usable as `K*` and Deribit local survival probability is available. They must be flagged separately because their `K*` is market-defined, while bucket-distribution events use a rule-selected event-start ATM boundary.

### 3.3 Event Life

The event life result is structurally important:

```text
median event life: 6.99 days
120 / 124 events are in the 3-7 day range
no event has a 14/30 day life
```

This changes the empirical design. Daily frequency is acceptable for distribution snapshots, but not for within-event lead-lag. Lead-lag requires hourly or multi-hour data.

### 3.4 Polymarket Prices-History Spike

Event tested:

```text
event_id: 21348
event: Bitcoin price on March 28?
life: 2025-03-21 15:45 UTC to 2025-03-28 12:00 UTC
cells: 7
```

Polymarket CLOB `prices-history` returned hourly in-life prices:

```text
history rows: 1,204
hourly distribution rows: 172
```

Probability sum check:

```text
all hourly rows in [0.9, 1.1]: 171 / 172
excluding first warm-up row: 171 / 171
```

The first hour had probability sum 3.02, consistent with market initialization noise. The main pipeline should exclude the first 1-3 hours after event start.

Example snapshot on 2025-03-25 23:00 UTC:

```text
<78k:     0.0115
78-80k:   0.0235
80-82k:   0.0460
82-84k:   0.0900
84-86k:   0.1650
86-88k:   0.2550
>88k:     0.4200
sum:      1.0110
```

Conclusion: Polymarket in-life distribution reconstruction is feasible, with a mandatory warm-up filter.

## 4. Deribit Feasibility

### 4.1 Public API Reality

The following public Deribit routes were tested:

```text
public/get_instruments
public/get_order_book
public/get_mark_price_history
public/get_tradingview_chart_data
public/get_last_trades_by_instrument_and_time
```

Key result:

```text
historical order book: not available for expired options
historical mark history: not usable for expired options
historical option OHLC via get_tradingview_chart_data: available
```

Therefore the project must not be framed as historical Deribit order-book reconstruction. The Deribit side is option-OHLC-implied probability reconstruction.

### 4.2 Historical OHLC Availability

The availability probe constructed expired option names and queried `get_tradingview_chart_data`.

Results:

```text
Polymarket target events: 124
target expiry groups: 26
chart history probes: 156
successful chart histories: 145
success rate: 92.9%
```

By asset:

```text
BTC: 77 / 84 = 91.7%
ETH: 68 / 72 = 94.4%
```

This confirms that historical option OHLC can be pulled without paid data, but instrument enumeration must be constructed from expiry and strike names rather than relying on `get_instruments(expired=true)`.

### 4.3 Daily Full-Grid RND Spike

Event tested:

```text
event_id: 21348
Deribit expiry: 2025-03-28 08:00 UTC
strike grid: 66k to 100k, step 2k
instruments attempted: 36
```

Daily OHLC result:

```text
chart rows: 882
errors: 6
days with >=6 distinct traded strikes: 30 / 31
days with >=8 distinct traded strikes: 30 / 31
median distinct traded strikes/day: 15
```

The failed instruments were far low-tail strikes, not the Polymarket main bucket range.

Additional manual convexity check on a mid-life day found that the raw call curve was monotone and almost convex, with one small local convexity violation consistent with last-trade noise. This supports using smoothed/shape-constrained option curves for daily bucket probabilities.

Conclusion: Deribit daily full-grid RND/bucket-probability reconstruction is feasible for distribution divergence.

Important caveat: daily OHLC is still built from last trades that may occur at different times across strikes. Track A must therefore use a fixed target snapshot time, such as 08:00 UTC, select trades in a pre-specified window around that target, and record cross-strike trade-time spread as a curve-quality field. Staleness alone is not enough; the curve also needs approximate cross-sectional simultaneity.

### 4.4 Hourly Full-RND Problem

Because Polymarket events mostly live for only 7 days, hourly frequency is needed for lead-lag. The same Deribit event was tested at `resolution=60`.

For the full 30-day option window:

```text
bar quality rows: 721
bars with >=6 distinct traded strikes: 639
bars with >=8 distinct traded strikes: 542
```

For the actual Polymarket event life window:

```text
window: 2025-03-21 16:00 UTC to 2025-03-28 08:00 UTC
bars: 161
>=6 distinct traded strikes: 136 / 161 = 84.5%
>=8 distinct traded strikes: 105 / 161 = 65.2%
median distinct traded strikes/hour: 9
```

This is enough to indicate hourly option information exists. However, full-RND reconstruction at hourly frequency is expected to be noisy because it depends on tail strikes and sparse last trades. It should not be the primary lead-lag input.

## 5. Final Methodological Design

### Track A: Distribution Divergence / P-Q Wedge Measurement

Purpose:

```text
Compare full Polymarket partition probabilities with Deribit risk-neutral bucket probabilities.
The primary interpretation is cross-market probability-measure wedge, not direct mispricing.
```

Frequency:

```text
daily
```

Polymarket:

```text
left tail + middle buckets + right tail
```

Deribit:

```text
construct call/put grid
clean stale instruments
fit smooth option curve or implied-vol smile
integrate probabilities over Polymarket cells
```

Core outputs:

```text
bucket probability differences
distribution distance metrics
location/spread/skew/tail divergence
unexplained wedge component after observable controls
within-event residual dynamics
```

Track A should be split into two specifications:

```text
Spec A1: wedge explanation / RQ1
    LHS = event-day distribution distance or cell-day raw divergence
    FE = asset FE; cell/moneyness FE only for cell-day LHS; no event FE
    controls = time-to-expiry, horizon gap, settlement/reference mismatch, mapping quality,
               liquidity/spread/volume, curve quality, tail-cell indicator when cell-level

Spec A2: within-event residual dynamics / RQ2
    LHS = change in unexplained wedge component / residual divergence proxy
    FE = event FE, with optional cell/moneyness FE
    controls = time-varying controls only
    not estimated = horizon gap, settlement/reference mismatch, mapping quality, asset effect
```

The split is necessary because event fixed effects mechanically absorb event-invariant variables such as horizon gap, settlement/reference mismatch, mapping quality, and asset.

Raw tail divergence must not be used as a headline "mispricing" result unless the Polymarket tail favorite-longshot bias and Deribit crash-risk premium interpretations are both discussed.

Residual interpretation:

```text
controlled residual divergence = wedge component not explained by observable controls
controlled residual divergence still mixes unmodeled time-varying risk premium and possible cross-market divergence
levels alone cannot identify mispricing
residual dynamics / mean reversion provide the only weak identification route for active divergence
```

### Track B: Price Discovery / Lead-Lag

Purpose:

```text
Test which market updates first around a common liquid threshold K*.
```

Frequency:

```text
hourly main
2h/4h robustness
```

Polymarket:

```text
P_PM(S_T > K*) = sum of all cells above K*
For point-threshold events, the YES price is already a threshold survival probability if the market definition matches K*.
Record K_star_source = rule_selected for bucket-distribution events and market_defined for point-threshold events.
```

Deribit:

```text
P_DER(S_T > K*) from local ATM option information
```

Why not full hourly RND:

```text
hourly full RND depends on stale tail strikes
noise can bias price-discovery tests against Deribit
ATM/local survival probability uses the most liquid strikes
```

The threshold `K*` must be selected ex ante. A practical rule is:

```text
choose the event strike closest to the reference underlying price near event start,
subject to minimum Deribit and Polymarket liquidity.
```

This avoids look-ahead.

Point-threshold caveat:

```text
market-defined K* is known ex ante, but it is not generated by the same rule as bucket-event K*
initial K* moneyness may differ systematically between bucket and point-threshold events
lead-lag regressions must control initial K* moneyness and report bucket-only robustness
```

Point-threshold quality gate:

```text
minimum Polymarket volume / liquidity
minimum real update frequency
maximum stale share
survival probability not saturated outside [0.05, 0.95] for most of event life
Deribit local strike coverage around the market-defined threshold
```

Mandatory non-synchronous trading checks:

```text
report Polymarket update frequency and Deribit trade frequency by event, asset, and time-to-expiry
record whether each bar contains a real update/trade or a carried-forward value
record time since last Polymarket update and time since last Deribit option trade
rerun lead-lag on bars where both sides have real updates
rerun lead-lag on low-stale subsamples and stale-ratio terciles
compare full-sample and both-sides-real-update results as state dependence, not as truth vs falsehood
```

Without these checks, a lead-lag result can be a trading-frequency artifact rather than price discovery.

## 6. Econometric Implications

The data are event panels, not independent hourly observations.

Even if each 7-day event provides roughly 160 hourly points, effective statistical power comes from event-level trajectories:

```text
124 usable events
79 clean distribution events
```

Lead-lag analysis should therefore avoid treating all hourly rows as independent. Use event fixed effects and wild cluster bootstrap as the primary inference method; ordinary clustered standard errors should be treated as descriptive diagnostics because cluster counts become small in BTC-only, ETH-only, or exact-only subsamples.

Cointegration and price discovery methods should be gated:

```text
if paired probability series are cointegrated:
    VECM / information share style analysis
else:
    differenced VAR / Granger / cross-correlation
```

## 7. Required Filters

Polymarket:

```text
exclude event warm-up period, at least first 1-3 hours
require all cells available
require probability sum within tolerance, e.g. [0.9, 1.1]
normalize only after recording raw sum error
```

Deribit:

```text
drop instruments not found
require positive OHLC/volume in relevant bar
for daily full RND, require enough traded strikes for curve fitting
for daily full RND, require acceptable cross-strike trade-time spread around the target snapshot time
for hourly lead-lag, require local ATM strike coverage
for hourly lead-lag, flag low-power bars where survival probabilities are saturated outside [0.05, 0.95]
for point-threshold Track B events, require substitute quality gates because partition-sum checks are unavailable
```

Event matching:

```text
main sample: exact/close Polymarket-Deribit horizon alignment
loose matches: robustness only
unmappable: excluded
```

## 8. Current Risk Register

Confirmed non-blockers:

```text
Polymarket complete partitions exist
Polymarket prices-history is available
Deribit historical option OHLC is available
Deribit daily full-grid reconstruction is feasible
```

Confirmed design constraints:

```text
historical order book unavailable
historical mark history unavailable
events mostly live for ~7 days
hourly full-RND is too noisy for lead-lag
```

Open P1 diagnostics:

```text
ETH hourly ATM survival coverage
low-volume event coverage
actual noise level of ATM survival probability
best K* selection rule
K* moneyness drift and survival saturation through event life
initial K* moneyness by K_star_source
bucket-only vs bucket+point-threshold Track B comparison
2h/4h robustness effect
stale-price and non-synchronous trading sensitivity
daily RND sensitivity to last-trade OHLC rather than simultaneous quotes
```

## 9. P0 Decision

Proceed to P1, but build the pipeline around the two-track design:

```text
daily full-distribution divergence
hourly/local survival-probability lead-lag
```

Do not build P1 around hourly full-RND reconstruction.
