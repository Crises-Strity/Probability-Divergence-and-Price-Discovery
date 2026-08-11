# Data Policy

Raw API responses under `data/raw/` and bulk generated panels are intentionally
excluded from Git.

The repository deliberately tracks 11 compact processed Parquet inputs,
approximately 2.8 MB in total, required by
`scripts/P2_diagnostics/run_p1_freeze.py --include-track-b`. This is a bounded
reproducibility package, not a raw-data archive.

`data/processed/frozen_input_manifest.json` records each tracked input's
SHA-256 hash, byte size, row count, and ordered schema. The strict P2 verifier
checks the files against that manifest.

The compact package reproduces the frozen paper tables and figures. It cannot
reproduce the original API collection step because historical public-market
responses may change after the project snapshot date.
