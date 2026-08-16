"""Snapshot-backed atlas rows. No local Jacobian or metric formulas."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from inequality_mechanisms.experiments.v4.atlas_config import Planar2RGeometryAtlasConfig
from inequality_mechanisms.experiments.v4.controls import AtlasArm
from inequality_mechanisms.experiments.v4.shared_q_atlas import SharedQSample
from inequality_mechanisms.transmission_geometry import geometry_snapshot
from inequality_mechanisms.transmission_geometry.snapshot import KinematicGeometrySnapshot

ATLAS_ROW_SCHEMA_VERSION = "v4.1.atlas_row.v1"


class AtlasRecordError(ValueError):
    """Typed atlas evaluation failure."""

    def __init__(self, message: str, *, failure_code: str) -> None:
        super().__init__(message)
        self.failure_code = failure_code


def git_revision() -> str | None:
    """Return HEAD SHA, or None if git is unavailable."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = proc.stdout.strip()
    return value or None


@dataclass(frozen=True, slots=True)
class AtlasRow:
    """One shared-Q sample evaluated on one mechanism arm."""

    q_sample_id: str
    mechanism_id: str
    mechanism_pair_id: str
    grid_index: tuple[int, int]
    snapshot: KinematicGeometrySnapshot | None
    config_digest: str
    git_revision: str | None
    failure_code: str | None
    failure_message: str | None

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable envelope around a V4.0 geometry snapshot."""
        record: dict[str, Any] = {
            "schema_version": ATLAS_ROW_SCHEMA_VERSION,
            "q_sample_id": self.q_sample_id,
            "mechanism_id": self.mechanism_id,
            "mechanism_pair_id": self.mechanism_pair_id,
            "grid_index": [int(self.grid_index[0]), int(self.grid_index[1])],
            "config_digest": self.config_digest,
            "git_revision": self.git_revision,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
            "snapshot": None if self.snapshot is None else self.snapshot.to_dict(),
        }
        return record

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AtlasRow:
        """Restore a row from :meth:`to_dict`."""
        snapshot_payload = data.get("snapshot")
        snapshot = (
            None
            if snapshot_payload is None
            else KinematicGeometrySnapshot.from_dict(snapshot_payload)
        )
        grid = data["grid_index"]
        return cls(
            q_sample_id=str(data["q_sample_id"]),
            mechanism_id=str(data["mechanism_id"]),
            mechanism_pair_id=str(data["mechanism_pair_id"]),
            grid_index=(int(grid[0]), int(grid[1])),
            snapshot=snapshot,
            config_digest=str(data["config_digest"]),
            git_revision=data.get("git_revision"),
            failure_code=data.get("failure_code"),
            failure_message=data.get("failure_message"),
        )


def evaluate_atlas_sample(
    arm: AtlasArm,
    sample: SharedQSample,
    *,
    config: Planar2RGeometryAtlasConfig,
    revision: str | None,
) -> AtlasRow:
    """Call the V4.0 snapshot builder at the unique inverse of ``sample.q``."""
    q = np.asarray(sample.q, dtype=np.float64)
    try:
        candidates = arm.robot.states_from_output(q)
        if not candidates:
            raise AtlasRecordError(
                "unique inverse missing",
                failure_code="invalid_physical_state",
            )
        state = candidates[0].state
        q_fwd = np.asarray(state.q, dtype=np.float64)
        if not np.allclose(q_fwd, q, atol=1e-9, rtol=0.0):
            raise AtlasRecordError(
                "inverse realization drifted from the shared q sample",
                failure_code="invalid_physical_state",
            )
        snapshot = geometry_snapshot(arm.robot, state)
    except AtlasRecordError as exc:
        return AtlasRow(
            q_sample_id=sample.q_sample_id,
            mechanism_id=arm.mechanism_id,
            mechanism_pair_id=config.mechanism_pair_id,
            grid_index=sample.grid_index,
            snapshot=None,
            config_digest=config.digest(),
            git_revision=revision,
            failure_code=exc.failure_code,
            failure_message=str(exc),
        )
    except Exception as exc:
        return AtlasRow(
            q_sample_id=sample.q_sample_id,
            mechanism_id=arm.mechanism_id,
            mechanism_pair_id=config.mechanism_pair_id,
            grid_index=sample.grid_index,
            snapshot=None,
            config_digest=config.digest(),
            git_revision=revision,
            failure_code="invalid_physical_state",
            failure_message=str(exc),
        )
    return AtlasRow(
        q_sample_id=sample.q_sample_id,
        mechanism_id=arm.mechanism_id,
        mechanism_pair_id=config.mechanism_pair_id,
        grid_index=sample.grid_index,
        snapshot=snapshot,
        config_digest=config.digest(),
        git_revision=revision,
        failure_code=None,
        failure_message=None,
    )


def assert_shared_pose(rows_by_mechanism: Mapping[str, AtlasRow]) -> None:
    """Fail closed if successful rows at one sample disagree in q or x."""
    successful = [
        row for row in rows_by_mechanism.values() if row.snapshot is not None
    ]
    if len(successful) < 2:
        return
    q0 = np.asarray(successful[0].snapshot.q, dtype=np.float64)
    x0 = np.asarray(successful[0].snapshot.x, dtype=np.float64)
    for row in successful[1:]:
        q = np.asarray(row.snapshot.q, dtype=np.float64)
        x = np.asarray(row.snapshot.x, dtype=np.float64)
        if not np.allclose(q, q0, atol=1e-9, rtol=0.0):
            raise AtlasRecordError(
                "shared-Q mismatch at "
                f"{row.q_sample_id}: {q.tolist()} vs {q0.tolist()}",
                failure_code="unequal_shared_pose",
            )
        if not np.allclose(x, x0, atol=1e-9, rtol=0.0):
            raise AtlasRecordError(
                "shared-X mismatch at "
                f"{row.q_sample_id}: {x.tolist()} vs {x0.tolist()}",
                failure_code="unequal_shared_pose",
            )
