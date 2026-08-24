"""V4-232: planner-geometry record, fail-closed gates, and OMPL-free session helpers."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from inequality_mechanisms.adapters.ompl.planner_base import solve_with_ompl_planner
from inequality_mechanisms.adapters.ompl.planner_geometry import (
    PlannerGeometryRecord,
    primary_ompl_geometry,
)
from inequality_mechanisms.adapters.ompl.session import (
    OmplSolveSession,
    finalize_ompl_result,
    run_checkpointed,
    run_single_shot,
)
from inequality_mechanisms.benchmarks.smoke_sampling_2r import (
    build_paired_arms,
    build_problem,
    smoke_task_catalog,
)
from inequality_mechanisms.core.local_motion import OutputLinearMotion
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.results import PlanningStatus

REPO_ROOT = Path(__file__).resolve().parents[2]


def _script_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    return env


def _planning_feasible_problem():
    arms = build_paired_arms()
    tasks = [t for t in smoke_task_catalog(arms) if t.kind == "planning_feasible"]
    assert tasks
    task = tasks[0]
    return build_problem(arms[task.mechanism], task)


class _DummyObjective:
    """PlanningObjective stand-in that is not actuator travel."""

    @property
    def objective_id(self) -> str:
        return "dummy_unsupported"

    def trajectory_cost(self, states: tuple[Any, ...]) -> float:
        return 0.0


class _FakePdef:
    def __init__(
        self,
        *,
        has_any: bool = False,
        has_exact: bool = False,
        difference: float = 0.0,
        path: Any = None,
    ) -> None:
        self._has_any = has_any
        self._has_exact = has_exact
        self._difference = difference
        self._path = path

    def hasSolution(self) -> bool:  # noqa: N802
        return self._has_any

    def hasExactSolution(self) -> bool:  # noqa: N802
        return self._has_exact

    def getSolutionDifference(self) -> float:  # noqa: N802
        return self._difference

    def getSolutionPath(self) -> Any:  # noqa: N802
        return self._path


class _FakePath:
    def length(self) -> float:
        return 1.25


class _FakePlanner:
    def __init__(
        self,
        pdef: _FakePdef,
        *,
        exact: bool = False,
        approximate: bool = False,
        path: Any = None,
    ) -> None:
        self.pdef = pdef
        self.exact = exact
        self.approximate = approximate
        self.path = path
        self.solve_times: list[float] = []

    def solve(self, t: float) -> str:
        self.solve_times.append(float(t))
        if self.exact:
            self.pdef._has_any = True
            self.pdef._has_exact = True
            self.pdef._path = self.path
            return "exact"
        if self.approximate:
            self.pdef._has_any = True
            self.pdef._has_exact = False
            self.pdef._path = self.path
            return "approximate"
        return "timeout"


def _session_for_fake_planner(pdef: _FakePdef) -> OmplSolveSession:
    problem = _planning_feasible_problem()
    return OmplSolveSession(
        problem=problem,
        planner_id="ompl_prm",
        geometry=primary_ompl_geometry(),
        seed=7,
        repetition_index=0,
        code_revision=None,
        goal_generator=None,
        max_goal_candidates=8,
        solve_time_s=0.6,
        extras={"nn_distance": "euclidean_u", "ompl_planner": "PRM"},
        ompl_metrics={"planner_data": {}, "ompl_solved": False},
        t0=time.perf_counter(),
        rng=None,
        start_valid=True,
        goal_usable=True,
        already_satisfied=False,
        pdef=pdef,
        task_class="direct/local feasible",
    )


def test_primary_ompl_geometry_emits_canonical_dict() -> None:
    record = primary_ompl_geometry()
    assert record.to_dict() == {
        "planner_role": "architecture_control",
        "state_coordinates": "u",
        "sampling_measure": "uniform_raw_u",
        "nearest_neighbor_distance": "euclidean_u",
        "optimization_objective": "actuator_travel",
        "cost_to_go_heuristic": "none",
        "exploration_projection": "none",
        "projection_normalization": "none",
        "projection_cell_sizes": [],
        "goal_representation": "finite_goal_states",
        "local_motion_model": "input_linear",
    }


def test_illegal_geometry_field_raises() -> None:
    with pytest.raises(ValueError, match="planner_role"):
        replace(primary_ompl_geometry(), planner_role="optimizing_search")
    with pytest.raises(ValueError, match="projection_cell_sizes"):
        replace(primary_ompl_geometry(), projection_cell_sizes=(0.1, 0.1))
    with pytest.raises(ValueError, match="state_coordinates"):
        PlannerGeometryRecord(
            planner_role="architecture_control",
            state_coordinates="q",
            sampling_measure="uniform_raw_u",
            nearest_neighbor_distance="euclidean_u",
            optimization_objective="actuator_travel",
            cost_to_go_heuristic="none",
            exploration_projection="none",
            projection_normalization="none",
            projection_cell_sizes=(),
            goal_representation="finite_goal_states",
            local_motion_model="input_linear",
        )


def test_unsupported_objective_fails_before_make_planner() -> None:
    problem = replace(_planning_feasible_problem(), objective=_DummyObjective())
    called: list[Any] = []

    def make_planner(si: Any) -> Any:
        called.append(si)
        raise AssertionError("make_planner must not run")

    with pytest.raises(ValueError, match="ActuatorTravelObjective"):
        solve_with_ompl_planner(
            problem,
            planner_id="ompl_prm",
            make_planner=make_planner,
            seed=7,
            repetition_index=0,
            code_revision=None,
            goal_generator=None,
            max_goal_candidates=8,
            solve_time_s=0.1,
        )
    assert called == []
    assert isinstance(ActuatorTravelObjective(), ActuatorTravelObjective)


def test_output_linear_motion_fails_before_make_planner() -> None:
    problem = _planning_feasible_problem()
    unsupported = replace(
        problem,
        local_motion=OutputLinearMotion(robot=problem.robot, n_samples=12),
    )
    called: list[Any] = []

    def make_planner(si: Any) -> Any:
        called.append(si)
        raise AssertionError("make_planner must not run")

    with pytest.raises(ValueError, match="InputLinearMotion only"):
        solve_with_ompl_planner(
            unsupported,
            planner_id="ompl_prm",
            make_planner=make_planner,
            seed=7,
            repetition_index=0,
            code_revision=None,
            goal_generator=None,
            max_goal_candidates=8,
            solve_time_s=0.1,
        )
    assert called == []


def test_single_shot_and_checkpointed_snapshot_shape() -> None:
    path = _FakePath()
    pdef_shot = _FakePdef()
    planner_shot = _FakePlanner(pdef_shot, exact=True, path=path)
    session_shot = _session_for_fake_planner(pdef_shot)
    returned = run_single_shot(session_shot, planner_shot)
    assert returned is path
    assert planner_shot.solve_times == [pytest.approx(0.6)]
    metrics = session_shot.ompl_metrics
    assert metrics["ompl_solved"] is True
    assert metrics["ompl_exact_solution"] is True
    assert metrics["ompl_approximate_solution"] is False
    assert metrics["stepwise_history"] == "unavailable"
    assert isinstance(metrics["planner_data"], dict)

    pdef_ckpt = _FakePdef()
    planner_ckpt = _FakePlanner(pdef_ckpt, exact=True, path=path)
    session_ckpt = _session_for_fake_planner(pdef_ckpt)
    returned_ckpt = run_checkpointed(session_ckpt, planner_ckpt, (0.1, 0.3, 0.6))
    assert returned_ckpt is path
    assert planner_ckpt.solve_times == [
        pytest.approx(0.1),
        pytest.approx(0.2),
        pytest.approx(0.3),
    ]
    records = session_ckpt.ompl_metrics["checkpoints"]
    assert len(records) == 3
    for record in records:
        assert set(record) >= {
            "checkpoint_s",
            "remaining_s",
            "ompl_status",
            "ompl_solved",
            "ompl_exact_solution",
            "ompl_solution_difference",
            "best_cost",
            "planner_data",
        }
    assert records[-1]["ompl_exact_solution"] is True
    assert records[-1]["best_cost"] == pytest.approx(1.25)
    assert session_ckpt.ompl_metrics["planner_data"] == records[-1]["planner_data"]
    assert session_ckpt.ompl_metrics["stepwise_history"] == "unavailable"


def test_approximate_only_solution_stays_unsolved() -> None:
    pdef = _FakePdef()
    planner = _FakePlanner(pdef, approximate=True, path=_FakePath())
    session = _session_for_fake_planner(pdef)
    path = run_single_shot(session, planner)
    assert path is None
    assert session.ompl_metrics["ompl_solved"] is True
    assert session.ompl_metrics["ompl_exact_solution"] is False
    assert session.ompl_metrics["ompl_approximate_solution"] is True
    result = finalize_ompl_result(session, planner, path)
    assert result.status is PlanningStatus.UNSOLVED
    assert result.trajectory is None
    assert result.provenance.extras["nn_distance"] == "euclidean_u"
    assert result.provenance.extras["ompl_planner"] == "PRM"


def test_session_and_geometry_import_does_not_import_ompl() -> None:
    code = (
        "import sys\n"
        "from inequality_mechanisms.adapters.ompl import planner_geometry\n"
        "from inequality_mechanisms.adapters.ompl import session\n"
        "assert 'ompl' not in sys.modules\n"
        "assert planner_geometry.primary_ompl_geometry().planner_role\n"
        "assert session.build_ompl_session is not None\n"
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
