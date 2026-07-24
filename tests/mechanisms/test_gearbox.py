"""Tests for unit and fixed-ratio gearbox mechanisms."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms import FixedRatioGearbox, Mechanism, UnitGearbox


def _central_jacobian(
    mech: Mechanism, u: np.ndarray, *, eps: float = 1e-6
) -> np.ndarray:
    """Central finite-difference approximation of ``output_jacobian``."""
    n = mech.input_dim
    m = mech.output_dim
    J = np.zeros((m, n), dtype=np.float64)
    for j in range(n):
        e = np.zeros(n, dtype=np.float64)
        e[j] = eps
        qp = mech.input_to_output(u + e)
        qm = mech.input_to_output(u - e)
        J[:, j] = (qp - qm) / (2.0 * eps)
    return J


class TestUnitGearbox:
    def test_identity_map_and_jacobian(self) -> None:
        gb = UnitGearbox(dim=2)
        u = np.array([0.4, -1.2])
        assert gb.input_to_output(u) == pytest.approx(u)
        assert gb.output_jacobian(u) == pytest.approx(np.eye(2))

    def test_unique_inverse(self) -> None:
        gb = UnitGearbox(dim=2)
        q = np.array([1.5, -0.25])
        preimages = gb.inverse_output(q)
        assert len(preimages) == 1
        assert preimages[0] == pytest.approx(q)
        assert gb.input_to_output(preimages[0]) == pytest.approx(q)

    def test_valid_input_always_true(self) -> None:
        gb = UnitGearbox(dim=2)
        assert gb.valid_input([0.0, 0.0]) is True
        assert gb.valid_input([1e6, -1e6]) is True

    def test_jacobian_matches_finite_differences(self) -> None:
        gb = UnitGearbox(dim=2)
        u = np.array([0.3, -0.7])
        assert gb.output_jacobian(u) == pytest.approx(
            _central_jacobian(gb, u), abs=1e-8
        )

    def test_wrong_shape_raises(self) -> None:
        gb = UnitGearbox(dim=2)
        with pytest.raises(ValueError, match="length 2"):
            gb.input_to_output([0.0])
        with pytest.raises(ValueError, match="1-D"):
            gb.input_to_output([[0.0, 0.0]])

    def test_non_finite_raises(self) -> None:
        gb = UnitGearbox(dim=2)
        with pytest.raises(ValueError, match="finite"):
            gb.input_to_output([0.0, np.inf])

    def test_invalid_dim_raises(self) -> None:
        with pytest.raises(ValueError, match="dim"):
            UnitGearbox(dim=0)

    def test_default_periodic_axes(self) -> None:
        gb = UnitGearbox(dim=3)
        assert gb.periodic_axes() == (True, True, True)

    def test_custom_periodic_axes(self) -> None:
        gb = UnitGearbox(dim=2, periodic=(True, False))
        assert gb.periodic_axes() == (True, False)

    def test_serialization_round_trip(self) -> None:
        gb = UnitGearbox(dim=2, periodic=(False, True), name="unit_a")
        restored = Mechanism.from_dict(gb.to_dict())
        assert isinstance(restored, UnitGearbox)
        assert restored.name == "unit_a"
        assert restored.input_dim == 2
        assert restored.periodic_axes() == (False, True)
        u = np.array([0.2, -0.3])
        assert restored.input_to_output(u) == pytest.approx(gb.input_to_output(u))


class TestFixedRatioGearbox:
    def test_forward_and_jacobian(self) -> None:
        gb = FixedRatioGearbox([2.0, -0.5])
        u = np.array([1.0, 4.0])
        assert gb.input_to_output(u) == pytest.approx([2.0, -2.0])
        assert gb.output_jacobian(u) == pytest.approx(np.diag([2.0, -0.5]))

    def test_unique_inverse(self) -> None:
        gb = FixedRatioGearbox([2.0, 0.5])
        q = np.array([4.0, -1.0])
        preimages = gb.inverse_output(q)
        assert len(preimages) == 1
        assert preimages[0] == pytest.approx([2.0, -2.0])
        assert gb.input_to_output(preimages[0]) == pytest.approx(q)

    def test_jacobian_matches_finite_differences(self) -> None:
        gb = FixedRatioGearbox([1.5, -2.0])
        u = np.array([-0.4, 0.9])
        assert gb.output_jacobian(u) == pytest.approx(
            _central_jacobian(gb, u), abs=1e-8
        )

    def test_zero_ratio_rejected(self) -> None:
        with pytest.raises(ValueError, match="nonzero"):
            FixedRatioGearbox([1.0, 0.0])
        with pytest.raises(ValueError, match="nonzero"):
            FixedRatioGearbox([0.0])

    def test_non_finite_ratio_rejected(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            FixedRatioGearbox([1.0, np.nan])

    def test_empty_ratios_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            FixedRatioGearbox([])

    def test_wrong_rank_ratios_rejected(self) -> None:
        with pytest.raises(ValueError, match="1-D"):
            FixedRatioGearbox([[1.0, 2.0]])

    def test_valid_input_always_true(self) -> None:
        gb = FixedRatioGearbox([3.0, 0.25])
        assert gb.valid_input([100.0, -100.0]) is True

    def test_ratios_property_is_copy(self) -> None:
        gb = FixedRatioGearbox([1.0, 2.0])
        r = gb.ratios
        r[0] = 99.0
        assert gb.ratios[0] == pytest.approx(1.0)

    def test_serialization_round_trip(self) -> None:
        gb = FixedRatioGearbox([1.25, -0.75], periodic=(True, False), name="ratio_a")
        restored = Mechanism.from_dict(gb.to_dict())
        assert isinstance(restored, FixedRatioGearbox)
        assert not isinstance(restored, UnitGearbox)
        assert restored.name == "ratio_a"
        assert restored.ratios == pytest.approx([1.25, -0.75])
        assert restored.periodic_axes() == (True, False)
        u = np.array([0.5, -1.0])
        assert restored.input_to_output(u) == pytest.approx(gb.input_to_output(u))

    def test_unit_is_fixed_ratio_with_ones(self) -> None:
        unit = UnitGearbox(dim=2)
        fixed = FixedRatioGearbox([1.0, 1.0])
        u = np.array([0.7, -0.2])
        assert unit.input_to_output(u) == pytest.approx(fixed.input_to_output(u))
        assert unit.output_jacobian(u) == pytest.approx(fixed.output_jacobian(u))
