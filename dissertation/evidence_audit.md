# Dissertation Evidence Audit

Audit date: 2026-07-14

## Scope and evidence order

This ledger covers the dissertation content review requested after the P1 empirical freeze. Evidence is ranked as follows:

1. paper-facing CSV tables and processed-panel metadata;
2. the scripts that generated the estimators, gates, tables, and figures;
3. P1 freeze and decision-log documents;
4. local source PDFs and current primary-source records for literature claims.

Git provenance regeneration and pipeline reruns are outside this audit.

## Confirmed corrections

| Chapter | Confirmed issue | Required correction |
|---|---|---|
| 2 | The text cites ng2025, but references.bib defines ng2026. | Use ng2026. |
| 2 | Four RQs promise a tradability result that the empirical work does not estimate. | Use three empirical RQs; discuss tradability as a boundary. |
| 3 | The displayed objective treats row weights as direct penalty coefficients, while least squares squares those row weights. | Write the objective with squared weights. |
| 3 | Frozen metadata says unavailable_not_git_repo although the folder is now a repository. | State that frozen artifacts predate repository initialisation. |
| 4 and 7 | The text says the reference-basis audit is incomplete. | Report the completed 124-event audit and proxy_assumed status. |
| 4 | Liquidity selection is called a lower-bound design without identification of the bias direction. | Report selection toward liquid events; leave bias direction unidentified. |
| 5 | The heavy-smoothing wider share is called indistinguishable from a coin flip without a formal test. | Say it is close to one half and no formal test is reported. |
| 5 | Coarser-frequency diagnostics are described as confirming a mechanism. | Use “consistent with reduced measurement noise”. |

## Chapter 2: literature numbers and citation facts

| Claim | Verified value | Evidence |
|---|---:|---|
| Le (2026) calibration sample | 292 million trades; 327,000 binary contracts | Local PDF: dissertation/literature_review/Decomposing Crowd Wisdom.pdf, abstract |
| Portnaya main BTC contract | n=214; mean gap 0.0558; t=6.46; HAC CI [0.0228, 0.0889] | Local PDF: Do Prediction Markets Match Option Prices..., Table 2 |
| Portnaya pooled Binance sample | n=287; mean gap 0.0633 | Same PDF, pooled table |
| Portnaya pooled Deribit sample | n=2,585; mean gap 0.1105 | Same PDF, Table 7 |
| Portnaya persistence | AR(1) half-life 4.2 hours | Same PDF, Table 2 |
| Portnaya arbitrage proxy | 16 trades; pooled net PnL 1.113; p=0.053 | Same PDF, Table 6 |
| Dubach microstructure archive | about 30 billion events over 52 days; 600-market panel | Local PDF: The Anatomy of a Decentralized Prediction Market..., abstract |
| Dubach direction agreement | about 59%; panel mean 0.615; 95% CI [0.58, 0.65] | Same PDF, abstract |
| Cheng NBA dataset | more than 75 million order-book snapshots; 173 games | Local PDF: Arbitrage Analysis in Polymarket NBA Markets.pdf, abstract |
| Gebele cross-platform dataset | over 100,000 events; ten venues; 2018--2025; average execution-aware deviations 2--4% | Local PDF: Semantic Non-Fungibility..., abstract |
| Ng paper date/key | first posted 2025; revised and dated April 2026; bibliography key ng2026 | Current SSRN record 5331995 and local PDF |
| Ng result | Polymarket leads Kalshi particularly when liquidity and trading activity are high | Current SSRN abstract and local PDF |

The 2026 arXiv claims for Portnaya and Dubach were also checked against their current arXiv abstract records on 2026-07-14.

## Chapter 3: implemented method and thresholds

