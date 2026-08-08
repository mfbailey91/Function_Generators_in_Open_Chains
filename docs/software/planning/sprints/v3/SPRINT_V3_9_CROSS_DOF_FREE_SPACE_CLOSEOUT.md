# Sprint V3.9 — Cross-DOF Free-Space Architecture Closeout

**Status:** drafted / not activated  
**Reserved work packages:** V3-900–V3-905  
**Code authorization:** none until Sprint V3.8 closes and ACTIVE_SPRINT explicitly activates V3.9  
**Depends on:** corrected V3.6 2R evidence, V3.7 3R evidence, V3.8 6R evidence

## Sprint intent

Freeze the free-space architecture evidence for 2R planar position, 3R planar position/full pose, and 6R spatial position/full pose. Add minimal new planning code. Verify invariants across dimensions and create the hard gate that authorizes collision work.

## Non-goals

- obstacles or collision geometry;
- new planner algorithms;
- MoveIt;
- raw performance pooling across 2R/3R/6R;
- production inference;
- 4R/5R implementation.

## Work packages

### V3-900 — Freeze evidence revisions

Record immutable implementation/evidence revisions for accepted 2R, 3R, and 6R packages.

### V3-901 — Contract conformance matrix

Audit physical state, robot model, goal predicate/generator, local motion, objective, scene, planner, and result/provenance for every DOF/task family. Dimension-specific exceptions must be explicit capability boundaries.

### V3-902 — Reproducibility audit

Verify exact starts, goal-representation metadata, stochastic seed/process rules, serialization, and rerun commands.

### V3-903 — Scaling diagnostics

Report feasibility/task-class consistency, represented-goal coverage, direct-reference suboptimality, total wall time, validity-call growth, and within-family planner diagnostics without claiming one cross-DOF effort estimand.

### V3-904 — Free-space architecture report

Show what remained invariant from 2R→3R→6R and what changed because of dimensionality/task geometry.

### V3-905 — Obstacle-entry gate

Authorize V3.10 only if remaining free-space failures are attributable to documented planner/task limits rather than unresolved state/goal/local-motion defects.

## Exit criteria

1. One documented V3 contract has been demonstrated at 2R, 3R, and 6R.
2. Exact-start semantics and mechanism-aware \(U\)-cost survive all dimensions.
3. Goal predicates remain separate from IK/goal generation.
4. Free-space planner failures are understood before collision checking is introduced.
5. Incompatible planner events and task estimands are not pooled.
6. Collision work remains blocked until this closeout is accepted.
