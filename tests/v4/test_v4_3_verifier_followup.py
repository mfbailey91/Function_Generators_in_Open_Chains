"""V4.3B adversarial verifier probes from the post-V4.3A review."""

from __future__ import annotations

import copy
import gzip
import json
from typing import Any

import numpy as np
import pytest

from inequality_mechanisms.audits import v4_3_artifact as artifact
from inequality_mechanisms.audits.v4_artifact_guard import (
    canonical_v4_3_corrective_root,
)


def _load_case_rows(case_id: str = "span_j1_095_j2_095") -> list[dict[str, Any]]:
    path = canonical_v4_3_corrective_root() / artifact.case_wrench_rel(case_id)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


@pytest.fixture(scope="module")
def near_singular_row() -> dict[str, Any]:
    return next(row for row in _load_case_rows() if row["status"] == "near_singular")


@pytest.fixture(scope="module")
def regular_row() -> dict[str, Any]:
    return next(row for row in _load_case_rows() if row["status"] == "regular")


def test_committed_corrective_rows_still_pass_tightened_rules(
    near_singular_row: dict[str, Any], regular_row: dict[str, Any]
) -> None:
    artifact._validate_row(near_singular_row)
    artifact._validate_row(regular_row)


def test_collapsed_near_singular_polygon_is_rejected(
    near_singular_row: dict[str, Any],
) -> None:
    row = copy.deepcopy(near_singular_row)
    row["vertices"] = [[0.0, 0.0] for _ in range(4)]
    with pytest.raises(artifact.V4_3ArtifactError, match="distinct"):
        artifact._validate_row(row)


def test_well_conditioned_positive_x_unbounded_relabel_is_rejected(
    near_singular_row: dict[str, Any],
) -> None:
    row = copy.deepcopy(near_singular_row)
    assert row["directional_capacity"]["positive_x"] is not None
    row["directional_capacity"]["positive_x"] = None
    row["directional_fields"]["positive_x"].update(
        value=None, status="unbounded", reason="unbounded_ideal_direction"
    )
    with pytest.raises(artifact.V4_3ArtifactError, match="ray"):
        artifact._validate_row(row)


def test_impossible_negative_hrep_residual_is_rejected(
    regular_row: dict[str, Any],
) -> None:
    row = copy.deepcopy(regular_row)
    row["vertex_feasibility"]["max_hrep_residual"] = -100.0
    row["vertex_feasibility"]["details"]["hrep_residual_max"] = -100.0
    with pytest.raises(artifact.V4_3ArtifactError, match="impossibly negative"):
        artifact._validate_row(row)


def test_bow_tie_vertex_reorder_is_rejected(regular_row: dict[str, Any]) -> None:
    row = copy.deepcopy(regular_row)
    verts = np.asarray(row["vertices"], dtype=float)
    # Swap the last two vertices to create a self-intersecting order.
    bow_tie = verts[[0, 1, 3, 2]].tolist()
    row["vertices"] = bow_tie
    with pytest.raises(
        artifact.V4_3ArtifactError, match="inconsistent|self-intersecting|effort"
    ):
        artifact._validate_row(row)


def test_aggregate_vertex_diagnostics_separates_near_singular_failures() -> None:
    rows = _load_case_rows()
    summary = artifact.aggregate_vertex_diagnostics(rows)
    assert summary["vertex_diagnostic_failures_by_status"].get("regular", 0) == 0
    assert summary["vertex_diagnostic_failures_by_status"].get("near_singular", 0) > 0
    assert "max_corner_residual" in summary
    assert "max_hrep_residual" in summary
