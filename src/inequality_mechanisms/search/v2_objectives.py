"""Version 2 objective registry for ``EmbeddedPlanningGraph`` (Sprint V2.4, V2-404).

Independent of ``search/objectives.py`` (Version 1's ``ConstrainedInputGraph``
registry): Version 2 costs and heuristics read ``q_state`` / ``u_state`` from
an :class:`~inequality_mechanisms.graphs.embedded.EmbeddedPlanningGraph`
directly instead of a mechanism's cached forward map. As with the Version 1
registry, A* must never reuse a heuristic built for an unrelated metric;
:func:`resolve_v2_objective` only allows the documented compatible pairs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.search.protocol import EdgeCost, Heuristic


class _V2GraphLike(Protocol):
    """Structural protocol for objective graphs (base or query overlay)."""

    branch: Any
    topology: Any

    def q_state(self, node_id: int) -> NDArray[np.float64]: ...

    def u_state(self, node_id: int) -> NDArray[np.float64]: ...

    def edge_trace(self, a: int, b: int, n_samples: int = 17) -> Any: ...

V2CostName = Literal[
    "uniform",
    "output_euclidean",
    "input_euclidean",
    "actuator_travel",
    "gain_resolution",
]
V2HeuristicName = Literal["zero", "uniform_step", "output_euclidean", "input_euclidean"]

KNOWN_V2_COST_TYPES: frozenset[str] = frozenset(
    {
        "uniform",
        "output_euclidean",
        "input_euclidean",
        "actuator_travel",
        "gain_resolution",
    }
)

#: Default compatible A* heuristic for each known Version 2 cost name.
_DEFAULT_HEURISTIC: dict[str, str] = {
    "uniform": "uniform_step",
    "output_euclidean": "output_euclidean",
    "input_euclidean": "input_euclidean",
    "actuator_travel": "input_euclidean",
    "gain_resolution": "zero",
}

#: Allowed heuristic names for each cost name (``zero`` always allowed).
_COMPATIBLE: dict[str, frozenset[str]] = {
    "uniform": frozenset({"uniform_step", "zero"}),
    "output_euclidean": frozenset({"output_euclidean", "zero"}),
    "input_euclidean": frozenset({"input_euclidean", "zero"}),
    "actuator_travel": frozenset({"input_euclidean", "zero"}),
    "gain_resolution": frozenset({"zero"}),
}


def zero_heuristic_v2(_node_id: int) -> float:
    """Dijkstra heuristic ``h ≡ 0``."""
    return 0.0


def uniform_edge_cost_v2(_a: int, _b: int) -> float:
    """Unit hop cost, one per traversed edge."""
    return 1.0


def output_euclidean_edge_cost(graph: _V2GraphLike) -> EdgeCost:
    """Build ``c(a, b) = d_Q(q_a, q_b)`` using the branch's ``OutputSpace``."""
    output_space = graph.branch.output_space

    def cost(a: int, b: int) -> float:
        return output_space.distance(graph.q_state(a), graph.q_state(b))

    return cost


def input_euclidean_edge_cost(graph: _V2GraphLike) -> EdgeCost:
    """Build ``c(a, b) = ||u_b - u_a||`` (Version 2 branches never wrap)."""

    def cost(a: int, b: int) -> float:
        return float(np.linalg.norm(graph.u_state(b) - graph.u_state(a)))

    return cost


def actuator_travel_edge_cost(graph: _V2GraphLike) -> EdgeCost:
    """Actuator travel objective on Q-state graphs (alias of input Euclidean).

    This is intentionally the same metric as ``input_euclidean`` but allows
    experiments to label the scientific intent explicitly.
    """

    return input_euclidean_edge_cost(graph)


def gain_resolution_edge_cost(
    graph: _V2GraphLike, *, edge_n_samples: int = 17
) -> EdgeCost:
    """A narrow, certification-friendly gain/resolution exposure cost.

    The cost is computed as a best-effort, nonnegative quadrature over an
    edge's Version-2 trace:

    - local gain magnitude is estimated from the diagonal of the branch
      Jacobian ``J_g(u)`` at each trace sample;
    - the edge cost accumulates ``||dq|| * (1/|gain|)`` across consecutive
      trace samples where the trace is valid.

    The heuristic for A* is kept at zero (V2-409 / V2-601: admissibility is
    not assumed).
    """

    eps = 1e-12
    branch = graph.branch

    def cost(a: int, b: int) -> float:
        trace = graph.edge_trace(a, b, n_samples=edge_n_samples)
        valid = trace.branch_valid
        if not np.any(valid):
            return 0.0

        total = 0.0
        for k in range(edge_n_samples - 1):
            if not (bool(valid[k]) and bool(valid[k + 1])):
                continue
            q0 = trace.q[k]
            q1 = trace.q[k + 1]
            dq_norm = float(np.linalg.norm(q1 - q0))
            if dq_norm <= 0.0:
                continue
            u_k = trace.u[k]
            # operating branches are certified axis-separable; treat diagonal
            # entries as per-axis gains.
            J = branch.jacobian(u_k)
            diag = np.diag(J)
            gain_abs = float(np.min(np.abs(diag)))
            denom = max(gain_abs, eps)
            total += dq_norm / denom

        if not np.isfinite(total) or total < 0.0:
            # Non-negativity + finite invariant; fall back to zero rather
            # than breaking search.
            return 0.0
        return float(total)

    return cost


def output_euclidean_heuristic_v2(graph: _V2GraphLike, goal: int) -> Heuristic:
    """Build ``h(n) = d_Q(q_n, q_goal)``; admissible/consistent for output cost."""
    output_space = graph.branch.output_space
    q_goal = graph.q_state(goal)

    def h(node_id: int) -> float:
        return output_space.distance(graph.q_state(node_id), q_goal)

    return h


