"""Wrap Version 2 Dijkstra/A* graph solvers as Version 3 planners."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from inequality_mechanisms.adapters.lattice_edge_cost import (
    EdgeCostMode,
    path_actuator_length,
    resolve_lattice_search_objective,
)
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
from inequality_mechanisms.graphs.query_overlay import QueryOverlayGraph
from inequality_mechanisms.search.graph_solver import (
    AStarGraphSolver,
    DijkstraGraphSolver,
    GraphSolver,
)

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
    Exact starts/goals may lie on lattice nodes or attach through
    ``QueryOverlayGraph`` (ADR-023; no task-semantic start tolerance).
    Supports endpoint or integrated actuator edge-cost modes (Sprint V3.3).

    Opt-in ``trace_sink`` / ``record_expanded`` are audit-only and do not
    change status, path, cost, or ordinary planner metrics when unused.
    """

    graph: EmbeddedPlanningGraph
    algorithm: SolverName = "dijkstra"
    lifecycle: PlannerLifecycle = PlannerLifecycle.SINGLE_QUERY
    q_match_tolerance: float = 1e-9
    edge_cost_mode: EdgeCostMode = "endpoint"
    allow_query_overlay: bool = True
    edge_n_samples: int = 32
    code_revision: str | None = None
    record_expanded: bool = False
    trace_sink: Any | None = None
    shared_edge_cost: Any | None = None

    @property
    def planner_id(self) -> str:
        """Stable planner id including algorithm and cost mode."""
        return f"graph_search_{self.algorithm}_{self.edge_cost_mode}"

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

    def _node_for_q(self, graph: Any, q: np.ndarray) -> int | None:
        matches: list[int] = []
        for node_id in range(graph.node_count):
            if not graph.node_is_valid(node_id):
                continue
            dist = float(np.linalg.norm(graph.q_state(node_id) - q))
            if dist <= self.q_match_tolerance:
                matches.append(node_id)
        if len(matches) == 1:
            return matches[0]
        if len(matches) == 0:
            return None
        raise ValueError(
            "expected at most one lattice node for "
            f"q={q.tolist()}, found {len(matches)}"
        )

    def _state_from_node(
        self, graph: Any, node_id: int, robot_assembly: dict
    ) -> PhysicalState:
        return PhysicalState(
            u=np.asarray(graph.u_state(node_id), dtype=np.float64),
            q=np.asarray(graph.q_state(node_id), dtype=np.float64),
            assembly_state=dict(robot_assembly),
            auxiliary_state={"lattice_node_id": int(node_id)},
        )

    def _invalid_result(
        self,
        *,
        residual: Any = None,
        metrics: dict[str, Any] | None = None,
    ) -> PlanningResult:
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
            final_goal_residual=residual,
            planner_metrics=metrics or {},
            provenance=ResultProvenance(
                architecture_version=3,
                code_revision=self.code_revision,
                planner_id=self.planner_id,
            ),
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
            return self._invalid_result()

        base = self.graph
        start_q = np.asarray(problem.start.q, dtype=np.float64)
        goal_q = np.asarray(problem.goal.q_goal, dtype=np.float64)
        try:
            start_on = self._node_for_q(base, start_q)
            goal_on = self._node_for_q(base, goal_q)
        except ValueError:
            return self._invalid_result(
                residual=problem.goal.residual(problem.start)
            )

        overlay_metrics: dict[str, Any] = {
            "edge_cost_mode": self.edge_cost_mode,
            "connectivity": str(base.topology.connectivity),
            "overlay_used": False,
        }
        search_graph: Any = base
        start_id: int
        goal_id: int

        if start_on is not None and goal_on is not None:
            start_id = start_on
            goal_id = goal_on
        elif not self.allow_query_overlay:
            return self._invalid_result(
                residual=problem.goal.residual(problem.start),
                metrics={"graph": overlay_metrics},
            )
        else:
            try:
                overlay = QueryOverlayGraph(
                    base=base,
                    start_q=start_q,
                    goal_q=goal_q,
                    dedup_tol=self.q_match_tolerance,
                    edge_n_samples=self.edge_n_samples,
                )
            except (ValueError, TypeError):
                return self._invalid_result(
                    residual=problem.goal.residual(problem.start),
                    metrics={"graph": overlay_metrics},
                )
            search_graph = overlay
            start_id = int(overlay.start_node_id)
            goal_id = int(overlay.goal_node_id)
            overlay_metrics["overlay_used"] = True
            overlay_metrics["overlay_start_node_id"] = start_id
            overlay_metrics["overlay_goal_node_id"] = goal_id
            overlay_metrics["start_attachment_residual_q"] = float(
                np.linalg.norm(overlay.q_state(start_id) - start_q)
            )
            overlay_metrics["goal_attachment_residual_q"] = float(
                np.linalg.norm(overlay.q_state(goal_id) - goal_q)
            )

        assembly = dict(problem.start.assembly_state)
        if self.shared_edge_cost is not None and self.edge_cost_mode == "integrated":
            from inequality_mechanisms.search.v2_objectives import (
                V2PlanningObjective,
                input_euclidean_heuristic_v2,
                zero_heuristic_v2,
            )

            heuristic = (
                input_euclidean_heuristic_v2(search_graph, goal_id)
                if self.algorithm == "astar"
                else zero_heuristic_v2
            )
            objective = V2PlanningObjective(
                edge_cost=self.shared_edge_cost,
                heuristic=heuristic,
                cost_name="actuator_travel_integrated",
                heuristic_name="input_euclidean" if self.algorithm == "astar" else "zero",
            )
        else:
            objective = resolve_lattice_search_objective(
                search_graph,
                goal_id,
                edge_cost_mode=self.edge_cost_mode,
                robot=problem.robot,
                algorithm=self.algorithm,
                scene=problem.scene,
                n_samples=self.edge_n_samples,
                assembly_state=assembly,
            )
        backend = _solver_backend(self.algorithm)
        want_expanded = bool(self.record_expanded or self.trace_sink is not None)
        t0 = time.perf_counter()
        search = backend.solve(
            search_graph,
            start_id,
            goal_id,
            objective,
            record_expanded=want_expanded,
        )
        query_time = time.perf_counter() - t0

        if self.trace_sink is not None:
            for step, node_id in enumerate(search.expanded_nodes):
                self.trace_sink.record(
                    family="graph",
                    phase="expand",
                    event_type="record_expanded",
                    payload={"node_id": int(node_id), "order": int(step)},
                )
            self.trace_sink.record(
                family="graph",
                phase="path",
                event_type="search_summary",
                payload={
                    "found": bool(search.found),
                    "n_expanded": int(search.n_expanded),
                    "n_generated": int(search.n_generated),
                    "n_stale": int(search.n_stale),
                    "path_node_ids": list(search.path),
                    "cost": None if not search.found else float(search.cost),
                },
            )

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
                        **overlay_metrics,
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

        states = tuple(
            self._state_from_node(search_graph, nid, assembly) for nid in search.path
        )
        selected_id = (
            search.selected_goal_node_id
            if search.selected_goal_node_id is not None
            else search.path[-1]
        )
        selected = self._state_from_node(search_graph, selected_id, assembly)
        path_u = path_actuator_length(
            search_graph,
            search.path,
            robot=problem.robot,
            edge_cost_mode=self.edge_cost_mode,
            scene=problem.scene,
            n_samples=self.edge_n_samples,
            assembly_state=assembly,
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
                    **overlay_metrics,
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
