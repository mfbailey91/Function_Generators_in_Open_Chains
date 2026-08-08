"""Audit-only planner trace capture (Sprint V3.6B / V3-622).

Traces live outside ``PlanningProblem`` and the ordinary ``PlanningResult``
schema. Opt-in sinks must not change status, selected goal, path, cost, or
standard planner metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableSequence, Protocol

JSONValue = Any


@dataclass(frozen=True, slots=True)
class PlannerTraceEvent:
    """One ordered audit event emitted by an opt-in planner sink.

    Parameters
    ----------
    family :
        Planner family label (``graph``, ``roadmap``, ``tree``, ``ompl``).
    phase :
        Coarse phase (``expand``, ``sample``, ``edge``, ``query``, ``connect``,
        ``path``, ``snapshot``, ...).
    step :
        Monotonic step index within the sink session.
    event_type :
        Fine-grained event name.
    payload :
        JSON-serializable event body.
    """

    family: str
    phase: str
    step: int
    event_type: str
    payload: Mapping[str, JSONValue]


class PlannerTraceSink(Protocol):
    """Minimal sink protocol for opt-in planner instrumentation."""

    def emit(self, event: PlannerTraceEvent) -> None:
        """Record one trace event."""


@dataclass
class ListPlannerTraceSink:
    """In-memory ordered collector used by the visual audit."""

    events: MutableSequence[PlannerTraceEvent] = field(default_factory=list)
    _step: int = 0

    def emit(self, event: PlannerTraceEvent) -> None:
        """Append ``event``, assigning ``step`` if the caller passed ``-1``."""
        if event.step < 0:
            event = PlannerTraceEvent(
                family=event.family,
                phase=event.phase,
                step=self._step,
                event_type=event.event_type,
                payload=dict(event.payload),
            )
        self._step = max(self._step, int(event.step) + 1)
        self.events.append(event)

    def record(
        self,
        *,
        family: str,
        phase: str,
        event_type: str,
        payload: Mapping[str, JSONValue] | None = None,
    ) -> None:
        """Convenience emitter that auto-assigns the next step index."""
        self.emit(
            PlannerTraceEvent(
                family=family,
                phase=phase,
                step=self._step,
                event_type=event_type,
                payload=dict(payload or {}),
            )
        )

    def clear(self) -> None:
        """Drop all events and reset the step counter."""
        self.events.clear()
        self._step = 0

    def to_jsonable(self) -> list[dict[str, Any]]:
        """Return a JSON-serializable copy of recorded events."""
        return [
            {
                "family": e.family,
                "phase": e.phase,
                "step": int(e.step),
                "event_type": e.event_type,
                "payload": dict(e.payload),
            }
            for e in self.events
        ]


__all__ = [
    "JSONValue",
    "ListPlannerTraceSink",
    "PlannerTraceEvent",
    "PlannerTraceSink",
]
