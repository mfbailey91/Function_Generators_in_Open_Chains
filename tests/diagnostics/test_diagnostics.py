"""Numerical assertions paired with Sprint 3 diagnostic visuals."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from inequality_mechanisms.diagnostics.bundle import generate_diagnostics_bundle
from inequality_mechanisms.diagnostics.mapping import mapping_curve
from inequality_mechanisms.diagnostics.plots import (
    basin_metrics,
    classify_lattice_edge,
    input_euclidean_cost,
    uniform_edge_cost,
)
from inequality_mechanisms.graphs.edge_trace import build_edge_trace, winding_number
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph, edge_is_valid
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox
from inequality_mechanisms.mechanisms.population import (
    limits_from_fourbar_follower_ranges,
)
from inequality_mechanisms.search import dijkstra
from inequality_mechanisms.spaces import OutputSpace

_CR = (1.0, 2.5, 2.0, 2.0)


def _fourbar_graph(shape=(16, 16), edge_samples=17) -> ConstrainedInputGraph:
    mech = IndependentFourBars.from_lengths([_CR, _CR], branch=1)
    limits = limits_from_fourbar_follower_ranges(mech, n_samples=181)
    space = OutputSpace.from_limits(limits)
    grid = PeriodicGrid2D(shape, wrap=(True, True))
    return ConstrainedInputGraph(
        grid, mech, limits, edge_samples=edge_samples, output_space=space
    )


class TestMappingAtlasAssertions:
    def test_raw_may_jump_canonical_continuous_and_in_limits(self) -> None:
        mech = IndependentFourBars.from_lengths([_CR], branch=1).bars[0]
        q_min, q_max = __import__(
            "inequality_mechanisms.mechanisms.population", fromlist=["follower_range"]
        ).follower_range(mech, n_samples=361)
        space = OutputSpace.bounded_revolute_box([q_min], [q_max])
        u = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
        curve = mapping_curve(
            lambda uu: float(mech.input_to_output([uu])[0]),
            space,
            u,
            axis=0,
        )
        can_jumps = np.abs(np.diff(curve["canonical"]))
        # Pass: canonical stays continuous even if raw jumps.
        assert float(np.max(can_jumps)) < np.pi
        # Pass: every sample that ``contains`` accepts is inside the closed box.
        for c in curve["canonical"]:
            if space.contains([float(c)]):
                assert q_min - 1e-9 <= float(c) <= q_max + 1e-9
        jac = np.array(
            [float(mech.output_jacobian([uu])[0, 0]) for uu in curve["u"]],
            dtype=np.float64,
        )
        mask = np.abs(jac) > 1e-3
        assert np.mean(np.sign(curve["dq_du"][mask]) == np.sign(jac[mask])) > 0.9

    def test_example_seam_winding_sequence(self) -> None:
        lo = np.deg2rad(170.0)
        hi = np.deg2rad(190.0)
        space = OutputSpace.bounded_revolute_box([lo], [hi])
        raws = np.deg2rad([170.0, 175.0, 179.0, -178.0, -173.0])
        cans = [float(space.canonicalize([r])[0]) for r in raws]
        winds = [winding_number(float(r), c) for r, c in zip(raws, cans, strict=True)]
        assert cans == pytest.approx(np.deg2rad([170.0, 175.0, 179.0, 182.0, 187.0]), abs=1e-9)
        assert winds == [0, 0, 0, 1, 1]


class TestEdgeMicroscopeAssertions:
    def test_trace_matches_validator_and_graph_cost(self) -> None:
        graph = _fourbar_graph((12, 12), edge_samples=9)
        edge = next(graph.iter_edges())
        i0, i1 = graph.grid.indices_from_id(edge[0])
        j0, j1 = graph.grid.indices_from_id(edge[1])
        ua = graph.grid.coordinates(i0, i1)
        ub = graph.grid.coordinates(j0, j1)
        trace = graph.edge_trace(i0, i1, j0, j1)
        assert trace.is_valid is True
        assert edge_is_valid(
            graph.mechanism,
            graph.limits,
            ua,
            ub,
            n_samples=graph.edge_samples,
            periodic_axes=graph.mechanism.periodic_axes(),
            output_space=graph.output_space,
        )
        assert graph.edge_is_valid(i0, i1, j0, j1)
        assert trace.total_endpoint_cost == pytest.approx(
            graph.output_displacement(ua, ub), abs=1e-12
        )

    def test_rejected_edge_reports_first_invalid_sample(self) -> None:
        graph = _fourbar_graph((12, 12), edge_samples=9)
        found = False
        for node in graph.iter_valid_nodes():
            i0, i1 = node.indices
            for j0, j1 in graph.grid.neighbors(i0, i1):
                if graph.edge_is_valid(i0, i1, j0, j1):
                    continue
                trace = graph.edge_trace(i0, i1, j0, j1)
                assert trace.is_valid is False
                assert trace.first_invalid_index is not None
                assert trace.first_invalid_reason in ("assembly", "limits")
                # Shared builder: free function agrees.
                ua = graph.grid.coordinates(i0, i1)
                ub = graph.grid.coordinates(j0, j1)
                other = build_edge_trace(
                    graph.mechanism,
                    graph.limits,
                    ua,
                    ub,
                    n_samples=graph.edge_samples,
                    output_space=graph.output_space,
                )
                assert other.first_invalid_index == trace.first_invalid_index
                found = True
                break
            if found:
                break
        assert found

    def test_inspect_output_serializable(self) -> None:
        graph = _fourbar_graph((8, 8), edge_samples=5)
        u = next(graph.iter_valid_nodes()).coordinates
        diag = graph.inspect_output(u)
        payload = diag.to_dict()
        assert payload["assembly_valid"] is True
        assert len(payload["axes"]) == graph.output_space.dim
        assert payload["axes"][0]["canonical"] is not None


class TestEdgeDensityAssertions:
    def test_edge_sets_nested(self) -> None:
        levels = (5, 9, 17, 33)
        sets = {}
        for n in levels:
            g = _fourbar_graph((10, 10), edge_samples=n)
            sets[n] = set(g.iter_edges())
        assert sets[33] <= sets[17] <= sets[9] <= sets[5]

    def test_gearbox_interior_invariant(self) -> None:
        mech_limits = limits_from_fourbar_follower_ranges(
            IndependentFourBars.from_lengths([_CR, _CR], branch=1), n_samples=181
        )
        space = OutputSpace.from_limits(mech_limits)
        grid = PeriodicGrid2D((10, 10), wrap=(True, True))
        interiors = []
        for n in (5, 9, 17, 33):
            g = ConstrainedInputGraph(
                grid,
                UnitGearbox(dim=2),
                mech_limits,
                edge_samples=n,
                output_space=space,
            )
            interiors.append(
                {
                    e
                    for e in g.iter_edges()
                    if classify_lattice_edge(g.grid, *e) == "interior"
                }
            )
        assert interiors[0] == interiors[1] == interiors[2] == interiors[3]


class TestSearchBasinAssertions:
    def test_eta_beta_and_expanded_recorded(self) -> None:
        graph = _fourbar_graph((12, 12), edge_samples=9)
        nodes = [n.node_id for n in graph.iter_valid_nodes()]
        start, goal = nodes[0], nodes[-1]
        for cfn in (None, uniform_edge_cost, input_euclidean_cost(graph)):
            result = dijkstra(graph, start, goal, edge_cost=cfn, record_expanded=True)
            if not result.found:
                continue
            assert len(result.expanded_nodes) == result.n_expanded
            from inequality_mechanisms.search.cost_to_go import reverse_dijkstra

            costs = reverse_dijkstra(graph, start, edge_cost=cfn).costs
            eta, beta = basin_metrics(
                costs, c_star=result.cost, n_expanded=result.n_expanded
            )
            assert 0.0 <= eta <= 1.0 + 1e-12
            assert 0.0 <= beta <= 1.0 + 1e-12
            break


class TestBundleCanvas:
    def test_generate_bundle_writes_canvas(self, tmp_path: Path) -> None:
        traces = generate_diagnostics_bundle(tmp_path, shape=(12, 12))
        expected = [
            "mapping_axis_0.png",
            "mapping_axis_1.png",
            "topology.png",
            "edge_density_differences.png",
            "search_basin_uniform.png",
            "search_basin_input_cost.png",
            "search_basin_output_cost.png",
            "task_preimages.png",
            "traces.json",
            "index.html",
        ]
        for name in expected:
            path = tmp_path / name
            assert path.is_file(), name
            assert path.stat().st_size > 0
        # At least one microscope fixture should exist.
        assert any((tmp_path / f"edge_{k}.png").is_file() for k in (
            "interior",
            "input_seam",
            "output_seam",
            "rejected_by_limit",
        ))
        data = json.loads((tmp_path / "traces.json").read_text(encoding="utf-8"))
        assert data["edge_density"]["nested"] is True
        assert "basin_output_cost" in data
        assert traces["edge_density"]["nested"] is True
