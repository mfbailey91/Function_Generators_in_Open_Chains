"""Corrected Sprint V3.6 free-space evidence runner.

This module preserves the v1 pilot and implements the v2 closeout contract:
shared physical starts, one frozen represented goal set, a direct input-linear
reference, lattice goal-set evaluation, and frozen stochastic repetitions.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import numpy as np

from inequality_mechanisms.adapters import GraphSearchPlanner
from inequality_mechanisms.adapters.ompl import is_ompl_available
from inequality_mechanisms.benchmarks.classification import (
    TASK_ALREADY_SATISFIED,
    TASK_INVALID_UNREPRESENTABLE,
    classify_direct_attempt,
)
from inequality_mechanisms.benchmarks.free_space_bank import build_bank_arms
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    FreeSpaceEvidenceContractV2,
    ResolvedFreeSpaceTaskV2,
    build_problem_v2,
    goal_generator_v2,
    load_free_space_bank_v2,
    resolve_free_space_tasks_v2,
)
from inequality_mechanisms.benchmarks.free_space_strata import (
    assign_size_stratum,
    paired_stratum_from_classes,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import build_paired_lattice_arms
from inequality_mechanisms.benchmarks.smoke_sampling_2r import SamplingSmokeArm
from inequality_mechanisms.core.goals import ExactOutputGoal, GoalSamplingRequest
from inequality_mechanisms.core.local_motion import OutputLinearMotion
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
    Trajectory,
)
from inequality_mechanisms.core.serialize import planning_result_from_dict
from inequality_mechanisms.graphs.topology import LatticeConnectivity
from inequality_mechanisms.planners.direct.input_linear import InputLinearDirectPlanner
from inequality_mechanisms.planners.direct.output_linear import OutputLinearDirectPlanner
from inequality_mechanisms.planners.roadmap import PRMPlanner
from inequality_mechanisms.planners.tree import RRTConnectPlanner

DeterministicPlanner = Literal[
    "input_linear",
    "output_linear",
    "lattice_dijkstra_eight_integrated",
]
StochasticPlanner = Literal[
    "prm",
    "rrt_connect",
    "ompl_prm",
    "ompl_rrt_connect",
]
PlannerNameV2 = DeterministicPlanner | StochasticPlanner

DETERMINISTIC_PLANNERS: tuple[DeterministicPlanner, ...] = (
    "input_linear",
    "output_linear",
    "lattice_dijkstra_eight_integrated",
)
STOCHASTIC_PLANNERS: tuple[StochasticPlanner, ...] = (
    "prm",
    "rrt_connect",
    "ompl_prm",
    "ompl_rrt_connect",
)


def _goal_candidates(
    arm: SamplingSmokeArm,
    task: ResolvedFreeSpaceTaskV2,
    contract: FreeSpaceEvidenceContractV2,
) -> list[Any]:
    problem = build_problem_v2(arm, task)
    generator = goal_generator_v2(arm, task)
    request = GoalSamplingRequest(
        max_candidates=contract.goal_representation.max_candidates
    )
    return list(generator.generate(arm.robot, problem.goal, request))


def _presearch(
    arm: SamplingSmokeArm,
    task: ResolvedFreeSpaceTaskV2,
    contract: FreeSpaceEvidenceContractV2,
) -> tuple[str, dict[str, Any], list[Any]]:
    problem = build_problem_v2(arm, task)
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
    size = assign_size_stratum(tip_distance, contract.base_bank.size_bins)

    direct_u = None
    direct_q = None
    if reference_candidate is not None and reference_candidate is not problem.start:
        direct_u = float(
            np.linalg.norm(reference_candidate.u - problem.start.u)
        )
        direct_q = float(
            np.linalg.norm(reference_candidate.q - problem.start.q)
        )

    descriptor = {
        "task_id": task.task_id,
        "mechanism": arm.name,
        "task_class": task_class,
        "size_stratum": size,
        "tip_distance": tip_distance,
        "goal_radius": float(task.goal_radius),
        "goal_center": task.goal_center.tolist(),
        "start_q": task.start_q.tolist(),
        "start_tip": task.start_tip.tolist(),
        "goal_representation": contract.goal_representation.kind,
        "goal_sample_points": [x.tolist() for x in task.goal_points],
        "goal_sample_point_ids": list(task.goal_point_ids),
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
            "graph": {
                "goal_set_short_circuit": reason,
                "goal_set_candidate_count": 0,
            }
        },
        provenance=ResultProvenance(
            architecture_version=3,
            planner_id=planner_id,
        ),
        state_validity_checks=1,
        motion_validity_checks=0,
    )


def _solve_lattice_goal_set(
    *,
    arm: SamplingSmokeArm,
    task: ResolvedFreeSpaceTaskV2,
    problem: Any,
    task_class: str,
    candidates: list[Any],
    lattice_arm: Any,
) -> PlanningResult:
    planner_id = "lattice_goal_set_dijkstra_eight_integrated"
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
    if not candidates:
        return _short_circuit_result(
            problem=problem,
            task_class=TASK_INVALID_UNREPRESENTABLE,
            planner_id=planner_id,
            status=PlanningStatus.INVALID,
            reason="no_represented_goal_candidate",
        )

    attempts: list[dict[str, Any]] = []
    attempt_results: list[PlanningResult] = []
    successes: list[tuple[float, int, PlanningResult]] = []
    wall_start = time.perf_counter()
    for idx, cand in enumerate(candidates):
        exact = replace(
            problem,
            goal=ExactOutputGoal(
                q_goal=np.asarray(cand.state.q, dtype=np.float64).copy()
            ),
        )
        planner = GraphSearchPlanner(
            graph=lattice_arm.graph,
            algorithm="dijkstra",
            edge_cost_mode="integrated",
            allow_query_overlay=True,
        )
        result = planner.solve(exact)
        attempt_results.append(result)
        attempts.append(
            {
                "candidate_index": idx,
                "goal_sample_id": cand.provenance.get("goal_sample_id"),
                "status": str(result.status),
                "objective_cost": result.objective_cost,
                "query_time_s": result.query_time_s,
                "total_wall_time_s": result.total_wall_time_s,
            }
        )
        if result.status is PlanningStatus.SUCCESS and result.objective_cost is not None:
            successes.append((float(result.objective_cost), idx, result))

    total_wall = time.perf_counter() - wall_start
    query_total = float(
        sum(float(r.query_time_s or 0.0) for r in attempt_results)
    )
    preprocessing_total = float(
        sum(float(r.preprocessing_time_s or 0.0) for r in attempt_results)
    )
    state_checks = int(
        sum(int(r.state_validity_checks or 0) for r in attempt_results)
    )
    motion_checks = int(
        sum(int(r.motion_validity_checks or 0) for r in attempt_results)
    )

    if not successes:
        return PlanningResult(
            status=PlanningStatus.UNSOLVED,
            trajectory=None,
            selected_goal_state=None,
            total_wall_time_s=total_wall,
            preprocessing_time_s=preprocessing_total,
            query_time_s=query_total,
            objective_cost=None,
            path_length_u=None,
            path_length_q=None,
            path_length_x=None,
            task_class=task_class,
            final_goal_residual=problem.goal.residual(problem.start),
            planner_metrics={
                "graph": {
                    "goal_set_candidate_count": len(candidates),
                    "goal_set_attempts": attempts,
                    "goal_set_successes": 0,
                }
            },
            provenance=ResultProvenance(
                architecture_version=3,
                planner_id=planner_id,
            ),
            state_validity_checks=state_checks,
            motion_validity_checks=motion_checks,
        )

    _, selected_idx, chosen = min(successes, key=lambda item: item[0])
    selected = chosen.selected_goal_state
    graph_metrics = dict(chosen.planner_metrics.get("graph", {}))
    graph_metrics.update(
        {
            "goal_set_candidate_count": len(candidates),
            "goal_set_attempts": attempts,
            "goal_set_successes": len(successes),
            "selected_goal_candidate_index": selected_idx,
            "selected_goal_sample_id": candidates[selected_idx].provenance.get(
                "goal_sample_id"
            ),
        }
    )
    return PlanningResult(
        status=PlanningStatus.SUCCESS,
        trajectory=chosen.trajectory,
        selected_goal_state=selected,
        total_wall_time_s=total_wall,
        setup_time_s=chosen.setup_time_s,
        preprocessing_time_s=preprocessing_total,
        query_time_s=query_total,
        postprocessing_time_s=chosen.postprocessing_time_s,
        objective_cost=chosen.objective_cost,
        path_length_u=chosen.path_length_u,
        path_length_q=chosen.path_length_q,
        path_length_x=chosen.path_length_x,
        task_class=task_class,
        final_goal_residual=(
            None if selected is None else problem.goal.residual(selected)
        ),
        planner_metrics={"graph": graph_metrics},
        provenance=ResultProvenance(
            architecture_version=3,
            code_revision=chosen.provenance.code_revision,
            planner_id=planner_id,
            extras={
                **dict(chosen.provenance.extras),
                "represented_goal_set": True,
            },
        ),
        state_validity_checks=state_checks,
        motion_validity_checks=motion_checks,
        collision_checks=chosen.collision_checks,
    )


def _solve_native(
    planner_name: PlannerNameV2,
    *,
    arm: SamplingSmokeArm,
    task: ResolvedFreeSpaceTaskV2,
    contract: FreeSpaceEvidenceContractV2,
    problem: Any,
    task_class: str,
    candidates: list[Any],
    lattice_arm: Any | None,
    seed: int | None,
) -> PlanningResult:
    generator = goal_generator_v2(arm, task)
    max_candidates = contract.goal_representation.max_candidates
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
    if planner_name == "lattice_dijkstra_eight_integrated":
        assert lattice_arm is not None
        return _solve_lattice_goal_set(
            arm=arm,
            task=task,
            problem=problem,
            task_class=task_class,
            candidates=candidates,
            lattice_arm=lattice_arm,
        )
    if seed is None:
        raise ValueError(f"{planner_name} requires a frozen seed")
    if planner_name == "prm":
        return PRMPlanner(
            seed=seed,
            n_samples=80,
            k_neighbors=10,
            max_edge_u=1.25,
            max_goal_candidates=max_candidates,
            goal_generator=generator,
        ).solve(problem)
    if planner_name == "rrt_connect":
        return RRTConnectPlanner(
            seed=seed,
            max_iterations=800,
            step_u=0.35,
            goal_bias=0.1,
            max_goal_candidates=max_candidates,
            goal_generator=generator,
        ).solve(problem)
    raise ValueError(f"{planner_name!r} is not an in-process native planner")


def _solve_ompl_isolated(
    *,
    contract: FreeSpaceEvidenceContractV2,
    task_id: str,
    mechanism: str,
    planner_name: str,
    seed: int,
    solve_time_s: float,
) -> tuple[PlanningResult | None, str | None]:
    if not is_ompl_available():
        return None, "ompl_unavailable"
    if not contract.ompl_process_isolation:
        raise ValueError("corrected V3.6 contract requires OMPL process isolation")

    request = {
        "contract_path": str(contract.source_path),
        "task_id": task_id,
        "mechanism": mechanism,
        "planner": planner_name,
        "seed": int(seed),
        "solve_time_s": float(solve_time_s),
    }
    with tempfile.TemporaryDirectory(prefix="v3_6_ompl_") as tmp:
        tmp_path = Path(tmp)
        req_path = tmp_path / "request.json"
        out_path = tmp_path / "result.json"
        req_path.write_text(json.dumps(request), encoding="utf-8")
        cmd = [
            sys.executable,
            "-m",
            "inequality_mechanisms.benchmarks.ompl_process_worker_v3_6",
            "--request",
            str(req_path),
            "--out",
            str(out_path),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            # OMPL PRM evaluates the frozen goal set sequentially (one GoalState
            # per attempt) to avoid a nanobind multi-GoalStates hang.
            timeout=max(
                60.0,
                float(contract.goal_representation.max_candidates)
                * (float(solve_time_s) + 3.0)
                + 30.0,
            ),
            env=os.environ.copy(),
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "OMPL isolated worker failed "
                f"({planner_name}, {task_id}, {mechanism}, seed={seed}): "
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    result = planning_result_from_dict(payload["result"])
    return result, None


def _result_row(
    *,
    contract: FreeSpaceEvidenceContractV2,
    task: ResolvedFreeSpaceTaskV2,
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


def run_free_space_evidence_v2(
    *,
    contract: FreeSpaceEvidenceContractV2 | None = None,
    deterministic_planners: tuple[DeterministicPlanner, ...] = (
        DETERMINISTIC_PLANNERS
    ),
    stochastic_planners: tuple[StochasticPlanner, ...] = STOCHASTIC_PLANNERS,
    seeds: tuple[int, ...] | None = None,
    ompl_solve_time_s: float = 1.0,
    lattice_shape: tuple[int, int] = (8, 8),
    task_ids: tuple[str, ...] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contract = contract if contract is not None else load_free_space_bank_v2()
    seeds = contract.stochastic_seeds if seeds is None else tuple(seeds)
    arms = build_bank_arms(contract.base_bank)
    resolved_all = resolve_free_space_tasks_v2(contract, arms=arms)
    if task_ids is not None:
        wanted = set(task_ids)
        resolved = tuple(t for t in resolved_all if t.task_id in wanted)
        if not resolved:
            raise ValueError("task_ids filtered to an empty task list")
    else:
        resolved = resolved_all

    lattice_arms: dict[str, Any] = {}
    if "lattice_dijkstra_eight_integrated" in deterministic_planners:
        lattice_arms = build_paired_lattice_arms(
            shape=lattice_shape,
            connectivity=LatticeConnectivity.CHEBYSHEV_1,
        )

    class_by_key: dict[tuple[str, str], str] = {}
    desc_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    cands_by_key: dict[tuple[str, str], list[Any]] = {}
    for task in resolved:
        shared_size: str | None = None
        for mech in contract.base_bank.mechanisms:
            arm = arms[mech]
            task_class, desc, cands = _presearch(arm, task, contract)
            class_by_key[(task.task_id, mech)] = task_class
            desc_by_key[(task.task_id, mech)] = desc
            cands_by_key[(task.task_id, mech)] = cands
            if shared_size is None:
                shared_size = str(desc["size_stratum"])
            elif shared_size != str(desc["size_stratum"]):
                raise RuntimeError(
                    f"{task.task_id}: paired size stratum differs despite shared start"
                )

    paired_by_task: dict[str, str] = {}
    for task in resolved:
        paired_by_task[task.task_id] = paired_stratum_from_classes(
            class_by_key[(task.task_id, "fourbar")],
            class_by_key[(task.task_id, "gearbox")],
        )
        fb_cands = cands_by_key[(task.task_id, "fourbar")]
        gb_cands = cands_by_key[(task.task_id, "gearbox")]
        fb_ids = [
            str(c.provenance.get("goal_sample_id")) for c in fb_cands
        ]
        gb_ids = [
            str(c.provenance.get("goal_sample_id")) for c in gb_cands
        ]
        if fb_ids != gb_ids:
            raise RuntimeError(
                f"{task.task_id}: represented goal-sample id ordering differs "
                "between paired mechanisms"
            )
        if len(fb_cands) != len(gb_cands):
            raise RuntimeError(
                f"{task.task_id}: represented goal-candidate count differs "
                "between paired mechanisms"
            )
        for fb_c, gb_c in zip(fb_cands, gb_cands):
            if not np.allclose(fb_c.state.q, gb_c.state.q, rtol=0.0, atol=1e-9):
                raise RuntimeError(
                    f"{task.task_id}: represented goal-state q ordering differs "
                    "between paired mechanisms beyond tolerance"
                )

    rows: list[dict[str, Any]] = []
    for task in resolved:
        paired = paired_by_task[task.task_id]
        for mech in contract.base_bank.mechanisms:
            arm = arms[mech]
            problem = build_problem_v2(arm, task)
            task_class = class_by_key[(task.task_id, mech)]
            desc = desc_by_key[(task.task_id, mech)]
            cands = cands_by_key[(task.task_id, mech)]
            lattice_arm = lattice_arms.get(mech)

            for planner_name in deterministic_planners:
                result = _solve_native(
                    planner_name,
                    arm=arm,
                    task=task,
                    contract=contract,
                    problem=problem,
                    task_class=task_class,
                    candidates=cands,
                    lattice_arm=lattice_arm,
                    seed=None,
                )
                rows.append(
                    _result_row(
                        contract=contract,
                        task=task,
                        mechanism=mech,
                        planner_name=planner_name,
                        descriptors=desc,
                        paired_stratum=paired,
                        result=result,
                        seed=None,
                        repetition_index=0,
                        stochastic=False,
                        process_isolated=False,
                    )
                )

            for repetition_index, seed in enumerate(seeds):
                for planner_name in stochastic_planners:
                    process_isolated = planner_name.startswith("ompl_")
                    skipped = None
                    if process_isolated:
                        result, skipped = _solve_ompl_isolated(
                            contract=contract,
                            task_id=task.task_id,
                            mechanism=mech,
                            planner_name=planner_name,
                            seed=seed,
                            solve_time_s=ompl_solve_time_s,
                        )
                    else:
                        result = _solve_native(
                            planner_name,
                            arm=arm,
                            task=task,
                            contract=contract,
                            problem=problem,
                            task_class=task_class,
                            candidates=cands,
                            lattice_arm=lattice_arm,
                            seed=seed,
                        )
                    rows.append(
                        _result_row(
                            contract=contract,
                            task=task,
                            mechanism=mech,
                            planner_name=planner_name,
                            descriptors=desc,
                            paired_stratum=paired,
                            result=result,
                            seed=seed,
                            repetition_index=repetition_index,
                            stochastic=True,
                            process_isolated=process_isolated,
                            skipped=skipped,
                        )
                    )

    resolved_dict = {
        "contract": {
            "bank_id": contract.bank_id,
            "reference_mechanism": contract.reference_mechanism,
            "stochastic_seeds": list(seeds),
        },
        "tasks": [
            {
                "task_id": task.task_id,
                "start_q": task.start_q.tolist(),
                "start_tip": task.start_tip.tolist(),
                "goal_center": task.goal_center.tolist(),
                "goal_radius": task.goal_radius,
                "goal_point_ids": list(task.goal_point_ids),
                "goal_points": [x.tolist() for x in task.goal_points],
            }
            for task in resolved
        ],
    }
    return rows, resolved_dict


def evidence_manifest_v2(
    rows: list[dict[str, Any]],
    *,
    contract: FreeSpaceEvidenceContractV2,
    implementation_revision: str | None,
    ompl_solve_time_s: float,
) -> dict[str, Any]:
    status_counts: dict[str, int] = defaultdict(int)
    skip_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.get("skipped"):
            skip_counts[str(row["skipped"])] += 1
        else:
            status_counts[str(row.get("status"))] += 1
    return {
        "snapshot_schema_version": 2,
        "snapshot_id": "v3_6_free_space_v2",
        "architecture_version": 3,
        "bank_id": contract.bank_id,
        "base_bank_id": contract.base_bank.bank_id,
        "implementation_revision": implementation_revision,
        "generated_at_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        ),
        "stochastic_seeds": list(contract.stochastic_seeds),
        "ompl_process_isolation": contract.ompl_process_isolation,
        "ompl_solve_time_s": float(ompl_solve_time_s),
        "ompl_available": bool(is_ompl_available()),
        "n_rows": len(rows),
        "status_counts": dict(status_counts),
        "skip_counts": dict(skip_counts),
        "scope_note": (
            "Corrected bounded free-space representation/optimality evidence; "
            "not population inference."
        ),
    }


__all__ = [
    "DETERMINISTIC_PLANNERS",
    "STOCHASTIC_PLANNERS",
    "evidence_manifest_v2",
    "run_free_space_evidence_v2",
]
