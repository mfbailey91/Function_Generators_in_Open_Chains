"""Golden Version 1 graph validity and connectivity checks."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from inequality_mechanisms.graphs import ConstrainedInputGraph, PeriodicGrid2D
from inequality_mechanisms.mechanisms.base import Mechanism
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


def test_unit_gearbox_all_nodes_valid_and_connected() -> None:
    fixture = _load("fixture_unit_gearbox.json")
    graph = _build_graph(fixture)
    assert graph.valid_node_count == fixture["expected"]["valid_node_count"]
    assert graph.valid_node_count == graph.grid.node_count
    start = fixture["start"]
    seen = {start}
    queue: deque[int] = deque([start])
    while queue:
        u = queue.popleft()
        i0, i1 = graph.grid.indices_from_id(u)
        for j0, j1 in graph.neighbors(i0, i1):
            v = graph.grid.node_id(j0, j1)
            if v not in seen:
                seen.add(v)
                queue.append(v)
    assert len(seen) == graph.valid_node_count


def test_fourbar_start_goal_in_same_component() -> None:
    fixture = _load("fixture_fourbar.json")
    graph = _build_graph(fixture)
    start = fixture["start"]
    goal = fixture["goal"]
    assert graph.node_is_valid_id(start)
    assert graph.node_is_valid_id(goal)
    seen = {start}
    queue: deque[int] = deque([start])
    while queue:
        u = queue.popleft()
        i0, i1 = graph.grid.indices_from_id(u)
        for j0, j1 in graph.neighbors(i0, i1):
            v = graph.grid.node_id(j0, j1)
            if v not in seen:
                seen.add(v)
                queue.append(v)
    assert goal in seen
