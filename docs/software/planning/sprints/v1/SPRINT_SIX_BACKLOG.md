# Sprint Six Backlog — Experimental Equivalence and Statistical Trust

## Objective

Build a defensible experimental foundation for comparing four-bar mechanisms
against linear gearbox baselines.

Sprint Six addresses three linked questions:

1. What gearbox should be considered an appropriate apples-to-apples control for
   a given four-bar?
2. At what graph resolution are the observed planning trends sufficiently
   stable?
3. How many independently sampled mechanisms and tasks are required before the
   Monte Carlo conclusions are trustworthy?

The sprint should convert these questions into explicit configuration,
calibration, and stopping rules.

## Sprint theme

> Match the baseline, calibrate the graph, and earn statistical confidence.

## Sprint question

> After matching the linear baseline to the four-bar, controlling graph
> resolution, and accounting for nested task sampling, which planning trends
> remain stable and statistically credible?

## Scope

Sprint Six includes:

1. implementing equivalent-gain gearbox baselines;
2. defining multiple matching rules for monotonic and full-cycle mechanisms;
3. ensuring gearbox and four-bar comparisons use matched input domains and graph
   dimensions where intended;
4. running a graph-resolution convergence study;
5. selecting a production graph resolution using documented criteria;
6. defining a hierarchical Monte Carlo design with tasks nested within
   mechanisms;
7. estimating the number of mechanism samples required from pilot variance;
8. adding sequential precision checks and stopping criteria;
9. running a high-resolution confirmation subset;
10. storing all equivalence, resolution, and sampling decisions in run metadata.

Sprint Six excludes:

- new search algorithms;
- new path-quality metrics;
- dynamics;
- collision checking;
- mechanism optimization;
- reinforcement learning;
- physical hardware;
- generalized spatial mechanism outputs;
- replacing the accepted input-space graph state.

## Background

The current project compares mechanism maps:

\[
\mathcal U
\xrightarrow{g_m}
\mathcal Q
\xrightarrow{f}
\mathcal X.
\]

A unit gearbox uses:

\[
q=u.
\]

A four-bar uses:

\[
q=g_{\mathrm{fb}}(u),
\]

with configuration-dependent gain:

\[
\frac{dq}{du}.
\]

The unit gearbox remains conceptually important as the identity transmission,
but it may not be the cleanest numerical control when the four-bar has a very
different average gain or output span.

Likewise, graph resolution affects:

- valid-node count;
- endpoint snapping;
- edge validation;
- connected components;
- path cost;
- path length;
- node expansions;
- runtime.

Finally, repeated tasks on the same mechanism are not independent observations.
A trustworthy Monte Carlo study must distinguish:

- between-mechanism variability;
- within-mechanism task variability;
- graph-resolution effects;
- finite Monte Carlo uncertainty.

---

# P0 — Equivalent gearbox baselines

## S6-01 Implement a general equivalent-gain gearbox

Add a gearbox control of the form:

\[
q_{\mathrm{gb}}(u)
=
q_{\mathrm{ref}}
+
r_{\mathrm{eq}}
\left(
u-u_{\mathrm{ref}}
\right).
\]

For a two-joint mechanism pair:

\[
\mathbf q_{\mathrm{gb}}
=
\mathbf q_{\mathrm{ref}}
+
\begin{bmatrix}
r_{\mathrm{eq},1} & 0\\
0 & r_{\mathrm{eq},2}
\end{bmatrix}
\left(
\mathbf u-\mathbf u_{\mathrm{ref}}
\right).
\]

The configuration must record:

- matching rule;
- equivalent ratio for each axis;
- input interval;
- output reference;
- output interval;
- whether the mechanism is monotonic or full-cycle;
- source four-bar parameters.

Minimum configuration example:

```yaml
mechanism:
  type: equivalent_gearbox
  matching_rule: span
  source_fourbar: fourbar_pair_001
```

**Deliverable:** equivalent gearbox implementation, schema support, and tests.

## S6-02 Add a span-matched gearbox for monotonic branches

For a monotonic four-bar branch:

\[
u\in[u_{\min},u_{\max}],
\qquad
q\in[q_{\min},q_{\max}],
\]

define:

