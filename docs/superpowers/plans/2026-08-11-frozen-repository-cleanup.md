# Frozen Repository Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the frozen empirical repository self-contained, move all dissertation material outside it safely, and document the final P0--P3 conclusions and reproducibility boundaries.

**Architecture:** Preserve the dissertation as a standalone Git clone plus an unversioned local support archive before removing the parent submodule. Keep the compact frozen input package and the existing P3 runtime configuration unchanged, then make the root documentation accurately describe the frozen project and its separate dissertation workflow.

**Tech Stack:** Git, Git submodules, rsync, Markdown, JSON, Python 3.11, uv, pytest.

## Global Constraints

- Do not change the frozen empirical specification or rerun exploratory work.
- Do not fabricate or update reported results without generated evidence.
- Preserve all local dissertation material before removing it from the parent repository.
- Do not add literature PDFs to either Git repository.
- Do not modify the dissertation repository's manuscript contents.
- Preserve unrelated user changes, including the current untracked P3 planning documents and `tmp/` files.
- Do not move or edit `configs/p3_track_a_extension.json`.
- Remove parent-repository dissertation paths only after both external destinations pass verification.

---

## File Map

- Create externally: `/Users/wanghaozhe/Desktop/UCL-Final-Dissertation/` -- independent local clone of the dissertation GitHub repository.
- Create externally: `/Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811/` -- unversioned copy of non-manuscript support material.
- Remove from parent: `.gitmodules` -- obsolete after dissertation separation.
- Remove from parent: `dissertation/` -- submodule gitlink and tracked parent-side workflow artifacts.
- Modify: `.gitignore` -- remove obsolete dissertation inbox, release ZIP, and literature rules.
- Modify: `README.md` -- frozen project entry point and final conclusions.
- Modify: `data/README.md` -- precise compact-input exception.
- Create: `configs/README.md` -- runtime configuration versus planning distinction.

### Task 1: Preserve the dissertation outside the parent repository

**Files:**
- Create externally: `/Users/wanghaozhe/Desktop/UCL-Final-Dissertation/`
- Create externally: `/Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811/`
- Read: `dissertation/manuscript/`
- Read: `dissertation/`

**Interfaces:**
- Consumes: clean submodule worktree at commit `19b48731492affabec5488b98d1819baeed69ba6` and all non-manuscript files under `dissertation/`.
- Produces: an independent Git repository with GitHub `origin`, plus a complete non-manuscript support copy that makes parent removal safe.

- [ ] **Step 1: Confirm destinations are absent and sources are stable**

Run:

```bash
test ! -e /Users/wanghaozhe/Desktop/UCL-Final-Dissertation
test ! -e /Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811
test "$(git -C dissertation/manuscript rev-parse HEAD)" = "19b48731492affabec5488b98d1819baeed69ba6"
test -z "$(git -C dissertation/manuscript status --porcelain)"
```

Expected: all commands exit zero. Stop without overwriting anything if a destination exists or the manuscript worktree is dirty.

- [ ] **Step 2: Create an independent local clone from the verified checkout**

Run with permission to write outside the project root:

```bash
git clone dissertation/manuscript /Users/wanghaozhe/Desktop/UCL-Final-Dissertation
git -C /Users/wanghaozhe/Desktop/UCL-Final-Dissertation remote set-url origin https://github.com/Crises-Strity/UCL-Final-Dissertation.git
```

Expected: clone completes without network dependency and `origin` is reset from the temporary local source path to the dedicated GitHub repository.

- [ ] **Step 3: Verify that the clone is independent and exact**

Run:

```bash
git -C /Users/wanghaozhe/Desktop/UCL-Final-Dissertation rev-parse --git-dir
git -C /Users/wanghaozhe/Desktop/UCL-Final-Dissertation rev-parse HEAD
git -C /Users/wanghaozhe/Desktop/UCL-Final-Dissertation branch --show-current
git -C /Users/wanghaozhe/Desktop/UCL-Final-Dissertation remote get-url origin
git -C /Users/wanghaozhe/Desktop/UCL-Final-Dissertation status --short
diff -qr --exclude=.git dissertation/manuscript /Users/wanghaozhe/Desktop/UCL-Final-Dissertation
```

Expected: Git dir is `.git`, HEAD is `19b48731492affabec5488b98d1819baeed69ba6`, branch is `main`, origin is the dedicated GitHub URL, and the status and diff commands print nothing.

