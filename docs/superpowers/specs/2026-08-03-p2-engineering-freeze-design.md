# P2 Engineering Freeze Design

**Date:** 2026-08-03

**Goal:** Finish the P2 code and repository freeze so that the existing Track A, Track B, robustness, and reference-audit results can be reproduced from a Python 3.11 environment and traced to a real code commit.

## 1. Current Evidence

The design is based on the current repository, frozen outputs, and dissertation drafts rather than the older roadmap alone.

- Git repository: present on `main`, current pre-freeze commit `45dfc16`.
- Remote: `origin` points to `Crises-Strity/Probability-Divergence-and-Price-Discovery`.
- Current runtime: Python 3.10.18 in Anaconda base.
- Python 3.11 executable: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11`.
- `uv`: not currently installed.
- Current core versions: pandas 2.3.3, SciPy 1.15.3, statsmodels 0.14.5, pyarrow 23.0.0, matplotlib 3.10.7, pytest 9.0.2.
- Frozen Track A sample: 294 event-days and 61 events.
- Frozen Track B sample: 1,121 joint-informative rows and 703 regression rows.
- Reference audit: 124 rows, all classified as `proxy_assumed`.
- Paper table inventory: 30 CSV table stems, each with a LaTeX counterpart.

The current `.gitignore` is too broad: it ignores all of `docs/`, `dissertation/`, `paper/`, `data/`, all CSV files, and all JSON files. The current provenance generator uses the new P0/P1/P2 script paths, but the generated provenance files still contain old `scripts/build_*.py` paths. Several generated metadata files also retain old `script_name` paths and null Git hashes.

## 2. Approaches Considered

### Approach A: Minimal repository cleanup

Only narrow `.gitignore`, add an environment file, and rerun provenance.

This is fast but leaves no automated protection against stale paths, missing metadata, changed sample counts, or nondeterministic regenerated tables.

### Approach B: Engineering freeze with invariant tests

Narrow `.gitignore`, create a Python 3.11 `uv` environment, remove hard-coded interpreter selection, correct metadata paths, add frozen-output verification, make a code commit, rerun the pipeline, and then make a result commit.

This is the selected approach. It directly addresses reproducibility without reopening the frozen estimators.

### Approach C: Expand inference before freezing

Implement wild cluster bootstrap and regenerate all regression inference before repository cleanup.

This is rejected for P2. The current Ch5, Ch6, Ch7, and Track B metadata already treat event-clustered p-values as descriptive. Adding bootstrap now would reopen the empirical specification and require a new inference validation cycle.

## 3. Scope

### Included

- Repository tracking policy and `.gitignore`.
- Python 3.11 project environment with exact dependency lock.
- Removal of the freeze runner's hard-coded Anaconda interpreter.
- New-path consistency in scripts, metadata, and provenance.
- Frozen-output tests and deterministic replay checks.
- Two-stage Git freeze: code commit followed by result commit.
- Alignment of P1/P2 engineering documents with the chosen descriptive-inference policy.
- A final consistency check against the existing Ch3, Ch5, Ch6, and Ch7 drafts.

### Excluded

- New wild cluster bootstrap estimates.
- New parametric or lognormal-mixture RND estimator.
- Reopening Track A or Track B sample-selection rules.
- New dissertation claims or chapter expansion during the engineering freeze.
- Committing raw data, large processed panels, exploratory outputs, or downloaded literature PDFs.

## 4. Repository Tracking Policy

The repository will track:

- `README.md`, `AGENTS.md`, and environment files.
- `scripts/`, excluding caches and local system files.
- `tests/`, excluding caches.
- `docs/`.
- dissertation source files such as `.tex`, `.bib`, `.md`, and small audit CSV files.
- `paper/tables/*.csv`, `paper/tables/*.tex`, and provenance `.json`/`.md` files.
- `paper/figures/*.pdf`.
- processed-data metadata JSON files needed to interpret frozen outputs.
- the explicit compact Parquet input set needed by the freeze runner, together with a SHA-256 input manifest.

The repository will ignore:

- `data/raw/`.
- processed CSV and Parquet panels other than the explicit freeze-runner input set.
- `result/` and `meeting_materials/`.
- downloaded literature PDFs under `dissertation/literature_review/`.
- `.DS_Store`, Python caches, pytest caches, notebook checkpoints, virtual environments, build artifacts, and archives.

The top-level `data/` directory will not be ignored wholesale. Its large tabular files will be ignored by extension under `data/processed/`, while metadata JSON files and the explicit freeze-runner inputs remain trackable. The compact input set consists of the Track A quality/divergence/comparison/curve/grid inputs and the Polymarket event/event-cell/hourly-distribution plus Deribit bar-quality inputs needed to reconstruct all 30 tables. Its expected size is only a few megabytes, not the full 203 MB data directory.

## 5. Environment Design

`pyproject.toml` is the human-readable dependency declaration and `uv.lock` is the exact machine-readable lock. The project requires Python `>=3.11,<3.12` for the frozen replay.

Runtime dependencies are limited to packages imported by the current scripts:

- matplotlib
- Jinja2, required by pandas LaTeX table rendering
- numpy
- pandas
- pyarrow
- python-dateutil
- requests
- scipy
- statsmodels

The development dependency group contains pytest. The initial constraints should preserve the currently verified package versions where Python 3.11 resolution permits them. `uv sync --python 3.11` creates `.venv`, and all documented commands use `uv run python` or the active environment's `python`.

The freeze runner must use `sys.executable`. It must not prefer `/Users/wanghaozhe/anaconda3/bin/python`, because that would bypass the project environment.

The Track A figure script must select matplotlib's non-interactive `Agg` backend before importing `pyplot`, so PDF generation does not depend on a macOS GUI session.

## 6. Provenance Flow

The freeze follows this order:

1. Complete code, configuration, documentation, and tests.
2. User creates Commit A and records its full hash.
3. Run `uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b` from a clean Commit A checkout. The Track B branch rebuilds K*, PM survival, hourly and 6h Deribit survival, hourly and 6h joined panels, and the 6h diagnostics before provenance.
4. Every regenerated metadata file records Commit A's hash.
5. Regenerate `paper/tables/table_source_metadata.{json,md}` last.
6. Run frozen-output and deterministic replay verification.
7. User creates Commit B containing only final tables, figures, provenance files, and required metadata.

Commit B's generated files intentionally refer to Commit A. A generated file cannot contain the hash of the same commit that contains that file without a recursive-hash problem.

The provenance generator will validate and record:

- exactly 30 table entries;
- script path and script existence;
- input paths and whether each input exists locally;
- metadata path and metadata existence;
- CSV row count;
- LaTeX counterpart existence;
- Commit A hash.

Commands containing script arguments, such as `--bar-hours 6`, must be split into a script path and argument list before checking script existence.

## 7. Frozen Invariants

The fast test suite will assert:

- all provenance script paths start with `scripts/P1_pipeline/` or `scripts/P2_diagnostics/`;
- no provenance or tracked metadata `script_name` uses the legacy `scripts/build_*.py` layout;
- all referenced scripts, local inputs, metadata files, CSV files, and LaTeX files exist;
- the table count is exactly 30;
- provenance row counts equal the actual CSV row counts;
- Track A has 294 main event-days and 61 main events;
- Track B has 1,121 joint-informative rows and 703 regression rows;
- the reference audit has 124 rows and 124 `proxy_assumed` rows;
- the Git hash is a 40-character hexadecimal commit and is not `unavailable_not_git_repo` or null after Commit A.

Deterministic replay is an explicit freeze check rather than a normal unit test because it runs the full empirical pipeline twice. It compares hashes of final table CSV files after excluding metadata timestamps. Any numerical difference fails the freeze.

## 8. Inference Policy

Wild cluster bootstrap will not be implemented in P2. Event-clustered p-values remain in output tables for transparent reporting of the fitted regressions, but they are descriptive diagnostics rather than primary confirmatory inference.

The following must use one consistent statement:

> Event-clustered standard errors and p-values are reported descriptively. No wild cluster bootstrap is implemented, and the coefficients do not identify causal or directional price discovery.

Older roadmap/spec statements that call wild cluster bootstrap the primary inference method must be marked superseded by the frozen P2 decision. Existing dissertation wording should only be changed where it contradicts this policy.

## 9. Failure Handling

- Environment resolution failure stops before Commit A.
- Missing local input files stop the freeze runner before output generation.
- A failed pipeline command stops the runner immediately.
- Missing or stale provenance mappings fail verification.
- Changed frozen counts fail verification and require investigation; tests must not be updated merely to accept new numbers.
- Numerical CSV differences across identical replays fail the deterministic freeze check.
- Commit B must not proceed if metadata does not contain Commit A's hash.

## 10. Completion Criteria

P2 engineering freeze is complete when:

- the Python 3.11 locked environment installs and imports all dependencies;
- a fresh checkout contains the compact frozen inputs required to rebuild all 30 tables;
- unit and frozen-output tests pass;
- Commit A exists on GitHub;
- the full freeze runner completes under the locked environment;
- all 30 tables have current P1/P2 paths and valid provenance;
- required metadata records Commit A;
- two full replays produce numerically identical final CSV tables;
- Commit B exists on GitHub and contains no raw or large processed data;
- the existing dissertation drafts contain no claim that bootstrap inference was implemented.
