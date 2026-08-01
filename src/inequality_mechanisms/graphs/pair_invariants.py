"""Shared uniform-Q pair invariants for Version 2 paired mechanism studies.

Sprint V2.8 / ADR-017 require that a four-bar and its span-matched gearbox
share one output topology. A mismatch is an invariant failure, not an
experimental result to average over.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.graphs.query_overlay import QueryOverlayGraph
from inequality_mechanisms.graphs.sampling import TransitionParameterization


class SharedQPairInvariantError(ValueError):
    """Raised when paired shared-Q graphs violate required invariants."""


@dataclass(frozen=True, slots=True)
class SharedQPairInvariantReport:
    """Diagnostic report for one shared-Q mechanism pair check.

    Attributes
    ----------
    passed :
        ``True`` when every required invariant holds.
    failures :
        Human-readable failure messages (empty when ``passed``).
    details :
        Structured counts and flags useful for serialization.
    """

    passed: bool
    failures: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to a plain dictionary."""
        return {
            "passed": self.passed,
            "failures": list(self.failures),
            "details": dict(self.details),
        }


def _adjacency(graph: EmbeddedPlanningGraph) -> dict[int, tuple[int, ...]]:
    return {
        node_id: tuple(graph.neighbors(node_id)) for node_id in range(graph.node_count)
    }


def assert_shared_q_pair_invariants(
    graph_a: EmbeddedPlanningGraph,
    graph_b: EmbeddedPlanningGraph,
    *,
    residual_tol: float = 1.0e-6,
    edge_n_samples: int = 17,
    require_identical_validity: bool = True,
    raise_on_failure: bool = True,
) -> SharedQPairInvariantReport:
    """Verify two embeddings share one uniform-Q topology and valid inverses.

    Parameters
    ----------
    graph_a, graph_b :
        Mechanism-specific embeddings that must reuse the same ``q`` lattice.
    residual_tol :
        Maximum allowed forward/inverse residual on accepted nodes and edge
        samples.
    edge_n_samples :
        Trace samples used when checking continuous inverses on edges.
    require_identical_validity :
        When ``True``, ``valid_nodes`` must match bitwise (Sprint V2.8 pair
        contract). When ``False``, only shared-topology checks apply.
    raise_on_failure :
        When ``True``, raise :class:`SharedQPairInvariantError` on failure.

    Returns
    -------
    SharedQPairInvariantReport
    """
    failures: list[str] = []
    details: dict[str, Any] = {
        "node_count_a": int(graph_a.node_count),
        "node_count_b": int(graph_b.node_count),
        "residual_tol": float(residual_tol),
    }

    if graph_a.topology is not graph_b.topology and (
        graph_a.topology.shape != graph_b.topology.shape
        or graph_a.topology.wrap != graph_b.topology.wrap
    ):
        failures.append("topology shape/wrap mismatch")
    elif graph_a.node_count != graph_b.node_count:
        failures.append(
            f"node_count mismatch: {graph_a.node_count} vs {graph_b.node_count}"
        )

    if not np.array_equal(graph_a.q_nodes, graph_b.q_nodes):
        failures.append("q_nodes are not bitwise identical")

    if (
        graph_a.transition_parameterization
        is not TransitionParameterization.OUTPUT_LINEAR
        or graph_b.transition_parameterization
        is not TransitionParameterization.OUTPUT_LINEAR
    ):
        failures.append("transition_parameterization must be output_linear for both")

    if require_identical_validity and not np.array_equal(
        graph_a.valid_nodes, graph_b.valid_nodes
    ):
        failures.append("valid_nodes masks differ across the pair")

    adj_a = _adjacency(graph_a)
    adj_b = _adjacency(graph_b)
    if adj_a != adj_b:
        failures.append("base adjacency differs across the pair")

    # Forward round-trip on every mutually valid node.
    max_residual = 0.0
    n_checked_nodes = 0
    for node_id in range(min(graph_a.node_count, graph_b.node_count)):
        if not (graph_a.valid_nodes[node_id] and graph_b.valid_nodes[node_id]):
            continue
        for graph in (graph_a, graph_b):
            q = graph.q_state(node_id)
            u = graph.u_state(node_id)
            if not np.all(np.isfinite(u)):
                failures.append(f"non-finite inverse at node {node_id}")
                continue
            q_rt = graph.branch.forward(u)
            resid = float(np.max(np.abs(q_rt - q)))
            max_residual = max(max_residual, resid)
            n_checked_nodes += 1
            if resid > residual_tol:
                failures.append(
                    f"forward round-trip residual {resid} exceeds tol at node {node_id}"
                )
                break
        if failures and failures[-1].startswith("forward round-trip"):
            # One representative node failure is enough for the report.
            break

    # Continuous inverse on a bounded sample of mutually valid edges.
    n_checked_edges = 0
    max_edge_residual = 0.0
    max_edges_to_check = 16
    for a, b in graph_a.topology.iter_edges():
        if n_checked_edges >= max_edges_to_check:
            break
        if not (
            graph_a.valid_nodes[a]
            and graph_a.valid_nodes[b]
            and graph_b.valid_nodes[a]
            and graph_b.valid_nodes[b]
        ):
            continue
        for graph in (graph_a, graph_b):
            trace = graph.edge_trace(a, b, n_samples=edge_n_samples)
            if not np.all(trace.branch_valid):
                failures.append(
                    f"edge ({a},{b}) has invalid inverse samples on "
                    f"{graph.branch.branch_id}"
                )
                break
            finite = trace.forward_inverse_residual[
                np.isfinite(trace.forward_inverse_residual)
            ]
            if finite.size:
                edge_resid = float(np.max(finite))
                max_edge_residual = max(max_edge_residual, edge_resid)
                if edge_resid > residual_tol:
                    failures.append(f"edge ({a},{b}) residual {edge_resid} exceeds tol")
                    break
        n_checked_edges += 1
        if failures and failures[-1].startswith("edge ("):
            break

    details.update(
        {
            "n_checked_nodes": n_checked_nodes,
            "n_checked_edges": n_checked_edges,
            "max_node_residual": max_residual,
            "max_edge_residual": max_edge_residual,
            "valid_node_count": int(np.sum(graph_a.valid_nodes)),
        }
    )
    # De-duplicate while preserving order.
    unique_failures = tuple(dict.fromkeys(failures))
    report = SharedQPairInvariantReport(
        passed=not unique_failures,
        failures=unique_failures,
        details=details,
    )
    if raise_on_failure and not report.passed:
        raise SharedQPairInvariantError(
            "shared-Q pair invariant failure: " + "; ".join(report.failures)
        )
    return report


