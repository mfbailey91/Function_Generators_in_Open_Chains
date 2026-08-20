"""Search a jointly compiled paired lattice (V4.2B / V4-226).

Base adjacency comes from ``compile_paired_q_search_graph``. Query overlay
edges are classified per arm under ADR-030 so generic Dijkstra/A* never
see ``+inf``. Overlay attachment is not the paired lattice estimand.
"""

from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.adapters.finite_search_edges import compile_finite_neighbors
from inequality_mechanisms.adapters.lattice_edge_cost import (
    integrated_actuator_edge_cost,
)
from inequality_mechanisms.benchmarks.classification import (
    TASK_ALREADY_SATISFIED,
    TASK_INVALID_UNREPRESENTABLE,
)
from inequality_mechanisms.core.goal_residuals import build_goal_residual_report
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
    Trajectory,
)
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.scene import PlanningScene
from inequality_mechanisms.core.state import PhysicalState, StateCandidate
from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.graphs.goal_set_query_overlay import (
    GoalSetQueryOverlay,
    IncompleteGoalSetAttachmentError,
)
from inequality_mechanisms.graphs.paired_edge_admission import PairedCompiledSearchGraph
from inequality_mechanisms.planners.sampling_space import match_selected_candidate
from inequality_mechanisms.search.graph_solver import (
    AStarGraphSolver,
    DijkstraGraphSolver,
)
from inequality_mechanisms.search.protocol import EdgeCost, SearchGraph
from inequality_mechanisms.search.v2_objectives import (
    V2PlanningObjective,
    input_euclidean_goal_set_heuristic_v2,
    zero_heuristic_v2,
)

SolverName = Literal["dijkstra", "astar"]


@dataclass
class OverlayCandidateGraph:
    """Candidate overlay whose base neighbors are the compiled admitted set."""

    overlay: GoalSetQueryOverlay
    compiled: PairedCompiledSearchGraph

    @property
    def node_count(self) -> int:
        return int(self.overlay.node_count)

    def node_is_valid(self, node_id: int) -> bool:
        return bool(self.overlay.node_is_valid(int(node_id)))

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        nid = int(node_id)
        base_n = int(self.overlay.base.node_count)
        if nid < base_n:
            extras = tuple(
                int(v) for v in self.overlay.neighbors(nid) if int(v) >= base_n
            )
            return tuple(int(v) for v in self.compiled.graph.neighbors(nid)) + extras
        return tuple(int(v) for v in self.overlay.neighbors(nid))

    def q_state(self, node_id: int) -> NDArray[np.float64]:
        return self.overlay.q_state(int(node_id))

    def u_state(self, node_id: int) -> NDArray[np.float64]:
        return self.overlay.u_state(int(node_id))


@dataclass
class CoordinateFilteredGraph:
    """Admitted overlay adjacency with overlay coordinates for heuristics."""

    overlay: GoalSetQueryOverlay
    graph: SearchGraph
    branch: Any = field(init=False)
    topology: Any = field(init=False)

    def __post_init__(self) -> None:
        self.branch = self.overlay.branch
        self.topology = self.overlay.topology

    @property
    def node_count(self) -> int:
        return int(self.graph.node_count)

    def node_is_valid(self, node_id: int) -> bool:
        return bool(self.graph.node_is_valid(int(node_id)))

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        return tuple(int(v) for v in self.graph.neighbors(int(node_id)))

    def q_state(self, node_id: int) -> NDArray[np.float64]:
        return self.overlay.q_state(int(node_id))

    def u_state(self, node_id: int) -> NDArray[np.float64]:
        return self.overlay.u_state(int(node_id))

    @property
    def base(self) -> Any:
        return self.overlay.base

    def edge_trace(self, a: int, b: int, n_samples: int = 17) -> Any:
        return self.overlay.edge_trace(int(a), int(b), n_samples=n_samples)


def _mixed_overlay_cost(
    *,
    overlay: GoalSetQueryOverlay,
    compiled: PairedCompiledSearchGraph,
    arm_name: str,
    robot: RobotModel,
    scene: PlanningScene | None,
    n_samples: int,
    assembly_state: dict[str, Any] | None,
) -> EdgeCost:
    base_n = int(overlay.base.node_count)
    shared = compiled.edge_costs[arm_name]
    overlay_cost = integrated_actuator_edge_cost(
        overlay,
        robot,
        scene=scene,
        n_samples=n_samples,
        assembly_state=assembly_state,
    )

    def cost(u: int, v: int) -> float:
        a = int(u)
        b = int(v)
        if a < base_n and b < base_n:
            return float(shared(a, b))
        return float(overlay_cost(a, b))

    return cost


