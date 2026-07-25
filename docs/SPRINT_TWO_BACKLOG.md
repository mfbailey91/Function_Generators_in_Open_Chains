# Sprint Two Backlog

## Objective

Harden the mathematical and software definition of output configuration space
\(\mathcal Q\), remove avoidable experiment ambiguity, and complete the
controlled-science work needed before large Monte Carlo claims.

Sprint Two begins after the Version-1 pilot, mechanism population, and
equal-valid-node implementation. The emphasis is **trust before scale**.

## Sprint question

> After controlling graph size, coordinate conventions, task matching,
> periodicity, edge validity, metric choice, and grid resolution, what planning
> effects remain attributable to the mechanism map?

## Scope

Sprint Two includes:

1. freezing the topology, coordinates, and metric of \(\mathcal Q\);
2. making four-bar output coordinates continuous and seam-safe;
3. measuring and enforcing matched-task accuracy;
4. validating graph construction and search assumptions;
5. completing the controlled ablations;
6. reporting uncertainty and mechanism descriptors.

Sprint Two excludes:

- dynamics and torque-limited planning;
- collision checking;
- mechanism optimization;
- reinforcement learning;
- physical hardware;
- paper-level biological claims.

## Working design decision — output configuration space \(\mathcal Q\)

For the Sprint Two study, define the output configuration space as a product of
bounded, lifted revolute-joint coordinates:

\[
\boxed{
\mathcal Q =
[q_{1,\min},q_{1,\max}]
\times
[q_{2,\min},q_{2,\max}]
\subset \mathbb R^2
}
\]

Each output coordinate represents a physical revolute joint, but the admissible
rocker motion is represented on a continuous real-valued chart rather than as a
periodic angle.

The corresponding space semantics are:

- \(\mathcal U\): periodic on axes whose actuator crank physically completes a
  revolution;
- \(\mathcal Q\): bounded Euclidean coordinates over the shared joint-limit
  window;
- \(\mathcal X\): Cartesian task space.

Thus, for the present mechanism family:

\[
\mathcal U_i \simeq S^1,
\qquad
\mathcal Q_i \simeq [q_{i,\min},q_{i,\max}].
\]

The fact that both \(u_i\) and \(q_i\) are measured in radians does not imply
that they have the same topology.

### Why \(\mathcal Q\) is not periodic in Sprint Two

The four-bar input crank may travel through a full revolution and return to the
same actuator configuration. The follower is a rocker: it travels between two
extrema and reverses direction. It does not pass through its upper output limit
and reappear at its lower output limit.

A shortest-angle metric would therefore create physically invalid shortcuts.
For example, a joint limited to

\[
-170^\circ \le q \le 170^\circ
\]

cannot move from \(169^\circ\) to \(-169^\circ\) by crossing \(180^\circ\),
because that route leaves the admissible joint window. In the bounded output
chart, the relevant displacement is approximately \(338^\circ\), not
\(22^\circ\).

### Lifted-angle representation

A physically continuous follower path can cross the principal-value seam even
though the mechanism motion is smooth. For example:

\[
170^\circ,\ 175^\circ,\ 179^\circ,\ -178^\circ,\ -173^\circ
\]

should be represented in the output chart as:

\[
170^\circ,\ 175^\circ,\ 179^\circ,\ 182^\circ,\ 187^\circ.
\]

For a bounded revolute axis with chart center

\[
q_c = \frac{q_{\min}+q_{\max}}{2},
\]

lift a raw angle \(\theta\) to the equivalent angle nearest the chart center:

\[
\operatorname{lift}(\theta)
=
q_c +
\operatorname{wrap}_{(-\pi,\pi]}
(\theta-q_c).
\]

The bounded-revolute representation requires:

\[
0 < q_{\max}-q_{\min} < 2\pi.
\]

A future joint with a complete rotational range must use a distinct periodic
axis type rather than this bounded chart.

### Output displacement and distance

All output-space differences must use the shared output-space representation:

\[
\Delta_{\mathcal Q}(q_a,q_b)
=
\operatorname{canonicalize}_{\mathcal Q}(q_b)
-
\operatorname{canonicalize}_{\mathcal Q}(q_a),
\]

and the default edge metric remains:

\[
c(u_a,u_b)
=
\left\|
\Delta_{\mathcal Q}
\left(g(u_a),g(u_b)\right)
\right\|_2.
\]

Raw principal-angle subtraction and unconditional shortest-angle wrapping are
both prohibited in output-space costs, task residuals, heuristics, and limit
checks.

### Software architecture decision

The current mathematical model uses bounded Euclidean output coordinates, but
the software should support mixed semantics on a per-axis basis.

The shared output-space abstraction should eventually permit:

- bounded revolute axes;
- periodic revolute axes;
- prismatic axes;
- mixed products such as \(S^1 \times [a,b]\).

For Sprint Two, only bounded revolute output axes are required.

The output-space object owns:

- coordinate canonicalization;
- displacement;
- distance;
- bounds checking;
- axis topology;
- serialization.

