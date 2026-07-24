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

## Documentation

- [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) — scope, architecture, milestones
- [docs/BACKLOG.md](docs/BACKLOG.md) — implementation issues
- [docs/ADR-001-search-in-input-space.md](docs/ADR-001-search-in-input-space.md) —
  search state identity lives in input configuration space