def input_euclidean_heuristic_v2(graph: _V2GraphLike, goal: int) -> Heuristic:
    """Build ``h(n) = ||u_n - u_goal||``; admissible/consistent for input cost."""
    u_goal = graph.u_state(goal)

    def h(node_id: int) -> float:
        return float(np.linalg.norm(graph.u_state(node_id) - u_goal))

    return h


def uniform_step_heuristic_v2(graph: _V2GraphLike, goal: int) -> Heuristic:
    """Admissible lattice Manhattan lower bound on hop count (unit edge cost).

    ``TensorGridTopology`` connects lattice indices that differ by one step
    on a single axis, so the index-space Manhattan distance to the goal is
    a valid lower bound on the number of edges to reach it, even though
    some neighbors may be invalid and force a longer detour.
    """
    goal_index = graph.topology.index_from_id(goal)

    def h(node_id: int) -> float:
        idx = graph.topology.index_from_id(node_id)
        return float(sum(abs(int(i) - int(g)) for i, g in zip(idx, goal_index)))

    return h


def build_v2_edge_cost(graph: _V2GraphLike, cost_name: str) -> EdgeCost:
    """Return the named Version 2 edge cost bound to ``graph``.

    Raises
    ------
    ValueError
        If ``cost_name`` is not a known Version 2 cost.
    """
    name = str(cost_name)
    if name == "uniform":
        return uniform_edge_cost_v2
    if name == "output_euclidean":
        return output_euclidean_edge_cost(graph)
    if name == "input_euclidean":
        return input_euclidean_edge_cost(graph)
    if name == "actuator_travel":
        return actuator_travel_edge_cost(graph)
    if name == "gain_resolution":
        return gain_resolution_edge_cost(graph)
    raise ValueError(
        f"unknown Version 2 cost {name!r}; expected one of "
        + ", ".join(sorted(KNOWN_V2_COST_TYPES))
    )


def default_v2_heuristic_name(cost_name: str) -> str:
    """Return the default compatible A* heuristic for a known Version 2 cost."""
    if cost_name not in _DEFAULT_HEURISTIC:
        raise ValueError(f"unknown Version 2 cost {cost_name!r}")
    return _DEFAULT_HEURISTIC[cost_name]


def compatible_v2_heuristic_names(cost_name: str) -> frozenset[str]:
    """Return allowed heuristic names for ``cost_name`` (always includes zero)."""
    if cost_name not in _COMPATIBLE:
        raise ValueError(f"unknown Version 2 cost {cost_name!r}")
    return _COMPATIBLE[cost_name]


def _build_v2_heuristic(
    graph: _V2GraphLike, goal: int, heuristic_name: str
) -> Heuristic:
    name = str(heuristic_name)
    if name == "zero":
        return zero_heuristic_v2
    if name == "uniform_step":
        return uniform_step_heuristic_v2(graph, goal)
    if name == "output_euclidean":
        return output_euclidean_heuristic_v2(graph, goal)
    if name == "input_euclidean":
        return input_euclidean_heuristic_v2(graph, goal)
    raise ValueError(f"unknown Version 2 heuristic name {name!r}")


@dataclass(frozen=True, slots=True)
class V2PlanningObjective:
    """Resolved edge cost and compatible heuristic pair for Version 2.

    Attributes
    ----------
    edge_cost :
        Nonnegative edge weight ``(u_id, v_id) -> float``.
    heuristic :
        Admissible cost-to-go estimate ``h(node_id)`` anchored at ``goal``.
    cost_name, heuristic_name :
        Registry names of the resolved metric and heuristic.
    """

    edge_cost: EdgeCost
    heuristic: Heuristic
    cost_name: str
    heuristic_name: str


def resolve_v2_objective(
    graph: _V2GraphLike,
    goal: int,
    cost_name: str,
    heuristic_name: str | None = None,
) -> V2PlanningObjective:
    """Resolve a compatible ``(edge_cost, heuristic)`` pair from names.

    Parameters
    ----------
    graph :
        Embedded planning graph the cost and heuristic are bound to.
    goal :
        Flat goal node id (used to anchor admissible heuristics).
    cost_name :
        Known Version 2 edge-cost registry name.
    heuristic_name :
        Optional heuristic override. Defaults to the compatible A*
        heuristic for ``cost_name``.

    Returns
    -------
    V2PlanningObjective

    Raises
    ------
    ValueError
        If ``cost_name`` is unknown, or the requested heuristic is
        incompatible with it (A* must never silently reuse a heuristic
        built for a different metric).
    """
    cost = str(cost_name)
    if cost not in KNOWN_V2_COST_TYPES:
        raise ValueError(
            f"unknown Version 2 cost {cost!r}; expected one of "
            + ", ".join(sorted(KNOWN_V2_COST_TYPES))
        )
    edge_cost = build_v2_edge_cost(graph, cost)
    allowed = compatible_v2_heuristic_names(cost)
    h_name = (
        default_v2_heuristic_name(cost)
        if heuristic_name is None
        else str(heuristic_name)
    )
    if h_name not in allowed:
        raise ValueError(
            f"heuristic {h_name!r} is incompatible with cost {cost!r}; "
            f"allowed: {', '.join(sorted(allowed))}"
        )
    heuristic = _build_v2_heuristic(graph, goal, h_name)
    return V2PlanningObjective(
        edge_cost=edge_cost,
        heuristic=heuristic,
        cost_name=cost,
        heuristic_name=h_name,
    )
