"""Frozen shared-Q sampled roadmap for the V3-637 metric-isolation diagnostic.

Native PRM samples and connects in ``U``, so it cannot isolate “same graph,
different actuator metric.” This module freezes one reusable Q sample cloud
and undirected k-NN adjacency, then inverse-lifts each vertex through a
certified operating branch. Edge validity and integrated actuator costs are
mechanism-specific; the frozen ``(V_Q, E_Q)`` are not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.graphs.pair_invariants import SharedQPairInvariantError
from inequality_mechanisms.graphs.sampling import (
    SamplingDomain,
    TransitionParameterization,
)
from inequality_mechanisms.mechanisms.operating_branch import (
    BranchInverseError,
    OperatingBranch,
)
from inequality_mechanisms.spaces.output_space import OutputSpace

BANK_MODE_REUSABLE = "reusable"


def _lock_array(arr: NDArray[Any]) -> NDArray[Any]:
    """Return a contiguous, read-only copy of ``arr``."""
    out = np.array(arr, copy=True)
    out.flags.writeable = False
    return out


def q_knn_indices(
    query_q: NDArray[np.float64],
    q_samples: NDArray[np.float64],
    *,
    k_neighbors: int,
    max_edge_q: float,
    skip_index: int | None = None,
) -> tuple[int, ...]:
    """Return up to ``k_neighbors`` Q-nearest sample indices within ``max_edge_q``.

    Tie-breaking uses stable argsort so the same ``(query_q, q_samples)`` pair
    yields the same neighbor ids on every mechanism.
    """
    q = np.asarray(query_q, dtype=np.float64)
    samples = np.asarray(q_samples, dtype=np.float64)
    if samples.ndim != 2:
        raise ValueError("q_samples must have shape (n_samples, output_dim)")
    if q.ndim != 1 or q.shape[0] != samples.shape[1]:
        raise ValueError(
            f"query_q shape {q.shape} must be ({samples.shape[1]},)"
        )
    k = int(k_neighbors)
    if k < 1:
        raise ValueError("k_neighbors must be >= 1")
    radius = float(max_edge_q)
    if not np.isfinite(radius) or radius <= 0.0:
        raise ValueError("max_edge_q must be finite and positive")

    dists = np.linalg.norm(samples - q, axis=1)
    if skip_index is not None:
        dists = np.array(dists, copy=True)
        dists[int(skip_index)] = np.inf
    order = np.argsort(dists, kind="stable")
    chosen: list[int] = []
    for j in order:
        if len(chosen) >= k:
            break
        d = float(dists[int(j)])
        if not np.isfinite(d) or d > radius:
            continue
        chosen.append(int(j))
    return tuple(chosen)


def _undirected_knn_edges(
    q_samples: NDArray[np.float64],
    *,
    k_neighbors: int,
    max_edge_q: float,
) -> tuple[tuple[int, int], ...]:
    """Union of per-sample Q k-NN, stored as sorted undirected ``(i, j)`` with ``i < j``."""
    n = int(q_samples.shape[0])
    edges: set[tuple[int, int]] = set()
    for i in range(n):
        for j in q_knn_indices(
            q_samples[i],
            q_samples,
            k_neighbors=k_neighbors,
            max_edge_q=max_edge_q,
            skip_index=i,
        ):
            a, b = (i, j) if i < j else (j, i)
            edges.add((a, b))
    return tuple(sorted(edges))


def _adjacency_from_edges(
    n_nodes: int, edges: tuple[tuple[int, int], ...]
) -> tuple[tuple[int, ...], ...]:
    adj: list[list[int]] = [[] for _ in range(int(n_nodes))]
    for a, b in edges:
        if a == b:
            raise ValueError(f"self-loop is not allowed: {(a, b)}")
        if not (0 <= a < n_nodes and 0 <= b < n_nodes):
            raise ValueError(f"edge {(a, b)} outside node range {n_nodes}")
        adj[a].append(int(b))
        adj[b].append(int(a))
    return tuple(tuple(sorted(nbs)) for nbs in adj)


@dataclass(frozen=True, slots=True)
class FrozenQSampleBank:
    """One deterministic reusable Q sample cloud and undirected adjacency.

    Attributes
    ----------
    q_samples :
        Frozen ``(n_samples, output_dim)`` sample array. Shared by every
        mechanism embedding of this bank.
    edges :
        Undirected unique pairs ``(i, j)`` with ``i < j``. Identical across
        mechanisms; validity does not mutate this list.
    seed, n_samples, k_neighbors, max_edge_q :
        Declared sampler settings.
    q_lower, q_upper :
        Closed output-box bounds copied from the shared ``OutputSpace``.
    bank_mode :
        ``reusable`` for the task-independent closeout bank.
    """

    q_samples: NDArray[np.float64]
    edges: tuple[tuple[int, int], ...]
    seed: int
    n_samples: int
    k_neighbors: int
    max_edge_q: float
    q_lower: tuple[float, ...]
    q_upper: tuple[float, ...]
    bank_mode: str = BANK_MODE_REUSABLE
    frozen_adjacency: tuple[tuple[int, ...], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "q_samples", _lock_array(self.q_samples))
        edges = tuple((int(a), int(b)) for a, b in self.edges)
        object.__setattr__(self, "edges", edges)
        n = int(self.n_samples)
        if self.q_samples.ndim != 2 or self.q_samples.shape[0] != n:
            raise ValueError(
                "q_samples shape must be (n_samples, output_dim), got "
                f"{self.q_samples.shape} with n_samples={n}"
            )
        if self.bank_mode != BANK_MODE_REUSABLE:
            raise ValueError(
                f"unsupported bank_mode {self.bank_mode!r}; V3-637 freezes "
                f"{BANK_MODE_REUSABLE!r}"
            )
        object.__setattr__(
            self, "frozen_adjacency", _adjacency_from_edges(n, edges)
        )

    def provenance_dict(self) -> dict[str, Any]:
        """Serializable bank settings for closeout config / result metrics."""
        return {
            "seed": int(self.seed),
            "n_samples": int(self.n_samples),
            "k_neighbors": int(self.k_neighbors),
            "max_edge_q": float(self.max_edge_q),
            "bank_mode": str(self.bank_mode),
            "q_lower": list(self.q_lower),
            "q_upper": list(self.q_upper),
            "n_edges": len(self.edges),
        }


def freeze_reusable_q_sample_bank(
    output_space: OutputSpace,
    *,
    n_samples: int,
    k_neighbors: int,
    max_edge_q: float,
    seed: int,
    bank_mode: str = BANK_MODE_REUSABLE,
) -> FrozenQSampleBank:
    """Sample ``n_samples`` points uniformly in the shared output box and freeze k-NN.

    The sample array and undirected edge list are generated once. Mechanism
    embeddings must reuse this object (or bitwise-identical arrays) rather than
    resampling per arm.
    """
    n = int(n_samples)
    if n < 2:
        raise ValueError("n_samples must be >= 2")
    dim = int(output_space.dim)
    lo = np.asarray(output_space.lower, dtype=np.float64)
    hi = np.asarray(output_space.upper, dtype=np.float64)
    if lo.shape != (dim,) or hi.shape != (dim,):
        raise ValueError("output_space bounds must match output_space.dim")
    rng = np.random.default_rng(int(seed))
    q_samples = rng.uniform(lo, hi, size=(n, dim)).astype(np.float64)
    edges = _undirected_knn_edges(
        q_samples, k_neighbors=int(k_neighbors), max_edge_q=float(max_edge_q)
    )
    return FrozenQSampleBank(
        q_samples=q_samples,
        edges=edges,
        seed=int(seed),
        n_samples=n,
        k_neighbors=int(k_neighbors),
        max_edge_q=float(max_edge_q),
        q_lower=tuple(float(x) for x in lo),
        q_upper=tuple(float(x) for x in hi),
        bank_mode=str(bank_mode),
    )


@dataclass(frozen=True)
class SampledQRoadmapGraph:
    """Mechanism embedding of a frozen shared-Q sample bank.

    Node identity and frozen adjacency live in ``Q``. Each valid node carries
    the unique certified-branch inverse in ``U``. Satisfies
    :class:`~inequality_mechanisms.search.protocol.SearchGraph`.
    """

    bank: FrozenQSampleBank
    branch: OperatingBranch
    u_nodes: NDArray[np.float64]
    valid_nodes: NDArray[np.bool_]

    def __post_init__(self) -> None:
        object.__setattr__(self, "u_nodes", _lock_array(self.u_nodes))
        object.__setattr__(
            self, "valid_nodes", _lock_array(np.asarray(self.valid_nodes, dtype=np.bool_))
        )
        n = int(self.bank.n_samples)
        input_dim = int(self.branch.mechanism.input_dim)
        output_dim = int(self.branch.mechanism.output_dim)
        if self.bank.q_samples.shape != (n, output_dim):
            raise ValueError(
                "bank q_samples shape must match branch output_dim, got "
                f"{self.bank.q_samples.shape} vs ({n}, {output_dim})"
            )
        if self.u_nodes.shape != (n, input_dim):
            raise ValueError(
                f"u_nodes shape must be ({n}, {input_dim}), got {self.u_nodes.shape}"
            )
        if self.valid_nodes.shape != (n,):
            raise ValueError(
                f"valid_nodes shape must be ({n},), got {self.valid_nodes.shape}"
            )

    @property
    def q_nodes(self) -> NDArray[np.float64]:
        """Frozen Q samples; the same array object as ``bank.q_samples``."""
        return self.bank.q_samples

    @property
    def edges(self) -> tuple[tuple[int, int], ...]:
        """Frozen undirected edge list (not mutated by inverse failure)."""
        return self.bank.edges

    @property
    def node_count(self) -> int:
        return int(self.bank.n_samples)

    @property
    def sampling_domain(self) -> SamplingDomain:
        return SamplingDomain.OUTPUT

    @property
    def transition_parameterization(self) -> TransitionParameterization:
        return TransitionParameterization.OUTPUT_LINEAR

    def node_is_valid(self, node_id: int) -> bool:
        if node_id < 0 or node_id >= self.node_count:
            raise ValueError(f"node_id out of range: {node_id}")
        return bool(self.valid_nodes[node_id])

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        """Valid frozen neighbors of ``node_id`` (deterministic order)."""
        if node_id < 0 or node_id >= self.node_count:
            raise ValueError(f"node_id out of range: {node_id}")
        return tuple(
            nb
            for nb in self.bank.frozen_adjacency[node_id]
            if self.valid_nodes[nb]
        )

    def q_state(self, node_id: int) -> NDArray[np.float64]:
        if node_id < 0 or node_id >= self.node_count:
            raise ValueError(f"node_id out of range: {node_id}")
        return np.array(self.q_nodes[node_id], copy=True)

    def u_state(self, node_id: int) -> NDArray[np.float64]:
        if node_id < 0 or node_id >= self.node_count:
            raise ValueError(f"node_id out of range: {node_id}")
        return np.array(self.u_nodes[node_id], copy=True)


def embed_sampled_q_roadmap(
    bank: FrozenQSampleBank, branch: OperatingBranch
) -> SampledQRoadmapGraph:
    """Inverse-lift each frozen Q sample through ``branch`` without resampling."""
    dim_q = int(branch.mechanism.output_dim)
    if bank.q_samples.shape[1] != dim_q:
        raise ValueError(
            f"bank output_dim {bank.q_samples.shape[1]} must match branch "
            f"output_dim {dim_q}"
        )
    n = int(bank.n_samples)
    u_nodes = np.full((n, branch.mechanism.input_dim), np.nan, dtype=np.float64)
    valid_nodes = np.zeros(n, dtype=np.bool_)
    for node_id in range(n):
        try:
            u_nodes[node_id] = branch.inverse(bank.q_samples[node_id])
            valid_nodes[node_id] = True
        except BranchInverseError:
            continue
    return SampledQRoadmapGraph(
        bank=bank,
        branch=branch,
        u_nodes=u_nodes,
        valid_nodes=valid_nodes,
    )


def embed_paired_sampled_q_roadmaps(
    bank: FrozenQSampleBank,
    branches: dict[str, OperatingBranch],
) -> dict[str, SampledQRoadmapGraph]:
    """Embed every paired branch on ``bank`` and fail closed if ``V_Q, E_Q`` diverge."""
    graphs = {
        name: embed_sampled_q_roadmap(bank, branch)
        for name, branch in branches.items()
    }
    names = list(graphs)
    for other in names[1:]:
        assert_identical_sampled_q_graphs(graphs[names[0]], graphs[other])
    return graphs


def assert_identical_sampled_q_graphs(
    graph_a: SampledQRoadmapGraph,
    graph_b: SampledQRoadmapGraph,
) -> None:
    """Require identical frozen ``V_Q`` and ``E_Q`` across a mechanism pair."""
    failures: list[str] = []
    if graph_a.bank is not graph_b.bank:
        if not np.array_equal(graph_a.q_nodes, graph_b.q_nodes):
            failures.append("q_samples are not bitwise identical")
        if graph_a.edges != graph_b.edges:
            failures.append("frozen undirected edge lists differ")
        pa = graph_a.bank.provenance_dict()
        pb = graph_b.bank.provenance_dict()
        for key in ("seed", "n_samples", "k_neighbors", "max_edge_q", "bank_mode"):
            if pa[key] != pb[key]:
                failures.append(f"bank {key} mismatch: {pa[key]!r} vs {pb[key]!r}")
    if graph_a.bank.frozen_adjacency != graph_b.bank.frozen_adjacency:
        failures.append("frozen adjacency lists differ")
    if failures:
        raise SharedQPairInvariantError(
            "shared-Q sampled-roadmap pair invariant failed: "
            + "; ".join(failures)
        )
