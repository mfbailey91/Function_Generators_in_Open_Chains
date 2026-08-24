"""OMPL-free physical projection maps for KPIECE (V4-234).

U remains the planner state. Q and X are mounted/FK views of reconstructed
``PhysicalState``. Native follower angles are never used.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.planners.sampling_space import actuator_bounds

ProjectionStrategy = Literal[
    "normalized_u",
    "normalized_mounted_q",
    "normalized_cartesian_x",
]

PROJECTION_STRATEGIES: frozenset[str] = frozenset(
    {
        "normalized_u",
        "normalized_mounted_q",
        "normalized_cartesian_x",
    }
)

FORMULAS: dict[str, str] = {
    "normalized_u": "pi_U = (u - u_min) / (u_max - u_min)",
    "normalized_mounted_q": "pi_Q = (q - q_min) / (q_max - q_min)",
    "normalized_cartesian_x": "pi_X = (x - x_min) / (x_max - x_min)",
}

DEFAULT_CELLS_PER_AXIS = 12
_DEGENERATE_ATOL = 1e-12
_X_GRID = 21


class ProjectionRejectedError(ValueError):
    """Projection bounds or evaluation failed closed."""

    def __init__(
        self,
        message: str,
        *,
        task_id: str = "",
        mechanism_id: str = "",
        projection_id: str = "",
    ) -> None:
        super().__init__(message)
        self.task_id = task_id
        self.mechanism_id = mechanism_id
        self.projection_id = projection_id


@dataclass(frozen=True, slots=True)
class ProjectionSpec:
    """Frozen affine projection onto the unit box."""

    projection_id: str
    strategy: str
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    cell_sizes: tuple[float, ...]
    formula: str
    task_id: str = ""
    mechanism_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "lower", tuple(float(v) for v in self.lower))
        object.__setattr__(self, "upper", tuple(float(v) for v in self.upper))
        object.__setattr__(self, "cell_sizes", tuple(float(v) for v in self.cell_sizes))
        if self.strategy not in PROJECTION_STRATEGIES:
            raise ProjectionRejectedError(
                f"unknown projection strategy {self.strategy!r}",
                task_id=self.task_id,
                mechanism_id=self.mechanism_id,
                projection_id=self.projection_id,
            )
        if len(self.lower) != len(self.upper) or len(self.lower) == 0:
            raise ProjectionRejectedError(
                "projection lower and upper must be nonempty and same length",
                task_id=self.task_id,
                mechanism_id=self.mechanism_id,
                projection_id=self.projection_id,
            )
        if len(self.cell_sizes) != len(self.lower):
            raise ProjectionRejectedError(
                "cell_sizes length must match projection dimension",
                task_id=self.task_id,
                mechanism_id=self.mechanism_id,
                projection_id=self.projection_id,
            )
        _assert_nondegenerate(
            np.asarray(self.lower, dtype=np.float64),
            np.asarray(self.upper, dtype=np.float64),
            task_id=self.task_id,
            mechanism_id=self.mechanism_id,
            projection_id=self.projection_id,
        )
        if any(not np.isfinite(c) or c <= 0.0 for c in self.cell_sizes):
            raise ProjectionRejectedError(
                f"cell_sizes must be positive and finite; got {self.cell_sizes!r}",
                task_id=self.task_id,
                mechanism_id=self.mechanism_id,
                projection_id=self.projection_id,
            )

    @property
    def dimension(self) -> int:
        """Projection dimension."""
        return len(self.lower)


def unit_cell_sizes(
    dim: int, cells_per_axis: int = DEFAULT_CELLS_PER_AXIS
) -> tuple[float, ...]:
    """Return explicit unit-box cell sizes for ``cells_per_axis`` bins."""
    n = int(cells_per_axis)
    if n < 1:
        raise ValueError("cells_per_axis must be a positive integer")
    width = 1.0 / float(n)
    return tuple(width for _ in range(int(dim)))


def _assert_nondegenerate(
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
    *,
    task_id: str,
    mechanism_id: str,
    projection_id: str,
) -> None:
    if lower.shape != upper.shape or lower.ndim != 1:
        raise ProjectionRejectedError(
            "projection bounds must be 1-D arrays of equal shape",
            task_id=task_id,
            mechanism_id=mechanism_id,
            projection_id=projection_id,
        )
    if not np.all(np.isfinite(lower)) or not np.all(np.isfinite(upper)):
        raise ProjectionRejectedError(
            "projection bounds must be finite",
            task_id=task_id,
            mechanism_id=mechanism_id,
            projection_id=projection_id,
        )
    span = upper - lower
    if np.any(span <= _DEGENERATE_ATOL):
        raise ProjectionRejectedError(
            f"degenerate projection axis for {projection_id}: "
            f"task={task_id!r} mechanism={mechanism_id!r} span={span.tolist()}",
            task_id=task_id,
            mechanism_id=mechanism_id,
            projection_id=projection_id,
        )


def affine_unit(
    value: NDArray[np.float64],
    lower: NDArray[np.float64],
    upper: NDArray[np.float64],
    *,
    task_id: str = "",
    mechanism_id: str = "",
    projection_id: str = "",
) -> NDArray[np.float64]:
    """Map ``value`` onto ``[0, 1]^n`` with frozen affine bounds."""
    y = np.asarray(value, dtype=np.float64)
    lo = np.asarray(lower, dtype=np.float64)
    hi = np.asarray(upper, dtype=np.float64)
    _assert_nondegenerate(
        lo, hi, task_id=task_id, mechanism_id=mechanism_id, projection_id=projection_id
    )
    if y.shape != lo.shape:
        raise ProjectionRejectedError(
            f"value shape {y.shape} does not match bounds {lo.shape}",
            task_id=task_id,
            mechanism_id=mechanism_id,
            projection_id=projection_id,
        )
    if not np.all(np.isfinite(y)):
        raise ProjectionRejectedError(
            "projection value is not finite",
            task_id=task_id,
            mechanism_id=mechanism_id,
            projection_id=projection_id,
        )
    return (y - lo) / (hi - lo)


def actuator_u_bounds(
    robot: RobotModel,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return the certified actuator box."""
    return actuator_bounds(robot)


