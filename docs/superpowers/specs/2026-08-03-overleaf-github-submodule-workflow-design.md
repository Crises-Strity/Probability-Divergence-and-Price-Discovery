# Overleaf--GitHub Dissertation Workflow Design

Date: 2026-08-03

## Objective

Restructure the dissertation area of the main project repository so that Overleaf remains the only normal editing surface for dissertation source, while GitHub and the local main repository provide versioned snapshots, review artifacts, numerical checks, and PDF visual inspection.

The workflow must prevent concurrent editing of the same dissertation source in Overleaf and locally. It must also preserve the current Overleaf export, compiled PDF, screenshots, literature PDFs, and evidence audit without destructive replacement.

## Confirmed external state

- The Overleaf project is linked through GitHub Sync to the private repository `Crises-Strity/UCL-Final-Dissertation`.
- The dissertation repository uses `main` as its default branch.
- Its initial commit is `d05b6c86b8ced810ac47d9ed96bb73b6eba7db36` with message `Initial Overleaf Import`.
- The GitHub source contains `main.tex`, the chapter files, figures, sections, and `references.bib`.
- The local main repository is `Crises-Strity/Probability-Divergence-and-Price-Discovery` and will track the dissertation repository through a Git submodule.
- The current Overleaf PDF was compiled with LuaTeX and contains 56 pages.

## Authority model

### Normal state: Overleaf authoritative

Overleaf is the only place where dissertation `.tex`, `.bib`, and paper-facing figure files are edited. GitHub Sync transports completed Overleaf states to GitHub. The local submodule is pull-only during this state.

Local work may:

- inspect and diff dissertation commits;
- verify citations, labels, numerical claims, and figure provenance;
- inspect exported PDFs and compile logs;
- create review checklists outside the submodule;
- update the parent repository's submodule pointer after a reviewed Overleaf push.

Local work must not modify or push files inside `dissertation/manuscript/` in the normal state.

### Exceptional state: explicit local editing window

If a future task requires an automated local source rewrite, the user must explicitly freeze Overleaf editing and authorize a temporary local editing window. That window must end by pushing the reviewed change to GitHub, pulling it into Overleaf through GitHub Sync, recompiling in Overleaf, and explicitly restoring Overleaf as the authoritative editor. This exception is not part of the initial implementation.

## Repository layout

The parent repository will use this structure:

```text
dissertation/
├── manuscript/                 # Git submodule: UCL-Final-Dissertation
├── literature_review/          # Existing source literature and audit CSV
├── reviews/                    # Tracked local review checklists
├── releases/
│   └── 2026-08-03-initial/
│       ├── dissertation.pdf
│       ├── source.zip
│       ├── logs/               # Compile log files or screenshots
│       └── manifest.json
├── inbox/                      # Temporary Overleaf downloads; ignored by Git
├── evidence_audit.md           # Existing numerical/literature evidence ledger
└── README.md                   # Operating procedure and command reference
```

The existing extracted `dissertation/Dissertation_template/` directory, `Dissertation_template.zip`, and `Dissertation_template.pdf` will first be preserved in the initial release. The extracted directory will not be retained as a second editable copy once the submodule is verified, because two live source trees would undermine the authority rule. No existing literature PDF or evidence file will be discarded.

## Synchronisation flow

### Overleaf-to-local review cycle

1. Edit source only in Overleaf.
2. Compile in Overleaf until the intended checkpoint is reached.
3. In Overleaf GitHub Sync, select **Push Overleaf changes to GitHub** and provide a meaningful commit message.
4. Update `dissertation/manuscript/` locally from GitHub using a fast-forward-only pull.
5. Run local source, evidence, citation, and PDF checks.
6. Write findings to a dated file under `dissertation/reviews/`.
7. Commit the review artifacts and updated submodule pointer in the parent repository.
8. Apply accepted fixes in Overleaf and repeat the cycle.

GitHub webpage editing is excluded from the normal cycle. Raw `git.overleaf.com` push/pull will not be used alongside GitHub Sync, because that would create a second transport path and make the synchronization state harder to reason about.

