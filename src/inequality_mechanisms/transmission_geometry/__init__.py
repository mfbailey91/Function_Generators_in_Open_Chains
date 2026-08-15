"""Kinematic transmission geometry kernel.

V4-001 through V4-004 land the differential protocol, algebra, metric and
mobility identities, and geometry snapshots. Audit migration and smoke
artifacts remain unauthorized until later V4.0 work packages.
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
from inequality_mechanisms.transmission_geometry.metrics import (
    actuator_metric_on_q,
    mobility_on_q,
    mobility_on_x,
    pullback_metric,
    validate_positive_definite,
)
from inequality_mechanisms.transmission_geometry.protocols import (
    DEFAULT_STATE_TOLERANCE,
    KinematicTransmissionRobotModel,
)
from inequality_mechanisms.transmission_geometry.snapshot import (
    GEOMETRY_SNAPSHOT_SCHEMA_VERSION,
    METRIC_STATUS_AVAILABLE,
    METRIC_STATUS_NONSQUARE,
    METRIC_STATUS_RANK_DEFICIENT,
    KinematicGeometrySnapshot,
    geometry_snapshot,
)

__all__ = [
    "DEFAULT_RANK_TOLERANCE_FACTOR",
    "DEFAULT_STATE_TOLERANCE",
    "DifferentialShapeError",
    "DifferentialSingularityError",
    "GEOMETRY_SNAPSHOT_SCHEMA_VERSION",
    "KinematicGeometrySnapshot",
    "KinematicTransmissionRobotModel",
    "METRIC_STATUS_AVAILABLE",
    "METRIC_STATUS_NONSQUARE",
    "METRIC_STATUS_RANK_DEFICIENT",
    "RankReport",
    "TransmissionGeometryError",
    "actuator_metric_on_q",
    "composite_jacobian",
    "default_rank_tolerance",
    "geometry_snapshot",
    "mobility_on_q",
    "mobility_on_x",
    "pullback_covector",
    "pullback_metric",
    "pushforward_vector",
    "rank_report",
    "validate_positive_definite",
]
