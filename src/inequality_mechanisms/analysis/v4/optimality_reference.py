"""V4.2D center-IK and historical V4.2B optimality references (ADR-032)."""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    canonical_v4_2b_retained_root,
    canonical_v4_2c_retained_root,
)
from inequality_mechanisms.benchmarks.classification import classify_direct_attempt
from inequality_mechanisms.benchmarks.free_space_bank_v2 import build_problem_v2
from inequality_mechanisms.core.goals import GoalSamplingRequest
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.state import StateCandidate
from inequality_mechanisms.experiments.span_cases import (
    generate_span_cases,
    realize_mounted_span_case,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    AUDIT_CASE_IDS,
    FROZEN_V4_2B_FILES_DIGEST,
)
from inequality_mechanisms.experiments.v4.span_common_physical_bank import (
    FROZEN_TASK_IDS,
    PLANAR_L1,
    PLANAR_L2,
    load_common_physical_bank,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    FROZEN_V3_6D_DIGEST,
    FROZEN_V3_6D_REGISTRY_REL,
)
from inequality_mechanisms.experiments.v4.span_controlled_corrective_audit import (
    sampling_arms_for_mounted,
    tasks_from_common_physical_bank,
)
from inequality_mechanisms.kinematics.planar_2r_goals import CartesianDiskGoalGenerator
from inequality_mechanisms.mechanisms.span_registry import load_span_registry
from inequality_mechanisms.planners.sampling_space import (
    resolve_connector,
    try_connect,
)

SCHEMA_VERSION = "v4.2d.optimality_reference.v1"
DEFAULT_CONFIG_REL = Path("configs") / "v4" / "optimality_reference_report_v1.json"
CANDIDATE_GENERATOR_ID = "cartesian_disk_center_ik"
PRIMARY_REFERENCE_COUNT = 100
FROZEN_STAGE_C_ROWS = 6200
FROZEN_V4_2C_FILES_DIGEST = (
    "99ec523a706632391c85e16cae505e6cd11a6f14d15682eb711515aefcf76c93"
)
MECHANISMS = ("fourbar", "gearbox")
PRM_PLANNER_ID = "ompl_prm"


class OptimalityReferenceError(ValueError):
    """Raised when a V4.2D reference cannot be reconstructed or validated."""

    failure_code = "v4_2d_optimality_reference_failed"


_PROBLEM_CACHE: dict[str, Any] = {}


def load_report_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load and lightly validate the frozen V4.2D report config."""
    source = (
        Path(path) if path is not None else CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise OptimalityReferenceError(f"V4.2D config must be a JSON object: {source}")
    if payload.get("schema_version") != "v4.2d.optimality_reference_report.v1":
        raise OptimalityReferenceError(f"unsupported V4.2D config schema in {source}")
    if payload.get("v4_2b_files_digest") != FROZEN_V4_2B_FILES_DIGEST:
        raise OptimalityReferenceError("config v4_2b_files_digest does not match lock")
    if payload.get("v4_2c_files_digest") != FROZEN_V4_2C_FILES_DIGEST:
        raise OptimalityReferenceError("config v4_2c_files_digest does not match lock")
    if tuple(payload.get("case_ids") or ()) != AUDIT_CASE_IDS:
        raise OptimalityReferenceError("config case_ids must equal AUDIT_CASE_IDS")
    if tuple(payload.get("task_ids") or ()) != FROZEN_TASK_IDS:
        raise OptimalityReferenceError("config task_ids must equal FROZEN_TASK_IDS")
    return dict(payload)


def _manifest_files_digest(root: Path) -> str:
    payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    digest = payload.get("files_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise OptimalityReferenceError(
            f"missing files_digest in {root / 'manifest.json'}"
        )
    return digest


def verify_source_package_digests(
    config: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Fail closed when frozen V4.2B or V4.2C trees have drifted."""
    cfg = dict(config) if config is not None else load_report_config()
    b_digest = _manifest_files_digest(canonical_v4_2b_retained_root())
    c_digest = _manifest_files_digest(canonical_v4_2c_retained_root())
    if b_digest != str(cfg["v4_2b_files_digest"]):
        raise OptimalityReferenceError(
            f"V4.2B files_digest drifted: {b_digest} != {cfg['v4_2b_files_digest']}"
        )
    if c_digest != str(cfg["v4_2c_files_digest"]):
        raise OptimalityReferenceError(
            f"V4.2C files_digest drifted: {c_digest} != {cfg['v4_2c_files_digest']}"
        )
    if c_digest != FROZEN_V4_2C_FILES_DIGEST:
        raise OptimalityReferenceError("V4.2C manifest files_digest drifted")
    return {
        "v4_2b_files_digest": b_digest,
        "v4_2c_files_digest": c_digest,
        "v4_2c_source_revision": str(cfg.get("v4_2c_source_revision") or ""),
    }


