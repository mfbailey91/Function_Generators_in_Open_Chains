#!/usr/bin/env python3
"""Plot randomized paired path demos on the pilot lattice (U / Q / X).

Example
-------
::

    python scripts/plot_path_demos.py --config configs/pilot.v1.yaml --seed 0
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Allow ``python scripts/plot_path_demos.py`` without relying solely on an
# editable install (macOS can mark setuptools ``.pth`` files UF_HIDDEN, which
# site.py then skips).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import numpy as np  # noqa: E402
import typer  # noqa: E402
from inequality_mechanisms.experiments import (  # noqa: E402
    build_paired_graphs,
    create_run,
    generate_paired_tasks,
    generate_run_id,
    load_experiment_config,
)
from inequality_mechanisms.kinematics import Planar2R  # noqa: E402
from inequality_mechanisms.search import astar, dijkstra  # noqa: E402
from inequality_mechanisms.visualization.paths import (  # noqa: E402
    cost_from_start,
    path_outputs,
    plot_cartesian_path,
    plot_input_path,
    plot_output_path,
)

app = typer.Typer(
    add_completion=False,
    help="Plot randomized gearbox / four-bar path demos on the pilot lattice.",
)


def _sample_reachable_task(
    paired: Any,
    *,
    rng: np.random.Generator,
    min_output_separation: float,
    preimage_policy: str,
    max_sample_attempts: int,
) -> tuple[Any, Any, Any]:
    """Return ``(task, gearbox_result, fourbar_result)`` with both A* paths found."""
    for _ in range(max_sample_attempts):
        tasks = generate_paired_tasks(
            paired.gearbox,
            paired.fourbar,
            n_trials=1,
            rng=rng,
            min_output_separation=min_output_separation,
            preimage_policy=preimage_policy,  # type: ignore[arg-type]
            max_sample_attempts=max_sample_attempts,
        )
        task = tasks[0]
        gb = astar(
            paired.gearbox,
            task.gearbox.start_node_id,
            task.gearbox.goal_node_id,
        )
        fb = astar(
            paired.fourbar,
            task.fourbar.start_node_id,
            task.fourbar.goal_node_id,
        )
        if gb.found and fb.found:
            return task, gb, fb
    raise RuntimeError(
        f"failed to sample a mutually reachable paired task after "
        f"{max_sample_attempts} attempts"
    )


@app.command()
def main(
    config: Path = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to experiment YAML (default: configs/pilot.v1.yaml).",
        exists=False,
        dir_okay=False,
    ),
    seed: int | None = typer.Option(
        None,
        "--seed",
        help="RNG seed override (default: config.seed).",
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
    L1: float = typer.Option(1.0, "--L1", help="Planar 2R proximal link length."),
    L2: float = typer.Option(1.0, "--L2", help="Planar 2R distal link length."),
) -> None:
    """Sample one paired reachable task and write U / Q / Cartesian PNGs."""
    cfg_path = (
        config if config is not None else _REPO_ROOT / "configs" / "pilot.v1.yaml"
    )
    if not cfg_path.is_file():
        raise typer.BadParameter(f"config not found: {cfg_path}")

    experiment = load_experiment_config(cfg_path)
    rng_seed = int(experiment.seed if seed is None else seed)
    paired = build_paired_graphs(experiment)
    rng = np.random.default_rng(rng_seed)

    task, gb_result, fb_result = _sample_reachable_task(
        paired,
        rng=rng,
        min_output_separation=experiment.trials.min_output_separation,
        preimage_policy=experiment.trials.preimage_policy,
        max_sample_attempts=experiment.trials.max_sample_attempts,
    )

    # Optional Dijkstra check (same C* under Version 1 symmetric costs).
    gb_dij = dijkstra(
        paired.gearbox,
        task.gearbox.start_node_id,
        task.gearbox.goal_node_id,
    )
    fb_dij = dijkstra(
        paired.fourbar,
        task.fourbar.start_node_id,
        task.fourbar.goal_node_id,
    )

    rid = (
        run_id
        if run_id is not None
        else f"path_demo_{generate_run_id(seed=rng_seed)}"
    )
    run = create_run(
        experiment,
        results_root=results_root,
        run_id=rid,
    )
    try:
        run.mark_running()
        plant = Planar2R(L1=L1, L2=L2)
        outputs_dir = run.path / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        gb_costs = cost_from_start(paired.gearbox, task.gearbox.start_node_id)
        fb_costs = cost_from_start(paired.fourbar, task.fourbar.start_node_id)

        figures: dict[str, Path] = {
            "gearbox_input": plot_input_path(
                paired.gearbox,
                gb_result.path,
                outputs_dir / "gearbox_input.png",
                costs=gb_costs,
                start=task.gearbox.start_node_id,
                goal=task.gearbox.goal_node_id,
                title="Gearbox: 4-connected grid in U",
            ),
            "gearbox_output": plot_output_path(
                paired.gearbox,
                gb_result.path,
                outputs_dir / "gearbox_output.png",
                costs=gb_costs,
                start=task.gearbox.start_node_id,
                goal=task.gearbox.goal_node_id,
                title="Gearbox: mapped path in Q",
            ),
            "gearbox_cartesian": plot_cartesian_path(
                path_outputs(paired.gearbox, gb_result.path),
                outputs_dir / "gearbox_cartesian.png",
                plant=plant,
                title="Gearbox: shared start/goal poses (Cartesian)",
            ),
            "fourbar_input": plot_input_path(
                paired.fourbar,
                fb_result.path,
                outputs_dir / "fourbar_input.png",
                costs=fb_costs,
                start=task.fourbar.start_node_id,
                goal=task.fourbar.goal_node_id,
                title="Four-bar: 4-connected grid in U",
            ),
            "fourbar_output": plot_output_path(
                paired.fourbar,
                fb_result.path,
                outputs_dir / "fourbar_output.png",
                costs=fb_costs,
                start=task.fourbar.start_node_id,
                goal=task.fourbar.goal_node_id,
                title="Four-bar: mapped path in Q",
            ),
            "fourbar_cartesian": plot_cartesian_path(
                path_outputs(paired.fourbar, fb_result.path),
                outputs_dir / "fourbar_cartesian.png",
                plant=plant,
                title="Four-bar: shared start/goal poses (Cartesian)",
            ),
        }

        for name, path in figures.items():
            run.register_output(name, f"outputs/{path.name}")

        run.write_json(
            "task",
            {
                "seed": rng_seed,
                "q_start": task.q_start.tolist(),
                "q_goal": task.q_goal.tolist(),
                "gearbox": task.gearbox.to_dict(),
                "fourbar": task.fourbar.to_dict(),
                "astar": {
                    "gearbox": {
                        "found": gb_result.found,
                        "cost": gb_result.cost,
                        "n_expanded": gb_result.n_expanded,
                        "n_path_edges": gb_result.n_path_edges,
                    },
                    "fourbar": {
                        "found": fb_result.found,
                        "cost": fb_result.cost,
                        "n_expanded": fb_result.n_expanded,
                        "n_path_edges": fb_result.n_path_edges,
                    },
                },
                "dijkstra": {
                    "gearbox": {
                        "found": gb_dij.found,
                        "cost": gb_dij.cost,
                        "n_expanded": gb_dij.n_expanded,
                    },
                    "fourbar": {
                        "found": fb_dij.found,
                        "cost": fb_dij.cost,
                        "n_expanded": fb_dij.n_expanded,
                    },
                },
                "plant": {"L1": L1, "L2": L2},
            },
        )
        run.mark_completed()
    except Exception as exc:
        run.mark_failed(str(exc))
        raise

    typer.echo(f"run_id={run.run_id}")
    typer.echo(f"status={run.status}")
    typer.echo(f"path={run.path}")
    for name in sorted(run.outputs):
        typer.echo(f"output[{name}]={run.resolve_output(name)}")


if __name__ == "__main__":
    app()
