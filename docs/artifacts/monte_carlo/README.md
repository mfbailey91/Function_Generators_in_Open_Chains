# Monte Carlo canvas run

Practical equal-node pilot used for the regenerable HTML canvas.

## What was run

```bash
MPLBACKEND=Agg PYTHONPATH=src .venv/bin/python scripts/reproduce_pilot.py \
  --config configs/pilot.canvas.v1.yaml \
  --results-root artifacts/monte_carlo
```

Config: `configs/pilot.canvas.v1.yaml`

- seed `0`
- `n_trials: 20` (equal valid-node ablation)
- grid `16×16`, `edge_samples: 9`
- algorithms: Dijkstra + A*
- cost: `output_euclidean`
- `n_path_samples: 2`

Completed run (do not overwrite):

`artifacts/monte_carlo/seed0_20260727T164134Z_2b532590/`

Open `index.html` in that directory. Regenerate the derived viewer only:

```bash
MPLBACKEND=Agg PYTHONPATH=src .venv/bin/python \
  scripts/generate_monte_carlo_canvas.py \
  --run artifacts/monte_carlo/seed0_20260727T164134Z_2b532590
```

Note: under this agent sandbox, `*.csv` writes are blocked by `.cursorignore`, so
`summary_table` / `residual_summary` were stored as `.txt` with identical CSV text.
Outside the sandbox the pilot prefers `.csv` (with `.txt` fallback on `PermissionError`).
