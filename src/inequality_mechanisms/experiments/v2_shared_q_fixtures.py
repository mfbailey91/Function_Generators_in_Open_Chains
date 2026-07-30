"""Frozen mechanism pairs and task templates for Sprint V2.8.

Selection is deterministic and versioned. Each arm is a certified monotonic
2R four-bar pair (one crank-rocker per joint). Pair labels follow the sprint
nonlinearity ladder: mild, moderate, strong, asymmetric, joint-distinct.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from inequality_mechanisms.experiments.v2_config import FourBarLinkConfig

PairId = Literal["pair_01", "pair_02", "pair_03", "pair_04", "pair_05"]
TaskTemplateId = Literal["cross_range", "joint1_dominant", "joint2_dominant"]

DEFAULT_ALPHAS: tuple[float, ...] = (1.0, 0.75, 0.5, 0.25, 0.0)


@dataclass(frozen=True, slots=True)
class MechanismPairFixture:
    """One frozen four-bar arm definition (per-axis links)."""

    pair_id: PairId
    label: str
    fourbars: tuple[FourBarLinkConfig, FourBarLinkConfig]

    def to_dict(self) -> dict[str, Any]:
        """Serialize for config/manifest embedding."""
        return {
            "pair_id": self.pair_id,
            "label": self.label,
            "fourbars": [
                {
                    "a": fb.a,
                    "b": fb.b,
                    "c": fb.c,
                    "d": fb.d,
                    "branch": fb.branch,
                }
                for fb in self.fourbars
            ],
        }


@dataclass(frozen=True, slots=True)
class TaskTemplate:
    """Normalized start/goal fractions inside a pair's shared output box."""

    task_set_id: TaskTemplateId
    start_fraction: tuple[float, float]
    goal_fraction: tuple[float, float]
    purpose: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the template."""
        return {
            "task_set_id": self.task_set_id,
            "start_fraction": list(self.start_fraction),
            "goal_fraction": list(self.goal_fraction),
            "purpose": self.purpose,
        }


def _fb(a: float, b: float, c: float, d: float, branch: int = 1) -> FourBarLinkConfig:
    return FourBarLinkConfig(a=a, b=b, c=c, d=d, branch=branch)


#: Five interpretable, versioned pairs (Sprint V2.8).
FROZEN_MECHANISM_PAIRS: tuple[MechanismPairFixture, ...] = (
    MechanismPairFixture(
        pair_id="pair_01",
        label="mild_gain_variation",
        fourbars=(_fb(1.0, 3.2, 2.8, 2.5), _fb(1.0, 3.2, 2.8, 2.5)),
    ),
    MechanismPairFixture(
        pair_id="pair_02",
        label="moderate_gain_variation",
        fourbars=(_fb(1.0, 2.5, 2.0, 2.0), _fb(1.0, 2.5, 2.0, 2.0)),
    ),
    MechanismPairFixture(
        pair_id="pair_03",
        label="strong_well_conditioned",
        fourbars=(_fb(1.0, 2.2, 1.8, 1.7), _fb(1.0, 2.2, 1.8, 1.7)),
    ),
    MechanismPairFixture(
        pair_id="pair_04",
        label="asymmetric_gain_distribution",
        # Same links, but branch sheet + geometry bias differs via lengths.
        fourbars=(_fb(1.0, 2.8, 2.4, 2.0), _fb(1.2, 2.6, 2.0, 1.9)),
    ),
    MechanismPairFixture(
        pair_id="pair_05",
        label="joint_distinct_behavior",
        fourbars=(_fb(1.0, 3.0, 2.5, 2.2), _fb(1.0, 2.2, 1.8, 1.7)),
    ),
)

TASK_TEMPLATES: tuple[TaskTemplate, ...] = (
    TaskTemplate(
        task_set_id="cross_range",
        start_fraction=(0.15, 0.20),
        goal_fraction=(0.85, 0.80),
        purpose="long diagonal movement through both axes",
    ),
    TaskTemplate(
        task_set_id="joint1_dominant",
        start_fraction=(0.15, 0.45),
        goal_fraction=(0.85, 0.55),
        purpose="expose joint-1 transmission structure",
    ),
    TaskTemplate(
        task_set_id="joint2_dominant",
        start_fraction=(0.45, 0.15),
        goal_fraction=(0.55, 0.85),
        purpose="expose joint-2 transmission structure",
    ),
)


def pair_by_id(pair_id: str) -> MechanismPairFixture:
    """Look up a frozen pair fixture by id."""
    for pair in FROZEN_MECHANISM_PAIRS:
        if pair.pair_id == pair_id:
            return pair
    raise KeyError(f"unknown mechanism pair id: {pair_id!r}")


def task_template_by_id(task_set_id: str) -> TaskTemplate:
    """Look up a frozen task template by id."""
    for task in TASK_TEMPLATES:
        if task.task_set_id == task_set_id:
            return task
    raise KeyError(f"unknown task template id: {task_set_id!r}")


def fractions_to_q(
    lower: Any,
    upper: Any,
    fraction: tuple[float, float] | list[float],
) -> list[float]:
    """Map normalized fractions into an absolute output vector."""
    import numpy as np

    lo = np.asarray(lower, dtype=np.float64)
    hi = np.asarray(upper, dtype=np.float64)
    z = np.asarray(fraction, dtype=np.float64)
    if lo.shape != hi.shape or z.shape != lo.shape:
        raise ValueError("lower, upper, and fraction must share one shape")
    return list(lo + z * (hi - lo))