def compile_overlay_search_graph(
    overlay: GoalSetQueryOverlay,
    compiled: PairedCompiledSearchGraph,
    *,
    arm_name: str,
    robot: RobotModel,
    scene: PlanningScene | None = None,
    n_samples: int = 16,
    assembly_state: dict[str, Any] | None = None,
) -> tuple[CoordinateFilteredGraph, EdgeCost, dict[tuple[int, int], Mapping[str, str]]]:
    """Admit overlay extras under ADR-030 on top of the compiled lattice.

    Parameters
    ----------
    overlay :
        Goal-set overlay built on one arm embedding.
    compiled :
        Jointly admitted paired lattice.
    arm_name :
        Key into ``compiled.edge_costs``.
    robot, scene, n_samples, assembly_state :
        Overlay connector cost arguments.

    Returns
    -------
    search_graph, edge_cost, rejected_overlay
        Filtered search graph with overlay coordinates, cached finite costs,
        and overlay-only rejections (``+inf`` omitted).
    """
    candidate = OverlayCandidateGraph(overlay=overlay, compiled=compiled)
    mixed = _mixed_overlay_cost(
        overlay=overlay,
        compiled=compiled,
        arm_name=arm_name,
        robot=robot,
        scene=scene,
        n_samples=n_samples,
        assembly_state=assembly_state,
    )
    finite = compile_finite_neighbors(candidate, mixed)
    search = CoordinateFilteredGraph(overlay=overlay, graph=finite.graph)
    return search, finite.edge_cost, dict(finite.rejected_candidates)


def _state_from_node(
    graph: Any, node_id: int, assembly: dict[str, Any]
) -> PhysicalState:
    return PhysicalState(
        u=np.asarray(graph.u_state(node_id), dtype=np.float64),
        q=np.asarray(graph.q_state(node_id), dtype=np.float64),
        assembly_state=dict(assembly),
        auxiliary_state={"lattice_node_id": int(node_id)},
    )


def _invalid(
    *,
    planner_id: str,
    residual: Any = None,
    metrics: dict[str, Any] | None = None,
    task_class: str | None = None,
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
        task_class=task_class,
        final_goal_residual=residual,
        planner_metrics=metrics or {},
        provenance=ResultProvenance(architecture_version=3, planner_id=planner_id),
    )