def assert_identical_query_overlays(
    overlay_a: QueryOverlayGraph,
    overlay_b: QueryOverlayGraph,
    *,
    raise_on_failure: bool = True,
) -> SharedQPairInvariantReport:
    """Require identical exact-query node IDs and Q coordinates."""
    failures: list[str] = []
    if overlay_a.start_node_id != overlay_b.start_node_id:
        failures.append(
            "start_node_id mismatch: "
            f"{overlay_a.start_node_id} vs {overlay_b.start_node_id}"
        )
    if overlay_a.goal_node_id != overlay_b.goal_node_id:
        failures.append(
            "goal_node_id mismatch: "
            f"{overlay_a.goal_node_id} vs {overlay_b.goal_node_id}"
        )
    qa_s = np.asarray(overlay_a.q_state(overlay_a.start_node_id), dtype=np.float64)
    qb_s = np.asarray(overlay_b.q_state(overlay_b.start_node_id), dtype=np.float64)
    qa_g = np.asarray(overlay_a.q_state(overlay_a.goal_node_id), dtype=np.float64)
    qb_g = np.asarray(overlay_b.q_state(overlay_b.goal_node_id), dtype=np.float64)
    if not np.allclose(qa_s, qb_s, atol=0.0, rtol=0.0):
        # Exact query states should match bitwise when overlays share Q.
        if not np.array_equal(qa_s, qb_s):
            failures.append("exact start_q mismatch across pair overlays")
    if not np.array_equal(qa_g, qb_g):
        failures.append("exact goal_q mismatch across pair overlays")

    report = SharedQPairInvariantReport(
        passed=not failures,
        failures=tuple(failures),
        details={
            "start_node_id": overlay_a.start_node_id,
            "goal_node_id": overlay_a.goal_node_id,
        },
    )
    if raise_on_failure and not report.passed:
        raise SharedQPairInvariantError(
            "shared-Q query overlay invariant failure: " + "; ".join(report.failures)
        )
    return report
