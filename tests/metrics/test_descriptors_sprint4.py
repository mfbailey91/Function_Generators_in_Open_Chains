"""Unit tests for mechanism/graph descriptors (S4-09)."""

from __future__ import annotations

import math

import pytest

from inequality_mechanisms.graphs import ConstrainedInputGraph, PeriodicGrid2D
from inequality_mechanisms.mechanisms import UnitGearbox
from inequality_mechanisms.metrics.descriptors import (
    correlate_descriptors,
    graph_descriptors,
    mechanism_descriptors,
)
from inequality_mechanisms.spaces import OutputJointLimits


def test_mechanism_descriptors_gearbox() -> None:
    mech = UnitGearbox(dim=2)
    desc = mechanism_descriptors(mech, n_samples=21)
    assert desc["n_jacobian_samples"] > 0
    assert math.isfinite(float(desc["gain_mean"]))
    assert float(desc["gain_mean"]) >= 0.0


def test_graph_descriptors_unit() -> None:
    grid = PeriodicGrid2D((5, 5), ranges=((0.0, 5.0), (0.0, 5.0)), wrap=(False, False))
    mech = UnitGearbox(dim=2)
    limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[5.0, 5.0])
    graph = ConstrainedInputGraph(grid, mech, limits)
    start = graph.grid.node_id(0, 0)
    goal = graph.grid.node_id(3, 2)
    desc = graph_descriptors(
        graph,
        cost_type="uniform",
        start=start,
        goal=goal,
        c_star=5.0,
        n_expanded=10,
    )
    assert desc["n_valid_nodes"] == 25
    assert desc["n_reachable_nodes"] > 0
    assert desc["shortest_unweighted_path_length"] == 5


def test_correlate_descriptors() -> None:
    rows = [
        {"n_expanded": 10.0, "beta": 0.1, "rho_epsilon": 0.2},
        {"n_expanded": 20.0, "beta": 0.2, "rho_epsilon": 0.3},
        {"n_expanded": 30.0, "beta": 0.3, "rho_epsilon": 0.4},
    ]
    corr = correlate_descriptors(
        rows, x_fields=("beta", "rho_epsilon"), y_field="n_expanded"
    )
    assert corr["beta"] == pytest.approx(1.0)
