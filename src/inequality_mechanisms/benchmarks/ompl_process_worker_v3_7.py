"""Fresh-process OMPL worker for Sprint V3.7 planar 3R evidence."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from inequality_mechanisms.adapters.ompl import (
    OmplPRMPlanner,
    OmplRRTConnectPlanner,
)
from inequality_mechanisms.benchmarks.free_space_bank_3r import (
    build_bank_arms_3r,
    build_problem_3r,
    goal_generator_3r,
    load_free_space_bank_3r,
    max_candidates_3r,
    resolve_free_space_tasks_3r,
)
from inequality_mechanisms.core.goals import GoalConstraint, GoalSamplingRequest
from inequality_mechanisms.core.results import PlanningResult, PlanningStatus
from inequality_mechanisms.core.serialize import planning_result_to_dict
from inequality_mechanisms.core.state import StateCandidate


@dataclass(frozen=True, slots=True)
class _SingleCandidateGenerator:
    """Yield exactly one frozen goal candidate (OMPL PRM multi-goal workaround)."""

    candidate: StateCandidate

    def generate(
        self,
        robot: Any,
        goal: GoalConstraint,
        request: GoalSamplingRequest,
    ) -> tuple[StateCandidate, ...]:
        return (self.candidate,)


def _merge_sequential_prm(
    results: list[PlanningResult],
    *,
    wall_s: float,
) -> PlanningResult:
    """Pick the best exact success among sequential single-goal PRM solves."""
    successes = [
        r
        for r in results
        if r.status == PlanningStatus.SUCCESS and r.objective_cost is not None
    ]
    if successes:
        best = min(successes, key=lambda r: float(r.objective_cost))
    elif results:
        best = results[-1]
    else:
        raise RuntimeError("OMPL PRM sequential solve produced no results")

    metrics = dict(best.planner_metrics)
    metrics["ompl_prm_sequential_goal_states"] = True
    metrics["ompl_prm_sequential_attempts"] = len(results)
    metrics["ompl_prm_sequential_successes"] = len(successes)
    extras = dict(best.provenance.extras)
    extras["ompl_prm_sequential_goal_states"] = True
    extras["ompl_prm_multi_goalstates_workaround"] = (
        "nanobind OMPL PRM hangs with GoalStates size>1; "
        "V3.7 evaluates the frozen represented set via sequential single-goal solves"
    )
    return replace(
        best,
        total_wall_time_s=float(wall_s),
        planner_metrics=metrics,
        provenance=replace(best.provenance, extras=extras),
        state_validity_checks=sum(
            (r.state_validity_checks or 0) for r in results
        ),
        motion_validity_checks=sum(
            (r.motion_validity_checks or 0) for r in results
        ),
    )


def _solve_ompl_prm_sequential(
    *,
    problem: Any,
    generator: Any,
    seed: int,
    solve_time_s: float,
    max_candidates: int,
) -> PlanningResult:
    """Avoid multi-GoalStates PRM hang by solving one represented goal at a time."""
    request = GoalSamplingRequest(max_candidates=max_candidates)
    candidates = list(generator.generate(problem.robot, problem.goal, request))
    if not candidates:
        return OmplPRMPlanner(
            seed=seed,
            goal_generator=generator,
            max_goal_candidates=1,
            solve_time_s=solve_time_s,
        ).solve(problem)

    t0 = time.perf_counter()
    results: list[PlanningResult] = []
    for cand in candidates:
        results.append(
            OmplPRMPlanner(
                seed=seed,
                goal_generator=_SingleCandidateGenerator(cand),
                max_goal_candidates=1,
                solve_time_s=solve_time_s,
            ).solve(problem)
        )
    return _merge_sequential_prm(results, wall_s=time.perf_counter() - t0)


def run_request(request: dict) -> dict:
    contract = load_free_space_bank_3r(Path(request["contract_path"]))
    arms = build_bank_arms_3r(contract)
    tasks = {
        t.task_id: t for t in resolve_free_space_tasks_3r(contract, arms=arms)
    }
    task = tasks[str(request["task_id"])]
    mech = str(request["mechanism"])
    arm = arms[mech]
    problem = build_problem_3r(arm, task)
    generator = goal_generator_3r(arm, task, contract)
    seed = int(request["seed"])
    solve_time_s = float(request["solve_time_s"])
    max_candidates = max_candidates_3r(task, contract)

    planner_name = str(request["planner"])
    if planner_name == "ompl_prm":
        result = _solve_ompl_prm_sequential(
            problem=problem,
            generator=generator,
            seed=seed,
            solve_time_s=solve_time_s,
            max_candidates=max_candidates,
        )
    elif planner_name == "ompl_rrt_connect":
        result = OmplRRTConnectPlanner(
            seed=seed,
            goal_generator=generator,
            max_goal_candidates=max_candidates,
            solve_time_s=solve_time_s,
        ).solve(problem)
    else:
        raise ValueError(f"unsupported OMPL worker planner {planner_name!r}")

    return {
        "process_isolated": True,
        "planner": planner_name,
        "seed": seed,
        "result": planning_result_to_dict(result),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    payload = run_request(request)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
