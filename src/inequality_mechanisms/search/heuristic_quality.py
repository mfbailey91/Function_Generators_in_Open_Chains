"""Exact cost-to-go and heuristic-quality diagnostics (S4-04)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from inequality_mechanisms.graphs.costs import EdgeCost
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.search.cost_to_go import reverse_dijkstra
from inequality_mechanisms.search.heuristics import Heuristic


@dataclass(frozen=True, slots=True)
class HeuristicQualityReport:
    """Summary of heuristic error relative to exact ``h*``.

    Attributes
    ----------
    cost_name, heuristic_name :
        Objective labels.
    n_sampled :
        Number of labeled nodes included in aggregate statistics.
    sample_seed :
        Seed used for subsampling (``None`` if all reachable nodes used).
    mean_error, median_error, max_error :
        Statistics of ``e_h = h* - h`` on sampled nodes.
    mean_strength :
        Mean of ``r_h = h / h*`` where ``h* > 0``.
    mean_strength_on_path :
        Mean strength on the optimal path nodes (excluding undefined).
    mean_strength_expanded :
        Mean strength on expanded nodes when provided.
    admissible :
        Whether ``0 <= h(u) <= h*(u)`` held on every checked node.
    failure_reason :
        First admissibility violation message, else ``None``.
    """

    cost_name: str
    heuristic_name: str
    n_sampled: int
    sample_seed: int | None
    mean_error: float
    median_error: float
    max_error: float
    mean_strength: float
    mean_strength_on_path: float | None
    mean_strength_expanded: float | None
    admissible: bool
    failure_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable report."""
        return asdict(self)


def _finite_mean(values: Sequence[float]) -> float:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        return float("nan")
    return float(np.mean(arr))


def _strength(h_val: float, h_star: float) -> float | None:
    if not (math.isfinite(h_star) and h_star > 0.0):
        return None
    if not math.isfinite(h_val):
        return None
    return float(h_val / h_star)


def heuristic_quality_report(
    graph: ConstrainedInputGraph,
    goal: int,
    heuristic: Heuristic,
    *,
    edge_cost: EdgeCost | None = None,
    cost_name: str = "output_euclidean",
    heuristic_name: str = "output_euclidean",
    path: Sequence[int] | None = None,
    expanded_nodes: Sequence[int] | None = None,
    max_sample_nodes: int | None = None,
    sample_seed: int | None = None,
    atol: float = 1e-9,
) -> HeuristicQualityReport:
    """Compare ``h`` to exact reverse-Dijkstra ``h*`` on reachable nodes.

    Parameters
    ----------
    graph :
        Constrained input lattice.
    goal :
        Goal node used for reverse search.
    heuristic :
        Candidate A* heuristic.
    edge_cost :
        Edge weights matching the planning objective (default output
        Euclidean via reverse Dijkstra).
    cost_name, heuristic_name :
        Labels stored in the report.
    path, expanded_nodes :
        Optional node sets for strength summaries.
    max_sample_nodes :
        If set and smaller than the reachable labeled set, subsample
        deterministically under ``sample_seed``.
    sample_seed :
        RNG seed for subsampling; required when subsampling.
    atol :
        Admissibility tolerance for ``h <= h*``.

    Returns
    -------
    HeuristicQualityReport
    """
    ctg = reverse_dijkstra(graph, int(goal), edge_cost=edge_cost)
    labeled = [
        (int(nid), float(c))
        for nid, c in ctg.costs.items()
        if math.isfinite(float(c))
    ]
    labeled.sort(key=lambda item: item[0])

    used_seed: int | None = None
    if max_sample_nodes is not None and max_sample_nodes < len(labeled):
        if sample_seed is None:
            raise ValueError("sample_seed is required when max_sample_nodes is set")
        used_seed = int(sample_seed)
        rng = np.random.default_rng(used_seed)
        idx = rng.choice(len(labeled), size=int(max_sample_nodes), replace=False)
        labeled = [labeled[int(i)] for i in sorted(idx.tolist())]

    errors: list[float] = []
    strengths: list[float] = []
    admissible = True
    failure_reason: str | None = None

    for node_id, h_star in labeled:
        h_val = float(heuristic(node_id))
        if not math.isfinite(h_val) or h_val < -atol:
            admissible = False
            failure_reason = (
                f"heuristic non-finite or negative at node {node_id}: h={h_val}"
            )
            break
        if h_val > h_star + atol:
            admissible = False
            failure_reason = (
                f"heuristic inadmissible at node {node_id}: h={h_val} > C*={h_star}"
            )
            break
        errors.append(h_star - h_val)
        strength = _strength(h_val, h_star)
        if strength is not None:
            strengths.append(strength)

    def _mean_strength_on(nodes: Sequence[int] | None) -> float | None:
        if nodes is None:
            return None
        vals: list[float] = []
        cost_map: Mapping[int, float] = ctg.costs
        for nid in nodes:
            h_star = float(cost_map.get(int(nid), math.inf))
            if not math.isfinite(h_star):
                continue
            h_val = float(heuristic(int(nid)))
            strength = _strength(h_val, h_star)
            if strength is not None:
                vals.append(strength)
        if not vals:
            return None
        return _finite_mean(vals)

    err_arr = np.asarray(errors, dtype=np.float64)
    return HeuristicQualityReport(
        cost_name=str(cost_name),
        heuristic_name=str(heuristic_name),
        n_sampled=len(labeled),
        sample_seed=used_seed,
        mean_error=float(np.mean(err_arr)) if err_arr.size else float("nan"),
        median_error=float(np.median(err_arr)) if err_arr.size else float("nan"),
        max_error=float(np.max(err_arr)) if err_arr.size else float("nan"),
        mean_strength=_finite_mean(strengths) if strengths else float("nan"),
        mean_strength_on_path=_mean_strength_on(path),
        mean_strength_expanded=_mean_strength_on(expanded_nodes),
        admissible=admissible,
        failure_reason=failure_reason,
    )


def validate_heuristic_admissible(
    graph: ConstrainedInputGraph,
    goal: int,
    heuristic: Heuristic,
    *,
    edge_cost: EdgeCost | None = None,
    atol: float = 1e-9,
) -> str | None:
    """Return a failure reason if ``h`` exceeds exact cost-to-go, else ``None``."""
    report = heuristic_quality_report(
        graph,
        goal,
        heuristic,
        edge_cost=edge_cost,
        atol=atol,
    )
    return report.failure_reason
