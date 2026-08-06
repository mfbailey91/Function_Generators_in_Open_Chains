# Version 3 — Sprint Index

Version 3 builds a planner-agnostic mechanism-aware motion-planning framework. Version 2 remains a frozen historical experiment lineage.

## Recommended sequence

1. [Sprint V3.0 — Architecture Contract and V2 Evidence Freeze](SPRINT_V3_0_ARCHITECTURE_CONTRACT.md) (completed)
2. [Sprint V3.1 — Core Planning Problem and Result Model](SPRINT_V3_1_CORE_PROBLEM_RESULT_MODEL.md) (completed)
3. [Sprint V3.2 — Direct 2R Cartesian Vertical Slice](SPRINT_V3_2_DIRECT_2R_VERTICAL_SLICE.md) (completed)
4. [Sprint V3.3 — Lattice and Local-Motion Validation](SPRINT_V3_3_LATTICE_LOCAL_MOTION.md) (**active**)
5. Sprint V3.4 — Native Roadmap and Tree Planners
6. Sprint V3.5 — OMPL Adapter
7. Sprint V3.6 — Free-Space Planner Evidence
8. Sprint V3.7 — Scene and Obstacle Framework
9. Sprint V3.8 — 3R Planar Pose
10. Sprint V3.9 — 4R/5R Partial Tasks
11. Sprint V3.10 — 6R and MoveIt Application Adapter
12. Sprint V3.11 — Production Mechanism Populations

V3.3 is authorized for execution while ACTIVE_SPRINT points here. Later items are roadmap milestones and must receive their own sprint contracts before implementation.

## Dependency map

```text
V2 evidence freeze
  └── V3.0 contracts + migration map
        └── V3.1 core problem/result interfaces
              └── V3.2 direct 2R vertical slice
                    └── V3.3 lattice/local-motion validation
                          ├── V3.4 native roadmap/tree planners
                          │     └── V3.5 OMPL adapter
                          │           └── V3.6 free-space evidence
                          │                 └── V3.7 obstacle scenes
                          │                       └── higher-DOF roadmap
                          └── representation ablations
                                └── historical Experiment A reinterpretation limits
```

## Scope rule

The graph, task bank, local motion, objective, and planner may not be fused into one experiment runner.

The V3 master contract is [`V3_PROJECT_PLAN.md`](../../../V3_PROJECT_PLAN.md).