Mechanisms own their raw maps \(q_{\mathrm{raw}}=g_m(u)\), while the shared
output-space object determines how those outputs are represented and compared
inside the experiment.

### Required implementation behavior

1. The gearbox and four-bar use the same output-space definition.
2. Four-bar follower ranges, pointwise forward maps, inverse maps, and stored
   task endpoints use the same lifted coordinate chart.
3. Output costs and A* heuristics use
   \(\Delta_{\mathcal Q}\), not raw subtraction.
4. Matched-task residuals are measured in the shared output-space metric.
5. Plotting and serialized results retain lifted output values so that paths do
   not contain false \(2\pi\) jumps.
6. Input-space periodicity remains independent of output-space periodicity.
7. No mechanism may silently choose its own output-angle convention.

### Acceptance examples

The design is accepted when tests demonstrate that:

- a smooth follower path crossing the principal-angle seam remains continuous;
- no edge receives an artificial near-\(2\pi\) output cost;
- bounded output limits do not admit circular shortcuts;
- inverse lookup accepts an equivalent raw angle and returns the correct lifted
  target;
- gearbox and four-bar task endpoints are compared in the same chart;
- A* and Dijkstra agree under the default output-space metric.

## P0 — Required before controlled Monte Carlo

### IM-032 Ratify output-space semantics

Convert the working design decision above into an accepted architecture record.

The ADR must establish that Sprint Two uses bounded, lifted revolute output
coordinates while preserving a per-axis software model that can later support
periodic revolute and prismatic axes.

Document:

- per-axis topology;
- coordinate lift and chart-center convention;
- displacement and distance definitions;
- limit semantics;
- behavior at principal-angle seams;
- ownership boundaries between mechanisms and the shared output space;
- consequences for forward maps, inverse maps, costs, heuristics, task
  residuals, serialization, and plots.

**Deliverable:** `docs/ADR-011-output-space-semantics.md`.

### IM-033 Implement an output-space abstraction

Add an explicit output-space object rather than using raw NumPy subtraction
throughout the codebase.

Minimum interface:

- `canonicalize(q)`;
- `displacement(q_from, q_to)`;
- `distance(q_from, q_to)`;
- `contains(q)`;
- serialization of axis types and bounds.

Version 1 may implement only bounded revolute coordinates, but the interface
should permit future mixtures of bounded revolute, periodic revolute, and
prismatic axes.

Replace direct output subtraction in:

- edge costs;
- A* heuristics;
- task matching;
- residual calculations;
- limit checks;
- path metrics.

### IM-034 Make four-bar output coordinates trial-consistent

Ensure the selected four-bar branch, follower-range calculation, runtime forward
map, inverse lookup, and stored task endpoints all use the same lifted output
coordinate chart.

Required tests:

- a follower curve crossing the principal-angle seam;
- forward values agreeing with the unwrapped follower range;
- inverse lookup accepting lifted target angles;
- no artificial near-\(2\pi\) edge cost;
- continuity over one full crank cycle;
- independent behavior on each axis.

### IM-035 Define cost and heuristic compatibility

Preserve output-space path length as the primary Version-1 edge metric:

\[
c(u_a,u_b) =
\left\|\Delta_{\mathcal Q}
\bigl(g(u_a),g(u_b)\bigr)\right\|_2.
\]

Require one of the following for A*:

1. the matching admissible output-space heuristic;
2. a user-supplied heuristic documented for the custom cost; or
3. a zero heuristic, reducing A* to Dijkstra.

A custom edge cost must not silently reuse an unrelated heuristic.

### IM-036 Record and enforce matched-task residuals

For every selected discrete start and goal preimage, store:

- requested output endpoint;
- realized discrete output endpoint;
- per-axis residual;
- output-space residual norm;
- number of continuous and discrete candidates.

Use an explicit output-space tolerance, not a tolerance inferred only from input
grid spacing. Reject or resample a paired task when either mechanism exceeds the
configured tolerance.

Add residual summary plots or tables to the run output.

### IM-037 Edge-validation sensitivity study

Run representative trials with:

- `edge_samples = 5`;
- `edge_samples = 9`;
- `edge_samples = 17`;
- `edge_samples = 33`;
- `edge_samples = 65`.

Report changes in:

- valid edges;
- connected components;
- task feasibility;
- optimal cost;
- expanded nodes.

If results do not stabilize, implement adaptive subdivision or a mechanism-aware
edge validator.

### IM-038 Regression and invariant test suite

Add invariant tests covering:

- no false seam jumps in \(\mathcal Q\);
- Dijkstra and A* optimal-cost agreement;
- heuristic admissibility for the default metric;
- shared output limits using the same coordinate chart;
- paired-task residual thresholds;
- deterministic task selection under fixed seeds;
- graph connectivity stability at the accepted edge-sampling level.

## P1 — Controlled science

### IM-019 Monotonic-branch ablation