\[
r_{\mathrm{span}}
=
\frac{
q_{\max}-q_{\min}
}{
u_{\max}-u_{\min}
}.
\]

For a monotonic branch, this is also the mean signed gain:

\[
r_{\mathrm{span}}
=
\frac{1}{\Delta u}
\int_{u_{\min}}^{u_{\max}}
\frac{dq}{du}\,du.
\]

### Required matching properties

The span-matched gearbox and four-bar should share:

\[
\Delta U_{\mathrm{gb}}
=
\Delta U_{\mathrm{fb}},
\]

and:

\[
\Delta Q_{\mathrm{gb}}
=
\Delta Q_{\mathrm{fb}}.
\]

Where intended, they should also share:

- identical input-grid dimensions;
- identical input-grid spacing;
- identical output limits;
- identical requested output tasks;
- identical search algorithms and metrics.

### Research purpose

> Compare a nonlinear transmission against a linear transmission with the same
> input and output span.

**Deliverable:** monotonic span-matched gearbox mode and invariant tests.

## S6-03 Add full-cycle gain-matching rules

For a full crank-rocker cycle:

\[
q(u_{\mathrm{end}})
=
q(u_{\mathrm{start}}),
\]

so the signed average gain is:

\[
\frac{1}{2\pi}
\int_0^{2\pi}
\frac{dq}{du}\,du
=
0.
\]

A zero-ratio gearbox is not a meaningful full-cycle equivalent.

Implement two explicit alternatives.

### Total-variation-matched gearbox

Define:

\[
r_{\mathrm{TV}}
=
\frac{1}{\Delta u}
\int
\left|
\frac{dq}{du}
\right|du.
\]

Equivalently:

\[
r_{\mathrm{TV}}
=
\frac{
\operatorname{TV}(q)
}{
\Delta u
}.
\]

This matches average output travel per unit input travel.

### RMS-gain-matched gearbox

Define:

\[
r_{\mathrm{RMS}}
=
\sqrt{
\frac{1}{\Delta u}
\int
\left(
\frac{dq}{du}
\right)^2du
}.
\]

This matches the average magnitude of the scalar pullback metric:

\[
M(u)
=
\left(
\frac{dq}{du}
\right)^2.
\]

### Required configuration

```yaml
mechanism:
  type: equivalent_gearbox
  matching_rule: total_variation
```

or:

```yaml
mechanism:
  type: equivalent_gearbox
  matching_rule: rms_gain
```

### Interpretation

The matching rule must be named explicitly in plots and tables.

Do not use the generic label:

> equivalent gearbox

without also recording the criterion of equivalence.

**Deliverable:** total-variation and RMS-gain matching modes with tests.

## S6-04 Preserve the unit gearbox as a separate baseline

The unit gearbox remains:

\[
q=u.
\]

It represents the identity transmission and the equal-robot baseline.

Sprint Six should therefore support at least:

1. unit gearbox;
2. span-matched gearbox;
3. total-variation-matched gearbox;
4. RMS-gain-matched gearbox;
5. four-bar.

The unit gearbox should not be replaced by equivalent-gain controls.

### Required comparison labels

```text
unit_gearbox
span_matched_gearbox
tv_matched_gearbox
rms_matched_gearbox
fourbar
```

**Deliverable:** baseline registry and naming standard.

## S6-05 Verify equivalence invariants

Add tests and run-time checks for the selected matching rule.

### Span matching

Verify:

\[
\Delta U_{\mathrm{gb}}
=
\Delta U_{\mathrm{fb}},
\]

\[
\Delta Q_{\mathrm{gb}}
=
\Delta Q_{\mathrm{fb}}.
\]

### Total-variation matching

Verify:

\[
r_{\mathrm{TV}}\Delta u
\approx
\operatorname{TV}(q_{\mathrm{fb}}).
\]

### RMS matching

Verify:

\[
r_{\mathrm{RMS}}^2
\approx
\frac{1}{\Delta u}
\int
\left(
\frac{dq}{du}
\right)^2du.
\]

### Graph matching

When the experiment requests matched input graphs, verify:

- identical grid shape;
- identical input-axis domain;
- identical periodicity setting;
- identical adjacency policy;
- identical edge-validation sampling policy.

**Deliverable:** equivalence diagnostics and failure behavior.

---

# P0 — Graph-resolution calibration

