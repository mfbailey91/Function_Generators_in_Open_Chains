"""Version 3.3 tests: lattice connectivity, integrated cost, overlay, smoke."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import (
    GraphSearchPlanner,
    OperatingBranchRobotModel,
    integrated_actuator_edge_cost,
)
from inequality_mechanisms.benchmarks.smoke_lattice_2r import (
    COST_TOL,
    build_paired_lattice_arms,
    run_lattice_query,
    run_lattice_smoke_pack,
)
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    ConstraintSet,
    EndpointDeclaredMotion,
    ExactOutputGoal,
    FreeSpaceScene,
    OutputLinearMotion,
    PhysicalState,
    PlanningProblem,
    PlanningStatus,
)
from inequality_mechanisms.graphs import LatticeConnectivity, TensorGridTopology
from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.mechanisms import equivalent_gearbox_branch


def test_topology_axis_vs_chebyshev_neighbors() -> None:
    axis = TensorGridTopology((3, 3), connectivity=LatticeConnectivity.AXIS_ALIGNED)
    cheb = TensorGridTopology((3, 3), connectivity=LatticeConnectivity.CHEBYSHEV_1)
    corner = axis.node_id((0, 0))
    center = axis.node_id((1, 1))
    assert set(axis.neighbors(corner)) == {
        axis.node_id((1, 0)),
        axis.node_id((0, 1)),
    }
    assert set(cheb.neighbors(corner)) == {
        cheb.node_id((1, 0)),
        cheb.node_id((0, 1)),
        cheb.node_id((1, 1)),
    }
    assert len(axis.neighbors(center)) == 4
    assert len(cheb.neighbors(center)) == 8
    # Default remains axis-aligned for V2 parity.
    default = TensorGridTopology((3, 3))
    assert default.connectivity is LatticeConnectivity.AXIS_ALIGNED


def test_integrated_vs_endpoint_edge_cost_on_fourbar() -> None:
    branch = fourbar_2d_branch()
    shared = UniformOutputLattice.from_output_space(
        branch.output_space,
        shape=(6, 6),
        connectivity=LatticeConnectivity.CHEBYSHEV_1,
    )
    graph = EmbeddedPlanningGraph.from_output_lattice(shared, branch)
    robot = OperatingBranchRobotModel(branch=branch)
    a = graph.topology.node_id((1, 1))
    nbs = list(graph.neighbors(a))
    assert nbs
    b = nbs[-1]  # last neighbor often includes a diagonal under chebyshev order
    endpoint = float(np.linalg.norm(graph.u_state(b) - graph.u_state(a)))
    integrated = integrated_actuator_edge_cost(graph, robot)(a, b)
    assert integrated >= endpoint - 1e-9
    start = PhysicalState(
        u=graph.u_state(a),
        q=graph.q_state(a),
        assembly_state=robot.state_from_input(graph.u_state(a)).assembly_state,
    )
    end = PhysicalState(
        u=graph.u_state(b),
        q=graph.q_state(b),
        assembly_state=start.assembly_state,
    )
    motion = OutputLinearMotion(robot=robot, n_samples=32).connect(start, end)
    assert motion is not None
    assert float(motion.parameters["actuator_path_length"]) == pytest.approx(
        integrated, abs=1e-9
    )


def test_exact_start_overlay_no_start_tolerance() -> None:
    arms = build_paired_lattice_arms(
        connectivity=LatticeConnectivity.CHEBYSHEV_1
    )
    arm = arms["fourbar"]
    topo = arm.graph.topology
    q_a = arm.graph.q_state(topo.node_id((1, 1)))
    q_b = arm.graph.q_state(topo.node_id((2, 2)))
    q_start = 0.5 * (q_a + q_b)
    q_c = arm.graph.q_state(topo.node_id((3, 3)))
    q_d = arm.graph.q_state(topo.node_id((4, 4)))
    q_goal = 0.5 * (q_c + q_d)
    start = arm.robot.states_from_output(q_start)[0].state
    problem = PlanningProblem(
        robot=arm.robot,
        scene=FreeSpaceScene(robot=arm.robot),
        start=start,
        goal=ExactOutputGoal(q_goal=q_goal),
        path_constraints=ConstraintSet.empty(),
        local_motion=EndpointDeclaredMotion(),
        objective=ActuatorTravelObjective(),
    )
    assert not hasattr(problem, "start_tolerance")
    result = GraphSearchPlanner(
        graph=arm.graph,
        algorithm="dijkstra",
        edge_cost_mode="integrated",
        allow_query_overlay=True,
    ).solve(problem)
    assert result.status is PlanningStatus.SUCCESS
    assert result.planner_metrics["graph"]["overlay_used"] is True
    assert result.provenance.architecture_version == 3


@pytest.mark.parametrize("arm_name", ["fourbar", "gearbox"])
def test_dijkstra_astar_cost_parity_eight_integrated(arm_name: str) -> None:
    arms = build_paired_lattice_arms(
        connectivity=LatticeConnectivity.CHEBYSHEV_1
    )
    arm = arms[arm_name]  # type: ignore[index]
    start_id = arm.graph.topology.node_id((0, 0))
    goal_id = arm.graph.topology.node_id((5, 5))
    start = PhysicalState(
        u=arm.graph.u_state(start_id),
        q=arm.graph.q_state(start_id),
        assembly_state=arm.robot.state_from_input(
            arm.graph.u_state(start_id)
        ).assembly_state,
    )
    problem = PlanningProblem(
        robot=arm.robot,
        scene=FreeSpaceScene(robot=arm.robot),
        start=start,
        goal=ExactOutputGoal(q_goal=arm.graph.q_state(goal_id)),
        path_constraints=ConstraintSet.empty(),
        local_motion=EndpointDeclaredMotion(),
        objective=ActuatorTravelObjective(),
    )
    d = run_lattice_query(
        arm, problem, algorithm="dijkstra", edge_cost_mode="integrated"
    )
    a = run_lattice_query(
        arm, problem, algorithm="astar", edge_cost_mode="integrated"
    )
    assert d.status is PlanningStatus.SUCCESS
    assert a.status is PlanningStatus.SUCCESS
    assert d.objective_cost == pytest.approx(a.objective_cost, abs=COST_TOL)
    assert d.path_length_u == pytest.approx(d.objective_cost, abs=1e-8)


def test_lattice_smoke_pack_rows() -> None:
    rows = run_lattice_smoke_pack()
    assert len(rows) >= 13  # 3 configs × 2 mechs × 2 algs + overlay
    assert all(r["architecture_version"] == 3 for r in rows)
    assert all(r["status"] == str(PlanningStatus.SUCCESS) for r in rows)
    overlay = [r for r in rows if r["config"] == "eight_integrated_overlay"]
    assert len(overlay) == 1
    assert overlay[0]["overlay_used"] is True


def test_compatibility_fixture_still_endpoint_default() -> None:
    """V3.1 compatibility path uses endpoint cost (planner default)."""
    fourbar = fourbar_2d_branch()
    gearbox = equivalent_gearbox_branch(fourbar, name="span_matched_gearbox")
    shared = UniformOutputLattice.from_output_space(
        fourbar.output_space, shape=(6, 6)
    )
    assert shared.topology.connectivity is LatticeConnectivity.AXIS_ALIGNED
    graph = EmbeddedPlanningGraph.from_output_lattice(shared, gearbox)
    planner = GraphSearchPlanner(graph=graph, algorithm="dijkstra")
    assert planner.edge_cost_mode == "endpoint"
    assert planner.planner_id == "graph_search_dijkstra_endpoint"
