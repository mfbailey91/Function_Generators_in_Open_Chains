"""Frozen shared-Q sampled-roadmap diagnostic runner (V3-637).

Builds one reusable Q sample bank, embeds mechanism-specific U lifts, attaches
the exact start and full ordered represented goal set by a shared Q-neighbor
rule, then runs Dijkstra (``h=0``) or A* (``input_euclidean_goal_set``) with
integrated actuator edge weights. Results are labeled
``shared_q_sampled_{dijkstra,astar}`` and never pooled with native PRM.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any, Literal

import numpy as np

from inequality_mechanisms.adapters.lattice_edge_cost import (
    path_actuator_length,
    resolve_lattice_goal_set_objective,
)
from inequality_mechanisms.benchmarks.classification import (
    TASK_ALREADY_SATISFIED,
    TASK_INVALID_UNREPRESENTABLE,
)
from inequality_mechanisms.core.goal_residuals import build_goal_residual_report
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
    Trajectory,
)
from inequality_mechanisms.core.state import PhysicalState, StateCandidate
from inequality_mechanisms.graphs.sampled_q_query_overlay import SampledQQueryOverlay
from inequality_mechanisms.graphs.sampled_q_roadmap import SampledQRoadmapGraph
from inequality_mechanisms.planners.sampling_space import match_selected_candidate
from inequality_mechanisms.search.graph_solver import AStarGraphSolver, DijkstraGraphSolver

AlgorithmName = Literal["dijkstra", "astar"]

PLANNER_ID_DIJKSTRA = "shared_q_sampled_dijkstra"
PLANNER_ID_ASTAR = "shared_q_sampled_astar"
METRICS_KEY = "shared_q_sampled_roadmap"
DIAGNOSTIC_LABEL = "metric-isolation diagnostic; not native PRM"


def planner_id_for_algorithm(algorithm: AlgorithmName) -> str:
    if algorithm == "dijkstra":
        return PLANNER_ID_DIJKSTRA
    if algorithm == "astar":
        return PLANNER_ID_ASTAR
    raise ValueError(f"unsupported shared-Q sampled-roadmap algorithm {algorithm!r}")


def _solver_backend(algorithm: AlgorithmName):
    if algorithm == "dijkstra":
        return DijkstraGraphSolver()
    if algorithm == "astar":
        return AStarGraphSolver()
    raise ValueError(f"unsupported shared-Q sampled-roadmap algorithm {algorithm!r}")


def _state_from_node(
    graph: Any, node_id: int, assembly: dict[str, Any]
) -> PhysicalState:
    return PhysicalState(
        u=np.asarray(graph.u_state(node_id), dtype=np.float64),
        q=np.asarray(graph.q_state(node_id), dtype=np.float64),
        assembly_state=dict(assembly),
        auxiliary_state={"sampled_q_node_id": int(node_id)},
    )


def _empty_metrics(graph: SampledQRoadmapGraph) -> dict[str, Any]:
    bank = graph.bank
    return {
        METRICS_KEY: {
            **bank.provenance_dict(),
            "vertices": int(graph.node_count),
            "valid_vertices": int(np.count_nonzero(graph.valid_nodes)),
            "edges": len(bank.edges),
            "start_attached": False,
            "goal_candidate_count": 0,
            "goal_attachment_count": 0,
            "expansions": 0,
            "diagnostic_label": DIAGNOSTIC_LABEL,
        }
    }


def solve_shared_q_sampled_roadmap(
    *,
    graph: SampledQRoadmapGraph,
    problem: PlanningProblem,
    candidates: Sequence[StateCandidate],
    algorithm: AlgorithmName,
    edge_n_samples: int = 16,
    record_expanded: bool = False,
    code_revision: str | None = None,
) -> PlanningResult:
    """Run one represented-goal-set query on a frozen shared-Q sampled roadmap."""
    planner_id = planner_id_for_algorithm(algorithm)
    if not isinstance(problem.objective, ActuatorTravelObjective):
        raise ValueError(
            "shared-Q sampled-roadmap diagnostic supports ActuatorTravelObjective only"
        )

    def _finish(
        *,
        status: PlanningStatus,
        trajectory: Trajectory | None = None,
        selected: PhysicalState | None = None,
        candidate: StateCandidate | None = None,
        cost: float | None = None,
        length_u: float | None = None,
        length_q: float | None = None,
        task_class: str | None = None,
        metrics: dict[str, Any],
        query_s: float | None = None,
        residual_state: PhysicalState | None = None,
        attachment_residual: float | None = None,
    ) -> PlanningResult:
        report = None
        residual = None
        state_for_residual = residual_state if residual_state is not None else selected
        if state_for_residual is not None:
            try:
                report = build_goal_residual_report(
                    problem.goal,
                    state_for_residual,
                    candidate=candidate,
                    attachment_residual=attachment_residual,
                )
                residual = report.physical
            except (NotImplementedError, ValueError, TypeError):
                report = None
                residual = None
        extras = {
            "v2_solver_id": algorithm,
            "represented_goal_set": True,
            "diagnostic": METRICS_KEY,
        }
        return PlanningResult(
            status=status,
            trajectory=trajectory,
            selected_goal_state=selected,
            selected_goal_candidate=candidate,
            total_wall_time_s=float(query_s or 0.0),
            query_time_s=query_s,
            objective_cost=cost,
            path_length_u=length_u,
            path_length_q=length_q,
            path_length_x=None,
            task_class=task_class,
            final_goal_residual=residual,
            goal_residuals=report,
            planner_metrics=metrics,
            provenance=ResultProvenance(
                architecture_version=3,
                code_revision=code_revision,
                planner_id=planner_id,
                extras=extras,
            ),
        )

    start_valid = problem.scene.state_is_valid(problem.start)
    try:
        _ = problem.goal.residual(problem.start)
        goal_usable = True
    except (NotImplementedError, ValueError, TypeError):
        goal_usable = False

    if not start_valid or not goal_usable:
        return _finish(
            status=PlanningStatus.INVALID,
            task_class=TASK_INVALID_UNREPRESENTABLE,
            metrics=_empty_metrics(graph),
            residual_state=problem.start if goal_usable else None,
        )

    if problem.goal.satisfied(problem.start):
        metrics = _empty_metrics(graph)
        metrics[METRICS_KEY]["start_attached"] = True
        return _finish(
            status=PlanningStatus.SUCCESS,
            trajectory=Trajectory(states=()),
            selected=problem.start,
            cost=0.0,
            length_u=0.0,
            length_q=0.0,
            task_class=TASK_ALREADY_SATISFIED,
            metrics=metrics,
            query_s=0.0,
        )

    if not candidates:
        return _finish(
            status=PlanningStatus.INVALID,
            task_class=TASK_INVALID_UNREPRESENTABLE,
            metrics=_empty_metrics(graph),
            residual_state=problem.start,
        )

    overlay = SampledQQueryOverlay(
        base=graph,
        start_q=np.asarray(problem.start.q, dtype=np.float64),
        start_u=np.asarray(problem.start.u, dtype=np.float64),
        goal_qs=[np.asarray(c.state.q, dtype=np.float64) for c in candidates],
        goal_us=[np.asarray(c.state.u, dtype=np.float64) for c in candidates],
    )
    start_id = int(overlay.start_node_id)
    goal_ids = tuple(int(n) for n in overlay.goal_node_ids)
    assembly = dict(problem.start.assembly_state)
    heuristic_name = "input_euclidean_goal_set" if algorithm == "astar" else "zero"
    objective = resolve_lattice_goal_set_objective(
        overlay,
        goal_ids,
        edge_cost_mode="integrated",
        robot=problem.robot,
        algorithm=algorithm,
        scene=problem.scene,
        n_samples=int(edge_n_samples),
        assembly_state=assembly,
    )
    backend = _solver_backend(algorithm)
    t0 = time.perf_counter()
    search = backend.solve(
        overlay,
        start_id,
        None,
        objective,
        goal_node_ids=goal_ids,
        record_expanded=record_expanded,
    )
    query_s = time.perf_counter() - t0

    bank = graph.bank
    family_metrics: dict[str, Any] = {
        **bank.provenance_dict(),
        "vertices": int(graph.node_count),
        "valid_vertices": int(np.count_nonzero(graph.valid_nodes)),
        "edges": len(bank.edges),
        "start_attached": True,
        "goal_candidate_count": len(candidates),
        "goal_attachment_count": len(goal_ids),
        "expansions": int(search.n_expanded),
        "generated": int(search.n_generated),
        "path_node_ids": list(search.path),
        "selected_goal_node_id": (
            None
            if search.selected_goal_node_id is None
            else int(search.selected_goal_node_id)
        ),
        "heuristic_name": heuristic_name,
        "diagnostic_label": DIAGNOSTIC_LABEL,
    }
    graph_metrics: dict[str, Any] = {
        "overlay_used": True,
        "overlay_start_node_id": start_id,
        "goal_node_ids": list(goal_ids),
        "goal_set_cardinality": len(goal_ids),
        "requested_goal_count": int(overlay.requested_goal_count),
        "heuristic_name": heuristic_name,
        "attachments": overlay.attachments_as_dicts(),
        "expansions": int(search.n_expanded),
        "generated": int(search.n_generated),
        "path_node_ids": list(search.path),
        "expansions_are_total_query_work": True,
    }
    if record_expanded:
        family_metrics["expanded_node_ids"] = list(search.expanded_nodes)
        graph_metrics["expanded_node_ids"] = list(search.expanded_nodes)
    metrics = {METRICS_KEY: family_metrics, "graph": graph_metrics}

    if not search.found:
        return _finish(
            status=PlanningStatus.UNSOLVED,
            metrics=metrics,
            query_s=query_s,
        )

    states = tuple(_state_from_node(overlay, nid, assembly) for nid in search.path)
    selected_id = (
        int(search.selected_goal_node_id)
        if search.selected_goal_node_id is not None
        else int(search.path[-1])
    )
    selected = _state_from_node(overlay, selected_id, assembly)
    family_metrics["selected_goal_node_id"] = selected_id
    graph_metrics["selected_goal_node_id"] = selected_id

    attachment_rec = overlay.attachment_for_goal_node(selected_id)
    attachment_residual = (
        None if attachment_rec is None else float(attachment_rec.attachment_residual_q)
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

    path_u = path_actuator_length(
        overlay,
        search.path,
        robot=problem.robot,
        edge_cost_mode="integrated",
        scene=problem.scene,
        n_samples=int(edge_n_samples),
        assembly_state=assembly,
    )
    path_q = float(
        sum(
            np.linalg.norm(states[i + 1].q - states[i].q)
            for i in range(len(states) - 1)
        )
    )
    return _finish(
        status=PlanningStatus.SUCCESS,
        trajectory=Trajectory(states=states),
        selected=selected,
        candidate=selected_candidate,
        cost=float(search.cost),
        length_u=path_u,
        length_q=path_q,
        metrics=metrics,
        query_s=query_s,
        attachment_residual=attachment_residual,
    )
