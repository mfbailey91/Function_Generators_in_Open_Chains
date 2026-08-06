from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import yaml

from inequality_mechanisms.experiments import v2_cartesian_goal_region as runner_module
from inequality_mechanisms.experiments.v2_cartesian_goal_region import (
    load_cartesian_goal_region_config,
    run_cartesian_goal_region,
)
from inequality_mechanisms.experiments.v2_cartesian_tasks import CartesianPositionTask
from inequality_mechanisms.experiments.v2_runner import (
    build_graphs,
    build_mechanism_branches,
)
from inequality_mechanisms.kinematics.planar_2r import Planar2R


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SMOKE_CONFIG = _REPO_ROOT / "configs/v2/cartesian_goal_region_smoke.yaml"


def test_repository_smoke_yaml_loads_without_duplicate_semantics() -> None:
    config = load_cartesian_goal_region_config(_SMOKE_CONFIG)
    assert config.solver_policy == "smoke_oracle_pair_v1"
    assert config.algorithms == ("dijkstra", "astar")
    assert config.base_experiment.objective.cost == "actuator_travel"
    assert not {"tasks", "algorithms", "objective", "trials", "seed"}.intersection(
        config.base_experiment_source
    )


def test_loader_rejects_duplicate_base_solver_or_task_fields(tmp_path: Path) -> None:
    raw = yaml.safe_load(_SMOKE_CONFIG.read_text(encoding="utf-8"))
    raw["base_experiment"]["algorithms"] = ["dijkstra"]
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    try:
        load_cartesian_goal_region_config(path)
    except ValueError as exc:
        assert "Experiment-B-irrelevant schema fields" in str(exc)
    else:
        raise AssertionError("duplicate base solver semantics were accepted")


def test_bounded_smoke_runner_writes_paired_dijkstra_astar_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    config = load_cartesian_goal_region_config(_SMOKE_CONFIG)
    branches = build_mechanism_branches(config.base_experiment)
    graphs = build_graphs(config.base_experiment, branches)
    reference_graph = next(iter(graphs.values()))
    fk = Planar2R(config.domain.L1, config.domain.L2)

    candidates: list[tuple[int, np.ndarray]] = []
    for node_id in range(reference_graph.node_count):
        if not reference_graph.node_is_valid(node_id):
            continue
        x = fk.forward(reference_graph.q_state(node_id))
        if config.domain.contains(x):
            candidates.append((node_id, x))
    assert candidates
    start_id, start_x = candidates[0]
    goal_id, goal_x = max(
        candidates,
        key=lambda item: float(np.linalg.norm(item[1] - start_x)),
    )
    assert start_id != goal_id
    assert np.linalg.norm(goal_x - start_x) > config.domain.min_start_goal_separation

    task = CartesianPositionTask(
        task_id="integration_task",
        requested_start_x=np.asarray(start_x, dtype=np.float64),
        requested_goal_x=np.asarray(goal_x, dtype=np.float64),
    )
    monkeypatch.setattr(
        runner_module,
        "generate_cartesian_task_bank",
        lambda _domain, *, n_tasks, seed: (task,),
    )

    result = run_cartesian_goal_region(config, results_root=tmp_path)
    assert result.n_tasks == 1
    assert result.n_failure_rows == 0
    assert result.n_trial_rows == 4

    trial_rows = [
        json.loads(line)
        for line in (result.path / "trials.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {row["algorithm"] for row in trial_rows} == {"dijkstra", "astar"}
    assert all(row["selected_goal_node_id"] is not None for row in trial_rows)
    assert all(row["start_attachment_policy"] for row in trial_rows)

    emitted_config = json.loads(
        (result.path / "config.json").read_text(encoding="utf-8")
    )
    assert emitted_config["solver_policy"] == "smoke_oracle_pair_v1"
    assert "tasks" not in emitted_config["base_experiment"]
    assert emitted_config["v2_schema_adapter"]["purpose"] == (
        "graph_builder_compatibility_only"
    )
