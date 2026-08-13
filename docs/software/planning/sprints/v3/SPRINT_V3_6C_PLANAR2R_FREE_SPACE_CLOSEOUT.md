# Sprint V3.6C — Planar 2R Free-Space Closeout

**Status:** active
**Reserved work packages:** V3-630–V3-639
**Code authorization:** V3-630–V3-639 only
**Depends on:** corrected Sprint V3.6 evidence; Sprint V3.6A; Sprint V3.6B and its completed Gate B review; ADR-021–026
**Blocks:** architecture-final Sprint V3.7 acceptance and Sprint V3.8 activation
**Decision note:** [`V3_6C_CLOSEOUT_DECISIONS.md`](../../../architecture/notes/V3_6C_CLOSEOUT_DECISIONS.md)
**Gate B findings:** [`V3_6B_GATE_B_REVIEW_FINDINGS.md`](../../../architecture/notes/V3_6B_GATE_B_REVIEW_FINDINGS.md)
**New report target:** `results/v3_review/v3_6c_planar2r_closeout/`

## Sprint intent

Close the concrete implementation discrepancies exposed by the V3.6B planar-2R
visual audit before treating the provisional 3R implementation as
architecture-final.

V3.6C is not a new population experiment and does not reinterpret the corrected
V3.6 evidence. It reuses the readable 2R case to repair common planner, result,
trajectory, trace, and metric contracts. The corrected artifact is published as
a new package; frozen V3.6 and V3.6B outputs remain untouched.

The closeout question is:

> Do direct, lattice, roadmap, and tree planners now consume the same physical
> task semantics, retain the same represented-goal identity, evaluate the same
> continuous motions, and expose the complete
> \(\mathcal U\rightarrow\mathcal Q\rightarrow\mathcal X\) chain?

## Frozen closeout corpus

Reuse the V3.6B audit corpus without task replacement or mechanism retuning:

- four-bar pair: two identical certified crank-rocker axes with
  \(a=1.0,b=2.5,c=2.0,d=2.0\);
- current span-matched equivalent gearbox;
- `Planar2R(L1=1, L2=1)`;
- corrected tasks `near_0`–`near_4` and `far_0`–`far_4`;
- one shared exact `start_q` and Cartesian start per task;
- the same physical Cartesian disk and frozen center-plus-eight represented
  points;
- seed `7` for visual trace reproducibility;
- shared uniform-Q `32 × 32`, 8-connected lattice for the readable graph audit;
- no collision geometry, no new mechanism population, and no favorable task
  substitution after outcomes are known.

V3.6C may add deterministic diagnostic structures derived from this corpus, but
it may not change the task predicate, represented points, candidate ordering, or
paired mechanism geometry.

## Closeout decisions

### Planner roles

The primary 2R free-space references remain:

1. input-linear direct reference;
2. output-linear direct control;
3. shared-Q lattice Dijkstra and A*;
4. RRTConnect as the dynamic-exploration view.

Native PRM remains in the report as a roadmap-family architecture and adapter
control. In the current obstacle-free convex domain it commonly attaches a
direct start-goal edge and reproduces the input-linear result, so it is not a
primary mechanism-performance result.

A separately named **frozen shared-Q sampled-roadmap diagnostic** is added to
isolate the graph-solver question:

\[
\text{same sampled }V_Q
+\text{same }E_Q
+\text{mechanism-specific }w_U.
\]

It is not relabeled as native PRM and is not pooled with PRM performance.

### State and projection semantics

For native roadmap and tree planners, physical state identity remains
\((u,q,\text{assembly state})\), with U the authoritative state view. Q and X
plots are synchronized projections of the same states and continuous physical
edges. A crossing in projected Q or X does not imply graph connectivity.

The shared-Q lattice and shared-Q sampled roadmap are explicit comparative
representations. Their node/edge topology is frozen in Q while each mechanism
supplies its own inverse realization and integrated actuator cost.

### Continuous motion is the reporting truth

A planner path is an ordered sequence of declared local motions, not merely a
polyline through returned waypoints. V3.6C reconstructs and samples every path
edge through its connector and uses the same samples for:

