# Version 3 migration map

**Status:** Sprint V3.0 deliverable (V3-008)  
**Reference:** [V3_PROJECT_PLAN.md](../../V3_PROJECT_PLAN.md) §15, [V3_CODE_INVENTORY.md](V3_CODE_INVENTORY.md), [V2_EVIDENCE_FREEZE.md](../../experiments/reports/V2_EVIDENCE_FREEZE.md)  
**Code authorization:** none in V3.0 — this document specifies adapters and a compatibility fixture; implementation begins in V3.1+

## Principle

Use a strangler migration. Preserve frozen Version 2 modules. Add Version 3 core beside them. Wrap before rewrite. Never silently recompute or reinterpret Version 2 results under Version 3.

## Sequence

| Step | Action | Sprint gate |
| --- | --- | --- |
| 1 | Freeze and tag trusted V2 evidence revision | V3.0 (done: freeze doc; tag when accepted) |
| 2 | Preserve V2 configs, runners, reports, and schemas as historical experiments | V3.0+ |
| 3 | Add V3 core interfaces beside existing modules (`PhysicalState`, robot, scene, goals, local motion, objective, planner, result) | V3.1 |
| 4 | Wrap certified V2 mechanism branches as V3 `RobotModel` transmission components | V3.1 |
| 5 | Wrap existing Dijkstra and A* as V3 planner adapters before rewriting them | V3.1 |
| 6 | Reproduce one known V2 case through V3 adapters (compatibility fixture) | V3.1 exit |
| 7 | Build free-space Cartesian vertical slice with exact start and direct planners | V3.2 |
| 8 | Lattice / local-motion validation (8-connected, integrated cost) | V3.3 |
| 9 | Native roadmap and tree planners | V3.4 |
| 10 | OMPL adapter before MoveIt | V3.5 → V3.10 |
| 11 | Return to production campaigns only after V3 benchmark gates pass | V3.11 |

## Inventory → first adapter touchpoints

| Inventory class | First V3 touchpoint |
| --- | --- |
| reusable unchanged: `search/{protocol,core,result,graph_solver}` | Consumed by lattice/graph planner adapters; no move |
| reusable unchanged: Mechanism protocol, `OutputSpace`, `planar_2r` | Compose into `RobotModel` |
| adapter: `EmbeddedPlanningGraph`, `v2_objectives` | Lattice planner backend + objective adapter |
| adapter: `dijkstra` / `astar` façades | `Planner` implementations declaring ADR-025 capabilities |
| adapter: V2 config/result schemas | Historical loaders only; new V3 schema discriminator |
| refactor: `OperatingBranch` | Keep V2 path; generalize only when a V3 robot needs it |
| refactor: `query_overlay`, Cartesian attachment | Exact-start query connection (ADR-023); drop task-semantic `start_tolerance` |
| legacy-only: V1 graphs/objectives/sprint runners | Reproduction only |
| diagnostic lineage: Experiment A Q-spanner (`v2_tasks.py`) | Separate diagnostic protocol under ADR-026 |

Do not reorganize toward the target source tree in the V3 plan until a move adds architectural value. Prefer new packages (`core/`, `planners/`, `adapters/`) beside stable modules.

## Compatibility fixture specification

### Purpose

Prove that Version 3 adapters around existing mechanism and search implementations agree with the frozen Version 2 stack where semantics are identical.

### Fixture identity (single required case)

One deterministic shared-Q paired unit case on a certified monotonic crank-rocker vs span-matched gearbox:

| Field | Requirement |
| --- | --- |
| Graph | Small uniform-\(\mathcal Q\) embedded graph (prefer an existing V2 shared-Q smoke/fixture scale) |
| Objective | `actuator_travel` / integrated or V2-equivalent endpoint cost **declared explicitly** |
| Query | Single start node and single goal node already on the lattice (no Cartesian attachment ambiguity) |
| Solvers | Dijkstra and A* with the ADR-018/020 heuristic pair used by V2 |
| Mechanisms | One four-bar operating branch and one equivalent-gain gearbox on the shared Q graph |

Prefer reusing an existing fixture under `experiments/v2_shared_q_fixtures.py` or a golden-scale subset rather than inventing a new numerical oracle.

### Agreement criteria

Run the same declared case through:

1. the frozen Version 2 stack;
2. Version 3 adapters that wrap the same mechanism maps and search core.

They must agree on:

- declared physical states at start and selected goal (`q`, `u`, branch id);
- path cost under the declared objective definition;
- selected goal identity;
- search instrumentation that shares semantics (expansions, generated, reopened) within exact integer equality for deterministic identical graphs.

Explicitly **out of scope** for the first fixture:

- Cartesian nearest-node `start_tolerance` attachment (V2-only formulation artifact);
- stochastic planners;
- obstacle scenes;
- reinterpretation of Monte Carlo population estimands.

### Pass / fail

| Check | Rule |
| --- | --- |
| Cost | Exact float equality within the existing V2 test tolerance used for Dijkstra/A* parity |
| Path node sequence | Equal under the declared graph identity, or equal cost with documented alternate optimal path only if V2 already allows ties—prefer fixtures without cost ties |
| Selected goal | Identical |
| Expansions | Identical for the same algorithm on the same graph |
| Provenance | Both runs record architecture version and code revision |

### Delivery

Implement the fixture as a test module in Sprint V3.1 (for example `tests/v3/test_v2_compatibility_fixture.py`) once adapters exist. This map only freezes the fixture contract.

## Held until later gates

- Version 2 Cartesian production inference and new Monte Carlo campaigns
- Obstacles, OMPL, MoveIt, 3R/4R/5R/6R implementation
- Repository-wide renames or deletion of legacy-only modules
- Any claim that V3 free-space results supersede V2.10/V2.11 without a separate diagnostic study

## Acceptance for V3.0

This migration map is accepted when reviewers agree that:

1. the strangler sequence matches the V3 project plan;
2. the compatibility fixture is specific enough to implement in V3.1;
3. inventory classes have clear first touchpoints;
4. no production or obstacle work is activated by accepting the map.
