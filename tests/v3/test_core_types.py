"""Unit tests for Version 3 core types and serialization."""

from __future__ import annotations

import numpy as np
import pytest
from tests.graphs_v2._fixtures import fourbar_2d_branch

from inequality_mechanisms.adapters import OperatingBranchRobotModel
from inequality_mechanisms.core import (
    ActuatorTravelObjective,
    ExactOutputGoal,
    PhysicalState,
    PlannerCapabilities,
    physical_state_from_dict,
    physical_state_to_dict,
    planner_capabilities_from_dict,
    planner_capabilities_to_dict,
    planning_result_from_dict,
    planning_result_to_dict,
)
from inequality_mechanisms.core.results import (
    PlanningResult,
    PlanningStatus,
    ResultProvenance,
)


def test_physical_state_round_trip() -> None:
    state = PhysicalState(
        u=np.array([0.1, 0.2]),
        q=np.array([0.3, 0.4]),
        assembly_state={"branch_id": "abc"},
    )
    restored = physical_state_from_dict(physical_state_to_dict(state))
    assert restored.u == pytest.approx(state.u)
    assert restored.q == pytest.approx(state.q)
    assert restored.assembly_state == state.assembly_state


def test_planner_capabilities_round_trip() -> None:
    caps = PlannerCapabilities(
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
    restored = planner_capabilities_from_dict(planner_capabilities_to_dict(caps))
    assert restored == caps


def test_planning_result_round_trip() -> None:
    state = PhysicalState(u=np.array([1.0, 2.0]), q=np.array([3.0, 4.0]))
    result = PlanningResult(
        status=PlanningStatus.SUCCESS,
        trajectory=None,
        selected_goal_state=state,
        total_wall_time_s=0.01,
        query_time_s=0.01,
        objective_cost=1.5,
        path_length_u=1.5,
        path_length_q=2.0,
        path_length_x=None,
        task_class=None,
        final_goal_residual=None,
        planner_metrics={"graph": {"expansions": 3}},
        provenance=ResultProvenance(
            architecture_version=3,
            planner_id="graph_search_dijkstra",
        ),
    )
    restored = planning_result_from_dict(planning_result_to_dict(result))
    assert restored.status == PlanningStatus.SUCCESS
    assert restored.objective_cost == pytest.approx(1.5)
    assert restored.selected_goal_state is not None
    assert restored.selected_goal_state.u == pytest.approx(state.u)
    assert restored.planner_metrics["graph"]["expansions"] == 3


def test_operating_branch_robot_rejects_inconsistent_state() -> None:
    robot = OperatingBranchRobotModel(branch=fourbar_2d_branch())
    good = robot.state_from_input(np.array([0.2, 0.3]))
    assert robot.validate_state(good, 1e-8)
    bad = PhysicalState(u=good.u, q=good.q + 1.0, assembly_state=good.assembly_state)
    assert not robot.validate_state(bad, 1e-8)


def test_exact_output_goal_and_actuator_objective() -> None:
    goal = ExactOutputGoal(q_goal=np.array([0.0, 0.0]), tolerance=1e-6)
    start = PhysicalState(u=np.array([0.1, 0.0]), q=np.array([0.1, 0.0]))
    assert not goal.satisfied(start)
    assert goal.residual(start).primary == pytest.approx(0.1)
    obj = ActuatorTravelObjective()
    end = PhysicalState(u=np.array([0.4, 0.0]), q=np.array([0.4, 0.0]))
    assert obj.trajectory_cost((start, end)) == pytest.approx(0.3)
