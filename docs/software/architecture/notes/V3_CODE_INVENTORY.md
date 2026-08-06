# Version 3 code inventory

**Status:** Sprint V3.0 deliverable (V3-001)  
**Package root:** `src/inequality_mechanisms/`  
**Reference:** [V3_PROJECT_PLAN.md](../../V3_PROJECT_PLAN.md), [V2_EVIDENCE_FREEZE.md](../../experiments/reports/V2_EVIDENCE_FREEZE.md)  
**Code authorization:** none — classification only; no module moves in V3.0

Fate labels:

| Label | Meaning |
| --- | --- |
| **reusable unchanged** | Keep as-is; V3 may call directly |
| **reusable through adapter** | Wrap behind V3 interfaces without rewriting core logic first |
| **requires refactor** | Semantics must change for V3 contracts (exact start, continuous local motion, etc.) |
| **legacy-only** | Preserve for V1/V2 reproduction; not a V3 building block |
| **obsolete after migration** | Candidate for eventual removal only after V3 adapters and fixtures replace call sites |

Classifications are migration guidance, not deletion orders. Stable Version 2 modules must not be moved merely to match the target tree in the V3 plan.

---

## 1. Mechanisms and operating branches

| Fate | Path | Responsibility | ADRs |
| --- | --- | --- | --- |
| reusable unchanged | `mechanisms/base.py` | Abstract `Mechanism` + serialization registry | 002 |
| reusable unchanged | `mechanisms/gearbox.py` | Fixed-ratio / unit / equivalent-gain maps | 002, 012 |
| reusable unchanged | `mechanisms/fourbar.py` | Planar four-bar Freudenstein maps | 003 |
| reusable unchanged | `mechanisms/population.py` | Crank-rocker Monte Carlo sampling | 009 |
| reusable unchanged | `mechanisms/equivalence.py` | Equivalent-gain matching | 012 |
| requires refactor | `mechanisms/operating_branch.py` | Certified 1–1 branch + inverse; currently square / axis-separable | 014 |
| requires refactor | `mechanisms/branch_selection.py` | Four-bar → `OperatingBranch` selection | 014 |
| legacy-only | `mechanisms/monotonic.py` | Pre-V2 `MonotonicSector` / Q-grid control | — |
| legacy-only | `mechanisms/_testing.py` | Test doubles | — |

**V3 note:** Wrap certified branches as `RobotModel` transmission components before generalizing branch geometry.

---

## 2. Spaces and kinematics

| Fate | Path | Responsibility | ADRs |
| --- | --- | --- | --- |
| reusable unchanged | `spaces/output_space.py` | Canonical Q chart, distance, bounds | 011 |
| reusable unchanged | `spaces/limits.py` | Shared output joint limits | 004 |
| reusable unchanged | `kinematics/planar_2r.py` | Planar 2R forward kinematics | 019 |

---

## 3. Output-state graphs and topology

| Fate | Path | Responsibility | ADRs |
| --- | --- | --- | --- |
| reusable unchanged | `graphs/topology.py` | Dimension-free `TensorGridTopology` | 015 |
| reusable unchanged | `graphs/sampling.py` | Sampling provenance records | 015 |
| reusable unchanged | `graphs/transitions.py` | V2 branch-local `EdgeTraceV2` (no wrap) | 015 |
| reusable through adapter | `graphs/embedded.py` | V2 `EmbeddedPlanningGraph` (Q identity + U realization) | 014, 015 |
| reusable through adapter | `graphs/pair_invariants.py` | Shared-Q pair invariant checks | 017 |
| reusable through adapter | `graphs/adapters.py` | V1 graphs → `SearchGraph` protocol | 015 |
| requires refactor | `graphs/query_overlay.py` | Exact query nodes on uniform-Q lattices (V2.6); start attachment still lattice-centric | 015 |
| legacy-only | `graphs/grid.py` | V1 `PeriodicGrid2D` | 001 |
| legacy-only | `graphs/validation.py` | V1 `ConstrainedInputGraph` + edge validity | 001, 004 |
| legacy-only | `graphs/output_grid.py` | `MonotonicOutputGraph` experimental control | 001 |
| legacy-only | `graphs/edge_trace.py` | V1 edge microscope / shared traces | 004 |
| legacy-only | `graphs/costs.py` | V1 edge-cost builders | 011 |

**V3 note:** Graph adjacency selects candidate neighbors; it does not define continuous local motion (ADR-024).

---

## 4. Query overlays, tasks, and Cartesian attachment

| Fate | Path | Responsibility | ADRs |
| --- | --- | --- | --- |
| requires refactor | `experiments/v2_cartesian_tasks.py` | Area-uniform Cartesian bank + nearest-node start attach (`start_tolerance`) | 019 |
| requires refactor | `experiments/v2_cartesian_goal_region.py` | Smoke / calibration / gate runner | 019, 020 |
| requires refactor | `experiments/v2_cartesian_calibration.py` | Radius/resolution calibration (V2B-005) | 019 |
| reusable through adapter | `experiments/v2_cartesian_canvas.py` | HTML printout for B packages | — |
| legacy-only (diagnostic lineage) | `experiments/v2_tasks.py` | Centered normalized-Q probes (Experiment A / Q-spanner) | 017 |
| requires refactor | `graphs/query_overlay.py` | Exact overlay for lattice/roadmap query attachment | 015 |

**V3 note:** Remove `start_tolerance` as a task parameter. Exact start is physical-state semantics; attachment residual is an algorithm diagnostic (ADR-023).

---

## 5. Objectives and heuristics

