"""Equal-cost Dijkstra vs A* path-degeneracy comparison (S5-07)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.visualization.paths import path_inputs, path_outputs

# Documented heap tie-break (ADR-005): (f, node_id, g).
TIE_BREAKING_POLICY = "heap_key=(f, node_id, g); deterministic node_id order"

_SECONDARY_FIELDS = (
    "n_path_edges",
    "path_length_u",
    "path_length_q",
    "path_length_x",
    "directness_ratio_q",
    "directness_ratio_x",
    "cumulative_turning_q",
    "cumulative_turning_x",
    "self_intersections_q",
    "self_intersections_x",
    "near_revisit_distance_q",
    "near_revisit_distance_x",
)


def _path_arrays(
    graph: Any,
    path: Sequence[int],
    *,
    plant: Planar2R | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    nodes = [int(n) for n in path]
    u = path_inputs(graph, nodes)
    q = path_outputs(graph, nodes)
    fk = plant if plant is not None else Planar2R()
    x = np.vstack([fk.forward(qi) for qi in q])
    return u, q, x


def compare_equal_cost_pair(
    dijkstra_row: Mapping[str, Any],
    astar_row: Mapping[str, Any],
    *,
    graph: Any | None = None,
    cost_atol: float = 1e-9,
    coord_atol: float = 1e-9,
) -> dict[str, Any]:
    """Compare one matched Dijkstra / A* cell for secondary path quality.

    Path identity uses private ``_path`` when present; otherwise falls back to
    scalar field equality only for cost agreement.
    """
    d_cost = dijkstra_row.get("optimal_cost")
    a_cost = astar_row.get("optimal_cost")
    same_cost = (
        d_cost is not None
        and a_cost is not None
        and np.isfinite(float(d_cost))
        and np.isfinite(float(a_cost))
        and abs(float(d_cost) - float(a_cost)) <= cost_atol
    )
    d_path = list(dijkstra_row.get("_path") or [])
    a_path = list(astar_row.get("_path") or [])
    same_node = bool(d_path) and d_path == a_path

    same_output = False
    same_cartesian = False
    if graph is not None and d_path and a_path:
        _, q_d, x_d = _path_arrays(graph, d_path)
        _, q_a, x_a = _path_arrays(graph, a_path)
        same_output = q_d.shape == q_a.shape and np.allclose(
            q_d, q_a, atol=coord_atol, rtol=0.0
        )
        same_cartesian = x_d.shape == x_a.shape and np.allclose(
            x_d, x_a, atol=coord_atol, rtol=0.0
        )
    elif same_node:
        same_output = True
        same_cartesian = True

    out: dict[str, Any] = {
        "trial_index": dijkstra_row.get("trial_index"),
        "mechanism": dijkstra_row.get("mechanism"),
        "cost_type": dijkstra_row.get("cost_type"),
        "same_optimal_cost": bool(same_cost),
        "same_node_path": bool(same_node),
        "same_output_path": bool(same_output),
        "same_cartesian_path": bool(same_cartesian),
        "tie_breaking_policy": TIE_BREAKING_POLICY,
        "dijkstra_optimal_cost": d_cost,
        "astar_optimal_cost": a_cost,
        "secondary_deltas": {},
    }
    if same_cost and not same_node:
        deltas: dict[str, Any] = {}
        for field in _SECONDARY_FIELDS:
            dv = dijkstra_row.get(field)
            av = astar_row.get(field)
            if dv is None or av is None:
                deltas[field] = None
                continue
            try:
                deltas[field] = float(av) - float(dv)
            except (TypeError, ValueError):
                deltas[field] = None
        out["secondary_deltas"] = deltas
    return out


def compare_equal_cost_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    graphs_by_key: Mapping[tuple[Any, ...], Any] | None = None,
    cost_atol: float = 1e-9,
) -> dict[str, Any]:
    """Build the equal-cost path-degeneracy report for a factorial run.

    Parameters
    ----------
    rows :
        Trial rows including private ``_path`` when available.
    graphs_by_key :
        Optional map ``(trial_index, mechanism) -> ConstrainedInputGraph``
        for projected path identity checks.
    """
    by_key: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        if not row.get("found"):
            continue
        key = (
            int(row["trial_index"]),
            str(row["mechanism"]),
            str(row.get("cost_type", "")),
        )
        by_key.setdefault(key, {})[str(row["algorithm"])] = row

    comparisons: list[dict[str, Any]] = []
    n_same_cost = 0
    n_same_path = 0
    n_diff_path = 0
    by_cost_type: dict[str, dict[str, int]] = {}

    for key, pair in sorted(by_key.items()):
        if "dijkstra" not in pair or "astar" not in pair:
            continue
        trial_index, mechanism, cost_type = key
        graph = None
        if graphs_by_key is not None:
            graph = graphs_by_key.get((trial_index, mechanism))
        cmp = compare_equal_cost_pair(
            pair["dijkstra"],
            pair["astar"],
            graph=graph,
            cost_atol=cost_atol,
        )
        comparisons.append(cmp)
        bucket = by_cost_type.setdefault(
            cost_type,
            {
                "n_pairs": 0,
                "n_same_optimal_cost": 0,
                "n_same_node_path": 0,
                "n_diff_node_path_same_cost": 0,
            },
        )
        bucket["n_pairs"] += 1
        if cmp["same_optimal_cost"]:
            n_same_cost += 1
            bucket["n_same_optimal_cost"] += 1
            if cmp["same_node_path"]:
                n_same_path += 1
                bucket["n_same_node_path"] += 1
            else:
                n_diff_path += 1
                bucket["n_diff_node_path_same_cost"] += 1

    return {
        "tie_breaking_policy": TIE_BREAKING_POLICY,
        "cost_atol": cost_atol,
        "n_matched_pairs": len(comparisons),
        "n_same_optimal_cost": n_same_cost,
        "n_same_node_path": n_same_path,
        "n_diff_node_path_same_cost": n_diff_path,
        "by_cost_type": by_cost_type,
        "comparisons": comparisons,
    }


def equal_cost_summary_csv(report: Mapping[str, Any]) -> str:
    """CSV summary of equal-cost path-degeneracy counts by cost type."""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "cost_type",
            "n_pairs",
            "n_same_optimal_cost",
            "n_same_node_path",
            "n_diff_node_path_same_cost",
        ],
    )
    writer.writeheader()
    for cost_type, stats in sorted(report.get("by_cost_type", {}).items()):
        writer.writerow({"cost_type": cost_type, **stats})
    return buf.getvalue()
