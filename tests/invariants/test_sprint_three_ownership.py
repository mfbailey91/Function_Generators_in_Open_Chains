"""Sprint 3 residual ownership and nesting regressions (IM-044 / S3-05)."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.graphs.costs import (
    graph_output_euclidean_cost,
    output_euclidean_cost,
)
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox
from inequality_mechanisms.mechanisms.population import (
    limits_from_fourbar_follower_ranges,
)
from inequality_mechanisms.search import astar, dijkstra
from inequality_mechanisms.spaces import OutputSpace

_CR = (1.0, 2.5, 2.0, 2.0)
_SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "inequality_mechanisms"

# Graph-facing packages that must not call Mechanism.input_to_output directly.
_GRAPH_FACING_DIRS = (
    "search",
    "experiments",
    "visualization",
    "metrics",
)

# Explicit allow-list: labeled construction / graph-free helpers.
_ALLOWED_INPUT_TO_OUTPUT_FILES = {
    _SRC_ROOT / "graphs" / "validation.py",  # raw_output + configuration_is_valid
    _SRC_ROOT / "graphs" / "costs.py",  # graph-free output_euclidean_cost
}


def _paired_fixed(
    shape: tuple[int, int] = (16, 16),
    *,
    edge_samples: int = 17,
) -> tuple[ConstrainedInputGraph, ConstrainedInputGraph]:
    mech = IndependentFourBars.from_lengths([_CR, _CR], branch=1)
    limits = limits_from_fourbar_follower_ranges(mech, n_samples=181)
    space = OutputSpace.from_limits(limits)
    grid = PeriodicGrid2D(shape, wrap=(True, True))
    gearbox = ConstrainedInputGraph(
        grid,
        UnitGearbox(dim=2),
        limits,
        edge_samples=edge_samples,
        output_space=space,
    )
    fourbar = ConstrainedInputGraph(
        grid,
        mech,
        limits,
        edge_samples=edge_samples,
        output_space=space,
    )
    return gearbox, fourbar


def _edge_set(graph: ConstrainedInputGraph) -> set[tuple[int, int]]:
    return set(graph.iter_edges())


def _collect_input_to_output_call_sites() -> list[tuple[Path, int, str]]:
    """Return (path, lineno, attr_context) for ``*.input_to_output`` calls."""
    hits: list[tuple[Path, int, str]] = []
    for py in _SRC_ROOT.rglob("*.py"):
        if "mechanisms" in py.parts:
            continue  # mechanism-internal implementations permitted
        rel = py.relative_to(_SRC_ROOT)
        if rel.parts[0] not in _GRAPH_FACING_DIRS and rel.parts[0] != "graphs":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "input_to_output":
                hits.append((py, node.lineno, py.name))
    return hits


class TestSprint3Ownership:
    def test_output_equals_canonicalize_raw(self) -> None:
        _, fb = _paired_fixed((12, 12), edge_samples=9)
        node = next(fb.iter_valid_nodes())
        u = node.coordinates
        raw = fb.raw_output(u)
        assert fb.output(u) == pytest.approx(fb.output_space.canonicalize(raw))
        assert fb.output_at(u) == pytest.approx(fb.output(u))

    def test_output_displacement_matches_graph_free_helper(self) -> None:
        gb, _ = _paired_fixed((10, 10), edge_samples=9)
        nodes = list(gb.iter_valid_nodes())
        assert len(nodes) >= 2
        u_a = nodes[0].coordinates
        u_b = nodes[1].coordinates
        via_graph = gb.output_displacement(u_a, u_b)
        via_helper = output_euclidean_cost(
            gb.mechanism, u_a, u_b, output_space=gb.output_space
        )
        via_named = graph_output_euclidean_cost(gb, u_a, u_b)
        assert via_graph == pytest.approx(via_helper)
        assert via_named == pytest.approx(via_graph)

    def test_cost_and_heuristic_share_output_semantics(self) -> None:
        _, fb = _paired_fixed((12, 12), edge_samples=9)
        nodes = [n.node_id for n in fb.iter_valid_nodes()]
        assert len(nodes) >= 2
        start, goal = nodes[0], nodes[-1]
        d = dijkstra(fb, start, goal)
        a = astar(fb, start, goal)
        assert d.found == a.found
        if d.found:
            assert d.cost == pytest.approx(a.cost, abs=1e-9)

    def test_seam_samples_canonicalize_continuously_when_in_limits(self) -> None:
        lo = np.deg2rad(170.0)
        hi = np.deg2rad(190.0)
        space = OutputSpace.bounded_revolute_box([lo], [hi])
        q0 = space.canonicalize([np.deg2rad(179.0)])
        q1 = space.canonicalize([np.deg2rad(-178.0)])
        assert float(q0[0]) == pytest.approx(np.deg2rad(179.0), abs=1e-12)
        assert float(q1[0]) == pytest.approx(np.deg2rad(182.0), abs=1e-12)
        assert space.contains(q1)

    def test_seam_crossing_rejected_when_above_limit(self) -> None:
        lo = np.deg2rad(170.0)
        hi = np.deg2rad(181.0)
        space = OutputSpace.bounded_revolute_box([lo], [hi])
        q1 = space.canonicalize([np.deg2rad(-178.0)])
        assert float(q1[0]) == pytest.approx(np.deg2rad(182.0), abs=1e-12)
        assert not space.contains(q1)

    def test_actuator_wrap_uses_short_periodic_input_path(self) -> None:
        from inequality_mechanisms.graphs.validation import interpolate_input_segment

        u_a = np.array([2.0 * np.pi - 0.05, 0.0])
        u_b = np.array([0.05, 0.0])
        mid = interpolate_input_segment(
            u_a, u_b, 0.5, periodic_axes=(True, True)
        )
        # Short path stays near 0 / 2pi, not through pi.
        assert abs(float(mid[0]) - 0.0) < 0.2 or abs(float(mid[0]) - 2.0 * np.pi) < 0.2

    def test_graph_facing_modules_avoid_direct_input_to_output(self) -> None:
        hits = _collect_input_to_output_call_sites()
        unexpected = [
            (str(path.relative_to(_SRC_ROOT)), lineno)
            for path, lineno, _ in hits
            if path not in _ALLOWED_INPUT_TO_OUTPUT_FILES
        ]
        assert unexpected == [], (
            "graph-facing modules must not call input_to_output directly; "
            f"found {unexpected}. Route via ConstrainedInputGraph.raw_output "
            "/ output / output_displacement, or add an audited allow-list entry."
        )

    def test_allowed_helpers_still_label_raw_access(self) -> None:
        validation = (_SRC_ROOT / "graphs" / "validation.py").read_text(encoding="utf-8")
        costs = (_SRC_ROOT / "graphs" / "costs.py").read_text(encoding="utf-8")
        assert "Construction helper (IM-042 / IM-043)" in validation
        assert "Graph-free helper (IM-043)" in costs
        assert "def raw_output" in validation

    def test_edge_sets_nested_as_samples_increase(self) -> None:
        # Residual nesting check (full IM-047 sweeps denser grids later).
        e9 = _edge_set(_paired_fixed((10, 10), edge_samples=9)[1])
        e17 = _edge_set(_paired_fixed((10, 10), edge_samples=17)[1])
        e33 = _edge_set(_paired_fixed((10, 10), edge_samples=33)[1])
        assert e33 <= e17 <= e9

    def test_serialization_round_trip_preserves_output_space(self) -> None:
        gb, _ = _paired_fixed((8, 8), edge_samples=5)
        restored = OutputSpace.from_dict(gb.output_space.to_dict())
        assert restored.to_dict() == gb.output_space.to_dict()
        u = next(gb.iter_valid_nodes()).coordinates
        assert restored.canonicalize(gb.raw_output(u)) == pytest.approx(gb.output(u))