| Fate | Path | Responsibility | ADRs |
| --- | --- | --- | --- |
| reusable through adapter | `search/v2_objectives.py` | V2 cost/heuristic registry + goal-set `input_euclidean_goal_set` | 017, 018, 020 |
| reusable unchanged | `search/heuristic_quality.py` | Exact cost-to-go / heuristic quality diagnostics | — |
| reusable unchanged | `search/cost_to_go.py` | Cost-to-go utilities | — |
| legacy-only | `search/objectives.py` | V1 objective registry | 011 |
| legacy-only | `search/heuristics.py` | V1 Q/U/hop heuristics | 011 |

---

## 6. Dijkstra / A* core

| Fate | Path | Responsibility | ADRs |
| --- | --- | --- | --- |
| reusable unchanged | `search/protocol.py` | `SearchGraph`, `EdgeCost`, `Heuristic`, `GoalTest` | 005, 020 |
| reusable unchanged | `search/core.py` | Generic best-first; single goal / set / predicate | 005, 020 |
| reusable unchanged | `search/result.py` | `SearchResult` + `selected_goal_node_id` | 005, 020 |
| reusable unchanged | `search/graph_solver.py` | Narrow production solver façade | 020 |
| reusable through adapter | `search/dijkstra.py` | Thin Dijkstra entry | 005 |
| reusable through adapter | `search/astar.py` | Thin A* entry | 005 |
| reusable through adapter | `search/v1_compat.py` | V1 wrappers over core | 001, 015 |

**V3 note:** First V3 planner adapters wrap these modules rather than rewriting them.

---

## 7. Metrics and analysis

| Fate | Path | Responsibility |
| --- | --- | --- |
| reusable unchanged | `metrics/path_metrics.py`, `path_quality.py`, `expansions.py`, `savings.py` | Length / quality / expansion utilities |
| reusable unchanged | `metrics/bootstrap.py`, `hierarchical_bootstrap.py` | Resampling statistics |
| reusable unchanged | `metrics/descriptors.py`, `equal_cost_paths.py` | Task/path descriptors |
| reusable through adapter | `experiments/v2_paired_metrics.py` | Paired mechanism effect metrics |
| reusable through adapter | `experiments/v2_production_analysis.py` | Hierarchical production analysis |

**V3 note:** Retain paired relative and absolute effects; namespace planner-family metrics (ADR-026).

---

## 8. Configs, schemas, runners, visualization

### Architecture gate and schemas

| Fate | Path | Responsibility | ADRs |
| --- | --- | --- | --- |
| requires refactor | `experiments/architecture.py` | V1/V2 gate; needs V3 discriminator | 016 |
| reusable through adapter | `experiments/v2_config.py`, `v2_results.py` | Strict V2 config + result schema | 016 |
| reusable through adapter | `experiments/v2_production_config.py` | Single-solver production Monte Carlo config | — |
| legacy-only | `experiments/config.py`, `schema.py`, `registry.py` | V1 Pydantic config / result / registry | 006, 007 |

### Runners

| Fate | Path | Responsibility |
| --- | --- | --- |
| reusable through adapter | `experiments/v2_runner.py` | General V2 experiment runner |
| reusable through adapter | `experiments/v2_production_runner.py` and `v2_production_*` helpers | V2.10/11 production orchestration |
| reusable through adapter | `experiments/v2_shared_q_paired_study.py`, `v2_shared_q_fixtures.py`, `v2_solver_comparison.py`, `v2_2r_study.py` | Experiment A / shared-Q studies |
| legacy-only | `experiments/{pilot,setup,tasks,equal_nodes,canvas,sprint4*,sprint5*,sprint6*,resolution,sample_bank,edge_sensitivity}.py` | V1 sprint/pilot pipeline |

### Visualization and diagnostics

| Fate | Path | Responsibility |
| --- | --- | --- |
| reusable unchanged | `visualization/{paths,path_lengths,path_quality,expansions,savings,landscape}.py` | Generic figures |
| reusable through adapter | `visualization/embedded_graphs.py`, `v2_expansions.py`, `branches.py` | V2 embedded / branch figures |
| reusable through adapter | `experiments/v2_*_canvas.py` | Run-package HTML canvases |
| legacy-only | `diagnostics/{mapping,plots,bundle}.py` | Sprint 3 mapping diagnostics |

---

## 9. Summary map for migration

```text
Keep as-is:     search/{protocol,core,result,graph_solver}, topology,
                Mechanism protocol, OutputSpace/limits, planar_2r FK,
                core metrics, V1 golden via adapters

Adapt first:    EmbeddedPlanningGraph, v2_objectives (goal-set),
                Dijkstra/A* façades, V2 config/result schemas,
                production runner stack (historical only)

Refactor next:  OperatingBranch (coupled/non-separable), query overlay,
                Cartesian domain/attachment (exact start),
                architecture version gate → 3

Legacy preserve: ConstrainedInputGraph, PeriodicGrid2D, Monotonic*,
                 V1 objectives/costs/heuristics, sprint4–6 runners,
                 Experiment A Q-spanner as separate diagnostic identity
```

Highest-leverage existing entry points for V3 adapters:

1. ADR-020 goal-set search in `search/core.py`
2. Experiment B separation of external Cartesian bank vs mechanism attachment
3. ADR-015 topology / embedding / transition split
4. Generic `SearchGraph` protocol already planner-facing for deterministic graph search

No Version 3 source packages exist yet. Introduce `core/` and adapters beside these modules in Sprint V3.1; do not reorganize the tree in V3.0.
