# ADR-001 — Search in Input Configuration Space

**Status:** Accepted

## Context

A four-bar follower map is generally not globally injective:

$$
u_a \neq u_b,
\qquad
g(u_a)=g(u_b).
$$

Collapsing those states in output space can create false connectivity.

## Decision

Graph state identity is the complete input configuration. Output and Cartesian states are attached data, not node identity.

## Consequences

Benefits:

- preserves physical mechanism state;
- supports full crank periodicity;
- retains duplicate output preimages;
- represents joint-limit preimages naturally.

Costs:

- larger graphs;
- output goals may have several valid preimages;
- output-space plots may overlap or cross.

Version 1 uses known start and goal preimages. Multi-source and multi-goal search are deferred.
