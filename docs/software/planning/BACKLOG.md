# Unscheduled software backlog

This file is reserved for accepted implementation work that is not already assigned to an active or planned sprint.

The Version 3 sequence is defined in [sprints/v3/README.md](sprints/v3/README.md), and the current execution document is [ACTIVE_SPRINT.md](ACTIVE_SPRINT.md). Version 2 remains a frozen historical lineage ([sprints/v2/README.md](sprints/v2/README.md)).

## Current backlog

- **Version 3 contracts (active):** Sprint V3.0 architecture deliverables under [sprints/v3/](sprints/v3/). No production campaign, obstacle, OMPL, MoveIt, or higher-DOF implementation until contracts are accepted.
- **V2 HTML run printout (evaluation tooling):** implemented beside the V2 runner (`v2_canvas.py`, `scripts/generate_v2_canvas.py`). Keep regenerable; do not treat as a substitute for V2.7.
- **Experiment B production promotion:** V2.12 smoke, V2B-005 calibration tooling, and regenerable HTML printouts are recorded, but population inference remains **held** under the V3 pivot. Do not activate production orchestration opportunistically. Protocol: [Experiment B](../experiments/protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md). Sprint: [V2.12](sprints/v2/SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md).
- **Experiment B exact-start control:** nearest-node start attachment is retained by the V2B-005 start-attachment decision (`retain_nearest_node_v1`) as a V2 formulation artifact; V3 removes `start_tolerance` as task semantics (ADR-023 proposed).
- **Experiment A task-set diagnostic:** deferred and low-confidence. Preserve as a separate Q-spanner diagnostic identity under V3; do not merge with Cartesian application estimands. See [project note](../architecture/notes/PROJECT_NOTE_EXPERIMENT_A_TASK_SET_EFFECT.md).
- **Sprint V2.7 (3R):** held until Version 3 contracts and the higher-DOF roadmap (V3.8+) are activated. See [sprints/v2/SPRINT_V2_7_3R_EXTENSION.md](sprints/v2/SPRINT_V2_7_3R_EXTENSION.md).

## Intake rules

Add an item only when:

1. the work is accepted but does not belong in an existing Version 3 (or frozen Version 2) sprint;
2. its architecture dependencies are identified;
3. its scientific or engineering purpose is explicit;
4. its tests and exit criteria can be stated;
5. it does not silently revive a superseded Version 1 or Version 2 formulation assumption as a universal claim.

Use a stable issue identifier and link the relevant ADR, contract, protocol, or sprint dependency.

## Historical work

The former completed Version 1 backlog was removed from the active planning surface. Version 1 execution history remains in [sprints/v1/](sprints/v1/) and in Git history. Version 2 sprint history remains in [sprints/v2/](sprints/v2/). Unfinished Version 2 production ideas must be re-evaluated under Version 3 contracts rather than copied forward automatically.
