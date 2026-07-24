"""Abstract Mechanism interface and serialization registry.

See ``docs/ADR-002-mechanism-protocol.md`` for shapes and failure behavior.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import numpy as np
from numpy.typing import ArrayLike, NDArray


class MechanismRegistryError(KeyError):
    """Raised when ``from_dict`` cannot resolve a mechanism ``type`` key."""


_MECHANISM_REGISTRY: dict[str, type[Mechanism]] = {}


def register_mechanism_type(type_key: str, cls: type[Mechanism]) -> None:
    """Register a concrete mechanism class for ``Mechanism.from_dict``.

    Parameters
    ----------
    type_key :
        Discriminator string stored under the ``\"type\"`` key in ``to_dict``.
    cls :
        Concrete ``Mechanism`` subclass.

    Raises
    ------
    ValueError
        If ``type_key`` is empty or already registered to a different class.
    """
    if not type_key:
        raise ValueError("type_key must be a non-empty string")
    existing = _MECHANISM_REGISTRY.get(type_key)
    if existing is not None and existing is not cls:
        raise ValueError(
            f"mechanism type {type_key!r} already registered to {existing.__name__}"
        )
    _MECHANISM_REGISTRY[type_key] = cls


def clear_mechanism_registry() -> None:
    """Remove all registered mechanism types.

    Intended for tests; production code should not call this.
    """
    _MECHANISM_REGISTRY.clear()


def _as_float_vector(x: ArrayLike, *, name: str, dim: int) -> NDArray[np.floating]:
    """Validate and convert an array-like to a 1-D float64 vector of length ``dim``.

    Parameters
    ----------
    x :
        Candidate vector.
    name :
        Argument name used in error messages.
    dim :
        Required length.

    Returns
    -------
    ndarray
        Contiguous ``float64`` vector of shape ``(dim,)``.

    Raises
    ------
    ValueError
        If rank, length, or finiteness is wrong.
    """
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got shape {arr.shape}")
    if arr.shape[0] != dim:
        raise ValueError(f"{name} must have length {dim}, got {arr.shape[0]}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


class Mechanism(ABC):
    """Map from input configuration space ``U`` to output joint space ``Q``.

    Search state identity lives in ``U``. Output and Cartesian quantities are
    attached data. ``inverse_output`` returns all valid preimages so duplicate
    output angles remain distinct physical states (ADR-001).

    ``valid_input`` checks assembly / kinematic domain only; shared output joint
    limits are applied elsewhere (IM-009).
    """

    #: Registry key written by ``to_dict`` / read by ``from_dict``.
    type_key: ClassVar[str]

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for logging and configuration."""

    @property
    @abstractmethod
    def input_dim(self) -> int:
        """Dimension of input configuration vectors."""

    @property
    @abstractmethod
    def output_dim(self) -> int:
        """Dimension of output configuration vectors."""

    @abstractmethod
    def input_to_output(self, u: ArrayLike) -> NDArray[np.floating]:
        """Forward map ``q = g(u)``.

        Parameters
        ----------
        u :
            Input configuration, shape ``(input_dim,)``.

        Returns
        -------
        ndarray
            Output configuration, shape ``(output_dim,)``.

        Raises
        ------
        ValueError
            If ``u`` has the wrong shape, is non-finite, or the mechanism does
            not assemble at ``u``.
        """

    @abstractmethod
    def output_jacobian(self, u: ArrayLike) -> NDArray[np.floating]:
        """Mechanism Jacobian ``J_g(u) = dq/du``.

        Parameters
        ----------
        u :
            Input configuration, shape ``(input_dim,)``.

        Returns
        -------
        ndarray
            Jacobian matrix, shape ``(output_dim, input_dim)``.

        Raises
        ------
        ValueError
            If ``u`` has the wrong shape, is non-finite, or the mechanism does
            not assemble at ``u``.
        """

    @abstractmethod
    def inverse_output(self, q: ArrayLike) -> list[NDArray[np.floating]]:
        """Return all valid input preimages of an output configuration.

        Parameters
        ----------
        q :
            Output configuration, shape ``(output_dim,)``.

        Returns
        -------
        list of ndarray
            Each entry has shape ``(input_dim,)``. Empty if no valid preimage
            exists. Duplicate preimages are preserved as distinct entries.

        Raises
        ------
        ValueError
            If ``q`` has the wrong shape or is non-finite.
        """

    @abstractmethod
    def valid_input(self, u: ArrayLike) -> bool:
        """Return whether ``u`` lies in the mechanism assembly domain.

        Does not apply shared output joint limits.

        Parameters
        ----------
        u :
            Input configuration, shape ``(input_dim,)``.

        Returns
        -------
        bool
            ``True`` if the mechanism assembles at ``u``.

        Raises
        ------
        ValueError
            If ``u`` has the wrong shape or is non-finite.
        """

    @abstractmethod
    def periodic_axes(self) -> tuple[bool, ...]:
        """Per-axis periodicity flags of length ``input_dim``.

        ``True`` means that axis wraps with period ``2 * pi``.
        """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize parameters to a plain dictionary with a ``type`` key."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Mechanism:
        """Deserialize a mechanism using the ``type`` registry.

        Parameters
        ----------
        data :
            Mapping that includes a ``\"type\"`` discriminator.

        Returns
        -------
        Mechanism
            Concrete instance produced by the registered class.

        Raises
        ------
        ValueError
            If ``data`` lacks a ``type`` key.
        MechanismRegistryError
            If ``type`` is not registered.
        """
        if "type" not in data:
            raise ValueError("mechanism dict must include a 'type' key")
        type_key = data["type"]
        if type_key not in _MECHANISM_REGISTRY:
            raise MechanismRegistryError(
                f"unknown mechanism type {type_key!r}; "
                f"known types: {sorted(_MECHANISM_REGISTRY)}"
            )
        concrete = _MECHANISM_REGISTRY[type_key]
        return concrete._from_dict(data)

    @classmethod
    @abstractmethod
    def _from_dict(cls, data: dict[str, Any]) -> Mechanism:
        """Construct an instance from a typed dictionary (subclass hook)."""

    def _validate_input(self, u: ArrayLike) -> NDArray[np.floating]:
        """Validate an input configuration vector."""
        return _as_float_vector(u, name="u", dim=self.input_dim)

    def _validate_output(self, q: ArrayLike) -> NDArray[np.floating]:
        """Validate an output configuration vector."""
        return _as_float_vector(q, name="q", dim=self.output_dim)
