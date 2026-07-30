"""Uniform output-space lattice for the Sprint Four monotonic control (S4-11).

Node identity on this graph is a regular sample in ``Q``. Each valid node
attaches the unique crank preimage ``u = g^{-1}(q)`` inside a monotonic
sector. This is an experimental control only; ADR-001 still governs the
physical search representation.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.graphs.grid import GridNode, PeriodicGrid2D
from inequality_mechanisms.graphs.validation import edge_is_valid
from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars
from inequality_mechanisms.mechanisms.monotonic import unique_inverse_output
from inequality_mechanisms.spaces.limits import OutputJointLimits
from inequality_mechanisms.spaces.output_space import OutputSpace

_DEFAULT_EDGE_SAMPLES = 17


class MonotonicOutputGraph:
    """Four-connected regular ``Q`` lattice with unique attached ``u``.

    Lattice coordinates are output configurations. Search APIs that expect a
    ``ConstrainedInputGraph`` duck-type against ``grid``, ``neighbors``,
    ``output``, and ``output_displacement``; path metrics must use
    :meth:`attached_u` for ``L_U``.
    """

    def __init__(
        self,
        grid: PeriodicGrid2D,
        mechanism: IndependentFourBars,
        limits: OutputJointLimits,
        *,
        u_ranges: tuple[tuple[float, float], tuple[float, float]],
        edge_samples: int = _DEFAULT_EDGE_SAMPLES,
        output_space: OutputSpace | None = None,
        inverse_atol: float = 1e-6,
    ) -> None:
        if not isinstance(mechanism, IndependentFourBars):
            raise TypeError("mechanism must be IndependentFourBars")
        if mechanism.input_dim != 2 or mechanism.output_dim != 2:
            raise ValueError("Version 1 Q-grid requires input_dim=output_dim=2")
        if limits.dim != 2:
            raise ValueError(f"limits.dim must be 2, got {limits.dim}")
        if edge_samples < 2:
            raise ValueError(f"edge_samples must be >= 2, got {edge_samples}")
        if any(grid.wrap):
            raise ValueError("monotonic Q-grid requires wrap=(False, False)")

        space = OutputSpace.from_limits(limits) if output_space is None else output_space
        self._grid = grid
        self._mechanism = mechanism
        self._limits = limits
        self._output_space = space
        self._edge_samples = int(edge_samples)
        self._u_ranges = (
            (float(u_ranges[0][0]), float(u_ranges[0][1])),
            (float(u_ranges[1][0]), float(u_ranges[1][1])),
        )
        self._inverse_atol = float(inverse_atol)
        self._attached_u = np.full((grid.node_count, 2), np.nan, dtype=np.float64)
        self._node_valid = np.zeros(grid.node_count, dtype=bool)

        for node in grid.iter_nodes():
            q = np.asarray(node.coordinates, dtype=np.float64)
            if not limits.contains(q):
                continue
            try:
                u = unique_inverse_output(
                    mechanism,
                    q,
                    u_ranges=self._u_ranges,
                    atol=self._inverse_atol,
                )
            except ValueError:
                continue
            # Lattice q is already the chart sample; unique_inverse verified
            # g(u) ≈ q. Require the chart point itself inside shared limits.
            q_can = space.canonicalize(q)
            if not limits.contains(q_can):
                continue
            self._attached_u[node.node_id] = u
            self._node_valid[node.node_id] = True

    @property
    def grid(self) -> PeriodicGrid2D:
        """Underlying regular output lattice."""
        return self._grid

    @property
    def mechanism(self) -> IndependentFourBars:
        """Mechanism providing ``g`` and inverses."""
        return self._mechanism

    @property
    def limits(self) -> OutputJointLimits:
        """Shared output joint limits."""
        return self._limits

    @property
    def output_space(self) -> OutputSpace:
        """Shared output chart."""
        return self._output_space

    @property
    def edge_samples(self) -> int:
        """Sample count for U-segment edge checks."""
        return self._edge_samples

    @property
    def u_ranges(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Monotonic crank box used for unique inverses."""
        return self._u_ranges

    @property
    def valid_node_count(self) -> int:
        """Number of lattice nodes with a unique attached preimage."""
        return int(np.count_nonzero(self._node_valid))

    def attached_u(self, node_id: int) -> NDArray[np.floating]:
        """Return the unique crank preimage attached to a valid Q-node."""
        if not self.node_is_valid_id(node_id):
            raise ValueError(f"node {node_id} is not a valid Q-grid node")
        return self._attached_u[int(node_id)].copy()

    def node_is_valid(self, i0: int, i1: int) -> bool:
        """Return whether lattice coordinates identify a valid node."""
        return bool(self._node_valid[self._grid.node_id(i0, i1)])

    def node_is_valid_id(self, node_id: int) -> bool:
        """Return whether a flat node id is valid."""
        if node_id < 0 or node_id >= self._grid.node_count:
            raise ValueError(f"node_id out of range: {node_id}")
        return bool(self._node_valid[node_id])

    def iter_valid_nodes(self) -> Iterator[GridNode]:
        """Iterate valid nodes in deterministic lattice order."""
        for node in self._grid.iter_nodes():
            if self._node_valid[node.node_id]:
                yield node

    def raw_output(self, q: ArrayLike) -> NDArray[np.floating]:
        """Treat lattice coordinates as raw output samples."""
        return np.asarray(q, dtype=np.float64).reshape(-1)

    def output(self, q: ArrayLike) -> NDArray[np.floating]:
        """Canonicalize a Q-lattice coordinate in the shared chart."""
        return self._output_space.canonicalize(self.raw_output(q))

    def output_displacement(self, q_from: ArrayLike, q_to: ArrayLike) -> float:
        """Return ``d_Q(q_from, q_to)`` (identity map on this lattice)."""
        return self._output_space.distance(self.raw_output(q_from), self.raw_output(q_to))

    def edge_is_valid(self, i0: int, i1: int, j0: int, j1: int) -> bool:
        """Validate a Q-lattice edge via the attached U-segment.

        Endpoints must be valid Q-nodes. The short open path between attached
        crank preimages must stay assembling and inside shared Q limits.
        """
        a = self._grid.node(i0, i1)
        b = self._grid.node(j0, j1)
        if not (self._node_valid[a.node_id] and self._node_valid[b.node_id]):
            return False
        ua = self._attached_u[a.node_id]
        ub = self._attached_u[b.node_id]
        return edge_is_valid(
            self._mechanism,
            self._limits,
            ua,
            ub,
            n_samples=self._edge_samples,
            periodic_axes=(False, False),
            output_space=self._output_space,
        )

    def neighbors(self, i0: int, i1: int) -> list[tuple[int, int]]:
        """Valid four-connected neighbors on the Q lattice."""
        if not self.node_is_valid(i0, i1):
            return []
        result: list[tuple[int, int]] = []
        for j0, j1 in self._grid.neighbors(i0, i1):
            if self.edge_is_valid(i0, i1, j0, j1):
                result.append((j0, j1))
        return result

    def iter_edges(self) -> Iterator[tuple[int, int]]:
        """Iterate undirected valid edges as sorted flat ``(a, b)``."""
        seen: set[tuple[int, int]] = set()
        for node in self.iter_valid_nodes():
            i0, i1 = node.indices
            a = node.node_id
            for j0, j1 in self.neighbors(i0, i1):
                b = self._grid.node_id(j0, j1)
                edge = (a, b) if a < b else (b, a)
                if edge not in seen:
                    seen.add(edge)
                    yield edge

    def valid_edge_count(self) -> int:
        """Number of undirected valid edges."""
        return sum(1 for _ in self.iter_edges())

    def q_resolution_stats(self) -> dict[str, float]:
        """Report lattice spacing and valid-node coverage in Q."""
        du0, du1 = self._grid.steps
        return {
            "delta_q0": float(du0),
            "delta_q1": float(du1),
            "delta_q_mean": float(0.5 * (du0 + du1)),
            "n_nodes": float(self._grid.node_count),
            "n_valid_nodes": float(self.valid_node_count),
            "valid_fraction": float(self.valid_node_count / max(1, self._grid.node_count)),
        }
