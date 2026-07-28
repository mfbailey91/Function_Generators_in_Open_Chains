# Sprint Four Backlog — Search Geometry Attribution

> **Status:** P0 (S4-01–S4-05) is the current implementation target.
> P1/P2 (S4-06–S4-12) is deferred follow-up. See
> `docs/notes/SPRINT_FOUR_P0_STATUS.md`.

## Objective

Determine how mechanism-induced graph topology, edge weighting, heuristic quality,
and path quality separately contribute to observed planning behavior.

Sprint Four moves beyond the question:

> Does the four-bar expand more or fewer nodes than the gearbox?

The sprint instead asks:

> On the same physical input-state graph, how do edge metric, heuristic
> information, and mechanism geometry separately affect search effort and the
> quality of the path returned?

The central implementation remains:

\[
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X
\]

with:

- graph state identity and adjacency in actuator space \(\mathcal U\);
- mechanism validity and shared joint limits evaluated in output space
  \(\mathcal Q\);
- task interpretation and path metrics evaluated across
  \(\mathcal U\), \(\mathcal Q\), and Cartesian space \(\mathcal X\).

## Sprint theme

> Separate topology, metric, heuristic, and path quality.

## Background

The current implementation searches an input-side graph while using
output-space displacement as the default edge cost:

\[
c_Q(a,b)
=
d_{\mathcal Q}
\left(
g_m(u_a),
g_m(u_b)
\right).
\]

This is physically appropriate for preserving hidden mechanism state and
multiple input preimages, but it combines several effects:

1. the valid-node and valid-edge topology induced by the mechanism;
2. periodicity and multiple-preimage structure in \(\mathcal U\);
3. the pullback metric induced by \(g_m\);
4. the compatibility and strength of the A* heuristic;
5. the quality of the final path in input, output, and Cartesian coordinates.

Sprint Four should make those effects independently measurable.

## Sprint question

> When the physical graph and matched task are held fixed, which observed
> differences are caused by topology, edge metric, heuristic guidance, and path
> geometry?

## Scope

Sprint Four includes:

1. making edge-cost selection fully configuration driven;
2. defining a cost-and-heuristic compatibility contract;
3. recording path length in \(\mathcal U\), \(\mathcal Q\), and \(\mathcal X\);
4. measuring A* savings relative to Dijkstra;
5. measuring exact or near-exact heuristic error on representative graphs;
6. visualizing cost fields, distance fields, and expansion basins;
7. running a controlled factorial experiment across mechanisms, costs, and
   search algorithms;
8. relating mechanism descriptors to search effort and path quality;
9. running a limited monotonic-branch uniform-\(\mathcal Q\) representation
   control.

Sprint Four excludes:

- reinforcement learning;
- dynamics and torque-limited planning;
- collision checking;
- mechanism optimization;
- physical hardware;
- generalized \(SE(3)\) mechanism outputs;
- new biological claims;
- replacing the accepted input-space state representation.

## Architectural decision preserved

The authoritative physical state remains the complete actuator configuration:

\[
v \leftrightarrow \mathbf u \in \mathcal U.
\]

Output and Cartesian coordinates remain attached data:

\[
\mathbf q = g_m(\mathbf u),
\qquad
\mathbf x = f(\mathbf q).
\]

A full-cycle four-bar may satisfy:

\[
u_a \neq u_b,
\qquad
g_m(u_a)=g_m(u_b).
\]

Those states must remain distinct. Sprint Four varies how the existing physical
graph is measured and searched; it does not collapse the graph into ordinary
output coordinates.

---

# P0 — Required infrastructure

## S4-01 Implement a configuration-driven cost registry

Expose the following edge-cost types through the normal configuration schema,
experiment runner, result metadata, and command-line workflow:

### Uniform edge count

\[
c_{\mathrm{uniform}}(a,b)=1.
\]

This minimizes the number of legal graph transitions:

\[
C_{\mathrm{uniform}}(\pi)=N_{\mathrm{path\ edges}}.
\]

### Input-space Euclidean distance

\[
c_U(a,b)
=
d_{\mathcal U}(u_a,u_b).
\]

This minimizes actuator-coordinate travel:

\[
L_U
=
\sum_k
d_{\mathcal U}(u_k,u_{k+1}).
\]

Periodic input axes must use physically correct wrapped displacement where
periodic boundaries are enabled.

### Output-space Euclidean distance

\[
c_Q(a,b)
=
d_{\mathcal Q}
\left(
g_m(u_a),
g_m(u_b)
\right).
\]

This remains the primary Version-1 mechanism-induced metric:

\[
L_Q
=
\sum_k
d_{\mathcal Q}
\left(
q_k,q_{k+1}
\right).
\]

### Configuration example

```yaml
cost:
  type: uniform
```

```yaml
cost:
  type: input_euclidean
```

```yaml
cost:
  type: output_euclidean
```

### Requirements

- use one shared graph for all cost ablations in a paired trial;
- keep valid nodes, valid edges, start, goal, seed, and mechanism fixed;
- record the selected cost type in every result row;
- reject unknown cost names during configuration validation;
- do not require notebook-only cost injection.

**Deliverable:** cost registry, schema update, configuration examples, and tests.

## S4-02 Define a cost-and-heuristic contract

Create one planning-objective resolver that returns a compatible pair:

```python
@dataclass(frozen=True)
class PlanningObjective:
    edge_cost: EdgeCost
    heuristic: Heuristic
    cost_name: str
    heuristic_name: str
```

Required supported combinations:

| Edge cost | Compatible A* heuristic |
| --- | --- |
| Uniform edge count | admissible grid-step lower bound or zero |
| Input Euclidean | admissible input-space distance |
| Output Euclidean | admissible output-space distance |
| Unknown custom cost | zero unless an explicit heuristic is supplied |

### Requirements

- A* must not silently reuse an unrelated heuristic.
- A zero heuristic must remain available for every nonnegative edge cost.
- Dijkstra and A* must return the same optimal cost for all supported
  cost-and-heuristic pairs.
- The result schema must record both the edge metric and heuristic.
- The experiment runner must resolve the objective from configuration.

**Deliverable:** objective resolver, admissibility tests, and updated search API.

## S4-03 Add complete path-metric instrumentation

For every solved path, calculate and store:

\[
N_{\mathrm{edges}},
\]

\[
L_U
=
\sum_k d_{\mathcal U}(u_k,u_{k+1}),
\]

\[
L_Q
=
\sum_k d_{\mathcal Q}(q_k,q_{k+1}),
\]

\[
L_X
=
\sum_k
\|x_{k+1}-x_k\|_2,
\]

and:

\[
C^*_{\mathrm{selected\ metric}}.
\]

Minimum result fields:

```text
n_path_edges
path_length_u
path_length_q
path_length_x
optimal_cost
cost_type
heuristic_type
```

### Required invariants

Under uniform edge cost:

\[
C^*=N_{\mathrm{edges}}.
\]

Under input-Euclidean edge cost:

\[
C^*=L_U.
\]

Under output-Euclidean edge cost:

\[
C^*=L_Q.
\]

These equalities should hold within an explicit numerical tolerance.

**Deliverable:** reusable path-metrics module, result-schema update, and tests.

## S4-04 Add reverse-search and exact cost-to-go diagnostics

Implement reverse Dijkstra or an equivalent exact graph-distance calculation for
representative static graphs:

\[
h^*(u)=d(u,u_g).
\]

For each supported A* heuristic, record:

\[
e_h(u)=h^*(u)-h(u),
\]

and, where \(h^*(u)>0\),

\[
r_h(u)
=
\frac{h(u)}{h^*(u)}.
\]

Summary statistics should include:

- mean heuristic error;
- median heuristic error;
- maximum heuristic error;
- mean normalized heuristic strength;
- heuristic strength along the optimal path;
- heuristic strength over expanded nodes.

### Requirements

- verify admissibility:

\[
0\le h(u)\le h^*(u);
\]

- support sampled-node diagnostics for large graphs;
- preserve deterministic sampling under a fixed seed;
- store diagnostic configuration and sample count.

**Deliverable:** reverse-distance API, heuristic-quality report, and tests.

## S4-05 Strengthen result reproducibility

Every Sprint Four run must store:

- run ID;
- configuration;
- seed;
- code revision;
- mechanism parameters;
- graph parameters;
- output-space definition;
- cost type;
- heuristic type;
- edge-validation policy;
- task endpoint requests and realized residuals;
- result schema version.

The same run configuration must reproduce identical graph structure, paths,
costs, and expansion counts.

---

# P1 — Controlled attribution experiments

## S4-06 Run the mechanism × cost × algorithm experiment

For each paired task, run:

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

All conditions within a paired trial must share:

- the requested output start and goal;
- selected input preimages for the relevant mechanism;
- graph resolution;
- periodicity mode;
- edge-validation policy;
- output limits;
- random seed;
- task acceptance criteria.

### Primary outputs

- expanded nodes;
- normalized expansion fraction;
- generated nodes;
- reopened nodes;
- runtime;
- optimal cost;
- path edges;
- \(L_U\);
- \(L_Q\);
- \(L_X\);
- task residual;
- reachable-node count;
- valid-node count.

### Primary comparisons

#### Topology-dominant behavior

If the four-bar differs under all three costs, investigate:

- valid-region topology;
- connected components;
- periodicity;
- duplicate preimages;
- endpoint selection;
- graph connectivity.

#### Metric-dominant behavior

If the four-bar differs primarily under \(c_Q\), attribute the effect to the
mechanism-induced pullback metric:

\[
M(u)
=
J_g(u)^\mathsf T J_g(u).
\]

#### Heuristic interaction

If Dijkstra and A* respond differently to the same metric, attribute the
difference to heuristic guidance rather than the graph alone.

#### Path-quality tradeoff

If expansions improve while \(L_U\), \(L_Q\), or \(L_X\) worsens, report the
tradeoff explicitly. Fewer expansions must not be treated as a complete measure
of mechanism quality.

**Deliverable:** versioned factorial experiment and paired summary tables.

## S4-07 Measure A* savings relative to Dijkstra

For every matched mechanism, task, and edge metric, calculate:

\[
S_A
=
1-
\frac{N_{\mathrm{A*}}}
{N_{\mathrm{Dijkstra}}}.
\]

Also record the absolute expansion difference:

\[
\Delta N_A
=
N_{\mathrm{Dijkstra}}
-
N_{\mathrm{A*}}.
\]

### Research question

> Does stronger mechanism-induced edge-weight variation make heuristic search
> more valuable, even when absolute A* expansions do not decrease?

### Required plots

- A* expansions versus Dijkstra expansions;
- A* savings by mechanism and cost type;
- heuristic strength versus A* savings;
- edge-cost variance versus A* savings;
- path length versus A* savings.

**Deliverable:** heuristic-savings analysis and plots.

## S4-08 Add search-landscape diagnostics

For selected representative trials, render the following over the input graph
\(\mathcal U\):

- valid-node mask;
- reachable-node mask;
- local edge-cost field;
- \(|dq/du|\) or mechanism Jacobian descriptors;
- Dijkstra distance from the start;
- exact distance to the goal;
- expanded-node mask;
- optimal path;
- input seams;
- goal-cost contour.

Define the goal-cost-ball fraction:

\[
\beta
=
\frac{
\left|
\left\{
u:
d(s,u)\le C^*
\right\}
\right|
}{
N_{\mathrm{reachable}}
}.
\]

Also define:

\[
\eta_{\mathrm{reachable}}
=
\frac{
N_{\mathrm{expanded}}
}{
N_{\mathrm{reachable}}
}.
\]