- actuator/output/Cartesian path lengths;
- continuous validity checks when required;
- U/Q/X path rendering;
- sparse manipulator poses;
- transmission-stretch diagnostics.

The planner's declared optimization objective remains authoritative. Reporting
metrics may diagnose that path but may not silently replace its objective with a
waypoint chord.

## Required corrections

### 1. True represented-goal graph search

Replace candidate-by-candidate lattice solving with one query over the complete
represented goal set. Attach the exact start and every represented goal to one
query graph and terminate when any goal is optimally settled.

For Dijkstra:

\[
h(n)=0.
\]

For A* under integrated actuator length, use the represented-set lower bound

\[
h(n)=\min_{g\in G_{\mathrm{rep}}}\|u_n-u_g\|_2,
\]

or another explicitly tested admissible bound. Report:

- total query expansions;
- generated and stale/reopened entries;
- selected goal candidate;
- all query attachments;
- heuristic name and goal-set cardinality.

Do not report the winning candidate's isolated expansion trace as though it were
the cost of one multi-goal query.

### 2. Goal-set parity for RRTConnect

Initialize the goal tree with every accepted frozen goal candidate. Each root
retains goal-sample ID, represented Cartesian point, IK family, and candidate
index. The first connected root determines the selected goal; all roots remain
part of the declared query.

PRM continues to attach every represented goal. Direct planners continue to
minimize over all valid represented candidates.

### 3. Candidate provenance and residual contract

Preserve candidate identity through selection. A successful goal-region result
must expose, when defined:

```text
goal_sample_id
goal_sample_index
goal_sample_point
ik_family
candidate_generator_id
```

Do not rely on audit-only post hoc matching when the planner already selected a
known candidate.

Separate residuals by meaning:

- `physical_goal_residual`: residual from the original task predicate;
- `goal_margin`: signed distance to the physical tolerance boundary when
  meaningful;
- `representation_residual`: error associated with represented samples or IK;
- `attachment_residual`: numerical query-overlay or state reconstruction error.

The main HTML table displays the physical task residual. Representation and
attachment residuals remain diagnostics.

### 4. Continuous trajectory evaluation

Add one shared evaluator that accepts a trajectory plus the connector policy
used by the planner and reconstructs each local motion. It returns a versioned
record containing:

- per-segment sampled U, Q, and X arrays;
- integrated \(L_U\), \(L_Q\), and \(L_X\);
- waypoint and sample counts;
- segment validity/failure information;
- start/end physical residuals;
- connector identity and sampling policy.

Direct planners, lattice planners, PRM, RRTConnect, and optional OMPL result
translation use this evaluator for fresh V3.6C reporting. Frozen results are not
rewritten.

### 5. Native PRM/RRT U/Q/X traces

PRM traces retain accepted sample states, accepted edge endpoints, exact start
attachments, every goal attachment, roadmap-search expansion order, and final
path. RRTConnect traces retain every inserted state, parent state, tree identity,
all goal roots, connection event, and final path.

Render construction/growth in:

1. U state space;
2. Q projection;
3. Cartesian X projection.

Every displayed edge is reconstructed through the declared local motion before
projection. The report includes final static views for all ten tasks and
synchronized contact-sheet/animation views for the designated representative
tasks.

### 6. Q-side actuator metric nomenclature

The V3.6B field currently called `M_Q` is the actuator-travel metric expressed in
Q:

\[
M_Q^{(U)}(q)
=J_{g^{-1}}(q)^\mathsf T J_{g^{-1}}(q),
\qquad
ds_U^2=dq^\mathsf T M_Q^{(U)}dq.
\]

Use the code/report name `actuator_metric_on_q` for new V3.6C records. Preserve
legacy V3.6B JSON as frozen provenance.

Report:

- \(\lambda_{\min}\) and \(\lambda_{\max}\);
- \(\sqrt{\det M_Q^{(U)}}\) as a local scale diagnostic;
- \(\kappa(M_Q^{(U)})\);
- \(\sqrt{\kappa(M_Q^{(U)})}\), labeled directional actuator-cost ratio;
- sparse metric ellipses in Q.

