"""Tests for the shared certify_branch routine and branch failure behavior (V2-201)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms import (
    AffineAxisInverse,
    BranchCertificationError,
    UnitGearbox,
    certify_branch,
)
from inequality_mechanisms.spaces.output_space import (
    AxisTopology,
    OutputAxis,
    OutputSpace,
)


def _unit_axis_inverses(dim: int) -> tuple[AffineAxisInverse, ...]:
    return tuple(AffineAxisInverse(ratio=1.0, u_ref=0.0, q_ref=0.0) for _ in range(dim))


def _prismatic_space(lower, upper) -> OutputSpace:
    return OutputSpace(
        axes=tuple(
            OutputAxis(
                topology=AxisTopology.PRISMATIC, lower=float(lo), upper=float(hi)
            )
            for lo, hi in zip(lower, upper)
        )
    )


class TestCertifyBranchInputValidation:
    def test_rejects_non_square_mechanism(self) -> None:
        class _NonSquare(UnitGearbox):
            @property
            def output_dim(self) -> int:  # type: ignore[override]
                return self.input_dim + 1

        mech = _NonSquare(dim=2)
        with pytest.raises(BranchCertificationError, match="square map"):
            certify_branch(
                mech,
                _prismatic_space([0.0], [1.0]),
                _unit_axis_inverses(2),
                input_lower=[0.0, 0.0],
                input_upper=[1.0, 1.0],
                certification_method="test",
            )

    def test_rejects_output_space_dim_mismatch(self) -> None:
        mech = UnitGearbox(dim=2, periodic=(False, False))
        with pytest.raises(BranchCertificationError, match="output_space dim"):
            certify_branch(
                mech,
                _prismatic_space([0.0], [1.0]),
                _unit_axis_inverses(2),
                input_lower=[0.0, 0.0],
                input_upper=[1.0, 1.0],
                certification_method="test",
            )

    def test_rejects_reversed_input_bounds(self) -> None:
        mech = UnitGearbox(dim=1, periodic=(False,))
        with pytest.raises(BranchCertificationError, match="input_upper must exceed"):
            certify_branch(
                mech,
                _prismatic_space([0.0], [1.0]),
                _unit_axis_inverses(1),
                input_lower=[1.0],
                input_upper=[0.0],
                certification_method="test",
            )

    def test_rejects_too_few_samples(self) -> None:
        mech = UnitGearbox(dim=1, periodic=(False,))
        with pytest.raises(ValueError, match="certification_samples_per_axis"):
            certify_branch(
                mech,
                _prismatic_space([0.0], [1.0]),
                _unit_axis_inverses(1),
                input_lower=[0.0],
                input_upper=[1.0],
                certification_samples_per_axis=2,
                certification_method="test",
            )

    def test_rejects_periodic_revolute_output_chart(self) -> None:
        mech = UnitGearbox(dim=1, periodic=(False,))
        space = OutputSpace(axes=(OutputAxis(topology=AxisTopology.PERIODIC_REVOLUTE),))
        with pytest.raises(BranchCertificationError, match="periodic_revolute"):
            certify_branch(
                mech,
                space,
                _unit_axis_inverses(1),
                input_lower=[0.0],
                input_upper=[1.0],
                certification_method="test",
            )


class TestCertifyBranchFailureModes:
    def test_ambiguous_output_chart_is_rejected(self) -> None:
        """A chart too narrow for the achieved output range is an ambiguous chart."""
        mech = UnitGearbox(dim=1, periodic=(False,))
        narrow_space = _prismatic_space([0.0], [0.5])
        with pytest.raises(BranchCertificationError, match="ambiguous output chart"):
            certify_branch(
                mech,
                narrow_space,
                _unit_axis_inverses(1),
                input_lower=[0.0],
                input_upper=[1.0],
                certification_method="test",
            )

    def test_gain_above_configured_maximum_is_rejected(self) -> None:
        mech = UnitGearbox(dim=1, periodic=(False,))
        with pytest.raises(BranchCertificationError, match="maximum \\|dq/du\\|"):
            certify_branch(
                mech,
                _prismatic_space([0.0], [1.0]),
                _unit_axis_inverses(1),
                input_lower=[0.0],
                input_upper=[1.0],
                max_abs_gain=0.5,
                certification_method="test",
            )

    def test_residual_above_tolerance_is_rejected(self) -> None:
        """A deliberately wrong axis inverse trips the residual check."""
        mech = UnitGearbox(dim=1, periodic=(False,))
        wrong_inverse = (AffineAxisInverse(ratio=1.0, u_ref=0.0, q_ref=0.05),)
        with pytest.raises(BranchCertificationError, match="residual"):
            certify_branch(
                mech,
                _prismatic_space([0.0], [1.0]),
                wrong_inverse,
                input_lower=[0.0],
                input_upper=[1.0],
                residual_tol=1e-9,
                certification_method="test",
            )

    def test_zero_net_displacement_is_rejected(self) -> None:
        from inequality_mechanisms.mechanisms.base import (
            Mechanism,
            register_mechanism_type,
        )

        class _ConstantMap(Mechanism):
            type_key = "test_constant_map_v2_2"

            @property
            def name(self) -> str:
                return "constant"

            @property
            def input_dim(self) -> int:
                return 1

            @property
            def output_dim(self) -> int:
                return 1

            def input_to_output(self, u):  # type: ignore[override]
                return np.array([0.0])

            def output_jacobian(self, u):  # type: ignore[override]
                return np.array([[0.0]])

            def inverse_output(self, q):  # type: ignore[override]
                return [np.array([0.0])]

            def valid_input(self, u) -> bool:  # type: ignore[override]
                return True

            def periodic_axes(self):  # type: ignore[override]
                return (False,)

            def to_dict(self):  # type: ignore[override]
                return {"type": self.type_key}

            @classmethod
            def _from_dict(cls, data):  # type: ignore[override]
                return cls()

        try:
            register_mechanism_type(_ConstantMap.type_key, _ConstantMap)
        except ValueError:
            pass
        mech = _ConstantMap()
        with pytest.raises(BranchCertificationError, match="zero net displacement"):
            certify_branch(
                mech,
                _prismatic_space([-1.0], [1.0]),
                _unit_axis_inverses(1),
                input_lower=[0.0],
                input_upper=[1.0],
                min_abs_gain=1e-9,
                certification_method="test",
            )
