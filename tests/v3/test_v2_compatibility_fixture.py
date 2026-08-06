"""V2 vs V3 shared-Q compatibility fixture (Sprint V3.1 / V3-103)."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import GraphSearchPlanner, OperatingBranchRobotModel
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    ConstraintSet,
    EndpointDeclaredMotion,
    ExactOutputGoal,
    FreeSpaceScene,
    PhysicalState,
    PlanningProblem,
    PlanningStatus,
)
from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.mechanisms import equivalent_gearbox_branch
from inequality_mechanisms.search.graph_solver import (
    AStarGraphSolver,
    DijkstraGraphSolver,
)
from inequality_mechanisms.search.v2_objectives import resolve_v2_objective

COST_TOL = 1e-10


def _paired_graphs(shape: tuple[int, int] = (6, 6)):
    fourbar = fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    shared = UniformOutputLattice.from_output_space(fourbar.output_space, shape=shape)
    return (
        fourbar,
        gearbox,
        EmbeddedPlanningGraph.from_output_lattice(shared, fourbar),
        EmbeddedPlanningGraph.from_output_lattice(shared, gearbox),
    )


def _corner_nodes(graph: EmbeddedPlanningGraph) -> tuple[int, int]:
    start = graph.topology.node_id((0, 0))
    goal = graph.topology.node_id((5, 5))
    assert graph.node_is_valid(start)
    assert graph.node_is_valid(goal)
    return start, goal


@pytest.mark.parametrize("algorithm", ["dijkstra", "astar"])
@pytest.mark.parametrize("arm", ["fourbar", "gearbox"])
def test_v2_v3_shared_q_compatibility(algorithm: str, arm: str) -> None:
    fourbar, gearbox, g_fb, g_gb = _paired_graphs()
    branch = fourbar if arm == "fourbar" else gearbox
    graph = g_fb if arm == "fourbar" else g_gb
    start_id, goal_id = _corner_nodes(graph)

    heuristic = "input_euclidean" if algorithm == "astar" else "zero"
    v2_objective = resolve_v2_objective(
        graph, goal_id, "actuator_travel", heuristic_name=heuristic
    )
    v2_solver = DijkstraGraphSolver() if algorithm == "dijkstra" else AStarGraphSolver()
    v2_result = v2_solver.solve(graph, start_id, goal_id, v2_objective)
    assert v2_result.found

    robot = OperatingBranchRobotModel(branch=branch)
    start_state = robot.state_from_input(graph.u_state(start_id))
    # Ensure q matches the lattice node exactly (shared-Q identity).
    start_state = type(start_state)(
        u=np.asarray(graph.u_state(start_id), dtype=np.float64),
        q=np.asarray(graph.q_state(start_id), dtype=np.float64),
        assembly_state=start_state.assembly_state,
    )
    goal = ExactOutputGoal(q_goal=np.asarray(graph.q_state(goal_id), dtype=np.float64))
    problem = PlanningProblem(
        robot=robot,
        scene=FreeSpaceScene(robot=robot),
        start=start_state,
        goal=goal,
        path_constraints=ConstraintSet.empty(),
        local_motion=EndpointDeclaredMotion(),
        objective=ActuatorTravelObjective(),
    )
    v3_planner = GraphSearchPlanner(graph=graph, algorithm=algorithm)  # type: ignore[arg-type]
    v3_result = v3_planner.solve(problem)

    assert v3_result.status is PlanningStatus.SUCCESS
    assert v3_result.objective_cost == pytest.approx(v2_result.cost, abs=COST_TOL)
    assert v3_result.planner_metrics["graph"]["expansions"] == v2_result.n_expanded
    assert v3_result.planner_metrics["graph"]["generated"] == v2_result.n_generated
    assert v3_result.planner_metrics["graph"]["path_node_ids"] == list(v2_result.path)
    assert v3_result.selected_goal_state is not None
    assert v3_result.selected_goal_state.q == pytest.approx(
        graph.q_state(goal_id), abs=1e-10
    )
    assert v3_result.selected_goal_state.u == pytest.approx(
        graph.u_state(goal_id), abs=1e-10
    )
    assert v3_result.provenance.architecture_version == 3


def test_shared_q_distinct_physical_states_across_mechanisms() -> None:
    fourbar, gearbox, g_fb, g_gb = _paired_graphs()
    # Interior node: shared Q identity with mechanism-dependent U for nonlinear maps.
    node_id = g_fb.topology.node_id((2, 3))
    assert g_fb.node_is_valid(node_id)
    assert g_gb.node_is_valid(node_id)
    assert g_fb.q_state(node_id) == pytest.approx(g_gb.q_state(node_id))

    robot_f = OperatingBranchRobotModel(branch=fourbar)
    robot_g = OperatingBranchRobotModel(branch=gearbox)
    s_f = PhysicalState(
        u=np.asarray(g_fb.u_state(node_id), dtype=np.float64),
        q=np.asarray(g_fb.q_state(node_id), dtype=np.float64),
        assembly_state=robot_f.state_from_input(g_fb.u_state(node_id)).assembly_state,
    )
    s_g = PhysicalState(
        u=np.asarray(g_gb.u_state(node_id), dtype=np.float64),
        q=np.asarray(g_gb.q_state(node_id), dtype=np.float64),
        assembly_state=robot_g.state_from_input(g_gb.u_state(node_id)).assembly_state,
    )
    assert s_f.q == pytest.approx(s_g.q)
    assert s_f is not s_g
    assert not np.allclose(s_f.u, s_g.u)
    assert s_f.assembly_state["mechanism_name"] != s_g.assembly_state["mechanism_name"]
