"""V4-237: frozen portfolio configs, staged runner, digest-locked resume."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits import v4_artifact_guard as guard
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import (
    STATUS_CHILD_CRASH,
    STATUS_COMPLETED,
    request_digest,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio import (
    V4OmplPortfolioRunnerError,
    assert_calibration_selection,
    build_request_matrix,
    run_ompl_planner_portfolio,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    CALIBRATION_SELECTION_SCHEMA,
    DEFAULT_AUDIT_CONFIG_REL,
    DEFAULT_CALIBRATION_CONFIG_REL,
    DEFAULT_SMOKE_CONFIG_REL,
    OmplPlannerPortfolioConfig,
    V4OmplPortfolioConfigError,
    load_ompl_portfolio_config,
)

SMOKE_ROW_COUNT = 32
CALIBRATION_ROW_COUNT = 768
AUDIT_ROW_COUNT = 6200


def _complete_worker(request: dict) -> dict:
    return {
        "schema_id": request.get("schema_id"),
        "status": STATUS_COMPLETED,
        "request_digest": request_digest(request),
        "planner_id": request["planner_id"],
        "seed": request["seed"],
        "result": {"ok": True},
    }


def _crash_worker(request: dict) -> dict:
    return {
        "schema_id": request.get("schema_id"),
        "status": STATUS_CHILD_CRASH,
        "request_digest": request_digest(request),
        "planner_id": request["planner_id"],
        "seed": request["seed"],
        "result": None,
        "unavailable_reason": "injected_crash",
    }


def test_committed_configs_load_and_matrix_counts_are_frozen() -> None:
    smoke = load_ompl_portfolio_config(DEFAULT_SMOKE_CONFIG_REL)
    calibration = load_ompl_portfolio_config(DEFAULT_CALIBRATION_CONFIG_REL)
    audit = load_ompl_portfolio_config(DEFAULT_AUDIT_CONFIG_REL)
    assert smoke.mode == "smoke"
    assert calibration.mode == "calibration"
    assert audit.mode == "audit"
    assert build_request_matrix(smoke)["n_rows"] == SMOKE_ROW_COUNT
    assert build_request_matrix(calibration)["n_rows"] == CALIBRATION_ROW_COUNT
    assert build_request_matrix(audit)["n_rows"] == AUDIT_ROW_COUNT
    first = build_request_matrix(smoke)
    second = build_request_matrix(smoke)
    assert [row["request_digest"] for row in first["rows"]] == [
        row["request_digest"] for row in second["rows"]
    ]


def test_control_planners_have_one_repetition_in_calibration() -> None:
    config = load_ompl_portfolio_config(DEFAULT_CALIBRATION_CONFIG_REL)
    matrix = build_request_matrix(config)
    by_planner: dict[str, int] = {}
    for row in matrix["rows"]:
        by_planner[row["planner_id"]] = by_planner.get(row["planner_id"], 0) + 1
    n_units = len(config.case_ids) * len(config.task_ids) * len(config.mechanisms)
    assert by_planner["ompl_prm"] == n_units
    assert by_planner["ompl_rrt_connect"] == n_units
    assert by_planner["ompl_rrt_star"] == n_units * config.repetitions


def test_strict_schema_rejects_unknown_and_forbidden_keys(
    tmp_path: Path,
) -> None:
    raw = json.loads(Path(DEFAULT_SMOKE_CONFIG_REL).read_text(encoding="utf-8"))
    raw["winner_table"] = True
    with pytest.raises(Exception):
        OmplPlannerPortfolioConfig.model_validate(raw)
    raw = json.loads(Path(DEFAULT_SMOKE_CONFIG_REL).read_text(encoding="utf-8"))
    raw["gravity"] = 9.8
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(V4OmplPortfolioConfigError, match="gravity"):
        load_ompl_portfolio_config(path)


def test_v4_2b_digest_mismatch_fails_before_planning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_ompl_portfolio_config(DEFAULT_SMOKE_CONFIG_REL)
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    called = {"n": 0}

    def boom(*_args: object, **_kwargs: object) -> dict:
        return {
            "files_digest": "0" * 64,
            "n_files": 23,
            "n_geometry_rows": 55539,
        }

    monkeypatch.setattr(
        "inequality_mechanisms.experiments.v4.ompl_planner_portfolio.verify_v4_2b_artifact",
        boom,
    )

    def invoker(request: dict, **_kwargs: object) -> dict:
        called["n"] += 1
        return _complete_worker(request)

    with pytest.raises(V4OmplPortfolioRunnerError, match="files_digest"):
        run_ompl_planner_portfolio(
            config, worker_invoker=invoker, repo_root=tmp_path
        )
    assert called["n"] == 0


def test_smoke_runner_writes_stage_a_and_resumes_by_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    config = load_ompl_portfolio_config(DEFAULT_SMOKE_CONFIG_REL)
    calls: list[str] = []

    def invoker(request: dict, **_kwargs: object) -> dict:
        calls.append(request_digest(request))
        return _complete_worker(request)

    first = run_ompl_planner_portfolio(
        config, worker_invoker=invoker, repo_root=tmp_path
    )
    assert first["n_rows"] == SMOKE_ROW_COUNT
    assert first["n_completed"] == SMOKE_ROW_COUNT
    assert first["n_failed"] == 0
    assert len(calls) == SMOKE_ROW_COUNT
    stage_dir = Path(first["stage_dir"])
    assert stage_dir.name == "stage_a"
    assert (stage_dir / "resolved_config.json").is_file()
    assert (stage_dir / "request_matrix.json").is_file()
    matrix = json.loads((stage_dir / "request_matrix.json").read_text(encoding="utf-8"))
    assert matrix["n_rows"] == SMOKE_ROW_COUNT
    case_ids = {row["case_id"] for row in matrix["rows"]}
    assert case_ids == set(config.case_ids)

    second = run_ompl_planner_portfolio(
        config, worker_invoker=invoker, repo_root=tmp_path
    )
    assert second["n_skipped"] == SMOKE_ROW_COUNT
    assert len(calls) == SMOKE_ROW_COUNT


def test_failed_child_is_retained_and_not_marked_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    config = load_ompl_portfolio_config(DEFAULT_SMOKE_CONFIG_REL)
    crash_planner = "ompl_fmt"

    def invoker(request: dict, **_kwargs: object) -> dict:
        if request["planner_id"] == crash_planner:
            return _crash_worker(request)
        return _complete_worker(request)

    summary = run_ompl_planner_portfolio(
        config, worker_invoker=invoker, repo_root=tmp_path
    )
    assert summary["n_failed"] > 0
    assert summary["n_completed"] + summary["n_failed"] == SMOKE_ROW_COUNT
    stage_dir = Path(summary["stage_dir"])
    matrix = json.loads((stage_dir / "request_matrix.json").read_text(encoding="utf-8"))
    assert {row["case_id"] for row in matrix["rows"]} == set(config.case_ids)
    row_files = list((stage_dir / "rows").glob("*.json"))
    attempt_files = list((stage_dir / "attempts").glob("*.json"))
    assert attempt_files
    completed_planners = {
        json.loads(path.read_text(encoding="utf-8"))["planner_id"] for path in row_files
    }
    assert crash_planner not in completed_planners
    for path in attempt_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["worker"]["status"] != STATUS_COMPLETED
        assert payload["worker"]["result"] is None


def test_config_drift_inside_output_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    config = load_ompl_portfolio_config(DEFAULT_SMOKE_CONFIG_REL)

    def invoker(request: dict, **_kwargs: object) -> dict:
        return _complete_worker(request)

    run_ompl_planner_portfolio(config, worker_invoker=invoker, repo_root=tmp_path)
    drifted = config.model_copy(update={"seed_base": config.seed_base + 1})
    with pytest.raises(V4OmplPortfolioRunnerError, match="drift"):
        run_ompl_planner_portfolio(
            drifted, worker_invoker=invoker, repo_root=tmp_path
        )


def test_audit_refuses_without_matching_calibration_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    config = load_ompl_portfolio_config(DEFAULT_AUDIT_CONFIG_REL)
    with pytest.raises(V4OmplPortfolioRunnerError, match="calibration selection"):
        assert_calibration_selection(config, repo_root=tmp_path)
    rel = config.calibration_selection_rel
    assert rel is not None
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": CALIBRATION_SELECTION_SCHEMA,
                "calibration_config_digest": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(V4OmplPortfolioRunnerError, match="digest"):
        assert_calibration_selection(config, repo_root=tmp_path)
    path.write_text(
        json.dumps(
            {
                "schema_version": CALIBRATION_SELECTION_SCHEMA,
                "calibration_config_digest": config.calibration_config_digest,
            }
        ),
        encoding="utf-8",
    )
    payload = assert_calibration_selection(config, repo_root=tmp_path)
    assert payload["calibration_config_digest"] == config.calibration_config_digest
