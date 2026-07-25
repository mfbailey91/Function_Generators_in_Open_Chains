"""Test doubles for the Mechanism contract.

These helpers are for unit tests only. Production unit gearboxes live in
IM-002 and must not depend on this module.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.mechanisms.base import Mechanism, register_mechanism_type


class IdentityMechanism(Mechanism):
    """Identity map ``q = u`` with optional box domain for validity tests.

    Parameters
    ----------
    dim :
        Input and output dimension.
    domain_half_width :
        If set, ``valid_input`` is true only when every coordinate of ``u``
        satisfies ``|u_i| <= domain_half_width``. If ``None``, the whole
        Euclidean space is valid.
    periodic :
        Per-axis periodicity flags. Defaults to all ``False``.
    name :
        Identifier string.
    """

    type_key = "identity_test"

    def __init__(
        self,
        dim: int = 2,
        *,
        domain_half_width: float | None = None,
        periodic: tuple[bool, ...] | None = None,
        name: str = "identity_test",
    ) -> None:
        if dim < 1:
            raise ValueError(f"dim must be >= 1, got {dim}")
        if domain_half_width is not None and domain_half_width < 0:
            raise ValueError("domain_half_width must be non-negative")
        if periodic is None:
            periodic = tuple(False for _ in range(dim))
        elif len(periodic) != dim:
            raise ValueError(f"periodic must have length {dim}, got {len(periodic)}")
        self._dim = dim
        self._domain_half_width = domain_half_width
        self._periodic = tuple(bool(p) for p in periodic)
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def input_dim(self) -> int:
        return self._dim

    @property
    def output_dim(self) -> int:
        return self._dim

    def input_to_output(self, u: ArrayLike) -> NDArray[np.floating]:
        u_vec = self._validate_input(u)
        if not self.valid_input(u_vec):
            raise ValueError("mechanism does not assemble at u")
        return u_vec.copy()

    def output_jacobian(self, u: ArrayLike) -> NDArray[np.floating]:
        u_vec = self._validate_input(u)
        if not self.valid_input(u_vec):
            raise ValueError("mechanism does not assemble at u")
        return np.eye(self._dim, dtype=np.float64)

    def inverse_output(self, q: ArrayLike) -> list[NDArray[np.floating]]:
        q_vec = self._validate_output(q)
        if not self.valid_input(q_vec):
            return []
        return [q_vec.copy()]

    def valid_input(self, u: ArrayLike) -> bool:
        u_vec = self._validate_input(u)
        if self._domain_half_width is None:
            return True
        return bool(np.all(np.abs(u_vec) <= self._domain_half_width))

    def periodic_axes(self) -> tuple[bool, ...]:
        return self._periodic

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type_key,
            "dim": self._dim,
            "domain_half_width": self._domain_half_width,
            "periodic": list(self._periodic),
            "name": self._name,
        }

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> IdentityMechanism:
        periodic_raw = data.get("periodic")
        periodic = tuple(periodic_raw) if periodic_raw is not None else None
        return cls(
            dim=int(data["dim"]),
            domain_half_width=data.get("domain_half_width"),
            periodic=periodic,
            name=str(data.get("name", "identity_test")),
        )


register_mechanism_type(IdentityMechanism.type_key, IdentityMechanism)
