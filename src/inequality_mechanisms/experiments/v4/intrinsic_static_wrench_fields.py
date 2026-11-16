"""V4.3 force-set, scalar, directional, and status field builders (V4-302–305).

All force mathematics come from the accepted V3.6E API. This module wraps
retained consumer rows into inspectable field records, eligibility masks,
and paired comparisons without inventing a second solver.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

from inequality_mechanisms.audits.v4_3_artifact import encode_numeric_field
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench import (
    ConsumedSourceRow,
    PairedPhysicalSample,
    SourceIdentity,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    ROW_SCHEMA_VERSION,
)
from inequality_mechanisms.metrics.static_wrench import (
    DEFAULT_TORQUE_LIMITS,
    NEAR_SINGULAR_CONDITION,
    StaticWrenchCapability2D,
    WrenchStateStatus,
    static_wrench_from_maps,
)
from inequality_mechanisms.metrics.wrench_directions import (
    DIRECTION_EPS,
    named_task_directions,
)
from inequality_mechanisms.transmission_geometry import rank_report

PRIMARY_MECHANISM_PAIR: tuple[str, str] = ("fourbar", "span_matched_gearbox")
IDENTITY_REFERENCE_MECHANISM = "identity_on_shared_q"
NAMED_DIRECTIONS: tuple[str, ...] = (
    "positive_x",
    "positive_y",
    "radial",
    "tangential",
)
PRIMARY_DISPLAY_STATUSES = frozenset({WrenchStateStatus.REGULAR.value})
VERTEX_FEASIBILITY_ATOL = 1e-9

INHERITED_TOLERANCE_POLICY: dict[str, Any] = {
    "direction_eps": DIRECTION_EPS,
    "near_singular_condition": NEAR_SINGULAR_CONDITION,
    "vertex_feasibility_atol": VERTEX_FEASIBILITY_ATOL,
    "primary_display_statuses": sorted(PRIMARY_DISPLAY_STATUSES),
    "note": (
        "Rank, direction, and near-singular thresholds are inherited from "
        "the V3.6E API; V4.3 does not retune them for display."
    ),
}


@dataclass(frozen=True, slots=True)
class VertexFeasibility:
    """Residuals for retained torque-box vertices against the H-representation."""

    ok: bool
    max_hrep_residual: float | None
    max_corner_saturation_residual: float | None
    n_vertices: int
    failure_code: str | None
    details: Mapping[str, Any]


def support_along(
    vertices: ArrayLike,
    direction: ArrayLike,
) -> float:
    """Diagnostic support ``max <F, d>`` over polygon vertices.

    This is not the shipped ray-capacity field. Use only to contrast ray
    capacity against the support function in analytic fixtures.
    """
    verts = np.asarray(vertices, dtype=np.float64)
    d = np.asarray(direction, dtype=np.float64).reshape(-1)
    nrm = float(np.linalg.norm(d))
    if verts.size == 0 or nrm <= DIRECTION_EPS:
        return float("nan")
    d = d / nrm
    return float(np.max(verts @ d))


def vertex_feasibility(
    wrench: StaticWrenchCapability2D,
    *,
    atol: float = VERTEX_FEASIBILITY_ATOL,
) -> VertexFeasibility:
    """Check retained vertices against H-rep and actuator-corner saturation."""
    if wrench.vertices is None:
        return VertexFeasibility(
            ok=True,
            max_hrep_residual=None,
            max_corner_saturation_residual=None,
            n_vertices=0,
            failure_code=None,
            details={"vertices": None, "reason": "no_closed_polygon"},
        )
    verts = np.asarray(wrench.vertices, dtype=np.float64)
    hrep_a = np.asarray(wrench.hrep_a, dtype=np.float64)
    hrep_b = np.asarray(wrench.hrep_b, dtype=np.float64)
    a_map = np.asarray(wrench.j_xu, dtype=np.float64).T
    tau = np.asarray(wrench.torque_limits, dtype=np.float64)

    hrep_residuals = hrep_a @ verts.T - hrep_b.reshape(-1, 1)
    max_hrep = float(np.max(hrep_residuals)) if hrep_residuals.size else 0.0

    corner_residuals: list[float] = []
    for vertex in verts:
        tau_u = a_map @ vertex
        corner_residuals.append(float(np.max(np.abs(tau_u) - tau)))
    max_corner = float(max(corner_residuals)) if corner_residuals else 0.0

    ok = max_hrep <= atol and max_corner <= atol
    failure = None if ok else "vertex_feasibility_failed"
    return VertexFeasibility(
        ok=ok,
        max_hrep_residual=max_hrep,
        max_corner_saturation_residual=max_corner,
        n_vertices=int(verts.shape[0]),
        failure_code=failure,
        details={
            "atol": float(atol),
            "hrep_residual_max": max_hrep,
            "corner_saturation_residual_max": max_corner,
        },
    )


def primary_eligible(wrench: StaticWrenchCapability2D | None) -> bool:
    """True when the primary heatmap may show this record."""
    if wrench is None:
        return False
    if wrench.status.value not in PRIMARY_DISPLAY_STATUSES:
        return False
    value = float(wrench.isotropic_radius)
    return math.isfinite(value)


def _scalar_status_for_wrench(
    wrench: StaticWrenchCapability2D | None,
    *,
    source_failure_code: str | None,
) -> tuple[float | None, str, str | None]:
    if source_failure_code is not None or wrench is None:
        return None, "source_failure", source_failure_code or "missing_wrench"
    if wrench.status == WrenchStateStatus.INVALID_MECHANISM_STATE:
        return None, "invalid", wrench.status.value
    value = float(wrench.isotropic_radius)
    if math.isinf(value):
        return None, "unbounded", wrench.status.value
    if not math.isfinite(value):
        return None, "undefined", "nonfinite_isotropic_radius"
    if wrench.status.value not in PRIMARY_DISPLAY_STATUSES:
        return value, "masked_nonregular", wrench.status.value
    return value, "finite", None


def classify_scalar_field(
    wrench: StaticWrenchCapability2D | None,
    *,
    source_failure_code: str | None = None,
) -> dict[str, Any]:
    """Encode ``isotropic_radius`` for strict JSON with eligibility status."""
    value, status, reason = _scalar_status_for_wrench(
        wrench, source_failure_code=source_failure_code
    )
    return encode_numeric_field(value, status=status, reason=reason)


def classify_directional_field(
    wrench: StaticWrenchCapability2D | None,
    direction: str,
    *,
    source_failure_code: str | None = None,
) -> dict[str, Any]:
    """Encode one named ray capacity independently of other directions.

    Whole-set status remains separate: an unbounded strip may still carry a
    finite directional capacity along a constrained axis.
    """
    if source_failure_code is not None or wrench is None:
        return encode_numeric_field(
            None,
            status="source_failure",
            reason=source_failure_code or "missing_wrench",
        )
    if wrench.status == WrenchStateStatus.INVALID_MECHANISM_STATE:
        return encode_numeric_field(None, status="invalid", reason=wrench.status.value)
    if direction in wrench.undefined_directions:
        return encode_numeric_field(
            None, status="undefined", reason="undefined_task_direction"
        )
    raw = float(wrench.directional_capacity.get(direction, float("nan")))
    if math.isinf(raw):
        return encode_numeric_field(
            None, status="unbounded", reason="unbounded_ideal_direction"
        )
    if not math.isfinite(raw):
        return encode_numeric_field(
            None, status="undefined", reason="nonfinite_directional_capacity"
        )
    return encode_numeric_field(raw, status="finite")


def direction_vectors_for_wrench(
    wrench: StaticWrenchCapability2D,
) -> dict[str, list[float] | None]:
    """Record the named unit directions used for this state."""
    named = named_task_directions(wrench.x)
    out: dict[str, list[float] | None] = {}
    for name in NAMED_DIRECTIONS:
        vec = named.get(name)
        out[name] = None if vec is None else [float(v) for v in np.asarray(vec)]
    return out


def build_force_record(item: ConsumedSourceRow) -> dict[str, Any]:
    """Per-state force-set record with identity and vertex residuals."""
    identity = item.identity
    record: dict[str, Any] = {
        "schema_version": ROW_SCHEMA_VERSION,
        "case_id": identity.case_id,
        "q_sample_id": identity.q_sample_id,
        "mechanism_id": identity.mechanism_id,
        "mechanism_pair_id": identity.mechanism_pair_id,
        "grid_index": [int(identity.grid_index[0]), int(identity.grid_index[1])],
        "config_digest": identity.config_digest,
        "source_revision": identity.source_revision,
        "source_relpath": identity.source_relpath,
        "source_failure_code": item.source_failure_code,
        "source_failure_message": item.source_failure_message,
        "wrench": None,
        "vertex_feasibility": None,
        "isotropic_radius_field": classify_scalar_field(
            item.wrench, source_failure_code=item.source_failure_code
        ),
        "directional_fields": {
            name: classify_directional_field(
                item.wrench,
                name,
                source_failure_code=item.source_failure_code,
            )
            for name in NAMED_DIRECTIONS
        },
        "status": None,
        "rank_attribution": None,
        "primary_eligible": False,
    }
    if item.wrench is None:
        return record

    wrench = item.wrench
    feasibility = vertex_feasibility(wrench)
    record["wrench"] = wrench.to_dict()
    record["vertex_feasibility"] = {
        "ok": feasibility.ok,
        "max_hrep_residual": feasibility.max_hrep_residual,
        "max_corner_saturation_residual": (feasibility.max_corner_saturation_residual),
        "n_vertices": feasibility.n_vertices,
        "failure_code": feasibility.failure_code,
        "details": dict(feasibility.details),
    }
    record["status"] = wrench.status.value
    record["rank_attribution"] = dict(wrench.rank_attribution)
    record["singular_values"] = [float(v) for v in wrench.singular_values]
    record["direction_vectors"] = direction_vectors_for_wrench(wrench)
    record["primary_eligible"] = primary_eligible(wrench)
    record["low_gain_warning"] = (
        wrench.rank_attribution.get("primary_cause") == "four_bar_low_gain"
    )
    return record


def paired_eligible(
    left: StaticWrenchCapability2D | None,
    right: StaticWrenchCapability2D | None,
    *,
    key: str = "isotropic_radius",
) -> tuple[bool, str | None]:
    """Decide whether a paired delta/ratio may be formed."""
    if left is None or right is None:
        return False, "missing_wrench"
    if left.status.value not in PRIMARY_DISPLAY_STATUSES:
        return False, f"left_{left.status.value}"
    if right.status.value not in PRIMARY_DISPLAY_STATUSES:
        return False, f"right_{right.status.value}"
    if key == "isotropic_radius":
        lv = float(left.isotropic_radius)
        rv = float(right.isotropic_radius)
    else:
        if key in left.undefined_directions or key in right.undefined_directions:
            return False, "undefined_direction"
        lv = float(left.directional_capacity.get(key, float("nan")))
        rv = float(right.directional_capacity.get(key, float("nan")))
    if not math.isfinite(lv) or not math.isfinite(rv):
        if math.isinf(lv) or math.isinf(rv):
            return False, "unbounded"
        return False, "undefined"
    if rv <= 0.0:
        return False, "nonpositive_denominator"
    return True, None


def paired_delta_ratio(
    left_value: float,
    right_value: float,
    *,
    eligible: bool,
    exclusion_reason: str | None,
) -> dict[str, Any]:
    """Encode paired delta and ratio under eligibility rules."""
    if not eligible:
        return {
            "eligible": False,
            "exclusion_reason": exclusion_reason,
            "delta": encode_numeric_field(
                None, status="invalid", reason=exclusion_reason or "ineligible"
            ),
            "ratio": encode_numeric_field(
                None, status="invalid", reason=exclusion_reason or "ineligible"
            ),
        }
    delta = float(left_value) - float(right_value)
    ratio = float(left_value) / float(right_value)
    return {
        "eligible": True,
        "exclusion_reason": None,
        "delta": encode_numeric_field(delta, status="finite"),
        "ratio": encode_numeric_field(ratio, status="finite"),
    }


def shared_color_limits(
    values: Sequence[float],
) -> dict[str, float | None]:
    """Deterministic paired colour limits from eligible finite values."""
    finite = [float(v) for v in values if math.isfinite(float(v))]
    if not finite:
        return {"vmin": None, "vmax": None, "n_values": 0}
    return {
        "vmin": float(min(finite)),
        "vmax": float(max(finite)),
        "n_values": len(finite),
    }


def _value_for_key(wrench: StaticWrenchCapability2D, key: str) -> float:
    if key == "isotropic_radius":
        return float(wrench.isotropic_radius)
    return float(wrench.directional_capacity.get(key, float("nan")))


def paired_comparison_summary(
    pairs: Sequence[PairedPhysicalSample],
    *,
    left_id: str = PRIMARY_MECHANISM_PAIR[0],
    right_id: str = PRIMARY_MECHANISM_PAIR[1],
    key: str = "isotropic_radius",
) -> dict[str, Any]:
    """Paired four-bar/gearbox deltas and ratios with exclusion counts."""
    exclusions: Counter[str] = Counter()
    eligible_count = 0
    scale_values: list[float] = []
    comparisons: list[dict[str, Any]] = []

    for pair in pairs:
        left_item = pair.arms[left_id]
        right_item = pair.arms[right_id]
        left = left_item.wrench
        right = right_item.wrench
        ok, reason = paired_eligible(left, right, key=key)
        if not ok or left is None or right is None:
            exclusions[reason or "ineligible"] += 1
            comparisons.append(
                {
                    "case_id": pair.case_id,
                    "q_sample_id": pair.q_sample_id,
                    "grid_index": list(pair.grid_index),
                    **paired_delta_ratio(
                        0.0,
                        0.0,
                        eligible=False,
                        exclusion_reason=reason,
                    ),
                }
            )
            continue
        left_value = _value_for_key(left, key)
        right_value = _value_for_key(right, key)
        eligible_count += 1
        scale_values.extend([left_value, right_value])
        comparisons.append(
            {
                "case_id": pair.case_id,
                "q_sample_id": pair.q_sample_id,
                "grid_index": list(pair.grid_index),
                **paired_delta_ratio(
                    left_value,
                    right_value,
                    eligible=True,
                    exclusion_reason=None,
                ),
            }
        )

    return {
        "key": key,
        "left_mechanism_id": left_id,
        "right_mechanism_id": right_id,
        "n_pairs": len(pairs),
        "n_eligible": eligible_count,
        "exclusion_counts": dict(sorted(exclusions.items())),
        "shared_color_limits": shared_color_limits(scale_values),
        "comparisons": comparisons,
    }


def status_mask(
    pairs: Sequence[PairedPhysicalSample],
) -> dict[str, Any]:
    """Whole-set status per arm/cell, distinct from per-direction labels."""
    cells: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for pair in pairs:
        arm_status: dict[str, Any] = {}
        for mechanism_id, item in pair.arms.items():
            if item.wrench is None:
                value = "source_failure"
            else:
                value = item.wrench.status.value
            arm_status[mechanism_id] = value
            counts[value] += 1
        cells.append(
            {
                "case_id": pair.case_id,
                "q_sample_id": pair.q_sample_id,
                "grid_index": list(pair.grid_index),
                "status_by_mechanism": arm_status,
            }
        )
    return {
        "n_cells": len(cells),
        "status_counts": dict(sorted(counts.items())),
        "cells": cells,
    }


def rank_attribution_summary(item: ConsumedSourceRow) -> dict[str, Any]:
    """Retain J_g / J_f / J_xu attribution and singular values."""
    if item.wrench is None:
        return {
            "source_failure_code": item.source_failure_code,
            "rank_attribution": None,
            "singular_values": None,
            "rank": None,
            "low_gain_warning": False,
        }
    return {
        "source_failure_code": None,
        "rank_attribution": dict(item.wrench.rank_attribution),
        "singular_values": [float(v) for v in item.wrench.singular_values],
        "rank": int(item.wrench.rank),
        "low_gain_warning": (
            item.wrench.rank_attribution.get("primary_cause") == "four_bar_low_gain"
        ),
        "status": item.wrench.status.value,
    }


def direction_status_mask(item: ConsumedSourceRow) -> dict[str, dict[str, Any]]:
    """Per-direction field status for one consumed row."""
    return {
        name: classify_directional_field(
            item.wrench,
            name,
            source_failure_code=item.source_failure_code,
        )
        for name in NAMED_DIRECTIONS
    }


def regular_unit_arm_fixture() -> StaticWrenchCapability2D:
    """Sprint §5 regular analytic fixture via ``static_wrench_from_maps``."""
    j_g = np.eye(2, dtype=np.float64)
    j_xu = np.array([[-1.0, -1.0], [1.0, 0.0]], dtype=np.float64)
    j_f = j_xu.copy()
    q = np.array([0.0, math.pi / 2.0], dtype=np.float64)
    u = q.copy()
    x = np.array([0.0, 1.0], dtype=np.float64)
    return static_wrench_from_maps(
        q=q,
        u=u,
        x=x,
        j_g=j_g,
        j_f=j_f,
        j_xu=j_xu,
        torque_limits=DEFAULT_TORQUE_LIMITS,
        named_directions=named_task_directions(x),
        rank_u_to_q=rank_report(j_g),
        rank_q_to_x=rank_report(j_f),
        rank_u_to_x=rank_report(j_xu),
    )


def stretched_unit_arm_fixture() -> StaticWrenchCapability2D:
    """Sprint §5 stretched/singular strip fixture."""
    j_g = np.eye(2, dtype=np.float64)
    j_xu = np.array([[0.0, 0.0], [2.0, 1.0]], dtype=np.float64)
    j_f = j_xu.copy()
    q = np.array([0.0, 0.0], dtype=np.float64)
    u = q.copy()
    x = np.array([2.0, 0.0], dtype=np.float64)
    return static_wrench_from_maps(
        q=q,
        u=u,
        x=x,
        j_g=j_g,
        j_f=j_f,
        j_xu=j_xu,
        torque_limits=DEFAULT_TORQUE_LIMITS,
        named_directions=named_task_directions(x),
        rank_u_to_q=rank_report(j_g),
        rank_q_to_x=rank_report(j_f),
        rank_u_to_x=rank_report(j_xu),
    )


def analytic_fixture_expectations() -> dict[str, Any]:
    """Machine-readable sprint §5 expectations for packet fixtures."""
    return {
        "regular_unit_arm": {
            "vertices_ccw": [[-1.0, -2.0], [1.0, 0.0], [1.0, 2.0], [-1.0, 0.0]],
            "isotropic_radius": 1.0 / math.sqrt(2.0),
            "positive_x_ray": 1.0,
            "positive_y_ray": 1.0,
            "positive_y_support_diagnostic": 2.0,
        },
        "stretched_unit_arm": {
            "vertices": None,
            "isotropic_radius": 0.5,
            "positive_x_ray": "unbounded",
            "positive_y_ray": 0.5,
            "force_set": "strip_abs_Fy_le_0.5_Fx_unbounded",
        },
        "inherited_tolerances": dict(INHERITED_TOLERANCE_POLICY),
    }


def force_records_from_consumed(
    items: Sequence[ConsumedSourceRow],
) -> list[dict[str, Any]]:
    """Map a consumed corpus/smoke subset to force-set records."""
    return [build_force_record(item) for item in items]


def identity_key(identity: SourceIdentity) -> dict[str, Any]:
    """Compact source identity for field grids."""
    return {
        "case_id": identity.case_id,
        "q_sample_id": identity.q_sample_id,
        "mechanism_id": identity.mechanism_id,
        "grid_index": list(identity.grid_index),
    }


__all__ = [
    "IDENTITY_REFERENCE_MECHANISM",
    "INHERITED_TOLERANCE_POLICY",
    "NAMED_DIRECTIONS",
    "PRIMARY_DISPLAY_STATUSES",
    "PRIMARY_MECHANISM_PAIR",
    "VERTEX_FEASIBILITY_ATOL",
    "VertexFeasibility",
    "analytic_fixture_expectations",
    "build_force_record",
    "classify_directional_field",
    "classify_scalar_field",
    "direction_status_mask",
    "direction_vectors_for_wrench",
    "force_records_from_consumed",
    "identity_key",
    "paired_comparison_summary",
    "paired_delta_ratio",
    "paired_eligible",
    "primary_eligible",
    "rank_attribution_summary",
    "regular_unit_arm_fixture",
    "shared_color_limits",
    "status_mask",
    "stretched_unit_arm_fixture",
    "support_along",
    "vertex_feasibility",
]
