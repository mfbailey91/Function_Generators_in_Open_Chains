"""Node and edge validity for mechanism graphs under shared output limits.

Node identity remains an input configuration. Validity combines mechanism
assembly (``valid_input``) with shared output joint limits in Q. Edges are
checked along the short input-space segment between endpoints, including
periodic wrapping when an axis is periodic.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.graphs.grid import GridNode, PeriodicGrid2D
from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.spaces.limits import OutputJointLimits
from inequality_mechanisms.spaces.output_space import OutputSpace

_TWO_PI = 2.0 * np.pi
_DEFAULT_EDGE_SAMPLES = 17


def interpolate_input_segment(
    u_a: ArrayLike,
    u_b: ArrayLike,
    s: float,
    *,
    periodic_axes: tuple[bool, ...],
    period: float = _TWO_PI,
) -> NDArray[np.floating]:
    """Interpolate along the short input path from ``u_a`` to ``u_b``.

    Parameters
    ----------
    u_a, u_b :
        Endpoint configurations, shape ``(n,)``.
    s :
        Interpolation parameter in ``[0, 1]``.
    periodic_axes :
        Per-axis flags; ``True`` selects the shortest wrapped displacement
        on that axis (period ``period``).
    period :
        Wrap period for periodic axes (default ``2 * pi``).

    Returns
    -------
    ndarray
        Configuration ``u(s)``, shape ``(n,)``.

    Raises
    ------
    ValueError
        If shapes disagree, ``s`` is outside ``[0, 1]``, or values are
        non-finite.
    """
    a = np.asarray(u_a, dtype=np.float64)
    b = np.asarray(u_b, dtype=np.float64)
    if a.ndim != 1 or b.ndim != 1:
        raise ValueError("u_a and u_b must be 1-D")
    if a.shape != b.shape:
        raise ValueError(f"u_a and u_b shape mismatch: {a.shape} vs {b.shape}")
    if len(periodic_axes) != a.shape[0]:
        raise ValueError(
            f"periodic_axes must have length {a.shape[0]}, got {len(periodic_axes)}"
        )
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
        raise ValueError("u_a and u_b must contain only finite values")
    if not np.isfinite(s) or s < 0.0 or s > 1.0:
        raise ValueError(f"s must lie in [0, 1], got {s}")
    if not np.isfinite(period) or period <= 0.0:
        raise ValueError(f"period must be finite and positive, got {period}")

    delta = b - a
    half = 0.5 * period
    for i, wrap in enumerate(periodic_axes):
        if wrap:
            delta[i] = (delta[i] + half) % period - half
    return a + float(s) * delta


def configuration_is_valid(
    mechanism: Mechanism,
    limits: OutputJointLimits,
    u: ArrayLike,
    *,
    output_space: OutputSpace | None = None,
) -> bool:
    """Return whether ``u`` assembles and maps into the shared output limits.

    Parameters
    ----------
    mechanism :
        Mechanism providing assembly checks and the forward map.
    limits :
        Shared output joint limits (same object for gearbox and four-bar).
    u :
        Input configuration, shape ``(mechanism.input_dim,)``.
    output_space :
        Shared output chart (ADR-011). Defaults to a bounded-revolute space
        built from ``limits``.

    Returns
    -------
    bool
        ``True`` if ``valid_input(u)`` and canonicalized ``g(u)`` lies in
        the shared chart / limit box.

    Raises
    ------
    ValueError
        If ``limits.dim`` does not match ``mechanism.output_dim``, or if
        ``u`` has the wrong shape / is non-finite.
    """
    if limits.dim != mechanism.output_dim:
        raise ValueError(
            f"limits.dim ({limits.dim}) must equal mechanism.output_dim "
            f"({mechanism.output_dim})"
        )
    space = OutputSpace.from_limits(limits) if output_space is None else output_space
    if space.dim != mechanism.output_dim:
        raise ValueError(
            f"output_space.dim ({space.dim}) must equal mechanism.output_dim "
            f"({mechanism.output_dim})"
        )
    if not mechanism.valid_input(u):
        return False
    # Construction helper (IM-042 / IM-043): no ConstrainedInputGraph yet.
    # Graph-facing code must use ConstrainedInputGraph.raw_output / output.
    q_raw = mechanism.input_to_output(u)
    return space.contains(q_raw)


def edge_is_valid(
    mechanism: Mechanism,
    limits: OutputJointLimits,
    u_a: ArrayLike,
    u_b: ArrayLike,
    *,
    n_samples: int = _DEFAULT_EDGE_SAMPLES,
    periodic_axes: tuple[bool, ...] | None = None,
    output_space: OutputSpace | None = None,
) -> bool:
    """Return whether the short input segment between endpoints stays valid.

    Samples ``n_samples`` configurations inclusive of both endpoints. Endpoint
    checks alone are insufficient: a nonlinear mechanism map can leave the
    limit box or assembly domain in the open segment.

    Decisions are delegated to :func:`inequality_mechanisms.graphs.edge_trace.build_edge_trace`
    so the edge microscope shares the same sample logic (IM-046).

    Parameters
    ----------
    mechanism :
        Mechanism used for assembly and forward map.
    limits :
        Shared output joint limits.
    u_a, u_b :
        Endpoint input configurations.
    n_samples :
        Number of sample points along the segment, including endpoints.
        Must be ``>= 2``.
    periodic_axes :
        Override for short-path wrapping. Defaults to
        ``mechanism.periodic_axes()``.
    output_space :
        Shared output chart; forwarded to the shared edge-trace builder.

    Returns
    -------
    bool
        ``True`` if every sample is a valid configuration.

    Raises
    ------
    ValueError
        On dimension mismatch, non-finite inputs, or ``n_samples < 2``.
    """
    from inequality_mechanisms.graphs.edge_trace import build_edge_trace

    return build_edge_trace(
        mechanism,
        limits,
        u_a,
        u_b,
        n_samples=n_samples,
        periodic_axes=periodic_axes,
        output_space=output_space,
    ).is_valid


class ConstrainedInputGraph:
    """Four-connected input grid filtered by assembly and output limits.

    Nodes whose input fails assembly or whose output leaves the shared limit
    box are removed. Lattice edges are retained only when the short continuous
    segment between endpoints stays valid (IM-010).

    Parameters
    ----------
    grid :
        Underlying periodic (or open) 2-D lattice.
    mechanism :
        Mechanism with ``input_dim == 2``.
    limits :
        Shared output joint limits with ``dim == mechanism.output_dim``.
    edge_samples :
        Sample count for edge-interior validation (including endpoints).
    output_space :
        Shared output chart (ADR-011). Defaults to bounded revolute axes
        matching ``limits``.
    """

    def __init__(
        self,
        grid: PeriodicGrid2D,
        mechanism: Mechanism,
        limits: OutputJointLimits,
        *,
        edge_samples: int = _DEFAULT_EDGE_SAMPLES,
        output_space: OutputSpace | None = None,
    ) -> None:
        if mechanism.input_dim != 2:
            raise ValueError(
                f"ConstrainedInputGraph requires input_dim == 2, "
                f"got {mechanism.input_dim}"
            )
        if limits.dim != mechanism.output_dim:
            raise ValueError(
                f"limits.dim ({limits.dim}) must equal mechanism.output_dim "
                f"({mechanism.output_dim})"
            )
        if edge_samples < 2:
            raise ValueError(f"edge_samples must be >= 2, got {edge_samples}")
        space = OutputSpace.from_limits(limits) if output_space is None else output_space
        if space.dim != mechanism.output_dim:
            raise ValueError(
                f"output_space.dim ({space.dim}) must equal mechanism.output_dim "
                f"({mechanism.output_dim})"
            )
        self._grid = grid
        self._mechanism = mechanism
        self._limits = limits
        self._output_space = space
        self._edge_samples = int(edge_samples)
        self._periodic = mechanism.periodic_axes()
        self._node_valid = np.zeros(grid.node_count, dtype=bool)
        for node in grid.iter_nodes():
            self._node_valid[node.node_id] = configuration_is_valid(
                mechanism,
                limits,
                node.coordinates,
                output_space=space,
            )

    @property
    def grid(self) -> PeriodicGrid2D:
        """Underlying lattice (unfiltered)."""
        return self._grid

    @property
    def mechanism(self) -> Mechanism:
        """Mechanism supplying assembly and forward map."""
        return self._mechanism

    @property
    def limits(self) -> OutputJointLimits:
        """Shared output joint limits."""
        return self._limits

    @property
    def output_space(self) -> OutputSpace:
        """Shared output configuration chart (ADR-011)."""
        return self._output_space

    @property
    def edge_samples(self) -> int:
        """Sample count used for edge-interior checks."""
        return self._edge_samples

    def raw_output(self, u: ArrayLike) -> NDArray[np.floating]:
        """Return raw mechanism output ``g(u)`` (not chart-canonicalized).

        Prefer :meth:`output` for validity, costs, heuristics, tasks, and
        plots. This method exists for diagnostics and for composing the
        graph-owned canonicalize path (IM-042).
        """
        return np.asarray(self._mechanism.input_to_output(u), dtype=np.float64)

    def output(self, u: ArrayLike) -> NDArray[np.floating]:
        """Return canonicalized ``g(u)`` in the shared output chart (IM-042)."""
        return self._output_space.canonicalize(self.raw_output(u))

    def output_at(self, u: ArrayLike) -> NDArray[np.floating]:
        """Alias for :meth:`output` (retained for existing call sites)."""
        return self.output(u)

    def output_displacement(
        self, u_from: ArrayLike, u_to: ArrayLike
    ) -> float:
        """Return ``d_Q(g(u_from), g(u_to))`` via the graph output boundary.

        Parameters
        ----------
        u_from, u_to :
            Input configurations, shape ``(input_dim,)``.

        Returns
        -------
        float
            Nonnegative Euclidean displacement in the shared chart.
        """
        return self._output_space.distance(self.raw_output(u_from), self.raw_output(u_to))

    def inspect_output(self, u: ArrayLike):
        """Return raw/canonical diagnostics without affecting search (IM-045).

        Parameters
        ----------
        u :
            Input configuration, shape ``(input_dim,)``.

        Returns
        -------
        OutputMappingDiagnostic
            Assembly flag and per-axis mapping records.
        """
        u_arr = np.asarray(u, dtype=np.float64)
        assembly = bool(self._mechanism.valid_input(u_arr))
        if not assembly:
            from inequality_mechanisms.diagnostics.mapping import (
                AxisMappingDiagnostic,
                OutputMappingDiagnostic,
            )

            axes = tuple(
                AxisMappingDiagnostic(
                    raw=float("nan"),
                    canonical=None,
                    winding=None,
                    within_bounds=False,
                    crossed_native_seam=False,
                )
                for _ in range(self._output_space.dim)
            )
            return OutputMappingDiagnostic(
                u=tuple(float(x) for x in u_arr),
                assembly_valid=False,
                axes=axes,
            )
        raw = self.raw_output(u_arr)
        from inequality_mechanisms.diagnostics.mapping import (
            OutputMappingDiagnostic,
            inspect_raw_output,
        )

        return OutputMappingDiagnostic(
            u=tuple(float(x) for x in u_arr),
            assembly_valid=True,
            axes=inspect_raw_output(raw, self._output_space),
        )

    def edge_trace(self, i0: int, i1: int, j0: int, j1: int):
        """Return the shared validation trace for a lattice edge (IM-046)."""
        from inequality_mechanisms.graphs.edge_trace import build_edge_trace

        a = self._grid.node(i0, i1)
        b = self._grid.node(j0, j1)
        return build_edge_trace(
            self._mechanism,
            self._limits,
            a.coordinates,
            b.coordinates,
            n_samples=self._edge_samples,
            periodic_axes=self._periodic,
            output_space=self._output_space,
        )

    @property
    def valid_node_count(self) -> int:
        """Number of lattice nodes that pass configuration validity."""
        return int(np.count_nonzero(self._node_valid))

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

    def edge_is_valid(self, i0: int, i1: int, j0: int, j1: int) -> bool:
        """Return whether the lattice edge between two index pairs is valid."""
        a = self._grid.node(i0, i1)
        b = self._grid.node(j0, j1)
        if not (self._node_valid[a.node_id] and self._node_valid[b.node_id]):
            return False
        return edge_is_valid(
            self._mechanism,
            self._limits,
            a.coordinates,
            b.coordinates,
            n_samples=self._edge_samples,
            periodic_axes=self._periodic,
            output_space=self._output_space,
        )

    def neighbors(self, i0: int, i1: int) -> list[tuple[int, int]]:
        """Valid four-connected neighbors of a lattice node.

        Returns an empty list when ``(i0, i1)`` itself is invalid. Order matches
        ``PeriodicGrid2D.neighbors``.
        """
        if not self.node_is_valid(i0, i1):
            return []
        result: list[tuple[int, int]] = []
        for j0, j1 in self._grid.neighbors(i0, i1):
            if self.edge_is_valid(i0, i1, j0, j1):
                result.append((j0, j1))
        return result

    def iter_edges(self) -> Iterator[tuple[int, int]]:
        """Iterate undirected valid edges as sorted flat ``(node_id_a, node_id_b)``.

        Each undirected edge appears once with ``a < b``.
        """
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

    def connected_component_count(self) -> int:
        """Number of connected components among valid nodes (undirected)."""
        remaining = {n.node_id for n in self.iter_valid_nodes()}
        if not remaining:
            return 0
        components = 0
        while remaining:
            components += 1
            seed = next(iter(remaining))
            stack = [seed]
            remaining.remove(seed)
            while stack:
                u = stack.pop()
                i0, i1 = self._grid.indices_from_id(u)
                for j0, j1 in self.neighbors(i0, i1):
                    v = self._grid.node_id(j0, j1)
                    if v in remaining:
                        remaining.remove(v)
                        stack.append(v)
        return components

    def to_networkx(self) -> Any:
        """Build an undirected ``networkx.Graph`` of valid nodes and edges.

        Requires the optional ``networkx`` development dependency.
        """
        try:
            import networkx as nx  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "networkx is required for ConstrainedInputGraph.to_networkx(); "
                "install with pip install 'inequality-mechanisms[dev]'"
            ) from exc
        g = nx.Graph()
        for node in self.iter_valid_nodes():
            g.add_node(
                node.node_id,
                indices=node.indices,
                coordinates=node.coordinates,
            )
        g.add_edges_from(self.iter_edges())
        return g
