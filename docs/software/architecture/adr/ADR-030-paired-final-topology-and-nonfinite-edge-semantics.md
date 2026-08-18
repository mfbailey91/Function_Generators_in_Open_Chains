# ADR-030 — Paired Final Topology and Nonfinite Edge Semantics

**Status:** Accepted for Sprint V4.2B and later paired planning experiments
**Architecture version:** V4; compatible with V3 graph-search contracts
**Related decisions:** ADR-021, ADR-024, ADR-025, ADR-027, ADR-029
**Supersedes:** no prior ADR; tightens the V4.2B interpretation of shared-Q topology and unavailable local motion

## Context

The span-controlled comparison is intended to hold the robot-visible planning representation fixed while allowing the transmission to change actuator realization and actuator cost.

A common Q lattice alone is insufficient. After candidate adjacency is built, a continuous connector may accept an edge for one mechanism and reject it for another. If each arm compiles its search graph independently, the final planner-facing topology can diverge even though the candidate samples and candidate adjacency were shared.

A second ambiguity exists in the edge-cost adapter. The current implementation uses nonfinite values to indicate unavailable local motion, but `NaN`, positive infinity, and negative infinity have different meanings:

- positive infinity may be a deliberate legacy sentinel for unavailable motion;
- `NaN` indicates an invalid numerical result;
- negative infinity is an invalid negative cost;
- a finite negative value violates shortest-path assumptions.

Silently treating all nonfinite values as ordinary graph exclusions can hide numerical defects.

## Decision

### 1. Generic search accepts only finite nonnegative edges

Dijkstra, A*, and every generic shortest-path implementation remain strict. Their weighted-neighbor interface may yield only:

\[
0\le c(u,v)<\infty.
\]

Generic search does not interpret local-motion failure or repair malformed weights.

### 2. Nonfinite classification occurs at the adapter boundary

The accepted classification is:

| Edge evaluation | Meaning | Adapter behavior |
| --- | --- | --- |
| finite, `>= 0` | available local motion | admit and cache |
| `+inf` | explicitly unavailable local motion | omit before search and retain a diagnostic |
| `NaN` | numerical/programming failure | raise a typed error |
| `-inf` | invalid negative-infinite cost | raise a typed error |
| finite, `< 0` | invalid negative cost | raise a typed error |

The positive-infinity sentinel is retained only as a bounded compatibility mechanism at the adapter boundary. A future typed connector result may replace it.

### 3. Paired experiments compile one final edge set jointly

For a paired four-bar/gearbox experiment:

1. build one common Q sample set and candidate adjacency;
2. inverse-lift the common samples through both mechanisms;
3. require one common valid-node mask;
4. evaluate each candidate local motion through every paired mechanism;
5. admit an edge to the primary planner graph only when every paired mechanism reports a finite nonnegative cost;
6. if any mechanism reports unavailable local motion, exclude that edge from the primary graph for all mechanisms;
7. retain the per-mechanism rejection outcomes as diagnostics;
8. attach separate mechanism-specific actuator costs to the one admitted edge ID.

The final node IDs and final edge IDs passed to the planners are therefore identical across the pair.

### 4. Post-hoc graph intersection is not the primary fairness contract

Constructing two final graphs independently and intersecting them after the fact is not accepted for the primary paired comparison. It may remain as a historical diagnostic or compatibility reader for frozen V4.2/V4.2A evidence.

### 5. Mechanism-specific connector disagreement is visible

An edge that is available for one mechanism and unavailable for the other is recorded with a typed, per-arm diagnostic. The edge is excluded from both primary planner graphs so topology remains controlled. These diagnostics may be analyzed separately but may not be pooled with actuator-cost effects.

## Consequences

### Benefits

- the final planner topology is genuinely paired;
- actuator-cost differences are not confounded with edge-set differences;
- numerical failures cannot masquerade as ordinary unavailable motion;
- Dijkstra/A* retain standard assumptions;
- mechanism-specific connector failures remain observable;
- downstream evidence can state precisely what was held fixed.

### Costs

- common admission may remove an edge that one mechanism could traverse;
- the shared graph may become more conservative or disconnected;
- paired edge evaluation is more expensive than compiling one arm at a time;
- the artifact schema must retain both common admission and per-arm diagnostics.

These costs are accepted because the primary experiment estimates a mechanism effect on a controlled graph. Mechanism-specific feasible topology is a separate estimand.

## Implementation consequences

A paired compiler should return:

- one common planner graph;
- one ordered admitted-edge ID set;
- separate cached edge-cost functions by mechanism;
- per-candidate, per-mechanism admission records;
- deterministic digests for candidate and admitted topology.

The existing single-arm finite-edge compiler must distinguish `+inf` from `NaN` and `-inf`.

## Test consequences

Required tests include:

- finite zero and positive weights are admitted;
- positive infinity is omitted as `unavailable_local_motion`;
- `NaN`, negative infinity, and finite negative values raise;
- an edge unavailable in either arm is absent from both final graphs;
- an edge available in both arms appears under the same ID in both cost maps;
- all-invalid queries return `found=False`, not `planner_exception`;
- Dijkstra and A* agree on feasibility and optimal cost;
- all 17 V4.2B cases have identical final paired node and edge IDs.

## Evidence consequences

V4.2B manifests and planner records must distinguish:

```text
candidate_edge_count
admitted_edge_count
candidate_topology_digest
admitted_topology_digest
per_arm_unavailable_edge_count
paired_connector_disagreement_count
```

No V4.2B closeout claim may use “same graph” unless the final admitted-topology digest is equal across the pair.
