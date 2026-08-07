"""OMPL RealVectorStateSpace over certified actuator coordinates (V3-502)."""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.adapters.ompl._availability import require_ompl
from inequality_mechanisms.core.robot import RobotModel
from inequality_mechanisms.core.state import PhysicalState
from inequality_mechanisms.planners.sampling_space import actuator_bounds

ROUND_TRIP_TOL = 1e-9


def build_actuator_state_space(robot: RobotModel) -> Any:
    """Return an OMPL ``RealVectorStateSpace`` bounded by the certified U box."""
    ob, _og = require_ompl()
    lo, hi = actuator_bounds(robot)
    dim = int(lo.shape[0])
    space = ob.RealVectorStateSpace(dim)
    bounds = ob.RealVectorBounds(dim)
    for i in range(dim):
        bounds.setLow(i, float(lo[i]))
        bounds.setHigh(i, float(hi[i]))
    space.setBounds(bounds)
    return space


def u_from_ompl_state(space: Any, state: Any) -> NDArray[np.float64]:
    """Extract actuator coordinates from an OMPL state."""
    dim = space.getDimension()
    # RealVectorStateSpace state supports indexing in Python bindings.
    return np.asarray([float(state[i]) for i in range(dim)], dtype=np.float64)


def write_u_to_ompl_state(space: Any, state: Any, u: NDArray[np.float64]) -> None:
    """Write actuator coordinates into an OMPL state."""
    dim = space.getDimension()
    u_arr = np.asarray(u, dtype=np.float64)
    if u_arr.shape != (dim,):
        raise ValueError(f"u shape {u_arr.shape} does not match space dim {dim}")
    for i in range(dim):
        state[i] = float(u_arr[i])


def physical_state_from_ompl(
    robot: RobotModel,
    space: Any,
    state: Any,
    *,
    assembly_state: dict[str, Any] | None = None,
) -> PhysicalState:
    """Rebuild authoritative ``PhysicalState`` from an OMPL U-state."""
    u = u_from_ompl_state(space, state)
    return robot.state_from_input(u, assembly_state=assembly_state)


def allocate_ompl_state(space: Any, u: NDArray[np.float64]) -> Any:
    """Allocate a scoped OMPL state and fill it from ``u``."""
    ob, _og = require_ompl()
    scoped = ob.State(space)
    write_u_to_ompl_state(space, scoped(), u)
    return scoped


def round_trip_residuals(
    robot: RobotModel,
    state: PhysicalState,
    *,
    assembly_state: dict[str, Any] | None = None,
) -> tuple[float, float]:
    """Encode ``state.u`` to OMPL and back; return ``(||du||, ||q-g(u)||)``."""
    space = build_actuator_state_space(robot)
    scoped = allocate_ompl_state(space, state.u)
    restored = physical_state_from_ompl(
        robot, space, scoped(), assembly_state=assembly_state
    )
    du = float(np.linalg.norm(restored.u - state.u))
    # Consistency residual of restored physical state.
    q_fwd = robot.state_from_input(restored.u, assembly_state=assembly_state).q
    dq = float(np.linalg.norm(restored.q - q_fwd))
    return du, dq
