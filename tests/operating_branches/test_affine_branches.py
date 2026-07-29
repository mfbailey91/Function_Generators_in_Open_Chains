"""Unit tests for affine (gearbox) operating branches (Sprint V2.2, V2-202)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms import (
    BranchCertificationError,
    BranchInverseError,
    OperatingBranch,
    equivalent_gearbox_branch,
    equivalent_gearbox_matching_endpoints,
    fixed_ratio_gearbox_branch,
    unit_gearbox_branch,
)


class TestUnitGearboxBranch:
    def test_forward_inverse_exactness(self) -> None:
        branch = unit_gearbox_branch(
            2, input_lower=[-1.0, -2.0], input_upper=[1.0, 2.0]
        )
        rng = np.random.default_rng(0)
        for _ in range(20):
            u = rng.uniform([-1.0, -2.0], [1.0, 2.0])
            q = branch.forward(u)
            assert q == pytest.approx(u, abs=1e-12)
            u_back = branch.inverse(q)
            assert u_back == pytest.approx(u, abs=1e-10)

    def test_jacobian_is_identity(self) -> None:
        branch = unit_gearbox_branch(
            2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
        )
        assert branch.jacobian([0.2, -0.3]) == pytest.approx(np.eye(2))

    def test_contains_input_output_boundaries(self) -> None:
        branch = unit_gearbox_branch(1, input_lower=[0.0], input_upper=[1.0])
        assert branch.contains_input([0.0]) is True
        assert branch.contains_input([1.0]) is True
        assert branch.contains_input([-1e-3]) is False
        assert branch.contains_input([1.0 + 1e-3]) is False
        assert branch.contains_output([0.5]) is True
        assert branch.contains_output([1.5]) is False

    def test_serialization_round_trip(self) -> None:
        branch = unit_gearbox_branch(
            2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
        )
        data = branch.to_dict()
        restored = OperatingBranch.from_dict(data)
        u = np.array([0.3, -0.4])
        assert restored.forward(u) == pytest.approx(branch.forward(u))
        assert restored.inverse(branch.forward(u)) == pytest.approx(u, abs=1e-10)
        assert restored.certificate == branch.certificate
        assert restored.branch_id == branch.branch_id

    def test_branch_id_deterministic_and_sensitive(self) -> None:
        b1 = unit_gearbox_branch(2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0])
        b2 = unit_gearbox_branch(2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0])
        b3 = unit_gearbox_branch(2, input_lower=[-1.0, -1.0], input_upper=[2.0, 1.0])
        assert b1.branch_id == b2.branch_id
        assert b1.branch_id != b3.branch_id

    def test_reject_zero_range(self) -> None:
        with pytest.raises(ValueError, match="input_upper must exceed input_lower"):
            unit_gearbox_branch(1, input_lower=[0.0], input_upper=[0.0])

    def test_reject_invalid_thresholds(self) -> None:
        with pytest.raises(ValueError, match="min_abs_gain"):
            unit_gearbox_branch(
                1, input_lower=[0.0], input_upper=[1.0], min_abs_gain=-1.0
            )
        with pytest.raises(ValueError, match="max_abs_gain"):
            unit_gearbox_branch(
                1,
                input_lower=[0.0],
                input_upper=[1.0],
                min_abs_gain=0.5,
                max_abs_gain=0.1,
            )

    def test_inverse_out_of_range_raises(self) -> None:
        branch = unit_gearbox_branch(1, input_lower=[0.0], input_upper=[1.0])
        with pytest.raises(BranchInverseError, match="outside the branch output range"):
            branch.inverse([2.0])

    def test_forward_wrong_shape_raises(self) -> None:
        branch = unit_gearbox_branch(
            2, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
        )
        with pytest.raises(ValueError, match="length 2"):
            branch.forward([0.0])


class TestFixedRatioGearboxBranch:
    def test_forward_inverse_exactness(self) -> None:
        branch = fixed_ratio_gearbox_branch(
            [2.0, -0.5], input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
        )
        rng = np.random.default_rng(1)
        for _ in range(20):
            u = rng.uniform([-1.0, -1.0], [1.0, 1.0])
            q = branch.forward(u)
            assert q == pytest.approx([2.0 * u[0], -0.5 * u[1]], abs=1e-12)
            assert branch.inverse(q) == pytest.approx(u, abs=1e-10)

    def test_zero_ratio_rejected_by_mechanism(self) -> None:
        with pytest.raises(ValueError, match="nonzero"):
            fixed_ratio_gearbox_branch(
                [1.0, 0.0], input_lower=[0.0, 0.0], input_upper=[1.0, 1.0]
            )

    def test_contains_output_scales_with_ratio(self) -> None:
        branch = fixed_ratio_gearbox_branch([2.0], input_lower=[0.0], input_upper=[1.0])
        assert branch.contains_output([0.0]) is True
        assert branch.contains_output([2.0]) is True
        assert branch.contains_output([2.1]) is False


class TestEquivalentGearboxBranch:
    def test_matches_reference_endpoints(self) -> None:
        reference = fixed_ratio_gearbox_branch(
            [3.0, -2.0], input_lower=[0.0, 1.0], input_upper=[2.0, 4.0]
        )
        matched = equivalent_gearbox_branch(reference)
        cert = reference.certificate
        u_lo = np.asarray(cert.input_lower)
        u_hi = np.asarray(cert.input_upper)
        q_lo = np.asarray(cert.output_lower)
        q_hi = np.asarray(cert.output_upper)
        expected_ratio = (q_hi - q_lo) / (u_hi - u_lo)
        assert np.asarray(matched.mechanism.ratios) == pytest.approx(expected_ratio)
        assert matched.forward(u_lo) == pytest.approx(q_lo, abs=1e-9)
        assert matched.forward(u_hi) == pytest.approx(q_hi, abs=1e-9)

    def test_roundtrip_and_certification(self) -> None:
        reference = fixed_ratio_gearbox_branch(
            [1.5], input_lower=[-1.0], input_upper=[1.0]
        )
        matched = equivalent_gearbox_branch(reference)
        q = matched.forward([0.2])
        assert matched.inverse(q) == pytest.approx([0.2], abs=1e-9)
        assert matched.certificate.certification_method == "affine_closed_form"

    def test_reject_zero_input_range(self) -> None:
        with pytest.raises(ValueError, match="zero range is invalid"):
            equivalent_gearbox_matching_endpoints(
                input_lower=[0.0],
                input_upper=[0.0],
                output_lower=[0.0],
                output_upper=[1.0],
            )

    def test_reject_zero_ratio(self) -> None:
        with pytest.raises(ValueError, match="nonzero"):
            equivalent_gearbox_matching_endpoints(
                input_lower=[0.0],
                input_upper=[1.0],
                output_lower=[0.0],
                output_upper=[0.0],
            )


class TestAffineBranchCouplingRejection:
    def test_nonseparable_jacobian_is_rejected(self) -> None:
        """A coupled (non-diagonal) mechanism must be rejected, not accepted."""
        from inequality_mechanisms.mechanisms.base import (
            Mechanism,
            register_mechanism_type,
        )
        from inequality_mechanisms.mechanisms.operating_branch import (
            affine_operating_branch,
        )

        class _CoupledLinear(Mechanism):
            type_key = "test_coupled_linear_v2_2"

            @property
            def name(self) -> str:
                return "coupled"

            @property
            def input_dim(self) -> int:
                return 2

            @property
            def output_dim(self) -> int:
                return 2

            def input_to_output(self, u):  # type: ignore[override]
                u_vec = np.asarray(u, dtype=np.float64)
                mat = np.array([[1.0, 0.5], [0.0, 1.0]])
                return mat @ u_vec

            def output_jacobian(self, u):  # type: ignore[override]
                return np.array([[1.0, 0.5], [0.0, 1.0]])

            def inverse_output(self, q):  # type: ignore[override]
                mat_inv = np.array([[1.0, -0.5], [0.0, 1.0]])
                return [mat_inv @ np.asarray(q, dtype=np.float64)]

            def valid_input(self, u) -> bool:  # type: ignore[override]
                return True

            def periodic_axes(self):  # type: ignore[override]
                return (False, False)

            def to_dict(self):  # type: ignore[override]
                return {"type": self.type_key}

            @classmethod
            def _from_dict(cls, data):  # type: ignore[override]
                return cls()

        try:
            register_mechanism_type(_CoupledLinear.type_key, _CoupledLinear)
        except ValueError:
            pass
        mech = _CoupledLinear()
        with pytest.raises(BranchCertificationError, match="separable|coupled"):
            affine_operating_branch(
                mech, input_lower=[-1.0, -1.0], input_upper=[1.0, 1.0]
            )