### Research question

> Do broad low-cost regions increase the number of states that remain
> competitive before the goal is settled?

### Required output bundle

```text
results/<run_id>/landscape/
├── valid_nodes.png
├── reachable_nodes.png
├── edge_cost_field.png
├── mechanism_gain_field.png
├── distance_from_start.png
├── distance_to_goal.png
├── expanded_mask.png
├── goal_cost_basin.png
├── optimal_path.png
└── landscape_metrics.json
```

**Deliverable:** search-landscape plotting module and representative diagnostic
bundle.

## S4-09 Extract mechanism and graph descriptors

For each mechanism axis and paired graph, record:

### Mechanism descriptors

- follower range;
- minimum, maximum, mean, and variance of \(|dq/du|\);
- low-gain fraction:

\[
\rho_\epsilon
=
\Pr
\left(
\left|
\frac{dq}{du}
\right|<\epsilon
\right);
\]

- high-gain fraction;
- near-reversal fraction;
- metric determinant statistics;
- metric condition-number statistics.

### Graph descriptors

- valid-node fraction;
- reachable-node fraction;
- connected-component count;
- number of discrete output preimages;
- edge-cost mean and variance;
- low-cost-edge fraction;
- goal-cost-ball fraction \(\beta\);
- shortest unweighted path length.

### Initial explanatory analyses

Relate expansions to:

\[
N_{\mathrm{expanded}}
\sim
\beta
+
\rho_\epsilon
+
\text{preimage count}
+
\text{component structure}.
\]

Relate A* savings to:

\[
S_A
\sim
\text{heuristic strength}
+
\text{edge-cost variation}
+
\beta.
\]

Use simple correlations and interpretable regressions first. Do not introduce a
complex predictive model until the basic relationships are understood.

**Deliverable:** descriptor table and explanatory analysis.

## S4-10 Add paired uncertainty estimates

For the Sprint Four primary metrics, calculate paired bootstrap confidence
intervals for:

- expansion difference;
- normalized expansion difference;
- A* savings difference;
- optimal-cost difference;
- \(L_U\) difference;
- \(L_Q\) difference;
- \(L_X\) difference;
- runtime difference;
- goal-cost-ball difference.

Store:

- bootstrap seed;
- number of bootstrap samples;
- confidence level;
- interval method;
- excluded and failed trial counts.

---

# P2 — Representation control

## S4-11 Implement a monotonic-branch uniform-\(\mathcal Q\) control

For a four-bar restricted to a one-to-one operating branch:

\[
q=g(u),
\qquad
u=g^{-1}(q),
\]

construct a regular output grid:

\[
q_i=q_{\min}+i\Delta q.
\]

Compare it with the existing regular input grid:

\[
u_i=u_{\min}+i\Delta u.
\]

### Purpose

This experiment asks:

> Does the observed planning behavior come from the nonlinear mechanism map
> itself, or from sampling the mechanism uniformly in actuator coordinates?

### Required controls

- monotonic branch only;
- no duplicate output preimages;
- no periodic boundary;
- matched output limits;
- matched output start and goal;
- matched or explicitly reported node count;
- same output-space path objective;
- same edge-validation policy where applicable.

### Required outputs

- expansions;
- normalized expansions;
- path edges;
- \(L_U\);
- \(L_Q\);
- \(L_X\);
- task residual;
- node count;
- output-resolution distribution.

### Explicit limitation

This is an experimental control, not a replacement for the accepted physical
state representation. A full-cycle \(q\)-only graph remains invalid when
multiple input states share one output coordinate.

**Deliverable:** monotonic uniform-\(\mathcal Q\) experiment and comparison
report.

## S4-12 Defer lifted output-state search

A future planner may represent state as:

\[
(q,\sigma),
\]

where \(\sigma\) identifies the mechanism preimage, branch, winding sector, or
assembly state.

