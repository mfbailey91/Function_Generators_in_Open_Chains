"""Version 3 planner protocols and capability metadata (ADR-025)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from inequality_mechanisms.core.problem import PlanningProblem
    from inequality_mechanisms.core.results import PlanningResult


class PlannerLifecycle(StrEnum):
    """How a planner manages preprocessing relative to queries."""

    SINGLE_QUERY = "single_query"
    BUILD_PER_TASK = "build_per_task"
    REUSE_WITHIN_RUN = "reuse_within_run"
    LOAD_FROZEN_STRUCTURE = "load_frozen_structure"


@dataclass(frozen=True, slots=True)
class PlannerCapabilities:
    """Declared capabilities of one planner backend."""

    deterministic: bool
    reproducible_with_seed: bool
    multi_query: bool
    optimizing: bool
    probabilistically_complete: bool | None
    asymptotically_optimal: bool | None
    requires_metric_space: bool
    supports_optimization_objective: bool
    supports_goal_region: bool
    supports_goal_sampling: bool
    supports_multi_start: bool
    supports_path_constraints: bool
    supports_approximate_solution: bool
    supports_incremental_solutions: bool
    reports_graph_exploration: bool
    supports_exact_start: bool


@runtime_checkable
class Planner(Protocol):
    """Planner entry point consuming ``PlanningProblem``."""

    @property
    def planner_id(self) -> str:
        """Stable planner registry name."""

    @property
    def capabilities(self) -> PlannerCapabilities:
        """Declared capability metadata."""

    @property
    def lifecycle(self) -> PlannerLifecycle:
        """Preprocessing lifecycle for this planner instance."""

    def solve(self, problem: PlanningProblem) -> PlanningResult:
        """Solve ``problem`` and return a ``PlanningResult``."""
