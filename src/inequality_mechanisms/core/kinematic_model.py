"""Dimension-independent kinematic model protocol (Sprint V3.6A / V3-611)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from numpy.typing import ArrayLike, NDArray


@runtime_checkable
class KinematicModel(Protocol):
    """Tip FK and Jacobian in output coordinates ``q``.

    Implementations expose tip position via ``forward``. Optional
    ``forward_pose`` may attach orientation; robot adapters build ``Pose``.
    """

    @property
    def dof(self) -> int:
        """Number of joint coordinates expected by ``forward`` / ``jacobian``."""

    def forward(self, q: ArrayLike) -> NDArray:
        """Return tip position for configuration ``q``."""

    def jacobian(self, q: ArrayLike) -> NDArray:
        """Return tip Jacobian ``dx/dq``."""
