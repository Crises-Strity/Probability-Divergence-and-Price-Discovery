# Track B and Empirical Project Wrap-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a verified 14-slide Track B and empirical-project wrap-up deck, an English leader brief, and separate Chinese meeting notes using only frozen local results.

**Architecture:** A temporary extraction script validates every displayed number and writes one compact JSON source snapshot. A JavaScript ES module using `@oai/artifact-tool` creates the editable PowerPoint while following the previous Track A deck's visual system. The two note files are maintained separately for different audiences and are checked against the same slide sequence and source snapshot.

**Tech Stack:** Python standard library for structured extraction and assertions; JavaScript ES modules with `@oai/artifact-tool` for PowerPoint generation; bundled PowerPoint rendering and overflow utilities for QA.

## Global Constraints

- Final outputs belong under `meeting_materials/2026.7.31 meeting/`.
- Meeting materials remain local and are not committed to Git.
- Use only frozen local P1 decision logs, metadata JSON files, and `paper/tables/` CSV files.
- Do not fabricate, estimate, or reconstruct empirical values from memory.
- Use the previous Track A deck as the visual reference.
- The deck contains 11 main slides and 3 appendix slides.
- Keep the English leader brief and Chinese meeting notes in separate files.
- State that the empirical project is complete unless specific feedback requires revision.
- Do not claim arbitrage, causal maturity effects, Polymarket leadership, or Deribit leadership.

---

### Task 1: Build and validate the presentation data snapshot

**Files:**
- Create: `/private/tmp/track-b-project-wrapup-2026-07-31/extract_wrapup_data.py`
- Create: `meeting_materials/2026.7.31 meeting/source_data/track_b_project_wrapup_data.json`

**Interfaces:**
- Consumes: frozen Track A and Track B JSON/CSV outputs listed in the design specification.
- Produces: one JSON object with keys `track_a`, `track_b_hourly`, `track_b_6h`, `cross_correlation`, `regressions`, `point_threshold`, and `sources`.

- [ ] **Step 1: Create the extraction script**

Implement helpers with these exact interfaces:

```python
def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_row(rows: list[dict[str, str]], **matches: str) -> dict[str, str]:
    selected = [
        row for row in rows
        if all(row[key] == value for key, value in matches.items())
    ]
    assert len(selected) == 1, (matches, len(selected))
    return selected[0]


def assert_close(
    actual: float,
    expected: float,
    tolerance: float = 1e-12,
) -> None:
    assert abs(actual - expected) <= tolerance, (actual, expected)
```

Read:

```text
data/processed/panels/trackA_diagnostics_summary.json
data/processed/panels/trackA_regression_diagnostics_summary.json
data/processed/panels/trackB_pm_survival_metadata.json
data/processed/panels/trackB_deribit_survival_metadata.json
data/processed/panels/trackB_deribit_survival_metadata_6h.json
data/processed/panels/trackB_lead_lag_panel_metadata.json
data/processed/panels/trackB_lead_lag_panel_metadata_6h.json
data/processed/panels/trackB_lead_lag_diagnostics_summary.json
paper/tables/tab_trackB_frequency_diagnostics_6h.csv
paper/tables/tab_trackB_cross_correlation_6h.csv
paper/tables/tab_trackB_pooled_lead_lag_6h.csv
paper/tables/tab_trackB_pm_informative_event_summary.csv
```

- [ ] **Step 2: Add exact assertions for headline values**

The script must fail unless these values match:

```python
assert track_a_days == 294
assert track_a_events == 61
assert_close(hourly_level_corr, 0.900819, tolerance=1e-6)
assert_close(hourly_change_corr, 0.040374, tolerance=1e-6)
assert_close(hourly_std_ratio, 2.728357, tolerance=1e-6)
assert_close(hourly_lag1, -0.449059, tolerance=1e-6)
assert joint_6h_rows == 1121
assert change_pair_rows == 889
assert regression_rows == 703
assert_close(level_corr_6h, 0.911992, tolerance=1e-6)
assert_close(change_corr_6h, 0.534829, tolerance=1e-6)
assert_close(cross_corr_minus_6h, 0.073590, tolerance=1e-6)
assert_close(cross_corr_plus_6h, 0.025272, tolerance=1e-6)
assert_close(pm_lag_to_deribit, 0.329746, tolerance=1e-6)
assert_close(deribit_own_lag, -0.400558, tolerance=1e-6)
```

- [ ] **Step 3: Run the extractor**

Run:

```bash
/Users/wanghaozhe/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  /private/tmp/track-b-project-wrapup-2026-07-31/extract_wrapup_data.py
```

Expected:

```text
Validated frozen Track A and Track B values.
/Users/wanghaozhe/Desktop/毕设项目/meeting_materials/2026.7.31 meeting/source_data/track_b_project_wrapup_data.json
```

- [ ] **Step 4: Inspect the JSON**

Run:

```bash
python -m json.tool "meeting_materials/2026.7.31 meeting/source_data/track_b_project_wrapup_data.json"
```

Expected: valid JSON containing all required keys and source paths.

### Task 2: Create the English leader brief

