"""Fresh-process OMPL worker for corrected Sprint V3.6 evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from inequality_mechanisms.adapters.ompl import (
    OmplPRMPlanner,
    OmplRRTConnectPlanner,
)
from inequality_mechanisms.benchmarks.free_space_bank import build_bank_arms
from inequality_mechanisms.benchmarks.free_space_bank_v2 import (
    build_problem_v2,
    goal_generator_v2,
    load_free_space_bank_v2,
    resolve_free_space_tasks_v2,
)
from inequality_mechanisms.core.serialize import planning_result_to_dict


def run_request(request: dict) -> dict:
    contract = load_free_space_bank_v2(Path(request["contract_path"]))
    arms = build_bank_arms(contract.base_bank)
    tasks = {
        t.task_id: t for t in resolve_free_space_tasks_v2(contract, arms=arms)
    }
    task = tasks[str(request["task_id"])]
    mech = str(request["mechanism"])
    arm = arms[mech]
    problem = build_problem_v2(arm, task)
    generator = goal_generator_v2(arm, task)
    seed = int(request["seed"])
    solve_time_s = float(request["solve_time_s"])
    max_candidates = contract.goal_representation.max_candidates

    planner_name = str(request["planner"])
    if planner_name == "ompl_prm":
        planner = OmplPRMPlanner(
            seed=seed,
            goal_generator=generator,
            max_goal_candidates=max_candidates,
            solve_time_s=solve_time_s,
        )
    elif planner_name == "ompl_rrt_connect":
        planner = OmplRRTConnectPlanner(
            seed=seed,
            goal_generator=generator,
            max_goal_candidates=max_candidates,
            solve_time_s=solve_time_s,
        )
    else:
        raise ValueError(f"unsupported OMPL worker planner {planner_name!r}")

    result = planner.solve(problem)
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