| Method statement | Implemented source |
|---|---|
| Track A fits non-negative discrete state probabilities by bounded least squares | scripts/P1_pipeline/build_trackA_deribit_rnd_panel.py: fit_state_probabilities |
| Sum, mean, and smoothness rows are multiplied by row weights before least squares | Same function; displayed objective must use squared weights |
| Baseline smoothness row weight is 0.10; sensitivity grid includes 0.00, 0.05, 0.10, and 0.20 | scripts/P1_pipeline/build_trackA_regression_diagnostics.py |
| Track A curve-input gate uses stale share <=0.30 and at least 8 fresh strikes | trackA_daily_quality_metadata.json and tab_trackA_sample_funnel.csv |
| Moment open-tail baseline is half a median finite bucket width; robustness uses one full width | build_trackA_deribit_rnd_panel.py and build_trackA_regression_diagnostics.py |
| Track B informative interval is strictly (0.05, 0.95) | build_trackB_pm_survival_panel.py and build_trackB_deribit_survival_panel.py |
| Six-hour Deribit blocks retain traded rows and use each instrument's last traded close in the block | build_trackB_deribit_survival_panel.py: aggregate_to_blocks |
| Six-hour PM blocks use the final hourly observation in the block and require at least one real update | build_trackB_lead_lag_panel.py: aggregate_pm_to_blocks |
| Lead-lag regressions use event fixed effects and event-clustered standard errors | build_trackB_lead_lag_diagnostics.py |
| Regression p-values are asymptotic cluster-robust; wild-cluster bootstrap is not implemented | trackB_lead_lag_diagnostics_summary.json, known_caveats |

## Chapter 4: data and sample numbers

### Canonical event universe

| Quantity | Value | Source |
|---|---:|---|
| Events | 124 | p1_event_cells_metadata.json |
| BTC / ETH events | 60 / 64 | tab_reference_basis_audit_summary.csv |
| Track A bucket-distribution events | 79 | p1_event_cells_metadata.json |
| Point-threshold events | 45 | p1_event_cells_metadata.json |
| Event cells | 1,338 | p1_event_cells_metadata.json |
| Interior / point-threshold / left-tail / right-tail cells | 687 / 493 / 79 / 79 | event_cells.parquet; counts sum to 1,338 |
| Missing YES token identifiers | 0 | p1_event_cells_metadata.json |

### Polymarket and Deribit panels

| Quantity | Value | Source |
|---|---:|---|
| Raw Polymarket history rows | 191,479 | polymarket_history_metadata.json |
| Polymarket hourly / daily distribution rows | 122,923 / 5,677 | polymarket_history_metadata.json |
| Track A PM quality: pass / borderline / fail events | 67 / 8 / 4 | polymarket_quality_diagnostics.parquet |
| Daily Deribit OHLC rows / event-day quality rows | 25,315 / 675 | deribit_ohlc_metadata.json |
| Median distinct daily traded strikes | 17 | deribit_bar_quality.parquet, direct calculation |
| Zero-strike event-days | 79; one for each event; no event-day has 1--9 strikes | deribit_bar_quality.parquet, direct calculation |
| Hourly Deribit OHLC rows / quality bars | 491,531 / 13,119 | deribit_ohlc_metadata_60.json |

### Track A funnel and matching

| Stage | Event-days | Events | Source |
|---|---:|---:|---|
| Joinable event-days | 531 | 79 | tab_trackA_sample_funnel.csv |
| Legacy PM plus Deribit min-8 gate | 406 | 67 | same |
| Curve-input gate | 301 | 61 | same |
| Curve-fit success | 301 | 61 | same |
| Curve-quality pass | 294 | 61 | same |
| Final cell-day rows | 3,114 | -- | same |

Additional verified quantities:

- The staleness gate removes 105 of 406 event-days.
- The curve-quality gate removes 7 fitted event-days.
- Signed gaps are -32, -8, +16, and +40 hours.
- Absolute gap range is 8--40 hours and median absolute gap is 32 hours.
- The six PM-main events removed entirely before curve fitting have median Polymarket event volume 145,844.450294, versus 531,366.668111 for the 61 surviving events; ratio 3.6434. This identifies liquidity selection, not the direction of bias in the wedge.

### Track B

