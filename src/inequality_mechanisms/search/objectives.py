"""Cost-and-heuristic planning objectives (S4-02).

A* must not silently reuse an unrelated heuristic. Resolve a named edge
cost with a compatible heuristic through :func:`resolve_planning_objective`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from inequality_mechanisms.graphs.costs import (
    KNOWN_COST_TYPES,
    EdgeCost,
    build_edge_cost,
)
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.search.core import _cached_outputs
from inequality_mechanisms.search.heuristics import (
    Heuristic,
    input_euclidean_heuristic,
    output_euclidean_heuristic,
    uniform_step_heuristic,
    zero_heuristic,
)

HeuristicName = Literal[
    "zero",
    "uniform_step",
    "input_euclidean",
    "output_euclidean",
]

# Compatible A* heuristics for each registered edge cost (excluding zero,
# which is always allowed).
_DEFAULT_HEURISTIC: dict[str, str] = {
    "uniform": "uniform_step",
    "input_euclidean": "input_euclidean",
    "output_euclidean": "output_euclidean",
}

_COMPATIBLE: dict[str, frozenset[str]] = {
    "uniform": frozenset({"uniform_step", "zero"}),
    "input_euclidean": frozenset({"input_euclidean", "zero"}),
    "output_euclidean": frozenset({"output_euclidean", "zero"}),
}


@dataclass(frozen=True, slots=True)
class PlanningObjective:
    """Resolved edge cost and compatible heuristic pair.

    Attributes
    ----------
    edge_cost :
        Nonnegative edge weight ``(u_id, v_id) -> float``.
    heuristic :
        Admissible cost-to-go estimate ``h(node_id)``.
    cost_name :
        Registry name of the edge metric.
    heuristic_name :
        Registry name of the heuristic.
    """

    edge_cost: EdgeCost
    heuristic: Heuristic
    cost_name: str
    heuristic_name: str


def default_heuristic_name(cost_name: str) -> str:
    """Return the default compatible A* heuristic for a known cost."""
    if cost_name not in _DEFAULT_HEURISTIC:
        return "zero"
    return _DEFAULT_HEURISTIC[cost_name]


def compatible_heuristic_names(cost_name: str) -> frozenset[str]:
    """Return allowed heuristic names for ``cost_name`` (always includes zero)."""
    if cost_name in _COMPATIBLE:
        return _COMPATIBLE[cost_name]
    # Unknown custom cost: zero unless an explicit compatible heuristic is
    # supplied by the caller (caller must pass heuristic_name="zero" or a
    # documented custom pair outside this table).
    return frozenset({"zero"})


def _build_heuristic(
    graph: ConstrainedInputGraph,
    goal: int,
    heuristic_name: str,
) -> Heuristic:
    name = str(heuristic_name)
    if name == "zero":
        return zero_heuristic
    if name == "uniform_step":
        return uniform_step_heuristic(graph, goal)
    if name == "input_euclidean":
        return input_euclidean_heuristic(graph, goal)
    if name == "output_euclidean":
        output_of = _cached_outputs(graph)
        q_goal = output_of(goal)
        return output_euclidean_heuristic(
            graph.mechanism,
            q_goal,
            output_of,
            output_space=graph.output_space,
        )
    raise ValueError(f"unknown heuristic name {name!r}")


def resolve_planning_objective(
    graph: ConstrainedInputGraph,
    goal: int,
    cost_name: str,
    heuristic_name: str | None = None,
) -> PlanningObjective:
    """Resolve a compatible ``(edge_cost, heuristic)`` pair from names.

    Parameters
    ----------
    graph :
        Physical input-state graph (held fixed across cost ablations).
    goal :
        Flat goal node id (used to anchor admissible heuristics).
    cost_name :
        Edge-cost registry name, or an unknown custom label.
    heuristic_name :
        Optional heuristic override. Defaults to the compatible A*
        heuristic for known costs, or ``zero`` for unknown costs.

    Returns
    -------
    PlanningObjective

    Raises
    ------
    ValueError
        If the requested heuristic is incompatible with the cost, or a
        known cost/heuristic name is invalid.
    """
    cost = str(cost_name)
    if cost in KNOWN_COST_TYPES:
        edge_cost = build_edge_cost(graph, cost)
        allowed = compatible_heuristic_names(cost)
        h_name = (
            default_heuristic_name(cost)
            if heuristic_name is None
            else str(heuristic_name)
        )
    else:
        # Unknown custom cost: refuse silent default heuristics.
        if heuristic_name is None:
            h_name = "zero"
        else:
            h_name = str(heuristic_name)
        allowed = frozenset({"zero"})
        if h_name != "zero":
            raise ValueError(
                f"unknown cost {cost!r} requires an explicit zero heuristic "
                f"or a caller-supplied compatible heuristic via "
                f"best_first_search; got heuristic={h_name!r}"
            )
        # Caller must supply edge_cost separately for unknown names; still
        # build a uniform placeholder only if they meant a typo — refuse.
        raise ValueError(
            f"unknown cost type {cost!r}; expected one of: "
            + ", ".join(sorted(KNOWN_COST_TYPES))
        )

    if h_name not in allowed:
        raise ValueError(
            f"heuristic {h_name!r} is incompatible with cost {cost!r}; "
            f"allowed: {', '.join(sorted(allowed))}"
        )

    return PlanningObjective(
        edge_cost=edge_cost,
        heuristic=_build_heuristic(graph, goal, h_name),
        cost_name=cost,
        heuristic_name=h_name,
    )
