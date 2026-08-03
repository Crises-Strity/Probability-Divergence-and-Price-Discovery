# Dissertation Chapters 1 and 6 Evidence-Locked Revision Design

## Objective

Complete the dissertation's Introduction (Chapter 1) and Discussion (Chapter 6), while synchronising Chapters 2--5 and 7 with the frozen empirical outputs, current pipeline methods, and completed reference-basis audit.

This revision covers dissertation content only. Git provenance regeneration, repository engineering, and reproducibility reruns are explicitly outside the present scope.

## Evidence Hierarchy

Claims will be checked in the following order:

1. Generated paper-facing CSV tables and metadata under `paper/tables/` and `data/processed/`.
2. The scripts under `scripts/P1_pipeline/` and `scripts/P2_diagnostics/` that define the estimators, gates, figures, and regressions.
3. The frozen interpretation in `docs/decision_logs/P1_EMPIRICAL_FREEZE.md` and `docs/decision_logs/P1_PAPER_CONCLUSIONS.md`.
4. Local source PDFs and current primary-source records for literature claims.

No numerical result will be introduced unless it is present in, or independently recomputable from, these sources.

## Research Questions

The dissertation will use three empirical research questions:

1. Do Polymarket and Deribit imply consistent full terminal-price distributions for matched BTC and ETH events?
2. Are near-the-money survival probabilities integrated across the two venues at an observable intraday frequency?
3. Can the available data identify which venue leads price discovery?

Tradability will not be presented as a fourth answered research question. It will be discussed as an economic interpretation and scope boundary because the project does not contain an execution-aware trading test.

## Chapter 1: Introduction

Target length: approximately 1,200--1,500 words.

The chapter will contain:

- motivation for comparing prediction-market probabilities with option-implied state prices;
- the empirical problem created by different probability measures, settlement references, and market microstructure;
- the three research questions;
- a concise description of Track A and Track B;
- the verified findings: centre alignment, material tail-relative divergence, a smoothing-conditional width wedge, six-hour level/change integration, and unidentified directional leadership;
- contributions relative to the nearest literature, especially Portnaya (2026);
- a chapter roadmap.

The introduction will not claim exact law-of-one-price comparability, arbitrage profits, causal horizon effects, or a venue-leadership ranking.

## Chapter 6: Discussion

Target length: approximately 1,600--2,000 words.

The chapter will interpret rather than repeat Chapter 5. It will cover:

- why centre agreement and shape disagreement can coexist;
- why the tail-relative wedge is more stable than the spread magnitude;
- why the width result is conditional on risk-neutral-density regularisation;
- how the results relate to favourite--longshot bias, risk-neutral versus event-market probabilities, market segmentation, and Portnaya (2026);
- why six-hour co-movement supports frequency-bounded integration but not directional price discovery;
- alternative explanations, including reference-basis mismatch, horizon mismatch, sparse Deribit option trading, generated-regressor uncertainty, and participant/liquidity differences;
- why a statistical wedge is not an executable arbitrage;
- implications for future data collection and research design.

Chapter 6 will not duplicate Chapter 7's catalogue of limitations. Chapter 6 explains the findings; Chapter 7 states the boundaries, future work, and final conclusion.

## Synchronised Corrections to Existing Chapters

### Chapter 2

- Replace the undefined citation key `ng2025` with `ng2026`.
- Replace the four-RQ positioning with the final three-RQ structure.
- Treat tradability as an interpretation boundary rather than an empirically answered RQ.
- Remove stale comments describing citation keys as placeholders.

### Chapter 3

- Align the weighted least-squares notation with the implemented row weights, whose contributions enter the squared objective.
- Describe six-hour construction as using the last traded close per instrument within each block, not as price averaging.
- State that the frozen artifacts predate repository initialisation rather than claiming that the current folder is not a Git repository.
- Preserve the existing two-track estimator structure.

### Chapter 4

- Incorporate the completed 124-event reference-basis audit: resolution text is available, and every event is classified as `proxy_assumed` because the Polymarket and Deribit reference bases differ.
- Retain all verified row counts and sample-funnel numbers.
- Replace the unsupported claim that liquidity selection makes the measured wedge a lower bound with the identified conclusion: the final sample is selected toward more liquid events, while the direction of bias in the wedge is not identified.

### Chapter 5

- Retain numerical results that match the frozen outputs.
- Replace unsupported inferential wording such as "indistinguishable from a coin flip" when no corresponding formal test is reported.
- Avoid language implying that weaker autocorrelation proves a specific mechanism.
- Insert three verified figures: the example distribution comparison, curve-fit quality diagnostic, and spread difference by horizon gap.
- Keep L1, staleness, and other exploratory figures outside the main text because their quantities are secondary or conditional.

### Chapter 7

- Replace the obsolete statement that the reference-basis audit remains to be completed.
- Report the audit as evidence of a systematic proxy comparison, not an exact reference match.
- Remove duplication with Chapter 6 while retaining limitations, future work, and conclusion.

## Figure Audit and Use

All eight PDFs in `paper/figures/` have been rendered and visually inspected. Their rendered pixels match the corresponding PDFs in `result/P1_main_results/figures/`; the binary PDF files differ only in non-visual metadata/encoding.

Main-text figures:

1. `fig_trackA_distribution_comparison_example.pdf` -- intuitive example of the common-grid comparison.
2. `fig_trackA_curve_fit_quality.pdf` -- transparent presentation of the curve-quality gate.
3. `fig_trackA_spread_diff_by_gap.pdf` -- visual support for the non-causal horizon-gap composition result.

The other five verified figures remain valid supporting artifacts but will not be inserted merely to increase figure count.

## Validation

The completed revision will be checked by:

- mapping every dissertation result number to a paper table, metadata field, or direct panel calculation;
- scanning all citation keys against `references.bib`;
- scanning labels and references for missing or duplicate identifiers;
- verifying that inserted figure paths exist and that captions do not overstate the plotted evidence;
- checking for stale placeholders and obsolete project-status statements;
- performing LaTeX static checks available in the environment.

No successful LaTeX compilation will be claimed unless a compiler is available and the full document actually compiles. The current environment does not expose `latexmk` or `pdflatex`.

## Deliverables

- `dissertation/ch1_introduction.tex`
- `dissertation/ch6_discussion.tex`
- synchronised corrections to Chapters 2--5 and 7
- a concise audit summary identifying corrected issues, verified figures, and any remaining limitations

