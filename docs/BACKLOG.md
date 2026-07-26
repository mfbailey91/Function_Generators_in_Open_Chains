# Initial Backlog

## P0 — Required before large Monte Carlo

### IM-001 Define `Mechanism` protocol — done
Forward map, Jacobian, inverse map, validity, periodicity, serialization.
See `docs/ADR-002-mechanism-protocol.md`.

### IM-002 Implement unit gearbox — done
Identity map, identity Jacobian, unique inverse, limit tests.

### IM-003 Implement fixed-ratio gearbox — done
Vector ratios, inverse, Jacobian, invalid zero-ratio handling.

### IM-004 Implement four-bar forward kinematics — done
Assembly validation, selected branch, periodic consistency.
See `docs/ADR-003-fourbar-conventions.md`.

### IM-005 Implement branch tracking — done
Continuous follower curve without artificial branch jumps.

### IM-006 Validate four-bar Jacobian — done
Analytic/implicit derivative agrees with finite differences.

### IM-007 Implement output preimage lookup — done
Return all valid input states for a target follower angle.

### IM-008 Build periodic 2D input graph — done
Four-connectivity, optional axis wrapping, deterministic indexing.

### IM-009 Apply shared output joint limits — done
Same output limits for gearbox and four-bar.
See `docs/ADR-004-shared-output-limits.md`.

### IM-010 Validate graph edges — done
Reject edges whose interior crosses invalid states.
See `docs/ADR-004-shared-output-limits.md`.

### IM-011 Implement Dijkstra — done
Optimal path, documented expansion semantics, stale-entry handling.
See `docs/ADR-005-search-semantics.md`.

### IM-012 Implement A* — done
Output-space Euclidean heuristic and deterministic tie-breaking.
See `docs/ADR-005-search-semantics.md`.

### IM-013 Add reverse Dijkstra — done
Exact cost-to-go for heuristic validation.
See `docs/ADR-005-search-semantics.md`.

### IM-014 Define config schema — done
Mechanisms, graph, limits, costs, algorithms, seed, and trials.
See `docs/ADR-006-experiment-config.md`.

### IM-015 Implement paired task generator — done
Matched output endpoints and stored selected preimages.
See `docs/ADR-006-experiment-config.md`.

### IM-016 Implement experiment registry — done
Run ID, config, seed, revision, environment, and outputs.
See `docs/ADR-007-experiment-registry.md`.

### IM-017 Reproduce pilot — done
Paired raw and normalized expansion plots.
See `docs/ADR-008-pilot-reproduction.md`.
CLI: `python scripts/reproduce_pilot.py --config configs/pilot.v1.yaml`.

### IM-031 Per-trial crank-rocker population — done
Sample two independent §12.1 crank-rockers per Monte Carlo trial; shared Q
limits come from those follower ranges and apply to both mechanisms.
See `docs/ADR-009-mechanism-population.md`.

## Sprint Two P0 — Output-space trust (see `docs/SPRINT_TWO_BACKLOG.md`)

- IM-032 Ratify output-space semantics — done (ADR-011)
- IM-033 Implement output-space abstraction — done
- IM-034 Four-bar trial-consistent lifted coordinates — done
- IM-035 Cost and heuristic compatibility — done (ADR-005)
- IM-036 Matched-task residuals — done
- IM-037 Edge-validation sensitivity study — done
  (`scripts/edge_validation_sensitivity.py`)
- IM-038 Regression and invariant test suite — done
  (`tests/invariants/test_sprint_two_invariants.py`)

## Sprint 3 — Ownership and controlled science (see `docs/SPRINT_3.md`)

Sprint Two P0 delivered ADR-011 and `OutputSpace`. Sprint 3 closes graph
ownership gaps, diagnostics, nested edge sensitivity, and open ablations.

### P0 — Ownership and residual correctness

- IM-042 Graph as canonical output boundary (S3-03)
- IM-043 Call-site audit of `input_to_output()` (S3-04)
- IM-044 Residual ownership / nesting regression tests (S3-05; extends IM-038)
- S3-01 / S3-02 confirm IM-032 / IM-033; amend ADR-011 only if needed

### P1 — Instrumentation and controlled science

- IM-045 Output inspection diagnostics (S3-06)
- IM-046 Minimal edge microscope (S3-07)
- IM-047 Nested edge-sampling sensitivity (S3-08; strengthens IM-037)
- IM-019 Monotonic-branch ablation (S3-09)
- IM-020 Periodic-boundary ablation (S3-09)
- IM-021 Input-cost versus output-cost ablation (S3-09)

## Earlier P1 — Controlled science (remaining outside Sprint 3 core)

- IM-018 Equal valid-node-count ablation — done (ADR-010; config
  `graph.match_valid_nodes`; `configs/pilot.equal_nodes.v1.yaml`)
- IM-022 Grid-resolution sweep
- IM-023 Mechanism descriptor extraction
- IM-024 Paired bootstrap confidence intervals

## P2 — Path quality and extension

- IM-025 Cartesian self-intersection count
- IM-026 Detour ratio
- IM-027 Cumulative turning
- IM-028 Near-revisit metric
- IM-029 Bidirectional Dijkstra
- IM-030 RL environment specification

## Definition of done

Every issue requires:

1. implementation;
2. tests;
3. documented interface;
4. defined failure behavior;
5. minimal example;
6. updated design note when relevant;
7. no required notebook-only logic.