- [ ] **Step 4: Copy all non-manuscript support material**

Run with permission to write outside the project root:

```bash
mkdir /Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811
rsync -a --exclude=manuscript/ dissertation/ /Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811/
```

Expected: literature PDFs, `literature_audit.csv`, `evidence_audit.md`, releases, reviews, README, and inbox contents are copied; the manuscript checkout is excluded.

- [ ] **Step 5: Verify the support copy before any parent removal**

Run:

```bash
diff -qr --exclude=manuscript dissertation /Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811
find dissertation -path dissertation/manuscript -prune -o -type f -print | sed 's#^dissertation/##' | sort > /private/tmp/dissertation-source-files-20260811.txt
find /Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811 -type f -print | sed 's#^/Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811/##' | sort > /private/tmp/dissertation-support-files-20260811.txt
diff -u /private/tmp/dissertation-source-files-20260811.txt /private/tmp/dissertation-support-files-20260811.txt
```

Expected: both diff commands print nothing. Parent removal remains blocked if either comparison differs.

### Task 2: Remove the parent dissertation boundary and update documentation

**Files:**
- Remove: `.gitmodules`
- Remove: `dissertation/`
- Modify: `.gitignore`
- Modify: `README.md`
- Modify: `data/README.md`
- Create: `configs/README.md`

**Interfaces:**
- Consumes: both verified external destinations from Task 1 and frozen decision records under `docs/decision_logs/`.
- Produces: a parent repository with no dissertation paths, accurate frozen-project documentation, unchanged empirical inputs, and an explained P3 runtime config.

- [ ] **Step 1: Move the original parent dissertation tree to a recoverable temporary backup**

Run:

```bash
test ! -e /private/tmp/dissertation-parent-backup-20260811
mv dissertation /private/tmp/dissertation-parent-backup-20260811
test -f /private/tmp/dissertation-parent-backup-20260811/manuscript/main.tex
```

Expected: the parent working tree no longer has `dissertation/`, while the exact original remains recoverable under `/private/tmp` during implementation.

- [ ] **Step 2: Remove obsolete parent integration metadata**

Use `apply_patch` to delete `.gitmodules` and remove these `.gitignore` rules:

```gitignore
dissertation/literature_review/*.pdf

# Dissertation handoff workspace
dissertation/inbox/*
!dissertation/inbox/.gitkeep
!dissertation/releases/**/source.zip
```

Expected: `.gitignore` retains all data, environment, result, and P3 rules and contains no `dissertation/` pattern.

- [ ] **Step 3: Create the configuration policy README**

Create `configs/README.md` with four explicit facts:

```markdown
# Runtime Configuration

This directory contains version-controlled parameters consumed directly by project scripts. It is not a planning directory.

`p3_track_a_extension.json` is the frozen source configuration for the P3 SOL feasibility extension. P3 externalized its continuation gates, inherited Track A parameters, API endpoints, and output paths so the feasibility decision could be reproduced without editing code.

P0--P2 retain their existing command-line and implementation parameters. Because the project is frozen, retrospective config files are not being created solely for directory symmetry.

Roadmaps, specifications, implementation plans, and empirical decisions live under `docs/`.
```

- [ ] **Step 4: Tighten the data policy**

Update `data/README.md` to state that raw API responses and bulk generated panels are excluded; 11 compact processed Parquet inputs are deliberately tracked; the package is approximately 2.8 MB; `frozen_input_manifest.json` records hash, size, row count, and schema; and the package rebuilds frozen paper outputs but cannot reproduce mutable historical API collection.

- [ ] **Step 5: Rewrite the root README around the final frozen state**

Use the existing root README as the base and include these exact sections: `Project Status`, `Frozen Conclusions`, `Research Design`, `Repository Structure`, `Stage Summary`, `Data and Reproducibility Policy`, `Environment and Verification`, `Dissertation Workflow`, and `Interpretation Boundaries`.

Report only these already-frozen facts:

