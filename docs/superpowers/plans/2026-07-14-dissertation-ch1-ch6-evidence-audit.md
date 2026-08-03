# Dissertation Chapters 1 and 6 Evidence-Locked Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Complete Chapters 1 and 6 and synchronise Chapters 2--5 and 7 with the frozen empirical evidence, implemented estimators, verified literature, and completed reference-basis audit.

**Architecture:** Preserve the existing chapter-per-file structure and standalone preambles. Treat generated tables, metadata, scripts, and the P1 freeze as the evidence layer; revise prose and selected figure inclusions without changing empirical outputs or pipeline code.

**Tech Stack:** LaTeX, BibTeX/natbib citation keys, existing PDF figures, shell-based static checks, and read-only Python/pandas verification.

## Global Constraints

- Code and LaTeX comments remain in English; handoff explanations are in Simplified Chinese.
- No fabricated result, p-value, confidence interval, or sample count.
- No Git commit, repository reorganisation, provenance regeneration, or pipeline rerun.
- Preserve the two-track design and existing chapter structure.
- Use three empirical RQs; tradability is an interpretation boundary, not a fourth answered RQ.
- Do not claim exact law-of-one-price comparability, causal horizon effects, executable arbitrage, or identified venue leadership.
- Keep the dissertation at approximately 10,000--15,000 words.
- Report successful LaTeX compilation only if a compiler is available and compilation succeeds.

---

### Task 1: Create the final evidence ledger

