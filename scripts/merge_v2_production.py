#!/usr/bin/env python3
"""Merge Version 2 production shards and regenerate the report canvas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import typer  # noqa: E402

from inequality_mechanisms.experiments.v2_production_canvas import (  # noqa: E402
    write_production_canvas,
)
from inequality_mechanisms.experiments.v2_production_config import (  # noqa: E402
    load_v2_production_config,
)
from inequality_mechanisms.experiments.v2_production_merge import (  # noqa: E402
    merge_production_run,
)

app = typer.Typer(add_completion=False, help="Merge a production run package.")


@app.command()
def main(
    run: Path = typer.Option(
        ...,
        "--run",
        help="Path to results/<run_id>.",
        exists=True,
        file_okay=False,
    ),
) -> None:
    """Merge shards under ``run`` and write reports."""
    snapshot = run / "config.snapshot.yaml"
    if not snapshot.is_file():
        raise typer.BadParameter(f"missing config snapshot: {snapshot}")
    config = load_v2_production_config(snapshot)
    summary = merge_production_run(run, config)
    env_path = run / "environment.json"
    environment = json.loads(env_path.read_text()) if env_path.is_file() else {}
    write_production_canvas(run, {"summary": summary, "environment": environment})
    typer.echo(f"n_mechanisms={summary['n_mechanisms']}")
    typer.echo(f"n_trials={summary['n_trials']}")
    typer.echo(f"path={run / 'reports' / 'index.html'}")


if __name__ == "__main__":
    app()
