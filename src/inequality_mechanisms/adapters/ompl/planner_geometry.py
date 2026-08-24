"""ADR-031 planner-geometry record for OMPL adapters (V4-232).

Importing this module must not import ``ompl``. Allowed field values are
strict: unknown labels fail closed in ``__post_init__``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

PLANNER_ROLES: Final[frozenset[str]] = frozenset(
    {"architecture_control", "primary_optimizing"}
)
STATE_COORDINATES: Final[frozenset[str]] = frozenset({"u"})
SAMPLING_MEASURES: Final[frozenset[str]] = frozenset({"uniform_raw_u"})
NEAREST_NEIGHBOR_DISTANCES: Final[frozenset[str]] = frozenset({"euclidean_u"})
OPTIMIZATION_OBJECTIVES: Final[frozenset[str]] = frozenset({"actuator_travel"})
COST_TO_GO_HEURISTICS: Final[frozenset[str]] = frozenset({"none", "euclidean_u"})
EXPLORATION_PROJECTIONS: Final[frozenset[str]] = frozenset({"none"})
PROJECTION_NORMALIZATIONS: Final[frozenset[str]] = frozenset({"none"})
GOAL_REPRESENTATIONS: Final[frozenset[str]] = frozenset({"finite_goal_states"})
LOCAL_MOTION_MODELS: Final[frozenset[str]] = frozenset({"input_linear"})

_FIELD_ALLOWED: Final[Mapping[str, frozenset[str]]] = {
    "planner_role": PLANNER_ROLES,
    "state_coordinates": STATE_COORDINATES,
    "sampling_measure": SAMPLING_MEASURES,
    "nearest_neighbor_distance": NEAREST_NEIGHBOR_DISTANCES,
    "optimization_objective": OPTIMIZATION_OBJECTIVES,
    "cost_to_go_heuristic": COST_TO_GO_HEURISTICS,
    "exploration_projection": EXPLORATION_PROJECTIONS,
    "projection_normalization": PROJECTION_NORMALIZATIONS,
    "goal_representation": GOAL_REPRESENTATIONS,
    "local_motion_model": LOCAL_MOTION_MODELS,
}


@dataclass(frozen=True, slots=True)
class PlannerGeometryRecord:
    """Common OMPL planner-geometry declaration (ADR-031).

    Parameters
    ----------
    planner_role
        Role of this planner in the V4.2C portfolio.
    state_coordinates
        Authoritative OMPL state coordinates.
    sampling_measure
        Sampling measure on those coordinates.
    nearest_neighbor_distance
        Distance used for nearest-neighbor queries.
    optimization_objective
        Declared optimization objective.
    cost_to_go_heuristic
        Cost-to-go heuristic label, or ``none``.
    exploration_projection
        Low-dimensional exploration projection, or ``none``.
    projection_normalization
        Projection normalization policy, or ``none``.
    projection_cell_sizes
        Projection cell sizes; empty when no projection is used.
    goal_representation
        How the physical goal is presented to OMPL.
    local_motion_model
        Local connector used for motion validation.
    """

    planner_role: str
    state_coordinates: str
    sampling_measure: str
    nearest_neighbor_distance: str
    optimization_objective: str
    cost_to_go_heuristic: str
    exploration_projection: str
    projection_normalization: str
    projection_cell_sizes: tuple[float, ...]
    goal_representation: str
    local_motion_model: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "projection_cell_sizes", tuple(self.projection_cell_sizes)
        )
        for name, allowed in _FIELD_ALLOWED.items():
            value = getattr(self, name)
            if value not in allowed:
                raise ValueError(
                    f"PlannerGeometryRecord.{name}={value!r} is not allowed; "
                    f"expected one of {sorted(allowed)}"
                )
        if self.projection_cell_sizes != ():
            raise ValueError(
                "PlannerGeometryRecord.projection_cell_sizes must be empty "
                f"for the primary OMPL geometry; got {self.projection_cell_sizes!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable copy of the common geometry fields."""
        return {
            "planner_role": self.planner_role,
            "state_coordinates": self.state_coordinates,
            "sampling_measure": self.sampling_measure,
            "nearest_neighbor_distance": self.nearest_neighbor_distance,
            "optimization_objective": self.optimization_objective,
            "cost_to_go_heuristic": self.cost_to_go_heuristic,
            "exploration_projection": self.exploration_projection,
            "projection_normalization": self.projection_normalization,
            "projection_cell_sizes": list(self.projection_cell_sizes),
            "goal_representation": self.goal_representation,
            "local_motion_model": self.local_motion_model,
        }


def primary_ompl_geometry() -> PlannerGeometryRecord:
    """Return the canonical geometry for existing PRM / RRTConnect rows."""
    return PlannerGeometryRecord(
        planner_role="architecture_control",
        state_coordinates="u",
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


def optimizing_ompl_geometry(
    *,
    cost_to_go_heuristic: str = "none",
) -> PlannerGeometryRecord:
    """Return the primary V4.2C geometry for RRT* / BIT* / FMT rows.

    Same physical contract as :func:`primary_ompl_geometry`, with
    ``planner_role="primary_optimizing"`` so architecture-control rows stay
    distinct. FMT heuristics-on rows pass ``cost_to_go_heuristic="euclidean_u"``.
    """
    return PlannerGeometryRecord(
        planner_role="primary_optimizing",
        state_coordinates="u",
        sampling_measure="uniform_raw_u",
        nearest_neighbor_distance="euclidean_u",
        optimization_objective="actuator_travel",
        cost_to_go_heuristic=cost_to_go_heuristic,
        exploration_projection="none",
        projection_normalization="none",
        projection_cell_sizes=(),
        goal_representation="finite_goal_states",
        local_motion_model="input_linear",
    )
