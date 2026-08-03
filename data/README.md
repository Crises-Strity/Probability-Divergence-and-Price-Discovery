# Data Policy

`data/raw/` and bulk generated panels are intentionally excluded from Git.

The repository tracks only the compact processed Parquet inputs required by
`scripts/P2_diagnostics/run_p1_freeze.py --include-track-b`. Their hashes,
sizes, row counts, and schemas are recorded in
`data/processed/frozen_input_manifest.json`.

The tracked inputs reproduce the frozen paper tables and figures. They do not
reproduce the original API collection step, because historical public-market
API responses can change after the project snapshot date.
