#!/usr/bin/env python3
"""Run the bounded Experiment B Cartesian goal-region Dijkstra/A* smoke."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import typer  # noqa: E402

from inequality_mechanisms.experiments.v2_cartesian_goal_region import (  # noqa: E402
    run_cartesian_goal_region_from_path,
)

app = typer.Typer(add_completion=False)


@app.command()
def main(
    config: Path = typer.Option(..., "--config", "-c", exists=True, dir_okay=False),
    results_root: Path | None = typer.Option(None, "--results-root"),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    result = run_cartesian_goal_region_from_path(
        config, results_root=results_root, run_id=run_id
    )
    typer.echo(f"run_id={result.run_id}")
    typer.echo(f"path={result.path}")
    typer.echo(f"n_tasks={result.n_tasks}")
    typer.echo(f"n_trial_rows={result.n_trial_rows}")
    typer.echo(f"n_failure_rows={result.n_failure_rows}")


if __name__ == "__main__":
    app()
