# V3.6C closeout decisions — planner roles, goal sets, and Q-side actuator metric

**Status:** implemented; Gate A/B accepted for Sprint V3.6C
**Scope:** planar 2R free-space closeout only
**Authority:** bounded architecture note; ADR-021–026 remain controlling contracts
**Related review:** [`V3_6B_GATE_B_REVIEW_FINDINGS.md`](V3_6B_GATE_B_REVIEW_FINDINGS.md)

## 1. Why a closeout gate is required

The V3.6B audit succeeded at making the implementation visible, but visibility
exposed several mismatches that should not be carried into architecture-final
3R work:

- lattice goal sets are evaluated as repeated exact-goal searches rather than one
  goal-set query;
- RRTConnect uses only the first represented goal;
- selected goal provenance is lost in common sampling helpers;
- physical, representation, and attachment residuals are conflated or omitted;
- planner-family path metrics do not always evaluate the same continuous local
  motions used by cost and visualization;
- native roadmap/tree traces are U-only and omit physical edges in Q and X;
- the Q-side actuator metric is mathematically valid but poorly named and
  visually incomparable across the pair.

V3.6C fixes those common contracts without replacing frozen V3.6/V3.6B evidence.

## 2. Planner-role decision

Use planners according to the question they can answer in free space.

| Role | Planner / diagnostic | Interpretation |
| --- | --- | --- |
| Mathematical reference | input-linear direct | shortest Euclidean actuator path to the represented goal set when valid |
| Visible-motion control | output-linear direct | same Q-local-motion policy, mechanism-specific U lift |
| Primary fixed-graph view | shared-Q lattice Dijkstra/A* | same Q topology, mechanism-specific integrated actuator metric |
| Primary dynamic exploration view | RRTConnect | mechanism-specific tree growth from exact physical start to full represented goal set |
| Roadmap-family control | native PRM | validates sampled roadmap/query architecture; often collapses to direct connection in present free space |
| Metric-isolation diagnostic | frozen shared-Q sampled roadmap | same sampled Q vertices/edges, mechanism-specific actuator weights; not native PRM |
| External adapter control | OMPL planners | final path/PlannerData when bindings are available; no invented stepwise history |

Native PRM remains in scope. It is not removed merely because the direct edge is
valid, and its direct edge is not disabled in the ordinary query to manufacture
interesting search. Any direct-edge-disabled variant must be explicitly labeled
a graph diagnostic and kept out of application planner comparisons.

## 3. State and projection decision

The physical chain is

\[
\mathcal U\xrightarrow{g_m}\mathcal Q\xrightarrow{f}\mathcal X.
\]

For native roadmap/tree planners, a state is the complete certified physical
state. U plus assembly identity determines state identity; Q and X are attached
physical projections. Therefore:

- nearest-neighbor and extension behavior are interpreted in the planner's
  declared state/metric;
- Q and X plots draw the same vertices and edges after mapping;
- projected crossings or overlaps never create adjacency;
- continuous parent/roadmap edges are sampled through the local connector before
  projection.

The shared-Q lattice and sampled-roadmap diagnostic are explicit comparative
representations. They freeze topology in Q and inverse-lift each vertex/edge
through each mechanism. Their scientific purpose is to isolate the mechanism-
induced actuator metric on one common graph.

## 4. Represented-goal decision

Let the frozen finite approximation of the physical goal predicate be

\[
G_{\mathrm{rep}}=\{c_1,\ldots,c_K\},
\]

where every candidate retains state and provenance.

All ordinary V3.6C planners receive the same ordered candidate set:

- direct planners evaluate every candidate;
- lattice and sampled roadmaps attach every candidate to one query graph and
  terminate when any candidate is optimally settled;
- PRM attaches every candidate;
- RRTConnect creates one goal-tree root per candidate;
- OMPL translation exposes the same goal set or documents an adapter limitation
  explicitly.

A candidate is not reduced to an anonymous `PhysicalState` before selection.
The selected result keeps its `goal_sample_id`, represented point, IK family,
index, and generator identity.

For an integrated Euclidean actuator-length objective, an admissible A* heuristic
to the represented set is

