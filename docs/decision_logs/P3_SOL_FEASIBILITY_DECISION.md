# P3 SOL Feasibility Decision

**Decision:** `FAIL — stop before the SOL Track A estimator`<br>
**Decision date:** 2026-08-03 UTC<br>
**Frozen baseline:** `f546f6a012109641957786de5f69927155b9a497`<br>
**P3 branch:** `codex/p3-sol-feasibility`

## Decision in one sentence

SOL data access and contract-unit adaptation are technically possible, but a mechanically selected three-expiry historical OHLC probe produced zero event-days that satisfy the frozen P1 cross-strike quality gate; full 44-event downloading and estimator construction are therefore not justified.

## Risks and stopping rationale

Continuing would create three avoidable risks:

1. relaxing `minimum_fresh_strikes=8` or `maximum_stale_bar_share=0.30` after seeing SOL liquidity would turn the extension into a post-result specification search;
2. downloading all 44 candidates despite zero passing smoke days would consume the feasibility time budget without evidence that the final `15 event-days / 5 events / 2 expiries` LIMITED PASS floor is attainable;
3. fitting an RND to sparse strike updates would make any cross-asset difference difficult to distinguish from liquidity and stale-price effects.

The decision does not mean that Deribit SOL options or Polymarket SOL markets do not exist. It means that the frozen P1 Track A design does not clear its continuation gate on the bounded SOL sample.

## Evidence funnel

### Polymarket candidate structure

The bounded discovery and canonical partition audit retained:

```text
discovered events: 120
resolved complete terminal-price partitions: 44
candidate settlement timestamps: 44
candidate cell rows: 424
finite bucket width: USD 10 for all candidates
duplicate event/market/token/event-cell keys: 0
missing YES token IDs: 0
```

The written rules identify Binance SOL/USDT one-minute close at noon ET as the resolution reference. Historical YES-token price-series coverage was not downloaded because the Deribit quality gate failed first.

### Deribit mapping and units

Archived metadata matching retained:

```text
matched candidate events: 44 / 44
distinct actual Deribit expiries: 41
mapping quality: 39 exact, 3 close, 2 loose, 0 unmappable
verified linear-USDC contract units: 44 / 44
```

The verified contract convention is USDC premium per SOL, multiplier 10 SOL per contract, `sol_usdc` index, and 08:00 UTC expiry. This confirms that a SOL adapter is implementable and that the BTC/ETH coin-denominated implementation cannot be reused unchanged.

### Historical full-grid smoke probe

The sample was selected before inspecting OHLC quality: earliest, middle, and latest events among exact expiry matches.

| Event ID | Deribit expiry | Grid instruments | Best fresh-strike count | Best stale share | Passing event-days |
|---:|---|---:|---:|---:|---:|
| 25536 | 2025-06-06 08:00 UTC | 32 | 8 | 40.0% | 0 |
| 57016 | 2025-10-16 08:00 UTC | 44 | 5 | 0.0% | 0 |
| 211899 | 2026-02-23 08:00 UTC | 38 | 2 | 0.0% | 0 |

Aggregate probe evidence:

```text
grid instruments requested: 114
instrument not found: 72
instrument exists but no OHLC data: 17
instruments with OHLC: 25
instruments with at least one real trade: 21
OHLC rows inside the requested windows: 130
observable event-days: 13
event-days passing all frozen gates: 0
```

The closest case was event `25536`: one date reached eight fresh strikes, but its best stale share was `40.0%`, above the frozen `30%` ceiling. The other two expiries never reached eight fresh strikes. Calls and puts were observed on both sides on some dates, so failure is specifically cross-strike freshness/coverage rather than total API inaccessibility.

## Gate table

| Gate | Evidence | Result |
|---|---|---|
| Terminal event definition | 44 automated complete partitions; manual review status remains pending | Not completed |
| Candidate panel size | 44 automated candidates / 44 settlement timestamps; YES-history access unverified | Numerical threshold met, qualitative gate incomplete |
| Actual expiry metadata | 44 matched / 41 Deribit expiries | Pass |
| Contract units | Linear USDC convention verified | Pass |
| Time/reference mapping | PM timestamp, Deribit expiry, and signed gaps retained | Pass with proxy limitation |
| Historical OHLC existence | 25 instruments returned OHLC; 21 had real trades | Pass for existence only |
| Frozen full-curve quality | 0 / 13 observable event-days pass | **Fail** |
| Final sample threshold | Full panel not downloaded after the representative smoke failure | Not evaluated / early stop |

## Scope of the finding

This is an early-stop feasibility decision, not a claim that all 44 candidates were downloaded. The three events span three distinct exact expiries across the available history and were selected mechanically. The result is sufficient to stop further collection under the bounded feasibility budget, but it does not estimate the population-wide share of passing SOL event-days. The Polymarket manual-review and historical YES-price gates remain explicitly incomplete because the Deribit failure already supplies a stopping condition.

Daily OHLC can establish whether an instrument traded within a day, but it cannot reconstruct exact simultaneous cross-strike trade times. Polymarket resolves against Binance SOL/USDT while Deribit uses `sol_usdc`; that reference-basis mismatch would remain an explicit proxy limitation even if liquidity passed.

## Authorized next action

Do not build the SOL option-pricing adapter, RND estimator, Polymarket history panel, or P-versus-Q comparison under P3. Preserve the negative feasibility result as the documented external-validity boundary.

XRP is not automatically activated: the pre-specified backup rule permits XRP after a SOL failure caused by asset-specific Polymarket coverage, whereas the observed failure is Deribit cross-strike liquidity. Any XRP audit would require a new explicit scope decision rather than being used to search for a preferred result.

## Reproducible artifacts

```text
configs/p3_track_a_extension.json
data/processed/p3_sol/polymarket_feasibility_metadata.json
data/processed/p3_sol/deribit_contract_spec.json
data/processed/p3_sol/deribit_feasibility_metadata.json
data/processed/p3_sol/deribit_expiry_match.parquet
data/processed/p3_sol/deribit_ohlc_probe.parquet
data/processed/p3_sol/deribit_ohlc_instrument_diagnostics.parquet
data/processed/p3_sol/deribit_bar_quality.parquet
data/raw/p3_sol/deribit_ohlc_smoke_<cache_key>_manifest.json
```

The bulk CSV/Parquet and raw OHLC artifacts remain local and ignored by Git. Cache filenames are keyed to the selected grid, exact event windows, resolution, and request bound, so a changed probe cannot be mislabeled as a cache hit. The compact metadata, decision logic, tests, and this decision log are version-controlled.
