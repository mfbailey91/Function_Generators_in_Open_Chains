#!/usr/bin/env python3
"""Reproduce the Sprint Five path-quality paired study (S5-06–S5-09).

Example
-------
::

    python scripts/reproduce_sprint5.py --config configs/sprint5.smoke.v1.yaml
    python scripts/reproduce_sprint5.py --config configs/sprint5.smoke.v1.yaml --seed 42
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import typer  # noqa: E402
from inequality_mechanisms.experiments import (  # noqa: E402
    load_experiment_config,
)
from inequality_mechanisms.experiments.sprint5 import run_sprint5  # noqa: E402

app = typer.Typer(
    add_completion=False,
    help="Reproduce Sprint Five path-quality paired study outputs.",
)


@app.command()
def main(
    config: Path = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to experiment YAML (default: configs/sprint5.smoke.v1.yaml).",
        exists=False,
        dir_okay=False,
    ),
    results_root: Path | None = typer.Option(
        None,
        "--results-root",
        help="Directory for run folders (default: repository results/).",
    ),
    run_id: str | None = typer.Option(
        None,
        "--run-id",
        help="Optional explicit run id (must not already exist).",
    ),
    figures_dir: Path | None = typer.Option(
        None,
        "--figures-dir",
        help="Optional directory to copy expansion PNGs into.",
    ),
    seed: int | None = typer.Option(
        None,
        "--seed",
        help=(
            "Master RNG seed for start/goal sampling. "
            "Default: a fresh random seed each invocation "
            "(so path-sample start/goal plots change)."
        ),
    ),
    use_config_seed: bool = typer.Option(
        False,
        "--use-config-seed",
        help="Keep the seed from the YAML config instead of drawing a fresh one.",
    ),
) -> None:
    """Run the Sprint Five path-quality study and write the result package."""
    cfg_path = (
        config
        if config is not None
        else _REPO_ROOT / "configs" / "sprint5.smoke.v1.yaml"
    )
    if not cfg_path.is_file():
        raise typer.BadParameter(f"config not found: {cfg_path}")

    experiment = load_experiment_config(cfg_path)
    if use_config_seed:
        chosen_seed = int(experiment.seed)
    elif seed is not None:
        chosen_seed = int(seed)
    else:
        chosen_seed = int(secrets.randbelow(2**31 - 1))
    # Pydantic models are frozen-ish via validation; rebuild with new seed.
    experiment = experiment.model_copy(update={"seed": chosen_seed})

    run = run_sprint5(
        experiment,
        results_root=results_root,
        run_id=run_id,
        figures_dir=figures_dir,
    )
    typer.echo(f"run_id={run.run_id}")
    typer.echo(f"seed={chosen_seed}")
    typer.echo(f"status={run.status}")
    typer.echo(f"path={run.path}")
    typer.echo(f"canvas={run.path / 'index.html'}")
    for name in sorted(run.outputs):
        typer.echo(f"output[{name}]={run.resolve_output(name)}")


if __name__ == "__main__":
    app()
