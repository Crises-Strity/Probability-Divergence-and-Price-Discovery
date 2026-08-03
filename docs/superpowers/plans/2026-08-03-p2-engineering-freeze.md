# P2 Engineering Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the frozen Track A, Track B, robustness, reference-audit, and 30-table result set reproducible from a fresh Git checkout under Python 3.11, with outputs tied to a real code commit.

**Architecture:** Git tracks a compact set of frozen Parquet inputs plus code, tests, documentation, final tables, figures, and metadata. A Python 3.11 `uv` environment runs a deterministic freeze runner; a separate verifier checks input hashes, output invariants, provenance paths, Commit A, and replay equality before the user creates Commit B.

**Tech Stack:** Python 3.11, uv, pandas 2.3.3, NumPy 2.2.6, SciPy 1.15.3, statsmodels 0.14.5, pyarrow 23.0.0, matplotlib 3.10.7, Jinja2 3.1.6, requests 2.32.5, python-dateutil 2.9.0.post0, pytest 9.0.2, Git.

## Global Constraints

- Code and comments are English; user-facing explanations are Simplified Chinese.
- Do not change frozen estimators, sample filters, or empirical claims.
- Wild cluster bootstrap is not implemented; event-clustered p-values remain descriptive.
- Do not commit `data/raw/`, large processed panels, `result/`, caches, virtual environments, meeting materials, or downloaded literature PDFs.
- Do not fabricate or update frozen counts merely to make tests pass.
- Commit A is created manually by the user before result regeneration; Commit B is created manually after verification.
- Generated metadata and provenance in Commit B must record Commit A, not Commit B.

---

### Task 1: Narrow the repository tracking policy

**Files:**
- Modify: `.gitignore`
- Create: `data/README.md`

**Interfaces:**
- Consumes: the current repository layout and the compact input list defined below.
- Produces: a Git-visible code/document/result tree while keeping bulk data and local artifacts ignored.

- [ ] **Step 1: Replace broad ignore rules with scoped rules**

Use this policy in `.gitignore`:

```gitignore
# macOS and editor state
.DS_Store
**/.DS_Store
.vscode/
.idea/

# Python caches and environments
__pycache__/
**/__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.ipynb_checkpoints/
.venv/
venv/
build/
dist/
*.egg-info/

# Archives and local research material
*.zip
meeting_materials/
result/
dissertation/literature_review/*.pdf

# Raw and bulk processed data
data/raw/
data/processed/**/*.csv
data/processed/**/*.parquet
data/processed/**/*.json

# Compact frozen inputs required by scripts/P2_diagnostics/run_p1_freeze.py
!data/processed/panels/trackA_event_day_quality.parquet
!data/processed/panels/trackA_event_day_divergence.parquet
!data/processed/panels/daily_distribution_comparison.parquet
!data/processed/panels/trackA_event_day_divergence_smooth005.parquet
!data/processed/panels/trackA_event_day_divergence_smooth02.parquet
!data/processed/deribit/deribit_curve_fits.parquet
!data/processed/deribit/deribit_state_price_grid.parquet
!data/processed/deribit/deribit_bar_quality_60.parquet
!data/processed/polymarket/event_universe.parquet
!data/processed/polymarket/event_cells.parquet
!data/processed/polymarket/polymarket_distribution_hourly.parquet

# Metadata required by the frozen result set
!data/processed/frozen_input_manifest.json
!data/processed/panels/trackA_diagnostics_summary.json
!data/processed/panels/trackA_regression_diagnostics_summary.json
!data/processed/panels/reference_basis_audit_metadata.json
!data/processed/panels/trackB_kstar_metadata.json
!data/processed/panels/trackB_pm_survival_metadata.json
!data/processed/panels/trackB_deribit_survival_metadata.json
!data/processed/panels/trackB_deribit_survival_metadata_6h.json
!data/processed/panels/trackB_lead_lag_panel_metadata.json
!data/processed/panels/trackB_lead_lag_panel_metadata_6h.json
!data/processed/panels/trackB_lead_lag_diagnostics_summary.json
```

Do not include global `*.csv` or `*.json` rules. This keeps final paper CSV files and metadata JSON files trackable.

