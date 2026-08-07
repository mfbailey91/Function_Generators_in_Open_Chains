"""OMPL state and motion validity bridges (V3-503)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inequality_mechanisms.adapters.ompl._availability import require_ompl
from inequality_mechanisms.adapters.ompl.state_space import physical_state_from_ompl
from inequality_mechanisms.core.local_motion import LocalMotionModel
from inequality_mechanisms.core.problem import PlanningProblem


@dataclass(slots=True)
class OmplValidityCounters:
    """Count OMPL calls delegated into Version 3 validity contracts."""

    state_checks: int = 0
    motion_checks: int = 0


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
    counters: OmplValidityCounters,
) -> Any:
    """Return an OMPL ``StateValidityChecker`` delegating to ``problem.scene``."""
    ob, _og = require_ompl()

    class _Checker(ob.StateValidityChecker):
        def __init__(self) -> None:
            super().__init__(si)

        def isValid(self, state: Any) -> bool:  # noqa: N802 — OMPL API
            counters.state_checks += 1
            return _is_state_valid(
                problem, space, state, assembly_state=assembly_state
            )

    return _Checker()


def _set_last_valid_at_start(space: Any, last: Any, start_state: Any) -> bool:
    """Populate OMPL's ``lastValid`` pair conservatively at fraction zero.

    The V3 motion checker currently returns only whole-segment validity, so on
    failure the only certified prefix is the exact start. OMPL Python binding
    builds expose the C++ ``pair<State*, double>`` either as a pair-like object
    or a mutable two-element sequence; support both forms without inventing an
    interior valid fraction.
    """
    # Pair-like binding with ``first`` / ``second`` attributes.
    if hasattr(last, "first") and hasattr(last, "second"):
        try:
            destination = last.first
            if destination is not None and hasattr(space, "copyState"):
                space.copyState(destination, start_state)
            else:
                last.first = start_state
            last.second = 0.0
            return True
        except Exception:
            pass

    # Mutable sequence binding: [State*, fraction].
    try:
        destination = last[0]
        if destination is not None and hasattr(space, "copyState"):
            space.copyState(destination, start_state)
        else:
            last[0] = start_state
        last[1] = 0.0
        return True
    except Exception:
        return False


def make_motion_validator(
    si: Any,
    problem: PlanningProblem,
    space: Any,
    connector: LocalMotionModel,
    *,
    assembly_state: dict[str, Any] | None,
    counters: OmplValidityCounters,
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
            counters.motion_checks += 1
            s1, s2 = args[0], args[1]
            ok = _segment_ok(s1, s2)
            if not ok and len(args) >= 3:
                if not _set_last_valid_at_start(space, args[2], s1):
                    raise RuntimeError(
                        "unsupported OMPL lastValid Python binding representation"
                    )
            return ok

    return _MotionValidator()