**Files:**
- Create: `meeting_materials/2026.7.31 meeting/track_b_project_wrapup_leader_brief_en.md`

**Interfaces:**
- Consumes: the 14-slide sequence and validated source snapshot.
- Produces: one English explanation section per slide.

- [ ] **Step 1: Write 14 slide sections**

Use this exact structure for each slide:

```markdown
## Slide N - Title

### What this slide shows

### Why it matters

### Appropriate interpretation

### Main limitation

[Sources]
- `data/processed/panels/trackB_lead_lag_diagnostics_summary.json`
```

- [ ] **Step 2: Add a project-level executive summary**

The summary must state:

```text
Track A identifies center alignment, material tail-relative divergence, and a
smoothing-conditional width wedge. Track B identifies strong level integration
and 6h contemporaneous co-movement, but no defensible directional leadership
ranking. The empirical project is therefore complete as a measurement and
identification-boundary study.
```

- [ ] **Step 3: Validate structure and claims**

Run:

```bash
rg -c '^## Slide [0-9]+ ' "meeting_materials/2026.7.31 meeting/track_b_project_wrapup_leader_brief_en.md"
rg -c '^\\[Sources\\]$' "meeting_materials/2026.7.31 meeting/track_b_project_wrapup_leader_brief_en.md"
rg -n 'arbitrage|Polymarket leads|Deribit leads' "meeting_materials/2026.7.31 meeting/track_b_project_wrapup_leader_brief_en.md"
```

Expected: 14 slide sections, 14 source blocks, and no unsupported directional or arbitrage claim.

### Task 3: Create the Chinese meeting notes

**Files:**
- Create: `meeting_materials/2026.7.31 meeting/track_b_project_wrapup_meeting_notes_zh.md`

**Interfaces:**
- Consumes: the same 14-slide sequence and validated source snapshot.
- Produces: presenter-facing Chinese notes with transitions and Q&A.

- [ ] **Step 1: Write 14 slide sections**

Use this exact structure:

```markdown
## 第 N 页 - 标题

### 本页目标

### 讲解顺序

### 必须提到的数字

### 可以省略

### 转场

### 可能问题与回答
```

- [ ] **Step 2: Add opening and closing scripts**

The opening must explain that the cancelled Track A meeting is closed through a brief full-panel recap. The closing must state that the empirical project is complete and only specific feedback should reopen analysis.

- [ ] **Step 3: Validate structure**

Run:

```bash
rg -c '^## 第 [0-9]+ 页 ' "meeting_materials/2026.7.31 meeting/track_b_project_wrapup_meeting_notes_zh.md"
rg -c '^### 转场$' "meeting_materials/2026.7.31 meeting/track_b_project_wrapup_meeting_notes_zh.md"
rg -n 'TODO|TBD|PLACEHOLDER|lorem' "meeting_materials/2026.7.31 meeting/track_b_project_wrapup_meeting_notes_zh.md"
```

Expected: 14 sections, 14 transitions, and no placeholders.

### Task 4: Build the editable PowerPoint deck

**Files:**
- Reference: `meeting_materials/2026.7.24 meeting/track_a_meeting_update.pptx`
- Create: `/private/tmp/track-b-project-wrapup-2026-07-31/build_deck.mjs`
- Create: `meeting_materials/2026.7.31 meeting/track_b_project_wrapup.pptx`

**Interfaces:**
- Consumes: `track_b_project_wrapup_data.json`.
- Produces: one editable 1280x720 PowerPoint with 14 slides.

- [ ] **Step 1: Load presentation dependencies and inspect the reference deck**

Read:

```text
presentations/SKILL.md
presentations/style_guidelines.md
presentations/references/template-following.md
presentations/artifact_tool_docs/API_QUICK_START.md
presentations/artifact_tool_docs/api/API_DOCS.md
```

Render the prior Track A deck and inspect all slides for margins, typography, title hierarchy, colors, chart styling, footers, and slide numbering.

- [ ] **Step 2: Initialize the artifact-tool workspace**

Run:

```bash
/Users/wanghaozhe/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
  "$SKILL_DIR/container_tools/setup_artifact_tool_workspace.mjs" \
  --workspace "/private/tmp/track-b-project-wrapup-2026-07-31"
```

Expected: the temporary directory is ready to import `@oai/artifact-tool`.

- [ ] **Step 3: Implement shared deck helpers**

The JavaScript module must define:

```javascript
function addText(slide, text, x, y, width, height, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width, height },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize: options.size ?? 20,
    typeface: "Helvetica Neue",
    color: options.color ?? "#111827",
    bold: options.bold ?? false,
    alignment: options.align ?? "left",
    verticalAlignment: options.valign ?? "top",
    autoFit: "shrinkText",
  };
  return shape;
}

function addHeader(slide, slideNumber, title, kicker) {
  addText(slide, kicker, 42, 26, 430, 22, {
    size: 12,
    color: "#667085",
    bold: true,
  });
  addText(slide, title, 42, 52, 1120, 82, { size: 32, bold: true });
  addText(slide, String(slideNumber).padStart(2, "0"), 1185, 28, 52, 22, {
    size: 13,
    color: "#667085",
    align: "right",
  });
}

function addSource(slide, sourceText) {
  return addText(slide, sourceText, 42, 676, 1120, 18, {
    size: 9,
    color: "#667085",
  });
}

function addStat(slide, x, y, width, value, label, color) {
  addText(slide, value, x, y, width, 50, {
    size: 34,
    bold: true,
    color,
  });
  return addText(slide, label, x, y + 54, width, 38, {
    size: 15,
    color: "#667085",
  });
}

function addChartFrame(slide, x, y, width, height) {
  return slide.shapes.add({
    geometry: "rect",
    position: { left: x, top: y, width, height },
    fill: "#F3F4F6",
    line: { style: "solid", fill: "#E5E7EB", width: 1 },
  });
}
```

Use the previous deck's white canvas, neutral ink, Polymarket blue, Deribit orange, green support, and amber/red qualifications.

- [ ] **Step 4: Implement slides 1-6**

Create:

```text
1. Title
2. Project status
3. Track A recap
4. Track B question and method
5. Hourly attempt and measurement problem
6. Six-hour solution and final sample
```

Slide 5 must visually contrast high hourly level correlation with near-zero hourly change correlation and show the noise diagnostics.

- [ ] **Step 5: Implement slides 7-11**

Create:

```text
7. 6h integration
8. Directional lead-lag unidentified
9. Track B conclusion
10. Cross-track project conclusions
11. Empirical project complete
```

Slide 8 must use the five-point symmetric cross-correlation series and visually emphasize the contemporaneous value without implying causality.

- [ ] **Step 6: Implement appendix slides 12-14**

Create:

```text
12. Point-threshold exclusion
13. Regression asymmetry
14. Identification limitations
```

- [ ] **Step 7: Export editable PPTX and scratch renders**

Export:

```text
meeting_materials/2026.7.31 meeting/track_b_project_wrapup.pptx
/private/tmp/track-b-project-wrapup-2026-07-31/rendered/slide-01.png through slide-14.png
```

Expected: the module exits with status 0 and reports 14 slides.

### Task 5: Verify all final artifacts

**Files:**
- Verify: `meeting_materials/2026.7.31 meeting/track_b_project_wrapup.pptx`
- Verify: both note files and the data snapshot.

**Interfaces:**
- Consumes: all Task 1-4 outputs.
- Produces: fresh evidence that the deliverables are structurally and visually valid.

- [ ] **Step 1: Re-run extraction and deck generation**

Run both scripts from a fresh process. Expected: both exit 0.

- [ ] **Step 2: Run PowerPoint overflow detection**

Run:

```bash
python "$SKILL_DIR/container_tools/slides_test.py" \
  "meeting_materials/2026.7.31 meeting/track_b_project_wrapup.pptx"
```

Expected:

```text
Test passed. No overflow detected.
```

- [ ] **Step 3: Validate the PPTX archive and slide count**

Run:

```bash
unzip -t "meeting_materials/2026.7.31 meeting/track_b_project_wrapup.pptx"
unzip -Z1 "meeting_materials/2026.7.31 meeting/track_b_project_wrapup.pptx" \
  | rg '^ppt/slides/slide[0-9]+\\.xml$' \
  | wc -l
```

Expected: no archive errors and exactly `14` slide XML files.

- [ ] **Step 4: Render with the independent PowerPoint renderer**

Run:

```bash
python "$SKILL_DIR/container_tools/render_slides.py" \
  "meeting_materials/2026.7.31 meeting/track_b_project_wrapup.pptx" \
  --output_dir "/private/tmp/track-b-project-wrapup-2026-07-31/final-render"
```

Expected: 14 PNG files.

- [ ] **Step 5: Create and inspect a montage**

Run:

```bash
python "$SKILL_DIR/container_tools/create_montage.py" \
  --input_dir "/private/tmp/track-b-project-wrapup-2026-07-31/final-render" \
  --output_file "/private/tmp/track-b-project-wrapup-2026-07-31/final-montage.png"
```

Inspect the montage for narrative flow, then inspect all 14 slides individually at full size.

- [ ] **Step 6: Run final note and placeholder checks**

Run:

```bash
rg -n 'TODO|TBD|PLACEHOLDER|lorem|xxx' \
  "meeting_materials/2026.7.31 meeting/track_b_project_wrapup_leader_brief_en.md" \
  "meeting_materials/2026.7.31 meeting/track_b_project_wrapup_meeting_notes_zh.md"
```

Expected: no matches.

- [ ] **Step 7: Confirm final files**

Run:

```bash
ls -lh \
  "meeting_materials/2026.7.31 meeting/track_b_project_wrapup.pptx" \
  "meeting_materials/2026.7.31 meeting/track_b_project_wrapup_leader_brief_en.md" \
  "meeting_materials/2026.7.31 meeting/track_b_project_wrapup_meeting_notes_zh.md" \
  "meeting_materials/2026.7.31 meeting/source_data/track_b_project_wrapup_data.json"
```

Expected: all four files exist and are non-empty.
