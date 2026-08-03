# P3 SOL Track A External-Validity Extension

## 1. Purpose

This document defines a bounded external-validity extension after the frozen P1
analysis. The extension asks one narrow question:

> Do the Track A findings observed for BTC and ETH also appear in a third crypto
> asset when the same distribution-comparison framework is applied?

The first candidate asset is `SOL`. `XRP` is a backup candidate only. This is not
a new primary project, not a reopening of P1, and not an attempt to obtain a more
interesting result by trying many assets or specifications.

The extension is useful under every honest outcome:

- similar results would provide limited cross-asset support;
- different results would document asset heterogeneity;
- insufficient data would document the boundary of the research design;
- technically valid but low-information results would show low marginal benefit
  from broadening the asset universe.

All outcomes must be retained and reported. The extension must not be hidden,
re-specified, or replaced because its estimates are statistically insignificant
or economically small.

## 2. Scope and hard boundaries

### Included

- one full feasibility audit for SOL;
- Polymarket terminal-price bucket-event discovery and cleaning;
- Deribit SOL option-contract and historical-OHLC feasibility checks;
- explicit adaptation of the option-pricing units if the feasibility gate passes;
- replication of the frozen Track A distribution comparison;
- the same center, spread, tail-relative, L1, and L2 diagnostic layers used in P1;
- one concise external-validity result table and, only if informative, one figure;
- metadata recording the data snapshot, code commit, configuration, exclusions,
  and sample funnel.

### Excluded

- Track B or any new lead-lag analysis;
- trading, arbitrage, or profitability claims;
- searching through many assets until one produces a preferred conclusion;
- changing the BTC/ETH frozen P1 outputs;
- selecting a new smoothing parameter based on SOL results;
- a new parametric RND model unless the supervisor explicitly requests it;
- using current order-book snapshots as substitutes for missing historical data;
- pooling SOL into BTC/ETH before the standalone SOL diagnostics have passed.

### Time limit

The full extension has a maximum budget of `7-10 calendar days`.

- The feasibility audit should stop after `2-3 days`.
- If the feasibility gate fails, no estimator should be built merely to rescue the
  extension.
- If the gate passes, Track A implementation, validation, and reporting should use
  the remaining time.
- No additional empirical scope should be opened after the end of the second week.

## 3. Relationship to the frozen project

P1 remains the primary empirical analysis:

```text
P1 primary assets: BTC and ETH
P1 Track A status: frozen
P1 Track B status: frozen
P3 role: standalone external-validity extension
```

The source of truth for the P1 interpretation remains:

```text
docs/decision_logs/P1_EMPIRICAL_FREEZE.md
docs/decision_logs/P1_PAPER_CONCLUSIONS.md
docs/decision_logs/P1_DECISION_LOG.md
```

P3 may reuse methodology, validation rules, and transformations from P1. It must
write to separate P3 paths and must not overwrite the existing P1 parquet, table,
figure, or metadata files.

Recommended output separation:

```text
data/raw/p3_sol/
data/processed/p3_sol/
result/P3_sol_extension/
paper/tables/tab_p3_sol_*.{csv,tex}
paper/figures/fig_p3_sol_*.pdf
docs/decision_logs/P3_SOL_EXTENSION_OUTCOME.md
```

## 4. Main methodological risk

The current Track A implementation is not asset-agnostic.

`scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py` currently treats Deribit
option closes as coin-denominated prices. Its payoffs are divided by spot, its
put-call parity calculation uses the inverse-option convention, and its fit-quality
tolerance is expressed in coin units.

Deribit documents SOL options as linear USDC-settled options. Therefore, changing
an asset label from BTC or ETH to SOL is not a valid implementation. Before using
SOL, P3 must confirm from instrument metadata and official contract documentation:

- settlement currency;
- contract size or multiplier;
- quotation unit of OHLC `close`;
- option payoff convention;
- expiry time and settlement index;
- correct put-call parity equation;
- correct conversion of option-price errors into USD or USDC terms.

Official references to retain in the metadata or research notes:

