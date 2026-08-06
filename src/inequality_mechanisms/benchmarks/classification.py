"""ADR-026 pre-search task classification helpers (Sprint V3.2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

#: Frozen ADR-026 string identifiers (do not invent synonyms in runners).
TASK_ALREADY_SATISFIED: Final[str] = "already satisfied"
TASK_DIRECT_LOCAL_FEASIBLE: Final[str] = "direct/local feasible"
TASK_DIRECT_CONNECTOR_UNAVAILABLE: Final[str] = "direct connector unavailable"
TASK_INVALID_UNREPRESENTABLE: Final[str] = "invalid/unrepresentable"
TASK_CERTIFIABLY_UNREACHABLE: Final[str] = "certifiably unreachable"

ALL_TASK_CLASSES: Final[tuple[str, ...]] = (
    TASK_ALREADY_SATISFIED,
    TASK_DIRECT_LOCAL_FEASIBLE,
    TASK_DIRECT_CONNECTOR_UNAVAILABLE,
    TASK_INVALID_UNREPRESENTABLE,
    TASK_CERTIFIABLY_UNREACHABLE,
)


@dataclass(frozen=True, slots=True)
class UnreachabilityCertificate:
    """Explicit certificate required for ``certifiably unreachable``.

    Smoke packs may leave this unused. Planners must not invent certificates
    from timeouts or connector failure alone (ADR-026).
    """

    kind: str
    details: dict[str, Any]


def classify_direct_attempt(
    *,
    start_valid: bool,
    goal_usable: bool,
    already_satisfied: bool,
    candidates_representable: bool,
    connector_succeeded: bool,
    certificate: UnreachabilityCertificate | None = None,
) -> str:
    """Return the ADR-026 task class for one mechanism-task instance.

    Parameters
    ----------
    start_valid :
        Whether the exact start is scene-/robot-valid.
    goal_usable :
        Whether the goal predicate / FK contract is usable for this robot.
    already_satisfied :
        Whether ``goal.satisfied(start)`` before search.
    candidates_representable :
        Whether at least one physical goal candidate was generated.
    connector_succeeded :
        Whether at least one declared direct connector succeeded.
    certificate :
        Optional explicit unreachability certificate.
    """
    if certificate is not None:
        return TASK_CERTIFIABLY_UNREACHABLE
    if not start_valid or not goal_usable:
        return TASK_INVALID_UNREPRESENTABLE
    if already_satisfied:
        return TASK_ALREADY_SATISFIED
    if not candidates_representable:
        return TASK_INVALID_UNREPRESENTABLE
    if connector_succeeded:
        return TASK_DIRECT_LOCAL_FEASIBLE
    return TASK_DIRECT_CONNECTOR_UNAVAILABLE
