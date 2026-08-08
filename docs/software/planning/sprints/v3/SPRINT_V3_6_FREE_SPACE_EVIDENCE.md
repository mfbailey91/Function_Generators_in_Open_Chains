# Sprint V3.6 — Free-Space Planner Evidence

**Status:** active — corrective free-space evidence contract after v1 pilot review
**Code authorization:** V3-600–V3-605 only
**Depends on:** [Sprint V3.5](SPRINT_V3_5_OMPL_ADAPTER.md) (completed); accepted ADRs 021–026
**Reference:** [V3_PROJECT_PLAN.md](../../../V3_PROJECT_PLAN.md) §16 V3-M6

## Sprint intent

Publish a **frozen external Cartesian** free-space task bank and run the already-delivered planner families (direct, lattice Dijkstra, native PRM/RRTConnect, OMPL when available) under ADR-026 pre-search classification and size strata. Produce a tracked review artifact. This is **not** population inference, Monte Carlo, or an obstacle study.

The scientific role of V3.6 is the free-space representation/optimality baseline:

> On the same physical start and the same represented Cartesian goal region, how
> faithfully does each planner recover the mechanism-aware direct actuator-space
> reference, and what algorithmic overhead/suboptimality does its representation
> introduce?

Under the current monotonic branch, convex actuator bounds, input-linear local
motion, and no obstacles, direct feasibility is expected for valid represented
goal states. Genuine routing necessity enters in V3.7.

## Entry conditions

1. V3.5 OMPL adapter, corrective contract, and `results/v3_review/v3_5_closeout/` are accepted.
2. ACTIVE_SPRINT explicitly activates V3.6.
3. No new planner algorithms are required; V3.6 consumes delivered planners only.

## Non-goals

- Obstacles / collision scenes (V3.7);
- MoveIt, higher-DOF, production Monte Carlo;
- Closing `V3-DEFER-001` native breadth (Lazy-PRM, PRM*, RRT*, …);
- Reinterpreting frozen V2 evidence;
- Claiming bank means equal population estimands;
- manufacturing `neither_direct` cases in an unconstrained convex free-space domain.

## V3.6 v1 pilot finding

`free_space_planar2r_v1.json` and `results/v3_review/v3_6_free_space/` are
preserved as pilot provenance. Review found two closeout blockers:

1. applying the same normalized `start_u_frac` independently to each
   transmission did **not** preserve the same physical start (`q` / Cartesian
   tip) across the four-bar and gearbox;
2. nonzero Cartesian disk radii were mostly realized through center IK only,
   so planner comparisons did not share an explicit finite goal-set
   approximation of the disk.

The v1 artifact must therefore not be used as the V3.6 closeout evidence.

## Corrective evidence contract (`free_space_planar2r_v2`)

### Shared start

The v2 bank retains each v1 actuator fraction only as an **authoring reference**
on the four-bar. At load time it is resolved once to a shared output state:

\[
q_s = g_F(u_{s,\mathrm{ref}})
\]

and every paired mechanism starts from its own certified inverse realization of
that same `q_s`. The loader verifies the resulting Cartesian start tips agree
within tolerance. The resolved `start_q` and `start_tip` are written into the
review artifact.

### Frozen Cartesian goal representation

Each physical disk goal remains the task predicate. For planner realization,
v2 freezes a common Cartesian sample set: the center plus eight near-boundary
points. The same Cartesian points and IK ordering feed all planner families.
The artifact records those points and the accepted physical goal candidates.

For each mechanism-task, the benchmark computes the exact free-space
input-linear actuator-travel optimum over this **represented goal set**:

\[
J^*_{\mathrm{rep}} =
\min_{s_g \in G_{\mathrm{rep}}}
\|u_g-u_s\|_2.
\]

Planner suboptimality is reported as `J_planner - J*_rep`.

### Stochastic repetitions

Direct and deterministic lattice planners run once. Native PRM/RRTConnect and
OMPL PRM/RRTConnect run the frozen seed set from the v2 contract. OMPL
repetitions run in fresh processes because its Python seed control is
process-global best effort.

### Publication provenance

Implementation and evidence are two commits:

1. commit the corrected bank/runner/tests;
2. from that clean revision, generate `results/v3_review/v3_6_free_space_v2/`
   and commit the generated artifact separately.

The manifest records the implementation revision, not the result commit.

## Work packages

### V3-600 — Sprint contract and activation

Author this contract; authorize V3-600–V3-605 only.

### V3-601 — Frozen Cartesian task bank

Preserve v1; add `configs/v3/free_space_planar2r_v2.json` as a corrective
contract layered over the frozen v1 task list. Resolve one shared `q`/tip start,
and freeze the finite disk representation.

### V3-602 — Classification, direct reference, and strata

ADR-026 per-mechanism task class before search; paired strata; shared
tip-separation size bins; pre-search descriptors; represented-goal-set direct
reference cost.

### V3-603 — Multi-planner evidence runner

Same resolved tasks × mechanisms × delivered planner families. Lattice search
evaluates the frozen goal candidate set rather than silently selecting the
first candidate. `already satisfied` and invalid tasks short-circuit to common
V3 results rather than planner-specific skips. Stochastic planners use frozen
repetitions; OMPL uses process isolation.

### V3-604 — Review artifact

Tracked package under `results/v3_review/v3_6_free_space_v2/` plus HTML
printout. Primary summaries are planner suboptimality, paired mechanism effects
(`ΔJ`, `Δ total_wall_time`), and common status metrics by size/class stratum.
Query-only timing remains secondary.

### V3-605 — Tests and gates

Shared-start equality, frozen goal-set determinism, direct-reference lower-bound
checks, lattice short-circuit behavior, paired summaries, OMPL process-isolated
worker path, and V1–V3.5 regressions.

## Exit criteria

1. The corrected v2 bank is versioned without rewriting v1 pilot provenance.
2. Both mechanisms realize the same `start_q` and Cartesian start tip for every paired task.
3. Every planner receives the same frozen Cartesian goal sample set/IK ordering.
4. Every evidence row records ADR-026 `task_class`, size stratum, paired stratum, represented-goal reference cost, and planner suboptimality when defined.
5. Lattice `already satisfied` / invalid tasks produce common V3 outcomes rather than `no_goal_candidate` skips.
6. Primary cross-family timing uses `total_wall_time`; setup/preprocess/query fields remain available separately.
7. Native and OMPL stochastic evidence use the declared frozen repetitions; OMPL repetitions are process isolated.
8. Review summaries report per-planner paired mechanism effects and suboptimality rather than only pooled planner means.
9. The generated manifest points to the clean implementation commit that contains the corrected V3.6 runner and bank.
10. No population inference or obstacle work is activated.
11. Hand off to V3.7 only after the corrected free-space semantics are reviewed.

## Deferred work

`V3-DEFER-001` remains open. Obstacle framework is Sprint V3.7.
