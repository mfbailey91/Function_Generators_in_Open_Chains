"""Path-quality metrics beyond length (Sprint Five S5-02 … S5-05).

Evaluates solved paths separately in ``U``, ``Q``, and Cartesian ``X``:

- directness / detour ratios;
- cumulative turning (primary in ``Q`` and ``X``);
- projected self-intersection counts;
- near-revisit distances and thresholded counts.

No composite path-quality score is defined.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from inequality_mechanisms.graphs.costs import wrapped_input_displacement
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.metrics.path_metrics import (
    PATH_METRIC_ATOL,
    PathMetrics,
    compute_path_metrics_from_trajectories,
)
from inequality_mechanisms.spaces.output_space import OutputSpace
from inequality_mechanisms.visualization.paths import path_inputs, path_outputs

# Absolute tolerances for geometric predicates (documented in Sprint Five note).
PATH_QUALITY_ATOL = 1e-12
SEGMENT_LENGTH_ATOL = 1e-12
DIRECTNESS_DENOM_ATOL = 1e-12

PATH_QUALITY_CONVENTIONS: dict[str, Any] = {
    "directness": {
        "definition": "R = L / d(start, goal) in the same space",
        "undefined": "None when endpoint displacement <= DIRECTNESS_DENOM_ATOL",
        "atol": DIRECTNESS_DENOM_ATOL,
    },
    "cumulative_turning": {
        "spaces": ["Q", "X"],
        "angular_range": "[0, pi]",
        "zero_segments": "skipped / merged before adjacent-angle accumulation",
        "atol": SEGMENT_LENGTH_ATOL,
    },
    "self_intersections": {
        "spaces": ["Q", "X"],
        "exclusions": [
            "identical segment pairs",
            "a segment against itself",
            "adjacent segments sharing a path vertex",
        ],
        "collinear_overlap": "counted as one intersection when interiors overlap",
        "endpoint_contact_nonadjacent": "counted when |t|,|u| in [0,1] within atol",
        "atol": PATH_QUALITY_ATOL,
    },
    "near_revisit": {
        "version": 1,
        "distance": "point-to-point Euclidean on projected samples",
        "exclusion": "|i - j| > revisit_exclusion_steps",
    },
}


@dataclass(frozen=True, slots=True)
class PathQualityMetrics:
    """Per-space path-quality scalars for one solved path.

    Length fields mirror :class:`PathMetrics`. Directness ratios are ``None``
    when the endpoint displacement in that space is degenerate.
    """

    n_path_edges: int
    path_length_u: float
    path_length_q: float
    path_length_x: float
    optimal_cost: float

    directness_ratio_u: float | None
    directness_ratio_q: float | None
    directness_ratio_x: float | None
    directness_defined_u: bool
    directness_defined_q: bool
    directness_defined_x: bool
    endpoint_displacement_u: float
    endpoint_displacement_q: float
    endpoint_displacement_x: float

    cumulative_turning_q: float
    cumulative_turning_x: float

    self_intersections_q: int
    self_intersections_x: int

    near_revisit_distance_q: float | None
    near_revisit_distance_x: float | None
    near_revisit_count_q: int
    near_revisit_count_x: int

    revisit_exclusion_steps: int
    revisit_threshold_q: float
    revisit_threshold_x: float

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable field dict (``None`` preserved)."""
        return asdict(self)

    def length_metrics(self) -> PathMetrics:
        """Return the length-only subset."""
        return PathMetrics(
            n_path_edges=self.n_path_edges,
            path_length_u=self.path_length_u,
            path_length_q=self.path_length_q,
            path_length_x=self.path_length_x,
            optimal_cost=self.optimal_cost,
        )


def _directness_ratio(
    length: float, displacement: float
) -> tuple[float | None, bool]:
    """Return ``(ratio_or_None, defined)``."""
    if displacement <= DIRECTNESS_DENOM_ATOL:
        return None, False
    return float(length / displacement), True