def solve_paired_lattice_goal_set(
    *,
    problem: Any,
    candidates: Sequence[StateCandidate],
    compiled: PairedCompiledSearchGraph,
    embedded: EmbeddedPlanningGraph,
    arm_name: str,
    algorithm: SolverName,
    edge_n_samples: int,
    q_match_tolerance: float = 1e-9,
    record_expanded: bool = True,
) -> tuple[PlanningResult, list[int]]:
    """Solve one represented goal set on the compiled paired lattice.

    Parameters
    ----------
    problem :
        Shared-Q start / Cartesian disk planning problem.
    candidates :
        Represented goal preimages for this arm.
    compiled :
        Jointly admitted search topology.
    embedded :
        This arm's shared-Q embedding (coordinates and overlay attachment).
    arm_name :
        Mechanism name matching ``compiled.edge_costs``.
    algorithm :
        ``dijkstra`` or ``astar``.
    edge_n_samples :
        Overlay connector quadrature.
    q_match_tolerance :
        Overlay lattice-node dedup tolerance.
    record_expanded :
        Record expansion ids for audit panels.

    Returns
    -------
    result, expanded
        Packed planning result and expanded node ids.
    """
    planner_id = f"paired_lattice_goal_set_{algorithm}_integrated"
    if problem.goal.satisfied(problem.start):
        return (
            PlanningResult(
                status=PlanningStatus.SUCCESS,
                trajectory=None,
                selected_goal_state=problem.start,
                total_wall_time_s=0.0,
                objective_cost=0.0,
                path_length_u=0.0,
                path_length_q=0.0,
                path_length_x=0.0,
                task_class=TASK_ALREADY_SATISFIED,
                final_goal_residual=problem.goal.residual(problem.start),
                planner_metrics={
                    "graph": {
                        "expansions": 0,
                        "path_node_ids": [],
                        "expansions_are_total_query_work": True,
                        "admitted_topology": True,
                    }
                },
                provenance=ResultProvenance(
                    architecture_version=3, planner_id=planner_id
                ),
            ),
            [],
        )
    if not candidates:
        return (
            _invalid(
                planner_id=planner_id,
                residual=problem.goal.residual(problem.start),
                metrics={
                    "graph": {
                        "goal_set_cardinality": 0,
                        "expansions_are_total_query_work": True,
                        "admitted_topology": True,
                    }
                },
                task_class=TASK_INVALID_UNREPRESENTABLE,
            ),
            [],
        )
    if not problem.scene.state_is_valid(problem.start):
        return (_invalid(planner_id=planner_id), [])

    start_q = np.asarray(problem.start.q, dtype=np.float64)
    start_u = np.asarray(problem.start.u, dtype=np.float64)
    goal_qs = [np.asarray(c.state.q, dtype=np.float64) for c in candidates]
    goal_us = [np.asarray(c.state.u, dtype=np.float64) for c in candidates]
    try:
        overlay = GoalSetQueryOverlay(
            base=embedded,
            start_q=start_q,
            goal_qs=goal_qs,
            start_u=start_u,
            goal_us=goal_us,
            dedup_tol=q_match_tolerance,
            edge_n_samples=edge_n_samples,
            require_all_goals=True,
        )
    except IncompleteGoalSetAttachmentError as exc:
        failed_candidates: list[dict[str, Any]] = []
        for failure in exc.failures:
            record = failure.to_dict()
            if 0 <= failure.goal_index < len(candidates):
                provenance = dict(candidates[failure.goal_index].provenance)
                if "goal_sample_id" in provenance:
                    record["goal_sample_id"] = provenance["goal_sample_id"]
            failed_candidates.append(record)
        return (
            _invalid(
                planner_id=planner_id,
                residual=problem.goal.residual(problem.start),
                metrics={
                    "graph": {
                        "overlay_used": False,
                        "search_started": False,
                        "goal_set_cardinality": 0,
                        "requested_goal_count": int(exc.requested_goal_count),
                        "attached_goal_candidate_count": int(exc.attached_goal_count),
                        "unique_goal_node_count": int(exc.unique_goal_node_count),
                        "goal_set_attachment_complete": False,
                        "query_failure": "incomplete_represented_goal_set_attachment",
                        "failed_goal_attachments": failed_candidates,
                        "expansions": 0,
                        "generated": 0,
                        "reopened_or_stale": 0,
                        "expansions_are_total_query_work": True,
                        "admitted_topology": True,
                    }
                },
            ),
            [],
        )
    except (ValueError, TypeError) as exc:
        return (
            _invalid(
                planner_id=planner_id,
                residual=problem.goal.residual(problem.start),
                metrics={
                    "graph": {
                        "overlay_used": False,
                        "search_started": False,
                        "goal_set_cardinality": 0,
                        "requested_goal_count": len(candidates),
                        "attached_goal_candidate_count": 0,
                        "unique_goal_node_count": 0,
                        "goal_set_attachment_complete": False,
                        "query_failure": "goal_set_overlay_invalid",
                        "failed_goal_attachments": [
                            {"goal_index": None, "reason": str(exc)}
                        ],
                        "expansions": 0,
                        "generated": 0,
                        "reopened_or_stale": 0,
                        "expansions_are_total_query_work": True,
                        "admitted_topology": True,
                    }
                },
            ),
            [],
        )

    assembly = dict(problem.start.assembly_state)
    search_graph, edge_cost, rejected_overlay = compile_overlay_search_graph(
        overlay,
        compiled,
        arm_name=arm_name,
        robot=problem.robot,
        scene=problem.scene,
        n_samples=edge_n_samples,
        assembly_state=assembly,
    )
    start_id = int(overlay.start_node_id)
    goal_ids = tuple(int(n) for n in overlay.goal_node_ids)
    heuristic_name = "input_euclidean_goal_set" if algorithm == "astar" else "zero"
    heuristic = (
        input_euclidean_goal_set_heuristic_v2(search_graph, goal_ids)
        if algorithm == "astar"
        else zero_heuristic_v2
    )
    objective = V2PlanningObjective(
        edge_cost=edge_cost,
        heuristic=heuristic,
        cost_name="actuator_travel_integrated",
        heuristic_name=heuristic_name,
    )
    backend = DijkstraGraphSolver() if algorithm == "dijkstra" else AStarGraphSolver()
    t0 = time.perf_counter()
    search = backend.solve(
        search_graph,
        start_id,
        None,
        objective,
        goal_node_ids=goal_ids,
        record_expanded=record_expanded,
    )
    query_time = time.perf_counter() - t0
    expanded = [int(n) for n in (search.expanded_nodes or ())]
    graph_metrics: dict[str, Any] = {
        "edge_cost_mode": "integrated",
        "connectivity": str(overlay.topology.connectivity),
        "overlay_used": True,
        "search_started": True,
        "overlay_start_node_id": start_id,
        "goal_node_ids": list(goal_ids),
        "goal_set_cardinality": len(goal_ids),
        "unique_goal_node_count": len(goal_ids),
        "requested_goal_count": int(overlay.requested_goal_count),
        "attached_goal_candidate_count": int(overlay.attached_goal_count),
        "goal_set_attachment_complete": bool(overlay.attachment_complete),
        "heuristic_name": heuristic_name,
        "attachments": overlay.attachments_as_dicts(),
        "failed_goal_attachments": list(overlay.failed_goal_attachments),
        "rejected_overlay_edges": [
            {"u": int(a), "v": int(b), **dict(payload)}
            for (a, b), payload in sorted(rejected_overlay.items())
        ],
        "admitted_topology": True,
        "expansions": int(search.n_expanded),
        "generated": int(search.n_generated),
        "reopened_or_stale": int(search.n_stale),
        "path_node_ids": list(search.path),
        "expansions_are_total_query_work": True,
    }
    if record_expanded:
        graph_metrics["expanded_node_ids"] = expanded

    if not search.found:
        return (
            PlanningResult(
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
                planner_metrics={"graph": graph_metrics},
                provenance=ResultProvenance(
                    architecture_version=3,
                    planner_id=planner_id,
                    extras={
                        "v2_solver_id": backend.solver_id,
                        "represented_goal_set": True,
                    },
                ),
            ),
            expanded,
        )

    states = tuple(_state_from_node(search_graph, nid, assembly) for nid in search.path)
    selected_id = (
        int(search.selected_goal_node_id)
        if search.selected_goal_node_id is not None
        else int(search.path[-1])
    )
    selected = _state_from_node(search_graph, selected_id, assembly)
    graph_metrics["selected_goal_node_id"] = selected_id
    attachment_rec = overlay.attachment_for_goal_node(selected_id)
    attachment_residual = (
        None if attachment_rec is None else float(attachment_rec.attachment_residual_q)
    )
    if attachment_residual is None:
        attachment_residual = float(
            np.linalg.norm(overlay.q_state(selected_id) - selected.q)
        )
    selected_candidate: StateCandidate | None = None
    if attachment_rec is not None and attachment_rec.goal_index is not None:
        src = candidates[int(attachment_rec.goal_index)]
        selected_candidate = StateCandidate(
            state=selected,
            residual=float(src.residual),
            provenance=dict(src.provenance),
        )
    if selected_candidate is None:
        matched = match_selected_candidate(candidates, selected)
        if matched is not None:
            selected_candidate = StateCandidate(
                state=selected,
                residual=float(matched.residual),
                provenance=dict(matched.provenance),
            )
    report = build_goal_residual_report(
        problem.goal,
        selected,
        candidate=selected_candidate,
        attachment_residual=attachment_residual,
    )
    path_u = 0.0
    path_nodes = list(search.path)
    for a, b in zip(path_nodes[:-1], path_nodes[1:]):
        path_u += float(edge_cost(int(a), int(b)))
    path_q = float(
        sum(
            np.linalg.norm(states[i + 1].q - states[i].q)
            for i in range(len(states) - 1)
        )
    )
    return (
        PlanningResult(
            status=PlanningStatus.SUCCESS,
            trajectory=Trajectory(states=states),
            selected_goal_state=selected,
            selected_goal_candidate=selected_candidate,
            query_time_s=query_time,
            total_wall_time_s=query_time,
            objective_cost=float(search.cost),
            path_length_u=path_u,
            path_length_q=path_q,
            path_length_x=None,
            task_class=None,
            final_goal_residual=report.physical,
            goal_residuals=report,
            planner_metrics={"graph": graph_metrics},
            provenance=ResultProvenance(
                architecture_version=3,
                planner_id=planner_id,
                extras={
                    "v2_solver_id": backend.solver_id,
                    "represented_goal_set": True,
                },
            ),
        ),
        expanded,
    )
