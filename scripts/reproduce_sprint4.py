#!/usr/bin/env python3
"""Reproduce the Sprint Four factorial attribution study (S4-06–S4-10).

Example
-------
::

    python scripts/reproduce_sprint4.py --config configs/sprint4.smoke.v1.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import typer  # noqa: E402
from inequality_mechanisms.experiments import (  # noqa: E402
    load_experiment_config,
    run_sprint4,
)

app = typer.Typer(
    add_completion=False,
    help="Reproduce Sprint Four mech × cost × algorithm factorial outputs.",
)


@app.command()
def main(
    config: Path = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to experiment YAML (default: configs/sprint4.smoke.v1.yaml).",
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
) -> None:
    """Run the Sprint Four factorial and write the result package."""
    cfg_path = (
        config
        if config is not None
        else _REPO_ROOT / "configs" / "sprint4.smoke.v1.yaml"
    )
    if not cfg_path.is_file():
        raise typer.BadParameter(f"config not found: {cfg_path}")

    experiment = load_experiment_config(cfg_path)
    run = run_sprint4(
        experiment,
        results_root=results_root,
        run_id=run_id,
        figures_dir=figures_dir,
    )
    typer.echo(f"run_id={run.run_id}")
    typer.echo(f"status={run.status}")
    typer.echo(f"path={run.path}")
    for name in sorted(run.outputs):
        typer.echo(f"output[{name}]={run.resolve_output(name)}")


if __name__ == "__main__":
    app()
