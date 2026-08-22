"""Serializable output-offset adapter for mounted robot joint coordinates.

Sprint V4.2B / ADR-029. The conversion is

    q_joint = q_native - q_offset

applied exactly once at the transmission layer. Jacobian ``J_g`` is unchanged.
Do not bake span-family offsets into ``PlanarFourBar`` or robot FK.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.mechanisms.base import Mechanism, register_mechanism_type
from inequality_mechanisms.mechanisms.operating_branch import (
    AffineAxisInverse,
    MonotoneTableAxisInverse,
    OperatingBranch,
)
from inequality_mechanisms.spaces.output_space import OutputAxis, OutputSpace

AxisInverse = AffineAxisInverse | MonotoneTableAxisInverse


def _as_offset(q_offset_rad: ArrayLike, *, dim: int) -> NDArray[np.floating]:
    """Validate a finite offset vector of length ``dim``."""
    arr = np.asarray(q_offset_rad, dtype=np.float64)
    if arr.ndim == 0:
        arr = np.atleast_1d(arr)
    if arr.ndim != 1 or int(arr.shape[0]) != int(dim):
        raise ValueError(
            f"q_offset_rad must be a 1-D vector of length {dim}, got shape {arr.shape}"
        )
    if not np.all(np.isfinite(arr)):
        raise ValueError("q_offset_rad must contain only finite values")
    return arr.copy()


class MountedOutputMechanism(Mechanism):
    """Mechanism wrapper ``g_m(u) = g_n(u) - q_offset``.

    Parameters
    ----------
    native :
        Unmounted mechanism whose output is the native follower coordinate.
    q_offset_rad :
        Constant offset with ``q_joint = q_native - q_offset``.
    name :
        Optional identifier; defaults to ``mounted[<native.name>]``.
    """

    type_key = "mounted_output"

    def __init__(
        self,
        native: Mechanism,
        q_offset_rad: ArrayLike,
        *,
        name: str | None = None,
    ) -> None:
        if isinstance(native, MountedOutputMechanism):
            raise ValueError("output mounting already applied")
        self._native = native
        self._offset = _as_offset(q_offset_rad, dim=native.output_dim)
        self._name = str(name) if name is not None else f"mounted[{native.name}]"

    @property
    def name(self) -> str:
        return self._name

    @property
    def input_dim(self) -> int:
        return self._native.input_dim

    @property
    def output_dim(self) -> int:
        return self._native.output_dim

    @property
    def native(self) -> Mechanism:
        """Unmounted inner mechanism."""
        return self._native

    @property
    def q_offset_rad(self) -> NDArray[np.floating]:
        """Copy of the constant output offset."""
        return self._offset.copy()

    def input_to_output(self, u: ArrayLike) -> NDArray[np.floating]:
        return self._native.input_to_output(u) - self._offset

    def output_jacobian(self, u: ArrayLike) -> NDArray[np.floating]:
        return self._native.output_jacobian(u)

    def inverse_output(self, q: ArrayLike) -> list[NDArray[np.floating]]:
        q_vec = self._validate_output(q)
        return self._native.inverse_output(q_vec + self._offset)

    def valid_input(self, u: ArrayLike) -> bool:
        return self._native.valid_input(u)

    def periodic_axes(self) -> tuple[bool, ...]:
        return self._native.periodic_axes()

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type_key,
            "native": self._native.to_dict(),
            "q_offset_rad": self._offset.tolist(),
            "name": self._name,
        }

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> MountedOutputMechanism:
        native = Mechanism.from_dict(data["native"])
        return cls(
            native,
            data["q_offset_rad"],
            name=str(data.get("name", "mounted_output")),
        )


def _axis_inverse_from_payload(data: dict[str, Any]) -> AxisInverse:
    kind = str(data.get("kind"))
    if kind == "affine":
        return AffineAxisInverse(
            ratio=float(data["ratio"]),
            u_ref=float(data["u_ref"]),
            q_ref=float(data["q_ref"]),
        )
    if kind == "monotone_table":
        return MonotoneTableAxisInverse(
            sign=int(data["sign"]),
            u_table=tuple(float(x) for x in data["u_table"]),
            q_table=tuple(float(x) for x in data["q_table"]),
            tol=float(data.get("tol", 1e-10)),
            max_iter=int(data.get("max_iter", 100)),
        )
    raise ValueError(f"unknown axis inverse kind {kind!r}")


def _shift_axis_inverse(inverse: AxisInverse, offset_i: float) -> AxisInverse:
    delta = float(offset_i)
    if isinstance(inverse, AffineAxisInverse):
        return AffineAxisInverse(
            ratio=inverse.ratio,
            u_ref=inverse.u_ref,
            q_ref=float(inverse.q_ref) - delta,
        )
    if isinstance(inverse, MonotoneTableAxisInverse):
        return MonotoneTableAxisInverse(
            sign=inverse.sign,
            u_table=inverse.u_table,
            q_table=tuple(float(q) - delta for q in inverse.q_table),
            tol=inverse.tol,
            max_iter=inverse.max_iter,
        )
    raise TypeError(f"unsupported axis inverse type {type(inverse)!r}")


def _shift_output_space(
    space: OutputSpace, offset: NDArray[np.floating]
) -> OutputSpace:
    axes: list[OutputAxis] = []
    for i, axis in enumerate(space.axes):
        if axis.lower is None or axis.upper is None:
            axes.append(axis)
            continue
        axes.append(
            OutputAxis(
                topology=axis.topology,
                lower=float(axis.lower) - float(offset[i]),
                upper=float(axis.upper) - float(offset[i]),
            )
        )
    return OutputSpace(axes=tuple(axes))


def _already_mounted(branch: OperatingBranch) -> bool:
    if isinstance(branch.mechanism, MountedOutputMechanism):
        return True
    count = branch.selector.get("mounting_application_count", 0)
    try:
        return int(count) >= 1
    except (TypeError, ValueError):
        return False


def mount_operating_branch(
    branch: OperatingBranch,
    q_offset_rad: ArrayLike,
) -> OperatingBranch:
    """Return an ordinary operating branch in mounted joint coordinates.

    Parameters
    ----------
    branch :
        Native certified operating branch. Must not already be mounted.
    q_offset_rad :
        Constant offset with ``q_joint = q_native - q_offset``. A zero
        offset is an identity adapter that still records provenance.

    Returns
    -------
    OperatingBranch
        Rebuilt branch whose ``forward`` / ``inverse`` / certificate Q
        bounds use mounted coordinates. U bounds, assembly, branch sign,
        and ``J_g`` are unchanged.

    Raises
    ------
    ValueError
        If mounting was already applied, or the offset is invalid.
    """
    if _already_mounted(branch):
        raise ValueError("output mounting already applied")
    offset = _as_offset(q_offset_rad, dim=branch.mechanism.output_dim)
    mounted_mech = MountedOutputMechanism(branch.mechanism, offset)
    cert = branch.certificate
    shifted_cert = replace(
        cert,
        output_lower=tuple(
            float(lo) - float(offset[i]) for i, lo in enumerate(cert.output_lower)
        ),
        output_upper=tuple(
            float(hi) - float(offset[i]) for i, hi in enumerate(cert.output_upper)
        ),
    )
    payload = branch.to_dict()
    inverses = tuple(
        _shift_axis_inverse(_axis_inverse_from_payload(item), float(offset[i]))
        for i, item in enumerate(payload["axis_inverses"])
    )
    selector = dict(branch.selector)
    selector.update(
        {
            "output_coordinate_kind": "mounted_joint",
            "native_output_offset_rad": offset.tolist(),
            "mounting_application_count": 1,
        }
    )
    return OperatingBranch(
        mounted_mech,
        _shift_output_space(branch.output_space, offset),
        axis_inverses=inverses,
        certificate=shifted_cert,
        selector=selector,
        residual_tol=branch.residual_tol,
    )


register_mechanism_type(MountedOutputMechanism.type_key, MountedOutputMechanism)
