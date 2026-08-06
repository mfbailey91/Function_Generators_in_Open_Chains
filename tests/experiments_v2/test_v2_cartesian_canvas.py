"""Experiment B Cartesian HTML printout tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from inequality_mechanisms.experiments import v2_cartesian_goal_region as runner_module
from inequality_mechanisms.experiments.v2_cartesian_calibration import (
    CartesianCalibrationSettings,
    run_cartesian_calibration_sweep,
    write_cartesian_calibration_decisions,
)
from inequality_mechanisms.experiments.v2_cartesian_canvas import (
    CartesianCanvasError,
    is_cartesian_goal_region_run_dir,
    resolve_cartesian_run_for_canvas,
    write_cartesian_canvas,
)
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


_REPO = Path(__file__).resolve().parents[2]
_SMOKE = _REPO / "configs/v2/cartesian_goal_region_smoke.yaml"
_CALIB = _REPO / "configs/v2/cartesian_goal_region_calibration.yaml"


def test_smoke_runner_writes_index_html(tmp_path: Path, monkeypatch) -> None:
    config = load_cartesian_goal_region_config(_SMOKE)
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
    start_id, start_x = candidates[0]
    goal_id, goal_x = max(
        candidates, key=lambda item: float(np.linalg.norm(item[1] - start_x))
    )
    assert start_id != goal_id
    task = CartesianPositionTask(
        task_id="canvas_task",
        requested_start_x=np.asarray(start_x, dtype=np.float64),
        requested_goal_x=np.asarray(goal_x, dtype=np.float64),
    )
    monkeypatch.setattr(
        runner_module,
        "generate_cartesian_task_bank",
        lambda _domain, *, n_tasks, seed: (task,),
    )
    result = run_cartesian_goal_region(
        config, results_root=tmp_path, run_id="eb_smoke_canvas"
    )
    canvas = result.path / "index.html"
    assert canvas.is_file()
    text = canvas.read_text(encoding="utf-8")
    assert "Experiment B smoke" in text
    assert "Dijkstra/A*" in text
    assert result.run_id in text


def test_calibration_canvas_regenerate_does_not_mutate_candidates(
    tmp_path: Path,
) -> None:
    raw = yaml.safe_load(_CALIB.read_text(encoding="utf-8"))
    raw["task_count"] = 3
    raw["calibration"] = {
        "candidate_resolutions": [16, 24],
        "candidate_goal_radii": [0.10, 0.12],
        "min_attachment_rate": 0.05,
        "run_search": False,
    }
    path = tmp_path / "calib.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    config = load_cartesian_goal_region_config(path)
    result = run_cartesian_goal_region(
        config, results_root=tmp_path / "runs", run_id="eb_calib_canvas"
    )
    candidates_path = result.path / "candidate_rows.jsonl"
    before = candidates_path.read_bytes()
    out = write_cartesian_canvas(result.path)
    after = candidates_path.read_bytes()
    assert before == after
    text = out.read_text(encoding="utf-8")
    assert "Experiment B calibration" in text
    assert "Calibration decisions" in text
    assert "cartesian_radius_decision.json" in text


def test_resolve_rejects_non_experiment_b(tmp_path: Path) -> None:
    bogus = tmp_path / "not_eb"
    bogus.mkdir()
    (bogus / "manifest.json").write_text(
        '{"architecture_version": 2, "run_id": "x"}\n', encoding="utf-8"
    )
    assert not is_cartesian_goal_region_run_dir(bogus)
    with pytest.raises(CartesianCanvasError, match="not an Experiment B"):
        resolve_cartesian_run_for_canvas(bogus)


def test_write_canvas_for_fixture_decisions_package(tmp_path: Path) -> None:
    smoke = load_cartesian_goal_region_config(_SMOKE)
    settings = CartesianCalibrationSettings(
        candidate_resolutions=(16,),
        candidate_goal_radii=(0.12,),
        min_attachment_rate=0.01,
        run_search=False,
    )
    sweep = run_cartesian_calibration_sweep(
        base_experiment=smoke.base_experiment,
        domain=smoke.domain,
        settings=settings,
        task_count=2,
        seed=3,
    )
    run_dir = tmp_path / "calib_fixture"
    run_dir.mkdir()
    write_cartesian_calibration_decisions(
        run_dir,
        radius_decision=sweep["cartesian_radius_decision"],
        resolution_decision=sweep["cartesian_resolution_decision"],
        start_attachment_decision=sweep["cartesian_start_attachment_decision"],
    )
    (run_dir / "candidate_rows.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in sweep["candidate_rows"]),
        encoding="utf-8",
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "calib_fixture",
                "experiment_id": "experiment_b_cartesian_goal_region_calibration",
                "experiment_b_schema_version": 1,
                "stage": "calibration",
                "solver_policy": "calibration_dijkstra_v1",
                "algorithms": ["dijkstra"],
                "cartesian_domain": smoke.domain.to_dict(),
                "chosen": sweep["chosen"],
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    out = write_cartesian_canvas(run_dir)
    text = out.read_text(encoding="utf-8")
    assert any(
        token in text
        for token in ("fallback", "coarsest", "single_candidate", "shape_n")
    )
