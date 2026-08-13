"""RRT-Connect planner (Sprint V3.4 / V3-403)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from inequality_mechanisms.benchmarks.classification import (
    TASK_ALREADY_SATISFIED,
    TASK_INVALID_UNREPRESENTABLE,
    classify_direct_attempt,
)
from inequality_mechanisms.core.goal_residuals import (
    GoalResidualReport,
    build_goal_residual_report,
)
from inequality_mechanisms.core.goals import GoalStateGenerator
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.planner import PlannerCapabilities, PlannerLifecycle
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
    Trajectory,
)
from inequality_mechanisms.core.state import PhysicalState, StateCandidate
from inequality_mechanisms.planners.sampling_rng import (
    SeededRun,
    make_generator,
    seed_provenance_extras,
)
from inequality_mechanisms.planners.sampling_space import (
    actuator_bounds,
    direct_connector_available,
    match_selected_candidate,
    path_cost_u,
    path_length_q,
    path_length_x,
    resolve_connector,
    sample_state_uniform,
    select_goal_candidates,
    try_connect,
)


def _goal_usable(problem: PlanningProblem) -> bool:
    try:
        _ = problem.goal.residual(problem.start)
        return True
    except (NotImplementedError, ValueError, TypeError):
        return False


@dataclass
class _TreeNode:
    state: PhysicalState
    parent: int | None


@dataclass(frozen=True, slots=True)
class RRTConnectPlanner:
    """Bidirectional RRT-Connect in certified actuator space.

    Not plain RRT and not RRT* (no rewiring). Exact start is the start-tree
    root; a selected goal candidate roots the goal tree.

    Opt-in ``trace_sink`` records tree growth events for audits without
    changing ordinary planner metrics.
    """

    seed: int = 0
    max_iterations: int = 500
    step_u: float = 0.25
    goal_bias: float = 0.05
    max_goal_candidates: int = 8
    goal_generator: GoalStateGenerator | None = None
    repetition_index: int = 0
    code_revision: str | None = None
    lifecycle: PlannerLifecycle = PlannerLifecycle.SINGLE_QUERY
    trace_sink: Any | None = None

    @property
    def planner_id(self) -> str:
        """Stable planner registry name."""
        return "rrt_connect"

    @property
    def capabilities(self) -> PlannerCapabilities:
        """Declare stochastic but seed-reproducible tree capabilities."""
        return PlannerCapabilities(
            deterministic=False,
            reproducible_with_seed=True,
            multi_query=False,
            optimizing=False,
            probabilistically_complete=None,
            asymptotically_optimal=None,
            requires_metric_space=True,
            supports_optimization_objective=True,
            supports_goal_region=True,
            supports_goal_sampling=True,
            supports_multi_start=False,
            supports_path_constraints=False,
            supports_approximate_solution=False,
            supports_incremental_solutions=False,
            reports_graph_exploration=False,
            supports_exact_start=True,
        )

    def solve(self, problem: PlanningProblem) -> PlanningResult:
        """Classify then grow bidirectional trees until connect or budget."""
        if not isinstance(problem.objective, ActuatorTravelObjective):
            raise ValueError(
                "RRTConnectPlanner currently supports ActuatorTravelObjective only"
            )

        t0 = time.perf_counter()
        run = SeededRun(seed=self.seed, repetition_index=self.repetition_index)
        rng = make_generator(run.seed, repetition_index=run.repetition_index)
        extras = seed_provenance_extras(run, planner_id=self.planner_id)

        start_valid = problem.scene.state_is_valid(problem.start)
        goal_usable = _goal_usable(problem)
        already = bool(goal_usable and problem.goal.satisfied(problem.start))

        def _finish(
            *,
            status: PlanningStatus,
            task_class: str,
            trajectory: Trajectory | None,
            selected: PhysicalState | None,
            cost: float | None,
            length_u: float | None,
            length_q: float | None,
            length_x: float | None = None,
            metrics: dict[str, Any],
            query_s: float | None = None,
            residual_state: PhysicalState | None = None,
            candidate: StateCandidate | None = None,
            state_checks: int | None = None,
            motion_checks: int | None = None,
        ) -> PlanningResult:
            total = time.perf_counter() - t0
            report: GoalResidualReport | None = None
            residual = None
            state_for_residual = residual_state if residual_state is not None else selected
            if state_for_residual is not None and goal_usable:
                report = build_goal_residual_report(
                    problem.goal,
                    state_for_residual,
                    candidate=candidate,
                )
                residual = report.physical
            return PlanningResult(
                status=status,
                trajectory=trajectory,
                selected_goal_state=selected,
                selected_goal_candidate=candidate,
                total_wall_time_s=total,
                query_time_s=query_s if query_s is not None else total,
                objective_cost=cost,
                path_length_u=length_u,
                path_length_q=length_q,
                path_length_x=length_x,
                task_class=task_class,
                final_goal_residual=residual,
                goal_residuals=report,
                planner_metrics=metrics,
                provenance=ResultProvenance(
                    architecture_version=3,
                    code_revision=self.code_revision,
                    planner_id=self.planner_id,
                    extras=extras,
                ),
                state_validity_checks=state_checks,
                motion_validity_checks=motion_checks,
            )

        base_metrics: dict[str, Any] = {
            "tree": {
                "iterations": 0,
                "extensions": 0,
                "nn_ops": 0,
                "rewires": 0,
                "seed": int(self.seed),
                "repetition_index": int(self.repetition_index),
                "direct_connector_policy": str(
                    getattr(
                        problem.local_motion,
                        "model_id",
                        type(problem.local_motion).__name__,
                    )
                ),
                "direct_connector_available": None,
            }
        }

        if not start_valid or not goal_usable:
            return _finish(
                status=PlanningStatus.INVALID,
                task_class=classify_direct_attempt(
                    start_valid=start_valid,
                    goal_usable=goal_usable,
                    already_satisfied=False,
                    candidates_representable=False,
                    connector_succeeded=False,
                ),
                trajectory=None,
                selected=None,
                cost=None,
                length_u=None,
                length_q=None,
                metrics=base_metrics,
                residual_state=problem.start if goal_usable else None,
                state_checks=1,
            )

        if already:
            return _finish(
                status=PlanningStatus.SUCCESS,
                task_class=TASK_ALREADY_SATISFIED,
                trajectory=Trajectory(states=()),
                selected=problem.start,
                cost=0.0,
                length_u=0.0,
                length_q=0.0,
                metrics=base_metrics,
                state_checks=1,
                query_s=0.0,
            )

        goal_candidates = select_goal_candidates(
            problem,
            goal_generator=self.goal_generator,
            max_candidates=self.max_goal_candidates,
            rng=rng,
        )
        goals = [c.state for c in goal_candidates]
        if not goals:
            return _finish(
                status=PlanningStatus.INVALID,
                task_class=TASK_INVALID_UNREPRESENTABLE,
                trajectory=None,
                selected=None,
                cost=None,
                length_u=None,
                length_q=None,
                metrics=base_metrics,
                residual_state=problem.start,
                state_checks=1,
            )

        direct_succeeded, direct_checks = direct_connector_available(problem, goals)
        base_metrics["tree"]["direct_connector_available"] = direct_succeeded
        task_class = classify_direct_attempt(
            start_valid=True,
            goal_usable=True,
            already_satisfied=False,
            candidates_representable=True,
            connector_succeeded=direct_succeeded,
        )
        connector = resolve_connector(problem)
        assembly = dict(problem.start.assembly_state)
        lo, hi = actuator_bounds(problem.robot)
        # V3-631: first-root only; V3-633 will initialize all goal roots.
        first_goal_candidate = goal_candidates[0]
        goal_root = first_goal_candidate.state
        sink = self.trace_sink

        start_tree: list[_TreeNode] = [_TreeNode(state=problem.start, parent=None)]
        goal_tree: list[_TreeNode] = [_TreeNode(state=goal_root, parent=None)]
        if sink is not None:
            sink.record(
                family="tree",
                phase="insert",
                event_type="vertex_insert",
                payload={
                    "tree": "start",
                    "index": 0,
                    "parent": None,
                    "u": problem.start.u.tolist(),
                },
            )
            sink.record(
                family="tree",
                phase="insert",
                event_type="vertex_insert",
                payload={
                    "tree": "goal",
                    "index": 0,
                    "parent": None,
                    "u": goal_root.u.tolist(),
                },
            )

        nn_ops = 0
        extensions = 0
        motion_checks = direct_checks
        state_checks = 1

        def nearest(tree: list[_TreeNode], target: PhysicalState) -> int:
            nonlocal nn_ops
            nn_ops += 1
            best_i = 0
            best_d = float("inf")
            for i, node in enumerate(tree):
                d = float(np.linalg.norm(node.state.u - target.u))
                if d < best_d:
                    best_d = d
                    best_i = i
            return best_i

        def steer(from_state: PhysicalState, toward: PhysicalState) -> PhysicalState | None:
            delta = toward.u - from_state.u
            dist = float(np.linalg.norm(delta))
            if dist <= 1e-15:
                return None
            if dist <= self.step_u:
                u_new = toward.u.copy()
            else:
                u_new = from_state.u + (self.step_u / dist) * delta
            u_new = np.clip(u_new, lo, hi)
            state = problem.robot.state_from_input(u_new, assembly_state=assembly)
            nonlocal state_checks
            state_checks += 1
            if not problem.scene.state_is_valid(state):
                return None
            return state

        def extend(
            tree: list[_TreeNode],
            target: PhysicalState,
            *,
            tree_id: str,
        ) -> tuple[str, int | None]:
            """Return ('reached'|'advanced'|'trapped', new_index)."""
            nonlocal extensions, motion_checks
            ni = nearest(tree, target)
            new_state = steer(tree[ni].state, target)
            if new_state is None:
                return "trapped", None
            motion_checks += 1
            if not try_connect(connector, problem, tree[ni].state, new_state):
                return "trapped", None
            tree.append(_TreeNode(state=new_state, parent=ni))
            extensions += 1
            new_i = len(tree) - 1
            if sink is not None:
                sink.record(
                    family="tree",
                    phase="insert",
                    event_type="vertex_insert",
                    payload={
                        "tree": tree_id,
                        "index": int(new_i),
                        "parent": int(ni),
                        "u": new_state.u.tolist(),
                    },
                )
            if float(np.linalg.norm(new_state.u - target.u)) <= 1e-9:
                return "reached", new_i
            return "advanced", new_i

        def connect(
            tree: list[_TreeNode],
            target: PhysicalState,
            *,
            tree_id: str,
        ) -> tuple[str, int | None]:
            status = "advanced"
            last: int | None = None
            while status == "advanced":
                status, last = extend(tree, target, tree_id=tree_id)
            return status, last

        def reconstruct(tree: list[_TreeNode], idx: int) -> list[PhysicalState]:
            out: list[PhysicalState] = []
            cur: int | None = idx
            while cur is not None:
                out.append(tree[cur].state)
                cur = tree[cur].parent
            out.reverse()
            return out

        t_query = time.perf_counter()
        swapped = False
        found = False
        start_meet: int | None = None
        goal_meet: int | None = None
        iterations = 0

        for it in range(self.max_iterations):
            iterations = it + 1
            if rng.random() < self.goal_bias:
                sample = goal_root if not swapped else problem.start
            else:
                sample = sample_state_uniform(
                    problem.robot, rng, assembly_state=assembly
                )
                state_checks += 1
                if not problem.scene.state_is_valid(sample):
                    continue

            a_tree, b_tree = (start_tree, goal_tree) if not swapped else (goal_tree, start_tree)
            a_id, b_id = ("start", "goal") if not swapped else ("goal", "start")
            status_a, new_a = extend(a_tree, sample, tree_id=a_id)
            if status_a == "trapped" or new_a is None:
                swapped = not swapped
                continue
            status_b, new_b = connect(b_tree, a_tree[new_a].state, tree_id=b_id)
            if status_b == "reached" and new_b is not None:
                found = True
                if not swapped:
                    start_meet, goal_meet = new_a, new_b
                else:
                    start_meet, goal_meet = new_b, new_a
                if sink is not None:
                    sink.record(
                        family="tree",
                        phase="connect",
                        event_type="trees_connected",
                        payload={
                            "start_meet": int(start_meet),
                            "goal_meet": int(goal_meet),
                            "iteration": int(iterations),
                        },
                    )
                break
            swapped = not swapped

        base_metrics["tree"]["iterations"] = iterations
        base_metrics["tree"]["extensions"] = extensions
        base_metrics["tree"]["nn_ops"] = nn_ops
        base_metrics["tree"]["start_tree_size"] = len(start_tree)
        base_metrics["tree"]["goal_tree_size"] = len(goal_tree)
        query_s = time.perf_counter() - t_query

        if not found or start_meet is None or goal_meet is None:
            return _finish(
                status=PlanningStatus.UNSOLVED,
                task_class=task_class,
                trajectory=None,
                selected=None,
                cost=None,
                length_u=None,
                length_q=None,
                metrics=base_metrics,
                residual_state=problem.start,
                query_s=query_s,
                state_checks=state_checks,
                motion_checks=motion_checks,
            )

        # Connect trees at meeting states (may need one more edge).
        path_start = reconstruct(start_tree, start_meet)
        path_goal = reconstruct(goal_tree, goal_meet)
        path_goal.reverse()
        if float(np.linalg.norm(path_start[-1].u - path_goal[0].u)) > 1e-9:
            motion_checks += 1
            if not try_connect(connector, problem, path_start[-1], path_goal[0]):
                return _finish(
                    status=PlanningStatus.UNSOLVED,
                    task_class=task_class,
                    trajectory=None,
                    selected=None,
                    cost=None,
                    length_u=None,
                    length_q=None,
                    metrics=base_metrics,
                    residual_state=problem.start,
                    query_s=query_s,
                    state_checks=state_checks,
                    motion_checks=motion_checks,
                )
            states = tuple(path_start + path_goal)
        else:
            states = tuple(path_start + path_goal[1:])

        selected = states[-1]
        selected_cand = match_selected_candidate(
            [first_goal_candidate], selected
        )
        cost = path_cost_u(states)
        if sink is not None:
            sink.record(
                family="tree",
                phase="path",
                event_type="final_path",
                payload={
                    "n_waypoints": len(states),
                    "cost_u": float(cost),
                    "start_tree_size": len(start_tree),
                    "goal_tree_size": len(goal_tree),
                },
            )
        return _finish(
            status=PlanningStatus.SUCCESS,
            task_class=task_class,
            trajectory=Trajectory(states=states),
            selected=selected,
            candidate=selected_cand,
            cost=cost,
            length_u=cost,
            length_q=path_length_q(states),
            length_x=path_length_x(states, robot=problem.robot),
            metrics=base_metrics,
            query_s=query_s,
            state_checks=state_checks,
            motion_checks=motion_checks,
        )