```text
Track A: 294 event-days, 61 events, 3,114 cell-day rows.
Center: location intercept 0.000572, p=0.801546.
Baseline spread: median PM-Deribit spread difference 0.004022; PM wider share 0.707483.
Heavy smoothing 0.20: median spread difference 0.000843; PM wider share 0.525597.
Tail/body relative absolute divergence means: 0.857979 / 0.570604.
Track B 6h: 1,121 informative rows; 703 regression rows; level correlation 0.911992; contemporaneous change correlation 0.534829.
Direction: directional price discovery unidentified; sub-6h lead-lag not measurable with current Deribit OHLC liquidity.
P3: FAIL -- stop before the SOL Track A estimator; the three-expiry smoke probe produced zero event-days passing frozen P1 cross-strike gates.
```

The repository tree must include `configs/`, `data/`, `docs/`, `paper/`, `result/`, `scripts/P0_data_collection` through `scripts/P3_asset_extension`, and `tests/`; it must not include `dissertation/`.

Link the dedicated dissertation repository as `[UCL-Final-Dissertation](https://github.com/Crises-Strity/UCL-Final-Dissertation)` and document the workflow as `Overleaf -> dedicated GitHub repository -> standalone local clone`. Do not reintroduce submodule commands.

- [ ] **Step 6: Stage only the intended parent changes and inspect them**

Run:

```bash
git add -u .gitmodules .gitignore dissertation README.md data/README.md
git add configs/README.md
git diff --cached --check
git diff --cached --stat
git status --short
```

Expected: staged changes contain only `.gitmodules`, `.gitignore`, `README.md`, `configs/README.md`, `data/README.md`, and deletions under `dissertation/`. The pre-existing P3 planning documents and `tmp/` remain untracked and unstaged.

- [ ] **Step 7: Commit the repository boundary and documentation update**

Run:

```bash
git commit -m "docs: finalize frozen project repository"
```

Expected: one commit records the parent dissertation removal and frozen documentation without empirical code or data changes.

### Task 3: Verify the frozen repository and preserved external state

**Files:**
- Verify: parent repository
- Verify externally: `/Users/wanghaozhe/Desktop/UCL-Final-Dissertation/`
- Verify externally: `/Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811/`

**Interfaces:**
- Consumes: Task 1 preservation outputs and Task 2 parent commit.
- Produces: evidence that repository cleanup did not alter frozen code, data, outputs, or unrelated work.

- [ ] **Step 1: Verify the parent has no dissertation integration**

Run:

```bash
test ! -e .gitmodules
test ! -e dissertation
test -z "$(git ls-files | rg '^(\.gitmodules|dissertation/)')"
```

Expected: all commands exit zero. Historical design and plan documents under `docs/superpowers/` may still describe the superseded migration and are intentionally retained as history.

- [ ] **Step 2: Verify the external dissertation destinations again**

Run:

```bash
test "$(git -C /Users/wanghaozhe/Desktop/UCL-Final-Dissertation rev-parse HEAD)" = "19b48731492affabec5488b98d1819baeed69ba6"
test "$(git -C /Users/wanghaozhe/Desktop/UCL-Final-Dissertation branch --show-current)" = "main"
test "$(git -C /Users/wanghaozhe/Desktop/UCL-Final-Dissertation remote get-url origin)" = "https://github.com/Crises-Strity/UCL-Final-Dissertation.git"
test -z "$(git -C /Users/wanghaozhe/Desktop/UCL-Final-Dissertation status --porcelain)"
diff -qr /private/tmp/dissertation-parent-backup-20260811/literature_review /Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811/literature_review
diff -qr /private/tmp/dissertation-parent-backup-20260811/releases /Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811/releases
diff -qr /private/tmp/dissertation-parent-backup-20260811/reviews /Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811/reviews
```

Expected: all tests exit zero and all diff commands print nothing.

- [ ] **Step 3: Run focused manifest and P3 config tests**

Run:

```bash
uv run pytest tests/test_p2_frozen_input_manifest.py tests/test_p3_config.py -q
```

Expected: all selected tests pass, proving the compact data and unchanged P3 configuration remain valid.

- [ ] **Step 4: Run the strict freeze verifier**

Run:

```bash
uv run python scripts/P2_diagnostics/verify_p2_freeze.py
```

Expected: exit zero with a successful frozen-output verification message.

- [ ] **Step 5: Run the complete test suite and Git integrity checks**

Run:

```bash
uv run pytest -q
git diff --check HEAD^
git status --short
```

Expected: all tests pass; the diff check prints nothing; status shows only the pre-existing untracked P3 planning documents and `tmp/`, with no staged changes.
