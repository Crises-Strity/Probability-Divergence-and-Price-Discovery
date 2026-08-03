# Track B and Empirical Project Wrap-up Design

## Objective

Prepare the Friday supervisor meeting materials that:

1. briefly close the cancelled Track A meeting by summarizing its full-panel results;
2. present Track B through a concise question-method-difficulty-solution-result chain;
3. synthesize the two tracks into project-level conclusions;
4. state that the empirical project is complete unless specific supervisor feedback requires revision.

The deck is a results-focused project wrap-up, not a full technical reconstruction of the pipeline.

## Audience Outcome

By the end of the meeting, the leader should understand that:

- Track A and Track B are both empirically complete;
- the two markets are integrated around the center and at 6h frequency;
- divergence remains material in tails and, conditionally, in distribution width;
- directional price-discovery ranking is not identified with the available Deribit OHLC data;
- the project should now move to dissertation writing, reproducibility, and final presentation of results.

## Deliverables

Create the following files under `meeting_materials/2026.7.31 meeting/`:

- `track_b_project_wrapup.pptx`
- `track_b_project_wrapup_leader_brief_en.md`
- `track_b_project_wrapup_meeting_notes_zh.md`
- `source_data/track_b_project_wrapup_data.json`

The files remain local meeting materials and are not committed to the project repository.

## Visual Direction

Use the previous Track A deck as the visual reference:

- white academic background;
- dark neutral typography;
- Polymarket blue;
- Deribit orange;
- green for supported findings;
- amber or red only for qualifications and identification limits;
- editable PowerPoint charts, tables, and text;
- no decorative imagery or marketing-style composition.

The Track B deck must look like the continuation and conclusion of the Track A presentation.

## Main Deck

### Slide 1 - Track B and Empirical Project Wrap-up

Minimal title slide.

Supporting line:

```text
Local survival integration, frequency limits, and the final cross-track conclusion
```

### Slide 2 - The empirical project now covers both divergence and integration

Brief status sequence:

```text
P0 feasibility -> one-event case -> full Track A -> Track B complete
```

Purpose:

- acknowledge the cancelled Track A meeting;
- show that Track A was expanded from the case study to the full sample;
- establish that the Friday meeting completes the empirical evidence chain.

### Slide 3 - Track A is complete on the full panel

Show:

- 61 events;
- 294 event-days;
- 3,114 cell-day rows.

Frozen conclusions:

- center aligned;
- tail-relative divergence material;
- Polymarket spread wedge present under low-to-moderate smoothing but attenuated under heavy smoothing.

Do not repeat the full Track A methodology or robustness section.

### Slide 4 - Track B tests whether either market incorporates information first

Briefly explain:

- select a local threshold `K*`;
- construct Polymarket and Deribit survival probabilities `P(S_T > K*)`;
- align observations by time;
- compare levels and probability changes.

Primary sample:

- bucket-distribution events only;
- point-threshold events remain an appendix limitation because of saturation.

### Slide 5 - The hourly attempt revealed a measurement problem

Show:

- hourly level correlation: 0.900819;
- hourly change correlation: 0.040374;
- Deribit/PM change standard-deviation ratio: 2.728357;
- Deribit change lag-1 autocorrelation: -0.449059.

Interpretation:

```text
Hourly levels agree, but hourly Deribit changes are dominated by sparse-trade and OHLC measurement noise.
```

This slide combines the initial attempt, observed difficulty, and diagnosis.

### Slide 6 - Six-hour aggregation improves the usable signal

Explain the adjustment:

- aggregate traded hourly observations into 6h blocks;
- retain explicit freshness, bracketing-strike, and joint-informative gates;
- reduce, but do not eliminate, Deribit microstructure noise.

Show:

- 79 events;
- 1,121 joint informative rows;
- 889 change pairs;
- 703 regression rows from 77 events;
- median longest joint-informative run: 48h.

### Slide 7 - At 6h, the two markets are strongly integrated

Show:

- level correlation: 0.911992;
- median absolute survival wedge: 0.049052;
- median signed PM minus Deribit wedge: -0.010667;
- contemporaneous change correlation: 0.534829.

Interpretation:

```text
The markets are strongly aligned in levels and co-move materially at 6h frequency.
```

### Slide 8 - Directional price discovery remains unidentified

Primary visual: symmetric 6h cross-correlation.

Show:

