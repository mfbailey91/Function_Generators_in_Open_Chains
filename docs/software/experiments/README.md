# Experiment documentation

Experiment documentation is separate from architecture and sprint execution.

- `protocols/` defines controlled comparisons and invariants.
- `schemas/` explains human-readable config and result contracts; Python remains the executable validator.
- `reports/` interprets accepted completed runs and links to immutable results.

Current task-definition documents:

- [`EXPERIMENT_A_CENTERED_Q_PROBES.md`](protocols/EXPERIMENT_A_CENTERED_Q_PROBES.md) — completed V2.10 Dijkstra and V2.11 A* centered canonical probes.
- [`EXPERIMENT_B_CARTESIAN_GOAL_REGION.md`](protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md) — accepted future 2R position-only Cartesian planning design; Sprint V2.12 held.

Complete run packages remain under `results/` or `diagnostics/`. Campaign summaries, selected figures, and checked-in Monte Carlo artifacts may live under `docs/software/experiments/reports/` or `docs/artifacts/`; do not copy entire production trees into `docs/`.
