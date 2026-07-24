"""Contract tests for the Mechanism ABC and serialization registry."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms import (
    Mechanism,
    MechanismRegistryError,
    register_mechanism_type,
)
from inequality_mechanisms.mechanisms._testing import IdentityMechanism


@pytest.fixture
def identity() -> IdentityMechanism:
    """Unrestricted 2-D identity mechanism."""
    return IdentityMechanism(dim=2)


@pytest.fixture
def boxed() -> IdentityMechanism:
    """Identity mechanism with a box domain for empty-preimage tests."""
    return IdentityMechanism(dim=2, domain_half_width=1.0)


def test_nominal_forward_and_jacobian(identity: IdentityMechanism) -> None:
    u = np.array([0.3, -0.7])
    q = identity.input_to_output(u)
    assert q == pytest.approx(u)
    J = identity.output_jacobian(u)
    assert J.shape == (2, 2)
    assert J == pytest.approx(np.eye(2))


def test_nominal_unique_inverse(identity: IdentityMechanism) -> None:
    q = np.array([1.0, 2.0])
    preimages = identity.inverse_output(q)
    assert len(preimages) == 1
    assert preimages[0] == pytest.approx(q)


def test_valid_input_true_on_domain(identity: IdentityMechanism) -> None:
    assert identity.valid_input([0.0, 0.0]) is True


def test_wrong_rank_raises(identity: IdentityMechanism) -> None:
    with pytest.raises(ValueError, match="1-D"):
        identity.input_to_output([[0.0, 0.0]])


def test_wrong_length_raises(identity: IdentityMechanism) -> None:
    with pytest.raises(ValueError, match="length 2"):
        identity.input_to_output([0.0])


def test_non_finite_raises(identity: IdentityMechanism) -> None:
    with pytest.raises(ValueError, match="finite"):
        identity.input_to_output([0.0, np.nan])


def test_invalid_assembly_raises_on_forward(boxed: IdentityMechanism) -> None:
    with pytest.raises(ValueError, match="does not assemble"):
        boxed.input_to_output([2.0, 0.0])
    with pytest.raises(ValueError, match="does not assemble"):
        boxed.output_jacobian([2.0, 0.0])


def test_empty_preimage_outside_domain(boxed: IdentityMechanism) -> None:
    assert boxed.inverse_output([2.0, 0.0]) == []
    assert boxed.valid_input([2.0, 0.0]) is False
    inside = boxed.inverse_output([0.5, -0.25])
    assert len(inside) == 1
    assert inside[0] == pytest.approx([0.5, -0.25])


def test_periodic_axes_length_matches_input_dim() -> None:
    mech = IdentityMechanism(dim=3, periodic=(True, False, True))
    axes = mech.periodic_axes()
    assert len(axes) == mech.input_dim
    assert axes == (True, False, True)


def test_serialization_round_trip(boxed: IdentityMechanism) -> None:
    restored = Mechanism.from_dict(boxed.to_dict())
    assert isinstance(restored, IdentityMechanism)
    assert restored.name == boxed.name
    assert restored.input_dim == boxed.input_dim
    assert restored.output_dim == boxed.output_dim
    assert restored.periodic_axes() == boxed.periodic_axes()
    sample = np.array([0.25, -0.5])
    assert restored.input_to_output(sample) == pytest.approx(
        boxed.input_to_output(sample)
    )


def test_from_dict_missing_type_raises() -> None:
    with pytest.raises(ValueError, match="type"):
        Mechanism.from_dict({"dim": 2})


def test_from_dict_unknown_type_raises() -> None:
    with pytest.raises(MechanismRegistryError, match="unknown mechanism type"):
        Mechanism.from_dict({"type": "not_a_real_mechanism"})


def test_register_rejects_conflicting_type() -> None:
    with pytest.raises(ValueError, match="already registered"):

        class Other(IdentityMechanism):
            type_key = "identity_test"

        register_mechanism_type("identity_test", Other)


def test_cannot_instantiate_abstract_mechanism() -> None:
    with pytest.raises(TypeError):
        Mechanism()  # type: ignore[abstract, call-arg]
