"""Sprint V3.7 planar 3R free-space evidence runner."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import numpy as np

from inequality_mechanisms.adapters.ompl import is_ompl_available
from inequality_mechanisms.benchmarks.classification import (
    TASK_ALREADY_SATISFIED,
    TASK_INVALID_UNREPRESENTABLE,
    classify_direct_attempt,
)
from inequality_mechanisms.benchmarks.free_space_bank_3r import (
    FreeSpaceEvidenceContract3R,
    ResolvedFreeSpaceTask3R,
    build_bank_arms_3r,
    build_problem_3r,
    goal_generator_3r,
    load_free_space_bank_3r,
    max_candidates_3r,
    resolve_free_space_tasks_3r,
    resolved_bank_3r_to_dict,
)
from inequality_mechanisms.benchmarks.free_space_strata import (
    assign_size_stratum,
    paired_stratum_from_classes,
)
from inequality_mechanisms.benchmarks.planar_3r_arms import Planar3RArm
from inequality_mechanisms.core.goals import GoalSamplingRequest
from inequality_mechanisms.core.local_motion import OutputLinearMotion
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
    Trajectory,
)
from inequality_mechanisms.core.serialize import planning_result_from_dict
from inequality_mechanisms.planners.direct.input_linear import InputLinearDirectPlanner
from inequality_mechanisms.planners.direct.output_linear import OutputLinearDirectPlanner
from inequality_mechanisms.planners.roadmap import PRMPlanner
from inequality_mechanisms.planners.tree import RRTConnectPlanner

DeterministicPlanner = Literal["input_linear", "output_linear"]
StochasticPlanner = Literal[
    "prm",
    "rrt_connect",
    "ompl_prm",
    "ompl_rrt_connect",
]
PlannerName3R = DeterministicPlanner | StochasticPlanner

DETERMINISTIC_PLANNERS: tuple[DeterministicPlanner, ...] = (
    "input_linear",
    "output_linear",
)
STOCHASTIC_PLANNERS: tuple[StochasticPlanner, ...] = (
    "prm",
    "rrt_connect",
    "ompl_prm",
    "ompl_rrt_connect",
)


def _short_circuit_result(
    *,
    problem: Any,
    task_class: str,
    planner_id: str,
    status: PlanningStatus,
    reason: str,
) -> PlanningResult:
    already = status is PlanningStatus.SUCCESS
    return PlanningResult(
        status=status,
        trajectory=Trajectory(states=()) if already else None,
        selected_goal_state=problem.start if already else None,
        total_wall_time_s=0.0,
        query_time_s=0.0,
        objective_cost=0.0 if already else None,
        path_length_u=0.0 if already else None,
        path_length_q=0.0 if already else None,
        path_length_x=0.0 if already else None,
        task_class=task_class,
        final_goal_residual=problem.goal.residual(problem.start),
        planner_metrics={
            "goal_set_short_circuit": reason,
            "goal_set_candidate_count": 0,
        },
        provenance=ResultProvenance(
            architecture_version=3,
            planner_id=planner_id,
        ),
        state_validity_checks=1,
        motion_validity_checks=0,
    )


def _maybe_short_circuit(
    *,
    problem: Any,
    task_class: str,
    planner_id: str,
) -> PlanningResult | None:
    if task_class == TASK_ALREADY_SATISFIED:
        return _short_circuit_result(
            problem=problem,
            task_class=task_class,
            planner_id=planner_id,
            status=PlanningStatus.SUCCESS,
            reason="already_satisfied",
        )
    if task_class == TASK_INVALID_UNREPRESENTABLE:
        return _short_circuit_result(
            problem=problem,
            task_class=task_class,
            planner_id=planner_id,
            status=PlanningStatus.INVALID,
            reason="invalid_unrepresentable",
        )
    return None


def _goal_candidates(
    arm: Planar3RArm,
    task: ResolvedFreeSpaceTask3R,
    contract: FreeSpaceEvidenceContract3R,
) -> list[Any]:
    problem = build_problem_3r(arm, task)
    generator = goal_generator_3r(arm, task, contract)
    request = GoalSamplingRequest(max_candidates=max_candidates_3r(task, contract))
    return list(generator.generate(arm.robot, problem.goal, request))


def _presearch(
    arm: Planar3RArm,
    task: ResolvedFreeSpaceTask3R,
    contract: FreeSpaceEvidenceContract3R,
) -> tuple[str, dict[str, Any], list[Any]]:
    problem = build_problem_3r(arm, task)
    start_valid = bool(problem.scene.state_is_valid(problem.start))
    try:
        _ = problem.goal.residual(problem.start)
        goal_usable = True
    except (NotImplementedError, ValueError, TypeError):
        goal_usable = False
    already = bool(goal_usable and problem.goal.satisfied(problem.start))
    candidates = _goal_candidates(arm, task, contract) if goal_usable else []

    direct_ok = already
    direct_reference_cost: float | None = 0.0 if already else None
    reference_candidate: Any | None = problem.start if already else None
    reference_candidate_id: str | None = "exact_start" if already else None
    direct_motion_checks = 0
    if not already:
        best: tuple[float, Any, str] | None = None
        for cand in candidates:
            motion = problem.local_motion.connect(problem.start, cand.state)
            if motion is None:
                continue
            direct_motion_checks += 1
            if not problem.scene.motion_is_valid(motion):
                continue
            cost = float(problem.objective.motion_cost(motion))
            sample_id = str(cand.provenance.get("goal_sample_id", "unknown"))
            if best is None or cost < best[0]:
                best = (cost, cand.state, sample_id)
        if best is not None:
            direct_ok = True
            direct_reference_cost = best[0]
            reference_candidate = best[1]
            reference_candidate_id = best[2]

    task_class = classify_direct_attempt(
        start_valid=start_valid,
        goal_usable=goal_usable,
        already_satisfied=already,
        candidates_representable=bool(candidates) or already,
        connector_succeeded=direct_ok,
    )
    tip_distance = float(np.linalg.norm(task.start_tip - task.goal_center))
    size = assign_size_stratum(tip_distance, contract.size_bins)

    direct_u = None
    direct_q = None
    if reference_candidate is not None and reference_candidate is not problem.start:
        direct_u = float(np.linalg.norm(reference_candidate.u - problem.start.u))
        direct_q = float(np.linalg.norm(reference_candidate.q - problem.start.q))

    descriptor = {
        "task_id": task.task_id,
        "task_family": task.task_family,
        "mechanism": arm.name,
        "task_class": task_class,
        "size_stratum": size,
        "tip_distance": tip_distance,
        "goal_radius": float(task.goal_radius),
        "goal_center": task.goal_center.tolist(),
        "goal_phi": task.goal_phi,
        "orientation_tol": task.orientation_tol,
        "start_q": task.start_q.tolist(),
        "start_tip": task.start_tip.tolist(),
        "start_phi": task.start_phi,
        "goal_sample_point_ids": list(task.goal_point_ids),
        "phi_samples": list(task.phi_samples),
        "goal_candidates": len(candidates),
        "direct_connector_policy": getattr(
            problem.local_motion, "model_id", type(problem.local_motion).__name__
        ),
        "direct_connector_available": bool(direct_ok),
        "direct_motion_checks": direct_motion_checks,
        "direct_goal_set_reference_cost": direct_reference_cost,
        "direct_reference_goal_sample_id": reference_candidate_id,
        "direct_u_distance": direct_u,
        "direct_q_distance": direct_q,
    }
    return task_class, descriptor, candidates


def _solve_native(
    planner_name: PlannerName3R,
    *,
    arm: Planar3RArm,
    task: ResolvedFreeSpaceTask3R,
    contract: FreeSpaceEvidenceContract3R,
    problem: Any,
    seed: int | None,
) -> PlanningResult:
    generator = goal_generator_3r(arm, task, contract)
    max_candidates = max_candidates_3r(task, contract)
    if planner_name == "input_linear":
        return InputLinearDirectPlanner(
            goal_generator=generator,
            max_candidates=max_candidates,
        ).solve(problem)
    if planner_name == "output_linear":
        out_problem = replace(
            problem,
            local_motion=OutputLinearMotion(robot=arm.robot, n_samples=64),
        )
        return OutputLinearDirectPlanner(
            goal_generator=generator,
            max_candidates=max_candidates,
        ).solve(out_problem)
    if seed is None:
        raise ValueError(f"{planner_name} requires a frozen seed")
    if planner_name == "prm":
        return PRMPlanner(
            seed=seed,
            n_samples=80,
            k_neighbors=10,
            max_edge_u=1.5,
            max_goal_candidates=max_candidates,
            goal_generator=generator,
        ).solve(problem)
    if planner_name == "rrt_connect":
        return RRTConnectPlanner(
            seed=seed,
            max_iterations=800,
            step_u=0.4,
            goal_bias=0.1,
            max_goal_candidates=max_candidates,
            goal_generator=generator,
        ).solve(problem)
    raise ValueError(f"{planner_name!r} is not an in-process native planner")


def _solve_ompl_isolated(
    *,
    contract: FreeSpaceEvidenceContract3R,
    task_id: str,
    mechanism: str,
    planner_name: str,
    seed: int,
    solve_time_s: float,
) -> tuple[PlanningResult | None, str | None]:
    if not is_ompl_available():
        return None, "ompl_unavailable"
    if not contract.ompl_process_isolation:
        raise ValueError("V3.7 contract requires OMPL process isolation")

    request = {
        "contract_path": str(contract.source_path),
        "task_id": task_id,
        "mechanism": mechanism,
        "planner": planner_name,
        "seed": int(seed),
        "solve_time_s": float(solve_time_s),
    }
    with tempfile.TemporaryDirectory(prefix="v3_7_ompl_") as tmp:
        tmp_path = Path(tmp)
        req_path = tmp_path / "request.json"
        out_path = tmp_path / "result.json"
        req_path.write_text(json.dumps(request), encoding="utf-8")
        cmd = [
            sys.executable,
            "-m",
            "inequality_mechanisms.benchmarks.ompl_process_worker_v3_7",
            "--request",
            str(req_path),
            "--out",
            str(out_path),
        ]
        max_cands = max(
            contract.position_only_representation.max_candidates,
            contract.full_pose_representation.max_candidates,
        )
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(60.0, float(max_cands) * (float(solve_time_s) + 3.0) + 30.0),
            env=os.environ.copy(),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "OMPL isolated worker failed "
                f"({planner_name}, {task_id}, {mechanism}, seed={seed}): "
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    return planning_result_from_dict(payload["result"]), None


def _result_row(
    *,
    contract: FreeSpaceEvidenceContract3R,
    task: ResolvedFreeSpaceTask3R,
    mechanism: str,
    planner_name: str,
    descriptors: dict[str, Any],
    paired_stratum: str,
    result: PlanningResult | None,
    seed: int | None,
    repetition_index: int,
    stochastic: bool,
    process_isolated: bool,
    skipped: str | None = None,
) -> dict[str, Any]:
    ref = descriptors.get("direct_goal_set_reference_cost")
    cost = None if result is None else result.objective_cost
    suboptimality = None
    if cost is not None and ref is not None:
        suboptimality = float(cost) - float(ref)
    return {
        "bank_id": contract.bank_id,
        "task_id": task.task_id,
        "task_family": task.task_family,
        "mechanism": mechanism,
        "planner": planner_name,
        "seed": seed,
        "repetition_index": repetition_index,
        "stochastic": stochastic,
        "process_isolated": process_isolated,
        "paired_stratum": paired_stratum,
        "size_stratum": descriptors["size_stratum"],
        "task_class": descriptors["task_class"],
        "planner_reported_task_class": (
            None if result is None else result.task_class
        ),
        "tip_distance": descriptors["tip_distance"],
        "presearch": descriptors,
        "direct_goal_set_reference_cost": ref,
        "suboptimality_to_direct_reference": suboptimality,
        "skipped": skipped,
        "status": None if result is None else str(result.status),
        "objective_cost": cost,
        "path_length_u": None if result is None else result.path_length_u,
        "path_length_q": None if result is None else result.path_length_q,
        "setup_time_s": None if result is None else result.setup_time_s,
        "preprocessing_time_s": (
            None if result is None else result.preprocessing_time_s
        ),
        "query_time_s": None if result is None else result.query_time_s,
        "postprocessing_time_s": (
            None if result is None else result.postprocessing_time_s
        ),
        "total_wall_time_s": (
            None if result is None else result.total_wall_time_s
        ),
        "state_validity_checks": (
            None if result is None else result.state_validity_checks
        ),
        "motion_validity_checks": (
            None if result is None else result.motion_validity_checks
        ),
        "planner_metrics": (
            None if result is None else dict(result.planner_metrics)
        ),
        "provenance_planner_id": (
            None if result is None else result.provenance.planner_id
        ),
        "provenance_extras": (
            None if result is None else dict(result.provenance.extras)
        ),
        "architecture_version": 3,
    }


def run_free_space_evidence_3r(
    *,
    contract: FreeSpaceEvidenceContract3R | None = None,
    deterministic_planners: tuple[DeterministicPlanner, ...] = (
        DETERMINISTIC_PLANNERS
    ),
    stochastic_planners: tuple[StochasticPlanner, ...] = STOCHASTIC_PLANNERS,
    seeds: tuple[int, ...] | None = None,
    ompl_solve_time_s: float = 1.0,
    task_ids: tuple[str, ...] | None = None,
    task_families: tuple[str, ...] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the frozen V3.7 multi-planner evidence matrix."""
    contract = contract if contract is not None else load_free_space_bank_3r()
    seeds = contract.stochastic_seeds if seeds is None else tuple(seeds)
    arms = build_bank_arms_3r(contract)
    resolved_all = resolve_free_space_tasks_3r(contract, arms=arms)
    resolved = resolved_all
    if task_ids is not None:
        wanted = set(task_ids)
        resolved = tuple(t for t in resolved if t.task_id in wanted)
    if task_families is not None:
        families = set(task_families)
        resolved = tuple(t for t in resolved if t.task_family in families)
    if not resolved:
        raise ValueError("task filters produced an empty task list")

    rows: list[dict[str, Any]] = []
    for task in resolved:
        descriptors: dict[str, dict[str, Any]] = {}
        classes: dict[str, str] = {}
        for mech in contract.mechanisms:
            arm = arms[mech]
            task_class, descriptor, _ = _presearch(arm, task, contract)
            descriptors[mech] = descriptor
            classes[mech] = task_class
        paired = paired_stratum_from_classes(
            classes[contract.mechanisms[0]],
            classes[contract.mechanisms[1]],
        )

        for planner_name in deterministic_planners:
            for mech in contract.mechanisms:
                arm = arms[mech]
                problem = build_problem_3r(arm, task)
                short = _maybe_short_circuit(
                    problem=problem,
                    task_class=classes[mech],
                    planner_id=planner_name,
                )
                result = short or _solve_native(
                    planner_name,
                    arm=arm,
                    task=task,
                    contract=contract,
                    problem=problem,
                    seed=None,
                )
                rows.append(
                    _result_row(
                        contract=contract,
                        task=task,
                        mechanism=mech,
                        planner_name=planner_name,
                        descriptors=descriptors[mech],
                        paired_stratum=paired,
                        result=result,
                        seed=None,
                        repetition_index=0,
                        stochastic=False,
                        process_isolated=False,
                    )
                )

        for planner_name in stochastic_planners:
            ompl = planner_name.startswith("ompl_")
            for rep_index, seed in enumerate(seeds):
                for mech in contract.mechanisms:
                    arm = arms[mech]
                    problem = build_problem_3r(arm, task)
                    short = _maybe_short_circuit(
                        problem=problem,
                        task_class=classes[mech],
                        planner_id=planner_name,
                    )
                    if short is not None:
                        rows.append(
                            _result_row(
                                contract=contract,
                                task=task,
                                mechanism=mech,
                                planner_name=planner_name,
                                descriptors=descriptors[mech],
                                paired_stratum=paired,
                                result=short,
                                seed=seed,
                                repetition_index=rep_index,
                                stochastic=True,
                                process_isolated=ompl,
                            )
                        )
                        continue
                    if ompl:
                        result, skipped = _solve_ompl_isolated(
                            contract=contract,
                            task_id=task.task_id,
                            mechanism=mech,
                            planner_name=planner_name,
                            seed=seed,
                            solve_time_s=ompl_solve_time_s,
                        )
                        rows.append(
                            _result_row(
                                contract=contract,
                                task=task,
                                mechanism=mech,
                                planner_name=planner_name,
                                descriptors=descriptors[mech],
                                paired_stratum=paired,
                                result=result,
                                seed=seed,
                                repetition_index=rep_index,
                                stochastic=True,
                                process_isolated=True,
                                skipped=skipped,
                            )
                        )
                        continue
                    result = _solve_native(
                        planner_name,
                        arm=arm,
                        task=task,
                        contract=contract,
                        problem=problem,
                        seed=seed,
                    )
                    rows.append(
                        _result_row(
                            contract=contract,
                            task=task,
                            mechanism=mech,
                            planner_name=planner_name,
                            descriptors=descriptors[mech],
                            paired_stratum=paired,
                            result=result,
                            seed=seed,
                            repetition_index=rep_index,
                            stochastic=True,
                            process_isolated=False,
                        )
                    )

    return rows, resolved_bank_3r_to_dict(contract, resolved_all)


