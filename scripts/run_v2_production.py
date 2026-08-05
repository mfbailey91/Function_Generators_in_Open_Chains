#!/usr/bin/env python3
"""Run a Version 2 Dijkstra production Monte Carlo campaign."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import typer  # noqa: E402

from inequality_mechanisms.experiments.v2_production_runner import (  # noqa: E402
    V2ProductionRunResult,
    run_v2_production_from_path,
)

app = typer.Typer(
    add_completion=False,
    help="Run a Version 2 Dijkstra production Monte Carlo config.",
)


@app.command()
def main(
    config: Path = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to a production Monte Carlo YAML.",
        exists=True,
        dir_okay=False,
    ),
    results_root: Path | None = typer.Option(
        None,
        "--results-root",
        help="Directory for run folders (default: repository results/).",
    ),
    run_id: str | None = typer.Option(
        None, "--run-id", help="Optional explicit run id."
    ),
    stage: str | None = typer.Option(None, "--stage", help="Override study.stage."),
    resume: bool = typer.Option(False, "--resume", help="Resume an existing run id."),
    memory_override: bool = typer.Option(
        False,
        "--memory-override",
        help="Recorded override when preflight exceeds the memory fraction.",
    ),
    apply_decisions: Path | None = typer.Option(
        None,
        "--apply-decisions",
        help="Directory or JSON file with resolution/task-count decisions.",
    ),
    export_sample_bank: Path | None = typer.Option(
        None,
        "--export-sample-bank",
        help="Write the sample bank JSON to this path.",
    ),
    retry_failed: bool = typer.Option(
        False,
        "--retry",
        help="Re-run failed mechanism-pair shards on resume.",
    ),
) -> None:
    """Execute one production stage and print the run package path."""
    result = run_v2_production_from_path(
        config,
        results_root=results_root,
        run_id=run_id,
        stage=stage,
        resume=resume if resume else None,
        memory_override=memory_override or None,
        apply_decisions=apply_decisions,
        export_sample_bank=export_sample_bank,
        retry_failed=retry_failed,
    )
    if isinstance(result, V2ProductionRunResult):
        typer.echo(f"run_id={result.run_id}")
        typer.echo(f"path={result.path}")
        typer.echo(f"stage={result.stage}")
        typer.echo(f"n_completed={result.n_completed}")
        typer.echo(f"n_failed={result.n_failed}")
        typer.echo(f"n_pending={result.n_pending}")
        return
    typer.echo(f"decision={result}")


if __name__ == "__main__":
    app()
