# Sprint V2.11 — A* Paired Campaign

**Status:** Completed ([evidence report](../../../experiments/reports/V2_11_ASTAR_PAIRED_CAMPAIGN_SUMMARY.md))
**Depends on:** completed V2.10 Dijkstra production package
**Primary solver:** A* only
**Reference solver:** frozen V2.10 Dijkstra artifacts; Dijkstra is not rerun inside this campaign

## Objective

Run A* on exactly the scientific basis frozen by V2.10, changing only the graph
solver and its heuristic. The campaign answers two paired questions:

1. Does the four-bar versus span-matched gearbox expansion effect persist under
   informed exact search?
2. How much does the admissible heuristic reduce work for each mechanism family
   relative to the already completed Dijkstra reference?

## Frozen basis

V2.11 must reuse without regeneration:

- `configs/v2/sample_banks/production_v1.json`;
- sample-bank digest `0216920c5703a2d74992171054c9fbdec75927ce4af49909f3b19020a7ccdf20`;
- production resolution `64 x 64`;
- task count `K=8`;
- objective `actuator_travel`;
- all branch, graph, overlay, edge-validation, and tie-breaking semantics;
- the exact completed mechanism IDs in `results/v2_10_production`;
- the exact frozen confirmation IDs in
  `results/v2_10_confirmation/confirmation_subset.json`.

The A* production campaign does **not** apply an independent sequential stop.
It replays every completed Dijkstra production mechanism so solver comparisons
remain fully paired.

## Heuristic contract

For actuator-travel edge cost, V2.11 uses
`input_euclidean`:

\[
h(u)=\lVert u-u_g\rVert_2.
\]

The V2 branch chart is bounded and nonperiodic. Edge costs are Euclidean input
increments, so straight-line input distance is a lower bound on every graph
path and satisfies the triangle inequality. The heuristic is therefore
admissible and consistent for this campaign.

A* release gates:

- configuration rejects every other heuristic;
- A* and Dijkstra return the same optimal cost on deterministic smoke fixtures;
- repeated A* runs produce identical paths and counters;
- manifest records solver and heuristic IDs;
- production rows record heuristic evaluations, stale entries, generated nodes,
  expansions, runtime, and optimal cost.

## Stages

### V2-1101 — A* smoke

Run `configs/v2/production_astar_smoke.yaml` and verify:

- shared-Q pair invariants;
- 100% task feasibility;
- Dijkstra/A* optimal-cost equality on the smoke fixture;
- deterministic A* outputs;
- correct solver/heuristic metadata.

### V2-1102 — Paired pilot

Run `configs/v2/production_astar_pilot.yaml` against the 50 completed mechanism
IDs in `results/v2_10_pilot`.

Report:

- A* four-bar/gearbox mechanism effect;
- expansion reduction relative to Dijkstra by mechanism family;
- optimal-cost agreement failures, which are campaign blockers;
- runtime and heuristic-call distributions.

### V2-1103 — Paired production

Run `configs/v2/production_astar.yaml` against the completed IDs in
`results/v2_10_production` (161 in the V2.10 closeout package).

Do not stop early. Complete the full Dijkstra reference set.

### V2-1104 — Frozen high-resolution confirmation

Run `configs/v2/production_astar_confirmation.yaml` at `96 x 96`, reusing the
15 mechanism IDs frozen before V2.10 confirmation search.

### Campaign commands

```bash
python scripts/run_v2_production.py \
  --config configs/v2/production_astar_smoke.yaml \
  --run-id v2_11_astar_smoke

python scripts/run_v2_production.py \
  --config configs/v2/production_astar_pilot.yaml \
  --run-id v2_11_astar_pilot

python scripts/run_v2_production.py \
  --config configs/v2/production_astar.yaml \
  --run-id v2_11_astar_production

python scripts/run_v2_production.py \
  --config configs/v2/production_astar_confirmation.yaml \
  --run-id v2_11_astar_confirmation

python scripts/compare_v2_solver_campaigns.py \
  --dijkstra-run results/v2_10_production \
  --astar-run results/v2_11_astar_production \
  --output results/v2_11_astar_production/reports/solver_comparison.json
```

The production runner also writes the comparison report automatically when
`study.reference_run` is configured; the explicit comparison command is kept
for reproducible regeneration and audit.

### V2-1105 — Solver comparison report

Join Dijkstra and A* rows by:

- sample-bank digest;
- mechanism-pair ID;
- mechanism side;
- task ID;
- graph shape;
- objective ID.

Primary paired quantities:

\[
\Delta_{A^*-D}
=
\log\!\left(\frac{N_{fb,A^*}+1}{N_{gb,A^*}+1}\right)
-
\log\!\left(\frac{N_{fb,D}+1}{N_{gb,D}+1}\right),
\]

and mechanism-specific heuristic savings

\[
S_m=1-\frac{N_{expanded,A^*}+1}{N_{expanded,D}+1}.
\]

Inference remains mechanism-clustered. Tasks are nested observations, not iid
samples.

## Exit criteria

V2.11 is complete when:

1. all A* configs are single-solver and use `input_euclidean`;
2. the bank digest and reference mechanism IDs match V2.10 exactly;
3. A* and Dijkstra optimal costs agree for every paired feasible query;
4. production completes all reference IDs without an independent stop;
5. confirmation reuses the frozen 15-ID subset at `96 x 96`;
6. a report separates the mechanism effect under A* from the heuristic savings
   relative to Dijkstra;
7. the frozen bank remains byte-for-byte unchanged.

## Out of scope

- weighted or anytime A*;
- bidirectional search;
- PRM, RRT, OMPL, or any sampled roadmap/tree construction;
- new mechanisms, tasks, resolutions, objectives, or bank regeneration;
- workers greater than one unless separately requalified.