**Files:**
- Create: dissertation/evidence_audit.md
- Read: paper/tables/*.csv
- Read: data/processed/**/*.json
- Read: docs/decision_logs/P1_EMPIRICAL_FREEZE.md
- Read: scripts/P1_pipeline/*.py
- Read: scripts/P2_diagnostics/build_reference_basis_audit.py

**Produces:** A chapter-by-chapter ledger mapping retained numbers and claims to generated sources.

- [ ] **Step 1: Record every retained dissertation number**

List each Chapter 2--7 result number, its exact source file, table row or metadata field, and the dissertation sentence that uses it. Include the Track A funnel, smoothness grid, Track B coverage, six-hour diagnostics and regressions, and the 124-event reference audit.

- [ ] **Step 2: Record confirmed corrections**

Record these exact issues:

    Ch2: ng2025 is undefined; use ng2026. Replace four RQs with three.
    Ch3: objective notation must reflect squared row weights; six-hour blocks use last traded closes; frozen provenance predates repository initialisation.
    Ch4: the reference-basis audit is complete; all 124 events are proxy_assumed. Liquidity selection does not identify the direction of wedge bias.
    Ch5: remove untested coin-flip language and mechanism-confirmation wording.
    Ch7: delete the obsolete future reference-audit claim and avoid duplicating Chapter 6.

- [ ] **Step 3: Verify the ledger**

Run an rg scan for 294, 3114, 0.004022, 0.857979, 0.534829, 0.911992, and proxy_assumed across the ledger and source artifacts.

Expected: every headline value in the ledger has a matching generated source.

---

### Task 2: Correct Chapter 2 positioning and citations

**Files:**
- Modify: dissertation/ch2_literature_review_working.tex
- Verify: dissertation/references.bib

- [ ] **Step 1: Remove stale header comments and repair the citation**

Delete comments calling citation keys placeholders. Replace \citet{ng2025} with \citet{ng2026}.

- [ ] **Step 2: Replace the four-RQ positioning**

Use three rows:

    RQ1: full-distribution consistency across a broader BTC/ETH event panel.
    RQ2: intraday integration of a local near-the-money survival probability.
    RQ3: whether directional price discovery can be identified with the available data.

Move tradability into a paragraph explaining why a statistical wedge is not automatically executable.

- [ ] **Step 3: Align research-gap prose**

State that the dissertation extends pointwise parity to distributional comparison and tests frequency-bounded integration. Do not promise Hasbrouck/ILS results.

- [ ] **Step 4: Verify citation keys**

Run a regex scan over dissertation/*.tex and dissertation/references.bib.

Expected: used citation keys minus bibliography keys is empty.

---

### Task 3: Correct Chapters 3 and 4

**Files:**
- Modify: dissertation/ch3_methodology.tex
- Modify: dissertation/ch4_data.tex

- [ ] **Step 1: Correct the Track A objective**

Use row-weight notation consistent with least squares:

    \min_{\pi\ge0} \sum_i(a_i^\top\pi-y_i)^2
    +w_\Sigma^2(\mathbf{1}^\top\pi-1)^2
    +w_\mu^2((x/\widehat S)^\top\pi-1)^2
    +w_s^2\sum_k(\pi_k-2\pi_{k+1}+\pi_{k+2})^2.

Explain that reported smoothness settings refer to implemented row weight w_s.

- [ ] **Step 2: Correct six-hour aggregation**

State that each block retains fresh traded rows and takes the last traded close for each instrument. Do not describe this as price averaging; retain the within-block non-synchronicity caveat.

- [ ] **Step 3: Correct provenance wording**

Say the frozen artifacts were generated before repository initialisation and retain unavailable commit provenance. Do not regenerate them.

- [ ] **Step 4: Add the completed reference audit to Chapter 4**

Report 124 events (60 BTC, 64 ETH), resolution-text availability share 1.0, mismatch share 1.0, and proxy_assumed status for all events. State that this is not a sample gate.

- [ ] **Step 5: Correct liquidity-selection interpretation**

Retain medians 145844 and 531367 and ratio 3.6, but say only that the sample is selected toward more liquid events and the bias direction is unidentified.

- [ ] **Step 6: Recheck all Chapter 4 counts**

Compare Chapter 4 against the Polymarket, Deribit, Track A, and Track B metadata JSON files.

Expected: no count differs after stated rounding.

---

### Task 4: Correct Chapter 5 and insert figures

**Files:**
- Modify: dissertation/ch5_results.tex
- Read: paper/figures/fig_trackA_distribution_comparison_example.pdf
- Read: paper/figures/fig_trackA_curve_fit_quality.pdf
- Read: paper/figures/fig_trackA_spread_diff_by_gap.pdf

- [ ] **Step 1: Add figure paths**

After graphicx, add:

    \graphicspath{{../paper/figures/}{paper/figures/}}

- [ ] **Step 2: Insert the example distribution**

Place it after the Track A opening with label fig:trackA-example. Caption it as one illustrative event-day.

- [ ] **Step 3: Insert curve-fit quality**

Place it near fit-quality/sensitivity discussion with label fig:trackA-curve-quality. Describe the RMSE gate without claiming causal validation.

- [ ] **Step 4: Insert horizon-gap spread**

Place it in the horizon-gap subsection with label fig:trackA-spread-gap. Call it descriptive composition, not a maturity effect.

- [ ] **Step 5: Calibrate wording**

Apply these substantive changes:

    “indistinguishable from a coin flip” -> “close to one half; no formal test against one half is reported”
    “confirming that the recovered signal reflects reduced noise” -> “consistent with reduced measurement noise at the coarser frequency”
    “they price the same probability” -> “their local survival probabilities are strongly aligned but not identical”

Retain the frozen numbers and unidentified-leadership conclusion.

- [ ] **Step 6: Verify**

Check all three figure files exist and scan Chapter 5 for 0.000572, 0.8015, 0.0040, 0.535, 0.330, and -0.401.

Expected: files exist and numbers remain present.

---

### Task 5: Write Chapter 1

**Files:**
- Create: dissertation/ch1_introduction.tex

- [ ] **Step 1: Create the standalone shell**

Follow Chapters 3--7 with report, amsmath, booktabs, siunitx, graphicx, and hyperref. Use \chapter{Introduction} and \label{ch:introduction}.

- [ ] **Step 2: Write motivation and empirical problem**

Explain why the probabilities are economically comparable but not identical, including probability measure, horizon, settlement basis, and sparse option trading.

- [ ] **Step 3: State three RQs**

Use one enumerated item per RQ. Word RQ3 as an identification question so “not identified” is a valid result.

- [ ] **Step 4: Summarise both tracks**

Describe Track A daily full distributions and Track B local intraday survival. Distinguish eligible universes from passing samples.

- [ ] **Step 5: State verified findings and contributions**

Use only these rounded headline values:

    Track A: 294 event-days, 61 events, 3,114 cell-days.
    Centre: intercept 0.000572, p=0.8015.
    Tail relative divergence: 0.858 versus 0.571.
    Spread: 0.0040 baseline and 0.0008 under heaviest smoothing.
    Track B: level correlation 0.912 and six-hour change correlation 0.535.
    Directional leadership: unidentified.

- [ ] **Step 6: Add roadmap and check length**

Expected: approximately 1,200--1,500 words and no fourth empirical RQ.

---

### Task 6: Write Chapter 6 and de-duplicate Chapter 7

**Files:**
- Create: dissertation/ch6_discussion.tex
- Modify: dissertation/ch7_limitations.tex

- [ ] **Step 1: Create Chapter 6 shell**

Use the existing standalone preamble, \chapter{Discussion}, and \label{ch:discussion}.

- [ ] **Step 2: Interpret Track A**

Explain centre agreement versus shape disagreement, the stronger tail-relative result, and regularisation-dependent spread. Relate to Portnaya (2026), favourite--longshot evidence, and physical versus risk-neutral measures.

- [ ] **Step 3: Interpret Track B**

Explain frequency-bounded integration, sparse OHLC constraints, and why regression asymmetry under differential measurement error does not identify Polymarket leadership.

- [ ] **Step 4: Discuss alternatives and economic meaning**

Cover reference and horizon mismatch, participant/clientele and liquidity selection, generated-regressor uncertainty, and non-fungible payoffs. State that no execution-aware arbitrage test exists.

- [ ] **Step 5: State implications**

Prioritise better trade/quote data, exact settlement mapping, and alternative low-dimensional RND estimators over more complex models on the same OHLC data.

- [ ] **Step 6: Update Chapter 7**

Replace the obsolete audit paragraph and shorten passages that duplicate Chapter 6 while retaining limitations, future work, and conclusion.

- [ ] **Step 7: Check length and overlap**

Expected: Chapter 6 approximately 1,600--2,000 words and no near-duplicate paragraph across Chapters 5--7.

---

### Task 7: Final dissertation-wide verification

**Files:**
- Verify: dissertation/ch1_introduction.tex
- Verify: dissertation/ch2_literature_review_working.tex
- Verify: dissertation/ch3_methodology.tex
- Verify: dissertation/ch4_data.tex
- Verify: dissertation/ch5_results.tex
- Verify: dissertation/ch6_discussion.tex
- Verify: dissertation/ch7_limitations.tex
- Verify: dissertation/references.bib
- Verify: dissertation/evidence_audit.md

- [ ] **Step 1: Scan citations**

Expected: no used citation key is absent from references.bib.

- [ ] **Step 2: Scan labels and references**

Report duplicate labels and unresolved references. Cross-chapter refs must exist somewhere in the seven chapter files.

- [ ] **Step 3: Scan stale statements**

Search for ng2025, citation-key placeholder comments, future reference-basis audit, current-folder-not-Git wording, TBD, and TODO.

Expected: no live prose match and no obsolete submission comment.

- [ ] **Step 4: Verify headline numbers**

Use read-only Python/pandas checks for Track A sample/smoothness, Track B correlations/regressions, and reference audit.

Expected: text equals sources after rounding.

- [ ] **Step 5: Re-render inserted figures**

Render the three PDFs with Poppler and inspect clipping, labels, and caption consistency.

- [ ] **Step 6: Run available LaTeX validation**

Check for latexmk, pdflatex, or another compiler. Compile if available; otherwise run brace/environment balance checks and report compilation not executed.

- [ ] **Step 7: Check total word count and scope**

Expected: seven chapters approximately 10,000--15,000 words and exactly three empirical RQs.

- [ ] **Step 8: Complete the audit handoff**

Update dissertation/evidence_audit.md with corrected issues, verified numbers, inserted figures, verified unused figures, checks executed, and residual limitations.

Do not claim completion until every available check has fresh evidence.
