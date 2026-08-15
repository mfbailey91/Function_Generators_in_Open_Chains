"""Kinematic transmission geometry kernel.

V4-002 lands robot-independent differential algebra. Metric, snapshot, and
robot-protocol modules remain unauthorized until later V4.0 work packages.
"""

from inequality_mechanisms.transmission_geometry.differential import (
    DEFAULT_RANK_TOLERANCE_FACTOR,
    RankReport,
    composite_jacobian,
    default_rank_tolerance,
    pullback_covector,
    pushforward_vector,
    rank_report,
)
from inequality_mechanisms.transmission_geometry.errors import (
    DifferentialShapeError,
    DifferentialSingularityError,
    TransmissionGeometryError,
)

__all__ = [
    "DEFAULT_RANK_TOLERANCE_FACTOR",
    "DifferentialShapeError",
    "DifferentialSingularityError",
    "RankReport",
    "TransmissionGeometryError",
    "composite_jacobian",
    "default_rank_tolerance",
    "pullback_covector",
    "pushforward_vector",
    "rank_report",
]