## S6-06 Implement a versioned resolution sweep

Run the same mechanism and task bank at:

\[
32\times32,
\quad
48\times48,
\quad
64\times64,
\quad
96\times96,
\quad
128\times128,
\]

when computationally practical.

Every resolution must reuse:

- the same mechanism parameters;
- the same requested output tasks;
- the same random seeds;
- the same endpoint-preimage policy;
- the same mechanism baseline definitions;
- the same search algorithms;
- the same edge metrics;
- the same edge-validation policy, unless edge validation itself is the
  calibrated variable.

### Required outputs

For each resolution, record:

- total nodes;
- valid nodes;
- reachable nodes;
- valid edges;
- connected components;
- task acceptance rate;
- endpoint residual;
- optimal cost;
- node expansions;
- normalized expansions;
- path edges;
- \(L_U\);
- \(L_Q\);
- \(L_X\);
- goal-cost-ball fraction;
- runtime;
- peak memory where practical.

**Deliverable:** resolution-sweep runner and result package.

## S6-07 Define graph-size scaling diagnostics

For an \(n\times n\) grid:

\[
|V|=n^2.
\]

For a nonperiodic four-connected grid:

\[
|E|
\approx
2n(n-1).
\]

For a fully periodic two-axis grid:

\[
|E|
\approx
2n^2.
\]

Record empirical scaling for:

- graph construction time;
- graph compilation time;
- Dijkstra runtime;
- A* runtime;
- memory use;
- number of valid edges;
- number of edge-validation samples evaluated.

### Research purpose

> Quantify the computational cost of refinement rather than treating
> resolution as a free accuracy improvement.

**Deliverable:** complexity and runtime scaling plots.

## S6-08 Define production-resolution selection criteria

Select the coarsest grid resolution that satisfies documented convergence
criteria.

The primary effect estimate should include at least:

\[
\log
\left(
\frac{
N_{\mathrm{expanded,fb}}+1
}{
N_{\mathrm{expanded,gb}}+1
}
\right).
\]

Candidate acceptance criteria:

1. the sign of the primary paired effect does not change at the next higher
   resolution;
2. the primary effect estimate changes by less than the configured tolerance;
3. confidence intervals substantially overlap;
4. endpoint residuals satisfy the accepted task tolerance;
5. connected-component structure is stable;
6. task feasibility is stable;
7. path-cost and path-length trends are stable;
8. graph-validity statistics are stable.

Example configuration:

```yaml
resolution_selection:
  max_relative_effect_change: 0.05
  require_sign_stability: true
  require_component_stability: true
  require_task_feasibility_stability: true
```

These thresholds are project decisions and must be recorded as such.

**Deliverable:** production-resolution ADR or design note.

## S6-09 Add a high-resolution confirmation subset

After selecting the production resolution, rerun a fixed representative subset
at the next higher practical resolution.

The confirmation subset should include:

- typical mechanisms;
- high-gain-variation mechanisms;
- large low-gain-fraction mechanisms;
- mechanisms near the accepted feasibility boundaries;
- trials with large gearbox/four-bar differences;
- trials near a null difference.

### Required conclusion

Report whether the headline effects survive refinement.

Do not require every individual path or expansion count to be identical.

**Deliverable:** high-resolution confirmation report.

## S6-10 Document grid anisotropy as a limitation

A four-connected graph permits axis-aligned moves only.

Refinement reduces step size but does not remove the adjacency model's intrinsic
directional bias.

Sprint Six should document:

> Grid refinement improves spatial resolution but does not make a
> four-connected graph isotropic.

An eight-connected or richer-motion-primitive ablation may be proposed for a
future sprint but is not required here.

**Deliverable:** documented limitation in methods and experiment metadata.

---

# P0 — Hierarchical Monte Carlo design

## S6-11 Define the independent sampling units

Let:

\[
M
=
\text{number of independently sampled mechanism pairs},
\]

and:

\[
K
=
\text{number of tasks per mechanism pair}.
\]

The total number of planning tasks is:

\[
N=MK.
\]

However, tasks on the same mechanism are not independent because they share:

- mechanism geometry;
- transmission curve;
- valid input region;
- graph topology;
- edge-weight field;
- connected components.

The primary generalization unit should therefore be the mechanism pair.