- [ ] **Step 2: Document the data boundary**

Create `data/README.md` with:

```markdown
# Data Policy

`data/raw/` and bulk generated panels are intentionally excluded from Git.

The repository tracks only the compact processed Parquet inputs required by
`scripts/P2_diagnostics/run_p1_freeze.py --include-track-b`. Their hashes,
sizes, row counts, and schemas are recorded in
`data/processed/frozen_input_manifest.json`.

The tracked inputs reproduce the frozen paper tables and figures. They do not
reproduce the original API collection step, because historical public-market
API responses can change after the project snapshot date.
```

- [ ] **Step 3: Verify ignore behavior**

Run:

```bash
git check-ignore -v data/raw data/processed/panels/pm_survival_hourly.csv result dissertation/literature_review/*.pdf
git check-ignore -v README.md AGENTS.md docs/specs/P2_NEXT_STEPS.md dissertation/ch5_results.tex paper/tables/tab_trackA_sample_funnel.csv paper/figures/fig_trackA_l1_distribution.pdf data/processed/panels/trackA_event_day_quality.parquet
```

Expected: the first command reports ignore rules. The second command prints nothing, meaning every listed file is trackable.

---

### Task 2: Add the locked Python 3.11 environment

**Files:**
- Create: `pyproject.toml`
- Create mechanically: `uv.lock`
- Modify: `README.md`

**Interfaces:**
- Consumes: Python 3.11 at `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11`.
- Produces: `.venv` and `uv run python` as the single project runtime.

- [ ] **Step 1: Add the dependency declaration**

Create `pyproject.toml`:

```toml
[project]
name = "probability-divergence-price-discovery"
version = "0.1.0"
description = "Frozen empirical pipeline for Polymarket-Deribit probability divergence and price discovery"
readme = "README.md"
requires-python = ">=3.11,<3.12"
dependencies = [
  "jinja2==3.1.6",
  "matplotlib==3.10.7",
  "numpy==2.2.6",
  "pandas==2.3.3",
  "pyarrow==23.0.0",
  "python-dateutil==2.9.0.post0",
  "requests==2.32.5",
  "scipy==1.15.3",
  "statsmodels==0.14.5",
]

[dependency-groups]
dev = [
  "pytest==9.0.2",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Install uv only if it remains unavailable**

Run after user approval for package installation:

```bash
brew install uv
```

Expected: `uv --version` exits zero. Do not install packages into Anaconda base.

- [ ] **Step 3: Resolve and synchronize Python 3.11**

Run:

```bash
uv lock --python /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11
uv sync --python /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11
uv run python --version
```

Expected: `uv.lock` exists and the final command reports Python 3.11.x.

- [ ] **Step 4: Verify exact core versions**

Run:

```bash
uv run python -c "import matplotlib,numpy,pandas,pyarrow,scipy,statsmodels; print(matplotlib.__version__, numpy.__version__, pandas.__version__, pyarrow.__version__, scipy.__version__, statsmodels.__version__)"
```

Expected:

```text
3.10.7 2.2.6 2.3.3 23.0.0 1.15.3 0.14.5
```

- [ ] **Step 5: Replace README environment instructions**

Document these commands in `README.md`:

```bash
uv sync --python 3.11
uv run pytest -q
uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b
```

Remove the statement that a frozen environment is still missing.

---

### Task 3: Build and test the compact input manifest

**Files:**
- Create: `scripts/P2_diagnostics/build_frozen_input_manifest.py`
- Create: `tests/test_p2_frozen_input_manifest.py`
- Generate: `data/processed/frozen_input_manifest.json`

**Interfaces:**
- Produces: `FROZEN_INPUTS: tuple[str, ...]`, `file_record(path: Path) -> dict[str, object]`, and `build_manifest(project_root: Path) -> dict[str, object]`.
- Manifest records: relative path, SHA-256, byte size, row count, and ordered column names. It deliberately contains no Git hash or generation timestamp.

- [ ] **Step 1: Write failing manifest tests**

Add tests that create a temporary Parquet file and assert:

```python
record = module.file_record(parquet_path)
assert record["sha256"] == hashlib.sha256(parquet_path.read_bytes()).hexdigest()
assert record["bytes"] == parquet_path.stat().st_size
assert record["rows"] == 2
assert record["columns"] == ["event_id", "value"]
```

Also assert that `build_manifest()` raises `FileNotFoundError` listing every missing frozen input.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
uv run pytest tests/test_p2_frozen_input_manifest.py -q
```

