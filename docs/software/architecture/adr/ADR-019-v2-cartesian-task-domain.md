# ADR-019 — Version 2 external Cartesian task domain

**Status:** Proposed prerequisite; not accepted  
**Applies to:** Version 2 Experiment B / held Sprint V2.12  
**Related:** ADR-011, ADR-014, ADR-017; [`EXPERIMENT_B_CARTESIAN_GOAL_REGION.md`](../../experiments/protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md)

## Context

Experiment A used centered, normalized-\(\mathcal Q\) canonical probes. Experiment
B needs a fixed external Cartesian exam shared across the mechanism population.
The domain \(\mathcal D_X\) must be chosen before any production search. Using
the intersection of sampled mechanism workspaces would let the population shape
the exam.

This ADR is a placeholder. It records the required decisions and the intended
primary contract. It does not freeze a numerical domain, \(\epsilon_X\), or
sampler implementation.

## Intended primary contract

When accepted, this ADR should adopt:

1. a fixed external Cartesian region defined from the nominal 2R arm geometry
   and an intended application area, not from observed mechanism expansions;
2. one area-uniform task bank frozen independently of the mechanism population;
3. reachability as an experimental outcome;
4. planning metrics reported conditionally on valid start and goal construction;
5. pair-local reachable-workspace sampling only as a secondary control with a
   separate experiment identifier.

## Decisions required before acceptance

- coordinate frame and relation to \(L_1,L_2\);
- analytic or sampled boundary of \(\mathcal D_X\);
- exclusions around singular or degenerate regions, if any;
- boundary-sampling policy;
- minimum start–goal Cartesian separation;
- relationship between that separation and \(\epsilon_X\), including whether
  the start pose may lie in the goal disk;
- area-uniform sampling method and seed;
- start-tolerance region used when attaching \(\mathbf x_s\) to discrete
  \(\mathcal Q\) states;
- task-bank schema, digest, freeze, and reuse rules;
- rejection taxonomy for infeasible or degenerate samples.

## Consequences once accepted

- Experiment B production refuses a missing or unfrozen domain decision.
- Mechanism descriptors must not regenerate \(\mathcal D_X\).
- Coverage and conditional search metrics remain separate estimands.
- Implementation remains blocked until this ADR is accepted and tested.

## Status note

Do not implement sampler or bank-export code against this placeholder.
