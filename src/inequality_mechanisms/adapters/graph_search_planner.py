"""Wrap Version 2 Dijkstra/A* graph solvers as Version 3 planners."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

import numpy as np

from inequality_mechanisms.core.goals import ExactOutputGoal
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.planner import PlannerCapabilities, PlannerLifecycle
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
    Trajectory,
)
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.search.graph_solver import (
    AStarGraphSolver,
    DijkstraGraphSolver,
    GraphSolver,
)
from inequality_mechanisms.search.v2_objectives import resolve_v2_objective

SolverName = Literal["dijkstra", "astar"]


def _solver_backend(name: SolverName) -> GraphSolver:
    if name == "dijkstra":
        return DijkstraGraphSolver()
    if name == "astar":
        return AStarGraphSolver()
    raise ValueError(f"unsupported graph solver {name!r}")


@dataclass(frozen=True, slots=True)
class GraphSearchPlanner:
    """Lattice/graph planner adapter around frozen EmbeddedPlanningGraph search.

    The graph is planner configuration, not a ``PlanningProblem`` field.
    Start and goal physical states must land on lattice nodes (exact ``q``).
    Only ``ActuatorTravelObjective`` is supported in Sprint V3.1.
    """

    graph: EmbeddedPlanningGraph
    algorithm: SolverName = "dijkstra"
    lifecycle: PlannerLifecycle = PlannerLifecycle.SINGLE_QUERY
    q_match_tolerance: float = 1e-9
    code_revision: str | None = None

    @property
    def planner_id(self) -> str:
        """Stable planner id including algorithm."""
        return f"graph_search_{self.algorithm}"

    @property
    def capabilities(self) -> PlannerCapabilities:
        """Declare graph-search capabilities (theory fields left None)."""
        return PlannerCapabilities(
            deterministic=True,
            reproducible_with_seed=True,
            multi_query=False,
            optimizing=True,
            probabilistically_complete=None,
            asymptotically_optimal=None,
            requires_metric_space=False,
            supports_optimization_objective=True,
            supports_goal_region=False,
            supports_goal_sampling=False,
            supports_multi_start=False,
            supports_path_constraints=False,
            supports_approximate_solution=False,
            supports_incremental_solutions=False,
            reports_graph_exploration=True,
            supports_exact_start=True,
        )

    def _node_for_q(self, q: np.ndarray) -> int:
        matches: list[int] = []
        for node_id in range(self.graph.node_count):
            if not self.graph.node_is_valid(node_id):
                continue
            dist = float(np.linalg.norm(self.graph.q_state(node_id) - q))
            if dist <= self.q_match_tolerance:
                matches.append(node_id)
        if len(matches) != 1:
            raise ValueError(
                "expected exactly one lattice node for "
                f"q={q.tolist()}, found {len(matches)}"
            )
        return matches[0]

    def _state_from_node(self, node_id: int, robot_assembly: dict) -> PhysicalState:
        return PhysicalState(
            u=np.asarray(self.graph.u_state(node_id), dtype=np.float64),
            q=np.asarray(self.graph.q_state(node_id), dtype=np.float64),
            assembly_state=dict(robot_assembly),
            auxiliary_state={"lattice_node_id": int(node_id)},
        )

    def solve(self, problem: PlanningProblem) -> PlanningResult:
        """Solve a lattice query through the frozen Version 2 search core."""
        if not isinstance(problem.objective, ActuatorTravelObjective):
            raise ValueError(
                "GraphSearchPlanner currently supports ActuatorTravelObjective only"
            )
        if not isinstance(problem.goal, ExactOutputGoal):
            raise ValueError(
                "GraphSearchPlanner currently supports ExactOutputGoal only"
            )
        if not problem.scene.state_is_valid(problem.start):
            return PlanningResult(
                status=PlanningStatus.INVALID,
                trajectory=None,
                selected_goal_state=None,
                total_wall_time_s=0.0,
                objective_cost=None,
                path_length_u=None,
                path_length_q=None,
                path_length_x=None,
                task_class=None,
                final_goal_residual=None,
                planner_metrics={},
                provenance=ResultProvenance(
                    architecture_version=3,
                    code_revision=self.code_revision,
                    planner_id=self.planner_id,
                ),
            )

        try:
            start_id = self._node_for_q(problem.start.q)
            goal_id = self._node_for_q(problem.goal.q_goal)
        except ValueError:
            return PlanningResult(
                status=PlanningStatus.INVALID,
                trajectory=None,
                selected_goal_state=None,
                total_wall_time_s=0.0,
                objective_cost=None,
                path_length_u=None,
                path_length_q=None,
                path_length_x=None,
                task_class=None,
                final_goal_residual=problem.goal.residual(problem.start),
                planner_metrics={},
                provenance=ResultProvenance(
                    architecture_version=3,
                    code_revision=self.code_revision,
                    planner_id=self.planner_id,
                ),
            )

        objective = resolve_v2_objective(
            self.graph,
            goal_id,
            "actuator_travel",
            heuristic_name="input_euclidean" if self.algorithm == "astar" else "zero",
        )
        backend = _solver_backend(self.algorithm)
        t0 = time.perf_counter()
        search = backend.solve(self.graph, start_id, goal_id, objective)
        query_time = time.perf_counter() - t0

        assembly = dict(problem.start.assembly_state)
        if not search.found:
            return PlanningResult(
                status=PlanningStatus.UNSOLVED,
                trajectory=None,
                selected_goal_state=None,
                query_time_s=query_time,
                total_wall_time_s=query_time,
                objective_cost=None,
                path_length_u=None,
                path_length_q=None,
                path_length_x=None,
                task_class=None,
                final_goal_residual=None,
                planner_metrics={
                    "graph": {
                        "expansions": int(search.n_expanded),
                        "generated": int(search.n_generated),
                        "reopened_or_stale": int(search.n_stale),
                        "path_node_ids": list(search.path),
                    }
                },
                provenance=ResultProvenance(
                    architecture_version=3,
                    code_revision=self.code_revision,
                    planner_id=self.planner_id,
                    extras={"v2_solver_id": backend.solver_id},
                ),
            )

        states = tuple(self._state_from_node(nid, assembly) for nid in search.path)
        selected_id = (
            search.selected_goal_node_id
            if search.selected_goal_node_id is not None
            else search.path[-1]
        )
        selected = self._state_from_node(selected_id, assembly)
        path_u = float(
            sum(
                np.linalg.norm(states[i + 1].u - states[i].u)
                for i in range(len(states) - 1)
            )
        )
        path_q = float(
            sum(
                np.linalg.norm(states[i + 1].q - states[i].q)
                for i in range(len(states) - 1)
            )
        )
        return PlanningResult(
            status=PlanningStatus.SUCCESS,
            trajectory=Trajectory(states=states),
            selected_goal_state=selected,
            query_time_s=query_time,
            total_wall_time_s=query_time,
            objective_cost=float(search.cost),
            path_length_u=path_u,
            path_length_q=path_q,
            path_length_x=None,
            task_class=None,
            final_goal_residual=problem.goal.residual(selected),
            planner_metrics={
                "graph": {
                    "expansions": int(search.n_expanded),
                    "generated": int(search.n_generated),
                    "reopened_or_stale": int(search.n_stale),
                    "path_node_ids": list(search.path),
                    "selected_goal_node_id": int(selected_id),
                }
            },
            provenance=ResultProvenance(
                architecture_version=3,
                code_revision=self.code_revision,
                planner_id=self.planner_id,
                extras={"v2_solver_id": backend.solver_id},
            ),
        )
