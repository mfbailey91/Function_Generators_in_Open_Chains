"""Version 2 output-state embedded planning graphs (Sprint V2.3, ADR-014/015).

``EmbeddedPlanningGraph`` is the Version 2 replacement search substrate: node
identity and stored planning coordinate live in ``Q`` (ADR-014), adjacency
comes from a dimension-independent, nonperiodic ``TensorGridTopology``
(ADR-015), and every node carries the unique actuator realization attached
by a certified ``OperatingBranch``. It deliberately does not reuse
``PeriodicGrid2D`` (Version 1's coordinate-owning, potentially periodic
grid) and does not promote ``MonotonicOutputGraph`` (Version 1's
noninjective-aware output graph) to Version 2 identity.

Two sampling modes are supported, both over a nonwrapped topology:

- :meth:`EmbeddedPlanningGraph.from_uniform_input` places nodes on a
  uniform ``U`` lattice and maps them through ``branch.forward`` (V2-302);
- :meth:`EmbeddedPlanningGraph.from_uniform_output` places nodes on a
  uniform ``Q`` lattice and maps them through ``branch.inverse`` (V2-303).

For the shared uniform-``Q`` null control (V2-306), :class:`UniformOutputLattice`
constructs the ``q`` sample array and topology exactly once;
:meth:`EmbeddedPlanningGraph.from_output_lattice` then attaches
mechanism-specific ``u`` realizations without regenerating ``q``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.graphs.sampling import (
    AxisSpacingStatistics,
    SamplingDomain,
    SamplingSpecification,
    TransitionParameterization,
    compute_axis_spacing_statistics,
)
from inequality_mechanisms.graphs.topology import LatticeConnectivity, TensorGridTopology
from inequality_mechanisms.graphs.transitions import EdgeTraceV2, build_edge_trace_v2
from inequality_mechanisms.mechanisms.operating_branch import (
    BranchInverseError,
    OperatingBranch,
)
from inequality_mechanisms.spaces.output_space import OutputSpace

_DEFAULT_EDGE_SAMPLES = 17


def _lock_array(arr: NDArray[Any]) -> NDArray[Any]:
    """Return a contiguous, read-only copy of ``arr``."""
    out = np.array(arr, copy=True)
    out.flags.writeable = False
    return out


def _row_major_grid(
    axis_samples: list[NDArray[np.float64]], topology: TensorGridTopology
) -> NDArray[np.float64]:
    """Stack per-axis 1-D samples into a ``(node_count, ndim)`` row-major array.

    Row order matches ``topology.node_id``: the last axis varies fastest.
    """
    mesh = np.meshgrid(*axis_samples, indexing="ij")
    return np.stack([g.reshape(-1) for g in mesh], axis=-1).astype(np.float64)


@dataclass(frozen=True, slots=True)
class UniformOutputLattice:
    """A shared uniform-``Q`` lattice built once for the null control (V2-306).

    Attributes
    ----------
    topology :
        Nonperiodic tensor-grid topology shared by every attached mechanism.
    q_nodes :
        Row-major ``(node_count, output_dim)`` uniform output samples.
    output_space :
        Output chart the lattice was built against.
    sampling :
        Provenance record for the lattice construction.
    """

    topology: TensorGridTopology
    q_nodes: NDArray[np.float64]
    output_space: OutputSpace
    sampling: SamplingSpecification

    def __post_init__(self) -> None:
        object.__setattr__(self, "q_nodes", _lock_array(self.q_nodes))
        if self.q_nodes.shape != (self.topology.node_count, self.output_space.dim):
            raise ValueError(
                "q_nodes shape must be (node_count, output_dim), got "
                f"{self.q_nodes.shape}, expected "
                f"({self.topology.node_count}, {self.output_space.dim})"
            )

    @classmethod
    def from_output_space(
        cls,
        output_space: OutputSpace,
        shape: tuple[int, ...],
        *,
        connectivity: LatticeConnectivity | str = LatticeConnectivity.AXIS_ALIGNED,
    ) -> UniformOutputLattice:
        """Build the shared uniform-``Q`` lattice exactly once.

        Parameters
        ----------
        output_space :
            Output chart common to every mechanism that will attach to this
            lattice (e.g. via :meth:`EmbeddedPlanningGraph.from_output_lattice`).
        shape :
            Number of samples along each output axis, length
            ``output_space.dim``, each entry ``>= 2``.
        connectivity :
            Lattice adjacency stencil (default axis-aligned / four-connected
            in 2-D for Version 2 parity; ``chebyshev_1`` for eight-connected).

        Returns
        -------
        UniformOutputLattice
            Shared topology and ``q`` sample array.
        """
        dim = output_space.dim
        if len(shape) != dim:
            raise ValueError(
                f"shape must have length {dim} to match output_space.dim, "
                f"got {len(shape)}"
            )
        lo = output_space.lower
        hi = output_space.upper
        axis_samples = [
            np.linspace(float(lo[i]), float(hi[i]), int(shape[i]), endpoint=True)
            for i in range(dim)
        ]
        topology = TensorGridTopology(
            tuple(int(n) for n in shape),
            connectivity=connectivity,
        )
        q_nodes = _row_major_grid(axis_samples, topology)
        sampling = SamplingSpecification(
            domain=SamplingDomain.OUTPUT,
            shape=tuple(int(n) for n in shape),
            endpoint=True,
            axis_lower=tuple(float(x) for x in lo),
            axis_upper=tuple(float(x) for x in hi),
        )
        return cls(
            topology=topology,
            q_nodes=q_nodes,
            output_space=output_space,
            sampling=sampling,
        )


@dataclass(frozen=True)
class EmbeddedPlanningGraph:
    """Version 2 output-state planning graph (ADR-014, ADR-015).

    Node identity and stored planning coordinate live in ``q_nodes``; every
    node also carries its unique certified-branch actuator realization in
    ``u_nodes``. Adjacency comes from ``topology`` alone (node IDs only, no
    coordinates). Satisfies
    :class:`inequality_mechanisms.search.protocol.SearchGraph`.

    Attributes
    ----------
    topology :
        Nonperiodic tensor-grid topology owning adjacency.
    branch :
        Certified operating branch every node's ``(q, u)`` pair belongs to.
    q_nodes :
        Row-major ``(node_count, output_dim)`` planning-state array.
    u_nodes :
        Row-major ``(node_count, input_dim)`` attached actuator realization.
    valid_nodes :
        Row-major ``(node_count,)`` boolean validity mask.
    sampling_domain :
        Domain (``INPUT`` or ``OUTPUT``) the lattice nodes were sampled from.
    transition_parameterization :
        How an edge between two nodes should be interpolated and traced.
    sampling :
        Optional full sampling provenance record (axis bounds, shape,
        endpoint policy) supplementing ``sampling_domain``.
    """

    topology: TensorGridTopology
    branch: OperatingBranch
    q_nodes: NDArray[np.float64]
    u_nodes: NDArray[np.float64]
    valid_nodes: NDArray[np.bool_]
    sampling_domain: SamplingDomain
    transition_parameterization: TransitionParameterization
    sampling: SamplingSpecification | None = field(default=None)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "sampling_domain", SamplingDomain(self.sampling_domain)
        )
        object.__setattr__(
            self,
            "transition_parameterization",
            TransitionParameterization(self.transition_parameterization),
        )
        object.__setattr__(self, "q_nodes", _lock_array(self.q_nodes))
        object.__setattr__(self, "u_nodes", _lock_array(self.u_nodes))
        valid = np.asarray(self.valid_nodes, dtype=np.bool_)
        object.__setattr__(self, "valid_nodes", _lock_array(valid))

        n = self.topology.node_count
        output_dim = self.branch.mechanism.output_dim
        input_dim = self.branch.mechanism.input_dim
        if self.q_nodes.shape != (n, output_dim):
            raise ValueError(
                f"q_nodes shape must be ({n}, {output_dim}), got {self.q_nodes.shape}"
            )
        if self.u_nodes.shape != (n, input_dim):
            raise ValueError(
                f"u_nodes shape must be ({n}, {input_dim}), got {self.u_nodes.shape}"
            )
        if self.valid_nodes.shape != (n,):
            raise ValueError(
                f"valid_nodes shape must be ({n},), got {self.valid_nodes.shape}"
            )

    # -- SearchGraph protocol -------------------------------------------------

    @property
    def node_count(self) -> int:
        """Total number of node ids, including any invalid ones."""
        return self.topology.node_count

    def node_is_valid(self, node_id: int) -> bool:
        """Return whether ``node_id`` is a valid, searchable node."""
        return bool(self.valid_nodes[node_id])

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        """Valid neighbor node ids of ``node_id``, in topology order."""
        return tuple(
            nb for nb in self.topology.neighbors(node_id) if self.valid_nodes[nb]
        )

    # -- Coordinate accessors (excluded from SearchGraph by design) ---------

    def q_state(self, node_id: int) -> NDArray[np.float64]:
        """Output-configuration planning state of ``node_id``."""
        return np.array(self.q_nodes[node_id], copy=True)

    def u_state(self, node_id: int) -> NDArray[np.float64]:
        """Attached actuator realization of ``node_id``."""
        return np.array(self.u_nodes[node_id], copy=True)

    def edge_trace(
        self, a: int, b: int, n_samples: int = _DEFAULT_EDGE_SAMPLES
    ) -> EdgeTraceV2:
        """Return the Version 2 edge trace between nodes ``a`` and ``b``.

        Uses ``self.transition_parameterization`` to decide whether ``u`` or
        ``q`` is linearly interpolated (ADR-015); never wraps.
        """
        n = self.node_count
        if not (0 <= a < n) or not (0 <= b < n):
            raise ValueError(f"node ids out of range: a={a}, b={b}, node_count={n}")
        return build_edge_trace_v2(
            self.branch,
            self.transition_parameterization,
            self.q_nodes[a],
            self.u_nodes[a],
            self.q_nodes[b],
            self.u_nodes[b],
            n_samples=n_samples,
        )

    # -- Spacing diagnostics (V2-302 / V2-303) --------------------------------

    def axis_marginal(
        self, values: NDArray[np.float64], axis: int
    ) -> NDArray[np.float64]:
        """Return the 1-D marginal of a ``(node_count, dim)`` array along ``axis``.

        Holds every other lattice index at ``0`` and reads out component
        ``axis`` of ``values`` while lattice axis ``axis`` sweeps its full
        range. Used for per-axis spacing statistics and ``q(u)`` diagnostics.
        """
        shape = self.topology.shape
        if not (0 <= axis < len(shape)):
            raise ValueError(f"axis {axis} out of range for shape {shape}")
        n = shape[axis]
        out = np.empty(n, dtype=np.float64)
        base_index = [0] * len(shape)
        for i in range(n):
            idx = list(base_index)
            idx[axis] = i
            node_id = self.topology.node_id(tuple(idx))
            out[i] = values[node_id, axis]
        return out

    def output_axis_spacing(self, axis: int) -> AxisSpacingStatistics:
        """Per-axis mapped-output (``q``) spacing statistics (V2-302)."""
        return compute_axis_spacing_statistics(
            self.axis_marginal(self.q_nodes, axis), axis=axis
        )

    def actuator_axis_spacing(self, axis: int) -> AxisSpacingStatistics:
        """Per-axis mapped-actuator (``u``) spacing statistics (V2-303)."""
        return compute_axis_spacing_statistics(
            self.axis_marginal(self.u_nodes, axis), axis=axis
        )

    # -- Factories -------------------------------------------------------------

    @classmethod
    def from_uniform_input(
        cls, branch: OperatingBranch, shape: tuple[int, ...]
    ) -> EmbeddedPlanningGraph:
        """Build a Version 2 graph by uniformly sampling the actuator box (V2-302).

        Samples ``u`` uniformly (``np.linspace(..., endpoint=True)``) inside
        the certified branch input box, maps every node through
        ``branch.forward``, and stores the mapped ``q`` as planning identity.
        The topology is always nonperiodic (ADR-014).

        Parameters
        ----------
        branch :
            Certified operating branch to sample.
        shape :
            Number of samples along each input axis, length
            ``branch.mechanism.input_dim``, each entry ``>= 2``.

        Returns
        -------
        EmbeddedPlanningGraph
            Graph with ``sampling_domain=INPUT`` and
            ``transition_parameterization=INPUT_LINEAR``. Every sampled node
            is valid: the certified branch box assembles and maps
            everywhere on it by construction.
        """
        dim = branch.mechanism.input_dim
        if len(shape) != dim:
            raise ValueError(
                f"shape must have length {dim} to match branch input_dim, "
                f"got {len(shape)}"
            )
        cert = branch.certificate
        lo = np.asarray(cert.input_lower, dtype=np.float64)
        hi = np.asarray(cert.input_upper, dtype=np.float64)
        axis_samples = [
            np.linspace(float(lo[i]), float(hi[i]), int(shape[i]), endpoint=True)
            for i in range(dim)
        ]
        topology = TensorGridTopology(tuple(int(n) for n in shape))
        u_nodes = _row_major_grid(axis_samples, topology)
        q_nodes = np.empty_like(u_nodes)
        for node_id in range(topology.node_count):
            q_nodes[node_id] = branch.forward(u_nodes[node_id])
        valid_nodes = np.ones(topology.node_count, dtype=np.bool_)
        sampling = SamplingSpecification(
            domain=SamplingDomain.INPUT,
            shape=tuple(int(n) for n in shape),
            endpoint=True,
            axis_lower=tuple(float(x) for x in lo),
            axis_upper=tuple(float(x) for x in hi),
        )
        return cls(
            topology=topology,
            branch=branch,
            q_nodes=q_nodes,
            u_nodes=u_nodes,
            valid_nodes=valid_nodes,
            sampling_domain=SamplingDomain.INPUT,
            transition_parameterization=TransitionParameterization.INPUT_LINEAR,
            sampling=sampling,
        )

    @classmethod
    def from_uniform_output(
        cls, branch: OperatingBranch, shape: tuple[int, ...]
    ) -> EmbeddedPlanningGraph:
        """Build a Version 2 graph by uniformly sampling the output box (V2-303).

        Samples ``q`` uniformly inside the certified branch output box and
        recovers the unique actuator realization through ``branch.inverse``.

        Parameters
        ----------
        branch :
            Certified operating branch to sample.
        shape :
            Number of samples along each output axis, length
            ``branch.mechanism.output_dim``, each entry ``>= 2``.

        Returns
        -------
        EmbeddedPlanningGraph
            Graph with ``sampling_domain=OUTPUT`` and
            ``transition_parameterization=OUTPUT_LINEAR``. A node is marked
            invalid only if ``branch.inverse`` fails at that sample (should
            not occur inside the certified output box, but the mask is kept
            explicit rather than assumed, per V2-305).
        """
        dim = branch.mechanism.output_dim
        if len(shape) != dim:
            raise ValueError(
                f"shape must have length {dim} to match branch output_dim, "
                f"got {len(shape)}"
            )
        cert = branch.certificate
        lo = np.asarray(cert.output_lower, dtype=np.float64)
        hi = np.asarray(cert.output_upper, dtype=np.float64)
        axis_samples = [
            np.linspace(float(lo[i]), float(hi[i]), int(shape[i]), endpoint=True)
            for i in range(dim)
        ]
        topology = TensorGridTopology(tuple(int(n) for n in shape))
        q_nodes = _row_major_grid(axis_samples, topology)
        u_nodes = np.full((topology.node_count, branch.mechanism.input_dim), np.nan)
        valid_nodes = np.zeros(topology.node_count, dtype=np.bool_)
        for node_id in range(topology.node_count):
            try:
                u_nodes[node_id] = branch.inverse(q_nodes[node_id])
                valid_nodes[node_id] = True
            except BranchInverseError:
                continue
        sampling = SamplingSpecification(
            domain=SamplingDomain.OUTPUT,
            shape=tuple(int(n) for n in shape),
            endpoint=True,
            axis_lower=tuple(float(x) for x in lo),
            axis_upper=tuple(float(x) for x in hi),
        )
        return cls(
            topology=topology,
            branch=branch,
            q_nodes=q_nodes,
            u_nodes=u_nodes,
            valid_nodes=valid_nodes,
            sampling_domain=SamplingDomain.OUTPUT,
            transition_parameterization=TransitionParameterization.OUTPUT_LINEAR,
            sampling=sampling,
        )

    @classmethod
    def from_output_lattice(
        cls, shared: UniformOutputLattice, branch: OperatingBranch
    ) -> EmbeddedPlanningGraph:
        """Attach a mechanism-specific ``u`` realization to a shared lattice (V2-306).

        Reuses ``shared.topology`` and ``shared.q_nodes`` verbatim (the same
        floating-point ``q`` array is never regenerated per mechanism);
        only ``u_nodes`` and ``valid_nodes`` are mechanism-specific.

        Parameters
        ----------
        shared :
            Lattice built once via :meth:`UniformOutputLattice.from_output_space`.
        branch :
            Certified operating branch to attach.

        Returns
        -------
        EmbeddedPlanningGraph
            Graph sharing ``shared.topology`` and ``shared.q_nodes`` with
            every other graph built from the same ``shared`` lattice.

        Raises
        ------
        ValueError
            If ``branch.mechanism.output_dim`` does not match
            ``shared.output_space.dim``.
        """
        dim = branch.mechanism.output_dim
        if dim != shared.output_space.dim:
            raise ValueError(
                f"branch output_dim ({dim}) must match shared lattice "
                f"output_space.dim ({shared.output_space.dim})"
            )
        node_count = shared.topology.node_count
        u_nodes = np.full((node_count, branch.mechanism.input_dim), np.nan)
        valid_nodes = np.zeros(node_count, dtype=np.bool_)
        for node_id in range(node_count):
            try:
                u_nodes[node_id] = branch.inverse(shared.q_nodes[node_id])
                valid_nodes[node_id] = True
            except BranchInverseError:
                continue
        return cls(
            topology=shared.topology,
            branch=branch,
            q_nodes=shared.q_nodes,
            u_nodes=u_nodes,
            valid_nodes=valid_nodes,
            sampling_domain=SamplingDomain.OUTPUT,
            transition_parameterization=TransitionParameterization.OUTPUT_LINEAR,
            sampling=shared.sampling,
        )