Four-bar and gearbox paired fields use one shared logarithmic color scale. The
report states that this condition number measures transmission anisotropy, not
Cartesian manipulator dexterity and not total path cost.

### 7. Readable family metrics

Each trial page includes compact family-specific tables rather than hiding them
only in raw JSON:

- lattice: expansions, generated, stale/reopened, attachments, path edges;
- PRM: requested/accepted samples, vertices, attempted/accepted edges, start and
  goal attachments, search expansions;
- RRTConnect: iterations, accepted extensions, nearest-neighbor operations,
  start/goal tree sizes, goal-root count, connection step;
- common: objective cost, integrated U/Q/X lengths, selected candidate,
  physical residual, validity checks, and phase timings.

## Work packages

### V3-630 — Closeout contract, activation, and artifact freeze

Land this sprint contract, completed Gate B findings, decision note, sprint-index
changes, and ACTIVE_SPRINT authorization. Add a guard that refuses to write into
frozen `v3_6_*` and `v3_6b_*` result directories from the V3.6C exporter.

### V3-631 — Goal-candidate identity and residual model

Preserve `StateCandidate` provenance through common selection helpers and result
assembly. Add typed/serialized physical, representation, and attachment
residuals with explicit failure behavior.

### V3-632 — Multi-goal graph query

Add a reusable goal-set graph-search contract and query overlay supporting one
exact start plus all represented goals. Implement Dijkstra and admissible A* to
that set, with one expansion trace and unambiguous total-work metrics.

### V3-633 — Roadmap/tree goal parity

Convert RRTConnect to a multi-root goal tree. Verify PRM and RRTConnect consume
the same ordered frozen candidate set, preserve exact starts, and return selected
candidate provenance.

### V3-634 — Continuous trajectory evaluation

Implement the shared local-motion reconstruction/evaluation record. Route fresh
direct, lattice, roadmap, tree, and OMPL audit results through it without
changing planner objective semantics.

### V3-635 — Native U/Q/X trace rendering

Extend trace payloads and renderers so PRM accepted edges, query search, RRT
parent edges, roots, and final paths are visible as synchronized physical motions
in U, Q, and X.

### V3-636 — Actuator metric on Q

Rename fresh records/labels, add eigenvalue and directional-ratio diagnostics,
metric ellipses, and one paired logarithmic scale. Document the interpretation in
the report.

### V3-637 — Frozen shared-Q sampled-roadmap diagnostic

Generate one deterministic Q sample set and adjacency per task (or one declared
reusable bank when task-independent), attach the same exact start and goal set,
and run Dijkstra/A* with mechanism-specific integrated actuator weights. Keep it
separate from native PRM rows.

### V3-638 — Report and regression suite

Add the V3.6C config/exporter/report target, readable family metrics, raw records,
link checks, print fallbacks, trace noninterference checks, and V1–V3.6B plus
provisional-V3.7 regression coverage.

### V3-639 — Clean generation and closeout review

Commit implementation first. From that clean revision, generate
`results/v3_review/v3_6c_planar2r_closeout/` and commit the artifact separately.
Update the Gate B disposition and ACTIVE_SPRINT only after the new report is
reviewed. Do not automatically activate V3.7.

## Proposed source targets

```text
src/inequality_mechanisms/
├── core/
│   ├── state.py
│   ├── goals.py
│   ├── results.py
│   └── trajectory_metrics.py
├── search/
│   ├── graph_solver.py
│   └── v2_objectives.py
├── graphs/
│   ├── query_overlay.py
│   └── goal_set_query_overlay.py          # new when a separate type is cleaner
├── planners/
│   ├── sampling_space.py
│   ├── roadmap/prm.py
│   └── tree/rrt_connect.py
├── audits/
│   ├── metrics.py
│   ├── traces.py
│   ├── planar2r_visual.py
│   ├── trajectory_evaluation.py           # new
│   └── html_report.py
└── visualization/
    ├── audit_graphs.py
    ├── audit_search.py
    └── audit_animation.py

configs/v3/planar2r_closeout_v1.json
scripts/export_v3_6c_planar2r_closeout.py
tests/v3/test_v3_6c_planar2r_closeout.py
results/v3_review/v3_6c_planar2r_closeout/
```

