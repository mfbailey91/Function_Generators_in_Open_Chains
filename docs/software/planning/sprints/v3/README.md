# Version 3 — Sprint Index

Version 3 builds a planner-agnostic mechanism-aware motion-planning framework. Version 2 remains a frozen historical experiment lineage.

## Recommended sequence

1. [Sprint V3.0 — Architecture Contract and V2 Evidence Freeze](SPRINT_V3_0_ARCHITECTURE_CONTRACT.md) (completed)
2. [Sprint V3.1 — Core Planning Problem and Result Model](SPRINT_V3_1_CORE_PROBLEM_RESULT_MODEL.md) (completed)
3. [Sprint V3.2 — Direct 2R Cartesian Vertical Slice](SPRINT_V3_2_DIRECT_2R_VERTICAL_SLICE.md) (completed)
4. [Sprint V3.3 — Lattice and Local-Motion Validation](SPRINT_V3_3_LATTICE_LOCAL_MOTION.md) (completed)
5. [Sprint V3.4 — Native Roadmap and Tree Planners](SPRINT_V3_4_NATIVE_ROADMAP_TREE.md) (completed)
6. [Sprint V3.5 — OMPL Adapter](SPRINT_V3_5_OMPL_ADAPTER.md) (completed)
7. [Sprint V3.6 — 2R Free-Space Planner Evidence](SPRINT_V3_6_FREE_SPACE_EVIDENCE.md) (completed)
8. [Sprint V3.7 — 3R Planar Free-Space Planning](SPRINT_V3_7_3R_PLANAR_FREE_SPACE.md) (**active**)
9. [Sprint V3.8 — 6R Spatial Free-Space Planning](SPRINT_V3_8_6R_SPATIAL_FREE_SPACE.md) (drafted; not activated)
10. [Sprint V3.9 — Cross-DOF Free-Space Architecture Closeout](SPRINT_V3_9_CROSS_DOF_FREE_SPACE_CLOSEOUT.md) (drafted; not activated)
11. [Sprint V3.10 — Scene and Collision Framework](SPRINT_V3_10_SCENE_COLLISION_FRAMEWORK.md) (drafted; not activated)
12. [Sprint V3.11 — Obstacle Routing Evidence](SPRINT_V3_11_OBSTACLE_ROUTING_EVIDENCE.md) (drafted; not activated)
13. [Sprint V3.12 — MoveIt Application Adapter](SPRINT_V3_12_MOVEIT_APPLICATION_ADAPTER.md) (drafted; not activated)
14. [Sprint V3.13 — Production Mechanism Populations](SPRINT_V3_13_PRODUCTION_MECHANISM_POPULATIONS.md) (drafted; not activated)

V3.7 is the only authorized sprint while ACTIVE_SPRINT points there (V3-700–V3-706). The dimensional free-space sequence remains a hard architecture gate: **2R → 3R → 6R → cross-DOF closeout → collision/obstacle work**. Later sprint documents are planning contracts only and carry no code authorization until explicitly activated.

Native planner breadth omitted from the narrowed V3.3/V3.4 slices remains tracked under `V3-DEFER-001`. Spatial 4R/5R partial-task studies remain accepted but non-gating work under `V3-DEFER-002`; they are not required before the standard 6R free-space architecture test.

## Dependency map

```text
V2 evidence freeze
  └── V3.0 contracts + migration map
        └── V3.1 core problem/result interfaces
              └── V3.2 direct 2R vertical slice
                    └── V3.3 lattice/local-motion validation
                          ├── V3.4 native roadmap/tree planners
                          │     └── V3.5 OMPL adapter
                          │           └── V3.6 2R free-space evidence (completed)
                          │                 └── V3.7 3R planar free space (active)
                          │                       └── V3.8 6R spatial free space
                          │                             └── V3.9 cross-DOF closeout
                          │                                   └── V3.10 scene/collision framework
                          │                                         └── V3.11 obstacle routing evidence
                          │                                               └── V3.12 MoveIt application adapter
                          │                                                     └── V3.13 production populations
                          └── representation ablations / deferred planner breadth
```

## Why obstacles move later

The `PlanningScene` abstraction already exists, so the architecture does not need collision geometry in order to validate higher-dimensional planning. Adding obstacles before 3R and 6R free-space validation would mix new kinematics, goal representations, planner dimensionality, collision checking, and route topology in one debugging step.

The revised sequence isolates those effects:

1. prove the common V3 contracts in 2R free space;
2. add planar redundancy and pose semantics at 3R;
3. add spatial kinematics and full-pose semantics at 6R;
4. close the free-space architecture across dimensions;
5. only then introduce collision geometry and genuine routing.

See [`V3_ROADMAP_DIMENSION_BEFORE_OBSTACLES.md`](../../../architecture/notes/V3_ROADMAP_DIMENSION_BEFORE_OBSTACLES.md).

## Scope rule

The graph, task bank, local motion, objective, and planner may not be fused into one experiment runner.

The V3 master contract is [`V3_PROJECT_PLAN.md`](../../../V3_PROJECT_PLAN.md).