Expected: collection/import fails because `build_frozen_input_manifest.py` does not exist.

- [ ] **Step 3: Implement the manifest builder**

Use `hashlib.sha256`, `Path`, and `pandas.read_parquet`. Keep `FROZEN_INPUTS` equal to the 11 `.gitignore` exceptions from Task 1. Write JSON with `indent=2`, `ensure_ascii=False`, and a final newline.

The CLI entry point writes:

```text
data/processed/frozen_input_manifest.json
```

- [ ] **Step 4: Run tests and generate the manifest**

Run:

```bash
uv run pytest tests/test_p2_frozen_input_manifest.py -q
uv run python scripts/P2_diagnostics/build_frozen_input_manifest.py
```

Expected: tests pass and the manifest reports 11 input files.

- [ ] **Step 5: Confirm the compact input size**

Run:

```bash
du -ch $(uv run python -c "from scripts.P2_diagnostics.build_frozen_input_manifest import FROZEN_INPUTS; print(' '.join(FROZEN_INPUTS))")
```

Expected: total remains a few megabytes and far below the 203 MB full data directory.

---

### Task 4: Make the freeze runner environment-safe and complete

**Files:**
- Modify: `scripts/P2_diagnostics/run_p1_freeze.py`
- Modify: `tests/test_p2_freeze_runner.py`

**Interfaces:**
- Produces: `python_executable() -> str`, `command_plan(include_track_b: bool) -> list[Command]`, `required_inputs(include_track_b: bool) -> tuple[str, ...]`, and `validate_required_inputs(include_track_b: bool) -> None`.
- Full Track B mode rebuilds every Track B paper table from the compact frozen inputs before provenance.

- [ ] **Step 1: Extend failing runner tests**

Add assertions:

```python
self.assertEqual(module.python_executable(), sys.executable)
self.assertEqual(scripts[-1], "scripts/P2_diagnostics/build_p1_table_provenance.py")
self.assertIn("scripts/P1_pipeline/build_trackB_kstar_panel.py", scripts)
self.assertIn("scripts/P1_pipeline/build_trackB_pm_survival_panel.py", scripts)
self.assertIn("scripts/P1_pipeline/build_trackB_deribit_survival_panel.py", scripts)
self.assertIn("scripts/P1_pipeline/build_trackB_lead_lag_panel.py", scripts)
self.assertIn("scripts/P1_pipeline/build_trackB_lead_lag_diagnostics.py", scripts)
```

Test both hourly commands with no arguments and 6h commands with `("--bar-hours", "6")`. Add a temporary-root test proving `validate_required_inputs()` raises before any subprocess runs.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
uv run pytest tests/test_p2_freeze_runner.py -q
```

Expected: failure because the runner still prefers the hard-coded Anaconda path and omits the K*, PM-survival, and hourly Track B stages.

- [ ] **Step 3: Implement the full command order**

Use `sys.executable` unconditionally. For `--include-track-b`, execute in this dependency order:

```text
build_trackB_kstar_panel.py
build_trackB_pm_survival_panel.py
build_trackB_deribit_survival_panel.py
build_trackB_lead_lag_panel.py
build_trackB_deribit_survival_panel.py --bar-hours 6
build_trackB_lead_lag_panel.py --bar-hours 6
build_trackB_lead_lag_diagnostics.py
```

Keep Track A diagnostics and reference audit before this branch, and provenance last. Validate all 11 compact inputs before starting the first command.

- [ ] **Step 4: Run runner tests and dry runs**

Run:

```bash
uv run pytest tests/test_p2_freeze_runner.py -q
uv run python scripts/P2_diagnostics/run_p1_freeze.py --dry-run
uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b --dry-run
```

Expected: tests pass, every printed command starts with the `.venv` Python executable, and provenance is last.

---

### Task 5: Strengthen table provenance

**Files:**
- Modify: `scripts/P2_diagnostics/build_p1_table_provenance.py`
- Create: `tests/test_p2_table_provenance.py`

**Interfaces:**
- Produces: `parse_script_command(command: str) -> tuple[str, list[str]]` and richer entries containing `script_file`, `script_args`, `script_file_exists`, `input_file_exists`, `metadata_file_exists`, and `tex_file_exists`.
- Keeps the existing human-readable `script` command for table display.

- [ ] **Step 1: Write failing provenance tests**

Test command parsing:

```python
script, args = module.parse_script_command(
    "scripts/P1_pipeline/build_trackB_deribit_survival_panel.py --bar-hours 6"
)
assert script == "scripts/P1_pipeline/build_trackB_deribit_survival_panel.py"
assert args == ["--bar-hours", "6"]
```

Use a temporary project tree to assert that `build_entries()` reports script, input, metadata, CSV-row, and TeX existence correctly.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
uv run pytest tests/test_p2_table_provenance.py -q
```

