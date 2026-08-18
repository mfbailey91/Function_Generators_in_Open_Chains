"""V4.2B Phase 1: one shared paired-Q planning topology (V4-224)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms.operating_branch import unit_gearbox_branch


def _edge_ids(graph: object) -> tuple[tuple[int, int], ...]:
    n = int(graph.node_count)  # type: ignore[attr-defined]
    edges: list[tuple[int, int]] = []
    for node_id in range(n):
        if not graph.node_is_valid(node_id):  # type: ignore[attr-defined]
            continue
        for neighbor in graph.neighbors(node_id):  # type: ignore[attr-defined]
            if node_id < int(neighbor):
                edges.append((int(node_id), int(neighbor)))
    return tuple(sorted(edges))


def _valid_node_ids(graph: object) -> tuple[int, ...]:
    n = int(graph.node_count)  # type: ignore[attr-defined]
    return tuple(i for i in range(n) if graph.node_is_valid(i))  # type: ignore[attr-defined]


def test_shared_weight_note_is_not_the_primary_fairness_api() -> None:
    from inequality_mechanisms.experiments.v4 import span_controlled_visual_audit
    from inequality_mechanisms.graphs.paired_q_planning import build_paired_q_planning_graph

    assert hasattr(span_controlled_visual_audit, "_shared_weight_note")
    assert callable(build_paired_q_planning_graph)
    assert build_paired_q_planning_graph is not span_controlled_visual_audit._shared_weight_note


def test_paired_smoke_graph_has_identical_node_and_edge_ids() -> None:
    from inequality_mechanisms.graphs.paired_q_planning import build_paired_q_planning_graph

    fourbar = unit_gearbox_branch(
        2, input_lower=[-0.5, -0.5], input_upper=[0.5, 0.5], name="fourbar"
    )
    gearbox = unit_gearbox_branch(
        2, input_lower=[-0.5, -0.5], input_upper=[0.5, 0.5], name="gearbox"
    )
    paired = build_paired_q_planning_graph(
        {"fourbar": fourbar, "gearbox": gearbox},
        q_shape=(3, 3),
    )
    fb = paired.arms["fourbar"]
    gb = paired.arms["gearbox"]
    assert _valid_node_ids(fb) == _valid_node_ids(gb)
    assert _edge_ids(fb) == _edge_ids(gb)
    np.testing.assert_allclose(fb.q_nodes, gb.q_nodes, atol=1e-12)


def test_paired_topology_mismatch_is_typed() -> None:
    from inequality_mechanisms.graphs.paired_q_planning import (
        PairedTopologyMismatch,
        build_paired_q_planning_graph,
    )

    fourbar = unit_gearbox_branch(
        2, input_lower=[-0.5, -0.5], input_upper=[0.5, 0.5], name="fourbar"
    )
    gearbox = unit_gearbox_branch(
        2, input_lower=[-1.5, -1.5], input_upper=[1.5, 1.5], name="gearbox"
    )
    with pytest.raises(PairedTopologyMismatch) as info:
        build_paired_q_planning_graph(
            {"fourbar": fourbar, "gearbox": gearbox},
            q_shape=(3, 3),
        )
    assert getattr(info.value, "failure_code", "paired_topology_mismatch") == (
        "paired_topology_mismatch"
    )


def test_mounted_span_cases_share_topology_at_smoke_shape() -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import CANONICAL_REPO_ROOT
    from inequality_mechanisms.experiments.span_cases import (
        generate_span_cases,
        realize_mounted_span_case,
    )
    from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
        load_locked_v3_6d_registry,
    )
    from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
        DEFAULT_CONFIG_REL,
        load_span_atlas_config,
    )
    from inequality_mechanisms.graphs.paired_q_planning import (
        build_paired_q_planning_graph,
    )

    config = load_span_atlas_config(CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL)
    registry = load_locked_v3_6d_registry(config)
    for case in generate_span_cases():
        realized = realize_mounted_span_case(case, registry)
        paired = build_paired_q_planning_graph(
            {"fourbar": realized.fourbar, "gearbox": realized.gearbox},
            q_shape=(3, 3),
            inset_fraction=0.01,
        )
        fb = paired.arms["fourbar"]
        gb = paired.arms["gearbox"]
        assert _valid_node_ids(fb) == _valid_node_ids(gb)
        assert _edge_ids(fb) == _edge_ids(gb)
        np.testing.assert_allclose(fb.q_nodes, gb.q_nodes, atol=1e-12)
        np.testing.assert_array_equal(fb.q_nodes, paired.q_by_node)
