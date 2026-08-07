"""OMPL state and motion validity bridges (V3-503)."""

from __future__ import annotations

from typing import Any

from inequality_mechanisms.adapters.ompl._availability import require_ompl
from inequality_mechanisms.adapters.ompl.state_space import physical_state_from_ompl
from inequality_mechanisms.core.local_motion import LocalMotionModel
from inequality_mechanisms.core.problem import PlanningProblem


def _is_state_valid(
    problem: PlanningProblem,
    space: Any,
    state: Any,
    *,
    assembly_state: dict[str, Any] | None,
) -> bool:
    try:
        physical = physical_state_from_ompl(
            problem.robot,
            space,
            state,
            assembly_state=assembly_state,
        )
    except (ValueError, TypeError):
        return False
    return bool(problem.scene.state_is_valid(physical))


def make_state_validity_checker(
    si: Any,
    problem: PlanningProblem,
    space: Any,
    *,
    assembly_state: dict[str, Any] | None,
) -> Any:
    """Return an OMPL ``StateValidityChecker`` delegating to ``problem.scene``."""
    ob, _og = require_ompl()

    class _Checker(ob.StateValidityChecker):
        def __init__(self) -> None:
            super().__init__(si)

        def isValid(self, state: Any) -> bool:  # noqa: N802 — OMPL API
            return _is_state_valid(
                problem, space, state, assembly_state=assembly_state
            )

    return _Checker()


def make_motion_validator(
    si: Any,
    problem: PlanningProblem,
    space: Any,
    connector: LocalMotionModel,
    *,
    assembly_state: dict[str, Any] | None,
) -> Any:
    """Return an OMPL ``MotionValidator`` using continuous local-motion checks."""
    ob, _og = require_ompl()

    def _segment_ok(s1: Any, s2: Any) -> bool:
        try:
            a = physical_state_from_ompl(
                problem.robot, space, s1, assembly_state=assembly_state
            )
            b = physical_state_from_ompl(
                problem.robot, space, s2, assembly_state=assembly_state
            )
        except (ValueError, TypeError):
            return False
        motion = connector.connect(a, b)
        return bool(motion is not None and problem.scene.motion_is_valid(motion))

    class _MotionValidator(ob.MotionValidator):
        def __init__(self) -> None:
            super().__init__(si)

        def checkMotion(self, *args: Any) -> bool:  # noqa: N802 — OMPL API
            # OMPL exposes 2-arg and 3-arg overloads; accept both.
            if len(args) < 2:
                return False
            s1, s2 = args[0], args[1]
            ok = _segment_ok(s1, s2)
            if not ok and len(args) >= 3:
                last = args[2]
                try:
                    # last may be a mutable float holder or (state, fraction).
                    if hasattr(last, "__setitem__"):
                        last[0] = 0.0
                    elif isinstance(last, list):
                        last[0] = 0.0
                except Exception:
                    pass
            return ok

    return _MotionValidator()
