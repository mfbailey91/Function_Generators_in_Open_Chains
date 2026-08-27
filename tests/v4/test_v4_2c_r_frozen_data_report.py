"""V4.2C-R frozen-data report clarification tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits import v4_artifact_guard as guard
from inequality_mechanisms.audits.v4_artifact_guard import (
    ArtifactPathForbiddenError,
    canonical_v4_2c_retained_root,
)
from inequality_mechanisms.benchmarks.classification import TASK_ALREADY_SATISFIED
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import (
    STATUS_COMPLETED,
    write_atomic_json,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio import (
    MATRIX_SCHEMA,
    PROGRESS_SCHEMA,
    ROW_SCHEMA,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    DEFAULT_SMOKE_CONFIG_REL,
    load_ompl_portfolio_config,
)
from inequality_mechanisms.visualization.v4 import (
    ompl_planner_portfolio_clarification as clarification,
)
from inequality_mechanisms.visualization.v4.ompl_planner_portfolio import (
    extract_row_view,
    href_targets,
    write_ompl_planner_portfolio_report,
)

CASE_ID = "span_j1_145_j2_145"
NEAR = "near_0"
FAR = "far_0"
FOURBAR = "fourbar"
GEARBOX = "gearbox"
RRTSTAR = "ompl_rrt_star"
BITSTAR = "ompl_bit_star"
KPIECE_U = "ompl_kpiece_u"
KPIECE_Q = "ompl_kpiece_q"
KPIECE_X = "ompl_kpiece_x"
ALREADY_DIGEST = "a" * 64


def _completed_worker(
    *,
    planner_id: str,
    digest: str,
    objective_cost: float,
    task_class: str = "direct/local feasible",
    first_cost: float | None = None,
    checkpoints: list[dict] | None = None,
    goal_id: str = "g0",
    vertices: int = 12,
    first_time: float = 0.1,
    trajectory: list[dict] | None = None,
) -> dict:
    extras: dict = {
        "family_metrics": {
            "unavailable_reason": "kpiece_cell_stats_not_exposed_by_binding"
        }
    }
    if first_cost is not None:
        extras["first_exact_time_s"] = first_time
        extras["first_exact_cost"] = first_cost
    states = trajectory or [
        {"u": [0.0, 0.0], "q": [0.1, 0.0], "x": [0.2, 0.0]},
        {"u": [0.4, 0.2], "q": [0.3, 0.1], "x": [0.5, 0.2]},
    ]
    return {
        "status": STATUS_COMPLETED,
        "request_digest": digest,
        "planner_id": planner_id,
        "result": {
            "status": STATUS_COMPLETED,
            "task_class": task_class,
            "trajectory": {"states": states},
            "selected_goal_candidate": {"provenance": {"candidate_id": goal_id}},
            "objective_cost": objective_cost,
            "path_length_u": objective_cost,
            "path_length_q": objective_cost * 0.8,
            "path_length_x": objective_cost * 0.5,
            "planner_metrics": {
                "ompl": {
                    "num_vertices": vertices,
                    "num_edges": vertices * 2,
                    "checkpoints": checkpoints or [],
                }
            },
            "provenance": {"extras": extras},
        },
    }


def _row(
    *,
    digest: str,
    planner_id: str,
    mechanism: str,
    task_id: str,
    worker: dict,
    role: str,
) -> dict:
    return {
        "schema_version": ROW_SCHEMA,
        "request_digest": digest,
        "case_id": CASE_ID,
        "task_id": task_id,
        "mechanism": mechanism,
        "planner_id": planner_id,
        "repetition": 0,
        "seed": 7,
        "role": role,
        "request": {"planner_id": planner_id},
        "worker": worker,
    }


def _write_stage(tmp_path: Path) -> Path:
    stage = tmp_path / guard.V4_2C_ALLOWED_OUTPUT_REL / "stage_c"
    (stage / "rows").mkdir(parents=True, exist_ok=True)
    config = load_ompl_portfolio_config(DEFAULT_SMOKE_CONFIG_REL)
    write_atomic_json(stage / "resolved_config.json", config.model_dump(mode="json"))
    checkpoints = [
        {"checkpoint_s": 0.1, "ompl_exact_solution": True, "best_cost": 2.4},
        {"checkpoint_s": 0.5, "ompl_exact_solution": True, "best_cost": 1.1},
    ]
    matrix_rows: list[dict] = []
    n = 0

    def next_digest() -> str:
        nonlocal n
        n += 1
        return f"{n:064x}"

    def add_row(
        planner_id: str,
        mechanism: str,
        task_id: str,
        role: str,
        **kwargs: object,
    ) -> str:
        token = str(kwargs.pop("digest")) if "digest" in kwargs else next_digest()
        record = _row(
            digest=token,
            planner_id=planner_id,
            mechanism=mechanism,
            task_id=task_id,
            role=role,
            worker=_completed_worker(planner_id=planner_id, digest=token, **kwargs),
        )
        write_atomic_json(stage / "rows" / f"{token}.json", record)
        matrix_rows.append(
            {
                "request_digest": token,
                "case_id": CASE_ID,
                "task_id": task_id,
                "mechanism": mechanism,
                "planner_id": planner_id,
                "repetition": 0,
                "seed": 7,
                "role": role,
                "request": {"planner_id": planner_id},
            }
        )
        return token

    add_row(
        RRTSTAR,
        FOURBAR,
        NEAR,
        "primary",
        digest=ALREADY_DIGEST,
        objective_cost=0.0,
        task_class=TASK_ALREADY_SATISFIED,
        first_cost=0.0,
        checkpoints=[],
        vertices=0,
        trajectory=[{"u": [0.0, 0.0], "q": [0.0, 0.0], "x": [0.0, 0.0]}],
    )
    add_row(
        RRTSTAR,
        FOURBAR,
        NEAR,
        "primary",
        objective_cost=1.10,
        first_cost=2.40,
        checkpoints=checkpoints,
        vertices=20,
        goal_id="g0",
    )
    add_row(
        RRTSTAR,
        GEARBOX,
        NEAR,
        "primary",
        objective_cost=1.30,
        first_cost=2.50,
        checkpoints=checkpoints,
        vertices=18,
        goal_id="g1",
    )
    add_row(
        RRTSTAR,
        FOURBAR,
        FAR,
        "primary",
        objective_cost=1.40,
        first_cost=2.80,
        checkpoints=checkpoints,
        vertices=22,
        goal_id="g2",
    )
    add_row(
        RRTSTAR,
        GEARBOX,
        FAR,
        "primary",
        objective_cost=1.55,
        first_cost=2.90,
        checkpoints=checkpoints,
        vertices=21,
        goal_id="g2",
    )
    add_row(
        BITSTAR,
        FOURBAR,
        FAR,
        "primary",
        objective_cost=1.20,
        first_cost=2.10,
        checkpoints=checkpoints,
        vertices=16,
        goal_id="g0",
    )
    add_row(
        BITSTAR,
        GEARBOX,
        FAR,
        "primary",
        objective_cost=1.25,
        first_cost=2.20,
        checkpoints=checkpoints,
        vertices=15,
        goal_id="g3",
    )
    add_row(
        KPIECE_U,
        FOURBAR,
        FAR,
        "projection",
        objective_cost=1.45,
        first_cost=1.70,
        vertices=30,
    )
    add_row(
        KPIECE_Q,
        FOURBAR,
        FAR,
        "projection",
        objective_cost=1.48,
        first_cost=1.72,
        vertices=28,
    )
    add_row(
        KPIECE_X,
        FOURBAR,
        FAR,
        "projection",
        objective_cost=1.50,
        first_cost=1.74,
        vertices=27,
    )
    add_row(
        KPIECE_U,
        GEARBOX,
        FAR,
        "projection",
        objective_cost=1.60,
        first_cost=1.80,
        vertices=29,
    )
    add_row(
        KPIECE_Q,
        GEARBOX,
        FAR,
        "projection",
        objective_cost=1.62,
        first_cost=1.82,
        vertices=26,
    )
    add_row(
        KPIECE_X,
        GEARBOX,
        FAR,
        "projection",
        objective_cost=1.64,
        first_cost=1.84,
        vertices=25,
    )

    write_atomic_json(
        stage / "request_matrix.json",
        {
            "schema_version": MATRIX_SCHEMA,
            "config_digest": config.digest(),
            "mode": config.mode,
            "stage": config.stage_name(),
            "n_rows": len(matrix_rows),
            "rows": matrix_rows,
        },
    )
    write_atomic_json(
        stage / "progress.json",
        {
            "schema_version": PROGRESS_SCHEMA,
            "config_digest": config.digest(),
            "n_rows": len(matrix_rows),
            "n_completed": len(matrix_rows),
            "n_failed": 0,
            "n_skipped": 0,
            "completed_digests": [item["request_digest"] for item in matrix_rows],
            "failed_digests": [],
        },
    )
    return stage


@pytest.fixture
def synthetic_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    stage = _write_stage(tmp_path)
    output = tmp_path / guard.V4_2C_R_ALLOWED_OUTPUT_REL
    return stage, output


def test_extract_row_view_exposes_task_class(
    synthetic_roots: tuple[Path, Path],
) -> None:
    stage, _output = synthetic_roots
    already = json.loads((stage / "rows" / f"{ALREADY_DIGEST}.json").read_text())
    view = extract_row_view(already)
    assert view["task_class"] == TASK_ALREADY_SATISFIED


def test_already_satisfied_excluded_from_executive_figures(
    synthetic_roots: tuple[Path, Path],
) -> None:
    stage, output = synthetic_roots
    payload = clarification.write_ompl_planner_portfolio_clarification(
        stage, output_dir=output
    )
    summary = json.loads(Path(payload["summary_path"]).read_text(encoding="utf-8"))
    assert summary["counts"]["n_already_satisfied"] == 1
    assert summary["counts"]["n_nontrivial"] >= 1
    executive_ids = {
        "optimizer_convergence_rrt_star",
        "optimizer_convergence_bit_star",
        "paired_mechanism_delta_distribution",
        "first_to_final_improvement",
    }
    for figure in summary["figures"]:
        if figure["id"] in executive_ids:
            assert ALREADY_DIGEST not in figure["row_digests"]
        assert int(figure["n_x_categories"]) <= clarification.MAX_X_CATEGORIES


def test_figure_labels_identify_grouping(synthetic_roots: tuple[Path, Path]) -> None:
    stage, output = synthetic_roots
    payload = clarification.write_ompl_planner_portfolio_clarification(
        stage, output_dir=output
    )
    html = Path(payload["index_path"]).read_text(encoding="utf-8")
    summary = json.loads(Path(payload["summary_path"]).read_text(encoding="utf-8"))
    assert "Sprint V4.2C is closed" in html
    assert html.find('id="lede"') < html.find("<h1>")
    assert "already satisfied" in html.lower() or "Already satisfied" in html
    assert CASE_ID in html
    assert RRTSTAR in html
    assert FOURBAR in html
    assert GEARBOX in html
    ids = {item["id"] for item in summary["figures"]}
    assert "kpiece_projection_occupancy" not in ids
    assert "kpiece_projection_diagnostic" in ids
    assert "final_planner_data_size_vs_solution_time" in ids
    assert "planner_data_growth" not in ids
    assert "kpiece_cell_stats_not_exposed_by_binding" in html
    assert "occupancy heatmap" not in html.lower() or "not scientific" in html.lower()


def test_kpiece_is_not_occupancy_heatmap(synthetic_roots: tuple[Path, Path]) -> None:
    stage, output = synthetic_roots
    payload = clarification.write_ompl_planner_portfolio_clarification(
        stage, output_dir=output
    )
    html = Path(payload["index_path"]).read_text(encoding="utf-8")
    assert "kpiece_projection_occupancy.png" not in html
    assert "kpiece_projection_diagnostic.png" in html


def test_uqx_example_is_paired_and_nontrivial(
    synthetic_roots: tuple[Path, Path],
) -> None:
    stage, output = synthetic_roots
    payload = clarification.write_ompl_planner_portfolio_clarification(
        stage, output_dir=output
    )
    summary = json.loads(Path(payload["summary_path"]).read_text(encoding="utf-8"))
    example = summary["uqx_example"]
    assert example is not None
    assert example["case_id"] == CASE_ID
    assert example["task_id"] == FAR
    assert set(example["arms"]) == {FOURBAR, GEARBOX}
    for arm in example["arms"].values():
        assert arm["request_digest"] != ALREADY_DIGEST
        assert arm["path_length_u"] not in (0, 0.0)


def test_href_integrity_and_forbidden_tokens(
    synthetic_roots: tuple[Path, Path],
) -> None:
    stage, output = synthetic_roots
    payload = clarification.write_ompl_planner_portfolio_clarification(
        stage, output_dir=output
    )
    index = Path(payload["index_path"])
    html = index.read_text(encoding="utf-8")
    missing = [path for path in href_targets(index) if not path.exists()]
    assert missing == []
    assert "winner" not in html.lower()
    assert payload["source_files_digest"] == clarification.FROZEN_V4_2C_FILES_DIGEST


def test_guard_refuses_frozen_v4_2c_and_v4_3(
    synthetic_roots: tuple[Path, Path],
) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        assert_v4_2c_r_output_allowed,
    )

    _stage, output = synthetic_roots
    assert assert_v4_2c_r_output_allowed(output) == output.resolve()
    frozen = output.parent / guard.V4_2C_ALLOWED_PACKAGE / "stage_c" / "rows" / "x.json"
    with pytest.raises(ArtifactPathForbiddenError, match="frozen V4.2C"):
        assert_v4_2c_r_output_allowed(frozen)
    v43 = output.parent / "v4_3_intrinsic_static_wrench"
    with pytest.raises(ArtifactPathForbiddenError, match="unauthorized V4 package"):
        assert_v4_2c_r_output_allowed(v43)


def test_v4_2c_files_digest_lock_unchanged() -> None:
    manifest = canonical_v4_2c_retained_root() / "manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["files_digest"] == clarification.FROZEN_V4_2C_FILES_DIGEST


def test_historical_v4_238_writer_still_runs(
    synthetic_roots: tuple[Path, Path],
) -> None:
    stage, _output = synthetic_roots
    payload = write_ompl_planner_portfolio_report(stage)
    assert Path(payload["index_path"]).is_file()