Compare full-cycle four-bar graphs with graphs restricted to a monotonic follower
branch.

Report:

- valid-node count;
- connected components;
- duplicate output preimages;
- expansions;
- normalized expansion fraction;
- optimal path cost.

### IM-020 Periodic-boundary ablation

Compare periodic and nonperiodic input-grid boundaries while keeping all other
trial settings fixed.

Distinguish:

- true physical crank wrapping;
- artificial lattice-boundary shortcuts;
- output-space seam behavior.

### IM-021 Input-cost versus output-cost ablation

Compare:

1. uniform edge count;
2. input-space Euclidean displacement;
3. output-space displacement.

Use Dijkstra for metrics without a proven admissible A* heuristic. Report how
much of the observed search effect comes from topology versus metric weighting.

### IM-022 Grid-resolution sweep

Run matched experiments over several lattice shapes, including at minimum:

- `32 x 32`;
- `48 x 48`;
- `64 x 64`;
- `96 x 96`;
- `128 x 128`, when computationally practical.

Track convergence of:

- valid-node fraction;
- component structure;
- matched-task residual;
- optimal cost;
- expansion fraction;
- effect-size estimates.

### IM-023 Mechanism descriptor extraction

Record trial-level descriptors for each four-bar axis:

- follower range;
- mean, minimum, maximum, and variance of `abs(dq/du)`;
- fraction of the crank cycle near rocker extrema;
- number of discrete output preimages;
- valid-node fraction;
- connected-component count;
- edge-cost distribution;
- metric anisotropy or condition statistics.

Use these descriptors to explain, not merely report, search-performance changes.

### IM-024 Paired uncertainty estimates

Add paired bootstrap confidence intervals for:

- expansion difference;
- normalized expansion difference;
- log expansion ratio;
- optimal-cost difference;
- runtime difference.

Store bootstrap seed, sample count, interval method, and excluded-trial counts.

### IM-039 Multi-source and multi-goal task search

Treat all valid discrete preimages of the requested output start and goal as
candidate endpoint sets.

Implement or reduce to:

- a virtual super-source with zero-cost edges to all start preimages;
- termination on the first optimally settled goal preimage.

Compare against the current single-preimage policy to measure endpoint-selection
bias.

### IM-040 Compile constrained graphs

Optionally compile each static trial graph before repeated searches:

- cached valid-node mask;
- cached output configuration per node;
- deterministic adjacency;
- cached edge weights;
- connected-component labels.

Compiled and dynamic graph modes must produce identical paths, costs, and search
instrumentation.

### IM-041 Sprint Two experiment runner

Create one versioned configuration family and one command that runs the accepted
Sprint Two ablations and writes:

- trial-level JSONL or columnar data;
- run metadata;
- exclusion and failure counts;
- paired summary tables;
- confidence intervals;
- standard plots;
- mechanism-descriptor tables.

## P2 — Path quality and follow-on work

### IM-025 Cartesian self-intersection count

Measure self-intersections in the Cartesian end-effector path.

### IM-026 Detour ratio

Compare path length against a clearly defined lower bound in input, output, or
Cartesian space.

### IM-027 Cumulative turning

Measure directional variation along output and Cartesian paths.

### IM-028 Near-revisit metric

Measure whether a path returns near previously visited output or Cartesian
states without exactly repeating graph nodes.

### IM-029 Bidirectional Dijkstra

Implement only after graph and endpoint-set semantics are stable.

### IM-030 Reinforcement-learning environment specification

Deferred beyond Sprint Two. The deterministic planning study must first isolate
topology, metric, resolution, and endpoint-preimage effects.

## Recommended execution order

1. IM-032 — output-space decision;
2. IM-033 — output-space abstraction;
3. IM-034 — four-bar coordinate consistency;
4. IM-035 — cost/heuristic contract;
5. IM-036 — matched-task residuals;
6. IM-038 — regression suite;
7. IM-037 — edge-sampling sensitivity;
8. IM-019 through IM-022 — controlled ablations;
9. IM-023 and IM-024 — explanation and uncertainty;
10. IM-039 — endpoint-set ablation;
11. IM-040 and IM-041 — scale and reproducibility.

## Sprint exit criteria

Sprint Two is complete when:

1. an accepted ADR defines \(\mathcal Q\);
2. all output differences use the output-space abstraction;
3. seam-crossing regression tests pass;
4. every paired task records and satisfies an output residual tolerance;
5. default A* is demonstrably admissible and agrees with Dijkstra;
6. edge-validation results are stable at the accepted sampling policy;
7. monotonicity, periodicity, metric, and resolution ablations are reproducible;
8. paired uncertainty intervals and mechanism descriptors are generated;
9. one versioned command reproduces the Sprint Two result package.

## Definition of done

Every issue requires:

1. implementation;
2. tests;
3. documented interface;
4. defined failure behavior;
5. a minimal reproducible example;
6. updated ADR or design note when relevant;
7. configuration and result-schema updates when relevant;
8. no required notebook-only logic.