- Deribit leads PM by 6h: 0.073590;
- contemporaneous: 0.534829;
- PM leads Deribit by 6h: 0.025272;
- both 12h lead correlations also remain below 0.08 in absolute magnitude.

Brief qualification:

- pooled regression asymmetry does not establish Polymarket leadership;
- noisier, negatively autocorrelated Deribit changes create errors-in-variables asymmetry.

Detailed regression coefficients remain in the appendix.

### Slide 9 - Track B supports integration, not a leadership ranking

Use four explicit statements:

- level convergence: supported;
- 6h contemporaneous co-movement: supported;
- directional price-discovery ranking: unidentified;
- sub-6h leadership: not measurable with current Deribit OHLC liquidity.

### Slide 10 - The two tracks produce a stronger project-level conclusion

New cross-track synthesis:

1. divergence and integration coexist;
2. agreement is strongest at the distribution center and in survival levels;
3. disagreement is concentrated in tails, smoothing-conditional width, and high-frequency measurement;
4. the evidence is consistent with probability-measure, tail-risk, and market-structure wedges;
5. the evidence does not support arbitrage or one-sided leadership;
6. additional modelling cannot replace unavailable historical order-book and exact trade-timestamp data.

### Slide 11 - The empirical project is complete

Use the active completion statement:

```text
The empirical project is complete. Unless specific feedback requires revision,
the next phase will focus on dissertation writing, reproducibility, and final
presentation of results.
```

Next phase:

- write the empirical results and limitations chapters;
- organize the Git repository and reproducibility instructions;
- finalize dissertation figures and tables;
- reopen empirical analysis only for a specific identification or validation concern.

## Appendix

### Slide 12 - Point-threshold events are excluded from the primary sample

Show:

- pass-quality saturated share: 0.421044;
- informative hours: 3,129;
- events with at least 72 informative hours: 25 / 45;
- events with zero informative hours: 4 / 45.

### Slide 13 - Regression asymmetry is not evidence of Polymarket leadership

Show:

- Deribit lag to PM change: coefficient 0.057729, p = 0.061500;
- PM lag to Deribit change: coefficient 0.329746, p = 0.000053;
- Deribit own lag: coefficient -0.400558.

Explain the errors-in-variables interpretation and point back to the symmetric cross-correlation.

### Slide 14 - Data limitations define the identification boundary

Show:

- no historical Deribit order book;
- OHLC bars do not expose exact last-trade timestamps;
- sparse bracketing strikes at 1h;
- settlement-reference and horizon mismatch;
- Track A RND smoothing sensitivity;
- sub-6h directional price discovery is not identifiable.

## English Leader Brief

`track_b_project_wrapup_leader_brief_en.md` is written for the leader and can be sent with the deck.

For every slide, include:

- what the slide presents;
- why the evidence is included;
- the appropriate interpretation;
- the main limitation;
- a `[Sources]` block pointing to frozen local outputs.

It is an explanatory document, not a speaking script.

## Chinese Meeting Notes

`track_b_project_wrapup_meeting_notes_zh.md` is written for the presenter.

For every slide, include:

- the main speaking objective;
- the order in which to explain the slide;
- numbers that must be mentioned;
- details that may be skipped;
- transition to the next slide;
- likely supervisor question and a concise response.

The Chinese file must remain separate from the English leader document.

## Sources of Truth

Use only frozen local outputs:

- `docs/decision_logs/P1_EMPIRICAL_FREEZE.md`
- `docs/decision_logs/P1_PAPER_CONCLUSIONS.md`
- `data/processed/panels/trackA_diagnostics_summary.json`
- `data/processed/panels/trackA_regression_diagnostics_summary.json`
- `data/processed/panels/trackB_pm_survival_metadata.json`
- `data/processed/panels/trackB_deribit_survival_metadata.json`
- `data/processed/panels/trackB_deribit_survival_metadata_6h.json`
- `data/processed/panels/trackB_lead_lag_panel_metadata.json`
- `data/processed/panels/trackB_lead_lag_panel_metadata_6h.json`
- `data/processed/panels/trackB_lead_lag_diagnostics_summary.json`
- relevant frozen CSV tables under `paper/tables/`

No result may be reconstructed from memory or manually invented.

## Verification

- assert every displayed number against the frozen outputs;
- export a 14-slide editable PPTX;
- run the PowerPoint overflow test;
- validate the PPTX archive and slide count;
- render all slides independently;
- inspect every slide at full size;
- scan both note files for missing slide sections, placeholders, and unsupported claims.
