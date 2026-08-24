"""Staged V4.2C OMPL planner-portfolio runner (V4-237).

The request matrix is frozen before any child is launched. Resume skips only
exact completed request digests. Failed attempts are retained. Audit mode
requires a frozen calibration-selection file matching the calibration digest.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from inequality_mechanisms.audits.v4_2b_artifact import verify_v4_2b_artifact
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    REPO_ROOT,
    canonical_v4_2b_retained_root,
    prepare_v4_2c_output_dir,
    v4_2b_git_tracked_package_digest,
)
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import (
    PROBLEM_SOURCE_V4_2B,
    SCHEMA_ID,
    STATUS_CHILD_CRASH,
    STATUS_COMPLETED,
    invoke_ompl_worker,
    request_digest,
    write_atomic_json,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    CALIBRATION_SELECTION_SCHEMA,
    CONTROL_PLANNER_IDS,
    OmplPlannerPortfolioConfig,
    PlannerSpec,
    V4OmplPortfolioConfigError,
    load_ompl_portfolio_config,
)

MATRIX_SCHEMA = "v4.2c.ompl_planner_portfolio.request_matrix.v1"
ROW_SCHEMA = "v4.2c.ompl_planner_portfolio.row.v1"
PROGRESS_SCHEMA = "v4.2c.ompl_planner_portfolio.progress.v1"
WorkerInvoker = Callable[..., dict[str, Any]]


class V4OmplPortfolioRunnerError(RuntimeError):
    """Raised when the staged portfolio runner refuses to proceed."""


def assert_v4_2b_source_lock(config: OmplPlannerPortfolioConfig) -> dict[str, Any]:
    """Verify the frozen V4.2B closeout before any planning row is launched."""
    root = canonical_v4_2b_retained_root()
    summary = verify_v4_2b_artifact(root)
    git_sha, git_n = v4_2b_git_tracked_package_digest()
    source = config.source
    if git_sha != source.v4_2b_git_tracked_sha256:
        raise V4OmplPortfolioRunnerError(
            "V4.2B git-tracked digest mismatch: "
            f"live={git_sha} lock={source.v4_2b_git_tracked_sha256}"
        )
    if git_n != source.v4_2b_git_tracked_n_files:
        raise V4OmplPortfolioRunnerError(
            "V4.2B git-tracked file count mismatch: "
            f"live={git_n} lock={source.v4_2b_git_tracked_n_files}"
        )
    if summary["files_digest"] != source.v4_2b_files_digest:
        raise V4OmplPortfolioRunnerError(
            "V4.2B files_digest mismatch: "
            f"live={summary['files_digest']} lock={source.v4_2b_files_digest}"
        )
    if int(summary["n_files"]) != source.v4_2b_n_files:
        raise V4OmplPortfolioRunnerError(
            "V4.2B n_files mismatch: "
            f"live={summary['n_files']} lock={source.v4_2b_n_files}"
        )
    if int(summary["n_geometry_rows"]) != source.v4_2b_n_geometry_rows:
        raise V4OmplPortfolioRunnerError(
            "V4.2B n_geometry_rows mismatch: "
            f"live={summary['n_geometry_rows']} lock={source.v4_2b_n_geometry_rows}"
        )
    return summary


def assert_calibration_selection(
    config: OmplPlannerPortfolioConfig, *, repo_root: Path
) -> dict[str, Any]:
    """Refuse audit mode unless a matching frozen calibration selection exists."""
    if config.mode != "audit":
        return {}
    rel = config.calibration_selection_rel
    digest = config.calibration_config_digest
    if not rel or not digest:
        raise V4OmplPortfolioRunnerError(
            "audit mode requires calibration_selection_rel and "
            "calibration_config_digest"
        )
    path = repo_root / rel
    if not path.is_file():
        raise V4OmplPortfolioRunnerError(
            f"audit mode refused: missing calibration selection at {path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise V4OmplPortfolioRunnerError(
            f"invalid calibration selection JSON at {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise V4OmplPortfolioRunnerError("calibration selection must be a JSON object")
    if payload.get("schema_version") != CALIBRATION_SELECTION_SCHEMA:
        raise V4OmplPortfolioRunnerError(
            "calibration selection schema_version mismatch: "
            f"got {payload.get('schema_version')!r}"
        )
    if payload.get("calibration_config_digest") != digest:
        raise V4OmplPortfolioRunnerError(
            "calibration selection digest mismatch: "
            f"file={payload.get('calibration_config_digest')!r} "
            f"config={digest!r}"
        )
    return payload


def worker_request_for_row(
    config: OmplPlannerPortfolioConfig,
    *,
    case_id: str,
    task_id: str,
    mechanism: str,
    spec: PlannerSpec,
    repetition: int,
    seed: int,
) -> dict[str, Any]:
    """Build one process-worker request. Outcome fields are never included."""
    del config
    request: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "planner_id": spec.planner_id,
        "seed": int(seed),
        "problem_source": PROBLEM_SOURCE_V4_2B,
        "case_id": str(case_id),
        "task_id": str(task_id),
        "mechanism": str(mechanism),
        "repetition": int(repetition),
        "planner_params": dict(spec.worker_params()),
        "solve_time_s": float(spec.solve_time_s),
    }
    if spec.checkpoints_s is not None:
        request["checkpoints_s"] = list(spec.checkpoints_s)
    if spec.num_samples is not None:
        request["num_samples"] = int(spec.num_samples)
    return request


def build_request_matrix(config: OmplPlannerPortfolioConfig) -> dict[str, Any]:
    """Freeze the Cartesian request matrix before any child is launched."""
    rows: list[dict[str, Any]] = []
    row_index = 0
    for case_id in config.case_ids:
        for task_id in config.task_ids:
            for mechanism in config.mechanisms:
                for spec in config.enabled_required_planners():
                    n_rep = 1 if spec.role == "control" else int(config.repetitions)
                    if spec.planner_id in CONTROL_PLANNER_IDS:
                        n_rep = 1
                    for repetition in range(n_rep):
                        seed = int(config.seed_base) + row_index
                        request = worker_request_for_row(
                            config,
                            case_id=case_id,
                            task_id=task_id,
                            mechanism=mechanism,
                            spec=spec,
                            repetition=repetition,
                            seed=seed,
                        )
                        digest = request_digest(request)
                        rows.append(
                            {
                                "row_index": row_index,
                                "request_digest": digest,
                                "case_id": case_id,
                                "task_id": task_id,
                                "mechanism": mechanism,
                                "planner_id": spec.planner_id,
                                "role": spec.role,
                                "repetition": repetition,
                                "seed": seed,
                                "request": request,
                            }
                        )
                        row_index += 1
    return {
        "schema_version": MATRIX_SCHEMA,
        "config_digest": config.digest(),
        "mode": config.mode,
        "stage": config.stage_name(),
        "n_rows": len(rows),
        "rows": rows,
    }


def stage_directory(config: OmplPlannerPortfolioConfig, *, repo_root: Path) -> Path:
    """Return the guarded stage directory under the V4.2C output root."""
    output_root = prepare_v4_2c_output_dir(repo_root / config.output_dir)
    stage_dir = output_root / config.stage_name()
    stage_dir.mkdir(parents=True, exist_ok=True)
    return stage_dir


def row_is_complete(path: Path, expected_request: Mapping[str, Any]) -> bool:
    """Return True only when a retained row file satisfies the complete contract."""
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return _payload_is_complete(payload, expected_request)


def _payload_is_complete(
    payload: Mapping[str, Any], expected_request: Mapping[str, Any]
) -> bool:
    worker = payload.get("worker")
    if not isinstance(worker, dict):
        return False
    digest = request_digest(expected_request)
    return (
        payload.get("request_digest") == digest
        and worker.get("request_digest") == digest
        and worker.get("status") == STATUS_COMPLETED
        and isinstance(worker.get("result"), dict)
        and worker.get("planner_id") == expected_request.get("planner_id")
        and worker.get("seed") == expected_request.get("seed")
        and payload.get("case_id") == expected_request.get("case_id")
        and payload.get("task_id") == expected_request.get("task_id")
        and payload.get("mechanism") == expected_request.get("mechanism")
        and payload.get("planner_id") == expected_request.get("planner_id")
        and payload.get("repetition") == expected_request.get("repetition")
    )


def _write_resolved_config(stage_dir: Path, config: OmplPlannerPortfolioConfig) -> None:
    path = stage_dir / "resolved_config.json"
    payload = config.model_dump(mode="json")
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        existing_cfg = OmplPlannerPortfolioConfig.model_validate(existing)
        if existing_cfg.digest() != config.digest():
            raise V4OmplPortfolioRunnerError(
                f"config drift in {path}: existing={existing_cfg.digest()} "
                f"incoming={config.digest()}"
            )
        return
    write_atomic_json(path, payload)


def _write_or_check_matrix(stage_dir: Path, matrix: Mapping[str, Any]) -> None:
    path = stage_dir / "request_matrix.json"
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("config_digest") != matrix["config_digest"]:
            raise V4OmplPortfolioRunnerError(
                "request matrix config_digest drift in "
                f"{path}: existing={existing.get('config_digest')!r} "
                f"incoming={matrix['config_digest']!r}"
            )
        existing_digests = [row["request_digest"] for row in existing.get("rows", [])]
        incoming_digests = [row["request_digest"] for row in matrix["rows"]]
        if existing_digests != incoming_digests:
            raise V4OmplPortfolioRunnerError(
                "frozen request matrix mismatch; case/task replacement is refused"
            )
        return
    write_atomic_json(path, dict(matrix))


def _default_invoker(
    request: Mapping[str, Any], *, timeout_s: float, work_dir: Path
) -> dict[str, Any]:
    return invoke_ompl_worker(
        request,
        timeout_s=timeout_s,
        work_dir=work_dir,
        cwd=CANONICAL_REPO_ROOT,
    )


def _next_attempt_path(attempts_dir: Path, digest: str) -> Path:
    index = 0
    while True:
        path = attempts_dir / f"{digest}_{index:02d}.json"
        if not path.exists():
            return path
        index += 1


def _invoke_row(
    invoker: WorkerInvoker,
    request: Mapping[str, Any],
    *,
    timeout_s: float,
    work_dir: Path,
) -> dict[str, Any]:
    try:
        payload = invoker(request, timeout_s=timeout_s, work_dir=work_dir)
    except TypeError:
        payload = invoker(dict(request))
    except Exception as exc:  # noqa: BLE001 — child crash must stay typed
        return {
            "schema_id": SCHEMA_ID,
            "status": STATUS_CHILD_CRASH,
            "request_digest": request_digest(request),
            "planner_id": request.get("planner_id"),
            "seed": request.get("seed"),
            "result": None,
            "unavailable_reason": f"invoker_exception:{exc}",
        }
    if not isinstance(payload, dict):
        return {
            "schema_id": SCHEMA_ID,
            "status": STATUS_CHILD_CRASH,
            "request_digest": request_digest(request),
            "planner_id": request.get("planner_id"),
            "seed": request.get("seed"),
            "result": None,
            "unavailable_reason": "invoker_returned_non_object",
        }
    return payload


def run_ompl_planner_portfolio(
    config: OmplPlannerPortfolioConfig,
    *,
    worker_invoker: WorkerInvoker | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Run one frozen stage. Failed attempts are retained and never marked complete."""
    assert_v4_2b_source_lock(config)
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    assert_calibration_selection(config, repo_root=root)
    stage_dir = stage_directory(config, repo_root=root)
    _write_resolved_config(stage_dir, config)
    matrix = build_request_matrix(config)
    _write_or_check_matrix(stage_dir, matrix)
    rows_dir = stage_dir / "rows"
    attempts_dir = stage_dir / "attempts"
    work_root = stage_dir / "work"
    rows_dir.mkdir(parents=True, exist_ok=True)
    attempts_dir.mkdir(parents=True, exist_ok=True)
    invoker = worker_invoker if worker_invoker is not None else _default_invoker
    n_skipped = 0
    n_completed = 0
    n_failed = 0
    completed_digests: list[str] = []
    failed_digests: list[str] = []
    for row in matrix["rows"]:
        digest = str(row["request_digest"])
        request = dict(row["request"])
        row_path = rows_dir / f"{digest}.json"
        if row_is_complete(row_path, request):
            n_skipped += 1
            n_completed += 1
            completed_digests.append(digest)
            continue
        work_dir = work_root / digest
        work_dir.mkdir(parents=True, exist_ok=True)
        worker = _invoke_row(
            invoker,
            request,
            timeout_s=float(config.child_timeout_s),
            work_dir=work_dir,
        )
        record = {
            "schema_version": ROW_SCHEMA,
            "request_digest": digest,
            "case_id": row["case_id"],
            "task_id": row["task_id"],
            "mechanism": row["mechanism"],
            "planner_id": row["planner_id"],
            "repetition": row["repetition"],
            "seed": row["seed"],
            "request": request,
            "worker": worker,
        }
        if _payload_is_complete(record, request):
            write_atomic_json(row_path, record)
            n_completed += 1
            completed_digests.append(digest)
        else:
            write_atomic_json(_next_attempt_path(attempts_dir, digest), record)
            n_failed += 1
            failed_digests.append(digest)
        progress = {
            "schema_version": PROGRESS_SCHEMA,
            "config_digest": config.digest(),
            "n_rows": matrix["n_rows"],
            "n_completed": n_completed,
            "n_failed": n_failed,
            "n_skipped": n_skipped,
            "completed_digests": list(completed_digests),
            "failed_digests": list(failed_digests),
        }
        write_atomic_json(stage_dir / "progress.json", progress)
    summary = {
        "schema_version": PROGRESS_SCHEMA,
        "config_digest": config.digest(),
        "stage": config.stage_name(),
        "stage_dir": str(stage_dir),
        "n_rows": matrix["n_rows"],
        "n_completed": n_completed,
        "n_failed": n_failed,
        "n_skipped": n_skipped,
        "completed_digests": completed_digests,
        "failed_digests": failed_digests,
    }
    write_atomic_json(stage_dir / "progress.json", summary)
    return summary


def run_ompl_planner_portfolio_from_path(
    config_path: Path | str,
    *,
    worker_invoker: WorkerInvoker | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Load a frozen JSON config and run the corresponding stage."""
    try:
        config = load_ompl_portfolio_config(config_path)
    except V4OmplPortfolioConfigError as exc:
        raise V4OmplPortfolioRunnerError(str(exc)) from exc
    return run_ompl_planner_portfolio(
        config, worker_invoker=worker_invoker, repo_root=repo_root
    )
