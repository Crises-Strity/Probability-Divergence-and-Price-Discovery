# Dissertation workflow

## Source of truth

Overleaf is the only normal editor for files in `manuscript/`. GitHub Sync
carries completed Overleaf checkpoints to
`Crises-Strity/UCL-Final-Dissertation`; this parent repository records the
reviewed submodule commit.

Do not edit the manuscript locally, on the GitHub web interface, or through
the raw `git.overleaf.com` remote during the normal workflow.

## Routine update

1. Finish the edit and compile in Overleaf.
2. Push Overleaf changes to GitHub with a meaningful message.
3. Confirm that the local submodule is clean.
4. Fast-forward the submodule from GitHub.
5. Run local source, evidence, citation, and PDF checks.
6. Record findings under `reviews/`.
7. Commit the review and updated submodule pointer in the parent repository.
8. Apply accepted changes in Overleaf.

```bash
git -C dissertation/manuscript status --short
git -C dissertation/manuscript pull --ff-only origin main
git add dissertation/manuscript dissertation/reviews
git commit -m "docs: review dissertation checkpoint YYYY-MM-DD"
```

## Stop conditions

Stop without resetting or force-pushing if the submodule is dirty, a pull is
not fast-forward, GitHub contains an unexpected commit, or a release ZIP
differs from the corresponding dissertation commit. Preserve both versions
and record the mismatch before doing anything else.

## Release checkpoint

Milestone releases live under `releases/YYYY-MM-DD-label/` and contain the
Overleaf source ZIP, compiled PDF, full compile log when available (otherwise
complete screenshots), and a manifest with SHA-256 hashes, page count,
compiler, dissertation commit, and review status.

The source ZIP is an immutable handoff artifact, not an editable source tree.
If its contents cannot be matched exactly to a dissertation commit, set
`dissertation_commit` to `null`, record `commit_status` as
`commit_unverified`, and describe the difference in the manifest.

## Editing-authority exception

A local manuscript edit requires an explicit Overleaf freeze and user
authorization. After the local change is reviewed and synchronized through
GitHub, Overleaf must pull it, compile it, and be explicitly restored as the
authoritative editor.
