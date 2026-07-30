"""Sprint Two invariant regression suite (IM-038)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.experiments.tasks import (
    default_snap_tol,
    generate_paired_tasks,
)
from inequality_mechanisms.graphs.costs import output_euclidean_cost
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox
from inequality_mechanisms.mechanisms.population import (
    follower_range,
    limits_from_fourbar_follower_ranges,
)
from inequality_mechanisms.search import astar, dijkstra, reverse_dijkstra
from inequality_mechanisms.search.heuristics import output_euclidean_heuristic
from inequality_mechanisms.search.v1_compat import _cached_outputs
from inequality_mechanisms.spaces import OutputSpace, lift_bounded_revolute

_CR = (1.0, 2.5, 2.0, 2.0)


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


class TestSprintTwoInvariants:
    def test_no_false_seam_jumps_in_q(self) -> None:
        bar = IndependentFourBars.from_lengths([_CR], branch=1).bars[0]
        q_min, q_max = follower_range(bar, n_samples=361)
        u = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
        lifted = bar.lifted_follower_curve(u, q_min=q_min, q_max=q_max)
        diffs = np.abs(np.diff(lifted))
        assert float(np.max(diffs)) < np.pi

    def test_dijkstra_astar_cost_agreement(self) -> None:
        gb, fb = _paired_fixed((12, 12), edge_samples=9)
        tasks = generate_paired_tasks(
            gb, fb, n_trials=3, rng=np.random.default_rng(0)
        )
        for task in tasks:
            for graph, pre in ((gb, task.gearbox), (fb, task.fourbar)):
                d = dijkstra(graph, pre.start_node_id, pre.goal_node_id)
                a = astar(graph, pre.start_node_id, pre.goal_node_id)
                assert d.found == a.found
                if d.found:
                    assert d.cost == pytest.approx(a.cost, abs=1e-9)

    def test_heuristic_admissible_default_metric(self) -> None:
        _, fb = _paired_fixed((10, 10), edge_samples=9)
        nodes = [n.node_id for n in fb.iter_valid_nodes()]
        assert len(nodes) >= 2
        goal = nodes[-1]
        ctg = reverse_dijkstra(fb, goal)
        output_of = _cached_outputs(fb)
        h = output_euclidean_heuristic(
            fb.mechanism,
            output_of(goal),
            output_of,
            output_space=fb.output_space,
        )
        for node_id, exact in ctg.costs.items():
            assert h(node_id) <= exact + 1e-9

    def test_shared_output_chart_for_limits(self) -> None:
        gb, fb = _paired_fixed()
        assert gb.output_space.to_dict() == fb.output_space.to_dict()
        assert np.allclose(gb.limits.lower, fb.limits.lower)
        assert np.allclose(gb.limits.upper, fb.limits.upper)

    def test_paired_task_residuals_within_tol(self) -> None:
        gb, fb = _paired_fixed((20, 20))
        tol = default_snap_tol(fb.grid)
        tasks = generate_paired_tasks(
            gb, fb, n_trials=5, rng=np.random.default_rng(1), snap_tol=tol
        )
        for task in tasks:
            assert task.output_residual_tol == pytest.approx(tol)
            for pre in (task.gearbox, task.fourbar):
                assert pre.start_residual is not None
                assert pre.goal_residual is not None
                assert pre.start_residual.residual_norm <= tol + 1e-12
                assert pre.goal_residual.residual_norm <= tol + 1e-12

    def test_deterministic_task_selection(self) -> None:
        gb, fb = _paired_fixed((16, 16))
        a = generate_paired_tasks(gb, fb, n_trials=4, rng=np.random.default_rng(99))
        b = generate_paired_tasks(gb, fb, n_trials=4, rng=np.random.default_rng(99))
        assert [t.to_dict() for t in a] == [t.to_dict() for t in b]

    def test_connectivity_stable_at_accepted_edge_samples(self) -> None:
        # At the Version-1 default (17) and denser sampling, component count
        # should not jump for this fixed crank-rocker pair.
        counts = []
        for n_samples in (17, 33):
            _, fb = _paired_fixed((12, 12), edge_samples=n_samples)
            counts.append(
                (fb.valid_node_count, fb.valid_edge_count(), fb.connected_component_count())
            )
        assert counts[0][0] == counts[1][0]
        assert counts[0][2] == counts[1][2]
        # Denser sampling may only remove edges, never add false ones.
        assert counts[1][1] <= counts[0][1]

    def test_bounded_limits_forbid_circular_shortcut_cost(self) -> None:
        lo = np.deg2rad(-170.0)
        hi = np.deg2rad(170.0)
        space = OutputSpace.bounded_revolute_box([lo, lo], [hi, hi])
        mech = UnitGearbox(dim=2)
        qa = [np.deg2rad(169.0), 0.0]
        qb = [np.deg2rad(-169.0), 0.0]
        # Identity map: inputs equal outputs for unit gearbox.
        c = output_euclidean_cost(mech, qa, qb, output_space=space)
        short = abs(lift_bounded_revolute(float(qb[0]), lo, hi) - float(qa[0]))
        # Wait: distance uses canonicalize of both; short-angle wrap is smaller.
        wrap_short = min(
            abs(float(qb[0]) - float(qa[0])),
            2.0 * np.pi - abs(float(qb[0]) - float(qa[0])),
        )
        assert c > np.pi
        assert c > wrap_short
        del short