### Required analysis modes

Support at least one of:

1. aggregate task metrics into one summary per mechanism pair;
2. use a hierarchical bootstrap that resamples mechanisms first and tasks
   second;
3. fit an explicit hierarchical model.

Sprint Six should prefer mechanism-level summaries and hierarchical bootstrap
before introducing a more complex model.

**Deliverable:** documented sampling hierarchy and analysis implementation.

## S6-12 Implement mechanism-level effect summaries

For mechanism pair \(m\) and task \(k\), define a paired log expansion ratio:

\[
d_{mk}
=
\log
\left(
\frac{
N_{\mathrm{expanded,fb},mk}+1
}{
N_{\mathrm{expanded,gb},mk}+1
}
\right).
\]

Define the mechanism-level effect:

\[
d_m
=
\frac{1}{K_m}
\sum_{k=1}^{K_m}
d_{mk}.
\]

The overall mean effect is:

\[
\bar d
=
\frac{1}{M}
\sum_{m=1}^{M}
d_m.
\]

Also support mechanism-level summaries for:

- normalized expansions;
- optimal cost;
- \(L_U\);
- \(L_Q\);
- \(L_X\);
- A* savings;
- goal-cost-ball fraction.

### Requirements

- record the number of accepted tasks per mechanism;
- define minimum accepted tasks per mechanism;
- reject or flag mechanisms with insufficient task coverage;
- preserve paired gearbox/four-bar task identity.

**Deliverable:** mechanism-level summary table.

## S6-13 Implement hierarchical bootstrap confidence intervals

The bootstrap procedure should:

1. resample mechanism pairs with replacement;
2. within each selected mechanism, resample tasks with replacement;
3. recompute mechanism-level and overall effects;
4. repeat for the configured number of bootstrap samples.

Store:

- bootstrap seed;
- number of bootstrap samples;
- confidence level;
- interval method;
- mechanism count;
- task count;
- excluded mechanisms;
- excluded tasks.

### Required outputs

Confidence intervals for:

- expansion difference;
- log expansion ratio;
- normalized expansion difference;
- optimal-cost difference;
- path-length differences;
- A* savings;
- goal-cost-ball difference.

**Deliverable:** hierarchical bootstrap module and validation tests.

## S6-14 Estimate required mechanism count from pilot variance

After a pilot calibration run, estimate the number of independent mechanisms
required for a target 95% confidence-interval half-width \(h\).

If the mechanism-level effect has sample standard deviation \(s_d\), use the
planning approximation:

\[
M_{\mathrm{required}}
\approx
\left(
\frac{
1.96s_d
}{
h
}
\right)^2.
\]

This is an initial planning estimate, not a replacement for the hierarchical
bootstrap.

### Example interpretation

If:

\[
h=0.10,
\]

then the multiplicative uncertainty on a log ratio is approximately:

\[
e^{0.10}\approx1.105.
\]

The chosen precision target must be defined in the experiment plan.

**Deliverable:** sample-size planning report based on pilot variance.

## S6-15 Define staged Monte Carlo execution

Use three stages.

### Stage A — Resolution calibration

Recommended initial target:

\[
40\text{–}60
\]

mechanism pairs with approximately:

\[
20
\]

fixed tasks per mechanism.

Run the reduced primary condition set across all candidate resolutions.

### Stage B — Main study

Recommended starting target:

\[
150
\]

mechanism pairs with:

\[
20\text{–}30
\]

tasks per mechanism.

Add mechanisms in fixed batches.

### Stage C — Confirmation

Rerun:

\[
25\text{–}50
\]

representative mechanism pairs at the next higher resolution.

These are initial planning targets. The final sample count must be determined by
the precision checks.

**Deliverable:** staged execution configuration family.

## S6-16 Implement sequential precision monitoring

After each new mechanism batch, calculate:

- current mechanism count;
- current task count;
- mean mechanism-level effect;
- hierarchical bootstrap interval;
- confidence-interval half-width;
- change in effect estimate from the previous batch;
- sign stability;
- mechanism-ranking stability where relevant.

Example batch schedule:

```yaml
monte_carlo:
  initial_mechanisms: 100
  mechanism_batch_size: 50
  tasks_per_mechanism: 25
  target_ci_half_width: 0.10
```

