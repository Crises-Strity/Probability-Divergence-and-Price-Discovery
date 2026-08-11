# Frozen Repository Cleanup Design

**Date:** 2026-08-11
**Status:** Approved for implementation planning

## Goal

Convert the frozen parent repository into a self-contained empirical project
repository. The dissertation must live outside the project repository, the
README must report the final P0--P3 status and frozen conclusions, and the
roles of tracked data and `configs/` must be explicit.

## Constraints

- Do not change the frozen empirical specification or rerun exploratory work.
- Do not fabricate or update reported results without generated evidence.
- Preserve all local dissertation material before removing it from the parent
  repository.
- Do not add literature PDFs to either Git repository.
- Do not modify the dissertation repository's manuscript contents.
- Preserve unrelated user changes, including current untracked P3 planning
  documents and `tmp/` files.

## Repository Boundary

The parent repository will no longer contain a dissertation submodule or any
`dissertation/` files. Remove the tracked `.gitmodules` file, the
`dissertation/manuscript` gitlink, and the tracked dissertation workflow,
review, evidence, and release artifacts from the parent repository.

Before removal, create and verify two independent local destinations:

1. `/Users/wanghaozhe/Desktop/UCL-Final-Dissertation` -- a standalone clone of
   `https://github.com/Crises-Strity/UCL-Final-Dissertation.git`, retaining the
   current manuscript commit `19b48731492affabec5488b98d1819baeed69ba6` on
   `main`.
2. `/Users/wanghaozhe/Desktop/UCL-Final-Dissertation-support-20260811` -- local,
   unversioned support material from the parent `dissertation/` directory,
   including literature PDFs, the literature audit, evidence audit, reviews,
   and archived release artifacts.

The existing submodule checkout cannot simply be moved because its `.git`
file points into the parent repository's submodule metadata. The standalone
clone must have its own Git directory and the expected GitHub remote. Removal
from the parent occurs only after both destinations have been checked.

## Data Policy

Keep the existing compact frozen input package under `data/processed/`. It is
approximately 2.8 MB and is required by the one-command freeze rebuild. The
package is not raw market data: its files are bounded reproducibility inputs
whose hashes, sizes, row counts, and schemas are recorded in
`data/processed/frozen_input_manifest.json`.

Continue excluding:

- all `data/raw/` content;
- bulk or non-frozen processed panels;
- transient downloads and exploratory result directories.

The root README and `data/README.md` must distinguish this deliberate compact
exception from the general rule that raw and bulk research data do not belong
in Git.

## Configuration and Planning Policy

Keep `configs/p3_track_a_extension.json` at its current path. It is an
executable, version-controlled parameter source read by the P3 scripts and
tests; it is not a planning document.

Add `configs/README.md` explaining:

- why the directory currently contains only P3 configuration;
- that P0--P2 used their existing CLI and implementation parameters;
- that the frozen project will not manufacture retrospective P0--P2 config
  files merely for visual symmetry;
- that roadmaps, specifications, implementation plans, and decision records
  remain under `docs/`.

Do not relocate the JSON or change P3 interfaces, because that would add risk
without changing the frozen evidence.

## Root README Design

Rewrite the root README as the entry point to a frozen empirical project. It
must contain:

1. the research question and conservative interpretation boundary;
2. the final P0--P3 status;
3. the frozen Track A and Track B conclusions;
4. the P3 SOL stopping decision;
5. an accurate repository tree with `configs/` and P3, and without
   `dissertation/`;
6. the compact-data exception and raw-data exclusion policy;
7. reproducible environment, rebuild, verification, and test commands;
8. a short dissertation workflow that links the dedicated GitHub repository
   and states `Overleaf -> GitHub -> standalone local clone`;
9. the project's final frozen status and non-claims.

The README will report only values already frozen in decision logs and
generated metadata. Its core empirical message is:

- distribution centers align;
- the Polymarket-wide spread result is conditional on low-to-moderate RND
  smoothing;
- tail relative divergence remains material;
- six-hour contemporaneous integration is supported;
- directional price discovery is unidentified with current Deribit OHLC
  liquidity;
- none of these results establishes executable arbitrage;
- the SOL extension failed its pre-estimator continuation gate and stopped.

## Migration Sequence

1. Check the current parent and submodule state.
2. Create the independent dissertation clone and verify its remote, branch,
   commit, and clean status.
3. Copy the non-manuscript dissertation support material to the local support
   directory and compare the source and destination inventories.
4. Remove the dissertation gitlink, `.gitmodules`, and tracked dissertation
   artifacts from the parent repository without touching unrelated changes.
5. Update `.gitignore` to remove obsolete dissertation-specific rules.
6. Add `configs/README.md` and update the root and data READMEs.
7. Run all verification checks.

## Verification

Completion requires evidence for all of the following:

- the standalone dissertation clone uses the expected GitHub remote, branch,
  and commit and is clean;
- the support directory contains the preserved non-manuscript files;
- `git ls-files` in the parent reports neither `.gitmodules` nor any
  `dissertation/` path;
- no root README path points to removed project files;
- the frozen input manifest verification succeeds;
- the strict freeze verifier succeeds;
- the full pytest suite succeeds;
- `git diff --check` succeeds;
- unrelated pre-existing working-tree changes remain untouched.

## Out of Scope

- Editing or compiling the dissertation.
- Changing the dedicated dissertation repository.
- Uploading literature or raw market data.
- Refactoring P0--P3 configuration interfaces.
- Re-estimating results or reopening the empirical specification.
- Deleting Git history that previously contained dissertation artifacts.
