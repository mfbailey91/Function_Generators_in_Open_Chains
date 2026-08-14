# Version 3 configs

Frozen Version 3 task banks and runner inputs live here. They are external to
planner implementations and must not fuse graph, objective, and planner into
one experiment runner (see `docs/software/planning/sprints/v3/README.md`).

## Banks

| File | Sprint | Role |
| --- | --- | --- |
| [`free_space_planar2r_v1.json`](free_space_planar2r_v1.json) | V3.6 pilot | Original bounded bank. Preserved as provenance; its normalized actuator starts produce different physical starts across mechanisms. |
| [`free_space_planar2r_v2.json`](free_space_planar2r_v2.json) | V3.6 corrective | Corrected evidence contract. Resolves each authoring start through a reference arm into one shared `q` / Cartesian start, freezes a finite Cartesian-disk goal representation, and declares stochastic repetition seeds. |
| [`free_space_planar3r_v1.json`](free_space_planar3r_v1.json) | V3.7 | Planar 3R free-space bank. Author `start_u_frac` on the four-bar reference; loaders resolve one shared `q` / tip / heading for paired arms. Includes position-only (frozen φ grid × disk samples) and full-pose SE(2) tasks. |

`v1` is not rewritten. The corrected V3.6 closeout candidate is `v2`. V3.7 adds a separate 3R bank rather than extending the 2R JSON.

## Audits / closeout

| File | Sprint | Role |
| --- | --- | --- |
| [`planar2r_visual_audit_v1.json`](planar2r_visual_audit_v1.json) | V3.6B | Planar 2R visual-audit contract (frozen corpus; report under `results/v3_review/v3_6b_planar2r_visual_audit/`). |
| [`planar2r_closeout_v1.json`](planar2r_closeout_v1.json) | V3.6C | Planar 2R free-space closeout contract; output only under `results/v3_review/v3_6c_planar2r_closeout/`. |
