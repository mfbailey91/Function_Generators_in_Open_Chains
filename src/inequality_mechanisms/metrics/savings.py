"""A* savings relative to Dijkstra (S4-07)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def astar_savings(n_dijkstra: int, n_astar: int) -> float:
    """Return ``S_A = 1 - N_A* / N_Dijkstra``.

    Parameters
    ----------
    n_dijkstra, n_astar :
        Expansion counts (must be positive for a defined ratio).

    Returns
    -------
    float

    Raises
    ------
    ValueError
        If ``n_dijkstra <= 0``.
    """
    if int(n_dijkstra) <= 0:
        raise ValueError(f"n_dijkstra must be > 0, got {n_dijkstra}")
    return 1.0 - float(n_astar) / float(n_dijkstra)


def astar_expansion_delta(n_dijkstra: int, n_astar: int) -> int:
    """Return ``ΔN_A = N_Dijkstra - N_A*``."""
    return int(n_dijkstra) - int(n_astar)


def _pair_key(row: Mapping[str, Any]) -> tuple[int, str, str]:
    return (
        int(row["trial_index"]),
        str(row["mechanism"]),
        str(row.get("cost_type", "output_euclidean")),
    )


def compute_savings_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build one savings record per matched (trial, mechanism, cost) pair.

    Requires both Dijkstra and A* found rows for the same key.
    """
    by_key: dict[tuple[int, str, str], dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        if not row.get("found"):
            continue
        algo = str(row["algorithm"])
        if algo not in ("dijkstra", "astar"):
            continue
        by_key.setdefault(_pair_key(row), {})[algo] = row

    out: list[dict[str, Any]] = []
    for key, pair in sorted(by_key.items()):
        d = pair.get("dijkstra")
        a = pair.get("astar")
        if d is None or a is None:
            continue
        n_d = int(d["n_expanded"])
        n_a = int(a["n_expanded"])
        if n_d <= 0:
            continue
        s_a = astar_savings(n_d, n_a)
        hq = a.get("heuristic_quality") if isinstance(a.get("heuristic_quality"), dict) else {}
        mean_strength = hq.get("mean_strength") if hq else a.get("mean_heuristic_strength")
        out.append(
            {
                "trial_index": key[0],
                "mechanism": key[1],
                "cost_type": key[2],
                "n_expanded_dijkstra": n_d,
                "n_expanded_astar": n_a,
                "s_a": float(s_a),
                "delta_n_a": astar_expansion_delta(n_d, n_a),
                "path_length_u": a.get("path_length_u", d.get("path_length_u")),
                "path_length_q": a.get("path_length_q", d.get("path_length_q")),
                "path_length_x": a.get("path_length_x", d.get("path_length_x")),
                "optimal_cost": a.get("optimal_cost", d.get("optimal_cost")),
                "edge_cost_variance": d.get("edge_cost_variance"),
                "beta": d.get("beta"),
                "mean_heuristic_strength": mean_strength,
                "rho_expanded_dijkstra": d.get("rho_expanded"),
                "rho_expanded_astar": a.get("rho_expanded"),
                "runtime_dijkstra": d.get("runtime_s"),
                "runtime_astar": a.get("runtime_s"),
            }
        )
    return out


def summarize_savings(savings_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate mean/median savings by mechanism and cost type."""
    groups: dict[str, list[float]] = {}
    for row in savings_rows:
        label = f"{row['mechanism']}|{row['cost_type']}"
        groups.setdefault(label, []).append(float(row["s_a"]))

    by_group: dict[str, dict[str, Any]] = {}
    for label, vals in sorted(groups.items()):
        mech, cost = label.split("|", 1)
        by_group[label] = {
            "mechanism": mech,
            "cost_type": cost,
            "n_pairs": len(vals),
            "mean_s_a": float(sum(vals) / len(vals)),
            "median_s_a": float(sorted(vals)[len(vals) // 2]),
        }
    return {"by_group": by_group, "n_pairs": len(savings_rows)}
