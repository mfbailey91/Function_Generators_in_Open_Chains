# Sprint V2.5 — Controlled 2R Study

## Theme

> Establish what the mechanism changes before asking whether the change is beneficial.

## Objective

Run the first scientifically interpretable Version 2 experiments on the 2R planar manipulator. Separate sampling, metric, heuristic, graph-resolution, and endpoint-residual effects using deterministic fixtures before a modest mechanism population.

## Sprint question

> For certified monotonic transmission branches, which planning differences arise from actuator-derived nonuniform sampling, and which remain when all mechanisms share a uniform output graph?

## Required experiment matrix

For every accepted mechanism pair and task set:

| Cell | Sampling | Cost | Required interpretation |
| --- | --- | --- | --- |
| A | uniform \(\mathcal U\) mapped to \(\mathcal Q\) | output Euclidean | sampling/allocation effect |
| B | uniform \(\mathcal Q\) | output Euclidean | exact null control |
| C | uniform \(\mathcal Q\) | input Euclidean | actuator metric effect |
| D | uniform \(\mathcal U\) mapped to \(\mathcal Q\) | input Euclidean | combined sampling and actuator metric |

Run Dijkstra for every cell. Run A* only with a validated compatible heuristic.

## Study phases

### Phase 1 — Deterministic fixtures

Use at least three fixed branch pairs:

1. identity or unit-gain control;
2. matched affine gearbox versus mildly nonlinear four-bar;
3. matched affine gearbox versus strongly nonlinear but safely certified four-bar.

Use fixed tasks chosen to exercise:

- low-gain region;
- high-gain region;
- cross-range motion;
- two-axis simultaneous displacement;
- near-boundary but valid states.

### Phase 2 — Grid-resolution sweep

At minimum:

```text
16 x 16
32 x 32
48 x 48
64 x 64
96 x 96
```

Use `128 x 128` only if computationally practical after profiling.

Track convergence of:

- endpoint residual;
- node and edge count;
- optimal cost;
- expansions and normalized expansions;
- \(L_U\), \(L_Q\), and \(L_X\);
- spacing distribution;
- mechanism effect estimates.

### Phase 3 — Modest mechanism population

Only after deterministic and resolution gates pass, sample a limited population of certified branches. Record branch rejection counts and reasons.

Do not begin with the largest prior Monte Carlo settings.

## Issues

### V2-501 — Freeze deterministic mechanisms and tasks

Store fixtures as versioned data, not code literals scattered across tests and scripts.

Every fixture records:

- mechanism parameters;
- branch selection settings;
- certificate;
- equivalent affine gearbox;
- output space;
- requested tasks;
- expected null-control equality.

### V2-502 — Implement paired experiment orchestration

For each requested task, construct all cells from the same branch pair and task request.

Do not redraw tasks per condition. A condition failure must be recorded rather than replaced silently.

### V2-503 — Add sampling descriptors

Record per axis:

- \(\Delta u\) distribution;
- \(\Delta q\) distribution;
- mean/min/max/variance of \(|dq/du|\);
- minimum gain margin;
- output-node density estimate;
- ratio of largest to smallest edge length in \(\mathcal Q\).

### V2-504 — Add search and path metrics

Required metrics:

- expanded, generated, stale nodes;
- expansion fraction over reachable nodes;
- optimal cost;
- path edges;
- \(L_U\), \(L_Q\), \(L_X\);
- requested and realized endpoint residuals;
- runtime, reported as secondary and environment-dependent.

### V2-505 — Validate heuristic behavior

For representative graphs, compute exact reverse distances and verify:

\[
0\le h(n)\le h^*(n).
\]

Report A* savings separately from mechanism effects.

### V2-506 — Run grid convergence study

Define an acceptance rule before inspecting results. Example:

- primary paired effect changes by less than a configured relative tolerance across the two finest accepted grids;
- endpoint residual remains below tolerance;
- no topology change occurs unexpectedly;
- null-control equality remains exact at every resolution.

If convergence is not achieved, do not select a preferred resolution merely because it gives a clearer result.

### V2-507 — Run modest population and uncertainty analysis

Use paired bootstrap intervals for:

- expansion difference;
- normalized expansion difference;
- optimal-cost difference;
- \(L_U\), \(L_Q\), \(L_X\) differences;
- A* savings difference.

Store bootstrap configuration and excluded-trial counts.

### V2-508 — Generate standard report

Required figures:

1. uniform-\(\mathcal U\) and uniform-\(\mathcal Q\) graph comparison in output space;
2. branch \(q(u)\) and gain curves;
3. paired expansions by experiment cell;
4. normalized expansions by cell;
5. grid-resolution convergence;
6. output spacing distribution;
7. \(L_U\), \(L_Q\), \(L_X\) comparison;
8. mechanism descriptors versus observed effects;
9. representative search landscapes.

Required tables:

- branch acceptance/rejection summary;
- null-control invariant report;
- deterministic fixture results;
- resolution study;
- modest population summary;
- uncertainty intervals.

## Interpretation rules

The sprint report must distinguish:

### Sampling effect

What changes between uniform-\(\mathcal U\) and uniform-\(\mathcal Q\) under the same output-distance objective?

### Metric effect

What changes on the same uniform-\(\mathcal Q\) graph when the objective changes from output distance to actuator distance?

### Heuristic effect

What reduction is due to A* information rather than mechanism or graph construction?

### Discretization effect

Which findings change materially with graph resolution or endpoint snapping?

### Null result

If the mechanism disappears under the normalized control, state that directly. This is expected under pure output geometry.

## Non-goals

- no capability reward design;
- no exact query overlays;
- no obstacles;
- no 3R;
- no reinforcement learning;
- no claim that fewer expansions imply a better robot.

## Verification

```bash
pytest tests/experiments_v2 tests/graphs_v2 tests/operating_branches
python scripts/run_v2_experiment.py --config configs/v2/deterministic_2r.yaml
python scripts/run_v2_experiment.py --config configs/v2/resolution_2r.yaml
pytest
ruff check .
ruff format --check .
mypy src
```

## Sprint exit criteria

1. The four-cell matrix runs reproducibly on deterministic fixtures.
2. The uniform-\(\mathcal Q\), output-distance null control passes at every tested resolution.
3. Endpoint residual and resolution effects are reported.
4. The selected production resolution has an explicit convergence justification.
5. A modest certified mechanism population has paired uncertainty estimates.
6. The report separates sampling, metric, heuristic, and discretization effects without forcing a favorable conclusion.

## Cursor starter prompt

```text
Implement and run Sprint V2.5 only. Freeze deterministic mechanisms and tasks
first, then implement paired orchestration for the four required experiment
cells. Add sampling descriptors, path/search metrics, heuristic validation,
resolution sweeps, and a modest population runner. Reuse the exact same task
requests across conditions and record failures rather than resampling silently.
Keep the uniform-Q output-distance null control as a hard invariant at every
resolution. Do not add capability costs, query overlays, obstacles, or 3R work.
```
