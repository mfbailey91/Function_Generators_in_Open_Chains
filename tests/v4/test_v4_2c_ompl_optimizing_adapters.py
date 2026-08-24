"""V4-233: RRT*, FMT, and BIT* adapters on the shared OMPL session."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from inequality_mechanisms.adapters.ompl._availability import is_ompl_available
from inequality_mechanisms.adapters.ompl.binding import (
    OmplBindingRejectedError,
    apply_ompl_method,
    apply_projection_cell_sizes,
    checkpoint_costs_nonincreasing,
    require_ompl_methods,
)
from inequality_mechanisms.adapters.ompl.bit_star import OmplBITStarPlanner
from inequality_mechanisms.adapters.ompl.fmt import OmplFMTPlanner
from inequality_mechanisms.adapters.ompl.planner_geometry import (
    optimizing_ompl_geometry,
    primary_ompl_geometry,
)
from inequality_mechanisms.adapters.ompl.rrt_star import OmplRRTStarPlanner
from inequality_mechanisms.benchmarks.smoke_sampling_2r import (
    SMOKE_SEED,
    build_paired_arms,
    build_problem,
    smoke_task_catalog,
)
from inequality_mechanisms.core.objectives import ActuatorTravelObjective
from inequality_mechanisms.core.results import PlanningStatus
from inequality_mechanisms.kinematics.planar_2r_goals import CartesianDiskGoalGenerator

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
    return arms[task.mechanism], task, build_problem(arms[task.mechanism], task)


class _IncompleteStar:
    def setRange(self, value: float) -> None:  # noqa: N802
        self.range = value


def test_optimizing_geometry_is_distinct_from_architecture_control() -> None:
    control = primary_ompl_geometry().to_dict()
    optimizing = optimizing_ompl_geometry().to_dict()
    assert control["planner_role"] == "architecture_control"
    assert optimizing["planner_role"] == "primary_optimizing"
    skipped = {"planner_role", "cost_to_go_heuristic"}
    for key in control:
        if key in skipped:
            continue
        assert optimizing[key] == control[key]
    heuristic = optimizing_ompl_geometry(cost_to_go_heuristic="euclidean_u")
    assert heuristic.cost_to_go_heuristic == "euclidean_u"


def test_lazy_optimizing_imports_do_not_import_ompl() -> None:
    code = (
        "import sys\n"
        "from inequality_mechanisms.adapters.ompl import (\n"
        "    OmplBITStarPlanner,\n"
        "    OmplFMTPlanner,\n"
        "    OmplRRTStarPlanner,\n"
        ")\n"
        "from inequality_mechanisms.adapters.ompl import binding\n"
        "assert 'ompl' not in sys.modules\n"
        "assert OmplRRTStarPlanner().planner_id == 'ompl_rrt_star'\n"
        "assert OmplFMTPlanner().planner_id == 'ompl_fmt'\n"
        "assert OmplBITStarPlanner().planner_id == 'ompl_bit_star'\n"
        "assert binding.OmplBindingRejectedError is not None\n"
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


def test_capability_flags_match_declared_ids() -> None:
    rrt = OmplRRTStarPlanner()
    fmt = OmplFMTPlanner()
    bit = OmplBITStarPlanner()
    assert rrt.planner_id == "ompl_rrt_star"
    assert fmt.planner_id == "ompl_fmt"
    assert bit.planner_id == "ompl_bit_star"
    assert rrt.capabilities.optimizing
    assert fmt.capabilities.optimizing
    assert bit.capabilities.optimizing
    assert rrt.capabilities.asymptotically_optimal is True
    assert fmt.capabilities.supports_incremental_solutions is False
    assert rrt.capabilities.supports_incremental_solutions is True
    assert bit.capabilities.supports_incremental_solutions is True
    assert rrt.capabilities.supports_exact_start
    assert not rrt.capabilities.supports_approximate_solution
    assert not fmt.capabilities.supports_approximate_solution


def test_missing_required_binding_method_is_typed_rejection() -> None:
    planner = _IncompleteStar()
    with pytest.raises(OmplBindingRejectedError, match="setGoalBias"):
        require_ompl_methods(
            planner, ("setRange", "setGoalBias"), planner_id="ompl_rrt_star"
        )
    record = apply_ompl_method(
        planner,
        "setRewireFactor",
        1.1,
        planner_id="ompl_rrt_star",
        required=False,
    )
    assert record["applied"] is False
    assert record["reason"] == "missing_method"


def test_projection_cell_sizes_use_per_dimension_binding() -> None:
    class _DimSetter:
        def __init__(self) -> None:
            self.calls: list[tuple[int, float]] = []

        def setCellSizes(self, dim: int, cellSize: float | None = None) -> None:
            if cellSize is None:
                raise TypeError("need dim and cellSize")
            self.calls.append((int(dim), float(cellSize)))

    evaluator = _DimSetter()
    record = apply_projection_cell_sizes(evaluator, (0.1, 0.25))
    assert record["signature"] == "dim_cellSize"
    assert evaluator.calls == [(0, 0.1), (1, 0.25)]


def test_fmt_rejects_nonpositive_sample_count() -> None:
    with pytest.raises(ValueError, match="num_samples"):
        OmplFMTPlanner(num_samples=0)


def test_bitstar_rejects_nonpositive_batch() -> None:
    with pytest.raises(ValueError, match="samples_per_batch"):
        OmplBITStarPlanner(samples_per_batch=0)


def test_checkpoint_costs_nonincreasing_helper() -> None:
    records = [
        {"best_cost": 2.0},
        {"best_cost": 1.5},
        {"best_cost": 1.5},
    ]
    assert checkpoint_costs_nonincreasing(records) is True
    records[-1]["best_cost"] = 1.6
    assert checkpoint_costs_nonincreasing(records) is False
    assert checkpoint_costs_nonincreasing([{"best_cost": 1.0}]) is None


def test_rrt_star_parameter_round_trip_on_dataclass() -> None:
    planner = OmplRRTStarPlanner(
        range_fraction=0.2,
        goal_bias=0.1,
        rewire_factor=1.2,
        k_nearest=False,
        delay_cc=False,
        checkpoints_s=(0.25, 0.5, 1.0),
    )
    assert planner.range_fraction == pytest.approx(0.2)
    assert planner.goal_bias == pytest.approx(0.1)
    assert planner.rewire_factor == pytest.approx(1.2)
    assert planner.k_nearest is False
    assert planner.checkpoints_s == (0.25, 0.5, 1.0)
    assert planner.tree_pruning is False
    assert planner.informed_sampling is False


def test_fmt_and_bitstar_parameter_round_trip_on_dataclass() -> None:
    fmt = OmplFMTPlanner(
        num_samples=250,
        nearest_k=False,
        radius_multiplier=1.3,
        heuristics=True,
        extended_fmt=False,
    )
    assert fmt.num_samples == 250
    assert fmt.nearest_k is False
    assert fmt.heuristics is True
    bit = OmplBITStarPlanner(
        samples_per_batch=40,
        rewire_factor=1.15,
        pruning=False,
        strict_queue_ordering=True,
        checkpoints_s=(0.2, 0.4),
    )
    assert bit.samples_per_batch == 40
    assert bit.pruning is False
    assert bit.strict_queue_ordering is True


@pytest.mark.ompl
@pytest.mark.skipif(
    not is_ompl_available(), reason="OMPL Python bindings not installed"
)
@pytest.mark.parametrize(
    "factory",
    [
        lambda gen: OmplRRTStarPlanner(
            seed=SMOKE_SEED, goal_generator=gen, solve_time_s=5.0
        ),
        lambda gen: OmplFMTPlanner(
            seed=SMOKE_SEED, goal_generator=gen, solve_time_s=5.0, num_samples=400
        ),
        lambda gen: OmplBITStarPlanner(
            seed=SMOKE_SEED, goal_generator=gen, solve_time_s=5.0
        ),
    ],
    ids=["ompl_rrt_star", "ompl_fmt", "ompl_bit_star"],
)
def test_optimizing_adapters_smoke_exact_start_and_cost(factory: Any) -> None:
    arm, _task, problem = _planning_feasible_problem()
    fk = arm.robot.planar_fk
    assert fk is not None
    planner = factory(CartesianDiskGoalGenerator(planar_fk=fk))
    result = planner.solve(problem)
    assert result.status in (
        PlanningStatus.SUCCESS,
        PlanningStatus.UNSOLVED,
        PlanningStatus.INVALID,
    )
    extras = dict(result.provenance.extras)
    assert extras["nn_distance"] == "euclidean_u"
    assert extras["planner_geometry"]["planner_role"] == "primary_optimizing"
    assert extras["planner_geometry"]["state_coordinates"] == "u"
    assert extras["ompl_planner"] in {"RRTstar", "FMT", "BITstar"}
    if result.status is PlanningStatus.SUCCESS:
        assert result.trajectory is not None
        first = result.trajectory.states[0]
        np.testing.assert_allclose(first.u, problem.start.u, atol=1e-12)
        assert problem.goal.satisfied(result.selected_goal_state)
        expected = ActuatorTravelObjective().trajectory_cost(result.trajectory.states)
        assert result.objective_cost == pytest.approx(expected)
        assert result.selected_goal_candidate is not None
