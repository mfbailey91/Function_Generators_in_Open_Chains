"""OMPL geometric FMT planner adapter (Sprint V4.2C / V4-233)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inequality_mechanisms.adapters.ompl._availability import require_ompl
from inequality_mechanisms.adapters.ompl.binding import (
    apply_ompl_method,
    require_ompl_class,
    require_ompl_methods,
)
from inequality_mechanisms.adapters.ompl.planner_base import solve_with_ompl_planner
from inequality_mechanisms.adapters.ompl.planner_geometry import (
    optimizing_ompl_geometry,
)
from inequality_mechanisms.core.goals import GoalStateGenerator
from inequality_mechanisms.core.planner import PlannerCapabilities, PlannerLifecycle
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningResult

_REQUIRED_METHODS = (
    "setNumSamples",
    "setNearestK",
    "setRadiusMultiplier",
    "setHeuristics",
    "setExtendedFMT",
)


@dataclass(frozen=True, slots=True)
class OmplFMTPlanner:
    """Thin Version 3 adapter around OMPL geometric ``FMT``.

    Each solve is an independent fixed-sample run. Checkpoints are rejected:
    raising the sample count is a new query, not a continuation of the same
    search.
    """

    seed: int = 0
    max_goal_candidates: int = 8
    goal_generator: GoalStateGenerator | None = None
    solve_time_s: float = 2.0
    num_samples: int = 1000
    nearest_k: bool = True
    radius_multiplier: float = 1.1
    heuristics: bool = False
    extended_fmt: bool = True
    cache_cc: bool = True
    repetition_index: int = 0
    code_revision: str | None = None
    lifecycle: PlannerLifecycle = PlannerLifecycle.SINGLE_QUERY
    trace_sink: Any | None = None

    def __post_init__(self) -> None:
        if int(self.num_samples) < 1:
            raise ValueError("num_samples must be a positive integer")

    @property
    def planner_id(self) -> str:
        """Stable planner registry name."""
        return "ompl_fmt"

    @property
    def capabilities(self) -> PlannerCapabilities:
        """Declare stochastic fixed-sample FMT capabilities."""
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
            supports_incremental_solutions=False,
            reports_graph_exploration=False,
            supports_exact_start=True,
        )

    def solve(self, problem: PlanningProblem) -> PlanningResult:
        """Solve via OMPL FMT and return a Version 3 ``PlanningResult``."""
        _ob, og = require_ompl()
        cls = require_ompl_class(og, "FMT", planner_id=self.planner_id)
        method_log: list[dict[str, Any]] = []
        heuristic = "euclidean_u" if self.heuristics else "none"

        def _make(si: Any) -> Any:
            planner = cls(si)
            require_ompl_methods(planner, _REQUIRED_METHODS, planner_id=self.planner_id)
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setNumSamples",
                    int(self.num_samples),
                    planner_id=self.planner_id,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setNearestK",
                    bool(self.nearest_k),
                    planner_id=self.planner_id,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setRadiusMultiplier",
                    float(self.radius_multiplier),
                    planner_id=self.planner_id,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setHeuristics",
                    bool(self.heuristics),
                    planner_id=self.planner_id,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setExtendedFMT",
                    bool(self.extended_fmt),
                    planner_id=self.planner_id,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setCacheCC",
                    bool(self.cache_cc),
                    planner_id=self.planner_id,
                    required=False,
                )
            )
            return planner

        extras: dict[str, Any] = {
            "ompl_planner": "FMT",
            "num_samples": int(self.num_samples),
            "effective_sample_count": int(self.num_samples),
            "nearest_k": bool(self.nearest_k),
            "radius_multiplier": float(self.radius_multiplier),
            "heuristics": bool(self.heuristics),
            "extended_fmt": bool(self.extended_fmt),
            "cache_cc": bool(self.cache_cc),
            "continuation": "independent_sample_count",
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
            geometry=optimizing_ompl_geometry(cost_to_go_heuristic=heuristic),
            checkpoints=None,
        )