def candidate_key(goal_sample_id: str, ik_family: str) -> str:
    """Return the stable ``<goal_sample_id>::<ik_family>`` identity."""
    return f"{goal_sample_id}::{ik_family}"


def _cache() -> dict[str, Any]:
    if "bank" in _PROBLEM_CACHE:
        return _PROBLEM_CACHE
    bank = load_common_physical_bank()
    registry_path = CANONICAL_REPO_ROOT / FROZEN_V3_6D_REGISTRY_REL
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    registry = load_span_registry(payload)
    digest = getattr(registry, "sha256", None)
    if digest is not None and digest != FROZEN_V3_6D_DIGEST:
        raise OptimalityReferenceError(
            f"V3.6D registry digest mismatch: file={digest} lock={FROZEN_V3_6D_DIGEST}"
        )
    _PROBLEM_CACHE["bank"] = bank
    _PROBLEM_CACHE["tasks"] = tasks_from_common_physical_bank(bank)
    _PROBLEM_CACHE["registry"] = registry
    _PROBLEM_CACHE["cases"] = {case.case_id: case for case in generate_span_cases()}
    _PROBLEM_CACHE["realized"] = {}
    return _PROBLEM_CACHE


def clear_problem_cache() -> None:
    """Drop cached bank/registry/realized cases (tests only)."""
    _PROBLEM_CACHE.clear()


def reconstruct_v4_2c_problem(
    case_id: str,
    task_id: str,
    mechanism: str,
) -> tuple[PlanningProblem, CartesianDiskGoalGenerator]:
    """Rebuild one V4.2C physical problem from the same public APIs as the worker."""
    cache = _cache()
    cases = cache["cases"]
    if case_id not in cases:
        raise OptimalityReferenceError(f"unknown_case_id:{case_id}")
    tasks = cache["tasks"]
    if task_id not in tasks:
        raise OptimalityReferenceError(f"unknown_task_id:{task_id}")
    realized_map = cache["realized"]
    if case_id not in realized_map:
        realized_map[case_id] = realize_mounted_span_case(
            cases[case_id], cache["registry"]
        )
    arms = sampling_arms_for_mounted(realized_map[case_id], L1=PLANAR_L1, L2=PLANAR_L2)
    if mechanism not in arms:
        raise OptimalityReferenceError(f"unknown_mechanism:{mechanism}")
    arm = arms[mechanism]
    problem = build_problem_v2(arm, tasks[task_id])
    fk = arm.robot.planar_fk
    if fk is None:
        raise OptimalityReferenceError("v4.2c arm is missing planar_fk")
    return problem, CartesianDiskGoalGenerator(planar_fk=fk)


def generate_center_candidates(
    problem: PlanningProblem,
    generator: CartesianDiskGoalGenerator,
    *,
    max_candidates: int = 8,
) -> tuple[StateCandidate, ...]:
    """Return scene-valid disk-center IK lifts, matching the OMPL adapter filter."""
    request = GoalSamplingRequest(max_candidates=max_candidates)
    raw = list(generator.generate(problem.robot, problem.goal, request))
    accepted = [cand for cand in raw if problem.scene.state_is_valid(cand.state)]
    return tuple(accepted[:max_candidates])


def _as_list(values: Any) -> list[float]:
    return [float(v) for v in np.asarray(values, dtype=np.float64).tolist()]