- [Deribit Linear USDC Options](https://support.deribit.com/hc/en-us/articles/31424932728093-Linear-USDC-Options)
- [Deribit Contract Introduction Policy](https://support.deribit.com/hc/en-us/articles/25944688876957)
- [Deribit altcoin-option introduction note](https://insights.deribit.com/education/new-altcoin-options-on-deribit-sol-xrp-matic/)

If the pricing unit cannot be verified, P3 stops at the feasibility stage.

## 5. Research design frozen before results

### Primary comparison

For each passing SOL event-day, compare:

```text
P = normalized Polymarket terminal bucket distribution
Q = Deribit option-implied risk-neutral terminal distribution
```

Use the same conceptual hierarchy as P1:

1. center/location agreement;
2. tail-relative or log-odds divergence;
3. spread difference, explicitly conditional on smoothing;
4. L1/L2 as secondary shape diagnostics.

### Baseline settings

The P1 baseline should be copied rather than selected again after seeing SOL:

```text
daily resolution
smooth_weight = 0.10
minimum fresh strikes = 8
maximum stale-bar share = 0.30
state-grid lower multiplier = 0.5
state-grid upper multiplier = 1.5
open-tail midpoint = 0.5 finite bucket widths
```

These are methodological carryovers, not claims that SOL has already passed them.
If contract-unit adaptation requires a different numerical error tolerance, that
tolerance must be derived from a common unit such as relative underlying value or
USD/USDC RMSE before viewing the distribution-divergence result.

### Required robustness layer

If SOL reaches the final comparison sample, run the existing P1 robustness logic:

```text
smooth_weight in {0.00, 0.05, 0.10, 0.20}
open-tail midpoint in {0.5w, 1.0w}
state-grid edge-mass diagnostic
```

The extension must not introduce a larger specification search.

## 6. Stage 0: preserve the baseline

Before changing code or downloading new data:

1. Record the current git commit and `git status`.
2. Confirm the P1 freeze outputs are unchanged.
3. Create P3-only output directories.
4. Save a configuration file containing:
   - candidate asset;
   - data snapshot timestamp in UTC;
   - official API endpoints used;
   - intended date range;
   - baseline and robustness parameters;
   - software versions;
   - random seed, if any stochastic procedure is introduced.
5. Do not silently clean or commit unrelated working-tree changes.

Deliverable:

```text
data/processed/p3_sol/p3_sol_run_config.json
```

## 7. Stage 1: Polymarket feasibility audit

### 7.1 Event discovery

Search for resolved SOL events whose outcome is the terminal SOL price at a stated
date and time. Keep discovery broad, but classify every candidate before downloading
full histories.

Include only events that can represent mutually exclusive terminal-price cells,
for example:

```text
SOL price below K1
SOL price between K1 and K2
...
SOL price above Kn
```

Exclude:

- hit/touch/path-dependent events such as "Will SOL reach X before date T?";
- daily-high, daily-low, or intraperiod crossing events;
- events with ambiguous or inconsistent settlement times;
- independent binary markets that do not form one coherent partition;
- events whose resolution source cannot be identified;
- duplicate or overlapping bins that cannot be resolved deterministically.

### 7.2 Required event-level fields

The inventory must contain at least:

```text
event_id
event_title
asset
event_type
event_start_time
event_end_time
settlement_timestamp
settlement_reference
resolution_status
number_of_cells
finite_bucket_width
has_left_tail
has_right_tail
has_overlap
has_gap
raw_probability_sum_available
exclusion_reason
```

The cell table must contain at least:

```text
event_id
cell_id
market_id
yes_token_id
cell_type
cell_low
cell_high
sort_key
```

### 7.3 Polymarket feasibility decision

The Polymarket side passes only if there is a defensible panel, not merely one
interesting event. Use the following pre-specified engineering-feasibility rules.
They are pragmatic continuation rules, not a statistical-power calculation:

```text
candidate event: at least 4 mutually exclusive cells, including both open tails
PASS candidate panel: at least 10 clean events across at least 3 distinct expiries
LIMITED PASS candidate panel: at least 5 clean events across at least 2 distinct expiries
FAIL candidate panel: fewer than 5 clean events or dependence on one expiry
```

The final cross-market sample must be assessed again after Deribit and curve-quality
gates:

```text
PASS final panel: at least 30 passing event-days from at least 10 events and 3 expiries
LIMITED PASS final panel: at least 15 passing event-days from at least 5 events and 2 expiries
concentration guard: no single event supplies more than 25% of passing event-days
FAIL final panel: below LIMITED PASS or concentration guard violated
```

These thresholds must not be relaxed after distribution-divergence estimates are
seen. `LIMITED PASS` authorizes descriptive evidence only; it does not support a
standalone cross-asset generalization claim.

At minimum, passing candidates must satisfy all of the following qualitative gates:

- resolved terminal-price bucket events exist;
- event cells form a complete or transparently repairable partition;
- both open tails are present or can be handled under the frozen P1 rule;
- historical YES-token price series are accessible;
- enough pre-expiry observations exist to form daily snapshots;
- exclusions do not leave the analysis dependent on a single event.

Deliverables:

```text
data/processed/p3_sol/polymarket_event_inventory.{csv,parquet}
data/processed/p3_sol/polymarket_event_cells.{csv,parquet}
data/processed/p3_sol/polymarket_feasibility_metadata.json
```

## 8. Stage 2: Deribit feasibility audit

For every Polymarket candidate expiry:

1. Query expired and current SOL option-instrument metadata.
2. Match the actual Deribit expiry timestamp; do not infer it only from a monthly
   calendar rule.
3. Record strikes, calls/puts, settlement period, quote currency, contract size,
   expiry timestamp, and settlement index.
4. Probe historical daily OHLC availability for a small number of instruments near
   the Polymarket bucket range.
5. Confirm that returned OHLC values have real trades and non-zero volume.
6. Confirm that enough calls, puts, and distinct strikes are available on relevant
   dates to support the frozen curve-quality gate.
7. Record Polymarket-to-Deribit horizon gap and reference-basis mismatch explicitly.

Do not treat instrument metadata as proof that historical prices exist. Do not treat
a non-empty chart response as proof of adequate cross-strike liquidity.

Deliverables:

```text
data/processed/p3_sol/deribit_instrument_inventory.{csv,parquet}
data/processed/p3_sol/deribit_expiry_match.{csv,parquet}
data/processed/p3_sol/deribit_ohlc_probe.{csv,parquet}
data/processed/p3_sol/deribit_contract_spec.json
data/processed/p3_sol/deribit_feasibility_metadata.json
```

## 9. Feasibility gate and stopping decision

Complete a written gate before building the full extension.

| Gate | Evidence required | Failure action |
|---|---|---|
| Event definition | Resolved terminal-price partitions | Stop if markets are path-dependent or ambiguous |
| PM history | Usable histories across multiple events | Stop if the panel depends on one event |
| Expiry match | Actual Deribit expiry metadata | Exclude unmatched events; stop if no panel remains |
| Contract units | Verified linear-USDC pricing equations | Stop if quotation/payoff units remain uncertain |
| Strike coverage | Calls/puts and sufficient fresh strikes around buckets | Exclude weak days; stop if coverage is structurally poor |
| Time alignment | Recorded settlement and snapshot gaps | Stop if timing cannot be defended |
| Reference basis | Both settlement references documented | Continue only as an explicit proxy if mismatch is measurable |
| Workload | Can be completed inside the remaining time budget | Stop rather than reopen project architecture |

Apply both sets of sample thresholds from Section 7.3. A candidate-stage `PASS`
authorizes full data collection. Candidate-stage `LIMITED PASS` authorizes only a
small-sample attempt if the Deribit audit requires no new architecture beyond the
linear-USDC adapter. The final label is determined again after all cross-market
quality gates and cannot be higher than the candidate-stage label.

Write the decision before Track A estimation:

```text
docs/decision_logs/P3_SOL_FEASIBILITY_DECISION.md
```

The decision must be one of:

```text
PASS: proceed to standalone SOL Track A
LIMITED PASS: proceed as a labelled small-sample case extension
FAIL: stop and report the data/contract limitation
```

`FAIL` is a valid research outcome and does not trigger an automatic search for
another asset.

## 10. XRP backup rule

XRP may be assessed only when one of the following is true:

1. SOL fails for an asset-specific Polymarket coverage reason and the remaining
   feasibility-audit time permits one backup check; or
2. SOL passes and XRP can use the same validated linear-USDC adapter without new
   estimator architecture.

Do not run XRP merely because the SOL result is weak, insignificant, or similar to
BTC/ETH. At most one backup feasibility audit is allowed.

## 11. Stage 3: implementation after a PASS

### 11.1 Required code separation

Do not edit P1 constants until the new contract logic is covered by tests. Preferred
structure:

```text
scripts/P3_asset_extension/
  build_p3_event_inventory.py
  check_p3_deribit_availability.py
  build_p3_polymarket_panels.py
  build_p3_deribit_ohlc.py
  build_p3_trackA_panel.py
  build_p3_trackA_diagnostics.py
  run_p3_sol_extension.py

tests/
  test_p3_option_units.py
  test_p3_event_cells.py
  test_p3_trackA_smoke.py
```

Shared pure functions may later be extracted from P1 only if tests show that the
refactor leaves all frozen BTC/ETH outputs unchanged.

### 11.2 Option-pricing adapter

Implement an explicit contract convention rather than scattered asset conditionals.
The adapter should define:

```text
quote_currency
settlement_currency
contract_multiplier
option_price_to_usd_or_usdc()
call_payoff()
put_payoff()
put_call_parity_spot_or_forward()
fit_error_in_common_units()
```

Required minimal tests:

1. A synthetic call/put pair recovers a known spot or forward under the documented
   SOL convention.
2. Synthetic option prices generated from a known discrete distribution recover a
   probability vector with non-negative entries and sum approximately one.
3. Rescaling the contract multiplier does not change recovered probabilities.
4. The adapter rejects mixed or unknown quote currencies.
5. The BTC/ETH frozen path remains numerically unchanged if shared code is touched.

### 11.3 Data pipeline

Run the same conceptual stages as P1:

```text
event inventory
-> canonical event cells
-> Polymarket price histories
-> PM hourly/daily normalized distributions
-> Deribit OHLC grids and bar-quality diagnostics
-> event-day alignment and quality gates
-> option-implied state probabilities
-> cell-level P-versus-Q comparison
-> event-day moments and divergence diagnostics
```

Every stage must write a parquet file plus metadata JSON. CSV is an inspection copy,
not the canonical machine-readable artifact.

## 12. Stage 4: validation before interpretation

Do not inspect or discuss economic conclusions until these checks pass:

### Data integrity

- no duplicate `event_id/cell_id/timestamp` keys;
- monotone, non-overlapping cell bounds;
- one asset and one settlement definition per event;
- UTC timestamps throughout;
- raw files are cached and never silently replaced;
- all exclusions have explicit reason codes.

### Polymarket distribution

- daily snapshot selection is reproducible;
- raw probability sums are reported before normalization;
- no look-ahead from post-snapshot prices;
- open-tail treatment matches P1.

### Deribit curve

- at least the frozen minimum number of fresh strikes;
- stale share and volume are recorded;
- call monotonicity and convexity diagnostics are reported;
- fitted probabilities are non-negative and sum to one within tolerance;
- forward/spot fit error is reported in the correct contract units;
- option repricing RMSE is reported in a common interpretable unit;
- state-grid edge mass is not silently ignored.

### Cross-market mapping

- PM settlement timestamp, PM snapshot timestamp, Deribit bar timestamp, and Deribit
  expiry timestamp are all retained;
- signed horizon gaps use the same definition as P1;
- settlement/reference-basis differences are shown as limitations rather than exact
  matches.

## 13. Stage 5: analysis and comparison

### Standalone SOL results

Report at least:

- full sample funnel: discovered events, eligible events, downloaded histories,
  aligned event-days, curve-quality passes, final comparison event-days;
- event count and event-day count together;
- distribution location difference;
- spread difference and PM-wider share;
- tail-relative and log-odds divergence;
- secondary L1/L2 distance;
- sensitivity to smoothing, open-tail midpoint, and state-grid truncation;
- fit-quality summaries and failure reasons.

### Cross-asset comparison

Compare SOL with frozen BTC and ETH descriptively. Do not automatically pool the
three assets. The comparison should distinguish:

```text
direction: does the sign/pattern agree?
magnitude: is the estimated wedge similar in economic size?
uncertainty: is the SOL sample precise enough to support a claim?
quality: are differences plausibly driven by liquidity, coverage, timing, or contract design?
```

Avoid treating a non-significant difference as proof that assets are identical.
Avoid treating a significant result from a small extension as a new universal law.

## 14. Required outputs

Minimum paper-facing outputs after a successful extension:

```text
paper/tables/tab_p3_sol_sample_funnel.{csv,tex}
paper/tables/tab_p3_sol_trackA_summary.{csv,tex}
paper/tables/tab_p3_cross_asset_comparison.{csv,tex}
paper/tables/tab_p3_sol_robustness.{csv,tex}
```

Optional figure, only when it communicates more clearly than the tables:

```text
paper/figures/fig_p3_sol_distribution_comparison.pdf
```

Required machine-readable and audit outputs:

```text
data/processed/p3_sol/p3_sol_sample_funnel.{csv,parquet}
data/processed/p3_sol/p3_sol_event_day_divergence.{csv,parquet}
data/processed/p3_sol/p3_sol_curve_fits.{csv,parquet}
data/processed/p3_sol/p3_sol_trackA_metadata.json
docs/decision_logs/P3_SOL_EXTENSION_OUTCOME.md
```

The final metadata must record:

```text
git_commit
data_snapshot_utc
source_endpoints
source_file_hashes or stable file inventory
software_versions
contract_convention
all parameter values
random_seed or deterministic=true
row and event counts at every gate
output file paths
```

## 15. Interpretation templates

Use only the template supported by the actual estimates.

### A. Broadly consistent

```text
The standalone SOL extension produced a qualitatively similar pattern to the
frozen BTC/ETH analysis. This provides limited cross-asset support for the main
Track A interpretation, although the conclusion remains conditional on the smaller
SOL event panel, linear-USDC option structure, and cross-market reference mismatch.
```

### B. Same direction, weak precision or small magnitude

```text
The SOL estimates point in the same direction as the BTC/ETH results, but their
magnitude and/or precision are weaker. The extension therefore does not materially
change the main conclusion and is treated as limited external-validity evidence
rather than a new headline result.
```

### C. Different pattern

```text
The SOL extension does not reproduce the BTC/ETH pattern. This suggests that the
P-versus-Q wedge is heterogeneous across assets and may depend on liquidity,
contract design, event composition, or maturity alignment. Given the extension's
sample size, the result is evidence against unrestricted generalization rather than
a definitive causal explanation.
```

### D. Feasibility failure

```text
The study assessed a SOL extension but did not proceed to full estimation because
the available event partitions, historical option coverage, contract-unit
verification, or expiry alignment did not satisfy the pre-specified feasibility
requirements. This identifies a practical external-validity boundary of the data
design rather than a null economic result.
```

### E. Low marginal research value

```text
The SOL extension was technically feasible but added little information beyond the
frozen BTC/ETH results. Because the added asset did not materially sharpen or alter
the central interpretation, the dissertation retains BTC and ETH as the primary
sample and reports SOL as a bounded robustness extension.
```

Do not use the phrase "no effect" unless an effect and a justified equivalence
margin were explicitly defined and tested. Prefer "did not materially change the
interpretation" or "was estimated imprecisely."

## 16. Completion and stop criteria

P3 is complete when exactly one of the following occurs:

### Feasibility stop

- the written gate records `FAIL`;
- evidence and failure reasons are saved;
- the limitation is added to the dissertation or appendix;
- no additional asset search is started unless the pre-specified XRP backup rule
  applies.

### Empirical completion

- the written gate records `PASS` or `LIMITED PASS`;
- all required tests and validation checks pass;
- standalone SOL outputs and metadata are generated;
- results are compared against the frozen BTC/ETH interpretation;
- the extension is reported regardless of direction or significance;
- P1 outputs remain byte-for-byte or numerically unchanged as appropriate;
- no Track B or new model is opened.

After either completion route, the remaining dissertation time returns to writing,
evidence checking, and P2 repository/reproducibility cleanup.

## 17. Suggested working schedule

### Days 1-2

- build the SOL Polymarket inventory;
- classify terminal bucket versus path-dependent events;
- inspect settlement rules and cell completeness;
- write provisional event counts without interpreting prices.

### Day 3

- inspect Deribit instrument metadata and historical OHLC probes;
- document the linear-USDC contract convention;
- write `P3_SOL_FEASIBILITY_DECISION.md`.

### Days 4-6, only after PASS

- implement and test the contract-pricing adapter;
- build SOL PM and Deribit panels;
- run a one-event smoke test before the full panel.

### Days 7-8

- run the full standalone Track A extension;
- validate quality gates and robustness specifications;
- generate tables and metadata.

### Days 9-10

- write `P3_SOL_EXTENSION_OUTCOME.md`;
- insert one concise subsection or appendix section into the dissertation;
- freeze P3 and return to dissertation writing.

## 18. Immediate next action

The next task is not full data collection. It is a read-only inventory and contract
audit that answers:

```text
Does a defensible multi-event SOL terminal-distribution panel exist on Polymarket,
and can it be matched to historically traded Deribit linear-USDC option curves
under a verified pricing convention?
```

Only a documented `PASS` or `LIMITED PASS` authorizes implementation of the SOL
Track A estimator.

## 19. Execution checklist

### Feasibility checkpoint

- [ ] Record baseline git state and P1 output inventory.
- [ ] Freeze `p3_sol_run_config.json` before inspecting divergence results.
- [ ] Build and manually audit the SOL Polymarket candidate inventory.
- [ ] Apply terminal-bucket, partition-completeness, expiry-diversity, and sample-size gates.
- [ ] Retrieve actual Deribit SOL instrument metadata for candidate expiries.
- [ ] Verify linear-USDC quotation, payoff, multiplier, parity, expiry, and settlement-index rules.
- [ ] Probe historical OHLC, trade freshness, strike coverage, and call/put availability.
- [ ] Write `P3_SOL_FEASIBILITY_DECISION.md` as `PASS`, `LIMITED PASS`, or `FAIL`.

### Implementation checkpoint, only after PASS or LIMITED PASS

- [ ] Write failing unit tests for the linear-USDC pricing adapter.
- [ ] Implement the smallest contract adapter that passes the synthetic tests.
- [ ] Verify that any touched shared function leaves frozen BTC/ETH outputs unchanged.
- [ ] Build P3 Polymarket history and daily-distribution panels in P3-only paths.
- [ ] Build P3 Deribit OHLC and curve-quality panels in P3-only paths.
- [ ] Run a one-event end-to-end smoke test and inspect all units and timestamps.
- [ ] Run the full eligible SOL panel without changing the frozen specification.

### Evidence checkpoint

- [ ] Reapply the final-panel sample and concentration gates.
- [ ] Run center, tail-relative, spread, L1/L2, smoothing, tail, and edge-mass diagnostics.
- [ ] Generate the required parquet, JSON, CSV, LaTeX, and optional PDF outputs.
- [ ] Verify counts and paper-facing values against machine-readable sources.
- [ ] Write `P3_SOL_EXTENSION_OUTCOME.md`, including failures and exclusions.
- [ ] Add only the supported interpretation to the dissertation or appendix.
- [ ] Freeze P3 and return to writing and P2 repository cleanup.
