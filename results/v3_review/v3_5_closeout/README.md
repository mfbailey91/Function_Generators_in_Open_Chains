# Version 3 review snapshot — V3.5 closeout

This directory is a **bounded smoke/parity review artifact**, not a production population study or Monte Carlo result.

- Code revision: `4e37d6cbaebedf53a15821d301eea77d6e97df49`
- Generated UTC: `2026-08-07T08:19:49.710573+00:00`
- OMPL version: `2.0.1`
- Frozen smoke seed: `7`
- OMPL solve budget per query: `5.0` s
- Snapshot validation: `PASS`

## Included suites

| suite                   | rows | status counts                |
| ----------------------- | ---- | ---------------------------- |
| v3_2_direct_smoke       | 12   | {"invalid": 4, "success": 8} |
| v3_3_lattice_smoke      | 13   | {"success": 13}              |
| v3_4_sampling_smoke     | 8    | {"success": 8}               |
| v3_5_ompl_native_parity | 8    | {"success": 8}               |

## OMPL/native parity

| task                      | mechanism | OMPL             | native      | OMPL status | native status | same class |
| ------------------------- | --------- | ---------------- | ----------- | ----------- | ------------- | ---------- |
| fourbar_already_satisfied | fourbar   | ompl_prm         | prm         | success     | success       | yes        |
| fourbar_already_satisfied | fourbar   | ompl_rrt_connect | rrt_connect | success     | success       | yes        |
| fourbar_planning_feasible | fourbar   | ompl_prm         | prm         | success     | success       | yes        |
| fourbar_planning_feasible | fourbar   | ompl_rrt_connect | rrt_connect | success     | success       | yes        |
| gearbox_already_satisfied | gearbox   | ompl_prm         | prm         | success     | success       | yes        |
| gearbox_already_satisfied | gearbox   | ompl_rrt_connect | rrt_connect | success     | success       | yes        |
| gearbox_planning_feasible | gearbox   | ompl_prm         | prm         | success     | success       | yes        |
| gearbox_planning_feasible | gearbox   | ompl_rrt_connect | rrt_connect | success     | success       | yes        |

Full row-level data are stored beside this README:

- `v3_2_direct_smoke.json`
- `v3_3_lattice_smoke.json`
- `v3_4_sampling_smoke.json`
- `v3_5_ompl_native_parity.json`
- `manifest.json`

Regenerate with:

```bash
PYTHONPATH=src python scripts/export_v3_review_results.py
```
