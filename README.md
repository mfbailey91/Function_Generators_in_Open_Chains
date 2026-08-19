# Inequality Mechanisms research software

Research software for studying how mechanism mappings

```text
U --g_m--> Q --f--> X
```

reshape planning, velocity, wrench, and flow. Core library code lives under
`src/inequality_mechanisms/`. Notebooks analyze results; they do not define
algorithms.

- **Version 1** is the preserved full-cycle, input-state research baseline.
  Graph identity lives in actuator space \(\mathcal U\).
- **Version 2** is frozen historical lineage: certified invertible-branch
  planning with output-state identity in \(\mathcal Q\) and an attached
  actuator realization.
- **Version 3** is the planner-independent physical-state architecture.
  Planar-2R free-space closeout (V3.6C) and the span/wrench insert (V3.6D–F)
  are accepted; residual 3R remains blocked.
- **Version 4** consumes that transmission geometry as a shared differential
  layer ([ADR-027](docs/software/architecture/adr/ADR-027-v4-kinematic-transmission-geometry.md)).
  V4.0 and V4.1 are closed. V4.2 and V4.2A are retained historical diagnostics.
  **Sprint V4.2B** is the active mounted-coordinate closeout
  ([ADR-029](docs/software/architecture/adr/ADR-029-mounted-output-coordinate.md),
  [ADR-030](docs/software/architecture/adr/ADR-030-paired-final-topology-and-nonfinite-edge-semantics.md)).
  V4.3 (intrinsic wrench on V4.2B snapshots) remains drafted and unauthorized.

Do not overwrite frozen V3 or V4.0–V4.2A packages. Canonical V4.2B evidence is
generated only from a clean implementation revision under
`results/v4_review/v4_2b_span_controlled_corrective_closeout/`.

## Requirements

- Python **3.11–3.13** (recommended). `requires-python` is `>=3.11`; scientific
  wheels may lag on newer interpreters.

## Development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

If `python3.12` is unavailable, use another 3.11–3.13 interpreter.

## CI-ready commands

```bash
pytest
ruff check .
ruff format --check .
mypy src
```

## Reproduce the pilot (IM-017)

```bash
MPLBACKEND=Agg PYTHONPATH=src python scripts/reproduce_pilot.py --config configs/pilot.v1.yaml
```

Writes a new immutable run under `results/<run_id>/` with trial JSONL, a
summary table, and paired raw / normalized / log-ratio expansion plots.
See [ADR-008](docs/software/architecture/adr/ADR-008-pilot-reproduction.md).

Equal valid-node ablation: `configs/pilot.equal_nodes.v1.yaml` (ADR-010).
For a smaller canvas-oriented Monte Carlo, use
`configs/pilot.canvas.v1.yaml` (20 equal-node trials).
Cost ablations (Sprint Four P0): `configs/pilot.cost_uniform.v1.yaml` and
`configs/pilot.cost_input.v1.yaml` (same physical graph, different edge
metric). Change `cost.type` in any config to `uniform`, `input_euclidean`,
or `output_euclidean`.

Sprint Four factorial attribution (P1):

```bash
MPLBACKEND=Agg PYTHONPATH=src python scripts/reproduce_sprint4.py \
  --config configs/sprint4.smoke.v1.yaml
```

Science-scale: `configs/sprint4.factorial.v1.yaml`. Writes mech × cost × algo
trials, A* savings plots, landscape bundles, descriptors, and bootstrap CIs.

Monotonic uniform-U vs uniform-Q control (P2 / S4-11):

```bash
MPLBACKEND=Agg PYTHONPATH=src python scripts/reproduce_sprint4_qgrid.py \
  --config configs/sprint4.qgrid.smoke.v1.yaml
```

Larger lattice: `configs/sprint4.qgrid.v1.yaml`. ADR-001 is unchanged; see
`docs/software/architecture/notes/S4-12-lifted-output-state.md` for deferred `(q,σ)` state.

### Monte Carlo canvas

After a completed run (or regenerating if `index.html` is missing):

```bash
MPLBACKEND=Agg PYTHONPATH=src python scripts/generate_monte_carlo_canvas.py --latest
# or: ... --run results/<run_id>
```

Open `results/<run_id>/index.html`. The canvas is a derived viewer over
summary stats, expansion PNGs, path samples, provenance, and Sprint Four
fields (`cost_type`, path lengths \(L_U/L_Q/L_X\), `result_schema_version`)
when present; regenerating it does not rewrite trial JSONL.

## Documentation

Start at [docs/README.md](docs/README.md). Canonical software paths are under
`docs/software/`:

- [Version matrix](docs/software/VERSION_MATRIX.md) — V1–V4 architecture and status
- [Active sprint](docs/software/planning/ACTIVE_SPRINT.md) — current authorization
- [Software project plan](docs/software/PROJECT_PLAN.md)
- [Version 4 project plan](docs/software/V4_PROJECT_PLAN.md)
- [V4 sprint index](docs/software/planning/sprints/v4/README.md)
- [ADR-001](docs/software/architecture/adr/ADR-001-search-in-input-space.md) —
  Version 1 search-state identity in input configuration space
- [ADR-008](docs/software/architecture/adr/ADR-008-pilot-reproduction.md) —
  pilot trial schema and expansion figures
- [ADR-027](docs/software/architecture/adr/ADR-027-v4-kinematic-transmission-geometry.md) —
  kinematic transmission geometry
- [ADR-029](docs/software/architecture/adr/ADR-029-mounted-output-coordinate.md) —
  mounted output coordinates
- [ADR-030](docs/software/architecture/adr/ADR-030-paired-final-topology-and-nonfinite-edge-semantics.md) —
  paired final topology and nonfinite edge semantics
