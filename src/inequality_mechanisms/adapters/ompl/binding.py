"""Guarded OMPL binding-method application (V4-233).

Importing this module does not import ``ompl``. Missing required setters are a
typed adapter rejection, not a silent default.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any


class OmplBindingRejectedError(ValueError):
    """Required OMPL class or method is absent from the installed binding."""


def _json_safe(value: Any) -> Any:
    """Return ``value`` or a type tag when it cannot be JSON-encoded."""
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return {"nonserializable_type": type(value).__name__}
    return value


def missing_ompl_methods(planner: Any, methods: Sequence[str]) -> tuple[str, ...]:
    """Return method names ``planner`` does not expose."""
    return tuple(name for name in methods if not hasattr(planner, name))


def require_ompl_methods(
    planner: Any,
    methods: Sequence[str],
    *,
    planner_id: str,
) -> None:
    """Raise :class:`OmplBindingRejectedError` if any required method is missing."""
    missing = missing_ompl_methods(planner, methods)
    if missing:
        raise OmplBindingRejectedError(
            f"{planner_id} missing required OMPL binding methods: {list(missing)}"
        )


def apply_ompl_method(
    planner: Any,
    method_name: str,
    value: Any,
    *,
    planner_id: str,
    required: bool = True,
) -> dict[str, Any]:
    """Call ``planner.method_name(value)`` and record whether it applied.

    If ``required`` and the method is absent, raise
    :class:`OmplBindingRejectedError`. Optional missing methods are recorded
    rather than approximated.
    """
    if not hasattr(planner, method_name):
        if required:
            raise OmplBindingRejectedError(
                f"{planner_id} missing required OMPL binding method {method_name}"
            )
        return {
            "method": method_name,
            "applied": False,
            "reason": "missing_method",
            "requested": _json_safe(value),
        }
    getattr(planner, method_name)(value)
    recorded: Any = value
    getter = "get" + method_name[3:] if method_name.startswith("set") else None
    if getter is not None and hasattr(planner, getter):
        try:
            recorded = getattr(planner, getter)()
        except Exception:
            recorded = value
    return {
        "method": method_name,
        "applied": True,
        "requested": _json_safe(value),
        "recorded": _json_safe(recorded),
    }


def apply_projection_cell_sizes(
    evaluator: Any, sizes: Sequence[float]
) -> dict[str, Any]:
    """Set projection cell sizes using the live binding signature.

    OMPL 2.0.1 nanobind exposes ``setCellSizes(dim: int, cellSize: float)``.
    Older docs describe a vector overload. Try the sequence form first, then
    the proven per-dimension form, then scalar ``setCellSize``.
    """
    values = [float(value) for value in sizes]
    if not values:
        raise OmplBindingRejectedError("projection cell_sizes must be nonempty")
    setter = getattr(evaluator, "setCellSizes", None)
    if callable(setter):
        try:
            setter(values)
            return {
                "method": "setCellSizes",
                "signature": "sequence",
                "applied": True,
                "requested": values,
            }
        except TypeError:
            for dim, size in enumerate(values):
                setter(int(dim), float(size))
            return {
                "method": "setCellSizes",
                "signature": "dim_cellSize",
                "applied": True,
                "requested": values,
            }
    scalar = getattr(evaluator, "setCellSize", None)
    if callable(scalar):
        scalar(float(values[0]))
        return {
            "method": "setCellSize",
            "signature": "scalar",
            "applied": True,
            "requested": values,
        }
    raise OmplBindingRejectedError(
        "projection evaluator missing setCellSizes/setCellSize"
    )


def require_ompl_class(og: Any, class_name: str, *, planner_id: str) -> Any:
    """Return ``og.class_name`` or raise :class:`OmplBindingRejectedError`."""
    cls = getattr(og, class_name, None)
    if cls is None:
        raise OmplBindingRejectedError(
            f"{planner_id} missing ompl.geometric.{class_name}"
        )
    return cls


def validate_checkpoints(checkpoints: Sequence[float]) -> tuple[float, ...]:
    """Return a strictly increasing nonnegative checkpoint tuple."""
    times = tuple(float(t) for t in checkpoints)
    if not times:
        raise ValueError("checkpoints must be a nonempty strictly increasing sequence")
    if any(t < 0.0 for t in times):
        raise ValueError("checkpoints must be nonnegative")
    if any(times[i] <= times[i - 1] for i in range(1, len(times))):
        raise ValueError("checkpoints must be strictly increasing")
    return times


def checkpoint_costs_nonincreasing(records: Sequence[dict[str, Any]]) -> bool | None:
    """Return whether exact-solution best costs never increase, or None."""
    costs = [
        record["best_cost"] for record in records if record.get("best_cost") is not None
    ]
    if len(costs) < 2:
        return None
    return all(costs[i] <= costs[i - 1] + 1e-12 for i in range(1, len(costs)))
