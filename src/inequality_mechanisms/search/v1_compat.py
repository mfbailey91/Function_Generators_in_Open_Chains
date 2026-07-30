"""Version 1 helpers bridging ``ConstrainedInputGraph`` to the generic core.

Sprint V2.1 removes Version 1 graph coupling from ``search/core.py``. The
helpers below reconstruct the pre-refactor default behavior (implicit output
Euclidean edge cost, cached canonical outputs by node id) for callers that
still hand a ``ConstrainedInputGraph`` to Dijkstra, A*, or reverse Dijkstra.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.graphs.costs import output_euclidean_edge_cost
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.search.protocol import EdgeCost


def resolve_v1_default_edge_cost(graph: ConstrainedInputGraph) -> EdgeCost:
    """Return the Version 1 default output Euclidean edge cost for ``graph``.

    Equivalent to the edge cost that ``best_first_search`` used to build
    implicitly (when ``edge_cost is None``) before Sprint V2.1 made
    ``edge_cost`` a required keyword argument at the generic search
    boundary. Version 1 public entry points (:func:`dijkstra`, :func:`astar`,
    :func:`reverse_dijkstra`) resolve this default themselves and pass it
    through explicitly.

    Parameters
    ----------
    graph :
        Constrained input lattice owning the shared ``OutputSpace``.

    Returns
    -------
    callable
        ``(u_id, v_id) -> float`` edge weight, ``d_Q(g(u_a), g(u_b))``.
    """
    return output_euclidean_edge_cost(graph)


def _cached_outputs(
    graph: ConstrainedInputGraph,
) -> Callable[[int], NDArray[np.floating]]:
    """Lazily cache canonicalized ``g(u)`` by flat node id."""
    cache: dict[int, NDArray[np.floating]] = {}

    def output_of(node_id: int) -> NDArray[np.floating]:
        cached = cache.get(node_id)
        if cached is not None:
            return cached
        coords = graph.grid.coordinates(*graph.grid.indices_from_id(node_id))
        q = graph.output(coords)
        cache[node_id] = q
        return q

    return output_of
