# Track A Meeting Update Design

## Purpose

Prepare the second supervisor-meeting presentation as a direct continuation of the prior one-event case study. The deck should show how the same validated distribution-comparison pipeline scales to the frozen Track A panel and should seek feedback on whether the Track A interpretation can be frozen.

## Audience and communication job

The audience is the project leader/supervisor. By the end of the presentation, the supervisor should understand that the one-event feasibility design has been applied consistently to a quality-gated panel, that the robust Track A findings concern center alignment and tail-relative divergence, and that the spread result must be stated as smoothing-conditional.

## Scope

- Cover Track A only.
- Mention P0 in one sentence as the completed feasibility stage before the case study.
- Use the prior BTC case only as a bridge, not as panel evidence.
- Preview Track B only on the closing slide.
- Do not present trading, arbitrage, causal maturity, or directional price-discovery claims.

## Deliverables

1. A PowerPoint deck with 10 main slides and 3 appendix slides.
2. A Markdown speaker-notes document.
3. Chart-ready source extracts generated from frozen local P1 tables and panels.
4. Rendered slide previews and QA outputs kept in external scratch space.

## Main-slide narrative

1. **Title:** Track A distribution divergence between Polymarket and Deribit.
2. **From case study to panel evidence:** one-sentence P0 closure, prior BTC feasibility case, and the new panel question.
3. **Sample funnel:** 79 events and 531 candidate event-days narrow to 61 events, 294 event-days, and 3,114 cell-day rows after quality gates.
4. **Panel comparison objects:** move from a single descriptive L1 distance to location, spread, and tail-relative measures; explain why L1 is secondary at panel level.
5. **Center alignment:** controlled location intercept `0.0005717472741070377`, event-clustered `p = 0.8015458060808593`; no robust bullish/bearish location shift.
6. **Tail-relative divergence:** tail relative absolute divergence mean `0.8579793181535111` versus body `0.5683060728305892`; raw absolute differences are similar, so the relative interpretation matters.
7. **Baseline spread result:** baseline PM-wider share `0.707483` and median PM-minus-Deribit spread difference `0.004022` in the frozen headline summary.
8. **Smoothness sensitivity:** on the common 293-event-day grid, PM-wider share moves from `0.9078498293515358` at smooth weight `0.00` to `0.5255972696245734` at `0.20`; the median spread difference falls from `0.009556196387606991` to `0.0008425785906285496`.
9. **Composition and horizon gaps:** spread variation is associated with horizon-gap categories, asset, and time to expiry; `R-squared = 0.468297794265668`; do not interpret coefficients as causal maturity effects.
10. **Track A conclusion:** centers align, tail-relative divergence remains material, and spread is smoothing-conditional. Preview Track B and request feedback before empirical freeze.

## Appendix

1. Sample and curve-quality gates.
2. L1/L2 shape-distance statistics and why they are secondary.
3. Tail-midpoint and state-grid-truncation robustness.

## Speaker-notes design

Each slide must include:

- **Must say:** one or two sentences sufficient to present the slide.
- **Optional detail:** supporting numerical or methodological context.
- **Likely question:** the most probable supervisor question and a concise answer.

The notes must include a short opening transition from the previous meeting and a closing sentence asking whether Track A can be treated as frozen subject to the later Track B discussion.

## Visual design

- Continue the restrained white-background academic style used in the first meeting deck.
- Use blue for Polymarket, orange for Deribit, and neutral gray for methodological context.
- Use editable native charts backed by frozen CSV values.
- Use takeaway-style slide titles.
- Avoid dense regression tables on main slides.
- Keep all body text at 16 points or above and all slide titles at 35 points or above.

## Data sources

- `paper/tables/tab_trackA_sample_funnel.csv`
- `paper/tables/tab_trackA_spread_regressions.csv`
- `paper/tables/tab_trackA_tail_relative_wedge.csv`
- `paper/tables/tab_trackA_smoothness_moment_grid.csv`
- `paper/tables/tab_trackA_divergence_overall.csv`
- `paper/tables/tab_trackA_tail_midpoint_robustness.csv`
- `paper/tables/tab_trackA_state_grid_truncation.csv`
- `data/processed/panels/trackA_diagnostics_summary.json`
- `docs/decision_logs/P1_EMPIRICAL_FREEZE.md`
- `docs/decision_logs/P1_PAPER_CONCLUSIONS.md`

## Interpretation constraints

- The prior case study establishes feasibility only.
- Center alignment is the robust location finding.
- Tail divergence is stated using relative or log-odds metrics, not raw tail probability alone.
- The spread wedge is conditional on RND smoothness.
- Horizon-gap coefficients are composition controls, not causal effects.
- L1/L2 magnitude is secondary because it is smoothness-sensitive.
- No result is described as an arbitrage opportunity.

## Verification

- Read every displayed value from frozen local outputs.
- Assert sample-funnel counts and chart arrays against the source files.
- Export a valid 13-slide PowerPoint file.
- Run overflow detection.
- Render every final slide and inspect each at full size.
- Confirm no placeholders, clipped titles, overlapping objects, or mismatched chart labels remain.
