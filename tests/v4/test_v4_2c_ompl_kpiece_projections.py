"""V4-234: normalized U/Q/X projections and KPIECE adapters."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from inequality_mechanisms.adapters.ompl._availability import is_ompl_available
from inequality_mechanisms.adapters.ompl.kpiece import (
    OmplKPIECEPlanner,
    nonprojection_config_json,
    resolved_kpiece_config,
)
from inequality_mechanisms.adapters.ompl.planner_geometry import (
    kpiece_ompl_geometry,
    primary_ompl_geometry,
)
from inequality_mechanisms.adapters.ompl.projections import (
    ProjectionRejectedError,
    ProjectionSpec,
    affine_unit,
    make_projection_spec,
    mounted_q_bounds,
    project_physical_state,
)
from inequality_mechanisms.benchmarks.smoke_sampling_2r import (
    SMOKE_SEED,
    build_paired_arms,
    build_problem,
    smoke_task_catalog,
)
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.results import PlanningStatus
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.kinematics.planar_2r_goals import CartesianDiskGoalGenerator

REPO_ROOT = Path(__file__).resolve().parents[2]
_PROJECTIONS = (
    "normalized_u",
    "normalized_mounted_q",
    "normalized_cartesian_x",
)
_PLANNER_IDS = {
    "normalized_u": "ompl_kpiece_u",
    "normalized_mounted_q": "ompl_kpiece_q",
    "normalized_cartesian_x": "ompl_kpiece_x",
}


def _script_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    return env


def _planning_feasible_problem():
    arms = build_paired_arms()
    tasks = [t for t in smoke_task_catalog(arms) if t.kind == "planning_feasible"]
    assert tasks
    task = tasks[0]
    return arms[task.mechanism], task, build_problem(arms[task.mechanism], task)


def _interior_state(robot: Any) -> PhysicalState:
    lo = np.asarray(robot.input_domain.lower, dtype=np.float64)
    hi = np.asarray(robot.input_domain.upper, dtype=np.float64)
    return robot.state_from_input(0.5 * (lo + hi))


def test_kpiece_geometry_is_projection_diagnostic() -> None:
    cells = (1.0 / 12.0, 1.0 / 12.0)
    record = kpiece_ompl_geometry("normalized_u", cells)
    payload = record.to_dict()
    assert payload["planner_role"] == "projection_diagnostic"
    assert payload["exploration_projection"] == "normalized_u"
    assert payload["projection_normalization"] == "minmax_unit"
    assert payload["projection_cell_sizes"] == list(cells)
    assert payload["state_coordinates"] == "u"
    control = primary_ompl_geometry().to_dict()
    assert control["exploration_projection"] == "none"
    assert control["projection_cell_sizes"] == []


def test_analytic_unit_box_at_bounds_and_midpoint() -> None:
    robot = build_paired_arms()["fourbar"].robot
    q_lo, q_hi = mounted_q_bounds(robot)
    for strategy in _PROJECTIONS:
        spec = make_projection_spec(
            strategy, robot, q_lower=q_lo, q_upper=q_hi, mechanism_id="fourbar"
        )
        lo = np.asarray(spec.lower)
        hi = np.asarray(spec.upper)
        np.testing.assert_allclose(affine_unit(lo, lo, hi), np.zeros_like(lo))
        np.testing.assert_allclose(affine_unit(hi, lo, hi), np.ones_like(hi))
        np.testing.assert_allclose(
            affine_unit(0.5 * (lo + hi), lo, hi), 0.5 * np.ones_like(lo)
        )
        assert spec.cell_sizes == tuple(1.0 / 12.0 for _ in range(spec.dimension))


def test_paired_mechanisms_share_q_and_x_but_not_u() -> None:
    arms = build_paired_arms()
    four = arms["fourbar"].robot
    gear = arms["gearbox"].robot
    q_lo, q_hi = mounted_q_bounds(four)
    np.testing.assert_allclose(q_lo, mounted_q_bounds(gear)[0])
    np.testing.assert_allclose(q_hi, mounted_q_bounds(gear)[1])
    q_mid = 0.5 * (q_lo + q_hi)
    four_state = four.states_from_output(q_mid)[0].state
    gear_state = gear.states_from_output(q_mid)[0].state
    np.testing.assert_allclose(four_state.q, gear_state.q, atol=1e-9)
    assert float(np.linalg.norm(four_state.u - gear_state.u)) > 1e-6
    spec_q_f = make_projection_spec(
        "normalized_mounted_q", four, mechanism_id="fourbar"
    )
    spec_q_g = make_projection_spec(
        "normalized_mounted_q", gear, mechanism_id="gearbox"
    )
    np.testing.assert_allclose(
        project_physical_state(four_state, spec_q_f, four),
        project_physical_state(gear_state, spec_q_g, gear),
        atol=1e-9,
    )
    spec_x_f = make_projection_spec(
        "normalized_cartesian_x",
        four,
        q_lower=q_lo,
        q_upper=q_hi,
        mechanism_id="fourbar",
    )
    spec_x_g = make_projection_spec(
        "normalized_cartesian_x",
        gear,
        q_lower=q_lo,
        q_upper=q_hi,
        mechanism_id="gearbox",
    )
    np.testing.assert_allclose(spec_x_f.lower, spec_x_g.lower)
    np.testing.assert_allclose(spec_x_f.upper, spec_x_g.upper)
    np.testing.assert_allclose(
        project_physical_state(four_state, spec_x_f, four),
        project_physical_state(gear_state, spec_x_g, gear),
        atol=1e-9,
    )
    spec_u_f = make_projection_spec("normalized_u", four, mechanism_id="fourbar")
    spec_u_g = make_projection_spec("normalized_u", gear, mechanism_id="gearbox")
    u_f = project_physical_state(four_state, spec_u_f, four)
    u_g = project_physical_state(gear_state, spec_u_g, gear)
    assert float(np.linalg.norm(u_f - u_g)) > 1e-6


def test_finite_difference_continuity_away_from_bounds() -> None:
    robot = build_paired_arms()["fourbar"].robot
    q_lo, q_hi = mounted_q_bounds(robot)
    base = _interior_state(robot)
    step = 1e-6
    for strategy in _PROJECTIONS:
        spec = make_projection_spec(
            strategy, robot, q_lower=q_lo, q_upper=q_hi, mechanism_id="fourbar"
        )
        p0 = project_physical_state(base, spec, robot)
        bumped = robot.state_from_input(base.u + step)
        p1 = project_physical_state(bumped, spec, robot)
        slope = float(np.linalg.norm(p1 - p0) / step)
        assert np.isfinite(slope)
        assert slope < 1e3


def test_degenerate_bounds_raise_with_ids() -> None:
    with pytest.raises(ProjectionRejectedError, match="degenerate") as caught:
        ProjectionSpec(
            projection_id="normalized_u",
            strategy="normalized_u",
            lower=(0.0, 1.0),
            upper=(1.0, 1.0),
            cell_sizes=(0.1, 0.1),
            formula="pi_U",
            task_id="task_a",
            mechanism_id="fourbar",
        )
    err = caught.value
    assert err.task_id == "task_a"
    assert err.mechanism_id == "fourbar"
    assert err.projection_id == "normalized_u"


def test_cell_sizes_match_user_configuration() -> None:
    robot = build_paired_arms()["fourbar"].robot
    spec = make_projection_spec(
        "normalized_u", robot, cells_per_axis=16, mechanism_id="fourbar"
    )
    assert spec.cell_sizes == (1.0 / 16.0, 1.0 / 16.0)
    planner = OmplKPIECEPlanner(projection="normalized_u", cells_per_axis=16)
    payload = resolved_kpiece_config(planner, spec)
    assert payload["cell_sizes"] == [1.0 / 16.0, 1.0 / 16.0]
    assert payload["planner_geometry"]["projection_cell_sizes"] == [
        1.0 / 16.0,
        1.0 / 16.0,
    ]


def test_factor_isolation_json_is_byte_identical_without_projection_fields() -> None:
    robot = build_paired_arms()["fourbar"].robot
    q_lo, q_hi = mounted_q_bounds(robot)
    blobs: list[str] = []
    for strategy in _PROJECTIONS:
        planner = OmplKPIECEPlanner(
            projection=strategy,  # type: ignore[arg-type]
            seed=3,
            range_fraction=0.2,
            goal_bias=0.07,
            border_fraction=0.85,
            min_valid_path_fraction=0.4,
            cells_per_axis=12,
            solve_time_s=1.5,
        )
        spec = make_projection_spec(
            strategy, robot, q_lower=q_lo, q_upper=q_hi, mechanism_id="fourbar"
        )
        blobs.append(nonprojection_config_json(resolved_kpiece_config(planner, spec)))
        assert planner.planner_id == _PLANNER_IDS[strategy]
    assert blobs[0] == blobs[1] == blobs[2]
    json.loads(blobs[0])


def test_lazy_kpiece_import_does_not_import_ompl() -> None:
    code = (
        "import sys\n"
        "from inequality_mechanisms.adapters.ompl import OmplKPIECEPlanner\n"
        "from inequality_mechanisms.adapters.ompl.projections import ProjectionSpec\n"
        "assert 'ompl' not in sys.modules\n"
        "assert OmplKPIECEPlanner().planner_id == 'ompl_kpiece_u'\n"
        "assert OmplKPIECEPlanner(projection='normalized_mounted_q').planner_id"
        " == 'ompl_kpiece_q'\n"
        "assert OmplKPIECEPlanner(projection='normalized_cartesian_x').planner_id"
        " == 'ompl_kpiece_x'\n"
        "assert ProjectionSpec is not None\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=_script_env(),
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_shared_path_projection_plot(tmp_path: Path) -> None:
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    robot = build_paired_arms()["fourbar"].robot
    q_lo, q_hi = mounted_q_bounds(robot)
    lo = np.asarray(robot.input_domain.lower)
    hi = np.asarray(robot.input_domain.upper)
    fracs = np.linspace(0.3, 0.7, 16)
    states = [robot.state_from_input(lo + f * (hi - lo)) for f in fracs]
    fig, axes = plt.subplots(1, 3, figsize=(9, 3))
    for ax, strategy in zip(axes, _PROJECTIONS, strict=True):
        spec = make_projection_spec(
            strategy, robot, q_lower=q_lo, q_upper=q_hi, mechanism_id="fourbar"
        )
        pts = np.stack([project_physical_state(s, spec, robot) for s in states])
        ax.plot(pts[:, 0], pts[:, 1], marker="o")
        ax.set_title(strategy)
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-0.05, 1.05)
        ax.set_aspect("equal")
    path = tmp_path / "kpiece_projection_views.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    assert path.is_file()
    assert path.stat().st_size > 0


@pytest.mark.ompl
@pytest.mark.skipif(
    not is_ompl_available(), reason="OMPL Python bindings not installed"
)
@pytest.mark.parametrize("strategy", list(_PROJECTIONS))
def test_kpiece_smoke_exact_start_and_cost(strategy: str) -> None:
    arm, _task, problem = _planning_feasible_problem()
    fk = arm.robot.planar_fk
    assert fk is not None
    planner = OmplKPIECEPlanner(
        projection=strategy,  # type: ignore[arg-type]
        seed=SMOKE_SEED,
        goal_generator=CartesianDiskGoalGenerator(planar_fk=fk),
        solve_time_s=5.0,
    )
    result = planner.solve(problem)
    assert result.status in (
        PlanningStatus.SUCCESS,
        PlanningStatus.UNSOLVED,
        PlanningStatus.INVALID,
    )
    extras = dict(result.provenance.extras)
    assert extras["nn_distance"] == "euclidean_u"
    assert extras["planner_geometry"]["planner_role"] == "projection_diagnostic"
    assert extras["planner_geometry"]["state_coordinates"] == "u"
    assert extras["planner_geometry"]["exploration_projection"] == strategy
    assert extras["ompl_planner"] == "KPIECE1"
    assert planner.planner_id == _PLANNER_IDS[strategy]
    assert extras["family_metrics"]["projection"]["cell_sizes"] == list(
        extras["planner_geometry"]["projection_cell_sizes"]
    )
    if result.status is PlanningStatus.SUCCESS:
        assert result.trajectory is not None
        first = result.trajectory.states[0]
        np.testing.assert_allclose(first.u, problem.start.u, atol=1e-12)
        assert problem.goal.satisfied(result.selected_goal_state)
        expected = ActuatorTravelObjective().trajectory_cost(result.trajectory.states)
        assert result.objective_cost == pytest.approx(expected)