Expected: failure because command parsing and existence fields are absent.

- [ ] **Step 3: Implement structured provenance fields**

Use `shlex.split()` for command strings. Store each input as:

```json
{"path": "data/processed/...", "exists": true}
```

Keep `rows` calculated from the UTF-8-SIG CSV. Add script and existence columns to the Markdown output without removing the existing paper-use and sample-gate columns.

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_p2_table_provenance.py -q
```

Expected: all provenance unit tests pass.

---

### Task 6: Add strict frozen-output verification

**Files:**
- Create: `scripts/P2_diagnostics/verify_p2_freeze.py`
- Create: `tests/test_p2_frozen_outputs.py`

**Interfaces:**
- Produces: `validate_freeze(project_root: Path, expected_git_commit: str | None) -> list[str]`, `table_hashes(project_root: Path) -> dict[str, str]`, and a CLI with `--expected-git-commit`, `--write-table-manifest`, and `--compare-table-manifest`.
- Returns all validation errors together; the CLI exits nonzero when the list is non-empty.

- [ ] **Step 1: Write failing verifier tests**

Build small temporary fixtures and test these failures separately:

```text
wrong table count
legacy scripts/build_*.py path
missing script/input/metadata/TeX file
CSV row-count mismatch
wrong Track A event-day or event count
wrong Track B informative or regression count
wrong reference-audit row/status count
missing or malformed expected Git hash
table-manifest hash mismatch
```

Also test a complete fixture returns `[]`.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
uv run pytest tests/test_p2_frozen_outputs.py -q
```

Expected: import failure because `verify_p2_freeze.py` does not exist.

- [ ] **Step 3: Implement exact frozen constants**

Use named constants:

```python
EXPECTED_TABLE_COUNT = 30
EXPECTED_TRACK_A_EVENT_DAYS = 294
EXPECTED_TRACK_A_EVENTS = 61
EXPECTED_TRACK_B_JOINT_INFORMATIVE_ROWS = 1121
EXPECTED_TRACK_B_REGRESSION_ROWS = 703
EXPECTED_REFERENCE_AUDIT_ROWS = 124
EXPECTED_REFERENCE_PROXY_ROWS = 124
```

Validate the actual summary JSON keys already used by the project. For Git validation, require every metadata file referenced by the 30 provenance entries to equal `--expected-git-commit`. Validate that the expected hash matches `[0-9a-f]{40}`.

Hash only `paper/tables/tab_*.csv` for deterministic comparison. Do not hash timestamp-bearing JSON or Markdown provenance files.

- [ ] **Step 4: Run all fast tests**

Run:

```bash
uv run pytest -q
```

Expected: all tests pass before Commit A because strict real-output Git validation is only activated by the verifier CLI after regeneration.

---

### Task 7: Align engineering documents and inference wording

