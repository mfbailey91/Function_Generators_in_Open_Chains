"""Regular periodic grids in input configuration space.

Version 1 search graphs are four-connected lattices over actuator angles.
Optional per-axis wrapping models full-cycle periodicity on S^1 factors.
Shared output limits and edge-interior validation are applied by
``ConstrainedInputGraph`` in ``validation.py`` (IM-009, IM-010).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class GridNode:
    """A discrete input-space sample.

    Attributes
    ----------
    node_id :
        Deterministic flat index ``i0 * n1 + i1``.
    indices :
        Integer lattice coordinates ``(i0, i1)``.
    coordinates :
        Configuration ``(u0, u1)`` in the configured axis ranges.
    """

    node_id: int
    indices: tuple[int, int]
    coordinates: tuple[float, float]


class PeriodicGrid2D:
    """Four-connected 2-D lattice with optional axis wrapping.

    Parameters
    ----------
    shape :
        Number of samples per axis ``(n0, n1)``. Each must be ``>= 2``.
    ranges :
        Closed sampling intervals ``((u0_min, u0_max), (u1_min, u1_max))``.
        Defaults to ``([0, 2 pi), [0, 2 pi))`` represented as
        ``((0, 2 pi), (0, 2 pi))`` with samples at
        ``u = lo + i * (hi - lo) / n`` for ``i = 0 .. n-1`` (endpoint ``hi``
        excluded so a full period is not double-counted when wrapping).
    wrap :
        Per-axis wrapping flags. When ``True``, the first and last samples on
        that axis are neighbors.
    """

    def __init__(
        self,
        shape: tuple[int, int],
        *,
        ranges: tuple[tuple[float, float], tuple[float, float]] | None = None,
        wrap: tuple[bool, bool] = (True, True),
    ) -> None:
        n0, n1 = int(shape[0]), int(shape[1])
        if n0 < 2 or n1 < 2:
            raise ValueError(f"shape entries must be >= 2, got {shape}")
        if ranges is None:
            two_pi = 2.0 * np.pi
            ranges = ((0.0, two_pi), (0.0, two_pi))
        r0 = (float(ranges[0][0]), float(ranges[0][1]))
        r1 = (float(ranges[1][0]), float(ranges[1][1]))
        if not np.isfinite(r0).all() or not np.isfinite(r1).all():
            raise ValueError("ranges must be finite")
        if r0[1] <= r0[0] or r1[1] <= r1[0]:
            raise ValueError("each range must satisfy max > min")
        if len(wrap) != 2:
            raise ValueError(f"wrap must have length 2, got {len(wrap)}")
        self._n0 = n0
        self._n1 = n1
        self._ranges = (r0, r1)
        self._wrap = (bool(wrap[0]), bool(wrap[1]))
        self._step0 = (r0[1] - r0[0]) / n0
        self._step1 = (r1[1] - r1[0]) / n1

    @property
    def shape(self) -> tuple[int, int]:
        """Sample counts ``(n0, n1)``."""
        return self._n0, self._n1

    @property
    def ranges(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Axis sampling intervals."""
        return self._ranges

    @property
    def wrap(self) -> tuple[bool, bool]:
        """Per-axis wrapping flags."""
        return self._wrap

    @property
    def steps(self) -> tuple[float, float]:
        """Sample spacing ``(du0, du1)``."""
        return self._step0, self._step1

    @property
    def node_count(self) -> int:
        """Total number of lattice nodes."""
        return self._n0 * self._n1

    def node_id(self, i0: int, i1: int) -> int:
        """Deterministic flat index for lattice coordinates."""
        self._check_indices(i0, i1)
        return i0 * self._n1 + i1

    def indices_from_id(self, node_id: int) -> tuple[int, int]:
        """Inverse of ``node_id``."""
        if node_id < 0 or node_id >= self.node_count:
            raise ValueError(f"node_id out of range: {node_id}")
        i0, i1 = divmod(int(node_id), self._n1)
        return i0, i1

    def coordinates(self, i0: int, i1: int) -> tuple[float, float]:
        """Configuration sample at lattice coordinates."""
        self._check_indices(i0, i1)
        u0 = self._ranges[0][0] + i0 * self._step0
        u1 = self._ranges[1][0] + i1 * self._step1
        return float(u0), float(u1)

    def node(self, i0: int, i1: int) -> GridNode:
        """Return the node record at lattice coordinates."""
        return GridNode(
            node_id=self.node_id(i0, i1),
            indices=(i0, i1),
            coordinates=self.coordinates(i0, i1),
        )

    def iter_nodes(self) -> Iterator[GridNode]:
        """Iterate all nodes in deterministic ``(i0, i1)`` order."""
        for i0 in range(self._n0):
            for i1 in range(self._n1):
                yield self.node(i0, i1)

    def coordinate_array(self) -> NDArray[np.floating]:
        """Stack all node coordinates, shape ``(node_count, 2)``."""
        out = np.empty((self.node_count, 2), dtype=np.float64)
        for node in self.iter_nodes():
            out[node.node_id, 0] = node.coordinates[0]
            out[node.node_id, 1] = node.coordinates[1]
        return out

    def neighbors(self, i0: int, i1: int) -> list[tuple[int, int]]:
        """Four-connected neighbor lattice coordinates.

        Order is deterministic: ``(+1,0), (-1,0), (0,+1), (0,-1)``, omitting
        missing non-wrapped edges.
        """
        self._check_indices(i0, i1)
        result: list[tuple[int, int]] = []
        for di0, di1 in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            j0, j1 = i0 + di0, i1 + di1
            nb = self._resolve_neighbor(j0, j1, axis0=di0 != 0)
            if nb is not None:
                result.append(nb)
        return result

    def iter_edges(self) -> Iterator[tuple[int, int]]:
        """Iterate undirected edges as sorted flat ``(node_id_a, node_id_b)``.

        Each undirected edge appears once with ``a < b``.
        """
        seen: set[tuple[int, int]] = set()
        for i0 in range(self._n0):
            for i1 in range(self._n1):
                a = self.node_id(i0, i1)
                for j0, j1 in self.neighbors(i0, i1):
                    b = self.node_id(j0, j1)
                    edge = (a, b) if a < b else (b, a)
                    if edge not in seen:
                        seen.add(edge)
                        yield edge

    def to_networkx(self) -> Any:
        """Build an undirected ``networkx.Graph`` for validation.

        Requires the optional ``networkx`` development dependency.
        """
        try:
            import networkx as nx  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "networkx is required for PeriodicGrid2D.to_networkx(); "
                "install with pip install 'inequality-mechanisms[dev]'"
            ) from exc
        g = nx.Graph()
        for node in self.iter_nodes():
            g.add_node(
                node.node_id,
                indices=node.indices,
                coordinates=node.coordinates,
            )
        g.add_edges_from(self.iter_edges())
        return g

    def _resolve_neighbor(
        self, j0: int, j1: int, *, axis0: bool
    ) -> tuple[int, int] | None:
        if axis0:
            if self._wrap[0]:
                j0 %= self._n0
            elif j0 < 0 or j0 >= self._n0:
                return None
            if j1 < 0 or j1 >= self._n1:
                return None
        else:
            if self._wrap[1]:
                j1 %= self._n1
            elif j1 < 0 or j1 >= self._n1:
                return None
            if j0 < 0 or j0 >= self._n0:
                return None
        return j0, j1

    def _check_indices(self, i0: int, i1: int) -> None:
        if i0 < 0 or i0 >= self._n0 or i1 < 0 or i1 >= self._n1:
            raise ValueError(
                f"indices ({i0}, {i1}) out of range for shape {self.shape}"
            )
