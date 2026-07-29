# Version 2 Rearchitecture — Sprint Index

## Recommended execution order

1. [Sprint V2.0 — Contract and Baseline Preservation](SPRINT_V2_0_CONTRACT_AND_BASELINE.md)
2. [Sprint V2.1 — Generic Search Graph and Topology Boundary](SPRINT_V2_1_GENERIC_SEARCH_GRAPH.md)
3. [Sprint V2.2 — Certified Invertible Operating Branches](SPRINT_V2_2_OPERATING_BRANCHES.md)
4. [Sprint V2.3 — Output-State Graphs and Sampling Provenance](SPRINT_V2_3_OUTPUT_STATE_GRAPHS.md)
5. [Sprint V2.4 — Versioned Experiment Pipeline](SPRINT_V2_4_EXPERIMENT_PIPELINE.md)
6. [Sprint V2.5 — Controlled 2R Study](SPRINT_V2_5_CONTROLLED_2R_STUDY.md)
7. [Sprint V2.6 — Exact Query Overlays and Initial Capability Objectives](SPRINT_V2_6_QUERY_OVERLAYS_AND_CAPABILITIES.md)
8. [Sprint V2.7 — 3R Planar Extension](SPRINT_V2_7_3R_EXTENSION.md)

## Dependency map

```text
V2.0 Contract + V1 baseline
  └── V2.1 Generic search/topology
        └── V2.2 Operating branches
              └── V2.3 Output-state graphs
                    └── V2.4 Experiment pipeline
                          └── V2.5 Controlled 2R study
                                └── V2.6 Exact tasks + capabilities
                                      └── V2.7 3R extension
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
| Grid convergence and exact-task controls pass | capability and 3R claims |
| 2R architecture is dimension-independent | 3R implementation |

## Scope boundary

Version 2 does not delete the full-cycle formulation. Use:

- Version 1 for noninjective maps, periodic input topology, and duplicate preimages;
- Version 2 for certified invertible branches and output-state planning.