**Files:**
- Modify: `docs/specs/P2_NEXT_STEPS.md`
- Modify: `docs/specs/P2_IMPLEMENTATION_PLAN.md`
- Modify: `docs/specs/P1_PIPELINE_SPEC.md`
- Modify: `docs/roadmap/DISSERTATION_TOPIC_OUTLINE.md`
- Modify only if contradictory: `dissertation/ch3_methodology.tex`
- Modify only if contradictory: `dissertation/ch5_results.tex`
- Modify only if contradictory: `dissertation/ch6_discussion.tex`
- Modify only if contradictory: `dissertation/ch7_limitations.tex`

**Interfaces:**
- Produces: one consistent frozen inference policy and current Git/environment status.

- [ ] **Step 1: Add a supersession notice to historical specs**

Where an older document calls wild cluster bootstrap primary inference, add a dated note:

```text
P2 freeze decision (2026-08-03): wild cluster bootstrap was not implemented.
Event-clustered standard errors and p-values are retained as descriptive
diagnostics and do not identify causal or directional price discovery.
```

Do not delete the historical design text; mark it superseded so the decision trail remains visible.

- [ ] **Step 2: Correct stale repository status**

Remove statements claiming the folder is not a Git repository. State that Commit A must be created before the final freeze run and that Commit B outputs intentionally reference Commit A.

- [ ] **Step 3: Check dissertation consistency**

Run:

```bash
rg -n "wild.cluster|bootstrap|clustered standard errors|p-values|directional" dissertation/ch3_methodology.tex dissertation/ch5_results.tex dissertation/ch6_discussion.tex dissertation/ch7_limitations.tex
```

Expected: no chapter claims that bootstrap was implemented or that clustered p-values provide causal/directional identification. Preserve already-correct prose.

- [ ] **Step 4: Run path and stale-status scans**

Run:

```bash
rg -n "scripts/build_[A-Za-z0-9_]+\.py|unavailable_not_git_repo|folder is not a git repository" README.md docs scripts tests dissertation
```

Expected: no active P2 instruction or generated-code source mapping uses a legacy path or stale non-Git status. Historical logs may retain old paths only when explicitly labelled historical.

---

### Task 8: User creates and pushes Commit A

**Files:**
- Stage code, configuration, documentation, dissertation source, and compact frozen inputs.
- Do not stage regenerated `paper/` outputs or result metadata in this commit.

**Interfaces:**
- Produces: the real code hash consumed by all regenerated metadata.

- [ ] **Step 1: Run the pre-commit verification**

```bash
uv run pytest -q
uv run python scripts/P2_diagnostics/build_frozen_input_manifest.py
git status --short
```

Expected: tests pass; only intended source/config/docs/input changes are visible.

- [ ] **Step 2: Stage Commit A explicitly**

Run manually:

```bash
git add .gitignore README.md AGENTS.md pyproject.toml uv.lock
git add data/README.md data/processed/frozen_input_manifest.json
git add data/processed/panels/trackA_event_day_quality.parquet
git add data/processed/panels/trackA_event_day_divergence.parquet
git add data/processed/panels/daily_distribution_comparison.parquet
git add data/processed/panels/trackA_event_day_divergence_smooth005.parquet
git add data/processed/panels/trackA_event_day_divergence_smooth02.parquet
git add data/processed/deribit/deribit_curve_fits.parquet
git add data/processed/deribit/deribit_state_price_grid.parquet
git add data/processed/deribit/deribit_bar_quality_60.parquet
git add data/processed/polymarket/event_universe.parquet
git add data/processed/polymarket/event_cells.parquet
git add data/processed/polymarket/polymarket_distribution_hourly.parquet
git add -A scripts tests docs dissertation
```

- [ ] **Step 3: Inspect staged scope**

Run manually:

```bash
git diff --cached --stat
git diff --cached --name-status
```

Expected: no `data/raw/`, `result/`, `.venv/`, cache, meeting-material, or literature PDF files are staged. Old top-level script deletions and new P0/P1/P2 paths appear together.

- [ ] **Step 4: Commit and push**

Run manually:

```bash
git commit -m "chore: freeze P2 code and reproducibility workflow"
git push origin main
CODE_COMMIT_A=$(git rev-parse HEAD)
printf '%s\n' "$CODE_COMMIT_A"
```

Keep `CODE_COMMIT_A` in the same shell for Task 9, or set it again there with `CODE_COMMIT_A=$(git rev-parse HEAD)`.

