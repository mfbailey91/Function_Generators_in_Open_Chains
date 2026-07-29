# ADR-014 — Version 2 Output-State Identity on Invertible Branches

**Status:** Accepted  
**Architecture versions:** Version 2 (does not replace ADR-001 for Version 1)  
**Related:** ADR-001, ADR-011, ADR-015, ADR-016

## Context

Biological and engineering transmissions are often operated on a locally
invertible branch rather than a full-cycle, multi-preimage map. Version 1
(ADR-001) correctly requires actuator-state identity in \(\mathcal U\) whenever
\(g_m\) is noninjective or periodic wraparound is in scope.

Version 2 changes the scientific question: restrict each mechanism to a
certified, one-to-one operating branch and study how uniform actuator sampling
allocates resolution across output configuration space. Under that contract,
output configuration \(\mathbf q\) is a complete kinematic planning state.

Removing wraparound from the core study simplifies task semantics and makes a
uniform-\(\mathcal Q\) null control well defined. It does not invalidate
Version 1 full-cycle evidence.

## Decision

### Binary state-identity rule

| Experiment regime | Planning node identity | Actuator realization |
| --- | --- | --- |
| Noninjective or full-cycle map (Version 1) | Complete \(\mathbf u\in\mathcal U\) | Identity itself |
| Certified injective operating branch (Version 2) | \(\mathbf q\in\mathcal Q\) | Unique \(\mathbf u=g_m^{-1}(\mathbf q)\) attached as node data |

### Mathematical branch contract

A Version 2 operating branch \(g_m:\mathcal U_b\rightarrow\mathcal Q_b\) must satisfy:

1. one fixed assembly mode;
2. continuous, strictly monotonic map per supported axis (initially axis-separable);
3. unique inverse \(g_m^{-1}\) over the configured output chart;
4. nonperiodic, bounded branch topology;
5. explicit certification (sampling density, gain margins, forward/inverse residuals).

Plain \(\mathcal Q\)-state search is allowed **only** when this contract holds.

### Prohibition

It is forbidden to collapse duplicate output preimages of a noninjective map
into one plain \(\mathcal Q\) node. A noninjective or uncertified map must use
Version 1 \(\mathcal U\)-state identity (ADR-001) or an explicit lifted state
such as \((q,\sigma)\) — the latter is not part of Version 2 core scope.

### Relationship to ADR-001

ADR-001 remains accepted and authoritative for Version 1. This ADR supersedes
ADR-001 **only** for Version 2 experiments that declare `architecture_version: 2`
and attach a certified operating branch. It does not globally rewrite Version 1
semantics.

## Rejected alternatives

- Merging duplicate preimages in \(\mathcal Q\) for convenience.
- Planning in \((q,\sigma)\) in the initial Version 2 core.
- Deleting or reinterpreting Version 1 baselines.
- Retaining full-cycle wraparound merely for software continuity.

## Consequences

Benefits:

- simpler task semantics in \(\mathcal Q\);
- no duplicate-preimage policy in Version 2;
- uniform-\(\mathcal U\) versus uniform-\(\mathcal Q\) sampling becomes a controlled comparison.

Costs:

- full-cycle topology leaves the Version 2 core study;
- every Version 2 graph depends on branch certification;
- loaders must reject mixed V1/V2 fields (ADR-016).

## Implementation consequences

- Version 2 graphs store `q_state` as planning identity and `u_state` as attached realization.
- `Mechanism.inverse_output` all-preimages behavior is unchanged; unique inversion lives on `OperatingBranch`.
- Tests must preserve Version 1 golden fixtures under ADR-001.
