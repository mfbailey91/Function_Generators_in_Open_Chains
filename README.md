# Inequality Mechanisms research software

Research software for studying how mechanism mappings

```text
U --g_m--> Q --f--> X
```

reshape graph-based manipulator planning. Version 1 asks how unit gearboxes
and four-bar mechanisms change graph-search node expansions under shared
output joint limits and matched output start/goal tasks.

Core library code lives under `src/inequality_mechanisms/`. Notebooks analyze
results; they do not define algorithms. Version 1 excludes RL, dynamics,
collision checking, hardware, and mechanism optimization.

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
See [docs/ADR-008-pilot-reproduction.md](docs/ADR-008-pilot-reproduction.md).

Equal valid-node ablation: `configs/pilot.equal_nodes.v1.yaml` (ADR-010).
For a smaller canvas-oriented Monte Carlo, use
`configs/pilot.canvas.v1.yaml` (20 equal-node trials).
Cost ablations (Sprint Four P0): `configs/pilot.cost_uniform.v1.yaml` and
`configs/pilot.cost_input.v1.yaml` (same physical graph, different edge
metric). Change `cost.type` in any config to `uniform`, `input_euclidean`,
or `output_euclidean`.

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

- [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) — scope, architecture, milestones
- [docs/BACKLOG.md](docs/BACKLOG.md) — implementation issues
- [docs/ADR-001-search-in-input-space.md](docs/ADR-001-search-in-input-space.md) —
  search state identity lives in input configuration space
- [docs/ADR-008-pilot-reproduction.md](docs/ADR-008-pilot-reproduction.md) —
  pilot trial schema and expansion figures