---

### Task 9: Regenerate twice and verify deterministic outputs

**Files:**
- Regenerate: `paper/tables/*`
- Regenerate: `paper/figures/*`
- Regenerate: required `data/processed/**/*metadata*.json` and `*summary.json`
- Temporary manifests: `/private/tmp/p2-table-manifest-first.json`, `/private/tmp/p2-table-manifest-second.json`

**Interfaces:**
- Consumes: clean Commit A and its 40-character hash.
- Produces: Commit B-ready final artifacts whose metadata references Commit A.

- [ ] **Step 1: Confirm the checkout is at Commit A**

Run manually:

```bash
git status --short
CODE_COMMIT_A=$(git rev-parse HEAD)
printf '%s\n' "$CODE_COMMIT_A"
```

Expected: the printed value is the 40-character Commit A hash. Untracked `paper/` outputs and result metadata may remain until Commit B; source/configuration changes must not remain unstaged.

- [ ] **Step 2: Run the first full freeze replay**

```bash
uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b
uv run python scripts/P2_diagnostics/verify_p2_freeze.py --expected-git-commit "$CODE_COMMIT_A" --write-table-manifest /private/tmp/p2-table-manifest-first.json
```

Expected: all pipeline commands exit zero, 30 tables are documented, and strict verification reports no errors.

- [ ] **Step 3: Run the second full freeze replay**

```bash
uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b
uv run python scripts/P2_diagnostics/verify_p2_freeze.py --expected-git-commit "$CODE_COMMIT_A" --write-table-manifest /private/tmp/p2-table-manifest-second.json --compare-table-manifest /private/tmp/p2-table-manifest-first.json
```

Expected: strict verification passes and all 30 table CSV hashes match the first replay.

- [ ] **Step 4: Re-run the complete test suite**

```bash
uv run pytest -q
```

Expected: all tests pass under Python 3.11.

---

### Task 10: User creates and pushes Commit B

**Files:**
- Stage: `paper/tables/`, `paper/figures/`, and metadata regenerated by Task 9.
- Do not stage generated intermediate CSV/Parquet panels.

**Interfaces:**
- Produces: the final GitHub result freeze tied to Commit A.

- [ ] **Step 1: Inspect result changes**

Run manually:

```bash
git status --short
git diff -- paper/tables paper/figures data/processed
```

Expected: changes are generated tables, figures, provenance, and metadata; no source code changed during the replay.

- [ ] **Step 2: Stage only final artifacts**

Run manually:

```bash
git add paper/tables paper/figures
git add data/processed/panels/trackA_diagnostics_summary.json
git add data/processed/panels/trackA_regression_diagnostics_summary.json
git add data/processed/panels/reference_basis_audit_metadata.json
git add data/processed/panels/trackB_kstar_metadata.json
git add data/processed/panels/trackB_pm_survival_metadata.json
git add data/processed/panels/trackB_deribit_survival_metadata.json
git add data/processed/panels/trackB_deribit_survival_metadata_6h.json
git add data/processed/panels/trackB_lead_lag_panel_metadata.json
git add data/processed/panels/trackB_lead_lag_panel_metadata_6h.json
git add data/processed/panels/trackB_lead_lag_diagnostics_summary.json
```

- [ ] **Step 3: Verify staged result scope**

Run manually:

```bash
git diff --cached --stat
git diff --cached --name-only
```

Expected: no raw data, bulk panels, source changes, caches, or virtual-environment files are staged.

- [ ] **Step 4: Commit and push**

Run manually:

```bash
git commit -m "results: freeze P2 tables figures and provenance"
git push origin main
```

- [ ] **Step 5: Final repository audit**

Run manually:

```bash
git status --short
git ls-files | rg "(^data/raw/|^result/|\.DS_Store$|__pycache__|\.venv/|dissertation/literature_review/.*\.pdf$)"
git show HEAD:paper/tables/table_source_metadata.json | rg '"git_commit"|"table_count"|scripts/P[12]_'
```

Expected: the working tree is clean; the forbidden-file scan prints nothing; provenance reports 30 tables, current P1/P2 paths, and the Commit A hash printed in Task 9.
