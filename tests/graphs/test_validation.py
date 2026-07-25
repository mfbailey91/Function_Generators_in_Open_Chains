"""Tests for output-limit filtering and edge-interior validation."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pytest
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.graphs import (
    ConstrainedInputGraph,
    PeriodicGrid2D,
    configuration_is_valid,
    edge_is_valid,
    interpolate_input_segment,
)
from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    Mechanism,
    UnitGearbox,
)
from inequality_mechanisms.mechanisms.fourbar import PlanarFourBar
from inequality_mechanisms.spaces import OutputJointLimits

_CR = dict(a=1.0, b=2.5, c=2.0, d=2.0)
_CR_LENGTHS = (_CR["a"], _CR["b"], _CR["c"], _CR["d"])


class _SinMechanism(Mechanism):
    """Test double: ``q = sin(u)`` on one axis (periodic)."""

    type_key: ClassVar[str] = "test_sin_mechanism"

    def __init__(self) -> None:
        self._name = "sin"

    @property
    def name(self) -> str:
        return self._name

    @property
    def input_dim(self) -> int:
        return 1

    @property
    def output_dim(self) -> int:
        return 1

    def input_to_output(self, u: ArrayLike) -> NDArray[np.floating]:
        u_vec = self._validate_input(u)
        return np.sin(u_vec)

    def output_jacobian(self, u: ArrayLike) -> NDArray[np.floating]:
        u_vec = self._validate_input(u)
        return np.array([[np.cos(u_vec[0])]], dtype=np.float64)

    def inverse_output(self, q: ArrayLike) -> list[NDArray[np.floating]]:
        self._validate_output(q)
        return []

    def valid_input(self, u: ArrayLike) -> bool:
        self._validate_input(u)
        return True

    def periodic_axes(self) -> tuple[bool, ...]:
        return (True,)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type_key}

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> _SinMechanism:
        return cls()


class TestInterpolateInputSegment:
    def test_linear_nonperiodic(self) -> None:
        u = interpolate_input_segment(
            [0.0, 0.0], [2.0, 4.0], 0.25, periodic_axes=(False, False)
        )
        assert u == pytest.approx([0.5, 1.0])

    def test_periodic_uses_short_wrap(self) -> None:
        # From 0.1 toward 2π - 0.1: short delta is negative ~ -0.2.
        u = interpolate_input_segment(
            [0.1],
            [2.0 * np.pi - 0.1],
            0.5,
            periodic_axes=(True,),
        )
        assert u[0] == pytest.approx(0.0, abs=1e-12)

    def test_rejects_bad_s(self) -> None:
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            interpolate_input_segment([0.0], [1.0], 1.5, periodic_axes=(False,))


class TestConfigurationValidity:
    def test_unit_gearbox_matches_limits_directly(self) -> None:
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[np.pi, np.pi])
        assert configuration_is_valid(mech, limits, [0.5, 1.0]) is True
        assert configuration_is_valid(mech, limits, [0.5, 4.0]) is False

    def test_shared_limits_object_for_gearbox_and_fourbar(self) -> None:
        limits = OutputJointLimits.box(lower=[1.1, 1.1], upper=[2.0, 2.0])
        gearbox = UnitGearbox(dim=2)
        fourbar = IndependentFourBars.from_lengths(
            [_CR_LENGTHS] * 2,
            branch=1,
        )
        # Same limit object identity for fair paired trials.
        assert configuration_is_valid(gearbox, limits, [1.5, 1.5]) is True
        # Four-bar maps u=1.5 into q≈1.35-ish — check consistently with same limits.
        u = np.array([1.5, 1.5])
        q_fb = fourbar.input_to_output(u)
        assert configuration_is_valid(fourbar, limits, u) is limits.contains(q_fb)

    def test_dim_mismatch_raises(self) -> None:
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0], upper=[1.0])
        with pytest.raises(ValueError, match="limits.dim"):
            configuration_is_valid(mech, limits, [0.5, 0.5])


class TestEdgeValidity:
    def test_gearbox_axis_edge_follows_endpoints(self) -> None:
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.0, 1.0])
        assert edge_is_valid(mech, limits, [0.1, 0.2], [0.9, 0.2], n_samples=9) is True
        assert edge_is_valid(mech, limits, [0.1, 0.2], [1.1, 0.2], n_samples=9) is False

    def test_short_periodic_path_accepted_long_path_rejected(self) -> None:
        mech = _SinMechanism()
        limits = OutputJointLimits.box(lower=[-0.3], upper=[0.3])
        u_a = np.array([0.1])
        u_b = np.array([2.0 * np.pi - 0.1])
        # Short wrap stays near 0 where |sin| is small.
        assert edge_is_valid(mech, limits, u_a, u_b, n_samples=21) is True
        # Forcing a non-periodic long chord crosses sin ≈ 1.
        assert (
            edge_is_valid(
                mech,
                limits,
                u_a,
                u_b,
                n_samples=21,
                periodic_axes=(False,),
            )
            is False
        )

    def test_fourbar_interior_limit_violation(self) -> None:
        bar = PlanarFourBar(**_CR, branch=1)
        us = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)
        qs = np.array([float(bar.input_to_output([u])[0]) for u in us])
        imax = int(np.argmax(qs))
        qmax = float(qs[imax])
        limit_hi = qmax - 0.05
        # Walk to valid samples on either side of the peak.
        left = imax
        while left > 0 and qs[left] > limit_hi:
            left -= 1
        right = imax
        while right < len(us) - 1 and qs[right] > limit_hi:
            right += 1
        u_a = np.array([us[left]])
        u_b = np.array([us[right]])
        limits = OutputJointLimits.box(lower=[0.0], upper=[limit_hi])
        assert configuration_is_valid(bar, limits, u_a) is True
        assert configuration_is_valid(bar, limits, u_b) is True
        # Endpoints valid, but the open segment crosses the peak.
        assert edge_is_valid(bar, limits, u_a, u_b, n_samples=65) is False

    def test_rejects_few_samples(self) -> None:
        mech = UnitGearbox(dim=1)
        limits = OutputJointLimits.box(lower=[0.0], upper=[1.0])
        with pytest.raises(ValueError, match="n_samples"):
            edge_is_valid(mech, limits, [0.0], [0.5], n_samples=1)


class TestConstrainedInputGraph:
    def test_unit_gearbox_filters_to_limit_box(self) -> None:
        grid = PeriodicGrid2D(
            (8, 8),
            ranges=((0.0, 2.0 * np.pi), (0.0, 2.0 * np.pi)),
            wrap=(False, False),
        )
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[np.pi, np.pi])
        graph = ConstrainedInputGraph(grid, mech, limits)
        for node in graph.iter_valid_nodes():
            u0, u1 = node.coordinates
            assert 0.0 <= u0 <= np.pi
            assert 0.0 <= u1 <= np.pi
        # Nodes outside the box are invalid.
        assert graph.node_is_valid(7, 7) is False
        assert graph.valid_node_count < grid.node_count

    def test_shared_limits_yield_different_valid_sets(self) -> None:
        grid = PeriodicGrid2D((12, 12), wrap=(True, True))
        limits = OutputJointLimits.box(lower=[1.2, 1.2], upper=[2.0, 2.0])
        gearbox = UnitGearbox(dim=2)
        fourbar = IndependentFourBars.from_lengths(
            [_CR_LENGTHS] * 2,
            branch=1,
        )
        g_gear = ConstrainedInputGraph(grid, gearbox, limits)
        g_bar = ConstrainedInputGraph(grid, fourbar, limits)
        # Same limit object; valid-node sets generally differ under nonlinear map.
        assert g_gear.limits is limits
        assert g_bar.limits is limits
        assert g_gear.valid_node_count != g_bar.valid_node_count

    def test_no_edge_between_valid_nodes_across_invalid_interior(self) -> None:
        # Build a coarse 1-D-like corridor using gearbox limits that leave a gap
        # on axis 0; four-connectivity cannot jump the gap.
        grid = PeriodicGrid2D(
            (6, 3),
            ranges=((0.0, 6.0), (0.0, 3.0)),
            wrap=(False, False),
        )
        mech = UnitGearbox(dim=2)
        # Valid bands: u0 in [0, 1.5] or [4.5, 6); middle samples invalid.
        # With unit map, coordinates are the outputs.
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.5, 3.0])
        graph = ConstrainedInputGraph(grid, mech, limits)
        # Node at i0=0 is valid; i0=5 has u0=5.0 > 1.5 → invalid under these limits.
        assert graph.node_is_valid(0, 1) is True
        assert graph.node_is_valid(5, 1) is False
        # No neighbor list should include an invalid node.
        for i0, i1 in graph.neighbors(0, 1):
            assert graph.node_is_valid(i0, i1)

    def test_invalid_node_has_no_neighbors(self) -> None:
        grid = PeriodicGrid2D((4, 4), wrap=(False, False))
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[1.0, 1.0])
        graph = ConstrainedInputGraph(grid, mech, limits)
        # Last sample is far outside.
        assert graph.node_is_valid(3, 3) is False
        assert graph.neighbors(3, 3) == []

    def test_networkx_subgraph(self) -> None:
        nx = pytest.importorskip("networkx")
        grid = PeriodicGrid2D((5, 5), wrap=(False, False))
        mech = UnitGearbox(dim=2)
        limits = OutputJointLimits.box(lower=[0.0, 0.0], upper=[2.0, 2.0])
        graph = ConstrainedInputGraph(grid, mech, limits)
        g = graph.to_networkx()
        assert g.number_of_nodes() == graph.valid_node_count
        assert g.number_of_edges() == len(list(graph.iter_edges()))
        assert nx.number_of_nodes(g) == graph.valid_node_count

    def test_rejects_non_2d_mechanism(self) -> None:
        grid = PeriodicGrid2D((3, 3), wrap=(False, False))
        mech = UnitGearbox(dim=3)
        limits = OutputJointLimits.box(lower=[0.0, 0.0, 0.0], upper=[1.0, 1.0, 1.0])
        with pytest.raises(ValueError, match="input_dim == 2"):
            ConstrainedInputGraph(grid, mech, limits)