def evaluate_center_candidate(
    problem: PlanningProblem,
    candidate: StateCandidate,
    *,
    tau: float,
) -> dict[str, Any]:
    """Evaluate input-linear actuator-travel cost for one center-IK candidate."""
    start = problem.start
    provenance = dict(candidate.provenance)
    sample_id = str(provenance.get("goal_sample_id") or "disk_center")
    family = str(provenance.get("ik_family") or "unknown")
    generator_id = str(
        provenance.get("candidate_generator_id") or CANDIDATE_GENERATOR_ID
    )
    connector = resolve_connector(problem)
    valid = try_connect(connector, problem, start, candidate.state)
    motion = connector.connect(start, candidate.state) if valid else None
    cost: float | None = None
    euclidean = float(np.linalg.norm(candidate.state.u - start.u))
    if valid and motion is not None:
        cost = float(ActuatorTravelObjective().motion_cost(motion))
        if abs(cost - euclidean) > tau:
            raise OptimalityReferenceError(
                "direct cost disagrees with Euclidean U endpoint distance: "
                f"{cost} vs {euclidean}"
            )
    residual = float(problem.goal.residual(candidate.state).primary)
    satisfied = bool(problem.goal.satisfied(candidate.state))
    return {
        "candidate_key": candidate_key(sample_id, family),
        "goal_sample_id": sample_id,
        "ik_family": family,
        "candidate_generator_id": generator_id,
        "direct_valid": bool(valid),
        "direct_cost": cost,
        "euclidean_u": euclidean,
        "residual": residual,
        "satisfies_disk": satisfied,
        "u": _as_list(candidate.state.u),
        "q": _as_list(candidate.state.q),
        "provenance": provenance,
    }


def _reference_row(
    *,
    case_id: str,
    task_id: str,
    mechanism: str,
    problem: PlanningProblem,
    evaluations: Sequence[Mapping[str, Any]],
    tau: float,
    tau_zero: float,
) -> dict[str, Any]:
    start = problem.start
    already = bool(problem.goal.satisfied(start))
    start_valid = bool(problem.scene.state_is_valid(start))
    any_valid = any(bool(item.get("direct_valid")) for item in evaluations)
    task_class = classify_direct_attempt(
        start_valid=start_valid,
        goal_usable=True,
        already_satisfied=already,
        candidates_representable=len(evaluations) > 0,
        connector_succeeded=any_valid,
    )
    if already:
        j_star = 0.0
        selected_key = None
        selected_cost = 0.0
    else:
        valid_costs = [
            (float(item["direct_cost"]), str(item["candidate_key"]))
            for item in evaluations
            if item.get("direct_valid") and item.get("direct_cost") is not None
        ]
        if not valid_costs:
            raise OptimalityReferenceError(
                f"no valid center-IK direct motion for {case_id}/{task_id}/{mechanism}"
            )
        valid_costs.sort(key=lambda pair: (pair[0], pair[1]))
        selected_cost, selected_key = valid_costs[0]
        j_star = float(selected_cost)
        if j_star < -tau:
            raise OptimalityReferenceError(
                f"negative reconstructed J*_C for {case_id}/{task_id}/{mechanism}"
            )
        selected_eval = next(
            item for item in evaluations if item["candidate_key"] == selected_key
        )
        if not selected_eval.get("satisfies_disk"):
            raise OptimalityReferenceError(
                "selected reference candidate does not satisfy the disk: "
                f"{selected_key}"
            )
    task_family = "near" if str(task_id).startswith("near_") else "far"
    return {
        "case_id": case_id,
        "task_id": task_id,
        "mechanism": mechanism,
        "task_family": task_family,
        "task_class": task_class,
        "already_satisfied": already,
        "j_star_c": float(j_star),
        "reference_candidate_key": selected_key,
        "n_candidates": len(evaluations),
        "n_valid_candidates": sum(
            1 for item in evaluations if item.get("direct_valid")
        ),
        "candidate_generator_id": CANDIDATE_GENERATOR_ID,
        "start_u": _as_list(start.u),
        "start_q": _as_list(start.q),
        "zero_reference": bool(j_star <= tau_zero),
    }


