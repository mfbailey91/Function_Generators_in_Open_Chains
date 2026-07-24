# Inequality Mechanisms — Software Project Plan

## Objective

Build a trustworthy, reproducible framework for studying how mechanism mappings

$$
\mathcal U \xrightarrow{g_m} \mathcal Q \xrightarrow{f} \mathcal X
$$

reshape graph-based manipulator planning.

The Version 1 research question is:

> Under shared output joint limits and matched output start/goal tasks, how do unit gearboxes and four-bar mechanisms change graph-search node expansions?

## Version 1 scope

Version 1 must:

1. support unit gearboxes, fixed-ratio gearboxes, and planar four-bars through one interface;
2. construct periodic input-side graphs;
3. preserve duplicate output preimages as distinct physical states;
4. apply shared output joint limits;
5. run instrumented Dijkstra and A*;
6. reproduce the exploratory pilot;
7. run graph-size, branch, periodicity, cost, and resolution ablations;
8. export reproducible trial-level data and plots.

Version 1 excludes RL, dynamics, collision checking, hardware, and mechanism optimization.

## Principles

- Trust before scale.
- Search state lives in input space.
- Constraints are shared in output space.
- Experiments are configuration driven.
- Every run stores config, seed, code revision, mechanisms, environment, and results.
- Notebooks analyze the library; they do not define it.

## Architecture

```text
inequality-mechanisms/
├── src/inequality_mechanisms/
│   ├── mechanisms/
│   ├── spaces/
│   ├── graphs/
│   ├── search/
│   ├── metrics/
│   ├── experiments/
│   └── visualization/
├── tests/
├── configs/
├── notebooks/
├── scripts/
├── results/
└── docs/
    ├── paper.md
    ├── literature_map.md
    └── decisions/
```

## Milestones

### M0 — Specification
Freeze state, goal, expansion, periodicity, cost, and fairness definitions.

### M1 — Mechanism core
Implement gearbox and four-bar maps, branch tracking, Jacobians, inverse/preimage lookup, periodicity, and random mechanism sampling.

**Exit:** periodicity, derivative, inverse, and assembly tests pass.

### M2 — Graph core
Implement regular grids, four-connectivity, periodic wrapping, shared output-limit filtering, edge validation, and connected-component diagnostics.

**Exit:** no false connectivity; hand-worked graph tests pass.

### M3 — Search core
Implement Dijkstra, A*, deterministic tie-breaking, path reconstruction, and instrumentation.

**Exit:** A* and Dijkstra return equal optimal cost; stale queue entries are not counted.

### M4 — Pilot reproduction
Recreate the exploratory Monte Carlo from a versioned config.

**Exit:** one command reproduces the paired expansion plots and results table.

### M5 — Controlled ablations
Run equal-node-count, monotonic/full-cycle, periodicity, input/output cost, and resolution experiments.

**Exit:** graph size, topology, and metric effects are reported separately.

### M6 — Path quality
Add self-intersections, detour ratio, cumulative turning, and near-revisit distance.

### M7 — Paper-ready release
Freeze configs, data, figure scripts, methods, tests, and a tagged release.

## Primary metrics

- expanded nodes;
- normalized expansion fraction;
- generated and reopened nodes;
- optimal graph cost;
- path edges;
- input/output/Cartesian path length;
- runtime.

## First two weeks

### Week 1
- create repository;
- freeze ADRs;
- implement mechanism interface;
- implement gearbox and four-bar forward maps;
- implement branch tracking;
- validate Jacobians.

### Week 2
- implement preimages;
- build periodic four-connected graph;
- add shared output limits;
- implement Dijkstra and A*;
- verify one paired gearbox/four-bar trial completely.

## Version 1 benchmark semantics

- graph nodes are input configurations;
- start and goal use known input preimages corresponding to matched output configurations;
- full assembly state is preserved;
- shared limits are enforced in output space;
- primary edge cost is Euclidean output displacement;
- Dijkstra and A* run on the same graph;
- periodic edges are enabled only in full-cycle modes.
