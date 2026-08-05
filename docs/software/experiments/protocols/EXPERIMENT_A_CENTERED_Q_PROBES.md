# Experiment A — Centered normalized Q-space canonical probes

**Status:** retrospective protocol for completed V2.10 Dijkstra and V2.11 A* evidence  
**Primary reports:** [`V2_10_PRODUCTION_DIJKSTRA_SUMMARY.md`](../reports/V2_10_PRODUCTION_DIJKSTRA_SUMMARY.md), [`V2_11_ASTAR_PAIRED_CAMPAIGN_SUMMARY.md`](../reports/V2_11_ASTAR_PAIRED_CAMPAIGN_SUMMARY.md)  
**Frozen bank:** `configs/v2/sample_banks/production_v1.json`  
**Task-set note:** [`PROJECT_NOTE_EXPERIMENT_A_TASK_SET_EFFECT.md`](../../architecture/notes/PROJECT_NOTE_EXPERIMENT_A_TASK_SET_EFFECT.md)

## Purpose

Experiment A is a controlled mechanism probe. It asks:

> On a shared output-state graph with identical topology and fixed output
> configuration endpoints, how does the mechanism-specific actuator-travel
> metric change graph-search effort?

It was designed to isolate a metric effect after earlier studies had mixed
graph size, topology, sampling, and endpoint effects.

## Precise task-set name

Experiment A is:

> A centered, normalized-\(\mathcal Q\), equal-weight canonical-query
> experiment designed to vary displacement scale and direction while
> approximately controlling query location.

It is **not**:

- a random task population;
- uniform \(\mathcal Q\)-space sampling;
- Cartesian task sampling;
- evidence about an entire diagonal region of the workspace or output box.

## Mechanism and graph contract

For each certified monotonic four-bar pair:

1. construct one shared uniform-\(\mathcal Q\) graph;
2. attach the four-bar actuator realization
   \(\mathbf u_{\mathrm{fb}}=g_{\mathrm{fb}}^{-1}(\mathbf q)\);
3. attach a span-matched affine gearbox realization;
4. preserve identical \(\mathbf q\) nodes, adjacency, and forward kinematics;
5. compute edge cost from raw Euclidean actuator travel;
6. run one deterministic exact solver per campaign.

The four-bar and gearbox therefore navigate the same output graph. They differ
in the actuator metric attached to its edges.

## Task definition

The frozen bank contains eight task templates specified by normalized start
and goal fractions of each pair's output-coordinate box.

For a task \(t\),

\[
\mathbf q_s^{(t)}
=
\mathbf q_{\min}
+
\mathbf r_s^{(t)}
\odot
(\mathbf q_{\max}-\mathbf q_{\min}),
\]

\[
\mathbf q_g^{(t)}
=
\mathbf q_{\min}
+
\mathbf r_g^{(t)}
\odot
(\mathbf q_{\max}-\mathbf q_{\min}).
\]

The task is a fixed point-to-point configuration query:

\[
\mathbf q_s^{(t)}
\longrightarrow
\mathbf q_g^{(t)}.
\]

The planner is not allowed to choose an alternative IK posture or a Cartesian
goal region.

## Why the probes are centered

Most task midpoints satisfy approximately

\[
\frac{\mathbf r_s+\mathbf r_g}{2}
\approx
(0.5,0.5).
\]

This approximately controls task location while varying:

- displacement length;
- joint-1 versus joint-2 dominance;
- diagonal direction;
- proximity of endpoints to the output bounds.

Centering was a practical controlled-design choice:

- long displacements remain feasible in several directions;
- endpoint clipping and boundary failures are reduced;
- displacement structure can be compared without moving every task to a
  different part of the mechanism map.

It is not a claim that central tasks represent the full workspace.

## Estimand

Let

\[
\Delta_{mk}
=
\log
\left(
\frac{N_{\mathrm{fb},mk}+1}
{N_{\mathrm{gb},mk}+1}
\right)
\]

for mechanism pair \(m\) and canonical task \(k\).

The reported mechanism effect is based on:

\[
\bar\Delta_m
=
\frac{1}{K}
\sum_{k=1}^{K}
\Delta_{mk},
\qquad K=8,
\]

followed by inference over mechanism pairs.

The result therefore applies to the equal-weight frozen probe set. The tasks
are nested repeated measurements, not independent random draws from a task
population. Expansion counts are solver-specific; optimal cost and actuator
path length \(L_U\) are solver-invariant on this bank.

## Planner-specific results

Experiment A contains two completed planner cells on the same frozen bank.

### V2.10 Dijkstra

Uninformed exact search showed a small negative hierarchical expansion effect
(\(\overline{\Delta}\approx -0.01953\), \(n=161\)) and substantial
task-category variation. The single `medium_diagonal` probe was much more
negative (\(\approx -0.0747\)) than the other seven probes.

### V2.11 A*

Informed exact search with the admissible `input_euclidean` heuristic preserved
optimal cost and \(L_U\) on every paired feasible query. The expansion-count
effect shrank (\(\overline{\Delta}\approx -0.00781\)) and the Dijkstra category
ordering did **not** survive. In particular, `medium_diagonal` moved from about
\(-0.0747\) to essentially zero (\(+0.0003\)).

That substantially weakens any reading of the Dijkstra category table as a
durable favorable mechanism corridor. The safer interpretation is:

> The strong Dijkstra category effect may reflect the interaction between the
> centered query, the actuator-cost basin, and uninformed search expansion
> rather than an intrinsic task-direction advantage.

## What Experiment A captures

- a transmission-induced actuator metric on a common output graph;
- exact known-start / known-goal configuration planning;
- task sensitivity across selected displacement archetypes;
- Dijkstra and A* expansion behavior under actuator-travel cost;
- mechanism-level uncertainty for the frozen probe suite.

## What Experiment A does not capture

- uniform random start and goal configurations in \(\mathcal Q\);
- uniform random Cartesian positions in \(\mathcal X\);
- Cartesian goal-set planning;
- IK posture choice at the goal;
- workspace coverage;
- obstacle avoidance;
- 3R planar pose or 6R spatial pose;
- a global mechanism advantage independent of task distribution and solver.

## Relationship to Experiment B

Experiment B does not invalidate Experiment A. The experiments answer different
questions:

- **Experiment A:** what does the mechanism metric do under controlled fixed
  configuration probes?
- **Experiment B:** what does the planner experience when asked to reach a
  Cartesian position region from a known physical start state?

Both results must name their task distribution and solver explicitly.
Experiment B remains the next task-definition stage and is held behind
accepted Cartesian-domain and goal-set search contracts.
