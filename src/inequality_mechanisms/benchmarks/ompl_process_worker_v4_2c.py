"""Fresh-process OMPL worker for Sprint V4.2C (V4-235).

Stochastic evidence rows go through this child. A truncated tempfile is never
the completed ``--out`` path. In-process multi-repetition seed reproducibility
is not claimed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields
from pathlib import Path
from typing import Any, Final

SCHEMA_ID: Final = "v4.2c.ompl_worker_request.v1"
PROBLEM_SOURCE_SMOKE: Final = "smoke_sampling_2r"
REQUIRED_PLANNER_IDS: Final[tuple[str, ...]] = (
    "ompl_prm",
    "ompl_rrt_connect",
    "ompl_rrt_star",
    "ompl_bit_star",
    "ompl_fmt",
    "ompl_kpiece_u",
    "ompl_kpiece_q",
    "ompl_kpiece_x",
)
OPTIONAL_PLANNER_IDS: Final[frozenset[str]] = frozenset({"ompl_pdst_u"})
CHECKPOINT_PLANNER_IDS: Final[frozenset[str]] = frozenset(
    {"ompl_rrt_star", "ompl_bit_star"}
)
ONESHOT_PLANNER_IDS: Final[frozenset[str]] = frozenset(
    {
        "ompl_prm",
        "ompl_rrt_connect",
        "ompl_kpiece_u",
        "ompl_kpiece_q",
        "ompl_kpiece_x",
    }
)
KPIECE_PROJECTION_BY_ID: Final[dict[str, str]] = {
    "ompl_kpiece_u": "normalized_u",
    "ompl_kpiece_q": "normalized_mounted_q",
    "ompl_kpiece_x": "normalized_cartesian_x",
}
DEFAULT_SAMPLER: Final[frozenset[str]] = frozenset(
    {"", "default", "uniform", "uniform_raw_u", "Uniform"}
)
STATUS_COMPLETED: Final = "completed"
STATUS_UNSUPPORTED_OPTIONAL: Final = "unsupported_optional"
STATUS_REJECTED: Final = "rejected"
STATUS_CHILD_TIMEOUT: Final = "child_timeout"
STATUS_CHILD_CRASH: Final = "child_crash"

PlannerFactory = Callable[[dict[str, Any]], Any]


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Serialize ``payload`` with sorted keys for digest stability."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def request_digest(request: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical request JSON."""
    return hashlib.sha256(canonical_json(request).encode("utf-8")).hexdigest()


