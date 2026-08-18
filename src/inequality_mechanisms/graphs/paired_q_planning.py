"""One common-Q paired planning graph (Sprint V4.2B / V4-224).

Build the Q lattice and candidate adjacency once, inverse-lift every arm,
and require identical validity before returning mechanism-specific U
embeddings. Do not fall back to post-hoc edge-set intersection.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.graphs.pair_invariants import (
    SharedQPairInvariantError,
    assert_shared_q_pair_invariants,
)
from inequality_mechanisms.graphs.topology import LatticeConnectivity, TensorGridTopology
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch
from inequality_mechanisms.spaces.output_space import OutputSpace

_Q_BOX_ATOL = 1e-12


class PairedTopologyMismatch(ValueError):
    """Raised when paired mechanisms do not share one Q planning topology."""

    failure_code = "paired_topology_mismatch"


@dataclass(frozen=True)
class PairedQPlanningGraph:
    """Shared-Q topology with per-mechanism U embeddings.

    Attributes
    ----------
    topology :
        Common tensor-grid adjacency.
    q_by_node :
        Shared row-major Q samples.
    x_by_node :
        Optional shared X samples. ``None`` when no robot was supplied.
    arms :
        Mechanism embeddings that reuse ``topology`` and ``q_by_node``.
    rejected_candidates :
        Per-arm rejected node ids. Empty on a successful pair.
    """

    topology: TensorGridTopology
    q_by_node: NDArray[np.float64]
    x_by_node: NDArray[np.float64] | None
    arms: Mapping[str, EmbeddedPlanningGraph]
    rejected_candidates: Mapping[str, tuple[int, ...]]


def _q_box(branch: OperatingBranch) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    cert = branch.certificate
    lo = np.asarray(cert.output_lower, dtype=np.float64)
    hi = np.asarray(cert.output_upper, dtype=np.float64)
    return lo, hi


def _require_matching_q_boxes(
    branches: Mapping[str, OperatingBranch],
) -> None:
    names = list(branches)
    ref_lo, ref_hi = _q_box(branches[names[0]])
    for name in names[1:]:
        lo, hi = _q_box(branches[name])
        if lo.shape != ref_lo.shape or hi.shape != ref_hi.shape:
            raise PairedTopologyMismatch(
                f"Q-box shape mismatch: {names[0]} {ref_lo.shape} vs {name} {lo.shape}"
            )
        if not (
            np.allclose(lo, ref_lo, atol=_Q_BOX_ATOL, rtol=0.0)
            and np.allclose(hi, ref_hi, atol=_Q_BOX_ATOL, rtol=0.0)
        ):
            raise PairedTopologyMismatch(
                f"certificate Q boxes differ: {names[0]} "
                f"[{ref_lo.tolist()}, {ref_hi.tolist()}] vs {name} "
                f"[{lo.tolist()}, {hi.tolist()}]"
            )


def _inset_output_space(space: OutputSpace, inset_fraction: float) -> OutputSpace:
    """Return a chart whose lattice samples stay strictly inside the box."""
    if inset_fraction == 0.0:
        return space
    if not np.isfinite(inset_fraction) or inset_fraction < 0.0 or inset_fraction >= 0.5:
        raise ValueError(
            f"inset_fraction must be in [0, 0.5), got {inset_fraction}"
        )
    axes = []
    for axis in space.axes:
        if axis.lower is None or axis.upper is None:
            raise PairedTopologyMismatch(
                "paired Q lattice requires bounded output axes"
            )
        lo = float(axis.lower)
        hi = float(axis.upper)
        inset = float(inset_fraction) * (hi - lo)
        inner_lo = lo + inset
        inner_hi = hi - inset
        if inner_hi <= inner_lo:
            raise PairedTopologyMismatch(
                "inset emptied the shared Q box on an output axis"
            )
        axes.append(replace(axis, lower=inner_lo, upper=inner_hi))
    return OutputSpace(axes=tuple(axes))


def _rejected_nodes(graph: EmbeddedPlanningGraph) -> tuple[int, ...]:
    return tuple(
        int(i) for i, valid in enumerate(graph.valid_nodes) if not bool(valid)
    )


def build_paired_q_planning_graph(
    branches: Mapping[str, OperatingBranch],
    *,
    q_shape: tuple[int, ...],
    connectivity: LatticeConnectivity | str = LatticeConnectivity.AXIS_ALIGNED,
    inset_fraction: float = 0.0,
) -> PairedQPlanningGraph:
    """Build one shared-Q planning graph and embed each mechanism in U.

    Parameters
    ----------
    branches :
        Named certified operating branches. At least two are required.
    q_shape :
        Uniform-Q lattice shape, one integer per output axis.
    connectivity :
        Lattice adjacency stencil. Default is Version 2 axis-aligned.
    inset_fraction :
        Fraction of each certified Q span excluded at each end. Zero keeps
        the certificate box. A positive inset is a shared sample domain,
        not an intersection of two independently built graphs.

    Returns
    -------
    PairedQPlanningGraph
        Shared topology plus per-arm embeddings.

    Raises
    ------
    ValueError
        If fewer than two branches are supplied, or the inset is invalid.
    PairedTopologyMismatch
        If Q boxes or inverse-validity masks differ. Does not intersect
        disagreeing graphs.
    """
    if len(branches) < 2:
        raise ValueError("build_paired_q_planning_graph requires at least two branches")
    _require_matching_q_boxes(branches)
    names = list(branches)
    reference = branches[names[0]]
    lattice_space = _inset_output_space(reference.output_space, inset_fraction)
    shared = UniformOutputLattice.from_output_space(
        lattice_space,
        q_shape,
        connectivity=connectivity,
    )
    arms: dict[str, EmbeddedPlanningGraph] = {}
    for name, branch in branches.items():
        arms[name] = EmbeddedPlanningGraph.from_output_lattice(shared, branch)

    ref_graph = arms[names[0]]
    for name in names[1:]:
        other = arms[name]
        if not np.array_equal(ref_graph.valid_nodes, other.valid_nodes):
            rejected = {
                names[0]: _rejected_nodes(ref_graph),
                name: _rejected_nodes(other),
            }
            raise PairedTopologyMismatch(
                "valid_nodes masks differ across the pair: "
                f"{names[0]} rejected {rejected[names[0]]} vs "
                f"{name} rejected {rejected[name]}"
            )
        try:
            assert_shared_q_pair_invariants(ref_graph, other)
        except SharedQPairInvariantError as exc:
            raise PairedTopologyMismatch(str(exc)) from exc

    return PairedQPlanningGraph(
        topology=shared.topology,
        q_by_node=shared.q_nodes,
        x_by_node=None,
        arms=arms,
        rejected_candidates={name: () for name in names},
    )
