# P3 SOL Preliminary Feasibility Evidence

**Snapshot:** 2026-08-03 UTC<br>
**Git baseline:** `f546f6a012109641957786de5f69927155b9a497`<br>
**Label:** `SUPERSEDED by P3_SOL_FEASIBILITY_DECISION.md`

The later full-grid smoke probe did not clear the frozen curve-quality gate. This file is retained as the chronological preliminary record; the formal stopping decision is the source of truth.

## Scope

This was a bounded existence and architecture probe. It did not download full Polymarket token histories, build a complete Deribit strike grid, estimate a risk-neutral distribution, inspect P-versus-Q divergence, or activate XRP.

## Polymarket evidence

The probe queried `public-search` page 0 with a maximum of 100 results per term for:

```text
solana
sol price
solana price
what price will solana be
```

Observed counts after event-ID deduplication:

```text
unique events returned: 120
automatically identified complete terminal-price partitions: 50
complete partitions marked closed/resolved by the event response: 44
distinct end timestamps among those resolved partitions: 44
```

The complete candidates contain mutually exclusive cells such as `less than`, contiguous `between`, and `greater than` buckets. Separate `reach`, `hit`, `dip`, and Up/Down events were observed and are excluded as path-dependent or incompatible.

These automated counts exceed the numerical candidate-panel continuation threshold. They do not constitute a candidate-stage `PASS` until every candidate's resolution rule, settlement timestamp/reference, token IDs, partition structure, and historical YES-price availability are manually and programmatically audited.

## Deribit contract and instrument evidence

The current `currency=USDC, kind=option` response contained:

```text
all active USDC options: 2,306
active SOL options: 452
active SOL expiries: 6
SOL options returned by expired=true: 36
expired SOL expiries returned by the bulk endpoint: 1
```

The bulk expired endpoint therefore does not provide a full historical instrument inventory. However, `public/get_instrument` successfully returned archived metadata for `SOL_USDC-10OCT25-230-C`, including:

```text
state: archivized
instrument_type: linear
quote_currency: USDC
settlement_currency: USDC
contract_size: 10
price_index: sol_usdc
expiry: 2025-10-10 08:00 UTC
```

Official Deribit documentation and the observed API metadata agree that the quoted premium is USDC per SOL and one SOL option contract represents 10 SOL. The BTC/ETH coin-denominated pricing path is therefore not reusable.

## Historical OHLC probe

Six archived instruments around the 2025-10-10 expiry were probed from 2025-09-10 through expiry at daily resolution:

| Instrument | Bars | Positive-volume bars | Status |
|---|---:|---:|---|
| `SOL_USDC-10OCT25-190-C` | 0 | 0 | no_data |
| `SOL_USDC-10OCT25-190-P` | 11 | 7 | ok |
| `SOL_USDC-10OCT25-230-C` | 16 | 14 | ok |
| `SOL_USDC-10OCT25-230-P` | 8 | 5 | ok |
| `SOL_USDC-10OCT25-280-C` | 16 | 11 | ok |
| `SOL_USDC-10OCT25-280-P` | 0 | 0 | no_data |

This proves that archived SOL option OHLC can exist and include real volume. It also proves that instrument metadata alone is insufficient: two of six valid archived contracts returned no chart data, so the full event-day strike-quality gate remains necessary.

## Current assessment

SOL is a credible primary feasibility candidate because:

1. numerous resolved terminal-price partitions appear to exist on Polymarket;
2. Deribit has a large current SOL linear-USDC option universe;
3. archived per-instrument metadata is retrievable even when the bulk expired endpoint omits older expiries;
4. archived historical OHLC with positive volume is retrievable for at least some calls and puts;
5. the quotation, settlement, multiplier, expiry, index, and payoff convention can be documented in common units.

The extension is not yet authorized for estimation. The remaining blockers are full event inventory review, historical YES-token coverage, actual expiry matching for every candidate, full cross-strike OHLC coverage, time/reference-basis audit, and a pre-result USD/USDC fit-tolerance rule.

## Next authorized action

Build the complete SOL event/cell inventory and actual Deribit expiry-match table, then probe strike grids only for those candidate expiries. Issue the formal `PASS`, `LIMITED PASS`, or `FAIL` decision before implementing the option-pricing adapter or inspecting divergence estimates.

## Formal inventory checkpoint — 2026-08-03

The reproducible inventory pipeline subsequently confirmed:

```text
discovered events: 120
resolved complete terminal partitions with verified rules: 44
distinct Polymarket settlement timestamps: 44
candidate cell rows: 424
duplicate event, market, token, or event/cell keys: 0
missing YES token IDs: 0
finite bucket width for every candidate: USD 10
```

Rules text identifies all 44 candidate events as the Binance SOL/USDT 1-minute close at noon ET. Converting the written rules with the `America/New_York` timezone gives 22 settlements at 16:00 UTC and 22 at 17:00 UTC. This corrected one event whose API `endDate` was four hours earlier than its written settlement rule; the original `event_end_time` remains retained for audit.

Verified archived Deribit metadata matching produced:

```text
candidate events matched: 44 / 44
distinct actual Deribit expiries: 41
mapping quality exact: 39
mapping quality close: 3
mapping quality loose: 2
mapping quality unmappable: 0
verified SOL linear-USDC units: 44 / 44
metadata API requests: 150
```

Signed PM-settlement-minus-Deribit-expiry gaps were concentrated at `+8h` and `+9h`; two events had `+57h` loose matches. No single Deribit expiry dominates the candidate set: the largest supplies 3 of 44 events.

This clears the event-definition, candidate-count, expiry-metadata, contract-unit, and preliminary concentration checks. The formal feasibility decision remains unwritten because the historical OHLC/full-strike freshness gate has not yet been applied across the matched expiry sample. No estimator work is authorized at this checkpoint.
