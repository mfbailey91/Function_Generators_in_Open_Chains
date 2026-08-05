# ADR-019 — Version 2 external Cartesian task domain

**Status:** Accepted for V2.12 smoke and calibration
**Applies to:** Version 2 Experiment B
**Related:** ADR-011, ADR-014, ADR-017; [`EXPERIMENT_B_CARTESIAN_GOAL_REGION.md`](../../experiments/protocols/EXPERIMENT_B_CARTESIAN_GOAL_REGION.md)

## Context

Experiment A used centered, normalized-\(\mathcal Q\) canonical probes.
Experiment B needs a fixed external Cartesian exam shared across the mechanism
population. The external task distribution must not be generated from observed
mechanism behavior or from the intersection of sampled mechanism workspaces.

The first implementation is an illustrative planar workcell, not a claim that
this sector is a universal robot task distribution. Changing it requires a new
`cartesian_domain_id`; existing task banks are immutable.

## Decision

### Coordinate frame and robot

Use the nominal planar 2R model

\[
L_1=L_2=1.
\]

The base is at the origin. Zero \(q_1\) points along \(+x\); positive angles are
counterclockwise.

### Fixed external domain

The primary domain is the left-facing annular sector

\[
\mathcal D_X=
\left\{
(r\cos\phi,r\sin\phi):
0.50\le r\le1.50,
\quad
2.15\le\phi\le3.55
\right\}.
\]

Its stable identifier is:

```text
planar2r_left_workcell_v1
```

This domain is defined before mechanism search and independently of the
mechanism population. Reachability inside a certified pair remains an outcome.
The primary analysis must not silently reduce the domain to the intersection of
mechanism workspaces.

### Area-uniform sampler

Sample Cartesian area uniformly by drawing

\[
r^2\sim\operatorname{Uniform}(r_{\min}^2,r_{\max}^2),
\qquad
\phi\sim\operatorname{Uniform}(\phi_{\min},\phi_{\max}).
\]

Then set

\[
\mathbf x=(r\cos\phi,r\sin\phi).
\]

Drawing \(r\) uniformly is forbidden because it overweights the inner radius.
The bank records its seed and generated coordinates. No mechanism rejection or
search result may cause in-place task replacement.

### Attachment and separation

For the initial V2.12 smoke:

```text
start_tolerance = 0.06
goal_radius = 0.06
minimum_start_goal_separation = 0.30
```

The separation is greater than twice either attachment radius. A sampled start
cannot intentionally lie inside the goal disk. Discrete attachment may still
produce a coincident start/goal node; that query is rejected explicitly as
`start_node_inside_goal_region`.

The graph attaches the start to the valid node with minimum Cartesian residual,
breaking exact residual ties by ascending node id. The goal is the complete set
of valid graph nodes inside the goal disk.

### Reachability and reporting

For every external task, preserve typed outcomes including:

- no valid graph nodes;
- start region has no graph node;
- goal region has no graph node;
- start node lies in goal region;
- disconnected search;
- solved.

Report coverage separately from search metrics:

\[
P(\text{task attached/reachable})
\]

and

\[
\mathbb E[\text{search metric}\mid\text{task attached/reachable}].
\]

Pair-local reachable-workspace sampling remains a secondary control with a
separate experiment and task-distribution identifier.

## Calibration and production gate

The numerical domain is accepted for smoke and calibration. Production still
requires decision JSON for:

- accepted graph resolution;
- accepted start tolerance and goal radius;
- empty-goal-set rate;
- goal-set cardinality distribution;
- selected-goal residual;
- sensitivity of the paired effect to radius and resolution.

A calibration change must create a new domain version or attachment-policy
version; it must not mutate `planar2r_left_workcell_v1` results.

## Consequences

- Experiment B can implement and export a fixed Cartesian bank.
- The mechanism population cannot shape the primary external exam.
- Unreachable tasks remain visible evidence rather than being resampled away.
- The first domain emphasizes an illustrative left-facing workcell; conclusions
  must name that distribution explicitly.