def mounted_q_bounds(
    robot: RobotModel,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return mounted output bounds from the operating-branch certificate."""
    branch = getattr(robot, "branch", None)
    cert = getattr(branch, "certificate", None) if branch is not None else None
    if cert is None:
        raise ProjectionRejectedError(
            "mounted Q bounds require an operating-branch certificate",
            projection_id="normalized_mounted_q",
        )
    lo = np.asarray(cert.output_lower, dtype=np.float64)
    hi = np.asarray(cert.output_upper, dtype=np.float64)
    _assert_nondegenerate(
        lo,
        hi,
        task_id="",
        mechanism_id="",
        projection_id="normalized_mounted_q",
    )
    return lo, hi


def cartesian_x_bounds(
    robot: RobotModel,
    q_lower: NDArray[np.float64],
    q_upper: NDArray[np.float64],
    *,
    n_grid: int = _X_GRID,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return a deterministic AABB of FK over a frozen mounted-Q grid."""
    lo_q = np.asarray(q_lower, dtype=np.float64)
    hi_q = np.asarray(q_upper, dtype=np.float64)
    _assert_nondegenerate(
        lo_q,
        hi_q,
        task_id="",
        mechanism_id="",
        projection_id="normalized_cartesian_x",
    )
    n = int(n_grid)
    if n < 2:
        raise ValueError("n_grid must be at least 2")
    axes = [np.linspace(lo_q[i], hi_q[i], n) for i in range(lo_q.shape[0])]
    mesh = np.meshgrid(*axes, indexing="ij")
    samples = np.stack([m.reshape(-1) for m in mesh], axis=1)
    xs: list[NDArray[np.float64]] = []
    dummy_u = np.zeros(lo_q.shape[0], dtype=np.float64)
    for q in samples:
        try:
            state = PhysicalState(u=dummy_u, q=np.asarray(q, dtype=np.float64))
            pos = np.asarray(robot.forward_kinematics(state).position, dtype=np.float64)
        except Exception:
            continue
        if pos.ndim != 1 or not np.all(np.isfinite(pos)):
            continue
        xs.append(pos)
    if not xs:
        raise ProjectionRejectedError(
            "cartesian X bounds grid produced no finite FK samples",
            projection_id="normalized_cartesian_x",
        )
    stacked = np.stack(xs, axis=0)
    lo_x = np.min(stacked, axis=0)
    hi_x = np.max(stacked, axis=0)
    _assert_nondegenerate(
        lo_x,
        hi_x,
        task_id="",
        mechanism_id="",
        projection_id="normalized_cartesian_x",
    )
    return lo_x, hi_x


def make_projection_spec(
    strategy: str,
    robot: RobotModel,
    *,
    q_lower: NDArray[np.float64] | None = None,
    q_upper: NDArray[np.float64] | None = None,
    cells_per_axis: int = DEFAULT_CELLS_PER_AXIS,
    task_id: str = "",
    mechanism_id: str = "",
) -> ProjectionSpec:
    """Build a frozen spec from certified U, mounted Q, or shared-Q X bounds."""
    if strategy == "normalized_u":
        lo, hi = actuator_u_bounds(robot)
    elif strategy == "normalized_mounted_q":
        lo, hi = mounted_q_bounds(robot)
    elif strategy == "normalized_cartesian_x":
        if q_lower is None or q_upper is None:
            q_lower, q_upper = mounted_q_bounds(robot)
        lo, hi = cartesian_x_bounds(robot, q_lower, q_upper)
    else:
        raise ProjectionRejectedError(
            f"unknown projection strategy {strategy!r}",
            task_id=task_id,
            mechanism_id=mechanism_id,
            projection_id=str(strategy),
        )
    cells = unit_cell_sizes(int(lo.shape[0]), cells_per_axis)
    return ProjectionSpec(
        projection_id=strategy,
        strategy=strategy,
        lower=tuple(float(v) for v in lo),
        upper=tuple(float(v) for v in hi),
        cell_sizes=cells,
        formula=FORMULAS[strategy],
        task_id=task_id,
        mechanism_id=mechanism_id,
    )


def project_physical_state(
    state: PhysicalState,
    spec: ProjectionSpec,
    robot: RobotModel | None = None,
) -> NDArray[np.float64]:
    """Project a reconstructed physical state with the frozen spec."""
    if spec.strategy == "normalized_u":
        raw = np.asarray(state.u, dtype=np.float64)
    elif spec.strategy == "normalized_mounted_q":
        raw = np.asarray(state.q, dtype=np.float64)
    elif spec.strategy == "normalized_cartesian_x":
        if robot is None:
            raise ProjectionRejectedError(
                "cartesian X projection requires the robot for FK",
                task_id=spec.task_id,
                mechanism_id=spec.mechanism_id,
                projection_id=spec.projection_id,
            )
        raw = np.asarray(robot.forward_kinematics(state).position, dtype=np.float64)
    else:
        raise ProjectionRejectedError(
            f"unknown projection strategy {spec.strategy!r}",
            task_id=spec.task_id,
            mechanism_id=spec.mechanism_id,
            projection_id=spec.projection_id,
        )
    return affine_unit(
        raw,
        np.asarray(spec.lower, dtype=np.float64),
        np.asarray(spec.upper, dtype=np.float64),
        task_id=spec.task_id,
        mechanism_id=spec.mechanism_id,
        projection_id=spec.projection_id,
    )


def spec_to_dict(spec: ProjectionSpec) -> dict[str, Any]:
    """JSON-serializable projection declaration."""
    return {
        "projection_id": spec.projection_id,
        "strategy": spec.strategy,
        "projection_bounds": {
            "lower": list(spec.lower),
            "upper": list(spec.upper),
        },
        "cell_sizes": list(spec.cell_sizes),
        "formula": spec.formula,
        "projection_normalization": "minmax_unit",
        "task_id": spec.task_id,
        "mechanism_id": spec.mechanism_id,
    }
