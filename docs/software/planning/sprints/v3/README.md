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
8. [Sprint V3.6A — Dimensional-Generalization Refactor](SPRINT_V3_6A_DIMENSIONAL_GENERALIZATION_REFACTOR.md) (completed)
9. [Sprint V3.6B — Planar 2R Mechanism and Planner Visual Audit](SPRINT_V3_6B_PLANAR2R_VISUAL_AUDIT.md) (completed)
10. [Sprint V3.6C — Planar 2R Free-Space Closeout](SPRINT_V3_6C_PLANAR2R_FREE_SPACE_CLOSEOUT.md) (completed)
11. [Sprint V3.6D — Canonical Span Corpus](SPRINT_V3_6D_CANONICAL_SPAN_CORPUS.md) (completed)
12. [Sprint V3.6E — Gravity-Free Static Wrench Core](SPRINT_V3_6E_GRAVITY_FREE_STATIC_WRENCH_CORE.md) (completed)
13. [Sprint V3.6F — Static Wrench Atlas and Biological Docs](SPRINT_V3_6F_STATIC_WRENCH_ATLAS_AND_BIOLOGICAL_DOCS.md) (completed)
14. [Sprint V3.7 — Planar 3R Free-Space Implementation](SPRINT_V3_7_3R_PLANAR_FREE_SPACE.md) (completed provisional / pre-gate; residual reconciliation drafted / blocked)
15. [Sprint V3.8 — 6R Spatial Free-Space Planning](SPRINT_V3_8_6R_SPATIAL_FREE_SPACE.md) (drafted; not activated)
16. [Sprint V3.9 — Cross-DOF Free-Space Architecture Closeout](SPRINT_V3_9_CROSS_DOF_FREE_SPACE_CLOSEOUT.md) (drafted; not activated)
17. [Sprint V3.10 — Scene and Collision Framework](SPRINT_V3_10_SCENE_COLLISION_FRAMEWORK.md) (drafted; not activated)
18. [Sprint V3.11 — Obstacle Routing Evidence](SPRINT_V3_11_OBSTACLE_ROUTING_EVIDENCE.md) (drafted; not activated)
19. [Sprint V3.12 — MoveIt Application Adapter](SPRINT_V3_12_MOVEIT_APPLICATION_ADAPTER.md) (drafted; not activated)
20. [Sprint V3.13 — Production Mechanism Populations](SPRINT_V3_13_PRODUCTION_MECHANISM_POPULATIONS.md) (drafted; not activated)

V3.6B and V3.6C are completed. V3.6D–F are completed span-corpus and gravity-free wrench contracts ([program](../../V3_POST_V3_6C_SPAN_WRENCH_PROGRAM.md)); they are not Sprint V4.3. Residual V3.7 remains blocked until a separate ACTIVE_SPRINT activation. The post-V3.6 gate is:

\[
\boxed{
2R\ \text{evidence}
\rightarrow
\text{dimension refactor}
\rightarrow
\text{2R visual audit}
\rightarrow
\text{2R closeout corrections}
\rightarrow
\text{canonical spans / gravity-free wrench (completed)}
\rightarrow
3R\ \text{(architecture-final)}
\rightarrow
6R
\rightarrow
\text{cross-DOF closeout}
\rightarrow
\text{collision/obstacles}
}
\]

Provisional planar 3R evidence already exists under [`results/v3_review/v3_7_3r_free_space/`](../../../../results/v3_review/v3_7_3r_free_space/) and is retained, but 3R is not treated as architecture-final until V3.6C closes and residual V3.7 reconciliation is reviewed. Later sprint documents are planning contracts only and carry no code authorization until explicitly activated.

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
                          │                 ├── V3.7 provisional 3R free space (shipped ahead of gates)
                          │                 └── V3.6A dimensional refactor (completed)
                          │                       └── V3.6B planar 2R visual audit (completed)
                          │                             └── V3.6C planar 2R closeout (completed)
                          │                                   └── V3.6D canonical span corpus (completed)
                          │                                         └── V3.6E gravity-free wrench core (completed)
                          │                                               └── V3.6F wrench atlas / biological docs (completed)
                          │                                                     └── V3.7 residual / architecture-final 3R (drafted / blocked)
                          │                                                           └── V3.8 6R spatial free space
                          │                                                                 └── V3.9 cross-DOF closeout
                          │                                                                       └── V3.10 scene/collision framework
                          │                                                                             └── V3.11 obstacle routing evidence
                          │                                                                                   └── V3.12 MoveIt application adapter
                          │                                                                                         └── V3.13 production populations
                          └── representation ablations / deferred planner breadth
```

## Why the pre-3R gates exist

The V3 interfaces are largely dimension-independent, but delivered implementations still contain concrete planar-2R and operating-branch dependencies. V3.6A removes those dependencies. V3.6B then uses the visually inspectable 2R case to audit the actual \(\mathcal U\rightarrow\mathcal Q\rightarrow\mathcal X\) mappings, edge metrics, planner traces, and result assembly in a trial-scoped HTML artifact. V3.6C closes the concrete discrepancies found by that audit: true represented-goal parity, selected-candidate provenance, continuous path reconstruction, native U/Q/X traces, and interpretable Q-side actuator metrics.

These gates were intended before first 3R activation. Because provisional 3R already shipped, they now run as architecture-debt gates before treating 3R as final and before V3.8. See [`V3_PRE_3R_REFACTOR_AND_VISUAL_AUDIT_PLAN.md`](../../V3_PRE_3R_REFACTOR_AND_VISUAL_AUDIT_PLAN.md).

## Why obstacles move later

The `PlanningScene` abstraction already exists, so the architecture does not need collision geometry in order to validate higher-dimensional planning. Adding obstacles before architecture-final 3R and 6R free-space validation would mix new kinematics, goal representations, planner dimensionality, collision checking, and route topology in one debugging step.

The revised sequence isolates those effects:

1. prove the common V3 contracts in 2R free space;
2. remove concrete dimensionality seams, visually audit the 2R implementation, and close the resulting discrepancies;
3. reconcile planar redundancy and pose semantics at 3R on the refactored architecture;
4. add spatial kinematics and full-pose semantics at 6R;
5. close the free-space architecture across dimensions;
6. only then introduce collision geometry and genuine routing.

See [`V3_ROADMAP_DIMENSION_BEFORE_OBSTACLES.md`](../../../architecture/notes/V3_ROADMAP_DIMENSION_BEFORE_OBSTACLES.md).

## Scope rule

The graph, task bank, local motion, objective, planner, trace collector, and report renderer may not be fused into one experiment runner.

The V3 master contract is [`V3_PROJECT_PLAN.md`](../../../V3_PROJECT_PLAN.md). The scoped pre-3R amendment is [`V3_PRE_3R_REFACTOR_AND_VISUAL_AUDIT_PLAN.md`](../../V3_PRE_3R_REFACTOR_AND_VISUAL_AUDIT_PLAN.md); it governs the V3.6→V3.6C→architecture-final-V3.7 handoff until its sequence is folded into a later master-plan revision.