### Stopping criteria

Stop the main study when all required conditions are met:

1. the primary confidence interval is narrower than the configured target;
2. the primary effect sign is stable over the last two batches;
3. the point estimate changes by less than the configured tolerance;
4. the minimum mechanism count is satisfied;
5. exclusion rates are below the accepted threshold;
6. the high-resolution confirmation subset does not reverse the conclusion.

The stopping rule must be fixed before examining the final batch results.

**Deliverable:** sequential precision report and deterministic stopping logic.

---

# P1 — Apples-to-apples experiment matrix

## S6-17 Run the baseline comparison matrix

At the selected production resolution, compare:

\[
\{
\text{unit gearbox},
\text{span-matched gearbox},
\text{TV-matched gearbox},
\text{RMS-matched gearbox},
\text{four-bar}
\}
\]

where each baseline is applicable.

### Monotonic branch matrix

Use:

- unit gearbox;
- span-matched gearbox;
- four-bar.

### Full-cycle matrix

Use:

- unit gearbox;
- TV-matched gearbox;
- RMS-matched gearbox;
- four-bar.

Run the accepted Sprint Four combinations of:

- edge cost;
- Dijkstra or A*;
- periodicity mode;
- task-matching policy.

### Primary questions

1. Does the four-bar effect persist after average gain is matched?
2. Does the result depend on whether matching is based on span, total
   variation, or RMS gain?
3. How much of the unit-gearbox difference was simply a scale mismatch?
4. Which effects remain attributable to nonlinearity, folding, and topology?

**Deliverable:** baseline-comparison result package.

## S6-18 Report matched and unmatched quantities explicitly

Every comparison table should identify which properties are matched.

Example:

| Comparison | Input span | Output span | Mean absolute gain | RMS gain | Topology |
| --- | --- | --- | --- | --- | --- |
| Unit gearbox vs four-bar | maybe | no | no | no | no |
| Span-matched vs monotonic four-bar | yes | yes | related | not required | no |
| TV-matched vs full-cycle four-bar | yes | no | yes | no | no |
| RMS-matched vs full-cycle four-bar | yes | no | no | yes | no |

This prevents the term “apples to apples” from hiding which quantities remain
different.

**Deliverable:** equivalence summary table in every Sprint Six report.

## S6-19 Reuse one fixed paired sample bank

The same mechanism and task bank should be reused across:

- gearbox baselines;
- edge metrics;
- Dijkstra and A*;
- selected graph resolutions;
- path-quality calculations.

### Requirements

- fixed mechanism IDs;
- fixed task IDs;
- fixed requested output endpoints;
- fixed seeds;
- fixed endpoint-preimage policy;
- explicit failure and exclusion records.

**Deliverable:** reusable sample-bank format and loader.

---

# P1 — Statistical and reporting safeguards

## S6-20 Prevent task-level pseudo-replication

Do not report task-level confidence intervals that treat all \(MK\) trials as
independent when tasks are nested within mechanisms.

Required reporting should include:

- mechanism count;
- task count;
- tasks per mechanism;
- cluster definition;
- mechanism-level effect distribution;
- hierarchical interval.

Task-level distributions may still be plotted, but they must not be presented
as independent population samples.

**Deliverable:** analysis assertions and reporting checks.

## S6-21 Report exclusions and feasibility

For every run, report:

- sampled mechanisms;
- accepted mechanisms;
- rejected mechanisms;
- requested tasks;
- accepted tasks;
- rejected tasks;
- failure reasons;
- mechanisms below minimum task coverage.

Common exclusion reasons should be coded, not stored only as free text.

**Deliverable:** exclusion schema and summary table.

## S6-22 Add Monte Carlo stability plots

Generate:

1. effect estimate versus mechanism count;
2. confidence-interval width versus mechanism count;
3. effect estimate by mechanism batch;
4. exclusion rate versus mechanism count;
5. resolution effect versus grid size;
6. runtime versus graph size;
7. valid-node fraction versus grid size;
8. task-feasibility rate versus grid size.

**Deliverable:** stability and convergence visualization package.

---

# Standard Sprint Six figures

The Sprint Six runner should generate at minimum:

