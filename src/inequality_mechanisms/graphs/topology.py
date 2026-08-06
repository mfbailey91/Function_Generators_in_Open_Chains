"""Coordinate-free N-dimensional tensor-grid topology.

Version 2 search must be able to reason about adjacency without reaching
into mechanism-specific coordinates. ``TensorGridTopology`` provides a
minimal, dimension-generic lattice: deterministic row-major node IDs and
configurable connectivity with optional per-axis wrapping. It owns no
physical coordinates, ranges, or samples (Sprint V2.1, V2-105; Sprint V3.3
connectivity modes).

``PeriodicGrid2D`` (``grid.py``) remains the Version 1 two-dimensional grid
with coordinates and is not replaced by this module.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from enum import StrEnum
from itertools import product
from typing import Protocol, runtime_checkable


class LatticeConnectivity(StrEnum):
    """Planner-configuration lattice adjacency stencil (ADR-024).

    Connectivity is not part of the robot model. The default
    ``AXIS_ALIGNED`` preserves Version 2 four-connected (in 2-D) behavior.
    ``CHEBYSHEV_1`` is the Version 3 eight-connected planar-2R baseline.
    """

    AXIS_ALIGNED = "axis_aligned"
    CHEBYSHEV_1 = "chebyshev_1"


@runtime_checkable
class GraphTopology(Protocol):
    """Minimal coordinate-free grid-topology contract.

    Implementations expose only shape, node count, ID/index conversion, and
    adjacency. No mechanism, coordinate, or sampling semantics belong here.
    """

    @property
    def shape(self) -> tuple[int, ...]:
        """Number of samples along each axis."""
        ...

    @property
    def node_count(self) -> int:
        """Total number of nodes in the topology."""
        ...

    def node_id(self, index: tuple[int, ...]) -> int:
        """Deterministic flat node ID for a lattice index."""
        ...

    def index_from_id(self, node_id: int) -> tuple[int, ...]:
        """Inverse of ``node_id``."""
        ...

    def neighbors(self, node_id: int) -> Iterable[int]:
        """Deterministically ordered neighbor node IDs."""
        ...


class TensorGridTopology:
    """Tensor-grid lattice with configurable connectivity.

    Parameters
    ----------
    shape :
        Number of samples along each axis, ``(n_0, ..., n_{D-1})``. Each
        entry must be ``>= 2`` (consistent with ``PeriodicGrid2D``) and
        ``D = len(shape)`` must be ``>= 1``.
    wrap :
        Per-axis wrapping flags. When ``True`` on axis ``k``, the first and
        last samples along that axis are neighbors. Defaults to no wrapping
        on any axis. Must have the same length as ``shape``.
    connectivity :
        Adjacency stencil. ``AXIS_ALIGNED`` is ``2*D``-connected (four-
        connected in 2-D). ``CHEBYSHEV_1`` includes all nonzero offsets in
        ``{-1,0,1}^D`` (eight-connected in 2-D).

    Notes
    -----
    Node IDs are deterministic row-major flat indices: for index
    ``(i_0, ..., i_{D-1})`` the ID is
    ``i_0 * n_1 * ... * n_{D-1} + i_1 * n_2 * ... * n_{D-1} + ... + i_{D-1}``,
    i.e. the last axis varies fastest. This matches the flat-index
    convention used by ``PeriodicGrid2D.node_id`` (``i0 * n1 + i1``) for
    ``D = 2``.

    Neighbor iteration is deterministic. Axis-aligned mode emits, for each
    axis ``0 .. D-1``, the negative-direction neighbor before the positive.
    Chebyshev mode emits offsets in lexicographic order on the offset tuple.

    This topology owns no physical coordinates, sampling ranges, or units.
    """

    def __init__(
        self,
        shape: tuple[int, ...],
        *,
        wrap: tuple[bool, ...] | None = None,
        connectivity: LatticeConnectivity | str = LatticeConnectivity.AXIS_ALIGNED,
    ) -> None:
        if len(shape) < 1:
            raise ValueError("shape must have at least one axis")
        dims = tuple(int(n) for n in shape)
        for n in dims:
            if n < 2:
                raise ValueError(f"shape entries must be >= 2, got {shape}")
        if wrap is None:
            wrap = (False,) * len(dims)
        if len(wrap) != len(dims):
            raise ValueError(
                f"wrap must have length {len(dims)} to match shape, got {len(wrap)}"
            )
        conn = LatticeConnectivity(connectivity)

        self._shape = dims
        self._wrap = tuple(bool(w) for w in wrap)
        self._ndim = len(dims)
        self._connectivity = conn

        strides = [1] * self._ndim
        for axis in range(self._ndim - 2, -1, -1):
            strides[axis] = strides[axis + 1] * dims[axis + 1]
        self._strides = tuple(strides)

        node_count = 1
        for n in dims:
            node_count *= n
        self._node_count = node_count

    @property
    def shape(self) -> tuple[int, ...]:
        """Number of samples along each axis."""
        return self._shape

    @property
    def ndim(self) -> int:
        """Number of axes ``D``."""
        return self._ndim

    @property
    def wrap(self) -> tuple[bool, ...]:
        """Per-axis wrapping flags."""
        return self._wrap

    @property
    def connectivity(self) -> LatticeConnectivity:
        """Configured adjacency stencil."""
        return self._connectivity

    @property
    def node_count(self) -> int:
        """Total number of lattice nodes, the product of ``shape``."""
        return self._node_count

    def node_id(self, index: tuple[int, ...]) -> int:
        """Deterministic row-major flat ID for a lattice index.

        Parameters
        ----------
        index :
            Integer lattice coordinates, one per axis.

        Returns
        -------
        int
            Flat node ID with the last index varying fastest.
        """
        self._check_index(index)
        return sum(i * stride for i, stride in zip(index, self._strides))

    def index_from_id(self, node_id: int) -> tuple[int, ...]:
        """Inverse of ``node_id``: lattice index for a flat node ID."""
        if node_id < 0 or node_id >= self._node_count:
            raise ValueError(f"node_id out of range: {node_id}")
        remainder = int(node_id)
        index = []
        for stride in self._strides:
            i, remainder = divmod(remainder, stride)
            index.append(i)
        return tuple(index)

    def neighbors(self, node_id: int) -> list[int]:
        """Deterministically ordered neighbor node IDs."""
        if self._connectivity is LatticeConnectivity.AXIS_ALIGNED:
            return self._neighbors_axis_aligned(node_id)
        if self._connectivity is LatticeConnectivity.CHEBYSHEV_1:
            return self._neighbors_chebyshev_1(node_id)
        raise ValueError(f"unsupported connectivity {self._connectivity!r}")

    def _neighbors_axis_aligned(self, node_id: int) -> list[int]:
        """Axis-aligned ``2*D`` neighbors (four-connected in 2-D)."""
        index = self.index_from_id(node_id)
        result: list[int] = []
        for axis in range(self._ndim):
            n = self._shape[axis]
            wrapped = self._wrap[axis]
            neighbor_offsets: list[int] = []
            for delta in (-1, 1):
                j = index[axis] + delta
                if wrapped:
                    j %= n
                elif j < 0 or j >= n:
                    continue
                if j not in neighbor_offsets:
                    neighbor_offsets.append(j)
            for j in neighbor_offsets:
                neighbor_index = index[:axis] + (j,) + index[axis + 1 :]
                result.append(self.node_id(neighbor_index))
        return result

    def _neighbors_chebyshev_1(self, node_id: int) -> list[int]:
        """Chebyshev radius-1 neighbors (eight-connected in 2-D)."""
        index = self.index_from_id(node_id)
        result: list[int] = []
        seen: set[int] = set()
        for offset in product((-1, 0, 1), repeat=self._ndim):
            if all(d == 0 for d in offset):
                continue
            neighbor_index: list[int] = []
            valid = True
            for axis, delta in enumerate(offset):
                j = index[axis] + delta
                n = self._shape[axis]
                if self._wrap[axis]:
                    j %= n
                elif j < 0 or j >= n:
                    valid = False
                    break
                neighbor_index.append(j)
            if not valid:
                continue
            nb_id = self.node_id(tuple(neighbor_index))
            if nb_id not in seen:
                seen.add(nb_id)
                result.append(nb_id)
        return result

    def iter_edges(self) -> Iterator[tuple[int, int]]:
        """Iterate undirected edges as sorted flat ``(node_id_a, node_id_b)``.

        Each undirected edge appears exactly once with ``a < b``, in
        deterministic order following node-ID and neighbor-list order.
        """
        seen: set[tuple[int, int]] = set()
        for a in range(self._node_count):
            for b in self.neighbors(a):
                edge = (a, b) if a < b else (b, a)
                if edge not in seen:
                    seen.add(edge)
                    yield edge

    def _check_index(self, index: tuple[int, ...]) -> None:
        if len(index) != self._ndim:
            raise ValueError(f"index has {len(index)} entries, expected {self._ndim}")
        for axis, i in enumerate(index):
            if i < 0 or i >= self._shape[axis]:
                raise ValueError(f"index {index} out of range for shape {self._shape}")
