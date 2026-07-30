"""Golden Version 1 search regression fixtures (Sprint V2.0)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.graphs import ConstrainedInputGraph, PeriodicGrid2D
from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.search import astar, dijkstra
from inequality_mechanisms.spaces import OutputJointLimits

_DATA = Path(__file__).resolve().parent / "data"


def _load(name: str) -> dict:
    return json.loads((_DATA / name).read_text())


def _build_graph(fixture: dict) -> ConstrainedInputGraph:
    gcfg = fixture["graph"]
    shape = tuple(int(x) for x in gcfg["shape"])
    wrap = tuple(bool(x) for x in gcfg.get("wrap", [True, True]))
    ranges = gcfg.get("ranges")
    if ranges is None:
        grid = PeriodicGrid2D(shape, wrap=wrap)
    else:
        grid = PeriodicGrid2D(
            shape,
            ranges=tuple((float(a), float(b)) for a, b in ranges),
            wrap=wrap,
        )
    mech = Mechanism.from_dict(fixture["mechanism"])
    limits = OutputJointLimits.from_dict(fixture["limits"])
    return ConstrainedInputGraph(grid, mech, limits)


@pytest.mark.parametrize(
    "filename",
    ["fixture_unit_gearbox.json", "fixture_fourbar.json"],
)
def test_dijkstra_matches_golden_fixture(filename: str) -> None:
    fixture = _load(filename)
    graph = _build_graph(fixture)
    expected = fixture["expected"]
    assert graph.valid_node_count == expected["valid_node_count"]
    result = dijkstra(graph, fixture["start"], fixture["goal"])
    assert result.found is expected["found"]
    assert result.cost == pytest.approx(expected["cost"], rel=0.0, abs=1e-12)
    assert list(result.path) == expected["path"]
    assert result.n_expanded == expected["n_expanded"]
    assert result.n_generated == expected["n_generated"]
    assert result.n_stale == expected["n_stale"]
    assert result.n_path_edges == expected["n_path_edges"]


@pytest.mark.parametrize(
    "filename",
    ["fixture_unit_gearbox.json", "fixture_fourbar.json"],
)
def test_astar_matches_dijkstra_cost(filename: str) -> None:
    fixture = _load(filename)
    graph = _build_graph(fixture)
    expected = fixture["expected"]
    d = dijkstra(graph, fixture["start"], fixture["goal"])
    a = astar(graph, fixture["start"], fixture["goal"])
    assert d.found and a.found
    assert a.cost == pytest.approx(d.cost, rel=0.0, abs=1e-12)
    assert a.cost == pytest.approx(expected["astar_cost"], rel=0.0, abs=1e-12)
    assert a.path[0] == fixture["start"]
    assert a.path[-1] == fixture["goal"]
