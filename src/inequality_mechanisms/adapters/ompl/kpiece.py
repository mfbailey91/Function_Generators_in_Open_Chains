"""OMPL geometric KPIECE1 adapter with U/Q/X projections (Sprint V4.2C / V4-234)."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from inequality_mechanisms.adapters.ompl._availability import require_ompl
from inequality_mechanisms.adapters.ompl.binding import (
    apply_ompl_method,
    require_ompl_class,
    require_ompl_methods,
)
from inequality_mechanisms.adapters.ompl.planner_base import solve_with_ompl_planner
from inequality_mechanisms.adapters.ompl.planner_geometry import kpiece_ompl_geometry
from inequality_mechanisms.adapters.ompl.projections import (
    ProjectionSpec,
    make_projection_spec,
    project_physical_state,
    spec_to_dict,
)
from inequality_mechanisms.adapters.ompl.state_space import physical_state_from_ompl
from inequality_mechanisms.core.goals import GoalStateGenerator
from inequality_mechanisms.core.planner import PlannerCapabilities, PlannerLifecycle
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningResult
from inequality_mechanisms.planners.sampling_space import actuator_bounds

_REQUIRED_METHODS = ("setRange", "setGoalBias", "setProjectionEvaluator")
_PLANNER_IDS: dict[str, str] = {
    "normalized_u": "ompl_kpiece_u",
    "normalized_mounted_q": "ompl_kpiece_q",
    "normalized_cartesian_x": "ompl_kpiece_x",
}
_STRIP_KEYS = (
    "exploration_projection",
    "projection_normalization",
    "projection_bounds",
    "projection_id",
    "strategy",
    "formula",
    "planner_id",
)


def _range_from_fraction(problem: PlanningProblem, range_fraction: float) -> float:
    lo, hi = actuator_bounds(problem.robot)
    span = np.asarray(hi, dtype=float) - np.asarray(lo, dtype=float)
    diagonal = float(np.linalg.norm(span))
    if diagonal <= 0.0:
        raise ValueError("certified actuator box has zero diagonal")
    return float(range_fraction) * diagonal


def _mechanism_id(problem: PlanningProblem) -> str:
    assembly = dict(problem.start.assembly_state)
    return str(assembly.get("mechanism_name", "") or "")


def _make_projection_evaluator(
    ob: Any,
    space: Any,
    problem: PlanningProblem,
    spec: ProjectionSpec,
) -> Any:
    robot = problem.robot
    assembly = dict(problem.start.assembly_state)

    class _PhysicalProjection(ob.ProjectionEvaluator):
        def __init__(self) -> None:
            super().__init__(space)
            sizes = [float(c) for c in spec.cell_sizes]
            if hasattr(self, "setCellSizes"):
                self.setCellSizes(sizes)
            elif hasattr(self, "setCellSize"):
                self.setCellSize(float(sizes[0]))

        def getDimension(self) -> int:  # noqa: N802
            return int(spec.dimension)

        def defaultCellSizes(self) -> None:  # noqa: N802
            sizes = [float(c) for c in spec.cell_sizes]
            if hasattr(self, "setCellSizes"):
                self.setCellSizes(sizes)

        def project(self, state: Any, projection: Any) -> None:
            physical = physical_state_from_ompl(
                robot, space, state, assembly_state=assembly
            )
            coords = project_physical_state(physical, spec, robot)
            for i, value in enumerate(coords):
                projection[i] = float(value)

    return _PhysicalProjection()


def resolved_kpiece_config(
    planner: OmplKPIECEPlanner,
    spec: ProjectionSpec,
) -> dict[str, Any]:
    """Fully resolved KPIECE config including projection declaration."""
    geometry = kpiece_ompl_geometry(planner.projection, spec.cell_sizes)
    payload = spec_to_dict(spec)
    payload.update(
        {
            "planner_id": planner.planner_id,
            "exploration_projection": planner.projection,
            "range_fraction": float(planner.range_fraction),
            "goal_bias": float(planner.goal_bias),
            "border_fraction": float(planner.border_fraction),
            "min_valid_path_fraction": float(planner.min_valid_path_fraction),
            "cells_per_axis": int(planner.cells_per_axis),
            "solve_time_s": float(planner.solve_time_s),
            "seed": int(planner.seed),
            "max_goal_candidates": int(planner.max_goal_candidates),
            "planner_geometry": geometry.to_dict(),
        }
    )
    return payload


def nonprojection_config_json(config: dict[str, Any]) -> str:
    """Canonical JSON of a resolved config with projection fields removed."""
    stripped = copy.deepcopy(config)
    for key in _STRIP_KEYS:
        stripped.pop(key, None)
    geom = stripped.get("planner_geometry")
    if isinstance(geom, dict):
        geom.pop("exploration_projection", None)
    return json.dumps(stripped, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class OmplKPIECEPlanner:
    """Thin Version 3 adapter around OMPL geometric ``KPIECE1``.

    One wrapper, three public IDs. Nonprojection knobs are shared; only the
    exploration projection changes. KPIECE is a diagnostic family, not an
    optimizer, and uses a one-shot solve.
    """

    projection: Literal[
        "normalized_u",
        "normalized_mounted_q",
        "normalized_cartesian_x",
    ] = "normalized_u"
    seed: int = 0
    max_goal_candidates: int = 8
    goal_generator: GoalStateGenerator | None = None
    solve_time_s: float = 2.0
    range_fraction: float = 0.1
    range_u: float | None = None
    goal_bias: float = 0.05
    border_fraction: float = 0.9
    min_valid_path_fraction: float = 0.5
    cells_per_axis: int = 12
    repetition_index: int = 0
    code_revision: str | None = None
    lifecycle: PlannerLifecycle = PlannerLifecycle.SINGLE_QUERY
    trace_sink: Any | None = None

    def __post_init__(self) -> None:
        if self.projection not in _PLANNER_IDS:
            raise ValueError(f"unsupported KPIECE projection {self.projection!r}")
        if int(self.cells_per_axis) < 1:
            raise ValueError("cells_per_axis must be a positive integer")

    @property
    def planner_id(self) -> str:
        """Stable planner registry name for this projection arm."""
        return _PLANNER_IDS[self.projection]

    @property
    def capabilities(self) -> PlannerCapabilities:
        """Declare stochastic projection-diagnostic KPIECE capabilities."""
        return PlannerCapabilities(
            deterministic=False,
            reproducible_with_seed=False,
            multi_query=False,
            optimizing=False,
            probabilistically_complete=None,
            asymptotically_optimal=False,
            requires_metric_space=True,
            supports_optimization_objective=True,
            supports_goal_region=True,
            supports_goal_sampling=True,
            supports_multi_start=False,
            supports_path_constraints=False,
            supports_approximate_solution=False,
            supports_incremental_solutions=False,
            reports_graph_exploration=False,
            supports_exact_start=True,
        )

    def solve(self, problem: PlanningProblem) -> PlanningResult:
        """Solve via OMPL KPIECE1 and return a Version 3 ``PlanningResult``."""
        ob, og = require_ompl()
        cls = require_ompl_class(og, "KPIECE1", planner_id=self.planner_id)
        range_u = (
            float(self.range_u)
            if self.range_u is not None
            else _range_from_fraction(problem, self.range_fraction)
        )
        spec = make_projection_spec(
            self.projection,
            problem.robot,
            cells_per_axis=int(self.cells_per_axis),
            mechanism_id=_mechanism_id(problem),
        )
        geometry = kpiece_ompl_geometry(self.projection, spec.cell_sizes)
        method_log: list[dict[str, Any]] = []
        held: list[Any] = []

        def _make(si: Any) -> Any:
            planner = cls(si)
            require_ompl_methods(planner, _REQUIRED_METHODS, planner_id=self.planner_id)
            space = (
                si.getStateSpace() if hasattr(si, "getStateSpace") else si.getSpace()
            )
            evaluator = _make_projection_evaluator(ob, space, problem, spec)
            held.append(evaluator)
            method_log.append(
                apply_ompl_method(
                    planner, "setRange", float(range_u), planner_id=self.planner_id
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setGoalBias",
                    float(self.goal_bias),
                    planner_id=self.planner_id,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setProjectionEvaluator",
                    evaluator,
                    planner_id=self.planner_id,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setBorderFraction",
                    float(self.border_fraction),
                    planner_id=self.planner_id,
                    required=False,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setMinValidPathFraction",
                    float(self.min_valid_path_fraction),
                    planner_id=self.planner_id,
                    required=False,
                )
            )
            return planner

        extras: dict[str, Any] = {
            "ompl_planner": "KPIECE1",
            "family_metrics": {
                "range_fraction": float(self.range_fraction),
                "range_u": range_u,
                "goal_bias": float(self.goal_bias),
                "border_fraction": float(self.border_fraction),
                "min_valid_path_fraction": float(self.min_valid_path_fraction),
                "cells_per_axis": int(self.cells_per_axis),
                "projection": spec_to_dict(spec),
                "binding_methods": method_log,
                "kpiece_cell_occupancy": None,
                "unavailable_reason": "kpiece_cell_stats_not_exposed_by_binding",
            },
        }
        return solve_with_ompl_planner(
            problem,
            planner_id=self.planner_id,
            make_planner=_make,
            seed=self.seed,
            repetition_index=self.repetition_index,
            code_revision=self.code_revision,
            goal_generator=self.goal_generator,
            max_goal_candidates=self.max_goal_candidates,
            solve_time_s=self.solve_time_s,
            extras_base=extras,
            trace_sink=self.trace_sink,
            geometry=geometry,
            checkpoints=None,
        )