The exact module split may differ if existing generic types can be extended
without coupling audit behavior into core planner contracts.

## Required tests and invariants

1. One multi-goal Dijkstra/A* query receives every represented candidate exactly
   once and selects the same optimum as exhaustive exact-candidate reference
   solving.
2. A* and Dijkstra agree on cost and selected goal under deterministic tie rules;
   the heuristic is verified against exact cost-to-go to the entire goal set.
3. Graph expansion metrics state whether they are total query work; no winning-
   candidate-only count is exposed under the generic `expansions` name.
4. RRTConnect initializes all goal roots, preserves their provenance, and can
   select a non-first candidate in a deterministic fixture.
5. Direct, PRM, RRTConnect, lattice, and OMPL translation retain selected
   candidate ID/IK provenance when the candidate is represented explicitly.
6. All planners report the same physical task residual for the same selected
   state; representation and attachment residuals are separately named.
7. Continuous path metrics and plotted U/Q/X samples come from the same rebuilt
   local motions. Waypoint chords are labeled diagnostics only when retained.
8. PRM/RRT trace mode does not change selected goal, path, objective cost,
   status, or standard planner metrics.
9. Every accepted native roadmap/tree edge shown in Q or X maps back to the same
   authoritative U edge and declared connector.
10. The equal-ratio gearbox field has \(\kappa(M_Q^{(U)})\approx1\) within
    tolerance; four-bar fields remain finite on the certified branch; paired
    plots share color limits.
11. The frozen shared-Q sampled roadmap has identical Q samples and adjacency
    across mechanisms and differs only through physical U realization, edge
    validity when genuinely mechanism-dependent, and integrated actuator cost.
12. V3.6C exporter refuses frozen output paths and writes a manifest containing
    implementation revision, config, task IDs, trace schema, metric schema, and
    artifact version.
13. V1, V2, V3.0–V3.6B, and provisional V3.7 regressions remain green.

## Exit criteria

1. Every planner family consumes one exact start and the same declared frozen
   represented goal set, or is explicitly labeled as a diagnostic with different
   representation semantics.
2. Lattice Dijkstra/A* run one true goal-set query and report unambiguous total
   exploration.
3. RRTConnect uses all represented goal candidates and retains selected-goal
   provenance.
4. Physical, representation, and attachment residuals are separated and readable.
5. Every fresh path metric and U/Q/X plot is derived from the same continuous
   local motions.
6. Native PRM/RRT construction and query traces are inspectable in U, Q, and X;
   projected crossings never imply false connectivity.
7. `actuator_metric_on_q` is named, scaled, and interpreted correctly, including
   directional actuator-cost ratio and paired metric ellipses.
8. Native PRM is presented as a roadmap-family control; the frozen shared-Q
   sampled roadmap is separately labeled and auditable.
9. Family-specific metrics are visible in HTML and complete in raw records.
10. The new report is generated from a clean implementation revision under
    `results/v3_review/v3_6c_planar2r_closeout/`; frozen evidence is unchanged.
11. Gate B findings are marked corrected or consciously deferred with a named
    blocker. No unresolved V3.6C blocker is silently moved into V3.7.
12. ACTIVE_SPRINT returns to no authorization after closeout. Residual V3.7 may
    be activated only in a separate planning change.

## Non-goals

- new mechanism populations or inference;
- changing the ten-task physical bank or tuning per mechanism;
- obstacles, self-collision, MoveIt, or 6R;
- closing deferred planner breadth beyond the one shared-Q diagnostic;
- noninjective/full-cycle mechanisms;
- overwriting any frozen V2, V3.5, V3.6, V3.6B, or provisional V3.7 artifact;
- ranking mechanisms with a hidden composite score.
