"""OMPL adapter tests (Sprint V3.5 / V3-505).

Marked ``ompl`` and skipped cleanly when OMPL Python bindings are absent.
"""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.adapters.ompl import (
    is_ompl_available,
    ompl_version_string,
)
from inequality_mechanisms.adapters.ompl.state_space import (
    ROUND_TRIP_TOL,
    round_trip_residuals,
)
from inequality_mechanisms.benchmarks.smoke_ompl_2r import (
    run_ompl_parity_smoke_pack,
    run_ompl_smoke_task,
)
from inequality_mechanisms.benchmarks.smoke_sampling_2r import (
    SMOKE_SEED,
    build_paired_arms,
    build_problem,
    smoke_task_catalog,
)
from inequality_mechanisms.core.goals import CartesianDiskGoalGenerator
from inequality_mechanisms.core.results import PlanningStatus
from inequality_mechanisms.core.state import PhysicalState

pytestmark = [
    pytest.mark.ompl,
    pytest.mark.skipif(
        not is_ompl_available(),
        reason="OMPL Python bindings not installed",
    ),
]


def _planning_feasible_task():
    arms = build_paired_arms()
    tasks = [t for t in smoke_task_catalog(arms) if t.kind == "planning_feasible"]
    assert tasks
    task = tasks[0]
    return arms[task.mechanism], task


def test_physical_state_round_trip_within_tolerance() -> None:
    arm, task = _planning_feasible_task()
    start = build_problem(arm, task).start
    du, dq = round_trip_residuals(arm.robot, start)
    assert du <= ROUND_TRIP_TOL
    assert dq <= ROUND_TRIP_TOL


@pytest.mark.parametrize("planner_name", ["ompl_prm", "ompl_rrt_connect"])
def test_exact_start_preserved(planner_name: str) -> None:
    arm, task = _planning_feasible_task()
    problem = build_problem(arm, task)
    result = run_ompl_smoke_task(
        arm, task, planner_name=planner_name, seed=SMOKE_SEED, solve_time_s=3.0
    )
    assert result.status == PlanningStatus.SUCCESS
    assert result.trajectory is not None
    assert len(result.trajectory.states) >= 1
    first: PhysicalState = result.trajectory.states[0]
    np.testing.assert_allclose(first.u, problem.start.u, atol=1e-12)


@pytest.mark.parametrize("planner_name", ["ompl_prm", "ompl_rrt_connect"])
def test_direct_connector_classification_metrics_present(planner_name: str) -> None:
    arm, task = _planning_feasible_task()
    result = run_ompl_smoke_task(
        arm, task, planner_name=planner_name, seed=SMOKE_SEED, solve_time_s=3.0
    )
    assert "ompl" in result.planner_metrics
    ompl = result.planner_metrics["ompl"]
    assert "direct_connector_available" in ompl
    assert ompl["direct_connector_available"] is not None
    assert ompl["nn_distance"] == "euclidean_u"
    assert result.task_class is not None
    assert result.provenance.extras.get("nn_distance") == "euclidean_u"
    assert result.provenance.extras.get("ompl_version") == ompl_version_string()


@pytest.mark.parametrize("planner_name", ["ompl_prm", "ompl_rrt_connect"])
def test_success_on_free_space_planning_feasible(planner_name: str) -> None:
    arm, task = _planning_feasible_task()
    result = run_ompl_smoke_task(
        arm, task, planner_name=planner_name, seed=SMOKE_SEED, solve_time_s=5.0
    )
    assert result.status == PlanningStatus.SUCCESS
    assert result.objective_cost is not None
    assert result.objective_cost >= 0.0
    assert result.selected_goal_state is not None
    problem = build_problem(arm, task)
    assert problem.goal.satisfied(result.selected_goal_state)


def test_parity_same_task_class_and_success_when_native_succeeds() -> None:
    rows = run_ompl_parity_smoke_pack(seed=SMOKE_SEED, solve_time_s=5.0)
    assert rows
    for row in rows:
        assert row["same_task_class"], row
        assert row["both_success_when_native_success"], row


def test_ompl_planners_import_lazy_without_eager_core_dependency() -> None:
    """Planner classes are importable via the package once OMPL is present."""
    from inequality_mechanisms.adapters.ompl import (
        OmplPRMPlanner,
        OmplRRTConnectPlanner,
    )

    assert OmplPRMPlanner().planner_id == "ompl_prm"
    assert OmplRRTConnectPlanner().planner_id == "ompl_rrt_connect"


def test_goal_generator_required_wiring() -> None:
    """Smoke uses CartesianDiskGoalGenerator; planners accept it explicitly."""
    arm, task = _planning_feasible_task()
    fk = arm.robot.planar_fk
    assert fk is not None
    generator = CartesianDiskGoalGenerator(planar_fk=fk)
    from inequality_mechanisms.adapters.ompl import OmplPRMPlanner

    problem = build_problem(arm, task)
    result = OmplPRMPlanner(
        seed=SMOKE_SEED, goal_generator=generator, solve_time_s=3.0
    ).solve(problem)
    assert result.status in (
        PlanningStatus.SUCCESS,
        PlanningStatus.UNSOLVED,
        PlanningStatus.INVALID,
    )
