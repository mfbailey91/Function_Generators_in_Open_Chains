"""OMPL geometric BIT* planner adapter (Sprint V4.2C / V4-233)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

_REQUIRED_METHODS = ("setSamplesPerBatch", "setRewireFactor")


@dataclass(frozen=True, slots=True)
class OmplBITStarPlanner:
    """Thin Version 3 adapter around OMPL geometric ``BITstar``.

    Uses the existing actuator-travel / path-length objective. Batch size,
    rewire factor, k-nearest/radius mode, pruning, and strict queue ordering
    are declared in provenance. Repeated ``solve`` continuation is the
    checkpointed session path.
    """

    seed: int = 0
    max_goal_candidates: int = 8
    goal_generator: GoalStateGenerator | None = None
    solve_time_s: float = 2.0
    samples_per_batch: int = 100
    rewire_factor: float = 1.1
    use_k_nearest: bool = True
    pruning: bool = True
    strict_queue_ordering: bool = False
    checkpoints_s: tuple[float, ...] | None = None
    repetition_index: int = 0
    code_revision: str | None = None
    lifecycle: PlannerLifecycle = PlannerLifecycle.SINGLE_QUERY
    trace_sink: Any | None = None

    def __post_init__(self) -> None:
        if int(self.samples_per_batch) < 1:
            raise ValueError("samples_per_batch must be a positive integer")

    @property
    def planner_id(self) -> str:
        """Stable planner registry name."""
        return "ompl_bit_star"

    @property
    def capabilities(self) -> PlannerCapabilities:
        """Declare stochastic optimizing BIT* capabilities."""
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
        """Solve via OMPL BIT* and return a Version 3 ``PlanningResult``."""
        _ob, og = require_ompl()
        cls = require_ompl_class(og, "BITstar", planner_id=self.planner_id)
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
                    planner,
                    "setSamplesPerBatch",
                    int(self.samples_per_batch),
                    planner_id=self.planner_id,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setRewireFactor",
                    float(self.rewire_factor),
                    planner_id=self.planner_id,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setUseKNearest",
                    bool(self.use_k_nearest),
                    planner_id=self.planner_id,
                    required=False,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setPruning",
                    bool(self.pruning),
                    planner_id=self.planner_id,
                    required=False,
                )
            )
            method_log.append(
                apply_ompl_method(
                    planner,
                    "setStrictQueueOrdering",
                    bool(self.strict_queue_ordering),
                    planner_id=self.planner_id,
                    required=self.strict_queue_ordering,
                )
            )
            return planner

        extras: dict[str, Any] = {
            "ompl_planner": "BITstar",
            "samples_per_batch": int(self.samples_per_batch),
            "rewire_factor": float(self.rewire_factor),
            "use_k_nearest": bool(self.use_k_nearest),
            "pruning": bool(self.pruning),
            "strict_queue_ordering": bool(self.strict_queue_ordering),
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
