# Version 2 Rearchitecture — Sprint Index

## Recommended execution order

1. [Sprint V2.0 — Contract and Baseline Preservation](SPRINT_V2_0_CONTRACT_AND_BASELINE.md)
2. [Sprint V2.1 — Generic Search Graph and Topology Boundary](SPRINT_V2_1_GENERIC_SEARCH_GRAPH.md)
3. [Sprint V2.2 — Certified Invertible Operating Branches](SPRINT_V2_2_OPERATING_BRANCHES.md)
4. [Sprint V2.3 — Output-State Graphs and Sampling Provenance](SPRINT_V2_3_OUTPUT_STATE_GRAPHS.md)
5. [Sprint V2.4 — Versioned Experiment Pipeline](SPRINT_V2_4_EXPERIMENT_PIPELINE.md)
6. [Sprint V2.5 — Controlled 2R Study](SPRINT_V2_5_CONTROLLED_2R_STUDY.md)
7. [Sprint V2.6 — Exact Query Overlays and Initial Capability Objectives](SPRINT_V2_6_QUERY_OVERLAYS_AND_CAPABILITIES.md)
8. [Sprint V2.8 — Shared-Q Paired Mechanism Study](SPRINT_V2_8_SHARED_Q_PAIRED_STUDY.md) (completed)
9. [Sprint V2.9 — Shared-Q Paired Mechanism Study (U-distance only)](SPRINT_V2_9_SHARED_Q_PAIRED_STUDY.md) (completed diagnostic)
10. [Sprint V2.10 — Production Monte Carlo Orchestration: Dijkstra Campaign](SPRINT_V2_10_PRODUCTION_MONTE_CARLO_ORCHESTRATION.md) (completed; [evidence report](../../../experiments/reports/V2_10_PRODUCTION_DIJKSTRA_SUMMARY.md))
11. [Sprint V2.11 — A* Paired Campaign](SPRINT_V2_11_ASTAR_PAIRED_CAMPAIGN.md) (completed; [evidence report](../../../experiments/reports/V2_11_ASTAR_PAIRED_CAMPAIGN_SUMMARY.md))
12. [Sprint V2.12 — Cartesian Goal-Region Planning](SPRINT_V2_12_CARTESIAN_GOAL_REGION_PLANNING.md) (**active bounded smoke**; Experiment B)

V2.11 is complete on the frozen V2.10 bank. Experiment A now has Dijkstra and A* cells. ADR-019 and ADR-020 are accepted, and V2.12 is active for bounded Cartesian goal-set search correctness only. Production inference remains held behind calibration decisions and crossed statistics. V2.7 is now held pending review of trusted Experiment B task-space solver evidence.

## Deferred

- [Sprint V2.7 — 3R Planar Extension](SPRINT_V2_7_3R_EXTENSION.md) — **held** pending review of trusted 2R Cartesian goal-set Dijkstra/A* evidence from V2.12. This explicitly aligns the dimension roadmap as 2R position, then 3R planar pose.

## Dependency map

```text
V2.0 Contract + V1 baseline
  └── V2.1 Generic search/topology
        └── V2.2 Operating branches
              └── V2.3 Output-state graphs
                    └── V2.4 Experiment pipeline
                          └── V2.5 Controlled 2R study
                                └── V2.6 Exact tasks + capabilities
                                      └── 2R evaluation / printout review
                                            └── V2.8 Shared-Q paired study
                                                  └── V2.9 U-distance-only paired study
                                                        └── V2.10 Production Monte Carlo (Dijkstra)
                                                              └── V2.11 paired A* campaign
                                                                    └── ADR-019 + ADR-020 accepted
                                                                          └── V2.12 bounded Cartesian goal-set smoke
                                                                                ├── task-space solver evidence review
                                                                                │     └── (deferred) V2.7 3R extension
                                                                                └── calibration + crossed statistics
                                                                                      └── V2.12 production campaign
```

V2.1 and early V2.2 design work may overlap after ADR acceptance, but V2.3 implementation must not begin until both contracts are stable.

## Hard gates

| Gate | Blocks |
| --- | --- |
| Version 1 golden regression passes | all implementation sprints |
| Search no longer depends on 2D input grid | Version 2 graph integration |
| Operating branch certificate passes | all Version 2 graphs |
| Shared uniform-Q graph invariant passes | Version 2 runner promotion |
| Search-level null control passes | controlled 2R study |
| Grid convergence and exact-task controls pass | capability claims and V2.8 |
| Shared-Q pair invariants and pure-Q null controls pass | V2.8 interpretation |
| V2.8 2R evidence reviewed | V2.9 U-distance-only revision |
| V2.9 U-distance diagnostic reviewed | V2.10 Dijkstra production Monte Carlo |
| V2.10 production evidence reviewed | V2.11 paired A* campaign |
| ADR-019 and ADR-020 accepted | V2.12 bounded smoke implementation |
| V2.12 Cartesian goal-set Dijkstra/A* evidence reviewed | 3R implementation (deferred) |
| Cartesian calibration decisions and crossed statistics implemented | V2.12 production inference |

## Scope boundary

Version 2 does not delete the full-cycle formulation. Use:

- Version 1 for noninjective maps, periodic input topology, and duplicate preimages;
- Version 2 for certified invertible branches and output-state planning.
