# Sprint Five Backlog — Path Quality and Trajectory Character

## Objective

Add a compact, reusable path-quality layer that evaluates every solved path in:

\[
\mathcal U,
\qquad
\mathcal Q,
\qquad
\mathcal X.
\]

Sprint Five follows the Search Geometry Attribution work of Sprint Four.

Sprint Four asks:

> Why was this path computationally easy or difficult to find?

Sprint Five asks:

> Was the path itself any good, and in which space?

The sprint should determine whether a mechanism or search method produces paths
that are:

- short;
- direct;
- smooth;
- loop-free;
- non-repetitive;
- and consistent across actuator, output, and Cartesian coordinates.

## Sprint theme

> Search effort is not path quality.

## Sprint question

> When two planners solve the same matched task, how do their returned paths
> differ in actuator travel, output motion, Cartesian directness, turning, and
> loop-like behavior?

## Scope

Sprint Five includes:

1. finalizing path-length reporting in \(\mathcal U\), \(\mathcal Q\), and
   \(\mathcal X\);
2. adding path directness and detour metrics;
3. adding cumulative-turning metrics;
4. adding projected self-intersection metrics;
5. adding near-revisit metrics;
6. generating representative path-quality diagnostic cards;
7. comparing equal-cost paths returned by Dijkstra and A*;
8. running a small paired gearbox/four-bar path-quality study using Sprint Four
   outputs.

Sprint Five excludes:

- new search algorithms;
- trajectory smoothing;
- spline fitting;
- shortcutting;
- collision checking;
- velocity, acceleration, and jerk profiles;
- dynamic feasibility;
- torque or energy optimization;
- mechanism optimization;
- reinforcement learning;
- a composite path-quality score.

## Background

The project searches a physical graph in actuator space:

\[
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X.
\]

A returned path is a sequence of actuator-space graph states:

\[
\pi_U
=
(u_0,u_1,\ldots,u_N).
\]

The same path induces:

\[
\pi_Q
=
(g_m(u_0),g_m(u_1),\ldots,g_m(u_N)),
\]

and:

\[
\pi_X
=
(f(g_m(u_0)),f(g_m(u_1)),\ldots,f(g_m(u_N))).
\]

A path that is simple in the complete physical state space may appear folded,
self-crossing, or indirect after projection into \(\mathcal Q\) or
\(\mathcal X\).

Sprint Five should preserve these distinctions rather than reducing path
quality to one scalar.

---

# P0 — Core path-quality metrics

## S5-01 Finalize path-length reporting

For every solved path, calculate and store:

### Discrete path length

\[
N_{\mathrm{edges}}
=
N.
\]

### Actuator-space path length

\[
L_U
=
\sum_{k=0}^{N-1}
d_{\mathcal U}(u_k,u_{k+1}).
\]

### Output-space path length

\[
L_Q
=
\sum_{k=0}^{N-1}
d_{\mathcal Q}(q_k,q_{k+1}).
\]

### Cartesian path length

\[
L_X
=
\sum_{k=0}^{N-1}
\|x_{k+1}-x_k\|_2.
\]

Minimum result fields:

```text
n_path_edges
path_length_u
path_length_q
path_length_x
```

### Requirements

- reuse the Sprint Four path-metrics implementation where available;
- use the shared input-space and output-space distance definitions;
- preserve periodic input displacement where applicable;
- use canonicalized bounded output coordinates;
- store explicit units or coordinate conventions in run metadata.

### Required tests

- straight discrete path;
- path with a periodic input seam crossing;
- path with identical \(L_U\) and different \(L_Q\);
- path with identical \(L_Q\) and different \(L_X\);
- one-edge and zero-edge paths.

**Deliverable:** finalized path-length API and result-schema fields.

## S5-02 Add directness and detour ratios

For each path, compare traveled distance with endpoint displacement.

### Input-space directness ratio

\[
R_U
=
\frac{
L_U
}{
d_{\mathcal U}(u_s,u_g)
}.
\]

### Output-space directness ratio

\[
R_Q
=
\frac{
L_Q
}{
d_{\mathcal Q}(q_s,q_g)
}.
\]

### Cartesian directness ratio

\[
R_X
=
\frac{
L_X
}{
\|x_g-x_s\|_2
}.
\]

For ordinary paths:

\[
R_U \ge 1,
\qquad
R_Q \ge 1,
\qquad
R_X \ge 1,
\]

subject to the selected metrics and numerical tolerance.

### Interpretation

A value near one indicates a geometrically direct path.

A larger value indicates excess travel, but not necessarily a poor or
unnecessary path. In particular, the Cartesian straight line is a geometric
reference and may not be kinematically feasible.

Use the term:

> Cartesian directness ratio

rather than claiming that \(R_X\) measures optimality.

### Degenerate endpoints

If the start and goal coincide in a projected space, the denominator may be
zero even when the physical input states differ.

Required behavior:

- return a documented sentinel value or `None`;
- do not divide by zero;
- preserve the path length and endpoint residual;
- record the degeneracy in the result.

Minimum result fields:

```text
directness_ratio_u
directness_ratio_q
directness_ratio_x
directness_defined_u
directness_defined_q
directness_defined_x
```

**Deliverable:** directness metrics and edge-case tests.

## S5-03 Add cumulative turning

Measure directional variation along the path in output and Cartesian space.

For path points:

\[
z_0,z_1,\ldots,z_N,
\]

define segment vectors:

\[
v_k=z_{k+1}-z_k.
\]

For nonzero adjacent segments, define the turning angle:

\[
\alpha_k
=
\operatorname{atan2}
\left(
|\det(v_k,v_{k+1})|,
v_k^\mathsf T v_{k+1}
\right).
\]

Then define cumulative turning:

\[
T
=
\sum_k \alpha_k.
\]

Calculate:

\[
T_Q,
\qquad
T_X.
\]

### Why input-space turning is deferred

On a four-connected input grid, input-space turning may be dominated by lattice
orientation and deterministic tie-breaking rather than meaningful physical path
shape.

Sprint Five should therefore make \(T_Q\) and \(T_X\) primary. An input-space
turning value may be retained as an optional diagnostic but should not be a
headline result.

### Requirements

- ignore or merge zero-length projected segments;
- use one consistent angular range;
- document treatment of repeated output or Cartesian points;
- support paths with fewer than three distinct projected points.

Minimum result fields:

```text
cumulative_turning_q
cumulative_turning_x
```

**Deliverable:** cumulative-turning implementation and hand-worked tests.

## S5-04 Add projected self-intersection counts

Count intersections between nonadjacent line segments in:

\[
\pi_Q,
\qquad
\pi_X.
\]

Define:

\[
N_{\mathrm{cross},Q},
\qquad
N_{\mathrm{cross},X}.
\]

### Segment-pair exclusions

Do not count:

- adjacent segments sharing a path vertex;
- identical segment pairs;
- a segment against itself;
- ordinary endpoint contact caused solely by sequence adjacency.

Explicitly define behavior for:

- repeated projected points;
- collinear overlap;
- endpoint contact between nonadjacent segments;
- floating-point tolerance.

### Interpretation

A path can have:

\[
N_{\mathrm{cross},U}=0
\]

while:

\[
N_{\mathrm{cross},Q}>0
\]

or:

\[
N_{\mathrm{cross},X}>0.
\]

This is expected when distinct physical input states overlap after projection.

Minimum result fields:

```text
self_intersections_q
self_intersections_x
```

**Deliverable:** robust segment-intersection utility and regression tests.

## S5-05 Add near-revisit metrics

Literal crossings are brittle. A path may form a hook or nearly return to an
earlier location without crossing itself.

For path points \(z_i\), define a temporal exclusion window \(m\):

\[
d_{\mathrm{revisit}}
=
\min_{|i-j|>m}
d(z_i,z_j).
\]

Calculate:

\[
d_{\mathrm{revisit},Q},
\qquad
d_{\mathrm{revisit},X}.
\]

Also support a thresholded count:

\[
N_{\mathrm{revisit},\epsilon}
=
\#
\left\{
(i,j):
|i-j|>m,
\;
d(z_i,z_j)<\epsilon
\right\}.
\]

### Required configuration

```yaml
path_quality:
  revisit_exclusion_steps: 4
  revisit_threshold_q: 0.05
  revisit_threshold_x: 0.05
```

### Requirements

- define whether distances are point-to-point or segment-to-segment;
- Version 1 may use point-to-point distance;
- store the exclusion window and threshold in run metadata;
- normalize thresholds only when the normalization is explicit;
- do not compare thresholded counts across incompatible coordinate scales.

