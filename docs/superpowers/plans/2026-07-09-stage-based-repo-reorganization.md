# Stage-Based Repo Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the project so scripts and results are readable by research stage without breaking the current data pipeline.

**Architecture:** Move CLI scripts into `scripts/P0_data_collection`, `scripts/P1_pipeline`, and `scripts/P2_diagnostics`. Keep physical `data/raw`, `data/processed`, `paper/figures`, and `paper/tables` stable, and add README files to document stage ownership. Use a root-discovery helper pattern in moved scripts so paths still resolve from nested script folders.

**Tech Stack:** Python 3.11+, pandas, pytest, current local Anaconda Python at `/Users/wanghaozhe/anaconda3/bin/python`.

## Global Constraints

- Do not delete raw data, processed panels, paper outputs, or result outputs.
- Do not rerun live API downloads.
- Keep empirical output paths stable for this pass.
- Code and code comments stay in English.
- Explanations to the user stay in Simplified Chinese.
- Use `utf-8-sig` for CSV defaults where scripts already write Chinese-friendly CSVs.

---

### Task 1: Create Stage Directories And README Files

**Files:**
- Create: `scripts/P0_data_collection/README.md`
- Create: `scripts/P1_pipeline/README.md`
- Create: `scripts/P2_diagnostics/README.md`
- Create: `data/README.md`
- Create: `result/README.md`
- Create: `docs/README.md`

**Interfaces:**
- Consumes: current project stage definitions.
- Produces: human-readable folder map.

- [ ] Create README files describing each directory's responsibility.
- [ ] Verify `find scripts -maxdepth 2 -type d | sort` shows the three stage directories.

### Task 2: Move Scripts By Stage

**Files:**
- Move P0 scripts into `scripts/P0_data_collection/`.
- Move P1 scripts into `scripts/P1_pipeline/`.
- Move P2 scripts into `scripts/P2_diagnostics/`.
- Move root `phase0_pair_inventory.py` into `scripts/P0_data_collection/phase0_pair_inventory.py`.

**Interfaces:**
- Consumes: existing script filenames.
- Produces: stable stage-based script paths.

- [ ] Move files without deleting any script.
- [ ] Add a root-discovery helper to every moved script that currently assumes `parents[1]`.
- [ ] Update script-to-script references such as freeze-runner command plans and provenance metadata.

### Task 3: Update Tests And Imports

**Files:**
- Modify: `tests/test_p2_freeze_runner.py`
- Modify: `tests/test_p2_reference_basis_audit.py`

**Interfaces:**
- Consumes: moved script paths.
- Produces: tests that import P2 modules from `scripts/P2_diagnostics`.

- [ ] Update dynamic imports or path references in tests.
- [ ] Run `/Users/wanghaozhe/anaconda3/bin/python -m pytest tests -q`.

### Task 4: Validate Path References

**Files:**
- Modify only files with stale script path references found by `rg`.

**Interfaces:**
- Consumes: current docs and script references.
- Produces: no stale references in executable code; docs may retain historical references only when explicitly described as historical.

- [ ] Run `rg "scripts/build_|phase0_pair_inventory|scripts/run_p1_freeze"`.
- [ ] Update executable references.
- [ ] Run freeze-runner dry run from the new path.
- [ ] Run the full pytest suite again.