1. four-bar gain curve with matched linear gearbox lines;
2. span-, TV-, and RMS-matching comparison;
3. node count versus grid resolution;
4. runtime versus grid resolution;
5. primary effect estimate versus grid resolution;
6. path metrics versus grid resolution;
7. endpoint residual versus grid resolution;
8. confidence-interval width versus mechanism count;
9. effect estimate versus mechanism count;
10. unit versus equivalent-gain gearbox comparisons;
11. high-resolution confirmation comparison.

# Standard Sprint Six tables

The result package should include:

1. run summary;
2. equivalence-definition table;
3. gearbox-ratio table;
4. graph-resolution summary;
5. convergence-criteria results;
6. production-resolution decision;
7. mechanism/task sample hierarchy;
8. exclusions and failures;
9. mechanism-level effect summaries;
10. hierarchical confidence intervals;
11. sequential precision checks;
12. high-resolution confirmation results.

# Recommended execution order

1. S6-01 — equivalent gearbox implementation;
2. S6-02 — span matching;
3. S6-03 — TV and RMS matching;
4. S6-04 — baseline registry;
5. S6-05 — equivalence invariants;
6. S6-06 — resolution sweep;
7. S6-07 — graph scaling diagnostics;
8. S6-08 — production-resolution criteria;
9. S6-10 — grid-anisotropy limitation;
10. S6-11 — sampling hierarchy;
11. S6-12 — mechanism-level summaries;
12. S6-13 — hierarchical bootstrap;
13. S6-14 — sample-size planning;
14. S6-15 — staged execution plan;
15. S6-16 — sequential precision monitoring;
16. S6-17 — baseline comparison matrix;
17. S6-18 — matched-quantity reporting;
18. S6-19 — fixed sample bank;
19. S6-20 through S6-22 — safeguards and reporting;
20. S6-09 — high-resolution confirmation.

# Sprint exit criteria

Sprint Six is complete when:

1. equivalent-gain gearboxes are selectable through configuration;
2. span, total-variation, and RMS matching are implemented and tested;
3. every comparison identifies which quantities are matched;
4. the unit gearbox remains available as a separate identity baseline;
5. a fixed mechanism/task bank has been run across the resolution sweep;
6. a production resolution has been selected using documented convergence
   criteria;
7. graph-size runtime and memory trends are reported;
8. mechanism pairs are treated as the primary independent sampling units;
9. mechanism-level effect summaries are generated;
10. hierarchical bootstrap confidence intervals are available;
11. required mechanism count is estimated from pilot variance;
12. sequential precision checks are generated by mechanism batch;
13. a stopping rule is defined before the final study is completed;
14. the main baseline matrix is run at the selected resolution;
15. a representative subset confirms the result at the next higher resolution;
16. one versioned command reproduces the Sprint Six result package.

# Definition of done

Every Sprint Six issue requires:

1. implementation;
2. unit and regression tests;
3. documented mathematical definition;
4. configuration-schema updates where relevant;
5. result-schema updates where relevant;
6. explicit matching assumptions;
7. explicit numerical integration or sampling policy;
8. deterministic behavior under fixed seeds;
9. defined failure and exclusion behavior;
10. a minimal reproducible example;
11. no required notebook-only logic;
12. inclusion in the versioned Sprint Six runner;
13. updated ADR or design note where a project-level decision is made.

# Expected Sprint Six conclusion format

Sprint Six should report conclusions in five parts.

## Baseline equivalence

How does the four-bar compare against:

- the unit gearbox;
- the span-matched gearbox;
- the total-variation-matched gearbox;
- the RMS-gain-matched gearbox?

## Resolution stability

Which effects converge with graph refinement, and which remain
resolution-sensitive?

## Computational scaling

What runtime and memory costs are introduced by higher resolution?

## Monte Carlo precision

How much between-mechanism and within-mechanism variability is present, and how
many independent mechanisms are needed for the target precision?

## Confirmed effects

Which mechanism trends remain after:

- gain matching;
- graph-resolution calibration;
- hierarchical uncertainty estimation;
- high-resolution confirmation?

The intended result is a defensible experimental statement:

> A nonlinear four-bar differs from a matched linear transmission because of
> configuration-dependent gain, folding, topology, and task interaction—not
> merely because the two graphs used different scales, resolutions, or sample
> counts.
