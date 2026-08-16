"""Output-range taxonomy for the V3.6D canonical span corpus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping

import numpy as np

RangeClassification = Literal[
    "restricted_control",
    "biological_refinement",
    "central_biological_anchor",
    "near_limit_stress",
    "legacy_regression",
]

SPAN_CLASSIFICATION: dict[float, RangeClassification] = {
    95.0: "restricted_control",
    135.0: "biological_refinement",
    145.0: "central_biological_anchor",
    150.0: "biological_refinement",
    175.0: "near_limit_stress",
    78.041: "legacy_regression",
}

_CONTAINMENT_ATOL = 1e-12


def _interval(values: tuple[float, float], *, name: str) -> tuple[float, float]:
    lo, hi = float(values[0]), float(values[1])
    if not np.isfinite(lo) or not np.isfinite(hi):
        raise ValueError(f"{name} bounds must be finite")
    if hi <= lo:
        raise ValueError(f"{name} must have positive width, got [{lo}, {hi}]")
    return (lo, hi)


def _contains(
    inner: tuple[float, float],
    outer: tuple[float, float],
    *,
    name: str,
) -> None:
    if inner[0] < outer[0] - _CONTAINMENT_ATOL or inner[1] > outer[1] + _CONTAINMENT_ATOL:
        raise ValueError(f"{name} must be contained in the enclosing interval")


@dataclass(frozen=True, slots=True)
class OutputRangeDefinition:
    """Nested mechanical / usable / task output intervals for one axis."""

    target_span_deg: float
    center_deg: float
    mechanical_interval_rad: tuple[float, float]
    usable_interval_rad: tuple[float, float]
    task_interval_rad: tuple[float, float] | None
    classification: RangeClassification

    def __post_init__(self) -> None:
        if not np.isfinite(self.target_span_deg) or float(self.target_span_deg) <= 0.0:
            raise ValueError("target_span_deg must be finite and positive")
        if not np.isfinite(self.center_deg):
            raise ValueError("center_deg must be finite")
        mechanical = _interval(self.mechanical_interval_rad, name="mechanical")
        usable = _interval(self.usable_interval_rad, name="usable")
        _contains(usable, mechanical, name="usable")
        if self.task_interval_rad is not None:
            task = _interval(self.task_interval_rad, name="task")
            _contains(task, usable, name="task")
        object.__setattr__(self, "mechanical_interval_rad", mechanical)
        object.__setattr__(self, "usable_interval_rad", usable)

    @property
    def usable_span_rad(self) -> float:
        """Width of the certified usable interval."""
        return float(self.usable_interval_rad[1] - self.usable_interval_rad[0])

    @property
    def usable_span_deg(self) -> float:
        """Width of the certified usable interval in degrees."""
        return float(np.rad2deg(self.usable_span_rad))

    def assert_zero_centered(self, *, atol: float = 1e-12) -> None:
        """Require the V3.6D canonical chart ``q in [-R/2, R/2]``."""
        if abs(float(self.center_deg)) > atol:
            raise ValueError("V3.6D usable intervals must be centered at 0 deg")
        mid = 0.5 * (
            float(self.usable_interval_rad[0]) + float(self.usable_interval_rad[1])
        )
        if abs(mid) > atol:
            raise ValueError("usable interval midpoint must be 0 rad")

    def to_dict(self) -> dict[str, Any]:
        """Serialize the range record."""
        return {
            "target_span_deg": float(self.target_span_deg),
            "center_deg": float(self.center_deg),
            "mechanical_interval_rad": list(self.mechanical_interval_rad),
            "usable_interval_rad": list(self.usable_interval_rad),
            "task_interval_rad": (
                None
                if self.task_interval_rad is None
                else list(self.task_interval_rad)
            ),
            "classification": self.classification,
            "usable_span_deg": self.usable_span_deg,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OutputRangeDefinition:
        """Deserialize a range record."""
        task = data.get("task_interval_rad")
        return cls(
            target_span_deg=float(data["target_span_deg"]),
            center_deg=float(data["center_deg"]),
            mechanical_interval_rad=(
                float(data["mechanical_interval_rad"][0]),
                float(data["mechanical_interval_rad"][1]),
            ),
            usable_interval_rad=(
                float(data["usable_interval_rad"][0]),
                float(data["usable_interval_rad"][1]),
            ),
            task_interval_rad=(
                None if task is None else (float(task[0]), float(task[1]))
            ),
            classification=str(data["classification"]),  # type: ignore[arg-type]
        )


def classification_for_span_deg(span_deg: float) -> RangeClassification:
    """Return the frozen classification for a target span."""
    key = float(span_deg)
    if key in SPAN_CLASSIFICATION:
        return SPAN_CLASSIFICATION[key]
    raise ValueError(f"no classification for span {span_deg}")


def zero_centered_usable(
    *,
    target_span_deg: float,
    usable_span_rad: float,
    mechanical_span_rad: float,
    classification: RangeClassification | None = None,
) -> OutputRangeDefinition:
    """Build nested intervals centered at zero for one target span."""
    if usable_span_rad <= 0.0 or mechanical_span_rad <= 0.0:
        raise ValueError("usable and mechanical spans must be positive")
    if usable_span_rad > mechanical_span_rad + _CONTAINMENT_ATOL:
        raise ValueError("usable span must not exceed mechanical span")
    half_u = 0.5 * float(usable_span_rad)
    half_m = 0.5 * float(mechanical_span_rad)
    label = classification or classification_for_span_deg(target_span_deg)
    record = OutputRangeDefinition(
        target_span_deg=float(target_span_deg),
        center_deg=0.0,
        mechanical_interval_rad=(-half_m, half_m),
        usable_interval_rad=(-half_u, half_u),
        task_interval_rad=None,
        classification=label,
    )
    record.assert_zero_centered()
    return record