Sprint Four should document this as a future alternative but should not
implement it unless all P0 and P1 work is complete.

---

# Standard Sprint Four figures

The Sprint Four runner should generate at minimum:

1. paired expansion differences by cost type;
2. normalized expansion differences by cost type;
3. A* versus Dijkstra expansion scatter;
4. A* savings by mechanism and cost;
5. \(L_U\), \(L_Q\), and \(L_X\) comparisons;
6. expansions versus goal-cost-ball fraction;
7. expansions versus low-gain fraction;
8. heuristic strength versus A* savings;
9. representative search-landscape figures;
10. monotonic uniform-\(\mathcal U\) versus uniform-\(\mathcal Q\) comparison.

# Standard Sprint Four tables

The result package should include:

1. run summary;
2. task acceptance and exclusion counts;
3. graph-size and connectivity summary;
4. search results by mechanism, cost, and algorithm;
5. path metrics by mechanism, cost, and algorithm;
6. heuristic-quality summary;
7. mechanism descriptors;
8. paired effect sizes and confidence intervals.

# Recommended execution order

1. S4-01 — cost registry;
2. S4-02 — cost-and-heuristic contract;
3. S4-03 — path metrics;
4. S4-04 — reverse-search diagnostics;
5. S4-05 — reproducibility updates;
6. S4-06 — factorial experiment;
7. S4-07 — A* savings;
8. S4-08 — search-landscape diagnostics;
9. S4-09 — mechanism and graph descriptors;
10. S4-10 — paired uncertainty estimates;
11. S4-11 — monotonic uniform-\(\mathcal Q\) control;
12. S4-12 — future-state documentation.

# Sprint exit criteria

Sprint Four is complete when:

1. uniform, input-Euclidean, and output-Euclidean costs are selectable through
   the normal configuration system;
2. every A* run uses and records a compatible heuristic;
3. Dijkstra and A* agree on optimal cost for every supported objective;
4. every solved path records path edges, \(L_U\), \(L_Q\), and \(L_X\);
5. exact cost-to-go and heuristic error can be calculated on representative
   graphs;
6. the same paired tasks have been run across all three costs and both search
   algorithms;
7. topology-dominant and metric-dominant effects can be distinguished;
8. A* savings relative to Dijkstra are reported;
9. goal-cost-ball fraction is measured and compared with node expansions;
10. mechanism descriptors are related to search and path metrics;
11. paired confidence intervals are generated for the primary results;
12. at least one monotonic uniform-\(\mathcal Q\) control is complete;
13. one versioned command reproduces the Sprint Four result package.

# Definition of done

Every Sprint Four issue requires:

1. implementation;
2. unit and regression tests;
3. documented interface;
4. defined failure behavior;
5. a minimal reproducible example;
6. configuration-schema updates where relevant;
7. result-schema updates where relevant;
8. deterministic behavior under fixed seeds;
9. no required notebook-only logic;
10. updated ADR or design note when an architectural decision changes;
11. inclusion in the versioned Sprint Four experiment runner.

# Expected Sprint Four conclusion format

Sprint Four should not force a predetermined result. Its final report should
classify the observed mechanism effects using the following structure:

## Topology effect

What changes remain under uniform and input-space costs?

## Metric effect

What changes appear specifically under output-space cost?

## Heuristic effect

How much does A* reduce work relative to Dijkstra, and how does that relate to
heuristic quality?

## Path-quality effect

What happens to actuator, output, and Cartesian path lengths?

## Representation effect

What changes when a monotonic mechanism is sampled uniformly in \(\mathcal Q\)
rather than uniformly in \(\mathcal U\)?

The intended outcome is a defensible causal decomposition:

\[
\text{mechanism}
\rightarrow
\begin{cases}
\text{graph topology},\\
\text{edge metric},\\
\text{heuristic quality},\\
\text{path geometry}
\end{cases}
\rightarrow
\text{observed planning behavior}.
\]