Minimum result fields:

```text
near_revisit_distance_q
near_revisit_distance_x
near_revisit_count_q
near_revisit_count_x
```

**Deliverable:** near-revisit metrics and threshold-sensitivity tests.

---

# P1 — Path-quality diagnostics and study

## S5-06 Generate path-quality cards

For each selected representative trial, generate a compact diagnostic figure
showing:

- input-space path;
- output-space path;
- Cartesian path;
- start and goal states;
- self-intersection markers;
- closest nonlocal revisit pair;
- relevant mechanism and planner metadata;
- path-quality summary.

Example summary:

```text
Mechanism: four_bar
Algorithm: astar
Cost: output_euclidean

Path edges: 74
L_U: 4.21
L_Q: 2.88
L_X: 3.46

R_U: 1.24
R_Q: 1.31
R_X: 1.57

T_Q: 5.82 rad
T_X: 7.14 rad

Q intersections: 0
X intersections: 1

Q near-revisit: 0.09
X near-revisit: 0.04
```

### Output bundle

```text
results/<run_id>/path_quality/
├── representative_trial_001.png
├── representative_trial_002.png
├── representative_trial_003.png
└── representative_trials.json
```

### Representative trial selection

Select examples deterministically using documented criteria such as:

- median expansion difference;
- largest Cartesian directness difference;
- largest cumulative-turning difference;
- path with a Cartesian self-intersection;
- path with the smallest near-revisit distance.

Do not select only visually dramatic examples.

**Deliverable:** path-quality visualization module and deterministic selection
logic.

## S5-07 Compare equal-cost Dijkstra and A* paths

For an admissible heuristic, Dijkstra and A* should return the same optimal cost,
but they may return different optimal paths when multiple equal-cost paths
exist.

For each matched run, record whether:

```text
same_optimal_cost
same_node_path
same_output_path
same_cartesian_path
```

When the costs agree but the paths differ, compare:

- \(N_{\mathrm{edges}}\);
- \(L_U\);
- \(L_Q\);
- \(L_X\);
- \(R_Q\);
- \(R_X\);
- \(T_Q\);
- \(T_X\);
- projected self-intersections;
- near-revisit distances.

### Research question

> Does search ordering select paths with different secondary qualities even
> when both planners are optimal under the configured edge metric?

### Requirements

- use deterministic tie-breaking;
- record the tie-breaking policy;
- do not treat a different path as an error when optimal costs agree;
- identify whether path differences occur primarily under uniform or weighted
  costs.

**Deliverable:** equal-cost path-degeneracy report.

## S5-08 Run a small paired path-quality study

Reuse the accepted Sprint Four task and mechanism population rather than
creating a large new experiment.

Evaluate:

\[
\{
\text{unit gearbox},
\text{four-bar}
\}
\times
\{
c_{\mathrm{uniform}},
c_U,
c_Q
\}
\times
\{
\text{Dijkstra},
\text{A*}
\}.
\]

### Primary metrics

- \(N_{\mathrm{edges}}\);
- \(L_U\);
- \(L_Q\);
- \(L_X\);
- \(R_U\);
- \(R_Q\);
- \(R_X\);
- \(T_Q\);
- \(T_X\);
- \(N_{\mathrm{cross},Q}\);
- \(N_{\mathrm{cross},X}\);
- \(d_{\mathrm{revisit},Q}\);
- \(d_{\mathrm{revisit},X}\).

### Primary comparisons

#### Mechanism comparison

Under the same configured edge objective:

- does the four-bar shorten the optimized quantity?
- what happens to nonoptimized path quantities?
- does the four-bar reduce or increase projected turning?
- does it reduce or increase near-revisits and self-intersections?

#### Cost comparison

For the same mechanism and task:

- how does optimizing \(L_U\) affect \(L_Q\) and \(L_X\)?
- how does optimizing \(L_Q\) affect actuator travel?
- does uniform edge count produce more path degeneracy?

#### Search comparison

For the same graph and edge objective:

- do Dijkstra and A* select different equal-cost paths?
- when they differ, which secondary path metrics change?

#### Search-effort versus path-quality comparison

Relate Sprint Four metrics to Sprint Five metrics:

- expansions versus \(L_X\);
- expansions versus \(R_X\);
- expansions versus \(T_X\);
- A* savings versus path directness;
- goal-cost-ball fraction versus path degeneracy.

The analysis should not assume that fewer expansions imply a shorter or smoother
path.

**Deliverable:** paired path-quality result package.

## S5-09 Add paired uncertainty estimates

Calculate paired bootstrap confidence intervals for:

- \(L_U\) difference;
- \(L_Q\) difference;
- \(L_X\) difference;
- \(R_Q\) difference;
- \(R_X\) difference;
- \(T_Q\) difference;
- \(T_X\) difference;
- self-intersection-count difference;
- near-revisit-distance difference.

Store:

- bootstrap seed;
- number of samples;
- interval method;
- confidence level;
- excluded and undefined metric counts.

For discrete sparse metrics such as self-intersection count, also report raw
frequencies and proportions.

---

# Standard Sprint Five figures

The Sprint Five runner should generate at minimum:

1. paired \(L_U\), \(L_Q\), and \(L_X\) comparisons;
2. output and Cartesian directness-ratio comparisons;
3. output and Cartesian cumulative-turning comparisons;
4. projected self-intersection frequency;
5. near-revisit-distance distributions;
6. Dijkstra versus A* equal-cost path comparison;
7. node expansions versus Cartesian directness;
8. node expansions versus cumulative turning;
9. representative path-quality cards.

# Standard Sprint Five tables

The result package should include:

1. run summary;
2. metric configuration and tolerance summary;
3. path-length summary;
4. directness-ratio summary;
5. cumulative-turning summary;
6. self-intersection and near-revisit summary;
7. equal-cost Dijkstra/A* path-degeneracy summary;
8. paired effect sizes and confidence intervals;
9. undefined and excluded metric counts.

# Recommended execution order

1. S5-01 — finalize path lengths;
2. S5-02 — directness ratios;
3. S5-03 — cumulative turning;
4. S5-04 — projected self-intersections;
5. S5-05 — near-revisit metrics;
6. S5-06 — path-quality cards;
7. S5-07 — equal-cost Dijkstra/A* comparison;
8. S5-08 — small paired study;
9. S5-09 — uncertainty estimates.

# Sprint exit criteria

Sprint Five is complete when:

1. every solved path reports \(N_{\mathrm{edges}}\), \(L_U\), \(L_Q\), and
   \(L_X\);
2. output and Cartesian directness ratios are available;
3. output and Cartesian cumulative turning are available;
4. output and Cartesian self-intersections are counted;
5. output and Cartesian near-revisits are measured;
6. metric edge cases and tolerances are documented;
7. all metrics have regression tests on hand-constructed paths;
8. representative path-quality cards are generated deterministically;
9. Dijkstra and A* equal-cost paths are compared for secondary quality;
10. a small paired gearbox/four-bar result package is reproducible;
11. paired uncertainty intervals are generated;
12. no unsupported composite path-quality score is introduced.

# Definition of done

Every Sprint Five issue requires:

1. implementation;
2. unit and regression tests;
3. documented metric definition;
4. documented coordinate space;
5. defined failure and degenerate-case behavior;
6. explicit numerical tolerances;
7. a minimal reproducible example;
8. configuration-schema updates where relevant;
9. result-schema updates where relevant;
10. deterministic behavior under fixed seeds;
11. no required notebook-only logic;
12. inclusion in the versioned Sprint Five experiment runner.

# Expected Sprint Five conclusion format

Sprint Five should report path quality without reducing it to one ranking.

## Length

How do mechanisms and objectives change:

\[
L_U,
\qquad
L_Q,
\qquad
L_X?
\]

## Directness

How much excess travel appears relative to endpoint displacement?

## Shape

How much turning occurs in output and Cartesian space?

## Projection effects

Do physically distinct input paths overlap, cross, or nearly revisit after
projection?

## Search-order effects

Do Dijkstra and A* select different equal-cost paths with different secondary
qualities?

## Search-effort tradeoff

Do fewer node expansions correspond to shorter or cleaner paths, or are search
effort and path quality largely independent?

The intended result is a multidimensional description:

\[
\text{path quality}
=
\left(
\text{length},
\text{directness},
\text{turning},
\text{crossing},
\text{revisit}
\right),
\]

evaluated separately in the spaces where each property has physical meaning.
