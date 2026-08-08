# Sprint V3.6B — Planar 2R Mechanism and Planner Visual Audit

**Status:** drafted / not activated
**Reserved work packages:** V3-620–V3-629
**Code authorization:** none until Sprint V3.6A closes and ACTIVE_SPRINT explicitly activates V3.6B
**Depends on:** corrected V3.6 closeout; Sprint V3.6A; ADR-021–026
**Program:** [V3 pre-3R refactor and visual audit](../../V3_PRE_3R_REFACTOR_AND_VISUAL_AUDIT_PLAN.md)

## Sprint intent

Produce a small, trial-scoped, offline HTML audit that makes the current
planar-2R implementation legible from mechanism map through planner result:

\[
\mathcal U\xrightarrow{g_m}\mathcal Q\xrightarrow{f}\mathcal X.
\]

The sprint is for implementation introspection and review. It is not a
population experiment, a new V3.6 evidence package, or a mechanism-performance
claim.

## Frozen audit contract

- representative two-axis crank-rocker pair:
  \(a=1.0,b=2.5,c=2.0,d=2.0\), certified monotonic branches;
- current span-matched equivalent gearbox;
- shared `Planar2R(L1=1, L2=1)` kinematics;
- corrected V3.6 tasks `near_0`–`near_4` and `far_0`–`far_4`;
- corrected shared-start and frozen Cartesian goal-candidate semantics;
- one stochastic seed: `7`;
- audit lattice: shared uniform-Q `32 × 32`, 8-connected, integrated cost;
- static print panels are authoritative; animations are supplementary;
- separate U-cost, Q-length, X-length, transmission-stretch, and configured
  composite diagnostic components;
- optional OMPL rows are marked unavailable rather than silently omitted.

## Non-goals

- inferential statistics or stochastic repetition estimates;
- changing the V3.6 bank or its committed artifacts;
- selecting a favorable subset after seeing planner outcomes;
- adding new planners;
- using the audit lattice resolution for scientific convergence claims;
- obstacles, higher DOF, MoveIt, or noninjective mechanisms;
- a single dashboard that visually mixes all ten trials.

## Work packages

### V3-620 — Audit config and artifact contract

Add `configs/v3/planar2r_visual_audit_v1.json`, output schema, deterministic
asset naming, manifest fields, and the no-inference statement. Freeze the ten
task IDs, seed, lattice shape, planner set, animation policy, and sign convention
\(\Delta z=z_F-z_G\).

### V3-621 — Pair/task resolver

Reuse the corrected V3.6 loader to obtain shared `start_q`, start tip, physical
Cartesian disk, represented points, candidate ordering, and mechanism-specific
physical states. Fail closed on any pair-invariant mismatch.

### V3-622 — Opt-in planner trace contract

Add audit-only trace capture for graph expansion order, PRM construction/search,
and RRTConnect tree growth. Preserve ordinary `PlanningResult` size and planner
behavior. Extract final OMPL `PlannerData` without claiming unavailable
step-by-step history.

### V3-623 — U/Q/X edge and field metrics

For every shared-Q edge, compute integrated \(w_U\), \(w_Q\), and \(w_X\) under
the declared connector. Compute per-axis transmission/inverse derivatives,
\(J_{u\to x}=J_fJ_g\), and Q-side actuator metric
\(M_Q=J_{g^{-1}}^T J_{g^{-1}}\). Store arrays or compact records used by both
plots and invariant tests.

### V3-624 — Mapping and graph visualizations

Generate, per mechanism and trial:

- four-bar versus gearbox axis `q(u)`, `u(q)`, and `dq/du` plots;
- shared Q graph;
- mechanism-specific U embedding;
- Cartesian X embedding;
- Q-layout edge colors for \(w_U\), \(w_Q\), and \(w_X\);
- local metric/gain and transmission-stretch fields;
- separate U/Q/X path components and transparent composite diagnostic panels;
- start, physical goal disk, represented goal candidates, selected goal, and
  final path overlays.

### V3-625 — Planner path and exploration panels

Run input-linear, output-linear, lattice Dijkstra/A*, native PRM/RRTConnect, and
optional OMPL PRM/RRTConnect. Generate final U/Q/X paths, manipulator pose trails,
expanded masks, goal-cost basins, roadmap/tree traces, and family-specific
metrics.

### V3-626 — Animations and print fallbacks

Generate one combined four-panel lattice expansion animation per trial. Generate
roadmap/tree growth animations for `near_0`, `near_3`, and `far_2`. Create static
0/25/50/75/100-percent contact sheets and configure print CSS to substitute them
for live animations.

### V3-627 — Trial-scoped HTML report

Build `index.html`, `architecture.html`, and one self-contained page per trial.
Each trial page keeps the gearbox/four-bar pair together and does not blend in
other tasks. Use relative assets and no external network dependency.

### V3-628 — Architecture and provenance audit

Include the actual module/class call chain, config, Git revision, dependency
versions, optional-OMPL state, source ownership table, and raw JSON links. Show
where task semantics, physical state, local motion, edge weights, planner trace,
metrics, and HTML assembly are produced.

### V3-629 — Tests and closeout

Test pair invariants, edge-weight invariants, trace noninterference, deterministic
asset generation, HTML link integrity, print fallback presence, complete
mechanism/planner rows, and V1–V3.6 regressions. Generate the report from a clean
implementation revision and commit the artifact separately if it is retained.

## Required trial page order

1. task definition and candidate set;
2. code/dataflow architecture;
3. mechanism transmission maps;
4. Q, U, and X graph embeddings;
5. \(w_U\), \(w_Q\), \(w_X\), and local metric fields;
6. direct planner paths;
7. lattice Dijkstra/A* traces and animation;
8. native roadmap/tree traces;
9. optional OMPL final graph/path;
10. common and family metrics;
11. paired differences and review notes;
12. raw records and asset manifest.

## Exit criteria

1. All ten frozen tasks produce one readable trial page even when a planner
   fails or OMPL is unavailable.
2. Q nodes/adjacency, starts, physical goals, and represented candidate ordering
   are pair-invariant.
3. Shared output-linear \(w_Q\) and \(w_X\) agree across mechanisms; \(w_U\) is
   mechanism-specific and integrated from the declared motion.
4. Dijkstra/A* cost parity and direct-reference lower-bound checks pass.
5. Lattice animations derive from recorded expansion order, not reconstructed
   guesses.
6. Trace mode does not change status, selected goal, path, cost, or standard
   metrics.
7. Static print views contain every result needed for review; animations are not
   authoritative and have contact-sheet fallbacks.
8. Composite diagnostic scores expose their U/Q/X components, normalization,
   and weights and are not substituted for the primary actuator-travel result.
9. The HTML report is offline, print-aware, manifest-complete, and organized by
   trial rather than pooled visual panels.
10. Review findings are recorded before V3.7 activation.
