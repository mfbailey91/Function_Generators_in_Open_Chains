"""OMPL geometric RRTConnect planner adapter (Sprint V3.5 / V3-504)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inequality_mechanisms.adapters.ompl._availability import require_ompl
from inequality_mechanisms.adapters.ompl.planner_base import solve_with_ompl_planner
from inequality_mechanisms.core.goals import GoalStateGenerator
from inequality_mechanisms.core.planner import PlannerCapabilities, PlannerLifecycle
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningResult


@dataclass(frozen=True, slots=True)
class OmplRRTConnectPlanner:
    """Thin Version 3 adapter around OMPL geometric ``RRTConnect``.

    Lifecycle is ``SINGLE_QUERY``. Nearest-neighbor distance inside OMPL is
    Euclidean in ``U`` (``nn_distance: euclidean_u``). Reported path cost uses
    actuator-travel along the returned polyline.
    """

    seed: int = 0
    max_goal_candidates: int = 8
    goal_generator: GoalStateGenerator | None = None
    solve_time_s: float = 2.0
    range_u: float | None = 0.35
    repetition_index: int = 0
    code_revision: str | None = None
    lifecycle: PlannerLifecycle = PlannerLifecycle.SINGLE_QUERY

    @property
    def planner_id(self) -> str:
        """Stable planner registry name."""
        return "ompl_rrt_connect"

    @property
    def capabilities(self) -> PlannerCapabilities:
        """Declare stochastic, seed-reproducible OMPL RRTConnect capabilities."""
        return PlannerCapabilities(
            deterministic=False,
            reproducible_with_seed=True,
            multi_query=False,
            optimizing=False,
            probabilistically_complete=None,
            asymptotically_optimal=None,
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
        """Solve via OMPL RRTConnect and return a Version 3 ``PlanningResult``."""
        _ob, og = require_ompl()
        range_u = self.range_u

        def _make(si: Any) -> Any:
            planner = og.RRTConnect(si)
            if range_u is not None and hasattr(planner, "setRange"):
                planner.setRange(float(range_u))
            return planner

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
            extras_base={"ompl_planner": "RRTConnect", "range_u": range_u},
        )
