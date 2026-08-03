# Track A Meeting Update Implementation Plan

**Goal:** Produce a self-contained supervisor meeting deck that moves from the prior one-event case study to frozen Track A panel evidence, with verified figures and practical speaker notes.

**Outputs:**

- `meeting_materials/track_a_meeting_update.pptx`
- `meeting_materials/track_a_meeting_speaker_notes.md`
- `meeting_materials/track_a_source_data/` containing compact, reproducible CSV/JSON extracts used by the deck

**Source of truth:**

- `docs/decision_logs/P1_EMPIRICAL_FREEZE.md`
- `docs/decision_logs/P1_PAPER_CONCLUSIONS.md`
- Frozen result tables under `paper/tables/`
- Existing prior case-study validation under `meeting_materials/source_data/`

---

## Task 1: Extract and validate presentation data

1. Read the frozen Track A decision logs and relevant CSV/JSON outputs.
2. Create a small extraction script in the external artifact scratch directory.
3. Export only the values used in the deck to `meeting_materials/track_a_source_data/`.
4. Assert sample counts, regression coefficients, smoothness-grid values, and robustness statistics against the frozen outputs.

## Task 2: Build the 13-slide presentation

1. Initialize an `@oai/artifact-tool` workspace outside the repository.
2. Use Codex Grid layout references and a restrained academic visual system: white background, Polymarket blue, Deribit orange, neutral gray.
3. Build 10 main slides and 3 appendix slides using editable native text, shapes, tables, and charts.
4. Keep Track A claims scoped to the frozen interpretation:
   - no robust center shift;
   - material tail-relative divergence;
   - spread difference conditional on smoothing;
   - horizon/composition regressions are descriptive, not causal.
5. Export to `meeting_materials/track_a_meeting_update.pptx`.

## Task 3: Write speaker notes

1. Create one section per slide.
2. For each slide include:
   - Must say: one or two sentences;
   - Optional detail;
   - Likely question and a concise answer.
3. Make the notes usable without memorizing every statistic.

## Task 4: Verify the artifact

1. Re-run data extraction and deck generation from a clean scratch state.
2. Run the presentation overflow test.
3. Validate the PPTX archive and confirm 13 slide XML files.
4. Render all slides to PNG, create a montage, and inspect each slide at full size.
5. Correct any clipping, overlap, inconsistent labels, or unsupported claims before delivery.

