# Sprint V2.7 — 3R Planar Extension

**Status: Deferred — do not implement until 2R V2.5/V2.6 results are reviewed.**

This sprint remains documented for later use. It is **out of the active Version 2 execution sequence**. Re-open only after controlled 2R null-control, resolution, overlay, and capability evidence have been evaluated.

## Theme

> Keep 2R as the microscope; use 3R as the first system that can make meaningful posture choices.

## Objective

Extend the proven Version 2 architecture from a 2R planar manipulator to a 3R planar manipulator without changing the mechanism, graph, search, or experiment contracts. Run full-pose planning first, then position-only redundant-goal planning.

## Entry gates

Do not start this sprint until:

1. generic topology and search support arbitrary dimension;
2. certified branches work independently on three axes;
3. uniform-input and uniform-output graphs pass 2R null controls;
4. exact query overlays are available;
5. 2R grid-convergence behavior is understood;
6. no production module assumes node states have length two;
7. **2R evaluation review is complete** (printout / study evidence accepted).

## Manipulator models

### Full planar pose

\[
\mathbf q=(q_1,q_2,q_3),
\qquad
\mathbf x=(x,y,\phi),
\]

with

\[
\phi=q_1+q_2+q_3.
\]

This gives a dimension-matched map:

\[
\mathcal Q^3\rightarrow SE(2).
\]

### Position-only task

\[
\mathbf x=(x,y),
\]

so

\[
\mathcal Q^3\rightarrow\mathbb R^2
\]

is redundant. A Cartesian goal corresponds to a family of valid output configurations.

## Issues

### V2-701 — Audit all 2D assumptions

Record and remove assumptions such as:

- tuple unpacking into `(i0, i1)`;
- fixed shapes `(n0, n1)`;
- arrays with second dimension two;
- four-connected language in generic modules;
- plots treated as core APIs;
- result schemas that assume two axes.

Deliver `docs/software/architecture/audits/V2_7_DIMENSION_AUDIT.md`.

### V2-702 — Implement 3R forward kinematics

Create a typed manipulator model:

```python
class Planar3R:
    link_lengths: tuple[float, float, float]

    def position(self, q: ArrayLike) -> NDArray[np.float64]: ...
    def pose(self, q: ArrayLike) -> NDArray[np.float64]: ...
    def jacobian_position(self, q: ArrayLike) -> NDArray[np.float64]: ...
    def jacobian_pose(self, q: ArrayLike) -> NDArray[np.float64]: ...
```

Validate analytic Jacobians against finite differences.

### V2-703 — Build 3D Version 2 graphs

Use `TensorGridTopology(shape=(n1,n2,n3), wrap=(False,False,False))` and the existing samplers.

Start with practical resolutions such as:

```text
16^3 = 4,096 nodes
24^3 = 13,824 nodes
32^3 = 32,768 nodes
48^3 = 110,592 nodes
```

Do not begin at `64^3` without profiling.

### V2-704 — Add 3D diagnostics

Because the full configuration graph cannot be shown in one ordinary 2D plot, provide:

- fixed-axis slices;
- orthogonal projections;
- path projection in \((q_1,q_2)\), \((q_1,q_3)\), and \((q_2,q_3)\);
- spacing statistics by axis;
- Cartesian arm animation or sampled poses only as a derived diagnostic;
- search-volume summaries rather than misleading flattened heat maps.

### V2-705 — Run full-pose planning

Use matched start and goal \((x,y,\phi)\) or matched \(\mathbf q\) endpoints.

Purpose:

- verify higher-dimensional correctness;
- test scaling of sampling and metric effects;
- retain a unique task target before introducing redundancy.

Run the same uniform-\(\mathcal U\)/uniform-\(\mathcal Q\) control matrix.

### V2-706 — Define Cartesian position goal sets

For position-only tasks, the goal is a set:

\[
\mathcal G_x=\{\mathbf q:\|f(\mathbf q)-\mathbf x_g\|\le\epsilon_x\}.
\]

Implement multi-goal search or a virtual super-goal without collapsing distinct \(\mathbf q\) states.

Required records:

- number of accepted goal nodes;
- selected terminal \(\mathbf q\);
- selected terminal \(\mathbf u\);
- Cartesian residual;
- terminal capability descriptors.

### V2-707 — Add posture-selection experiments

On the same Cartesian position task, compare which terminal posture is selected under:

- output path length;
- actuator travel;
- terminal precision/gain preference;
- combined path plus terminal objective.

This is the first experiment in which the mechanism may make a meaningful choice among physically different postures that accomplish the same external task.

### V2-708 — Scaling and memory report

Measure:

- graph construction time;
- search time;
- memory use;
- cached versus on-demand edge costs;
- compiled versus dynamic adjacency if both exist.

Optimize only after profiling. Preserve deterministic behavior.

## Tests

- 3R forward kinematics hand-worked cases;
- Jacobian finite-difference agreement;
- 3D topology neighbor counts;
- 3D uniform-input/output node invariants;
- 3R uniform-\(\mathcal Q\) null control;
- exact overlay start/goal in 3D;
- multi-goal optimality against a small brute-force fixture;
- selected posture reproducibility;
- no regression in 2R or Version 1.

## Non-goals

- spatial 6-DOF robots;
- collision checking in the first 3R sprint;
- dynamics;
- hardware;
- reinforcement learning;
- coupled multi-input transmission modules.

## Sprint exit criteria

1. The same graph/search APIs run 2R and 3R without dimension-specific branches in core code.
2. Full-pose 3R null controls pass.
3. Position-only goal sets preserve distinct \(\mathbf q\) states.
4. At least one posture-selection experiment is reproducible.
5. Scaling limits are measured and documented.
6. 2R remains the canonical visualization and debugging fixture.

## Cursor starter prompt

```text
Implement Sprint V2.7 only after confirming all entry gates. Start with a full
2D-assumption audit. Add Planar3R kinematics and Jacobian tests, then run the
existing generic topology, branch, graph, overlay, objective, and search APIs in
three dimensions. Validate full-pose null controls before implementing
position-only multi-goal planning. Preserve distinct Q terminal states and
record the selected posture and U realization. Profile before optimizing. Do not
add collisions, dynamics, RL, or spatial robot support.
```
