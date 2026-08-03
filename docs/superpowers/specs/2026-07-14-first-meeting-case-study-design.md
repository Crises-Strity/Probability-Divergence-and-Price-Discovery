# First Meeting Case Study Design

## Purpose

Prepare a compact first-meeting presentation that demonstrates an end-to-end probability-distribution comparison without presenting the full P1 sample as a final empirical conclusion.

## Audience and framing

The audience is the project leader/supervisor. The presentation should establish feasibility, make the data construction transparent, and invite feedback on the comparison design. It must describe the evidence as a preliminary event-level case study rather than an arbitrage result, causal result, or general market-level conclusion.

## Primary case

- Polymarket event `21348`: **Bitcoin price on March 28?**
- Polymarket event end: `2025-03-28 00:00 UTC`
- Nearest Deribit expiry: `2025-03-28 08:00 UTC`
- Horizon gap: `-8 hours`
- Event partition: seven terminal markets forming a clean bucket distribution
- Main comparison date: `2025-03-25`
- Time to Deribit expiry on the comparison date: `72 hours`
- Observed normalized L1 divergence on that date: `0.219552383690131`

This event is selected because it already connects the P0 API spike to the P1 distribution pipeline, has exact event-to-expiry mapping under the project rules, and has seven valid daily comparisons from `2025-03-21` through `2025-03-27`.

## Backup case

- Polymarket event `86992`: **Ethereum price on November 28?**
- Exact event-to-expiry mapping under the project rules
- Horizon gap: `-8 hours`
- Seven valid daily comparisons

The backup case is used only to show that the pipeline is not BTC-specific. It should appear in an appendix or be held for questions, not compete with the primary case in the main narrative.

## Deliverables

1. A six-slide PowerPoint deck:
   - research question and two-track project framing;
   - minimal literature motivation;
   - P0 data/API acquisition and validation flow;
   - construction of Polymarket and Deribit probability distributions;
   - primary event distribution comparison and divergence path;
   - interpretation, limitations, and next step.
2. One appendix slide for the ETH backup case.
3. Concise speaker notes in Markdown, including a two-to-three-minute walkthrough and likely supervisor questions.
4. Editable native charts backed only by existing processed CSV/Parquet files, plus rendered slide previews for QA.

## Visual requirements

- Use a restrained academic style with white background, dark text, and distinct blue/orange market colors.
- Keep each slide to one main message.
- Use an editable native grouped bucket-probability chart for the primary date.
- Use an editable native seven-day L1 divergence line chart for the primary event.
- Clearly label the eight-hour expiry mismatch and the different settlement references.
- Do not display full-sample P1 headline estimates as if they were the meeting's central result.

## Interpretation constraints

- Polymarket probabilities and Deribit risk-neutral probabilities are not treated as identical structural objects.
- The comparison is descriptive and demonstrates feasibility.
- The horizon gap, settlement-reference mismatch, stale option bars, and option-curve model error must be stated.
- No fabricated values, backtest claims, causal claims, or directional price-discovery claims are permitted.

## Verification

- Every numeric value must be read from the existing processed data.
- Probability vectors must sum to one after the documented normalization/tail treatment, within floating-point tolerance.
- Figures must be checked against the source rows.
- The deck must be rendered to images and visually inspected for clipping, overlap, and readability.