def build_center_ik_references(
    *,
    config: Mapping[str, Any] | None = None,
    stage_c_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build 100 primary J*_C,m rows and the candidate-cost table."""
    cfg = dict(config) if config is not None else load_report_config()
    tau = float(cfg["tau"])
    tau_zero = float(cfg["tau_zero"])
    max_candidates = int(
        cfg.get("max_candidates") or cfg.get("max_goal_candidates") or 8
    )
    case_ids = tuple(cfg["case_ids"])
    task_ids = tuple(cfg["task_ids"])
    mechanisms = tuple(cfg.get("mechanisms") or MECHANISMS)
    reference_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for case_id in case_ids:
        for task_id in task_ids:
            for mechanism in mechanisms:
                problem, generator = reconstruct_v4_2c_problem(
                    str(case_id), str(task_id), str(mechanism)
                )
                task = _cache()["tasks"][str(task_id)]
                start_q = np.asarray(problem.start.q, dtype=np.float64)
                expected_q = np.asarray(task.start_q, dtype=np.float64)
                if float(np.linalg.norm(start_q - expected_q)) > tau:
                    raise OptimalityReferenceError(
                        f"reconstructed start Q disagrees for {case_id}/{task_id}"
                    )
                tip = np.asarray(
                    problem.robot.forward_kinematics(problem.start).position,
                    dtype=np.float64,
                )
                expected_x = np.asarray(task.start_tip, dtype=np.float64)
                if float(np.linalg.norm(tip - expected_x)) > tau:
                    raise OptimalityReferenceError(
                        f"reconstructed start X disagrees for {case_id}/{task_id}"
                    )
                candidates = generate_center_candidates(
                    problem, generator, max_candidates=max_candidates
                )
                evaluations = [
                    evaluate_center_candidate(problem, cand, tau=tau)
                    for cand in candidates
                ]
                for item in evaluations:
                    if item["candidate_generator_id"] != CANDIDATE_GENERATOR_ID:
                        raise OptimalityReferenceError(
                            "candidate_generator_id is not cartesian_disk_center_ik"
                        )
                    candidate_rows.append(
                        {
                            "case_id": case_id,
                            "task_id": task_id,
                            "mechanism": mechanism,
                            **item,
                        }
                    )
                reference_rows.append(
                    _reference_row(
                        case_id=str(case_id),
                        task_id=str(task_id),
                        mechanism=str(mechanism),
                        problem=problem,
                        evaluations=evaluations,
                        tau=tau,
                        tau_zero=tau_zero,
                    )
                )
    if len(reference_rows) != PRIMARY_REFERENCE_COUNT:
        raise OptimalityReferenceError(
            f"expected {PRIMARY_REFERENCE_COUNT} reference rows, "
            f"got {len(reference_rows)}"
        )
    if stage_c_rows is not None:
        validate_against_stage_c(
            reference_rows,
            candidate_rows,
            stage_c_rows,
            tau=tau,
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "reference_rows": reference_rows,
        "candidate_rows": candidate_rows,
    }


def _stage_c_ompl(record: Mapping[str, Any]) -> Mapping[str, Any]:
    worker = record.get("worker")
    if not isinstance(worker, Mapping):
        return {}
    result = worker.get("result")
    if not isinstance(result, Mapping):
        return {}
    metrics = result.get("planner_metrics")
    if not isinstance(metrics, Mapping):
        return {}
    ompl = metrics.get("ompl")
    return ompl if isinstance(ompl, Mapping) else {}


def _stage_c_result(record: Mapping[str, Any]) -> Mapping[str, Any]:
    worker = record.get("worker")
    if not isinstance(worker, Mapping):
        return {}
    result = worker.get("result")
    return result if isinstance(result, Mapping) else {}


def validate_against_stage_c(
    reference_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    stage_c_rows: Sequence[Mapping[str, Any]],
    *,
    tau: float,
) -> None:
    """Fail closed on generator-ID, candidate-count, and cost-lower-bound errors."""
    refs = {
        (row["case_id"], row["task_id"], row["mechanism"]): row
        for row in reference_rows
    }
    n_valid = {
        (row["case_id"], row["task_id"], row["mechanism"]): 0 for row in reference_rows
    }
    for item in candidate_rows:
        if item.get("direct_valid"):
            key = (item["case_id"], item["task_id"], item["mechanism"])
            n_valid[key] = n_valid.get(key, 0) + 1
    for record in stage_c_rows:
        key = (record.get("case_id"), record.get("task_id"), record.get("mechanism"))
        ref = refs.get(key)
        if ref is None:
            raise OptimalityReferenceError(
                f"Stage C orphan {key} has no reconstructed J*_C"
            )
        result = _stage_c_result(record)
        ompl = _stage_c_ompl(record)
        nontrivial = not ref.get("already_satisfied")
        if nontrivial and record.get("planner_id") != PRM_PLANNER_ID:
            count = ompl.get("discrete_goal_state_count")
            if count is not None and int(count) != int(ref["n_candidates"]):
                raise OptimalityReferenceError(
                    "reconstructed candidate count disagrees with V4.2C metadata "
                    f"for {key}/{record.get('planner_id')}: "
                    f"{ref['n_candidates']} vs {count}"
                )
        selected = result.get("selected_goal_candidate")
        if isinstance(selected, Mapping):
            provenance = selected.get("provenance")
            if isinstance(provenance, Mapping):
                generator_id = provenance.get("candidate_generator_id")
                if (
                    generator_id is not None
                    and str(generator_id) != CANDIDATE_GENERATOR_ID
                ):
                    raise OptimalityReferenceError(
                        "V4.2C candidate_generator_id disagrees with reconstruction"
                    )
        if ompl.get("direct_connector_available") is True and n_valid[key] < 1:
            raise OptimalityReferenceError(
                f"V4.2C reports direct_connector_available but reconstruction "
                f"has no valid motion for {key}"
            )
        j_star = float(ref["j_star_c"])
        costs: list[float] = []
        final_cost = result.get("objective_cost")
        if final_cost is not None and ompl.get("ompl_exact_solution") is not False:
            costs.append(float(final_cost))
        checkpoints = ompl.get("checkpoints")
        if isinstance(checkpoints, list):
            for item in checkpoints:
                if not isinstance(item, Mapping):
                    continue
                exact_cp = item.get("ompl_exact_solution")
                if exact_cp and item.get("best_cost") is not None:
                    costs.append(float(item["best_cost"]))
        for cost in costs:
            if cost < j_star - tau:
                raise OptimalityReferenceError(
                    f"exact planner cost {cost} is below J*_C={j_star} - tau "
                    f"for {key}/{record.get('planner_id')}"
                )


def load_v4_2b_historical_references(
    *,
    config: Mapping[str, Any] | None = None,
    package_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Load unique V4.2B ``input_linear`` rows as J*_B,m (read-only)."""
    cfg = dict(config) if config is not None else load_report_config()
    root = (
        Path(package_root)
        if package_root is not None
        else canonical_v4_2b_retained_root()
    )
    jsonl = root / "planning_audit" / "data" / "planner_rows.jsonl.gz"
    if not jsonl.is_file():
        raise OptimalityReferenceError(f"missing V4.2B planner_rows at {jsonl}")
    case_ids = set(cfg["case_ids"])
    task_ids = set(cfg["task_ids"])
    wanted = set(cfg.get("mechanisms") or MECHANISMS)
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    with gzip.open(jsonl, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("planner") != "input_linear":
                continue
            case_id = str(row.get("case_id"))
            task_id = str(row.get("task_id"))
            mechanism = str(row.get("mechanism"))
            if case_id not in case_ids or task_id not in task_ids:
                continue
            if mechanism not in wanted:
                continue
            key = (case_id, task_id, mechanism)
            if key in grouped:
                raise OptimalityReferenceError(
                    f"duplicate V4.2B input_linear row for {key}"
                )
            grouped[key] = {
                "case_id": case_id,
                "task_id": task_id,
                "mechanism": mechanism,
                "j_star_b": None
                if row.get("objective_cost") is None
                else float(row["objective_cost"]),
                "status": row.get("status"),
                "task_class": row.get("task_class"),
                "selected_goal_sample_id": row.get("selected_goal_sample_id"),
                "path_length_u": row.get("path_length_u"),
            }
    if len(grouped) != PRIMARY_REFERENCE_COUNT:
        raise OptimalityReferenceError(
            f"expected {PRIMARY_REFERENCE_COUNT} V4.2B input_linear rows, "
            f"got {len(grouped)}"
        )
    return [grouped[key] for key in sorted(grouped)]


def join_representation_penalty(
    center_rows: Sequence[Mapping[str, Any]],
    historical_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Attach J*_B,m and representation penalty onto center-IK rows."""
    hist = {
        (row["case_id"], row["task_id"], row["mechanism"]): row
        for row in historical_rows
    }
    out: list[dict[str, Any]] = []
    for row in center_rows:
        key = (row["case_id"], row["task_id"], row["mechanism"])
        other = hist.get(key)
        if other is None:
            raise OptimalityReferenceError(
                f"missing V4.2B historical reference for {key}"
            )
        j_c = float(row["j_star_c"])
        j_b = other.get("j_star_b")
        penalty = None if j_b is None else float(j_c) - float(j_b)
        merged = dict(row)
        merged["j_star_b"] = j_b
        merged["representation_penalty"] = penalty
        merged["v4_2b_selected_goal_sample_id"] = other.get("selected_goal_sample_id")
        out.append(merged)
    return out


def canonical_dumps(payload: Any) -> str:
    """Return a deterministic JSON encoding."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
