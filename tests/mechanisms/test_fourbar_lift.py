"""Four-bar output-chart consistency (IM-034 / ADR-011)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.graphs.costs import output_euclidean_cost
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms import IndependentFourBars, PlanarFourBar
from inequality_mechanisms.mechanisms.population import (
    follower_range,
    limits_from_fourbar_follower_ranges,
)
from inequality_mechanisms.spaces import OutputSpace, lift_bounded_revolute, wrap_to_pi

_CRANK_ROCKER = dict(a=1.0, b=2.5, c=2.0, d=2.0)


class TestFourBarLiftedCoordinates:
    def test_lifted_curve_matches_unwrap_in_chart(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        q_min, q_max = follower_range(bar, n_samples=361)
        u = np.linspace(0.0, 2.0 * np.pi, 361, endpoint=False)
        unwrapped = bar.follower_curve(u, unwrap=True)
        lifted = bar.lifted_follower_curve(u, q_min=q_min, q_max=q_max)
        # Both live in the continuous image; lift recovers unwrap mod chart.
        assert lifted == pytest.approx(unwrapped, abs=1e-9)
        assert float(np.min(lifted)) == pytest.approx(q_min, abs=1e-6)
        assert float(np.max(lifted)) == pytest.approx(q_max, abs=1e-6)

    def test_seam_crossing_lift_is_continuous(self) -> None:
        # Synthetic principal values that cross +pi / -pi.
        raw = np.array([2.967, 3.054, 3.124, -3.107, -3.020], dtype=np.float64)
        q_min, q_max = 2.9, 3.35
        lifted = np.array(
            [lift_bounded_revolute(float(t), q_min, q_max) for t in raw]
        )
        diffs = np.diff(lifted)
        assert np.all(diffs > -1e-12)
        assert float(np.max(np.abs(diffs))) < 0.2

    def test_inverse_accepts_lifted_and_raw_equivalent(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        u_seed = 0.7
        q_raw = float(bar.input_to_output([u_seed])[0])
        q_min, q_max = follower_range(bar)
        q_lifted = lift_bounded_revolute(q_raw, q_min, q_max)
        # Equivalent principal angle on the other side of the seam.
        q_alt = q_raw + 2.0 * np.pi if q_raw < 0.0 else q_raw - 2.0 * np.pi
        pre_raw = bar.inverse_output([q_raw])
        pre_lift = bar.inverse_output([q_lifted])
        pre_alt = bar.inverse_output([q_alt])
        assert len(pre_raw) >= 1
        assert len(pre_lift) == len(pre_raw)
        assert len(pre_alt) == len(pre_raw)
        for a, b in zip(pre_raw, pre_lift, strict=True):
            assert wrap_to_pi(float(a[0] - b[0])) == pytest.approx(0.0, abs=1e-9)

    def test_no_artificial_near_two_pi_edge_cost(self) -> None:
        bar = PlanarFourBar(**_CRANK_ROCKER, branch=1)
        q_min, q_max = follower_range(bar)
        space = OutputSpace.bounded_revolute_box([q_min], [q_max])
        u = np.linspace(0.0, 2.0 * np.pi, 180, endpoint=False)
        # Neighboring crank samples on the dense sweep.
        for i in range(len(u) - 1):
            c = output_euclidean_cost(
                bar, [float(u[i])], [float(u[i + 1])], output_space=space
            )
            assert c < np.pi, f"edge cost {c} looks like a seam shortcut failure"

    def test_independent_axes_use_separate_charts(self) -> None:
        mech = IndependentFourBars.from_lengths(
            [
                (
                    _CRANK_ROCKER["a"],
                    _CRANK_ROCKER["b"],
                    _CRANK_ROCKER["c"],
                    _CRANK_ROCKER["d"],
                ),
                (1.1, 2.4, 2.1, 2.0),
            ],
            branch=1,
        )
        limits = limits_from_fourbar_follower_ranges(mech, n_samples=181)
        space = OutputSpace.from_limits(limits)
        assert space.dim == 2
        u = np.array([0.5, 1.2])
        q_raw = mech.input_to_output(u)
        q_lift = space.canonicalize(q_raw)
        for i in range(2):
            assert q_lift[i] == pytest.approx(
                lift_bounded_revolute(
                    float(q_raw[i]),
                    float(space.lower[i]),
                    float(space.upper[i]),
                )
            )
        # Axes keep independent charts (distinct bounds for these lengths).
        assert not np.allclose(space.lower, [space.lower[0], space.lower[0]])

    def test_graph_outputs_are_canonicalized(self) -> None:
        mech = IndependentFourBars.from_lengths(
            [(_CRANK_ROCKER["a"], _CRANK_ROCKER["b"], _CRANK_ROCKER["c"], _CRANK_ROCKER["d"])] * 2,
            branch=1,
        )
        limits = limits_from_fourbar_follower_ranges(mech, n_samples=181)
        space = OutputSpace.from_limits(limits)
        grid = PeriodicGrid2D((16, 16), wrap=(True, True))
        graph = ConstrainedInputGraph(
            grid, mech, limits, edge_samples=5, output_space=space
        )
        for node in list(graph.iter_valid_nodes())[:20]:
            q = graph.output_at(node.coordinates)
            assert space.contains(q)
            raw = mech.input_to_output(node.coordinates)
            assert q == pytest.approx(space.canonicalize(raw))