def evidence_manifest_3r(
    rows: list[dict[str, Any]],
    *,
    contract: FreeSpaceEvidenceContract3R,
    implementation_revision: str | None,
    ompl_solve_time_s: float,
) -> dict[str, Any]:
    """Build the V3.7 evidence manifest."""
    by_family: dict[str, int] = defaultdict(int)
    for row in rows:
        by_family[str(row["task_family"])] += 1
    return {
        "sprint": "V3.7",
        "bank_id": contract.bank_id,
        "schema_version": contract.schema_version,
        "architecture_version": 3,
        "implementation_revision": implementation_revision,
        "n_rows": len(rows),
        "rows_by_task_family": dict(by_family),
        "deterministic_planners": list(DETERMINISTIC_PLANNERS),
        "stochastic_planners": list(STOCHASTIC_PLANNERS),
        "stochastic_seeds": list(contract.stochastic_seeds),
        "ompl_process_isolation": contract.ompl_process_isolation,
        "ompl_solve_time_s": float(ompl_solve_time_s),
        "position_only_and_full_pose_estimands_separate": True,
        "dense_3d_lattice": "diagnostic_only_not_evidence_exit_criterion",
        "contract_path": str(contract.source_path),
    }


__all__ = [
    "DETERMINISTIC_PLANNERS",
    "STOCHASTIC_PLANNERS",
    "evidence_manifest_3r",
    "run_free_space_evidence_3r",
]
