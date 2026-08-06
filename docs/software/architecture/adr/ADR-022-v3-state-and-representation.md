# ADR-022 — Version 3 state and representation contract

**Status:** Proposed  
**Applies to:** Version 3  
**Related:** ADR-001, ADR-014, ADR-015, ADR-021; Sprint V3.0 V3-003  
**Supersedes:** nothing

## Context

Version 1 identifies planning nodes by complete actuator state in \(\mathcal U\). Version 2 identifies nodes by output state in \(\mathcal Q\) with a unique attached actuator realization on a certified branch. Planner-internal lattice indices, roadmap vertices, and tree nodes are easy to confuse with physical identity or task-space pose.

## Decision

Freeze four distinct layers:

1. **Physical state** — \(\,(u, q, \text{branch_id}, \ldots)\,\) uniquely identifies the mechanism and robot for objectives, validity, and later noninjective maps.
2. **Planner representation** — coordinates or discrete states used by a specific planner (lattice node, roadmap vertex, OMPL state, etc.).
3. **Task-space pose** — \(f(q)\) or richer \(SE(2)/SE(3)\) quantities used by goal predicates and diagnostics.
4. **Graph or planner internal bookkeeping** — parent pointers, open-set handles, heuristic caches; never task semantics.

The physical chain remains

\[
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X.
\]

### Initial comparative special case

For certified monotonic operating branches, Version 3 may use a shared bounded \(\mathcal Q\) representation across paired mechanisms while inducing actuator costs through \(u_m = g_m^{-1}(q)\):

\[
\text{same }Q\text{ geometry} + \text{same Cartesian task} + \text{mechanism-dependent }U\text{ cost}.
\]

This comparative formulation is a special case of the general physical-state contract, not the universal state model.

### Later noninjective requirement

When noninjective or multi-sheet maps return, physical state must preserve distinct preimages. Never collapse duplicate output preimages into one plain \(\mathcal Q\) node. Version 1 ADR-001 remains authoritative for that regime.

## Consequences

- Adapters must map planner representation ↔ physical state explicitly.
- Shared-Q comparative studies must declare the special-case contract.
- Heuristics and objectives that need \(u\) read physical state, not lattice indices alone.

## Non-goals

- Implementing noninjective state in V3.0–V3.2.
- Replacing ADR-014 for frozen Version 2 evidence.
