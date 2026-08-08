# Version 3 configs

Frozen Version 3 task banks and runner inputs live here. They are external to
planner implementations and must not fuse graph, objective, and planner into
one experiment runner (see `docs/software/planning/sprints/v3/README.md`).

## Banks

| File | Sprint | Role |
| --- | --- | --- |
| [`free_space_planar2r_v1.json`](free_space_planar2r_v1.json) | V3.6 pilot | Original bounded bank. Preserved as provenance; its normalized actuator starts produce different physical starts across mechanisms. |
| [`free_space_planar2r_v2.json`](free_space_planar2r_v2.json) | V3.6 corrective | Corrected evidence contract. Resolves each authoring start through a reference arm into one shared `q` / Cartesian start, freezes a finite Cartesian-disk goal representation, and declares stochastic repetition seeds. |

`v1` is not rewritten. The corrected V3.6 closeout candidate is `v2`.
