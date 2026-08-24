"""OMPL geometric RRT* planner adapter (Sprint V4.2C / V4-233)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from inequality_mechanisms.adapters.ompl._availability import require_ompl
from inequality_mechanisms.adapters.ompl.binding import (
    apply_ompl_method,
    require_ompl_class,
    require_ompl_methods,
    validate_checkpoints,
)
from inequality_mechanisms.adapters.ompl.planner_base import solve_with_ompl_planner
from inequality_mechanisms.adapters.ompl.planner_geometry import (
    optimizing_ompl_geometry,
)
from inequality_mechanisms.core.goals import GoalStateGenerator
from inequality_mechanisms.core.planner import PlannerCapabilities, PlannerLifecycle
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningResult
from inequality_mechanisms.planners.sampling_space import actuator_bounds

_REQUIRED_METHODS = ("setRange", "setGoalBias")


def _range_from_fraction(problem: PlanningProblem, range_fraction: float) -> float:
    lo, hi = actuator_bounds(problem.robot)
    span = np.asarray(hi, dtype=float) - np.asarray(lo, dtype=float)
    diagonal = float(np.linalg.norm(span))
    if diagonal <= 0.0:
        raise ValueError("certified actuator box has zero diagonal")
    return float(range_fraction) * diagonal


@dataclass(frozen=True, slots=True)
class OmplRRTStarPlanner:
    """Thin Version 3 adapter around OMPL geometric ``RRTstar``.

    Primary condition is plain RRT*: tree pruning and informed sampling stay
    off unless a separately labeled diagnostic sets them. Range is declared as
    a fraction of the certified U-box diagonal and resolved at solve time.
    """

    seed: int = 0
    max_goal_candidates: int = 8
    goal_generator: GoalStateGenerator | None = None
    solve_time_s: float = 2.0
    range_fraction: float = 0.1
    range_u: float | None = None
    goal_bias: float = 0.05
    rewire_factor: float = 1.1
    k_nearest: bool = True
    delay_cc: bool = True
    tree_pruning: bool = False
    informed_sampling: bool = False
    checkpoints_s: tuple[float, ...] | None = None
    repetition_index: int = 0
    code_revision: str | None = None
    lifecycle: PlannerLifecycle = PlannerLifecycle.SINGLE_QUERY
    trace_sink: Any | None = None

    @property
    def planner_id(self) -> str:
        """Stable planner registry name."""
        return "ompl_rrt_star"

    @property
    def capabilities(self) -> PlannerCapabilities:
        """Declare stochastic optimizing RRT* capabilities."""
        return PlannerCapabilities(
            deterministic=False,
            reproducible_with_seed=False,
            multi_query=False,
            optimizing=True,
            probabilistically_complete=None,
            asymptotically_optimal=True,
            requires_metric_space=True,
            supports_optimization_objective=True,
            supports_goal_region=True,
            supports_goal_sampling=True,
            supports_multi_start=False,
            supports_path_constraints=False,
            supports_approximate_solution=False,
            supports_incremental_solutions=True,
            reports_graph_exploration=False,
            supports_exact_start=True,
        )

    def solve(self, problem: PlanningProblem) -> PlanningResult:
        """Solve via OMPL RRT* and return a Version 3 ``PlanningResult``."""
        _ob, og = require_ompl()
        cls = require_ompl_class(og, "RRTstar", planner_id=self.planner_id)
        range_u = (
            float(self.range_u)
            if self.range_u is not None
            else _range_from_fraction(problem, self.range_fraction)
        )
        checkpoints = (
            validate_checkpoints(self.checkpoints_s)
            if self.checkpoints_s is not None
            else None
        )
        method_log: list[dict[str, Any]] = []

        def _make(si: Any) -> Any:
            planner = cls(si)
            require_ompl_methods(planner, _REQUIRED_METHODS, planner_id=self.planner_id)
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
                    "setRewireFactor",
                    float(self.rewire_factor),
                    planner_id=self.planner_id,
                    required=False,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setKNearest",
                    bool(self.k_nearest),
                    planner_id=self.planner_id,
                    required=False,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setDelayCC",
                    bool(self.delay_cc),
                    planner_id=self.planner_id,
                    required=False,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setTreePruning",
                    bool(self.tree_pruning),
                    planner_id=self.planner_id,
                    required=self.tree_pruning,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setInformedSampling",
                    bool(self.informed_sampling),
                    planner_id=self.planner_id,
                    required=self.informed_sampling,
                )
            )
            return planner

        extras: dict[str, Any] = {
            "ompl_planner": "RRTstar",
            "range_fraction": float(self.range_fraction),
            "range_u": range_u,
            "goal_bias": float(self.goal_bias),
            "rewire_factor": float(self.rewire_factor),
            "k_nearest": bool(self.k_nearest),
            "delay_cc": bool(self.delay_cc),
            "tree_pruning": bool(self.tree_pruning),
            "informed_sampling": bool(self.informed_sampling),
            "checkpoints_s": list(checkpoints) if checkpoints is not None else None,
            "binding_methods": method_log,
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
            geometry=optimizing_ompl_geometry(),
            checkpoints=checkpoints,
        )
