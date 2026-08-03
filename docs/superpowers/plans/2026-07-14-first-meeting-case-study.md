# First Meeting Case Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a concise, evidence-backed first-meeting deck and speaker notes around one BTC case, with one ETH backup case.

**Architecture:** A data-extraction step will read the frozen processed panels and validate selected event-day rows. A plain JavaScript ES module using `@oai/artifact-tool` will create editable native charts and assemble the PowerPoint deck. A separate Markdown file will hold the talk track and anticipated questions. Generated artifacts stay under `meeting_materials/` and are not added to the project-only GitHub scope.

**Tech Stack:** Python 3.11+, pandas, matplotlib, bundled presentation runtime, PowerPoint `.pptx`, Markdown.

## Global Constraints

- Use event `21348` on `2025-03-25` as the primary snapshot.
- Use event `86992` only as the ETH backup case.
- Read all values from existing processed files; never type empirical values from memory.
- Describe results as preliminary and descriptive.
- Explicitly disclose the horizon gap and reference-basis mismatch.
- Render and visually inspect the completed deck.

---

### Task 1: Validate and extract the two cases

**Files:**
- Read: `data/processed/panels/daily_distribution_comparison.csv`
- Read: `data/processed/panels/trackA_event_day_divergence.csv`
- Read: `data/processed/polymarket/event_universe.csv`
- Create: `meeting_materials/source_data/primary_case_cells.csv`
- Create: `meeting_materials/source_data/primary_case_daily_divergence.csv`
- Create: `meeting_materials/source_data/backup_case_cells.csv`

- [ ] Filter event `21348`, date `2025-03-25`, and the main Track A quality gate.
- [ ] Assert that normalized Polymarket and Deribit cell probabilities each sum to one within `1e-8`.
- [ ] Extract all valid daily divergence rows for event `21348` and assert there are seven dates.
- [ ] Select the event `86992` day closest to that event's median valid L1 divergence and extract its cells.
- [ ] Save the three UTF-8-SIG CSV extracts and record their row counts.

### Task 2: Prepare chart-ready data

**Files:**
- Read: `meeting_materials/source_data/primary_case_cells.csv`
- Read: `meeting_materials/source_data/primary_case_daily_divergence.csv`
- Read: `meeting_materials/source_data/backup_case_cells.csv`

- [ ] Convert cell boundaries into explicit human-readable bucket labels.
- [ ] Preserve the seven chronological BTC dates and normalized-L1 values.
- [ ] Preserve the ETH backup probability vectors with the same market ordering.
- [ ] Check all chart labels, dates, and empirical values against the extracted CSVs.

### Task 3: Build the presentation

**Files:**
- Create in external scratch: `build_first_meeting_deck.mjs`
- Create: `meeting_materials/first_meeting_case_study.pptx`

- [ ] Build six main slides following the approved narrative with `@oai/artifact-tool` and Codex Grid layout references.
- [ ] Add one appendix slide for the ETH backup case.
- [ ] Use editable native charts for both probability comparisons and the L1 path.
- [ ] Add source footers pointing to the local processed-data filenames.
- [ ] Keep empirical interpretation limited to feasibility and descriptive divergence.

### Task 4: Write the talk track

**Files:**
- Create: `meeting_materials/first_meeting_speaker_notes.md`

- [ ] Write a two-to-three-minute slide-by-slide walkthrough.
- [ ] Include concise answers for probability-measure mismatch, expiry mismatch, settlement basis, stale bars, and event-selection questions.
- [ ] Include the proposed next step: repeat the same validated comparison on the wider event panel after supervisor feedback.

### Task 5: Verify the package

**Files:**
- Verify: `meeting_materials/first_meeting_case_study.pptx`
- Verify: `meeting_materials/first_meeting_speaker_notes.md`

- [ ] Render every slide to PNG.
- [ ] Inspect all rendered slides for clipping, overlap, unreadable labels, and visual consistency.
- [ ] Re-open the PowerPoint file programmatically to confirm it is valid and contains seven slides.
- [ ] Re-run the case-data assertions and report the exact verification result.
