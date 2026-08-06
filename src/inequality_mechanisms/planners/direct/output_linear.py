"""Direct output-linear planner (Sprint V3.2)."""

from __future__ import annotations

from dataclasses import dataclass

from inequality_mechanisms.core.goals import GoalStateGenerator
from inequality_mechanisms.core.local_motion import OutputLinearMotion
from inequality_mechanisms.core.planner import PlannerCapabilities, PlannerLifecycle
from inequality_mechanisms.core.problem import PlanningProblem
from inequality_mechanisms.core.results import PlanningResult
from inequality_mechanisms.planners.direct._common import solve_with_direct_connector

OUTPUT_LINEAR_POLICY = "output_linear_v1"


@dataclass(frozen=True, slots=True)
class OutputLinearDirectPlanner:
    """Classify then connect with output-linear lift (ADR-024/026)."""

    goal_generator: GoalStateGenerator
    n_samples: int = 64
    max_candidates: int = 8
    code_revision: str | None = None
    lifecycle: PlannerLifecycle = PlannerLifecycle.SINGLE_QUERY

    @property
    def planner_id(self) -> str:
        """Stable planner registry name."""
        return "direct_output_linear"

    @property
    def capabilities(self) -> PlannerCapabilities:
        """Declare deterministic exact-start goal-region capabilities."""
        return PlannerCapabilities(
            deterministic=True,
            reproducible_with_seed=True,
            multi_query=False,
            optimizing=True,
            probabilistically_complete=None,
            asymptotically_optimal=None,
            requires_metric_space=False,
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
        """Solve via ADR-026 classification and output-linear connection."""
        connector = OutputLinearMotion(
            robot=problem.robot,
            model_id=OUTPUT_LINEAR_POLICY,
            n_samples=self.n_samples,
        )
        return solve_with_direct_connector(
            problem,
            connector=connector,
            connector_policy=OUTPUT_LINEAR_POLICY,
            goal_generator=self.goal_generator,
            planner_id=self.planner_id,
            max_candidates=self.max_candidates,
            code_revision=self.code_revision,
        )
