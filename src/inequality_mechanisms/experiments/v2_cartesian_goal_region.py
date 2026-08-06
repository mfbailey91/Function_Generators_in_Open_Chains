"""Experiment B Cartesian goal-region runner (smoke, calibration, production gate).

Smoke proves goal-set Dijkstra/A* on one pair. Calibration (V2B-005) writes
radius/resolution/start-attachment decision JSON. Production refuses a missing
decision package; crossed-population orchestration remains a later work package.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml  # type: ignore[import-untyped]

from inequality_mechanisms.experiments.registry import (
    capture_environment,
    capture_revision,
    default_results_root,
    generate_run_id,
    validate_run_id,
)
from inequality_mechanisms.experiments.v2_cartesian_calibration import (
    CartesianCalibrationSettings,
    apply_cartesian_calibration_decisions,
    assert_cartesian_calibration_decisions_present,
    load_cartesian_calibration_decisions,
    run_cartesian_calibration_sweep,
    write_cartesian_calibration_decisions,
)
from inequality_mechanisms.experiments.v2_cartesian_canvas import write_cartesian_canvas
from inequality_mechanisms.experiments.v2_cartesian_tasks import (
    CartesianAnnularSectorDomain,
    assert_paired_cartesian_query_identity,
    generate_cartesian_task_bank,
    ik_family,
    resolve_cartesian_task,
)
from inequality_mechanisms.experiments.v2_config import (
    V2ExperimentConfig,
    validate_v2_config_mapping,
)
from inequality_mechanisms.experiments.v2_runner import (
    build_graphs,
    build_mechanism_branches,
)
from inequality_mechanisms.graphs.pair_invariants import assert_shared_q_pair_invariants
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.search.graph_solver import production_graph_solver
from inequality_mechanisms.search.v2_objectives import resolve_v2_goal_set_objective

VALID_STAGES = frozenset({"smoke", "calibration", "production"})


@dataclass(frozen=True, slots=True)
class CartesianGoalRegionRunConfig:
    """Validated Experiment B configuration loaded from one YAML."""

    experiment_id: str
    seed: int
    task_count: int
    stage: str
    solver_policy: str
    algorithms: tuple[str, ...]
    record_expanded: bool
    base_experiment: V2ExperimentConfig
    base_experiment_source: dict[str, Any]
    domain: CartesianAnnularSectorDomain
    calibration: CartesianCalibrationSettings | None = None
    calibration_decisions: str | None = None


@dataclass(frozen=True, slots=True)
class CartesianGoalRegionRunResult:
    run_id: str
    path: Path
    n_tasks: int
    n_trial_rows: int
    n_failure_rows: int
    stage: str = "smoke"


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _infer_stage(root: Mapping[str, Any], solver_policy: str) -> str:
    if "stage" in root and root["stage"] is not None:
        stage = str(root["stage"])
    elif solver_policy == "smoke_oracle_pair_v1":
        stage = "smoke"
    elif solver_policy == "calibration_dijkstra_v1":
        stage = "calibration"
    else:
        stage = "production"
    if stage not in VALID_STAGES:
        raise ValueError(f"stage must be one of {sorted(VALID_STAGES)}")
    return stage


def _parse_calibration_settings(raw: dict[str, Any] | None) -> CartesianCalibrationSettings:
    block = raw or {}
    resolutions = block.get("candidate_resolutions", [32, 64, 96, 128])
    radii = block.get("candidate_goal_radii", [0.04, 0.06, 0.08, 0.10, 0.12])
    return CartesianCalibrationSettings(
        candidate_resolutions=tuple(int(n) for n in resolutions),
        candidate_goal_radii=tuple(float(r) for r in radii),
        min_attachment_rate=float(block.get("min_attachment_rate", 0.50)),
        max_relative_effect_change=float(
            block.get("max_relative_effect_change", 0.05)
        ),
        separation_floor=float(block.get("separation_floor", 0.30)),
        run_search=bool(block.get("run_search", True)),
    )


def load_cartesian_goal_region_config(
    path: Path | str,
    *,
    stage_override: str | None = None,
) -> CartesianGoalRegionRunConfig:
    """Load the strict nested Experiment B config without weakening V2 gates."""
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    root = _require_mapping(raw, "config root")
    if int(root.get("experiment_b_schema_version", -1)) != 1:
        raise ValueError("experiment_b_schema_version must equal 1")
    base_source = dict(
        _require_mapping(root.get("base_experiment"), "base_experiment")
    )
    forbidden_schema_carriers = {"seed", "trials", "objective", "tasks", "algorithms"}
    present_carriers = sorted(forbidden_schema_carriers.intersection(base_source))
    if present_carriers:
        raise ValueError(
            "base_experiment contains Experiment-B-irrelevant schema fields: "
            + ", ".join(present_carriers)
        )
    # V2 graph builders currently accept V2ExperimentConfig. Inject private,
    # deterministic schema-carrier values here rather than exposing duplicate
    # task/solver/heuristic semantics in the public Experiment B YAML.
    base_for_validation = dict(base_source)
    base_for_validation.update(
        {
            "seed": int(root["seed"]),
            "trials": 1,
            "objective": {
                "cost": "actuator_travel",
                "heuristic": "input_euclidean",
            },
            "tasks": {
                "source": "fixed_output_pairs",
                "output_tolerance": 0.0,
                "pairs": [{"start_q": [0.0, 0.0], "goal_q": [0.0, 0.0]}],
            },
            "algorithms": ["dijkstra"],
        }
    )
    base = validate_v2_config_mapping(base_for_validation)
    if base.mechanisms.dim != 2:
        raise ValueError("Experiment B kickoff requires a planar 2R base experiment")
    if base.sampling.domain != "output":
        raise ValueError("Experiment B requires the shared uniform-Q graph")
    if base.objective.cost != "actuator_travel":
        raise ValueError("Experiment B primary objective must be actuator_travel")

    domain_raw = _require_mapping(root.get("cartesian_domain"), "cartesian_domain")
    domain = CartesianAnnularSectorDomain(
        domain_id=str(domain_raw["domain_id"]),
        radial_min=float(domain_raw["radial_min"]),
        radial_max=float(domain_raw["radial_max"]),
        angle_min=float(domain_raw["angle_min"]),
        angle_max=float(domain_raw["angle_max"]),
        start_tolerance=float(domain_raw["start_tolerance"]),
        goal_radius=float(domain_raw["goal_radius"]),
        min_start_goal_separation=float(
            domain_raw["min_start_goal_separation"]
        ),
        L1=float(domain_raw.get("L1", 1.0)),
        L2=float(domain_raw.get("L2", 1.0)),
    )
    solver_policy = str(root.get("solver_policy", ""))
    stage = (
        str(stage_override)
        if stage_override is not None
        else _infer_stage(root, solver_policy)
    )
    if stage not in VALID_STAGES:
        raise ValueError(f"stage must be one of {sorted(VALID_STAGES)}")
    algorithms = tuple(str(a) for a in root.get("algorithms", ()))
    if stage == "smoke":
        if solver_policy != "smoke_oracle_pair_v1":
            raise ValueError("smoke stage requires solver_policy smoke_oracle_pair_v1")
        if algorithms != ("dijkstra", "astar"):
            raise ValueError(
                "smoke_oracle_pair_v1 requires algorithms: [dijkstra, astar] "
                "in that order"
            )
        calibration = None
    elif stage == "calibration":
        if solver_policy != "calibration_dijkstra_v1":
            raise ValueError(
                "calibration stage requires solver_policy calibration_dijkstra_v1"
            )
        if algorithms != ("dijkstra",):
            raise ValueError(
                "calibration_dijkstra_v1 requires algorithms: [dijkstra]"
            )
        calibration = _parse_calibration_settings(
            root.get("calibration") if isinstance(root.get("calibration"), dict) else None
        )
    else:
        if solver_policy == "smoke_oracle_pair_v1":
            raise ValueError(
                "production stage must not use smoke_oracle_pair_v1"
            )
        if not algorithms:
            raise ValueError("production stage requires at least one algorithm")
        calibration = _parse_calibration_settings(
            root.get("calibration") if isinstance(root.get("calibration"), dict) else None
        )
    task_count = int(root.get("task_count", 0))
    if task_count < 1:
        raise ValueError("task_count must be positive")
    decisions_path = root.get("calibration_decisions")
    return CartesianGoalRegionRunConfig(
        experiment_id=str(root.get("experiment_id", "experiment_b_cartesian_goal_region")),
        seed=int(root["seed"]),
        task_count=task_count,
        stage=stage,
        solver_policy=solver_policy,
        algorithms=algorithms,
        record_expanded=bool(root.get("record_expanded", False)),
        base_experiment=base,
        base_experiment_source=base_source,
        domain=domain,
        calibration=calibration,
        calibration_decisions=(
            str(decisions_path) if decisions_path is not None else None
        ),
    )


def _path_lengths(graph: Any, path: tuple[int, ...], fk: Planar2R) -> dict[str, float]:
    length_u = 0.0
    length_q = 0.0
    length_x = 0.0
    for a, b in zip(path[:-1], path[1:]):
        length_u += float(np.linalg.norm(graph.u_state(b) - graph.u_state(a)))
        length_q += float(
            graph.branch.output_space.distance(graph.q_state(a), graph.q_state(b))
        )
        length_x += float(np.linalg.norm(fk.forward(graph.q_state(b)) - fk.forward(graph.q_state(a))))
    return {
        "path_length_u": length_u,
        "path_length_q": length_q,
        "path_length_x": length_x,
    }


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def _with_applied_decisions(
    config: CartesianGoalRegionRunConfig,
    decisions: Mapping[str, Any] | None,
) -> CartesianGoalRegionRunConfig:
    if decisions is None:
        return config
    floor = (
        config.calibration.separation_floor
        if config.calibration is not None
        else 0.30
    )
    domain, base = apply_cartesian_calibration_decisions(
        domain=config.domain,
        base_experiment=config.base_experiment,
        decisions=decisions,
        separation_floor=floor,
    )
    source = dict(config.base_experiment_source)
    sampling = dict(source.get("sampling", {}))
    shape_n = int(base.sampling.shape[0])
    sampling["shape"] = [shape_n, shape_n]
    source["sampling"] = sampling
    return replace(
        config,
        domain=domain,
        base_experiment=base,
        base_experiment_source=source,
    )


def _run_search_package(
    config: CartesianGoalRegionRunConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
) -> CartesianGoalRegionRunResult:
    """Execute the paired search evidence package (smoke / production stages)."""
    root = Path(results_root) if results_root is not None else default_results_root()
    root.mkdir(parents=True, exist_ok=True)
    rid = validate_run_id(run_id) if run_id is not None else generate_run_id(seed=config.seed)
    run_dir = root / rid
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")

    branches = build_mechanism_branches(config.base_experiment)
    graphs = build_graphs(config.base_experiment, branches)
    if len(graphs) != 2:
        raise RuntimeError("Experiment B paired smoke requires exactly two mechanisms")
    graph_items = list(graphs.items())
    assert_shared_q_pair_invariants(
        graph_items[0][1],
        graph_items[1][1],
        residual_tol=config.base_experiment.branch.inverse_tolerance,
        edge_n_samples=config.base_experiment.edge_validation.samples,
        raise_on_failure=True,
    )

    fk = Planar2R(config.domain.L1, config.domain.L2)
    tasks = generate_cartesian_task_bank(
        config.domain, n_tasks=config.task_count, seed=config.seed
    )
    task_rows: list[dict[str, Any]] = []
    trial_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []

    for task in tasks:
        resolved_by_mechanism = {
            mechanism_id: resolve_cartesian_task(graph, task, config.domain, fk=fk)
            for mechanism_id, graph in graph_items
        }
        resolved_values = list(resolved_by_mechanism.values())
        assert_paired_cartesian_query_identity(
            graph_items[0][1],
            graph_items[1][1],
            resolved_values[0],
            resolved_values[1],
        )
        reference = resolved_values[0]
        task_rows.append(reference.to_dict())
        if not reference.accepted:
            failure_rows.append(
                {
                    "experiment_id": config.experiment_id,
                    "task_id": task.task_id,
                    "cartesian_domain_id": config.domain.domain_id,
                    "failure_or_exclusion_reason": reference.rejection_reason,
                    "requested_start_x": task.requested_start_x.tolist(),
                    "requested_goal_x": task.requested_goal_x.tolist(),
                    "start_residual": reference.start_residual,
                    "nearest_goal_residual": reference.nearest_goal_residual,
                    "goal_set_size": len(reference.goal_node_ids),
                }
            )
            continue
        assert reference.start_node_id is not None

        for mechanism_id, graph in graph_items:
            algorithm_results: dict[str, Any] = {}
            for algorithm in config.algorithms:
                heuristic_name = (
                    "zero" if algorithm == "dijkstra" else "input_euclidean_goal_set"
                )
                objective = resolve_v2_goal_set_objective(
                    graph,
                    reference.goal_node_ids,
                    cost_name="actuator_travel",
                    heuristic_name=heuristic_name,
                    edge_n_samples=config.base_experiment.edge_validation.samples,
                )
                solver = production_graph_solver(algorithm)
                result = solver.solve(
                    graph,
                    reference.start_node_id,
                    None,
                    objective,
                    goal_node_ids=reference.goal_node_ids,
                    record_expanded=config.record_expanded,
                )
                if not result.found or not result.path:
                    failure_rows.append(
                        {
                            "experiment_id": config.experiment_id,
                            "task_id": task.task_id,
                            "mechanism_id": mechanism_id,
                            "algorithm": algorithm,
                            "failure_or_exclusion_reason": "search_disconnected_or_failed",
                            "goal_set_size": len(reference.goal_node_ids),
                        }
                    )
                    continue
                if result.selected_goal_node_id is None:
                    raise AssertionError(
                        "found goal-set result did not record selected_goal_node_id"
                    )
                selected_goal = int(result.selected_goal_node_id)
                selected_x = fk.forward(graph.q_state(selected_goal))
                row = {
                    "experiment_id": config.experiment_id,
                    "task_id": task.task_id,
                    "cartesian_domain_id": config.domain.domain_id,
                    "mechanism_id": mechanism_id,
                    "algorithm": algorithm,
                    "objective_cost": objective.cost_name,
                    "heuristic": objective.heuristic_name,
                    "selected_start_node_id": reference.start_node_id,
                    "selected_start_q": graph.q_state(reference.start_node_id).tolist(),
                    "selected_start_u": graph.u_state(reference.start_node_id).tolist(),
                    "selected_start_ik_family": reference.selected_start_ik_family,
                    "start_attachment_policy": reference.start_attachment_policy,
                    "requested_start_x": task.requested_start_x.tolist(),
                    "requested_goal_x": task.requested_goal_x.tolist(),
                    "goal_radius_x": config.domain.goal_radius,
                    "goal_set_size": len(reference.goal_node_ids),
                    "selected_goal_node_id": selected_goal,
                    "selected_goal_q": graph.q_state(selected_goal).tolist(),
                    "selected_goal_u": graph.u_state(selected_goal).tolist(),
                    "selected_goal_x": selected_x.tolist(),
                    "selected_goal_residual_x": float(
                        np.linalg.norm(selected_x - task.requested_goal_x)
                    ),
                    "selected_goal_ik_family": ik_family(graph.q_state(selected_goal)),
                    "found": result.found,
                    "cost": result.cost,
                    "n_expanded": result.n_expanded,
                    "n_generated": result.n_generated,
                    "n_stale": result.n_stale,
                    "path_node_ids": list(result.path),
                    **_path_lengths(graph, result.path, fk),
                }
                trial_rows.append(row)
                algorithm_results[algorithm] = result
            if config.stage == "smoke" and {"dijkstra", "astar"}.issubset(
                algorithm_results
            ):
                dijkstra = algorithm_results["dijkstra"]
                astar = algorithm_results["astar"]
                if dijkstra.found != astar.found or not np.isclose(
                    dijkstra.cost, astar.cost, atol=1e-10, rtol=1e-10
                ):
                    raise AssertionError(
                        f"Dijkstra/A* goal-set disagreement for {mechanism_id} "
                        f"task {task.task_id}: {dijkstra.cost} vs {astar.cost}"
                    )

    run_dir.mkdir(parents=True)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "experiment_id": config.experiment_id,
                "stage": config.stage,
                "seed": config.seed,
                "task_count": config.task_count,
                "solver_policy": config.solver_policy,
                "algorithms": list(config.algorithms),
                "record_expanded": config.record_expanded,
                "cartesian_domain": config.domain.to_dict(),
                "base_experiment": config.base_experiment_source,
                "v2_schema_adapter": {
                    "private_fields": [
                        "seed",
                        "trials",
                        "objective",
                        "tasks",
                        "algorithms",
                    ],
                    "purpose": "graph_builder_compatibility_only",
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "tasks.json").write_text(
        json.dumps(task_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (run_dir / "trials.jsonl").write_text(_jsonl(trial_rows), encoding="utf-8")
    (run_dir / "failures.jsonl").write_text(_jsonl(failure_rows), encoding="utf-8")
    manifest = {
        "run_id": rid,
        "experiment_id": config.experiment_id,
        "stage": config.stage,
        "experiment_b_schema_version": 1,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "n_tasks": len(tasks),
        "n_trial_rows": len(trial_rows),
        "n_failure_rows": len(failure_rows),
        "mechanism_ids": list(graphs),
        "solver_policy": config.solver_policy,
        "algorithms": list(config.algorithms),
        "cartesian_domain": config.domain.to_dict(),
        "revision": capture_revision(cwd=None),
        "environment": capture_environment(),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_cartesian_canvas(run_dir)
    return CartesianGoalRegionRunResult(
        run_id=rid,
        path=run_dir,
        n_tasks=len(tasks),
        n_trial_rows=len(trial_rows),
        n_failure_rows=len(failure_rows),
        stage=config.stage,
    )


def _run_calibration_package(
    config: CartesianGoalRegionRunConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
) -> CartesianGoalRegionRunResult:
    if config.calibration is None:
        raise CartesianCalibrationError("calibration settings are required")
    root = Path(results_root) if results_root is not None else default_results_root()
    root.mkdir(parents=True, exist_ok=True)
    rid = validate_run_id(run_id) if run_id is not None else generate_run_id(seed=config.seed)
    run_dir = root / rid
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")

    sweep = run_cartesian_calibration_sweep(
        base_experiment=config.base_experiment,
        domain=config.domain,
        settings=config.calibration,
        task_count=config.task_count,
        seed=config.seed,
    )
    run_dir.mkdir(parents=True)
    write_cartesian_calibration_decisions(
        run_dir,
        radius_decision=sweep["cartesian_radius_decision"],
        resolution_decision=sweep["cartesian_resolution_decision"],
        start_attachment_decision=sweep["cartesian_start_attachment_decision"],
    )
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "experiment_id": config.experiment_id,
                "stage": config.stage,
                "seed": config.seed,
                "task_count": config.task_count,
                "solver_policy": config.solver_policy,
                "algorithms": list(config.algorithms),
                "cartesian_domain": config.domain.to_dict(),
                "calibration": {
                    "candidate_resolutions": list(
                        config.calibration.candidate_resolutions
                    ),
                    "candidate_goal_radii": list(
                        config.calibration.candidate_goal_radii
                    ),
                    "min_attachment_rate": config.calibration.min_attachment_rate,
                    "max_relative_effect_change": (
                        config.calibration.max_relative_effect_change
                    ),
                    "separation_floor": config.calibration.separation_floor,
                    "run_search": config.calibration.run_search,
                },
                "base_experiment": config.base_experiment_source,
                "chosen": sweep["chosen"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "tasks.json").write_text(
        json.dumps(sweep["tasks"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "candidate_rows.jsonl").write_text(
        _jsonl(list(sweep["candidate_rows"])), encoding="utf-8"
    )
    (run_dir / "failures.jsonl").write_text("", encoding="utf-8")
    (run_dir / "trials.jsonl").write_text("", encoding="utf-8")
    manifest = {
        "run_id": rid,
        "experiment_id": config.experiment_id,
        "stage": config.stage,
        "experiment_b_schema_version": 1,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "n_tasks": len(sweep["tasks"]),
        "n_trial_rows": 0,
        "n_failure_rows": 0,
        "n_candidate_rows": len(sweep["candidate_rows"]),
        "solver_policy": config.solver_policy,
        "algorithms": list(config.algorithms),
        "cartesian_domain": config.domain.to_dict(),
        "chosen": sweep["chosen"],
        "decision_files": [
            "cartesian_radius_decision.json",
            "cartesian_resolution_decision.json",
            "cartesian_start_attachment_decision.json",
        ],
        "revision": capture_revision(cwd=None),
        "environment": capture_environment(),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_cartesian_canvas(run_dir)
    return CartesianGoalRegionRunResult(
        run_id=rid,
        path=run_dir,
        n_tasks=len(sweep["tasks"]),
        n_trial_rows=0,
        n_failure_rows=0,
        stage=config.stage,
    )


def run_cartesian_goal_region(
    config: CartesianGoalRegionRunConfig,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    apply_decisions: Path | str | None = None,
) -> CartesianGoalRegionRunResult:
    """Execute smoke, calibration, or decision-gated production package."""
    decisions: dict[str, Any] | None = None
    decisions_path = apply_decisions or config.calibration_decisions
    if decisions_path is not None:
        decisions = load_cartesian_calibration_decisions(decisions_path)
    assert_cartesian_calibration_decisions_present(
        config.stage, decisions=decisions
    )
    effective = _with_applied_decisions(config, decisions)
    if effective.stage == "calibration":
        return _run_calibration_package(
            effective, results_root=results_root, run_id=run_id
        )
    return _run_search_package(
        effective, results_root=results_root, run_id=run_id
    )


def run_cartesian_goal_region_from_path(
    config_path: Path | str,
    *,
    results_root: Path | str | None = None,
    run_id: str | None = None,
    stage: str | None = None,
    apply_decisions: Path | str | None = None,
) -> CartesianGoalRegionRunResult:
    return run_cartesian_goal_region(
        load_cartesian_goal_region_config(config_path, stage_override=stage),
        results_root=results_root,
        run_id=run_id,
        apply_decisions=apply_decisions,
    )