def write_atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write JSON via a tempfile and ``os.replace``.

    A truncated ``.tmp`` sibling is never the completed ``--out`` path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(
            json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _environment_record() -> dict[str, Any]:
    from inequality_mechanisms.adapters.ompl._availability import (
        is_ompl_available,
        ompl_version_string,
    )

    return {
        "python": sys.version,
        "platform": platform.platform(),
        "ompl_available": bool(is_ompl_available()),
        "ompl_version": ompl_version_string() if is_ompl_available() else None,
        "process_isolated": True,
    }


def _dataclass_kwargs(cls: type[Any], params: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {item.name for item in fields(cls)} - {"lifecycle", "trace_sink"}
    return {key: value for key, value in params.items() if key in allowed}


def _factory_prm(params: dict[str, Any]) -> Any:
    from inequality_mechanisms.adapters.ompl.prm import OmplPRMPlanner

    return OmplPRMPlanner(**_dataclass_kwargs(OmplPRMPlanner, params))


def _factory_rrt_connect(params: dict[str, Any]) -> Any:
    from inequality_mechanisms.adapters.ompl.rrt_connect import OmplRRTConnectPlanner

    return OmplRRTConnectPlanner(**_dataclass_kwargs(OmplRRTConnectPlanner, params))


def _factory_rrt_star(params: dict[str, Any]) -> Any:
    from inequality_mechanisms.adapters.ompl.rrt_star import OmplRRTStarPlanner

    return OmplRRTStarPlanner(**_dataclass_kwargs(OmplRRTStarPlanner, params))


def _factory_bit_star(params: dict[str, Any]) -> Any:
    from inequality_mechanisms.adapters.ompl.bit_star import OmplBITStarPlanner

    return OmplBITStarPlanner(**_dataclass_kwargs(OmplBITStarPlanner, params))


def _factory_fmt(params: dict[str, Any]) -> Any:
    from inequality_mechanisms.adapters.ompl.fmt import OmplFMTPlanner

    return OmplFMTPlanner(**_dataclass_kwargs(OmplFMTPlanner, params))


def _factory_kpiece(params: dict[str, Any]) -> Any:
    from inequality_mechanisms.adapters.ompl.kpiece import OmplKPIECEPlanner

    planner_id = str(params["planner_id"])
    kwargs = _dataclass_kwargs(OmplKPIECEPlanner, params)
    kwargs["projection"] = KPIECE_PROJECTION_BY_ID[planner_id]
    return OmplKPIECEPlanner(**kwargs)


PLANNER_FACTORIES: Final[dict[str, PlannerFactory]] = {
    "ompl_prm": _factory_prm,
    "ompl_rrt_connect": _factory_rrt_connect,
    "ompl_rrt_star": _factory_rrt_star,
    "ompl_bit_star": _factory_bit_star,
    "ompl_fmt": _factory_fmt,
    "ompl_kpiece_u": _factory_kpiece,
    "ompl_kpiece_q": _factory_kpiece,
    "ompl_kpiece_x": _factory_kpiece,
}


def _custom_sampler_requested(request: Mapping[str, Any]) -> bool:
    sampler = request.get("sampler")
    if sampler is None:
        sampler = (request.get("planner_params") or {}).get("sampler")
    if sampler is None:
        return False
    return str(sampler) not in DEFAULT_SAMPLER


def _checkpoints(request: Mapping[str, Any]) -> tuple[float, ...] | None:
    raw = request.get("checkpoints_s")
    if raw is None:
        raw = (request.get("planner_params") or {}).get("checkpoints_s")
    if raw is None:
        return None
    return tuple(float(t) for t in raw)


def _build_smoke_problem(request: Mapping[str, Any]) -> tuple[Any, Any]:
    from inequality_mechanisms.benchmarks.smoke_sampling_2r import (
        build_paired_arms,
        build_problem,
        smoke_task_catalog,
    )
    from inequality_mechanisms.kinematics.planar_2r_goals import (
        CartesianDiskGoalGenerator,
    )

    mechanism = str(request.get("mechanism", "fourbar"))
    task_kind = str(request.get("task_kind", "planning_feasible"))
    arms = build_paired_arms()
    if mechanism not in arms:
        raise ValueError(f"unknown smoke mechanism {mechanism!r}")
    tasks = [
        task
        for task in smoke_task_catalog(arms)
        if task.mechanism == mechanism and task.kind == task_kind
    ]
    task_id = request.get("task_id")
    if task_id is not None:
        tasks = [task for task in tasks if task.task_id == str(task_id)]
    if not tasks:
        raise ValueError(
            f"no smoke task for mechanism={mechanism!r} kind={task_kind!r}"
        )
    arm = arms[mechanism]
    problem = build_problem(arm, tasks[0])
    fk = arm.robot.planar_fk
    if fk is None:
        raise ValueError("smoke arm is missing planar_fk")
    return problem, CartesianDiskGoalGenerator(planar_fk=fk)


def _failed_attempt(
    *,
    status: str,
    request: Mapping[str, Any] | None,
    stdout: str | None,
    stderr: str | None,
    returncode: int | None,
    detail: str,
) -> dict[str, Any]:
    digest = request_digest(request) if request is not None else None
    return {
        "schema_id": SCHEMA_ID,
        "status": status,
        "request_digest": digest,
        "planner_id": None if request is None else request.get("planner_id"),
        "seed": None if request is None else request.get("seed"),
        "process_isolated": True,
        "result": None,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode,
        "unavailable_reason": detail,
        **_environment_record(),
    }


def execute_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Run one resolved worker request in the current process.

    Optional PDST / custom samplers return ``unsupported_optional`` without
    constructing a planner. Unknown IDs fail closed.
    """
    digest = request_digest(request)
    base: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "request_digest": digest,
        "planner_id": request.get("planner_id"),
        "seed": request.get("seed"),
        "process_isolated": True,
        **_environment_record(),
    }
    planner_id = str(request.get("planner_id", ""))
    if planner_id in OPTIONAL_PLANNER_IDS or _custom_sampler_requested(request):
        reason = (
            "custom_sampler_not_implemented"
            if _custom_sampler_requested(request)
            else "optional_pdst_not_implemented"
        )
        return {
            **base,
            "status": STATUS_UNSUPPORTED_OPTIONAL,
            "unavailable_reason": reason,
            "result": None,
        }
    if planner_id not in PLANNER_FACTORIES:
        return {
            **base,
            "status": STATUS_REJECTED,
            "unavailable_reason": f"unknown_planner_id:{planner_id}",
            "result": None,
        }
    checkpoints = _checkpoints(request)
    if planner_id == "ompl_fmt" and checkpoints is not None:
        return {
            **base,
            "status": STATUS_REJECTED,
            "unavailable_reason": "fmt_is_independent_sample_count_run",
            "result": None,
        }
    if planner_id in ONESHOT_PLANNER_IDS and checkpoints is not None:
        return {
            **base,
            "status": STATUS_REJECTED,
            "unavailable_reason": "optimizer_checkpoints_not_supported",
            "result": None,
        }
    source = str(request.get("problem_source", PROBLEM_SOURCE_SMOKE))
    if source != PROBLEM_SOURCE_SMOKE:
        return {
            **base,
            "status": STATUS_REJECTED,
            "unavailable_reason": f"unsupported_problem_source:{source}",
            "result": None,
        }
    problem, goal_generator = _build_smoke_problem(request)
    params = dict(request.get("planner_params") or {})
    params["seed"] = int(request["seed"])
    params["goal_generator"] = goal_generator
    params["planner_id"] = planner_id
    if request.get("solve_time_s") is not None:
        params["solve_time_s"] = float(request["solve_time_s"])
    if planner_id == "ompl_fmt":
        num_samples = request.get("num_samples", params.get("num_samples"))
        if num_samples is not None:
            params["num_samples"] = int(num_samples)
        params.pop("checkpoints_s", None)
    elif planner_id in CHECKPOINT_PLANNER_IDS and checkpoints is not None:
        params["checkpoints_s"] = checkpoints
    planner = PLANNER_FACTORIES[planner_id](params)
    result = planner.solve(problem)
    from inequality_mechanisms.core.serialize import planning_result_to_dict

    return {
        **base,
        "status": STATUS_COMPLETED,
        "planner_id": planner.planner_id,
        "result": planning_result_to_dict(result),
    }


def invoke_ompl_worker(
    request: Mapping[str, Any],
    *,
    timeout_s: float,
    work_dir: Path,
    self_test: str | None = None,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Spawn one child for ``request`` and always return an attempt record."""
    work_dir.mkdir(parents=True, exist_ok=True)
    request_map = dict(request)
    digest = request_digest(request_map)
    request_path = work_dir / "request.json"
    out_path = work_dir / "result.json"
    request_path.write_text(canonical_json(request_map) + "\n", encoding="utf-8")
    cmd = [
        sys.executable,
        "-m",
        "inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c",
        "--request",
        str(request_path),
        "--out",
        str(out_path),
    ]
    if self_test:
        cmd.extend(["--self-test", self_test])
    child_env = dict(os.environ if env is None else env)
    src_root = Path(__file__).resolve().parents[2]
    existing = child_env.get("PYTHONPATH", "")
    child_env["PYTHONPATH"] = os.pathsep.join(
        [str(src_root)] + ([existing] if existing else [])
    )
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=float(timeout_s),
            env=child_env,
            cwd=str(cwd) if cwd is not None else None,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else None
        stderr = exc.stderr if isinstance(exc.stderr, str) else None
        return _failed_attempt(
            status=STATUS_CHILD_TIMEOUT,
            request=request_map,
            stdout=stdout,
            stderr=stderr,
            returncode=None,
            detail="child_timeout",
        )
    payload: dict[str, Any] | None = None
    if out_path.exists():
        try:
            loaded = json.loads(out_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except json.JSONDecodeError:
            payload = None
    stdout = proc.stdout
    stderr = proc.stderr
    if proc.returncode != 0:
        if payload is not None and payload.get("status") in {
            STATUS_CHILD_CRASH,
            STATUS_REJECTED,
            STATUS_UNSUPPORTED_OPTIONAL,
        }:
            payload.setdefault("stdout", stdout)
            payload.setdefault("stderr", stderr)
            payload.setdefault("returncode", proc.returncode)
            return payload
        return _failed_attempt(
            status=STATUS_CHILD_CRASH,
            request=request_map,
            stdout=stdout,
            stderr=stderr,
            returncode=proc.returncode,
            detail="child_crash",
        )
    if payload is None:
        return _failed_attempt(
            status=STATUS_CHILD_CRASH,
            request=request_map,
            stdout=stdout,
            stderr=stderr,
            returncode=proc.returncode,
            detail="missing_or_invalid_atomic_out",
        )
    if payload.get("request_digest") != digest:
        return _failed_attempt(
            status=STATUS_CHILD_CRASH,
            request=request_map,
            stdout=stdout,
            stderr=stderr,
            returncode=proc.returncode,
            detail="request_digest_mismatch",
        )
    payload["stdout"] = stdout
    payload["stderr"] = stderr
    payload["returncode"] = proc.returncode
    return payload


def compare_fresh_process_agreement(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two isolated solves without claiming RNG reproducibility."""
    first_result = first.get("result") or {}
    second_result = second.get("result") or {}
    status_match = first.get("status") == second.get("status")
    cost_match = first_result.get("objective_cost") == second_result.get(
        "objective_cost"
    )
    return {
        "fresh_process_agreement": bool(status_match and cost_match),
        "status_match": bool(status_match),
        "cost_match": bool(cost_match),
        "reproducibility_contract": "not_claimed_in_process",
        "first_status": first.get("status"),
        "second_status": second.get("status"),
        "first_cost": first_result.get("objective_cost"),
        "second_cost": second_result.get("objective_cost"),
    }


def _run_self_test(kind: str, out_path: Path, request: Mapping[str, Any]) -> None:
    if kind == "hang":
        time.sleep(3600.0)
        return
    if kind == "crash":
        raise RuntimeError("injected worker crash")
    if kind == "truncated-tmp":
        tmp = out_path.with_name(f".{out_path.name}.{os.getpid()}.tmp")
        tmp.write_text('{"status": "completed", "truncated": tru', encoding="utf-8")
        sys.exit(0)
    if kind == "crash-after-write":
        write_atomic_json(
            out_path,
            {
                **_failed_attempt(
                    status=STATUS_CHILD_CRASH,
                    request=request,
                    stdout=None,
                    stderr="injected crash after write",
                    returncode=2,
                    detail="injected_crash_after_write",
                ),
                "request_digest": request_digest(request),
            },
        )
        sys.exit(2)
    raise ValueError(f"unknown self-test {kind!r}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry: ``--request`` JSON in, atomic ``--out`` JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--self-test", default=None)
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if not isinstance(request, dict):
        raise ValueError("worker request must be a JSON object")
    try:
        if args.self_test:
            _run_self_test(str(args.self_test), args.out, request)
        payload = execute_request(request)
        write_atomic_json(args.out, payload)
        return 0
    except Exception as exc:
        write_atomic_json(
            args.out,
            _failed_attempt(
                status=STATUS_CHILD_CRASH,
                request=request,
                stdout=None,
                stderr=traceback.format_exc(),
                returncode=1,
                detail=f"child_crash:{exc}",
            ),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
