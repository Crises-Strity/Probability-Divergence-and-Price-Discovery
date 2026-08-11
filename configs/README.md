# Runtime Configuration

This directory contains version-controlled parameters consumed directly by
project scripts. It is not a planning directory.

`p3_track_a_extension.json` is the frozen source configuration for the P3 SOL
feasibility extension. P3 externalized its continuation gates, inherited Track
A parameters, API endpoints, and output paths so the feasibility decision can
be reproduced without editing code.

P0--P2 retain their existing command-line and implementation parameters.
Because the project is frozen, retrospective config files are not being
created solely for directory symmetry.

Roadmaps, specifications, implementation plans, and empirical decisions live
under `docs/`.
