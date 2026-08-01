"""Paired comparison metrics for Sprint V2.8 shared-Q studies."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.kinematics import Planar2R


def _path_edges(path: list[int] | tuple[int, ...]) -> set[tuple[int, int]]:
    edges: set[tuple[int, int]] = set()
    for a, b in zip(path[:-1], path[1:]):
        edges.add((int(a), int(b)) if int(a) <= int(b) else (int(b), int(a)))
    return edges


def output_path_overlap(
    path_a: list[int] | tuple[int, ...],
    path_b: list[int] | tuple[int, ...],
) -> dict[str, float]:
    """Return node/edge Jaccard overlap between two output paths."""
    nodes_a = set(int(n) for n in path_a)
    nodes_b = set(int(n) for n in path_b)
    edges_a = _path_edges(path_a)
    edges_b = _path_edges(path_b)
    node_union = nodes_a | nodes_b
    edge_union = edges_a | edges_b
    return {
        "node_jaccard": (
            float(len(nodes_a & nodes_b) / len(node_union)) if node_union else 1.0
        ),
        "edge_jaccard": (
            float(len(edges_a & edges_b) / len(edge_union)) if edge_union else 1.0
        ),
        "identical_path": bool(list(path_a) == list(path_b)),
    }


def cartesian_path_separation(
    q_path_a: NDArray[np.float64],
    q_path_b: NDArray[np.float64],
) -> dict[str, float | None]:
    """Compare planar-2R end-effector paths resampled to equal length."""
    if q_path_a.ndim != 2 or q_path_b.ndim != 2 or q_path_a.shape[1] != 2:
        return {
            "max_separation": None,
            "mean_separation": None,
            "length_a": None,
            "length_b": None,
            "detour_ratio": None,
        }
    fk = Planar2R()
    xa = np.vstack([fk.forward(q) for q in q_path_a])
    xb = np.vstack([fk.forward(q) for q in q_path_b])
    n = max(len(xa), len(xb), 2)
    ta = np.linspace(0.0, 1.0, len(xa))
    tb = np.linspace(0.0, 1.0, len(xb))
    t = np.linspace(0.0, 1.0, n)
    xa_i = np.column_stack([np.interp(t, ta, xa[:, i]) for i in range(2)])
    xb_i = np.column_stack([np.interp(t, tb, xb[:, i]) for i in range(2)])
    sep = np.linalg.norm(xa_i - xb_i, axis=1)
    len_a = (
        float(np.sum(np.linalg.norm(np.diff(xa, axis=0), axis=1)))
        if len(xa) > 1
        else 0.0
    )
    len_b = (
        float(np.sum(np.linalg.norm(np.diff(xb, axis=0), axis=1)))
        if len(xb) > 1
        else 0.0
    )
    detour = None
    if len_a > 0.0 and len_b > 0.0:
        detour = float(max(len_a, len_b) / min(len_a, len_b))
    return {
        "max_separation": float(np.max(sep)) if sep.size else 0.0,
        "mean_separation": float(np.mean(sep)) if sep.size else 0.0,
        "length_a": len_a,
        "length_b": len_b,
        "detour_ratio": detour,
    }


def compare_paired_rows(
    row_a: dict[str, Any],
    row_b: dict[str, Any],
    *,
    q_path_a: NDArray[np.float64] | None = None,
    q_path_b: NDArray[np.float64] | None = None,
) -> dict[str, Any]:
    """Build one paired comparison record from two trial rows."""
    path_a = tuple(row_a.get("path_node_ids") or ())
    path_b = tuple(row_b.get("path_node_ids") or ())
    overlap = output_path_overlap(path_a, path_b)
    cost_a = row_a.get("optimal_cost")
    cost_b = row_b.get("optimal_cost")
    exp_a = row_a.get("n_expanded")
    exp_b = row_b.get("n_expanded")
    lu_a = row_a.get("path_length_u")
    lu_b = row_b.get("path_length_u")
    alpha = row_a.get("alpha")
    null_ok = None
    if alpha == 1.0 or alpha == 1:
        null_ok = (
            row_a.get("found") == row_b.get("found")
            and path_a == path_b
            and isinstance(cost_a, (int, float))
            and isinstance(cost_b, (int, float))
            and math.isfinite(float(cost_a))
            and math.isfinite(float(cost_b))
            and abs(float(cost_a) - float(cost_b)) <= 1e-12
            and exp_a == exp_b
        )
    cart = (
        cartesian_path_separation(q_path_a, q_path_b)
        if q_path_a is not None and q_path_b is not None
        else {
            "max_separation": None,
            "mean_separation": None,
            "length_a": None,
            "length_b": None,
            "detour_ratio": None,
        }
    )
    actuator_ratio = None
    if (
        isinstance(lu_a, (int, float))
        and isinstance(lu_b, (int, float))
        and float(lu_b) != 0.0
    ):
        actuator_ratio = float(lu_a) / float(lu_b)

    return {
        "pair_id": row_a.get("pair_id"),
        "task_set_id": row_a.get("task_set_id"),
        "alpha": alpha,
        "algorithm": row_a.get("algorithm"),
        "mechanism_a": row_a.get("mechanism_id"),
        "mechanism_b": row_b.get("mechanism_id"),
        "found_a": row_a.get("found"),
        "found_b": row_b.get("found"),
        "cost_a": cost_a,
        "cost_b": cost_b,
        "cost_delta": (
            float(cost_a) - float(cost_b)
            if isinstance(cost_a, (int, float)) and isinstance(cost_b, (int, float))
            else None
        ),
        "n_expanded_a": exp_a,
        "n_expanded_b": exp_b,
        "expansion_delta": (
            int(exp_a) - int(exp_b)
            if isinstance(exp_a, int) and isinstance(exp_b, int)
            else None
        ),
        "path_length_u_a": lu_a,
        "path_length_u_b": lu_b,
        "actuator_travel_ratio": actuator_ratio,
        "path_length_q_a": row_a.get("path_length_q"),
        "path_length_q_b": row_b.get("path_length_q"),
        "path_length_x_a": row_a.get("path_length_x"),
        "path_length_x_b": row_b.get("path_length_x"),
        "null_control_equal": null_ok,
        **overlap,
        **cart,
        "cost_d_q_a": row_a.get("cost_d_q"),
        "cost_d_q_b": row_b.get("cost_d_q"),
        "cost_d_u_a": row_a.get("cost_d_u"),
        "cost_d_u_b": row_b.get("cost_d_u"),
        "cost_norm_q_a": row_a.get("cost_norm_q"),
        "cost_norm_q_b": row_b.get("cost_norm_q"),
        "cost_norm_u_a": row_a.get("cost_norm_u"),
        "cost_norm_u_b": row_b.get("cost_norm_u"),
    }


def divergence_onset_by_alpha(
    comparisons: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return the largest alpha at which paired paths first diverge."""
    by_key: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for row in comparisons:
        key = (row.get("pair_id"), row.get("task_set_id"))
        by_key.setdefault(key, []).append(row)
    onset: dict[str, Any] = {}
    for (pair_id, task_set_id), rows in by_key.items():
        ordered = sorted(
            rows,
            key=lambda r: float(r.get("alpha") if r.get("alpha") is not None else -1.0),
            reverse=True,
        )
        first = None
        for row in ordered:
            if not row.get("identical_path", True):
                first = row.get("alpha")
                break
        onset[f"{pair_id}:{task_set_id}"] = first
    return onset
