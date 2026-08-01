#!/usr/bin/env python3
"""Run a Version 2 experiment and write an immutable run package (Sprint V2.4).

Example
-------
::

    python scripts/run_v2_experiment.py --config configs/v2/smoke.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow ``python scripts/run_v2_experiment.py`` without relying solely on an
# editable install (macOS can mark setuptools ``.pth`` files UF_HIDDEN, which
# site.py then skips).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import typer  # noqa: E402

from inequality_mechanisms.experiments.v2_runner import (  # noqa: E402
    run_v2_experiment_from_path,
)
from inequality_mechanisms.experiments.v2_shared_q_paired_study import (  # noqa: E402
    is_shared_q_paired_study_mapping,
    run_shared_q_paired_study_from_path,
)

app = typer.Typer(
    add_completion=False,
    help="Run a strict Version 2 experiment config and write a run package.",
)


@app.command()
def main(
    config: Path = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to a Version 2 experiment YAML (default: configs/v2/smoke.yaml).",
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
    no_figures: bool = typer.Option(
        False,
        "--no-figures",
        help="Skip writing figures/ PNGs.",
    ),
) -> None:
    """Run the Version 2 pipeline and print the resulting run package path."""
    import yaml  # type: ignore[import-untyped]

    cfg_path = (
        config if config is not None else _REPO_ROOT / "configs" / "v2" / "smoke.yaml"
    )
    if not cfg_path.is_file():
        raise typer.BadParameter(f"config not found: {cfg_path}")

    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and is_shared_q_paired_study_mapping(raw):
        result = run_shared_q_paired_study_from_path(
            cfg_path,
            results_root=results_root,
            run_id=run_id,
            write_figures=not no_figures,
        )
        typer.echo(f"run_id={result.run_id}")
        typer.echo(f"path={result.path}")
        typer.echo(f"n_trial_rows={result.n_trial_rows}")
        typer.echo(f"n_failure_rows={result.n_failure_rows}")
        typer.echo(f"n_pair_comparisons={result.n_pair_comparisons}")
        return

    result = run_v2_experiment_from_path(
        cfg_path,
        results_root=results_root,
        run_id=run_id,
        write_figures=not no_figures,
    )
    typer.echo(f"run_id={result.run_id}")
    typer.echo(f"path={result.path}")
    typer.echo(f"mechanism_ids={result.mechanism_ids}")
    typer.echo(f"n_tasks={result.n_tasks}")
    typer.echo(f"n_trial_rows={result.n_trial_rows}")
    typer.echo(f"n_failure_rows={result.n_failure_rows}")


if __name__ == "__main__":
    app()
