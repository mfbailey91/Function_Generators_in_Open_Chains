# Sprint Four status

## P0 (complete)

Config-driven costs, planning objectives, path metrics, heuristic-quality
diagnostics, and schema `4.0.0`. Monte Carlo canvas surfaces those fields.

## P1 (complete)

Factorial attribution study `run_sprint4` (S4-06–S4-10):

- mech × cost × algorithm trials (schema `4.1.0`)
- A* savings tables and plots
- search-landscape bundles under `landscape/`
- mechanism/graph descriptors and simple correlations
- paired bootstrap CIs

Reproduce:

```bash
MPLBACKEND=Agg PYTHONPATH=src python scripts/reproduce_sprint4.py \
  --config configs/sprint4.smoke.v1.yaml
```

Science-scale fixed pair: `configs/sprint4.factorial.v1.yaml`.

## P2 (complete)

- **S4-11** monotonic uniform-U vs uniform-Q control: `run_sprint4_qgrid`,
  configs `configs/sprint4.qgrid.smoke.v1.yaml` /
  `configs/sprint4.qgrid.v1.yaml`, schema `4.2.0` for control rows.
- **S4-12** deferred `(q,σ)` design note:
  `docs/notes/S4-12-lifted-output-state.md` (ADR-001 unchanged).

Reproduce:

```bash
MPLBACKEND=Agg PYTHONPATH=src python scripts/reproduce_sprint4_qgrid.py \
  --config configs/sprint4.qgrid.smoke.v1.yaml
```