| Quantity | Value | Source |
|---|---:|---|
| K-star available | 124/124 events | trackB_kstar_metadata.json |
| Bucket initial survival median / distance to 0.5 | 0.490063 / 0.044450 | same |
| Point-threshold distance to 0.5 | 0.265 | same |
| PM survival rows / pass-quality rows | 18,225 / 16,700 | trackB_pm_survival_metadata.json |
| Bucket / point pass-quality saturated share | 0.089856 / 0.421044 | same |
| Bucket events with at least 72 informative hours | 73/79 | tab_trackB_pm_informative_event_summary.csv |
| Point events with at least 72 informative hours / none | 25/45 / 4/45 | same |
| Hourly Deribit pass / informative bars | 4,913 / 4,168 of 13,119 | trackB_deribit_survival_metadata.json |
| Hourly joint-informative rows | 2,973 | trackB_lead_lag_panel_metadata.json |
| Hourly events with at least 72 joint hours | 2 | same |
| Hourly median longest run / events with 24-hour run | 6 hours / 0 | direct frozen metadata/table |
| Six-hour Deribit pass / informative bars | 1,821 / 1,569 of 2,226 | trackB_deribit_survival_metadata_6h.json |
| Six-hour joint-informative rows | 1,121 | trackB_lead_lag_panel_metadata_6h.json |
| Six-hour change pairs / events | 889 / 78 | tab_trackB_frequency_diagnostics_6h.csv and cross-correlation table |

A direct 2026-07-14 panel check confirmed that all 889 reported current change pairs span exactly six hours.

### Completed reference-basis audit

| Asset | Events | Track A eligible | Track B eligible | Text available share | Mismatch share | Status |
|---|---:|---:|---:|---:|---:|---|
| BTC | 60 | 39 | 60 | 1.0 | 1.0 | proxy_assumed |
| ETH | 64 | 40 | 64 | 1.0 | 1.0 | proxy_assumed |

Source: paper/tables/tab_reference_basis_audit_summary.csv and reference_basis_audit_metadata.json. This audit is textual/provenance evidence and is not an empirical sample gate.

## Chapter 5: result numbers

### Track A

| Result | Value | Source |
|---|---:|---|
| Final sample | 294 event-days; 61 events; 3,114 cell-days | tab_trackA_sample_funnel.csv |
| Location regression intercept / p-value / R-squared | 0.000572 / 0.801546 / 0.011 approximately | tab_trackA_spread_regressions.csv, location_continuous_tte rows |
| Baseline PM / Deribit spread medians | 0.051511 / 0.045570 | tab_trackA_tail_midpoint_robustness.csv |
| Baseline median spread difference / PM-wider share | 0.004022 / 0.707483 | same |
| Common smoothness sample | 293 event-days; 61 events | tab_trackA_smoothness_moment_grid.csv |
| Smoothness 0.00: RMSE / wider share / median spread difference | 0.005925 / 0.907850 / 0.009556 | smoothness tables |
| Smoothness 0.05 | 0.006166 / 0.812287 / 0.006791 | same |
| Smoothness 0.10 common sample | 0.006351 / 0.706485 / 0.003968 | same |
| Smoothness 0.20 | 0.006669 / 0.525597 / 0.000843 | same |
| Edge probability median / days above 5% | 0.001388 / 1 of 294 | tab_trackA_state_grid_truncation.csv |
| Tail/body mean absolute divergence | 0.026924 / 0.027306 | tab_trackA_tail_relative_wedge.csv |
| Tail/body mean relative absolute divergence | 0.857979 / 0.568306 in cell table; 0.570604 in event-day headline aggregation | tail table and diagnostics metadata |
| Tail/body median log-odds divergence | 1.424039 / 0.004185 | tab_trackA_tail_relative_wedge.csv |
| Median L1 / L2 | 0.235481 / 0.090428 | tab_trackA_divergence_overall.csv |
| Unsmoothed common-sample median L1 | 0.885704 | tab_trackA_smoothness_moment_grid.csv |
| Gap coefficients (-32h, +16h, +40h) | -0.004105 / 0.006737 / 0.009367 | tab_trackA_spread_regressions.csv |
| ETH / TTE-day coefficients | 0.005407 / 0.001126 | same |
| Spread regression R-squared | 0.468298 | same |
| Partial Spearman after asset/TTE controls | 0.653329 | tab_trackA_partial_spearman.csv |

The dissertation must distinguish the body relative-divergence aggregation used: the tail-relative paper table reports 0.568306 across cell rows, whereas the event-day headline metadata reports 0.570604 after event-day aggregation. Chapter 5 currently uses the cell-table value 0.568 and is internally consistent with its accompanying tail-table quantities.

### Track B

