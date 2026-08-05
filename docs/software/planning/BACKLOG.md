# Unscheduled software backlog

This file is reserved for accepted implementation work that is not already assigned to an active or planned sprint.

The Version 2 sequence is defined in [sprints/v2/README.md](sprints/v2/README.md), and the current execution document is [ACTIVE_SPRINT.md](ACTIVE_SPRINT.md).

## Current backlog

- **V2 HTML run printout (evaluation tooling):** implemented beside the V2 runner (`v2_canvas.py`, `scripts/generate_v2_canvas.py`). Keep regenerable; do not treat as a substitute for V2.7.
- **Experiment B / Sprint V2.12 — 2R Cartesian goal-region planning:** accepted conceptual design, held. Prerequisites before activation: [ADR-019 Cartesian domain](../architecture/adr/ADR-019-v2-cartesian-task-domain.md), [ADR-020 goal-set search](../architecture/adr/ADR-020-v2-goal-set-search.md), and [crossed statistics](../architecture/notes/PROJECT_NOTE_EXPERIMENT_B_CROSSED_STATISTICS.md). Protocol: [Experiment B](../experiments/protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md). Sprint: [V2.12](sprints/v2/SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md).
- **Experiment A task-set diagnostic:** deferred and low-confidence. A* already failed the first persistence check for `medium_diagonal`. Do not promote into a claim or into Experiment B's primary domain. See [project note](../architecture/notes/PROJECT_NOTE_EXPERIMENT_A_TASK_SET_EFFECT.md).
- **Sprint V2.7 (3R):** deferred pending review of trusted 2R Dijkstra + A* solver evidence. Unchanged by the held Experiment B stage. See [sprints/v2/SPRINT_V2_7_3R_EXTENSION.md](sprints/v2/SPRINT_V2_7_3R_EXTENSION.md).

## Intake rules

Add an item only when:

1. the work is accepted but does not belong in an existing Version 2 sprint;
2. its architecture dependencies are identified;
3. its scientific or engineering purpose is explicit;
4. its tests and exit criteria can be stated;
5. it does not silently revive a superseded Version 1 assumption.

Use a stable issue identifier and link the relevant ADR, contract, protocol, or sprint dependency.

## Historical work

The former completed Version 1 backlog was removed from the active planning surface. Version 1 execution history remains in [sprints/v1/](sprints/v1/) and in Git history. Unfinished Version 1 ideas should be re-evaluated and accepted as new Version 2 work rather than copied forward automatically.
