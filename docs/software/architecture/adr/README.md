# Architecture decision records

ADRs use one global numbering sequence. Each ADR should state:

- status;
- architecture version applicability;
- related or superseded ADRs;
- implementation and test consequences.

ADR-001 remains accepted for Version 1 noninjective/full-cycle planning. Version 2 adds narrower decisions rather than rewriting that history. Version 3 ADRs (021–026) are **accepted** planner-agnostic contracts and do not reinterpret frozen Version 2 evidence.

| ADR | Title | Versions |
| --- | --- | --- |
| 001–013 | Version 1 baseline decisions | V1 |
| [014](ADR-014-v2-output-state-on-invertible-branches.md) | V2 output-state on invertible branches | V2 |
| [015](ADR-015-topology-embedding-transition-provenance.md) | Topology, embedding, transition provenance | V1 adapters / V2 |
| [016](ADR-016-v1-v2-configuration-compatibility.md) | V1/V2 configuration compatibility | V1 + V2 |
| [017](ADR-017-shared-q-normalized-qu-cost.md) | Shared-Q planning with normalized Q/U cost | V2 |
| [018](ADR-018-astar-actuator-travel-heuristic.md) | A* heuristic for actuator-travel production campaigns | V2 |
| [019](ADR-019-v2-cartesian-task-domain.md) | V2 external Cartesian task domain (accepted for smoke/calibration) | V2 |
| [020](ADR-020-v2-goal-set-search.md) | V2 goal-set search semantics (accepted) | V2 |
| [021](ADR-021-v3-planning-problem-contract.md) | V3 planning problem contract | V3 (accepted) |
| [022](ADR-022-v3-state-and-representation.md) | V3 state and representation contract | V3 (accepted) |
| [023](ADR-023-v3-exact-start-and-goal-regions.md) | V3 exact start and goal-region contract | V3 (accepted) |
| [024](ADR-024-v3-local-motion-and-cost.md) | V3 local motion and cost contract | V3 (accepted) |
| [025](ADR-025-v3-planner-capabilities-and-adapters.md) | V3 planner capabilities and adapters | V3 (accepted) |
| [026](ADR-026-v3-benchmark-classification-and-metrics.md) | V3 benchmark classification and metrics | V3 (accepted) |
| [027](ADR-027-v4-kinematic-transmission-geometry.md) | Kinematic transmission geometry as a shared differential layer | V4 (accepted; V4.0/V4.1 implemented) |
| [028](ADR-028-gravity-free-static-wrench.md) | Gravity-free static wrench from kinematic geometry | V3.6E/F accepted; drafted V4.3 consumes this API (unauthorized) |
