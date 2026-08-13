"""Basic PRM planner (Sprint V3.4 / V3-402)."""

from __future__ import annotations

import heapq
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


@dataclass(frozen=True, slots=True)
class PRMPlanner:
    """Basic probabilistic roadmap planner over certified actuator samples.

    Builds a roadmap per solve (``BUILD_PER_TASK``), attaches the exact start
    and every accepted goal candidate, then runs Dijkstra to the goal set.
    Not Lazy-PRM and not PRM*.

    Opt-in ``trace_sink`` records sample/edge/query/search events for audits
    without changing ordinary planner metrics.
    """

    seed: int = 0
    n_samples: int = 64
    k_neighbors: int = 8
    max_edge_u: float = 0.75
    max_goal_candidates: int = 8
    goal_generator: GoalStateGenerator | None = None
    repetition_index: int = 0
    code_revision: str | None = None
    lifecycle: PlannerLifecycle = PlannerLifecycle.BUILD_PER_TASK
    trace_sink: Any | None = None

    @property
    def planner_id(self) -> str:
        """Stable planner registry name."""
        return "prm_basic"

    @property
    def capabilities(self) -> PlannerCapabilities:
        """Declare stochastic but seed-reproducible roadmap capabilities."""
        return PlannerCapabilities(
            deterministic=False,
            reproducible_with_seed=True,
            multi_query=False,
            optimizing=True,
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
        """Classify, build a PRM, attach query, and search."""
        if not isinstance(problem.objective, ActuatorTravelObjective):
            raise ValueError("PRMPlanner currently supports ActuatorTravelObjective only")

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
            preprocess_s: float | None = None,
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
                preprocessing_time_s=preprocess_s,
                query_time_s=query_s,
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
            "roadmap": {
                "n_samples_requested": int(self.n_samples),
                "vertices": 0,
                "attempted_edges": 0,
                "accepted_edges": 0,
                "start_attached": False,
                "goal_attached": False,
                "goal_candidate_count": 0,
                "goal_attachment_count": 0,
                "expansions": 0,
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
                preprocess_s=0.0,
                query_s=0.0,
            )

        goal_candidates = select_goal_candidates(
            problem,
            goal_generator=self.goal_generator,
            max_candidates=self.max_goal_candidates,
            rng=rng,
        )
        goals = [c.state for c in goal_candidates]
        base_metrics["roadmap"]["goal_candidate_count"] = len(goal_candidates)
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
        base_metrics["roadmap"]["direct_connector_available"] = direct_succeeded
        task_class = classify_direct_attempt(
            start_valid=True,
            goal_usable=True,
            already_satisfied=False,
            candidates_representable=True,
            connector_succeeded=direct_succeeded,
        )
        connector = resolve_connector(problem)
        assembly = dict(problem.start.assembly_state)

        t_pre = time.perf_counter()
        vertices: list[PhysicalState] = []
        state_checks = 1
        sink = self.trace_sink
        for sample_i in range(self.n_samples):
            sample = sample_state_uniform(
                problem.robot, rng, assembly_state=assembly
            )
            state_checks += 1
            accepted_sample = problem.scene.state_is_valid(sample)
            if sink is not None:
                sink.record(
                    family="roadmap",
                    phase="sample",
                    event_type="sample_accept" if accepted_sample else "sample_reject",
                    payload={
                        "index": int(sample_i),
                        "u": sample.u.tolist(),
                        "accepted": bool(accepted_sample),
                    },
                )
            if accepted_sample:
                vertices.append(sample)
        base_metrics["roadmap"]["vertices"] = len(vertices)

        # Adjacency as undirected weighted edges among sample vertices.
        adj: list[list[tuple[int, float]]] = [[] for _ in range(len(vertices))]
        attempted = 0
        accepted = 0
        motion_checks = direct_checks
        for i, si in enumerate(vertices):
            dists = [
                (j, float(np.linalg.norm(si.u - vertices[j].u)))
                for j in range(len(vertices))
                if j != i
            ]
            dists.sort(key=lambda t: t[1])
            for j, dist in dists[: self.k_neighbors]:
                if dist > self.max_edge_u or dist <= 0.0:
                    continue
                if j < i:
                    continue  # undirected: connect once
                attempted += 1
                motion_checks += 1
                if try_connect(connector, problem, si, vertices[j]):
                    accepted += 1
                    adj[i].append((j, dist))
                    adj[j].append((i, dist))
                    if sink is not None:
                        sink.record(
                            family="roadmap",
                            phase="edge",
                            event_type="edge_accept",
                            payload={"i": int(i), "j": int(j), "dist_u": float(dist)},
                        )
        base_metrics["roadmap"]["attempted_edges"] = attempted
        base_metrics["roadmap"]["accepted_edges"] = accepted
        preprocess_s = time.perf_counter() - t_pre

        # Attach start and goals as extra nodes.
        t_query = time.perf_counter()
        start_idx = len(vertices)
        vertices.append(problem.start)
        adj.append([])
        goal_indices: list[int] = []
        for g in goals:
            gi = len(vertices)
            vertices.append(g)
            adj.append([])
            goal_indices.append(gi)

        def _attach(src: int, dsts: list[int]) -> int:
            attached = 0
            nonlocal motion_checks
            for dst in dsts:
                dist = float(np.linalg.norm(vertices[src].u - vertices[dst].u))
                if dist > self.max_edge_u and src != start_idx:
                    # Still allow start/goal attachment within 2x max for query.
                    if dist > 2.0 * self.max_edge_u:
                        continue
                elif dist > 2.0 * self.max_edge_u:
                    continue
                motion_checks += 1
                if try_connect(connector, problem, vertices[src], vertices[dst]):
                    adj[src].append((dst, dist))
                    adj[dst].append((src, dist))
                    attached += 1
                    if sink is not None:
                        sink.record(
                            family="roadmap",
                            phase="query",
                            event_type="attach_edge",
                            payload={
                                "src": int(src),
                                "dst": int(dst),
                                "dist_u": float(dist),
                            },
                        )
            return attached

        sample_ids = list(range(start_idx))
        start_links = _attach(start_idx, sample_ids + goal_indices)
        base_metrics["roadmap"]["start_attached"] = start_links > 0
        goal_links = 0
        for gi in goal_indices:
            goal_links += _attach(gi, sample_ids + [start_idx])
        base_metrics["roadmap"]["goal_attached"] = goal_links > 0
        base_metrics["roadmap"]["goal_attachment_count"] = int(goal_links)
        if sink is not None:
            sink.record(
                family="roadmap",
                phase="query",
                event_type="query_attach",
                payload={
                    "start_idx": int(start_idx),
                    "goal_indices": list(goal_indices),
                    "start_links": int(start_links),
                    "goal_links": int(goal_links),
                },
            )

        # Dijkstra from start to any goal.
        goal_set = set(goal_indices)
        dist = [float("inf")] * len(vertices)
        prev: list[int | None] = [None] * len(vertices)
        dist[start_idx] = 0.0
        heap: list[tuple[float, int]] = [(0.0, start_idx)]
        expansions = 0
        found_goal: int | None = None
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            expansions += 1
            if sink is not None:
                sink.record(
                    family="roadmap",
                    phase="search",
                    event_type="dijkstra_expand",
                    payload={"node": int(u), "order": int(expansions - 1)},
                )
            if u in goal_set:
                found_goal = u
                break
            for v, w in adj[u]:
                nd = d + w
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))
        base_metrics["roadmap"]["expansions"] = expansions
        query_s = time.perf_counter() - t_query

        if found_goal is None:
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
                preprocess_s=preprocess_s,
                query_s=query_s,
                state_checks=state_checks,
                motion_checks=motion_checks,
            )

        # Reconstruct path.
        node_ids: list[int] = []
        cur: int | None = found_goal
        while cur is not None:
            node_ids.append(cur)
            cur = prev[cur]
        node_ids.reverse()
        states = tuple(vertices[i] for i in node_ids)
        selected = states[-1]
        selected_cand = match_selected_candidate(goal_candidates, selected)
        cost = path_cost_u(states)
        if sink is not None:
            sink.record(
                family="roadmap",
                phase="path",
                event_type="final_path",
                payload={"node_ids": list(node_ids), "cost_u": float(cost)},
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
            preprocess_s=preprocess_s,
            query_s=query_s,
            state_checks=state_checks,
            motion_checks=motion_checks,
        )