\[
h(n)=\min_{c_k\in G_{\mathrm{rep}}}\|u(n)-u(c_k)\|_2.
\]

It lower-bounds the actuator arc length of any path from the current state to any
represented goal. Heuristic tests target the complete set, not one candidate at
a time.

## 5. Residual decision

Residual fields must state what was measured.

- **Physical task residual:** evaluated by the original `GoalConstraint` on the
  selected state; this is the main success-quality value.
- **Goal margin:** signed relation to the physical tolerance boundary when the
  predicate supports it.
- **Representation residual:** error introduced by finite goal sampling, IK, or
  deduplication.
- **Attachment residual:** error introduced by graph overlay, reconstruction, or
  numerical state lifting.

An exact-Q overlay residual of zero is not substituted for the Cartesian disk
residual. A structured `GoalResidual` is serialized rather than discarded when
it is not a scalar.

## 6. Trajectory-evaluation decision

A `Trajectory` contains ordered states. Its physical execution is the sequence
of local motions connecting them under the planner's declared connector policy.
V3.6C introduces one shared evaluator that rebuilds those motions and samples
U, Q, and X consistently.

The evaluator owns fresh reporting values:

\[
L_U=\sum_e\int_e\|\dot u\|dt,
\qquad
L_Q=\sum_e\int_e\|\dot q\|dt,
\qquad
L_X=\sum_e\int_e\|\dot x\|dt.
\]

The same sampled segments feed plots. Endpoint waypoint-polylines may remain as
explicitly named diagnostics, but they are not mixed silently with integrated
values across planner families.

Planner objective cost remains authoritative. The evaluator does not recompute a
different optimization objective and declare it the planner's result.

## 7. Q-side actuator metric decision

The audit field is

\[
M_Q^{(U)}(q)
=J_{g^{-1}}(q)^\mathsf T J_{g^{-1}}(q),
\qquad
ds_U^2=dq^\mathsf T M_Q^{(U)}dq.
\]

It is the actuator-travel metric expressed in output-joint coordinates. New code
and records call it `actuator_metric_on_q`.

For positive-definite \(M_Q^{(U)}\),

\[
\kappa(M_Q^{(U)})
=\frac{\lambda_{\max}}{\lambda_{\min}},
\]

and

\[
\sqrt{\kappa(M_Q^{(U)})}
\]

is the ratio of the most to least actuator-expensive local Q directions per unit
Q displacement. The condition number measures anisotropy, not overall scale.
For example, \(100I\) has condition number one while all Q directions remain
actuator-expensive.

For independent axes,

\[
J_g=\operatorname{diag}(g_1',g_2'),
\qquad
M_Q^{(U)}=\operatorname{diag}(1/g_1'^2,1/g_2'^2).
\]

A span-matched gearbox with equal axis ratios is therefore isotropic and has
\(\kappa\approx1\). A four-bar can have much larger condition number because
\(g_i'(u_i)\) varies with configuration and the two axes generally occupy
different points on that gain curve. Squaring inverse gain amplifies directional
differences.

The report must also state what this is not:

- not the condition number of the manipulator Cartesian Jacobian;
- not a direct dexterity metric;
- not a path cost;
- not evidence that larger anisotropy is always beneficial.

Paired plots use the same logarithmic color scale and include
\(\lambda_{\min}\), \(\lambda_{\max}\), \(\sqrt{\det M}\),
\(\sqrt{\kappa}\), and sparse metric ellipses.

## 8. Artifact and compatibility decision

The following packages remain frozen provenance:

```text
results/v3_review/v3_6_free_space/
results/v3_review/v3_6_free_space_v2/
results/v3_review/v3_6b_planar2r_visual_audit/
results/v3_review/v3_7_3r_free_space/
```

V3.6C writes only to:

```text
results/v3_review/v3_6c_planar2r_closeout/
```

Fresh schemas may use corrected names and residual fields. Readers of frozen
artifacts retain legacy compatibility; no migration rewrites committed evidence.

## 9. Gate consequence

V3.6C closes only when the common planner/result corrections are implemented,
tested, visible in the new report, and reviewed. Closeout returns ACTIVE_SPRINT
to no authorization. Architecture-final V3.7 reconciliation requires a separate
activation change.
