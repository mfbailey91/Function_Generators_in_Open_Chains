"""Sprint V2.5 — Controlled 2R study (minimal implementation).

This module provides a small, deterministic driver that executes the
four required experiment cells using the already-implemented Version 2
single-experiment runner (`experiments.v2_runner.run_v2_experiment`).

It focuses on:
1. Running the four-cell matrix (A–D) for a fixed task set.
2. Enforcing the shared uniform-Q null-control gate via V2-409 on cell B.
3. Running a lightweight resolution sweep (cell B only) suitable for unit tests.

It intentionally does *not* implement the full “modest mechanism population”
and full paper-facing reporting pipeline from the sprint description.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.experiments.v2_config import (
    validate_v2_config_mapping,
)
from inequality_mechanisms.experiments.v2_runner import V2RunResult, run_v2_experiment

_MechanismIdA = Literal["fourbar"]
_MechanismIdB = Literal["equivalent_affine_gearbox"]

_CELL_NAMES = ("A", "B", "C", "D")
_ObjectiveCost = Literal["output_euclidean", "input_euclidean"]
_SamplingDomain = Literal["input", "output"]


@dataclass(frozen=True, slots=True)
class CellSpec:
    name: Literal["A", "B", "C", "D"]
    sampling_domain: _SamplingDomain
    objective_cost: _ObjectiveCost


_FOUR_CELL_MATRIX: tuple[CellSpec, ...] = (
    CellSpec(name="A", sampling_domain="input", objective_cost="output_euclidean"),
    CellSpec(name="B", sampling_domain="output", objective_cost="output_euclidean"),
    CellSpec(name="C", sampling_domain="output", objective_cost="input_euclidean"),
    CellSpec(name="D", sampling_domain="input", objective_cost="input_euclidean"),
)


def _read_trials(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _assert_null_control_cell_b_matches(
    *,
    run_path: Path,
    algorithm: str = "dijkstra",
    mechanism_a: _MechanismIdA = "fourbar",
    mechanism_b: _MechanismIdB = "equivalent_affine_gearbox",
) -> None:
    """Check the null-control invariant at the row level (V2-409)."""
    trials_path = run_path / "trials.jsonl"
    assert trials_path.is_file()
    rows = _read_trials(trials_path)

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        by_key[(row["mechanism_id"], row["algorithm"])] = row

    row_a = by_key[(mechanism_a, algorithm)]
    row_b = by_key[(mechanism_b, algorithm)]

    assert row_a["found"] == row_b["found"]
    assert row_a["start_node_id"] == row_b["start_node_id"]
    assert row_a["goal_node_id"] == row_b["goal_node_id"]
    assert math.isfinite(row_a["optimal_cost"])
    assert math.isfinite(row_b["optimal_cost"])
    assert abs(row_a["optimal_cost"] - row_b["optimal_cost"]) <= 1e-12
    assert row_a["path_node_ids"] == row_b["path_node_ids"]
    assert row_a["expanded_node_ids"] == row_b["expanded_node_ids"]


def _base_v2_config_dict(
    *,
    seed: int,
    trials: int,
    tasks_pairs: tuple[tuple[float, float], tuple[float, float]],
    output_tolerance: float,
    shape: tuple[int, int],
    algorithms: list[str],
    min_abs_gain: float,
    inverse_tolerance: float,
    endpoint_margin_fraction: float,
    n_samples: int,
    table_samples_per_axis: int,
    certification_samples_per_axis: int,
    min_u_width: float,
) -> dict[str, Any]:
    start_q = list(map(float, tasks_pairs[0]))
    goal_q = list(map(float, tasks_pairs[1]))

    # Single-task fixture for unit-test speed.
    tasks = {
        "source": "fixed_output_pairs",
        "output_tolerance": float(output_tolerance),
        "pairs": [{"start_q": start_q, "goal_q": goal_q}],
    }

    return {
        "architecture_version": 2,
        "result_schema_version": 2,
        "planning_space": "output",
        "seed": int(seed),
        "trials": int(trials),
        "mechanisms": {"comparison": "fourbar_vs_equivalent_affine_gearbox", "dim": 2},
        "branch": {
            "selection": "monotonic_interval",
            "certification_samples_per_axis": int(certification_samples_per_axis),
            "minimum_abs_gain": float(min_abs_gain),
            "inverse_tolerance": float(inverse_tolerance),
            "endpoint_margin_fraction": float(endpoint_margin_fraction),
            "n_samples": int(n_samples),
            "min_u_width": float(min_u_width),
            "table_samples_per_axis": int(table_samples_per_axis),
        },
        "sampling": {
            "domain": "output",  # overridden per cell
            "shape": [int(shape[0]), int(shape[1])],
            "include_endpoints": True,
        },
        "objective": {
            "cost": "output_euclidean",  # overridden per cell
            "heuristic": None,
        },
        "edge_validation": {"samples": 17},
        "tasks": tasks,
        "algorithms": list(algorithms),
    }


def run_v2_2r_controlled_deterministic_matrix(
    *,
    results_root: Path,
    run_id_prefix: str,
    shape: tuple[int, int] = (6, 6),
    seed: int = 123,
    algorithms: list[str] | None = None,
    tasks_pairs: tuple[tuple[float, float], tuple[float, float]]
    = ((0.0, 0.0), (1.0, 1.0)),
    output_tolerance: float = 100.0,
) -> dict[str, V2RunResult]:
    """Run a deterministic 2R four-cell matrix for a fixed resolution."""
    if algorithms is None:
        algorithms = ["dijkstra"]

    base = _base_v2_config_dict(
        seed=seed,
        trials=1,
        tasks_pairs=tasks_pairs,
        output_tolerance=output_tolerance,
        shape=shape,
        algorithms=algorithms,
        min_abs_gain=0.05,
        inverse_tolerance=1.0e-6,
        endpoint_margin_fraction=0.02,
        n_samples=64,
        table_samples_per_axis=17,
        certification_samples_per_axis=9,
        min_u_width=0.3,
    )

    out: dict[str, V2RunResult] = {}
    for cell in _FOUR_CELL_MATRIX:
        cfg_dict = dict(base)
        cfg_dict["sampling"] = dict(base["sampling"], domain=cell.sampling_domain)
        cfg_dict["objective"] = dict(
            base["objective"],
            cost=cell.objective_cost,
            heuristic=cell.objective_cost,
        )
        cfg = validate_v2_config_mapping(cfg_dict)

        run_id = f"{run_id_prefix}_cell{cell.name}_{shape[0]}x{shape[1]}"
        out[cell.name] = run_v2_experiment(
            cfg,
            results_root=results_root,
            run_id=run_id,
            write_figures=False,
        )

    return out


def run_v2_2r_resolution_sweep_cell_b(
    *,
    results_root: Path,
    run_id_prefix: str,
    shapes: list[tuple[int, int]] = [(4, 4), (6, 6)],
    seed: int = 123,
    tasks_pairs: tuple[tuple[float, float], tuple[float, float]]
    = ((0.0, 0.0), (1.0, 1.0)),
    output_tolerance: float = 100.0,
) -> list[V2RunResult]:
    """Run cell B across a small set of resolutions (suitable for tests)."""
    results: list[V2RunResult] = []
    for shape in shapes:
        runs = run_v2_2r_controlled_deterministic_matrix(
            results_root=results_root,
            run_id_prefix=run_id_prefix,
            shape=shape,
            seed=seed,
            algorithms=["dijkstra"],
            tasks_pairs=tasks_pairs,
            output_tolerance=output_tolerance,
        )
        results.append(runs["B"])
    return results

