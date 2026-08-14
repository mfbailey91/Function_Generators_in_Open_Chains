"""V3-632: true represented-goal multi-goal lattice graph search."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from tests.graphs_v2._fixtures import affine_1d_branch, fourbar_2d_branch

from inequality_mechanisms.adapters import GraphSearchPlanner
from inequality_mechanisms.adapters.lattice_edge_cost import (
    resolve_lattice_goal_set_objective,
)
from inequality_mechanisms.adapters.planar_2r_robot import (
    planar_2r_operating_branch_robot,
)
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    CartesianDiskGoal,
    ConstraintSet,
    ExactOutputGoal,
    FreeSpaceScene,
    InputLinearMotion,
    PhysicalState,
    PlanningProblem,
    PlanningStatus,
    StateCandidate,
)
from inequality_mechanisms.graphs import GoalSetQueryOverlay, QueryOverlayGraph
from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.graphs.topology import LatticeConnectivity
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.search.v2_objectives import (
    input_euclidean_goal_set_heuristic_v2,
)


def _affine_base() -> EmbeddedPlanningGraph:
    return EmbeddedPlanningGraph.from_uniform_output(affine_1d_branch(), shape=(8,))


def _fourbar_lattice(
    shape: tuple[int, int] = (6, 6),
) -> tuple[EmbeddedPlanningGraph, Any]:
    branch = fourbar_2d_branch()
    shared = UniformOutputLattice.from_output_space(
        branch.output_space,
        shape=shape,
        connectivity=LatticeConnectivity.CHEBYSHEV_1,
    )
    graph = EmbeddedPlanningGraph.from_output_lattice(shared, branch)
    robot = planar_2r_operating_branch_robot(branch, planar_fk=Planar2R(1.0, 1.0))
    return graph, robot


def _candidate_from_node(
    graph: EmbeddedPlanningGraph,
    robot: Any,
    node_id: int,
    *,
    index: int,
    sample_id: str,
) -> StateCandidate:
    state = PhysicalState(
        u=np.asarray(graph.u_state(node_id), dtype=np.float64),
        q=np.asarray(graph.q_state(node_id), dtype=np.float64),
        assembly_state=dict(robot.state_from_input(graph.u_state(node_id)).assembly_state),
        auxiliary_state={"lattice_node_id": int(node_id)},
    )
    tip = np.asarray(robot.forward_kinematics(state).position, dtype=np.float64)
    return StateCandidate(
        state=state,
        residual=0.0,
        provenance={
            "goal_sample_id": sample_id,
            "goal_sample_index": int(index),
            "goal_sample_point": tip.tolist(),
            "ik_family": "lattice_fixture",
            "candidate_generator_id": "v3_632_test",
        },
    )


def _problem_from_start_goal(
    robot: Any,
    start: PhysicalState,
    goal: Any,
) -> PlanningProblem:
    return PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=InputLinearMotion(robot=robot, n_samples=16),
        objective=ActuatorTravelObjective(),
    )


def test_goal_set_overlay_attaches_ordered_goals() -> None:
    base = _affine_base()
    start_q = 0.5 * (base.q_state(1) + base.q_state(2))
    goal_qs = [base.q_state(4), base.q_state(6), 0.5 * (base.q_state(3) + base.q_state(4))]
    overlay = GoalSetQueryOverlay(
        base=base,
        start_q=start_q,
        goal_qs=goal_qs,
        dedup_tol=1e-12,
    )
    assert overlay.start_node_id == base.node_count
    assert overlay.goal_node_ids[0] == 4
    assert overlay.goal_node_ids[1] == 6
    assert len(overlay.goal_node_ids) == 3
    assert overlay.requested_goal_count == 3
    goal_atts = [a for a in overlay.attachments if a.role == "goal"]
    assert [a.goal_index for a in goal_atts] == [0, 1, 2]


def test_single_goal_overlay_api_unchanged() -> None:
    base = _affine_base()
    overlay = QueryOverlayGraph(
        base=base,
        start_q=base.q_state(1),
        goal_q=base.q_state(5),
    )
    assert overlay.start_node_id == 1
    assert overlay.goal_node_id == 5
    assert overlay.node_count == base.node_count


def test_oracle_parity_exhaustive_single_goal_reference() -> None:
    graph, robot = _fourbar_lattice()
    topo = graph.topology
    start_id = topo.node_id((0, 0))
    goal_ids = [topo.node_id((2, 2)), topo.node_id((4, 1)), topo.node_id((3, 4))]
    start = PhysicalState(
        u=graph.u_state(start_id),
        q=graph.q_state(start_id),
        assembly_state=dict(robot.state_from_input(graph.u_state(start_id)).assembly_state),
    )
    candidates = [
        _candidate_from_node(graph, robot, gid, index=i, sample_id=f"g{i}")
        for i, gid in enumerate(goal_ids)
    ]
    tip = np.asarray(
        robot.forward_kinematics(candidates[0].state).position, dtype=np.float64
    )
    problem = _problem_from_start_goal(
        robot,
        start,
        CartesianDiskGoal(center=tip, radius=2.0, robot=robot),
    )
    multi = GraphSearchPlanner(
        graph=graph,
        algorithm="dijkstra",
        edge_cost_mode="endpoint",
        allow_query_overlay=True,
    ).solve_goal_set(problem, candidates)
    assert multi.status is PlanningStatus.SUCCESS

    oracle_costs: list[tuple[float, int]] = []
    for i, cand in enumerate(candidates):
        exact = _problem_from_start_goal(
            robot,
            start,
            ExactOutputGoal(q_goal=np.asarray(cand.state.q, dtype=np.float64)),
        )
        one = GraphSearchPlanner(
            graph=graph,
            algorithm="dijkstra",
            edge_cost_mode="endpoint",
            allow_query_overlay=True,
        ).solve(exact)
        assert one.status is PlanningStatus.SUCCESS
        assert one.objective_cost is not None
        oracle_costs.append((float(one.objective_cost), i))
    best_cost, best_idx = min(oracle_costs, key=lambda item: item[0])
    assert multi.objective_cost == pytest.approx(best_cost, abs=1e-9)
    assert multi.selected_goal_candidate is not None
    assert multi.selected_goal_candidate.provenance["goal_sample_id"] == f"g{best_idx}"


def test_dijkstra_astar_agree_on_cost_and_selected_goal() -> None:
    graph, robot = _fourbar_lattice()
    topo = graph.topology
    start_id = topo.node_id((0, 0))
    goal_ids = [topo.node_id((5, 5)), topo.node_id((1, 4)), topo.node_id((4, 0))]
    start = PhysicalState(
        u=graph.u_state(start_id),
        q=graph.q_state(start_id),
        assembly_state=dict(robot.state_from_input(graph.u_state(start_id)).assembly_state),
    )
    candidates = [
        _candidate_from_node(graph, robot, gid, index=i, sample_id=f"cand_{i}")
        for i, gid in enumerate(goal_ids)
    ]
    tip = np.asarray(
        robot.forward_kinematics(candidates[-1].state).position, dtype=np.float64
    )
    problem = _problem_from_start_goal(
        robot,
        start,
        CartesianDiskGoal(center=tip, radius=2.0, robot=robot),
    )
    d = GraphSearchPlanner(
        graph=graph, algorithm="dijkstra", edge_cost_mode="endpoint"
    ).solve_goal_set(problem, candidates)
    a = GraphSearchPlanner(
        graph=graph, algorithm="astar", edge_cost_mode="endpoint"
    ).solve_goal_set(problem, candidates)
    assert d.status is PlanningStatus.SUCCESS
    assert a.status is PlanningStatus.SUCCESS
    assert d.objective_cost == pytest.approx(a.objective_cost, abs=1e-9)
    assert d.planner_metrics["graph"]["selected_goal_node_id"] == (
        a.planner_metrics["graph"]["selected_goal_node_id"]
    )
    assert a.planner_metrics["graph"]["heuristic_name"] == "input_euclidean_goal_set"
    assert d.planner_metrics["graph"]["heuristic_name"] == "zero"


def test_goal_set_heuristic_zero_on_goals_and_admissible() -> None:
    graph, robot = _fourbar_lattice()
    topo = graph.topology
    goals = (topo.node_id((2, 2)), topo.node_id((4, 3)))
    overlay = GoalSetQueryOverlay(
        base=graph,
        start_q=graph.q_state(topo.node_id((0, 0))),
        goal_qs=[graph.q_state(g) for g in goals],
    )
    h = input_euclidean_goal_set_heuristic_v2(overlay, overlay.goal_node_ids)
    for gid in overlay.goal_node_ids:
        assert h(gid) == pytest.approx(0.0, abs=1e-12)
    objective = resolve_lattice_goal_set_objective(
        overlay,
        overlay.goal_node_ids,
        edge_cost_mode="endpoint",
        robot=robot,
        algorithm="astar",
    )
    assert objective.heuristic_name == "input_euclidean_goal_set"
    # Consistency / admissibility spot-check on a few edges.
    for nid in range(min(12, overlay.node_count)):
        if not overlay.node_is_valid(nid):
            continue
        for nb in overlay.neighbors(nid):
            c = float(objective.edge_cost(nid, nb))
            if not np.isfinite(c):
                continue
            assert objective.heuristic(nid) <= c + objective.heuristic(nb) + 1e-9


def test_expansions_are_total_query_work_not_winning_candidate_only() -> None:
    graph, robot = _fourbar_lattice()
    topo = graph.topology
    start_id = topo.node_id((0, 0))
    near = topo.node_id((1, 0))
    far = topo.node_id((5, 5))
    start = PhysicalState(
        u=graph.u_state(start_id),
        q=graph.q_state(start_id),
        assembly_state=dict(robot.state_from_input(graph.u_state(start_id)).assembly_state),
    )
    candidates = [
        _candidate_from_node(graph, robot, near, index=0, sample_id="near"),
        _candidate_from_node(graph, robot, far, index=1, sample_id="far"),
    ]
    tip = np.asarray(
        robot.forward_kinematics(candidates[0].state).position, dtype=np.float64
    )
    problem = _problem_from_start_goal(
        robot,
        start,
        CartesianDiskGoal(center=tip, radius=2.0, robot=robot),
    )
    multi = GraphSearchPlanner(
        graph=graph,
        algorithm="dijkstra",
        edge_cost_mode="endpoint",
        record_expanded=True,
    ).solve_goal_set(problem, candidates)
    assert multi.status is PlanningStatus.SUCCESS
    metrics = multi.planner_metrics["graph"]
    assert metrics["expansions_are_total_query_work"] is True
    assert metrics["goal_set_cardinality"] == 2
    assert int(metrics["expansions"]) == len(metrics["expanded_node_ids"])

    # Isolated near-goal query expands fewer (or equal) nodes than the full set
    # query when the far goal is also attached and reachable.
    near_only = GraphSearchPlanner(
        graph=graph,
        algorithm="dijkstra",
        edge_cost_mode="endpoint",
        record_expanded=True,
    ).solve(
        _problem_from_start_goal(
            robot, start, ExactOutputGoal(q_goal=graph.q_state(near))
        )
    )
    assert near_only.status is PlanningStatus.SUCCESS
    assert int(metrics["expansions"]) >= int(
        near_only.planner_metrics["graph"]["expansions"]
    )


def test_non_first_candidate_provenance_retained() -> None:
    graph, robot = _fourbar_lattice()
    topo = graph.topology
    start_id = topo.node_id((0, 0))
    far = topo.node_id((5, 5))
    near = topo.node_id((1, 1))
    # Put the cheaper goal second so selection cannot be "first candidate".
    goal_order = [far, near]
    start = PhysicalState(
        u=graph.u_state(start_id),
        q=graph.q_state(start_id),
        assembly_state=dict(robot.state_from_input(graph.u_state(start_id)).assembly_state),
    )
    candidates = [
        _candidate_from_node(graph, robot, gid, index=i, sample_id=f"order_{i}")
        for i, gid in enumerate(goal_order)
    ]
    tip = np.asarray(
        robot.forward_kinematics(candidates[1].state).position, dtype=np.float64
    )
    problem = _problem_from_start_goal(
        robot,
        start,
        CartesianDiskGoal(center=tip, radius=2.0, robot=robot),
    )
    result = GraphSearchPlanner(
        graph=graph, algorithm="dijkstra", edge_cost_mode="endpoint"
    ).solve_goal_set(problem, candidates)
    assert result.status is PlanningStatus.SUCCESS
    assert result.selected_goal_candidate is not None
    assert result.selected_goal_candidate.provenance["goal_sample_id"] == "order_1"
    assert result.selected_goal_candidate.provenance["goal_sample_index"] == 1
    assert result.selected_goal_candidate.provenance["ik_family"] == "lattice_fixture"


def test_physical_and_attachment_residuals_separated() -> None:
    graph, robot = _fourbar_lattice()
    topo = graph.topology
    start_id = topo.node_id((0, 0))
    goal_id = topo.node_id((3, 3))
    start = PhysicalState(
        u=graph.u_state(start_id),
        q=graph.q_state(start_id),
        assembly_state=dict(robot.state_from_input(graph.u_state(start_id)).assembly_state),
    )
    cand = _candidate_from_node(graph, robot, goal_id, index=0, sample_id="center")
    tip = np.asarray(robot.forward_kinematics(cand.state).position, dtype=np.float64)
    problem = _problem_from_start_goal(
        robot,
        start,
        CartesianDiskGoal(center=tip, radius=0.05, robot=robot),
    )
    result = GraphSearchPlanner(
        graph=graph, algorithm="dijkstra", edge_cost_mode="endpoint"
    ).solve_goal_set(problem, [cand])
    assert result.status is PlanningStatus.SUCCESS
    assert result.goal_residuals is not None
    assert result.goal_residuals.physical is not None
    assert result.final_goal_residual is result.goal_residuals.physical
    assert result.goal_residuals.attachment is not None
    assert np.isfinite(result.goal_residuals.attachment)
    # Physical residual is the disk residual, not attachment.
    assert result.goal_residuals.physical.primary == pytest.approx(
        float(problem.goal.residual(result.selected_goal_state).primary),  # type: ignore[union-attr]
        abs=1e-12,
    )


def test_fail_closed_empty_candidates_and_empty_overlay() -> None:
    graph, robot = _fourbar_lattice()
    topo = graph.topology
    start_id = topo.node_id((0, 0))
    start = PhysicalState(
        u=graph.u_state(start_id),
        q=graph.q_state(start_id),
        assembly_state=dict(robot.state_from_input(graph.u_state(start_id)).assembly_state),
    )
    tip = np.asarray(robot.forward_kinematics(start).position, dtype=np.float64)
    problem = _problem_from_start_goal(
        robot,
        start,
        CartesianDiskGoal(center=tip + np.array([0.2, 0.0]), radius=0.05, robot=robot),
    )
    empty = GraphSearchPlanner(
        graph=graph, algorithm="dijkstra", edge_cost_mode="endpoint"
    ).solve_goal_set(problem, [])
    assert empty.status is PlanningStatus.INVALID
    assert empty.planner_metrics["graph"]["goal_set_cardinality"] == 0

    with pytest.raises(ValueError, match="at least one goal"):
        GoalSetQueryOverlay(
            base=graph,
            start_q=graph.q_state(start_id),
            goal_qs=[],
        )


def test_exact_output_goal_solve_smoke_unchanged() -> None:
    graph, robot = _fourbar_lattice()
    topo = graph.topology
    start_id = topo.node_id((0, 0))
    goal_id = topo.node_id((2, 2))
    start = PhysicalState(
        u=graph.u_state(start_id),
        q=graph.q_state(start_id),
        assembly_state=dict(robot.state_from_input(graph.u_state(start_id)).assembly_state),
    )
    problem = _problem_from_start_goal(
        robot,
        start,
        ExactOutputGoal(q_goal=graph.q_state(goal_id)),
    )
    result = GraphSearchPlanner(
        graph=graph, algorithm="dijkstra", edge_cost_mode="endpoint"
    ).solve(problem)
    assert result.status is PlanningStatus.SUCCESS
    assert result.objective_cost is not None
    assert result.selected_goal_candidate is None
