"""Rank and singularity attribution from V4.0 snapshot reports only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inequality_mechanisms.experiments.v4.geometry_atlas import AtlasRow
from inequality_mechanisms.transmission_geometry.snapshot import KinematicGeometrySnapshot


@dataclass(frozen=True, slots=True)
class RankAttribution:
    """Transmission vs manipulator vs composite rank at one sample."""

    q_sample_id: str
    mechanism_id: str
    transmission_full_rank: bool
    manipulator_full_rank: bool
    composite_full_rank: bool
    transmission_rank: int
    manipulator_rank: int
    composite_rank: int
    transmission_condition_number: float | None
    manipulator_condition_number: float | None
    composite_condition_number: float | None
    metric_status: str
    failure_code: str | None

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable rank field record."""
        return {
            "q_sample_id": self.q_sample_id,
            "mechanism_id": self.mechanism_id,
            "transmission_full_rank": self.transmission_full_rank,
            "manipulator_full_rank": self.manipulator_full_rank,
            "composite_full_rank": self.composite_full_rank,
            "transmission_rank": self.transmission_rank,
            "manipulator_rank": self.manipulator_rank,
            "composite_rank": self.composite_rank,
            "transmission_condition_number": self.transmission_condition_number,
            "manipulator_condition_number": self.manipulator_condition_number,
            "composite_condition_number": self.composite_condition_number,
            "metric_status": self.metric_status,
            "failure_code": self.failure_code,
        }


def attribution_from_snapshot(
    snapshot: KinematicGeometrySnapshot,
    *,
    q_sample_id: str,
    mechanism_id: str,
) -> RankAttribution:
    """Copy rank reports from a geometry snapshot. Do not recompute SVD."""
    return RankAttribution(
        q_sample_id=q_sample_id,
        mechanism_id=mechanism_id,
        transmission_full_rank=bool(snapshot.rank_u_to_q.full_rank),
        manipulator_full_rank=bool(snapshot.rank_q_to_x.full_rank),
        composite_full_rank=bool(snapshot.rank_u_to_x.full_rank),
        transmission_rank=int(snapshot.rank_u_to_q.rank),
        manipulator_rank=int(snapshot.rank_q_to_x.rank),
        composite_rank=int(snapshot.rank_u_to_x.rank),
        transmission_condition_number=snapshot.rank_u_to_q.condition_number,
        manipulator_condition_number=snapshot.rank_q_to_x.condition_number,
        composite_condition_number=snapshot.rank_u_to_x.condition_number,
        metric_status=str(snapshot.metric_status),
        failure_code=None,
    )


def attribution_from_row(row: AtlasRow) -> RankAttribution:
    """Build attribution from an atlas row, preserving typed failures."""
    if row.snapshot is None:
        return RankAttribution(
            q_sample_id=row.q_sample_id,
            mechanism_id=row.mechanism_id,
            transmission_full_rank=False,
            manipulator_full_rank=False,
            composite_full_rank=False,
            transmission_rank=0,
            manipulator_rank=0,
            composite_rank=0,
            transmission_condition_number=None,
            manipulator_condition_number=None,
            composite_condition_number=None,
            metric_status="unavailable",
            failure_code=row.failure_code or "invalid_physical_state",
        )
    return attribution_from_snapshot(
        row.snapshot,
        q_sample_id=row.q_sample_id,
        mechanism_id=row.mechanism_id,
    )