| Result | Value | Source |
|---|---:|---|
| Six-hour level correlation | 0.911992 | P1 freeze; recomputable from lead_lag_survival_panel_6h.parquet |
| Six-hour median absolute wedge | 0.049052 | P1 freeze; row-level informative sample |
| Six-hour contemporaneous change correlation | 0.534829 | tab_trackB_cross_correlation_6h.csv |
| Change pairs / events | 889 / 78 | same |
| Deribit/PM change standard-deviation ratio | 1.592076 | tab_trackB_frequency_diagnostics_6h.csv |
| Deribit lag-1 autocorrelation | -0.248387 | same |
| Deribit-leading / PM-leading six-hour correlations | 0.073590 / 0.025272 | tab_trackB_cross_correlation_6h.csv |
| Deribit lag to PM coefficient / p-value | 0.057729 / 0.061500 | tab_trackB_pooled_lead_lag_6h.csv |
| PM lag to Deribit coefficient / p-value | 0.329746 / 0.0000527 | same |
| Deribit own lag coefficient / p-value | -0.400558 / 3.09e-28 | same |
| Regression sample | 703 rows; 77 events | same and diagnostics metadata |

The event-clustered regression p-values are descriptive because no wild-cluster bootstrap was implemented. The asymmetric coefficients do not identify venue leadership.

## Figures

All eight paper-facing PDFs were rendered to PNG and visually inspected. Each rendered paper figure is pixel-identical to its counterpart in result/P1_main_results/figures; binary PDF differences are non-visual.

| Figure | Data/method source | Main-text status |
|---|---|---|
| fig_trackA_distribution_comparison_example.pdf | build_trackA_diagnostics.py; daily_distribution_comparison.parquet | Inserted as an illustrative event-day |
| fig_trackA_curve_fit_quality.pdf | build_trackA_diagnostics.py; deribit_curve_fits.parquet | Inserted as fit-quality diagnostic |
| fig_trackA_spread_diff_by_gap.pdf | build_trackA_diagnostics.py; Track A event-day divergence | Inserted as descriptive composition |
| fig_trackA_cell_divergence_by_type.pdf | same diagnostics script | Verified; supporting only |
| fig_trackA_l1_by_gap.pdf | same | Verified; supporting only |
| fig_trackA_l1_distribution.pdf | same | Verified; supporting only |
| fig_trackA_l1_vs_staleness.pdf | same | Verified; supporting only |
| fig_trackA_spread_diff_vs_tte.pdf | same | Verified; supporting only |

## Chapter 7 repetitions

Chapter 7 result numbers repeat the verified Chapter 4/5 values: 8--40 hour mismatch, 61 Track A events, 79 Track B bucket events, and 124 canonical events. The substantive correction is not numerical: the reference audit is complete and shows systematic proxy rather than exact basis matching.

## Final verification status

- Chapters 1 and 6 have been added; Chapters 2--5 and 7 have been synchronously corrected against this ledger.
- Existing Chapter 4 and Chapter 5 empirical counts match the current generated outputs at their stated rounding. Direct recomputation from the frozen Track B panel gives level correlation 0.9119924351 and median absolute wedge 0.0490518937; these agree with the reported six-decimal values.
- The Chapter 2 external quantitative claims listed above match the local source PDFs and the checked primary-source records.
- Citation resolution found no missing bibliography keys after replacing `ng2025` with `ng2026`; label and cross-reference scans found no duplicate labels or unresolved references.
- Environment and brace-balance checks passed for all seven chapter files. No stale `TODO`, placeholder, fourth research question, incomplete-audit, or unsupported coin-flip wording remains.
- All eight paper-facing PDFs were rendered and visually inspected. The three figures inserted into Chapter 5 were rendered again after insertion; their text, axes, legends, and margins are legible and unclipped.
- A normalized comparison of 69 substantive paragraphs across Chapters 5--7 found no cross-chapter pair with similarity at or above 0.80.
- The approximate plain-text total across Chapters 1--7 is 13,111 words under the final reproducible LaTeX-stripping count, within the stated 10,000--15,000-word dissertation range.
- No LaTeX engine (`latexmk`, `pdflatex`, `xelatex`, `lualatex`, or `tectonic`) is installed in the current environment, so a full compilation was not executed. Static checks do not replace compilation and remain the principal residual verification limitation.
- Git provenance regeneration and end-to-end pipeline reruns remain outside scope, as requested. Regression inference still uses asymptotic event-clustered standard errors; no wild-cluster bootstrap was retrofitted.
