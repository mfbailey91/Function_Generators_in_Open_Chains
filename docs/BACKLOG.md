# Initial Backlog

## P0 — Required before large Monte Carlo

### IM-001 Define `Mechanism` protocol
Forward map, Jacobian, inverse map, validity, periodicity, serialization.

### IM-002 Implement unit gearbox
Identity map, identity Jacobian, unique inverse, limit tests.

### IM-003 Implement fixed-ratio gearbox
Vector ratios, inverse, Jacobian, invalid zero-ratio handling.

### IM-004 Implement four-bar forward kinematics
Assembly validation, selected branch, periodic consistency.

### IM-005 Implement branch tracking
Continuous follower curve without artificial branch jumps.

### IM-006 Validate four-bar Jacobian
Analytic/implicit derivative agrees with finite differences.

### IM-007 Implement output preimage lookup
Return all valid input states for a target follower angle.

### IM-008 Build periodic 2D input graph
Four-connectivity, optional axis wrapping, deterministic indexing.

### IM-009 Apply shared output joint limits
Same output limits for gearbox and four-bar.

### IM-010 Validate graph edges
Reject edges whose interior crosses invalid states.

### IM-011 Implement Dijkstra
Optimal path, documented expansion semantics, stale-entry handling.

### IM-012 Implement A*
Output-space Euclidean heuristic and deterministic tie-breaking.

### IM-013 Add reverse Dijkstra
Exact cost-to-go for heuristic validation.

### IM-014 Define config schema
Mechanisms, graph, limits, costs, algorithms, seed, and trials.

### IM-015 Implement paired task generator
Matched output endpoints and stored selected preimages.

### IM-016 Implement experiment registry
Run ID, config, seed, revision, environment, and outputs.

### IM-017 Reproduce pilot
Paired raw and normalized expansion plots.

## P1 — Controlled science

- IM-018 Equal valid-node-count ablation
- IM-019 Monotonic-branch ablation
- IM-020 Periodic-boundary ablation
- IM-021 Input-cost versus output-cost ablation
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
