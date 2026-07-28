"""Fixed-ratio, unit, and equivalent-gain gearbox mechanisms.

A fixed-ratio gearbox applies an independent constant ratio on each coordinate:

    q_i = r_i u_i

with Jacobian ``diag(r)``. A unit gearbox is the special case ``r = 1``.
An equivalent-gain gearbox (Sprint Six / ADR-012) is the affine map

    q = q_ref + r_eq * (u - u_ref)

Assembly is always valid: gearboxes have no linkage singularity. Shared
output joint limits are applied by ``OutputJointLimits`` (IM-009 / ADR-004),
not in ``valid_input``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.mechanisms.base import Mechanism, register_mechanism_type


def _parse_ratios(ratios: ArrayLike) -> NDArray[np.floating]:
    """Validate a ratio vector: 1-D, finite, and nowhere zero."""
    arr = np.asarray(ratios, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"ratios must be 1-D, got shape {arr.shape}")
    if arr.size < 1:
        raise ValueError("ratios must be non-empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError("ratios must contain only finite values")
    if np.any(arr == 0.0):
        raise ValueError("ratios must be nonzero (zero ratio is invalid)")
    return arr.copy()


def _parse_periodic(periodic: tuple[bool, ...] | None, dim: int) -> tuple[bool, ...]:
    """Parse per-axis periodicity flags; default all axes periodic."""
    if periodic is None:
        return tuple(True for _ in range(dim))
    if len(periodic) != dim:
        raise ValueError(f"periodic must have length {dim}, got {len(periodic)}")
    return tuple(bool(p) for p in periodic)


class FixedRatioGearbox(Mechanism):
    """Diagonal fixed-ratio transmission ``q = r * u``.

    Parameters
    ----------
    ratios :
        Per-axis transmission ratios, shape ``(n,)``. Each entry must be
        finite and nonzero.
    periodic :
        Per-axis input periodicity flags of length ``n``. Defaults to all
        ``True`` (revolute actuators wrap with period ``2 * pi``).
    name :
        Identifier string.
    """

    type_key = "fixed_ratio_gearbox"

    def __init__(
        self,
        ratios: ArrayLike,
        *,
        periodic: tuple[bool, ...] | None = None,
        name: str = "fixed_ratio_gearbox",
    ) -> None:
        self._ratios = _parse_ratios(ratios)
        self._dim = int(self._ratios.shape[0])
        self._periodic = _parse_periodic(periodic, self._dim)
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

    @property
    def ratios(self) -> NDArray[np.floating]:
        """Copy of the transmission ratio vector."""
        return self._ratios.copy()

    def input_to_output(self, u: ArrayLike) -> NDArray[np.floating]:
        u_vec = self._validate_input(u)
        return self._ratios * u_vec

    def output_jacobian(self, u: ArrayLike) -> NDArray[np.floating]:
        self._validate_input(u)
        return np.diag(self._ratios)

    def inverse_output(self, q: ArrayLike) -> list[NDArray[np.floating]]:
        q_vec = self._validate_output(q)
        return [(q_vec / self._ratios).copy()]

    def valid_input(self, u: ArrayLike) -> bool:
        self._validate_input(u)
        return True

    def periodic_axes(self) -> tuple[bool, ...]:
        return self._periodic

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type_key,
            "ratios": self._ratios.tolist(),
            "periodic": list(self._periodic),
            "name": self._name,
        }

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> FixedRatioGearbox:
        periodic_raw = data.get("periodic")
        periodic = tuple(periodic_raw) if periodic_raw is not None else None
        return cls(
            ratios=data["ratios"],
            periodic=periodic,
            name=str(data.get("name", "fixed_ratio_gearbox")),
        )


class UnitGearbox(FixedRatioGearbox):
    """Unit-ratio gearbox ``q = u`` (identity map and Jacobian).

    Parameters
    ----------
    dim :
        Input and output dimension.
    periodic :
        Per-axis input periodicity flags. Defaults to all ``True``.
    name :
        Identifier string.
    """

    type_key = "unit_gearbox"

    def __init__(
        self,
        dim: int = 2,
        *,
        periodic: tuple[bool, ...] | None = None,
        name: str = "unit_gearbox",
    ) -> None:
        if dim < 1:
            raise ValueError(f"dim must be >= 1, got {dim}")
        super().__init__(
            ratios=np.ones(dim, dtype=np.float64),
            periodic=periodic,
            name=name,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type_key,
            "dim": self._dim,
            "periodic": list(self._periodic),
            "name": self._name,
        }

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> UnitGearbox:
        periodic_raw = data.get("periodic")
        periodic = tuple(periodic_raw) if periodic_raw is not None else None
        return cls(
            dim=int(data["dim"]),
            periodic=periodic,
            name=str(data.get("name", "unit_gearbox")),
        )


class EquivalentGearbox(Mechanism):
    """Affine equivalent-gain gearbox ``q = q_ref + r ⊙ (u − u_ref)``.

    Used as a Sprint Six matched linear control (ADR-012). Distinct from
    ``FixedRatioGearbox`` (``q = r ⊙ u``) and ``UnitGearbox`` (``q = u``).

    Parameters
    ----------
    ratios :
        Per-axis equivalent ratios ``r_eq``, nonzero and finite.
    u_ref :
        Input reference, shape ``(n,)``.
    q_ref :
        Output reference, shape ``(n,)``.
    matching_rule :
        Criterion name: ``span``, ``total_variation``, or ``rms_gain``.
    periodic :
        Per-axis input periodicity flags. Defaults to all ``True``.
    name :
        Identifier string.
    provenance :
        Optional matching metadata (intervals, source params, cycle class).
    """

    type_key = "equivalent_gearbox"

    def __init__(
        self,
        ratios: ArrayLike,
        *,
        u_ref: ArrayLike,
        q_ref: ArrayLike,
        matching_rule: str,
        periodic: tuple[bool, ...] | None = None,
        name: str = "equivalent_gearbox",
        provenance: dict[str, Any] | None = None,
    ) -> None:
        self._ratios = _parse_ratios(ratios)
        self._dim = int(self._ratios.shape[0])
        self._u_ref = _parse_ref(u_ref, dim=self._dim, name="u_ref")
        self._q_ref = _parse_ref(q_ref, dim=self._dim, name="q_ref")
        rule = str(matching_rule).strip()
        if rule not in {"span", "total_variation", "rms_gain"}:
            raise ValueError(
                "matching_rule must be one of "
                "{'span', 'total_variation', 'rms_gain'}, "
                f"got {matching_rule!r}"
            )
        self._matching_rule = rule
        self._periodic = _parse_periodic(periodic, self._dim)
        self._name = name
        self._provenance: dict[str, Any] = (
            {} if provenance is None else dict(provenance)
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def input_dim(self) -> int:
        return self._dim

    @property
    def output_dim(self) -> int:
        return self._dim

    @property
    def ratios(self) -> NDArray[np.floating]:
        """Copy of the equivalent-ratio vector."""
        return self._ratios.copy()

    @property
    def u_ref(self) -> NDArray[np.floating]:
        """Copy of the input reference."""
        return self._u_ref.copy()

    @property
    def q_ref(self) -> NDArray[np.floating]:
        """Copy of the output reference."""
        return self._q_ref.copy()

    @property
    def matching_rule(self) -> str:
        """Matching criterion used to choose ``ratios``."""
        return self._matching_rule

    @property
    def provenance(self) -> dict[str, Any]:
        """Copy of matching provenance metadata."""
        return dict(self._provenance)

    def input_to_output(self, u: ArrayLike) -> NDArray[np.floating]:
        u_vec = self._validate_input(u)
        return self._q_ref + self._ratios * (u_vec - self._u_ref)

    def output_jacobian(self, u: ArrayLike) -> NDArray[np.floating]:
        self._validate_input(u)
        return np.diag(self._ratios)

    def inverse_output(self, q: ArrayLike) -> list[NDArray[np.floating]]:
        q_vec = self._validate_output(q)
        u = self._u_ref + (q_vec - self._q_ref) / self._ratios
        return [u.copy()]

    def valid_input(self, u: ArrayLike) -> bool:
        self._validate_input(u)
        return True

    def periodic_axes(self) -> tuple[bool, ...]:
        return self._periodic

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type_key,
            "ratios": self._ratios.tolist(),
            "u_ref": self._u_ref.tolist(),
            "q_ref": self._q_ref.tolist(),
            "matching_rule": self._matching_rule,
            "periodic": list(self._periodic),
            "name": self._name,
        }
        if self._provenance:
            payload["provenance"] = dict(self._provenance)
        return payload

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> EquivalentGearbox:
        if "ratios" not in data:
            raise ValueError(
                "equivalent_gearbox deserialization requires 'ratios'; "
                "derive from a four-bar via match_equivalent_gearbox when "
                "ratios are omitted from experiment YAML"
            )
        periodic_raw = data.get("periodic")
        periodic = tuple(periodic_raw) if periodic_raw is not None else None
        provenance = data.get("provenance")
        return cls(
            ratios=data["ratios"],
            u_ref=data["u_ref"],
            q_ref=data["q_ref"],
            matching_rule=str(data["matching_rule"]),
            periodic=periodic,
            name=str(data.get("name", "equivalent_gearbox")),
            provenance=dict(provenance) if isinstance(provenance, dict) else None,
        )


def _parse_ref(value: ArrayLike, *, dim: int, name: str) -> NDArray[np.floating]:
    """Validate a reference vector of length ``dim``."""
    arr = np.asarray(value, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got shape {arr.shape}")
    if int(arr.shape[0]) != int(dim):
        raise ValueError(f"{name} must have length {dim}, got {arr.shape[0]}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr.copy()


register_mechanism_type(FixedRatioGearbox.type_key, FixedRatioGearbox)
register_mechanism_type(UnitGearbox.type_key, UnitGearbox)
register_mechanism_type(EquivalentGearbox.type_key, EquivalentGearbox)
