"""Multi-planner free-space evidence runner (Sprint V3.6 / V3-603)."""

from __future__ import annotations

import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

import numpy as np

from inequality_mechanisms.adapters import GraphSearchPlanner
from inequality_mechanisms.adapters.ompl import is_ompl_available
from inequality_mechanisms.benchmarks.free_space_bank import (
    FreeSpaceBankTask,
    FreeSpaceTaskBank,
    build_bank_arms,
    build_cartesian_problem,
    load_free_space_bank,
)
from inequality_mechanisms.benchmarks.free_space_strata import (
    classify_problem_presearch,
    paired_stratum_from_classes,
    presearch_descriptors,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import build_paired_lattice_arms
from inequality_mechanisms.benchmarks.smoke_sampling_2r import (
    SMOKE_SEED,
    SamplingSmokeArm,
)
from inequality_mechanisms.core.goals import ExactOutputGoal
from inequality_mechanisms.core.local_motion import (
    InputLinearMotion,
    OutputLinearMotion,
)
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningResult, PlanningStatus
from inequality_mechanisms.graphs.topology import LatticeConnectivity
from inequality_mechanisms.kinematics.planar_2r_goals import CartesianDiskGoalGenerator
from inequality_mechanisms.planners.direct.input_linear import InputLinearDirectPlanner
from inequality_mechanisms.planners.direct.output_linear import OutputLinearDirectPlanner
from inequality_mechanisms.planners.roadmap import PRMPlanner
from inequality_mechanisms.planners.tree import RRTConnectPlanner

PlannerName = Literal[
    "input_linear",
    "output_linear",
    "lattice_dijkstra_eight_integrated",
    "prm",
    "rrt_connect",
    "ompl_prm",
    "ompl_rrt_connect",
]

DEFAULT_PLANNERS: tuple[PlannerName, ...] = (
    "input_linear",
    "output_linear",
    "lattice_dijkstra_eight_integrated",
    "prm",
    "rrt_connect",
    "ompl_prm",
    "ompl_rrt_connect",
)


def _git_revision() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = proc.stdout.strip()
    return value or None


def _result_row(
    *,
    bank: FreeSpaceTaskBank,
    task: FreeSpaceBankTask,
    mechanism: str,
    planner_name: str,
    descriptors: dict[str, Any],
    paired_stratum: str,
    result: PlanningResult | None,
    skipped: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "bank_id": bank.bank_id,
        "task_id": task.task_id,
        "mechanism": mechanism,
        "planner": planner_name,
        "paired_stratum": paired_stratum,
        "size_stratum": descriptors.get("size_stratum"),
        "task_class": descriptors.get("task_class"),
        "tip_distance": descriptors.get("tip_distance"),
        "presearch": descriptors,
        "skipped": skipped,
        "status": None if result is None else str(result.status),
        "objective_cost": None if result is None else result.objective_cost,
        "path_length_u": None if result is None else result.path_length_u,
        "path_length_q": None if result is None else result.path_length_q,
        "query_time_s": None if result is None else result.query_time_s,
        "total_wall_time_s": None if result is None else result.total_wall_time_s,
        "preprocessing_time_s": None if result is None else result.preprocessing_time_s,
        "state_validity_checks": None if result is None else result.state_validity_checks,
        "motion_validity_checks": None
        if result is None
        else result.motion_validity_checks,
        "planner_metrics": None if result is None else dict(result.planner_metrics),
        "provenance_planner_id": None
        if result is None
        else result.provenance.planner_id,
        "provenance_extras": None
        if result is None
        else dict(result.provenance.extras),
        "architecture_version": 3,
    }
    return row


def _lattice_problem_from_cartesian(
    cartesian: PlanningProblem,
    goal_candidates: list[Any],
) -> PlanningProblem | None:
    """Map a Cartesian disk task to ExactOutputGoal for lattice search."""
    if not goal_candidates:
        return None
    selected = goal_candidates[0]
    return replace(
        cartesian,
        goal=ExactOutputGoal(q_goal=np.asarray(selected.q, dtype=np.float64).copy()),
    )


def _solve_with_planner(
    planner_name: PlannerName,
    *,
    arm: SamplingSmokeArm,
    problem: PlanningProblem,
    goal_candidates: list[Any],
    lattice_arms: dict[str, Any],
    seed: int,
    ompl_solve_time_s: float,
) -> tuple[PlanningResult | None, str | None]:
    """Solve one planner; return ``(result, skip_reason)``."""
    fk = arm.robot.planar_fk
    generator = None if fk is None else CartesianDiskGoalGenerator(planar_fk=fk)

    if planner_name == "input_linear":
        if generator is None:
            return None, "no_goal_generator"
        return InputLinearDirectPlanner(goal_generator=generator).solve(problem), None
    if planner_name == "output_linear":
        if generator is None:
            return None, "no_goal_generator"
        out_problem = replace(
            problem,
            local_motion=OutputLinearMotion(robot=arm.robot, n_samples=12),
        )
        return (
            OutputLinearDirectPlanner(goal_generator=generator).solve(out_problem),
            None,
        )
    if planner_name == "lattice_dijkstra_eight_integrated":
        lattice_arm = lattice_arms[arm.name]
        lattice_problem = _lattice_problem_from_cartesian(problem, goal_candidates)
        if lattice_problem is None:
            return None, "no_goal_candidate_for_lattice"
        planner = GraphSearchPlanner(
            graph=lattice_arm.graph,
            algorithm="dijkstra",
            edge_cost_mode="integrated",
            allow_query_overlay=True,
        )
        return planner.solve(lattice_problem), None
    if planner_name == "prm":
        return (
            PRMPlanner(
                seed=seed,
                n_samples=80,
                k_neighbors=10,
                max_edge_u=1.25,
                goal_generator=generator,
            ).solve(problem),
            None,
        )
    if planner_name == "rrt_connect":
        return (
            RRTConnectPlanner(
                seed=seed,
                max_iterations=800,
                step_u=0.35,
                goal_bias=0.1,
                goal_generator=generator,
            ).solve(problem),
            None,
        )
    if planner_name in ("ompl_prm", "ompl_rrt_connect"):
        if not is_ompl_available():
            return None, "ompl_unavailable"
        from inequality_mechanisms.adapters.ompl import (
            OmplPRMPlanner,
            OmplRRTConnectPlanner,
        )

        if planner_name == "ompl_prm":
            return (
                OmplPRMPlanner(
                    seed=seed,
                    goal_generator=generator,
                    solve_time_s=ompl_solve_time_s,
                ).solve(problem),
                None,
            )
        return (
            OmplRRTConnectPlanner(
                seed=seed,
                goal_generator=generator,
                solve_time_s=ompl_solve_time_s,
            ).solve(problem),
            None,
        )
    raise ValueError(f"unknown planner {planner_name!r}")


def run_free_space_evidence(
    *,
    bank: FreeSpaceTaskBank | None = None,
    planners: tuple[PlannerName, ...] = DEFAULT_PLANNERS,
    seed: int = SMOKE_SEED,
    ompl_solve_time_s: float = 2.0,
    lattice_shape: tuple[int, int] = (8, 8),
    task_ids: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Run the free-space evidence pack; return row dictionaries.

    Parameters
    ----------
    task_ids
        Optional subset of bank task ids (for tests / focused reruns).
    """
    bank = bank if bank is not None else load_free_space_bank()
    tasks = bank.tasks
    if task_ids is not None:
        wanted = set(task_ids)
        tasks = tuple(t for t in bank.tasks if t.task_id in wanted)
        if not tasks:
            raise ValueError("task_ids filtered to an empty task list")
    arms = build_bank_arms(bank)
    need_lattice = "lattice_dijkstra_eight_integrated" in planners
    lattice_arms: dict[str, Any] = {}
    if need_lattice:
        lattice_arms = build_paired_lattice_arms(
            shape=lattice_shape,
            connectivity=LatticeConnectivity.CHEBYSHEV_1,
        )

    # Pre-search classification per mechanism-task (shared across planners).
    class_by_key: dict[tuple[str, str], tuple[str, dict[str, Any], list[Any]]] = {}
    descriptors_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for task in tasks:
        for mech in bank.mechanisms:
            arm = arms[mech]
            problem = build_cartesian_problem(arm, task)
            fk = arm.robot.planar_fk
            generator = (
                None if fk is None else CartesianDiskGoalGenerator(planar_fk=fk)
            )
            task_class, extras, cands = classify_problem_presearch(
                problem, goal_generator=generator
            )
            class_by_key[(task.task_id, mech)] = (task_class, extras, cands)
            descriptors_by_key[(task.task_id, mech)] = presearch_descriptors(
                arm,
                task,
                bank,
                problem,
                task_class=task_class,
                class_extras=extras,
                goal_candidates=cands,
            )

    paired_by_task: dict[str, str] = {}
    for task in tasks:
        fb = class_by_key[(task.task_id, "fourbar")][0]
        gb = class_by_key[(task.task_id, "gearbox")][0]
        paired_by_task[task.task_id] = paired_stratum_from_classes(fb, gb)

    rows: list[dict[str, Any]] = []
    for task in tasks:
        for mech in bank.mechanisms:
            arm = arms[mech]
            problem = build_cartesian_problem(arm, task)
            _tc, _ex, cands = class_by_key[(task.task_id, mech)]
            descriptors = descriptors_by_key[(task.task_id, mech)]
            paired = paired_by_task[task.task_id]
            for planner_name in planners:
                result, skipped = _solve_with_planner(
                    planner_name,
                    arm=arm,
                    problem=problem,
                    goal_candidates=cands,
                    lattice_arms=lattice_arms,
                    seed=seed,
                    ompl_solve_time_s=ompl_solve_time_s,
                )
                rows.append(
                    _result_row(
                        bank=bank,
                        task=task,
                        mechanism=mech,
                        planner_name=planner_name,
                        descriptors=descriptors,
                        paired_stratum=paired,
                        result=result,
                        skipped=skipped,
                    )
                )
    return rows


def evidence_manifest(
    rows: list[dict[str, Any]],
    *,
    bank: FreeSpaceTaskBank,
    seed: int,
    ompl_solve_time_s: float,
    planners: tuple[str, ...],
) -> dict[str, Any]:
    """Build a review manifest for the evidence package."""
    status_counts: dict[str, int] = {}
    skip_counts: dict[str, int] = {}
    for row in rows:
        if row.get("skipped"):
            key = str(row["skipped"])
            skip_counts[key] = skip_counts.get(key, 0) + 1
            continue
        st = str(row.get("status"))
        status_counts[st] = status_counts.get(st, 0) + 1
    return {
        "snapshot_schema_version": 1,
        "snapshot_id": "v3_6_free_space",
        "architecture_version": 3,
        "bank_id": bank.bank_id,
        "bank_path": _relative_bank_path(bank.source_path),
        "code_revision": _git_revision(),
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": int(seed),
        "ompl_solve_time_s": float(ompl_solve_time_s),
        "ompl_available": bool(is_ompl_available()),
        "planners": list(planners),
        "n_tasks": len(bank.tasks),
        "n_mechanisms": len(bank.mechanisms),
        "n_rows": len(rows),
        "status_counts": status_counts,
        "skip_counts": skip_counts,
        "ompl_process_isolation_note": (
            "OMPL seed setting is process-global best effort "
            "(reproducible_with_seed=False); use process isolation for "
            "frozen OMPL repetitions."
        ),
        "scope_note": (
            "Bounded free-space planner evidence only; not population inference."
        ),
    }


def _relative_bank_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


__all__ = [
    "DEFAULT_PLANNERS",
    "PlannerName",
    "evidence_manifest",
    "run_free_space_evidence",
]