## Release artifacts

A release snapshot is created for the initial import and for later milestones rather than for every keystroke-level update. Each release contains:

- the source ZIP exported from Overleaf;
- the compiled PDF downloaded from Overleaf;
- `output.log` and other generated logs when downloadable, or clearly named screenshots when not;
- a `manifest.json` containing the dissertation Git commit, export timestamp, PDF page count, compiler when known, SHA-256 hashes of the ZIP/PDF/log artifacts, and review status.

The source ZIP is retained as an external-state snapshot but is not used as the working source tree. The GitHub dissertation commit is the working source snapshot.

## Initial migration

The implementation will:

1. verify the current export artifacts and their hashes;
2. create the release, review, inbox, and documentation structure;
3. preserve the current ZIP, PDF, and compile screenshots in the initial release;
4. add `Crises-Strity/UCL-Final-Dissertation` as the `dissertation/manuscript/` submodule;
5. verify that the submodule commit contains the same expected Overleaf project structure;
6. remove the redundant extracted source copy only after preservation and verification, using a non-destructive move during the migration rather than an unverified deletion;
7. add a focused `.gitignore` rule for transient inbox and LaTeX auxiliary files;
8. create an initial compile-review checklist from the supplied PDF and screenshots.

## Initial compile-review scope

The first review checklist will record, without silently editing the authoritative source:

- the undefined `\mathbb` command in Chapter 2, caused by missing `amsfonts` or `amssymb` support;
- duplicate package declarations in `main.tex`;
- the `fancyhdr` `\headheight` warning;
- the long Chapter 2 title and section title overfull boxes;
- the Chapter 2 research-question table width and underfull boxes;
- the Chapter 4 API identifier overflow in the data-source table;
- default `hyperref` link borders visible in the compiled PDF;
- placeholder dissertation title, abstract, acknowledgements, appendix, and project summary content;
- spelling and spacing issues on the title/disclaimer pages, including `Acadamic` and missing spaces after full stops.

Each finding will identify the source file and line, severity, observed evidence, and proposed Overleaf-side correction.

## Failure and conflict handling

- If GitHub contains a commit not known to Overleaf, stop the cycle and inspect it before pressing Pull or Push in Overleaf.
- If the local submodule is dirty, do not pull or reset it. Report the modified paths and determine whether an unauthorized local editing window occurred.
- If a submodule update is not fast-forward, stop and inspect both histories; do not force-push or rewrite either history.
- If the exported PDF commit cannot be identified, mark the release manifest as `commit_unverified` rather than guessing.
- If a compile log cannot be downloaded, store the complete supplied screenshots and record that the log evidence is partial.
- If source ZIP contents differ from the corresponding GitHub commit, preserve both artifacts, record the mismatch, and do not overwrite either version.

## Verification requirements

The initial implementation is complete only when:

- `git submodule status dissertation/manuscript` resolves to the expected dissertation commit;
- the submodule remote is the dedicated dissertation repository;
- `main.tex`, all eight chapters, sections, three figures, and `references.bib` exist in the submodule;
- the initial ZIP, PDF, screenshots, and manifest exist in the release directory;
- the PDF page count and SHA-256 hashes are recorded from the actual files;
- the parent repository contains no second live editable copy of the Overleaf source;
- the README documents the routine sync commands and the authority rule;
- the initial review checklist contains every confirmed compile or layout issue listed above;
- unrelated untracked files and existing project work are not staged or committed.

Local LaTeX compilation is not required for the migration because the current environment has no TeX engine. Overleaf remains responsible for compilation, while local PDF rendering is used for visual verification.

## Out of scope

- Editing the dissertation source during the migration.
- Fixing the current LaTeX errors directly in the local submodule.
- Configuring GitHub Actions or a local TeX distribution.
- Rewriting dissertation repository history.
- Migrating the literature archive into the dissertation submodule.
- Storing raw research data or pipeline outputs in the dissertation repository.
