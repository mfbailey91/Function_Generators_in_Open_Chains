#!/usr/bin/env python3
"""Reproduce the Sprint Six equivalence / resolution / MC study.

Example
-------
::

    python scripts/reproduce_sprint6.py --config configs/sprint6.equivalence.smoke.v1.yaml
    python scripts/reproduce_sprint6.py --config configs/sprint6.resolution.smoke.v1.yaml --mode resolution
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import typer  # noqa: E402
from inequality_mechanisms.experiments import (  # noqa: E402
    load_experiment_config,
)
from inequality_mechanisms.experiments.sprint6 import run_sprint6  # noqa: E402

app = typer.Typer(
    add_completion=False,
    help="Reproduce Sprint Six equivalence, resolution, and Monte Carlo outputs.",
)


@app.command()
def main(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to experiment YAML (default: configs/sprint6.equivalence.smoke.v1.yaml).",
        exists=False,
        dir_okay=False,
    ),
    results_root: Optional[Path] = typer.Option(
        None,
        "--results-root",
        help="Directory for run folders (default: repository results/).",
    ),
    run_id: Optional[str] = typer.Option(
        None,
        "--run-id",
        help="Optional explicit run id (must not already exist).",
    ),
    mode: str = typer.Option(
        "full",
        "--mode",
        help="full | equivalence | resolution | monte_carlo",
    ),
) -> None:
    """Run the Sprint Six study and write the result package."""
    cfg_path = (
        config
        if config is not None
        else _REPO_ROOT / "configs" / "sprint6.equivalence.smoke.v1.yaml"
    )
    cfg = load_experiment_config(cfg_path)
    run = run_sprint6(
        cfg,
        results_root=results_root,
        run_id=run_id,
        mode=mode,
    )
    typer.echo(f"Sprint Six run completed: {run.run_id}")
    typer.echo(f"  path: {run.path}")
    canvas = run.path / "index.html"
    if canvas.is_file():
        typer.echo(f"  canvas: {canvas}")


if __name__ == "__main__":
    app()
