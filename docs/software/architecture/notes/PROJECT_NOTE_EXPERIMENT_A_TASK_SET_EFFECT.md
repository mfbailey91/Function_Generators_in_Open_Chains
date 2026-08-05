# Project note — Experiment A task-set effect

**Status:** unresolved diagnostic / planner interaction; deferred; low confidence  
**Source:** V2.10 Dijkstra and V2.11 A* production reports  
**Normative authority:** none — do not treat as an ADR or experiment requirement  
**Return condition:** revisit only if later evidence suggests explanatory value beyond the failed A* persistence check

## Observation

The frozen Experiment A task set produced materially different mean paired
expansion effects by task template under Dijkstra. The single
`medium_diagonal` probe had the largest negative mean log expansion ratio:

\[
\overline{\Delta}_{\text{medium diagonal, Dijkstra}}
\approx -0.0747.
\]

The overall eight-probe Dijkstra production estimate was approximately:

\[
\overline{\Delta}_{\text{all probes, Dijkstra}}
\approx -0.0195.
\]

Task variation was much larger than between-mechanism variation in the V2.10
variance decomposition.

## First persistence check failed under A*

V2.11 replayed the same frozen bank under A* with `input_euclidean`. Category
order was not preserved. In particular:

\[
\overline{\Delta}_{\text{medium diagonal, A*}}
\approx +0.0003.
\]

A* already failed the first persistence check recorded when this note was
drafted. The `medium_diagonal` Dijkstra spike is therefore a diagnostic anomaly
or planner interaction until further evidence says otherwise.

The safer interpretation is:

> The strong Dijkstra category effect may reflect the interaction between the
> centered query, the actuator-cost basin, and uninformed search expansion
> rather than an intrinsic task-direction advantage.

## Why this is not a finding about diagonal tasks

The task bank was deliberately structured:

- one task per named category;
- normalized \(\mathcal Q\)-space endpoints;
- midpoints concentrated near the center of the output box;
- mostly positive movement in both joint coordinates;
- fixed point-to-point configuration goals;
- four-connected grid;
- actuator-travel cost;
- start-rooted expansion count.

The category effect therefore entangles displacement direction, length, start
and goal location, passage through the central branch region, local actuator
gain, Dijkstra cost-ball geometry, grid and tie semantics, and now solver
identity.

Calling this an “efficient diagonal area” would exceed the evidence. Experiment
A is not evidence about an entire diagonal region.

## Do not expand scope now

Do not add a task atlas to Experiment B's primary scope. Experiment B should
use its frozen external Cartesian distribution without being tuned around this
observation.

## Efficient return path

Revisit this note only if later evidence, independent of the failed A*
category-order check, suggests explanatory value. The smallest useful follow-up
would still be:

1. reverse each canonical task;
2. translate a fixed displacement vector across feasible \(\mathcal Q\)
   midpoints;
3. separate midpoint, length, and direction;
4. compare Dijkstra and A*;
5. repeat at the accepted and confirmation resolutions.

Until then, preserve the observation, keep confidence low, and make no
directional mechanism claim.
