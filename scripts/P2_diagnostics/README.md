# P2 Diagnostics Scripts

Purpose: run robustness, audit, provenance, and freeze checks around the P1 empirical result set.

This stage should not silently change P1 methodology. It documents whether the frozen result set is reproducible, defensible, and ready for dissertation writing.

Typical outputs:

- `data/processed/panels/reference_basis_audit.*`
- `paper/tables/table_source_metadata.*`
- `paper/tables/tab_reference_basis_audit_summary.*`

Project freeze commands:

```bash
uv run python scripts/P2_diagnostics/build_frozen_input_manifest.py
uv run python scripts/P2_diagnostics/run_p1_freeze.py --include-track-b
uv run python scripts/P2_diagnostics/verify_p2_freeze.py --expected-git-commit <commit-a-hash>
```

The full runner reconstructs Track A diagnostics, the reference audit, all
Track B hourly and 6h paper tables, and provenance. Generated metadata must
record the code-only Commit A; final artifacts are committed separately in
Commit B.