def cumulative_turning(points: np.ndarray, *, atol: float = SEGMENT_LENGTH_ATOL) -> float:
    """Sum turning angles along a 2-D polyline.

    Zero-length segments are dropped. Angles use

    ``alpha = atan2(|det(v_k, v_{k+1})|, v_k · v_{k+1})``

    in ``[0, pi]``. Paths with fewer than two nonzero segments return ``0``.
    """
    arr = np.asarray(points, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError("points must have shape (N, >=2)")
    if arr.shape[0] < 3:
        return 0.0

    segments: list[np.ndarray] = []
    for i in range(arr.shape[0] - 1):
        v = arr[i + 1, :2] - arr[i, :2]
        if float(np.linalg.norm(v)) > atol:
            segments.append(v)
    if len(segments) < 2:
        return 0.0

    total = 0.0
    for k in range(len(segments) - 1):
        v0 = segments[k]
        v1 = segments[k + 1]
        det = float(v0[0] * v1[1] - v0[1] * v1[0])
        dot = float(v0[0] * v1[0] + v0[1] * v1[1])
        total += float(np.arctan2(abs(det), dot))
    return float(total)


def segments_intersect(
    a0: np.ndarray,
    a1: np.ndarray,
    b0: np.ndarray,
    b1: np.ndarray,
    *,
    atol: float = PATH_QUALITY_ATOL,
) -> bool:
    """Return whether closed segments ``a0--a1`` and ``b0--b1`` intersect.

    Uses oriented-bounding / parametric overlap with absolute tolerance
    ``atol``. Collinear overlapping interiors count as an intersection.
    """
    p = np.asarray(a0, dtype=np.float64)[:2]
    r = np.asarray(a1, dtype=np.float64)[:2] - p
    q = np.asarray(b0, dtype=np.float64)[:2]
    s = np.asarray(b1, dtype=np.float64)[:2] - q
    rxs = float(r[0] * s[1] - r[1] * s[0])
    q_p = q - p
    qpxr = float(q_p[0] * r[1] - q_p[1] * r[0])

    if abs(rxs) <= atol and abs(qpxr) <= atol:
        rr = float(r @ r)
        if rr <= atol * atol:
            return _point_on_segment(p, q, q + s, atol=atol)
        t0 = float(q_p @ r) / rr
        t1 = float((q_p + s) @ r) / rr
        t_lo, t_hi = (t0, t1) if t0 <= t1 else (t1, t0)
        return t_hi >= -atol and t_lo <= 1.0 + atol

    if abs(rxs) <= atol:
        return False

    t = float(q_p[0] * s[1] - q_p[1] * s[0]) / rxs
    u = qpxr / rxs
    return (-atol <= t <= 1.0 + atol) and (-atol <= u <= 1.0 + atol)


def _point_on_segment(
    p: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
    *,
    atol: float,
) -> bool:
    ab = b - a
    ap = p - a
    cross = float(ab[0] * ap[1] - ab[1] * ap[0])
    if abs(cross) > atol:
        return False
    dot = float(ap @ ab)
    if dot < -atol:
        return False
    return dot <= float(ab @ ab) + atol


def count_self_intersections(
    points: np.ndarray,
    *,
    atol: float = PATH_QUALITY_ATOL,
) -> int:
    """Count intersections between nonadjacent polyline segments.

    Adjacent segments that share a vertex are excluded. Identical segment
    indices against themselves are excluded.
    """
    arr = np.asarray(points, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[0] < 4:
        return 0
    n_seg = arr.shape[0] - 1
    count = 0
    for i in range(n_seg):
        a0, a1 = arr[i], arr[i + 1]
        for j in range(i + 2, n_seg):
            b0, b1 = arr[j], arr[j + 1]
            if segments_intersect(a0, a1, b0, b1, atol=atol):
                count += 1
    return int(count)


def near_revisit_metrics(
    points: np.ndarray,
    *,
    exclusion_steps: int,
    threshold: float,
) -> tuple[float | None, int]:
    """Return ``(min nonlocal distance, thresholded pair count)``.

    Version 1 uses point-to-point Euclidean distance. When no pair satisfies
    ``|i-j| > exclusion_steps``, the minimum distance is ``None``.
    """
    arr = np.asarray(points, dtype=np.float64)
    n = int(arr.shape[0])
    m = int(exclusion_steps)
    if n < 2 or m < 0:
        return None, 0

    min_d: float | None = None
    count = 0
    thr = float(threshold)
    for i in range(n):
        for j in range(i + 1, n):
            if (j - i) <= m:
                continue
            d = float(np.linalg.norm(arr[i, :2] - arr[j, :2]))
            if min_d is None or d < min_d:
                min_d = d
            if d < thr:
                count += 1
    return min_d, int(count)


def _cartesian_path(q_path: np.ndarray, plant: Planar2R) -> np.ndarray:
    return np.vstack([plant.forward(q) for q in np.asarray(q_path, dtype=np.float64)])


def compute_path_quality_from_trajectories(
    u_path: np.ndarray,
    q_path: np.ndarray,
    *,
    optimal_cost: float,
    wrap_u: tuple[bool, ...] | list[bool] = (False, False),
    plant: Planar2R | None = None,
    output_space: OutputSpace | None = None,
    revisit_exclusion_steps: int = 4,
    revisit_threshold_q: float = 0.05,
    revisit_threshold_x: float = 0.05,
) -> PathQualityMetrics:
    """Compute length and Sprint Five quality metrics from sample sequences."""
    fk = plant if plant is not None else Planar2R()
    lengths = compute_path_metrics_from_trajectories(
        u_path,
        q_path,
        optimal_cost=optimal_cost,
        wrap_u=wrap_u,
        plant=fk,
        output_space=output_space,
    )
    u_arr = np.asarray(u_path, dtype=np.float64)
    q_arr = np.asarray(q_path, dtype=np.float64)
    x_arr = _cartesian_path(q_arr, fk)

    if u_arr.shape[0] == 0:
        raise ValueError("u_path must be non-empty")

    disp_u = float(wrapped_input_displacement(u_arr[0], u_arr[-1], wrap=wrap_u))
    if output_space is not None:
        disp_q = float(output_space.distance(q_arr[0], q_arr[-1]))
    else:
        disp_q = float(np.linalg.norm(q_arr[-1] - q_arr[0]))
    disp_x = float(np.linalg.norm(x_arr[-1] - x_arr[0]))

    r_u, def_u = _directness_ratio(lengths.path_length_u, disp_u)
    r_q, def_q = _directness_ratio(lengths.path_length_q, disp_q)
    r_x, def_x = _directness_ratio(lengths.path_length_x, disp_x)

    t_q = cumulative_turning(q_arr)
    t_x = cumulative_turning(x_arr)
    n_cross_q = count_self_intersections(q_arr)
    n_cross_x = count_self_intersections(x_arr)

    d_rev_q, n_rev_q = near_revisit_metrics(
        q_arr,
        exclusion_steps=revisit_exclusion_steps,
        threshold=revisit_threshold_q,
    )
    d_rev_x, n_rev_x = near_revisit_metrics(
        x_arr,
        exclusion_steps=revisit_exclusion_steps,
        threshold=revisit_threshold_x,
    )

    return PathQualityMetrics(
        n_path_edges=lengths.n_path_edges,
        path_length_u=lengths.path_length_u,
        path_length_q=lengths.path_length_q,
        path_length_x=lengths.path_length_x,
        optimal_cost=lengths.optimal_cost,
        directness_ratio_u=r_u,
        directness_ratio_q=r_q,
        directness_ratio_x=r_x,
        directness_defined_u=def_u,
        directness_defined_q=def_q,
        directness_defined_x=def_x,
        endpoint_displacement_u=disp_u,
        endpoint_displacement_q=disp_q,
        endpoint_displacement_x=disp_x,
        cumulative_turning_q=t_q,
        cumulative_turning_x=t_x,
        self_intersections_q=n_cross_q,
        self_intersections_x=n_cross_x,
        near_revisit_distance_q=d_rev_q,
        near_revisit_distance_x=d_rev_x,
        near_revisit_count_q=n_rev_q,
        near_revisit_count_x=n_rev_x,
        revisit_exclusion_steps=int(revisit_exclusion_steps),
        revisit_threshold_q=float(revisit_threshold_q),
        revisit_threshold_x=float(revisit_threshold_x),
    )


def compute_path_quality(
    graph: ConstrainedInputGraph,
    path: Sequence[int],
    *,
    optimal_cost: float,
    plant: Planar2R | None = None,
    revisit_exclusion_steps: int = 4,
    revisit_threshold_q: float = 0.05,
    revisit_threshold_x: float = 0.05,
) -> PathQualityMetrics:
    """Compute Sprint Five path-quality metrics for a node path."""
    nodes = [int(n) for n in path]
    if not nodes:
        raise ValueError("path must be non-empty")
    u_path = path_inputs(graph, nodes)
    q_path = path_outputs(graph, nodes)
    return compute_path_quality_from_trajectories(
        u_path,
        q_path,
        optimal_cost=optimal_cost,
        wrap_u=graph.grid.wrap,
        plant=plant,
        output_space=graph.output_space,
        revisit_exclusion_steps=revisit_exclusion_steps,
        revisit_threshold_q=revisit_threshold_q,
        revisit_threshold_x=revisit_threshold_x,
    )


def path_quality_null_fields() -> dict[str, Any]:
    """Trial-row null placeholders for unsolved paths."""
    return {
        "directness_ratio_u": None,
        "directness_ratio_q": None,
        "directness_ratio_x": None,
        "directness_defined_u": None,
        "directness_defined_q": None,
        "directness_defined_x": None,
        "endpoint_displacement_u": None,
        "endpoint_displacement_q": None,
        "endpoint_displacement_x": None,
        "cumulative_turning_q": None,
        "cumulative_turning_x": None,
        "self_intersections_q": None,
        "self_intersections_x": None,
        "near_revisit_distance_q": None,
        "near_revisit_distance_x": None,
        "near_revisit_count_q": None,
        "near_revisit_count_x": None,
    }


def attach_path_quality_fields(
    record: dict[str, Any],
    quality: PathQualityMetrics | None,
) -> None:
    """Write path-quality fields onto a trial record (mutates ``record``)."""
    if quality is None:
        record.update(path_quality_null_fields())
        return
    data = quality.to_dict()
    for key, value in data.items():
        if key in {
            "revisit_exclusion_steps",
            "revisit_threshold_q",
            "revisit_threshold_x",
        }:
            continue
        record[key] = value


def quality_config_metadata(config: Mapping[str, Any] | None) -> dict[str, Any]:
    """Serialize path-quality config + conventions for run metadata."""
    cfg = dict(config) if config is not None else {}
    return {
        "path_quality": {
            "revisit_exclusion_steps": int(cfg.get("revisit_exclusion_steps", 4)),
            "revisit_threshold_q": float(cfg.get("revisit_threshold_q", 0.05)),
            "revisit_threshold_x": float(cfg.get("revisit_threshold_x", 0.05)),
        },
        "conventions": PATH_QUALITY_CONVENTIONS,
        "path_metric_atol": PATH_METRIC_ATOL,
        "path_quality_atol": PATH_QUALITY_ATOL,
    }
