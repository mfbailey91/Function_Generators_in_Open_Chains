"""Planar four-bar function generators.

Conventions are frozen in ``docs/ADR-003-fourbar-conventions.md``. Shared
output joint limits are applied by ``OutputJointLimits`` (IM-009 / ADR-004),
not in ``valid_input``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.mechanisms.base import Mechanism, register_mechanism_type

BranchSign = Literal[1, -1]

_TWO_PI = 2.0 * np.pi
_ASSEMBLY_TOL = 1e-10
_SINGULAR_TOL = 1e-10


def _wrap_to_pi(angle: float) -> float:
    """Wrap an angle to ``(-pi, pi]``."""
    return float((angle + np.pi) % _TWO_PI - np.pi)


def _wrap_to_two_pi(angle: float) -> float:
    """Wrap an angle to ``[0, 2 pi)``."""
    return float(angle % _TWO_PI)


def _parse_branch(branch: int) -> BranchSign:
    if branch not in (1, -1):
        raise ValueError(f"branch must be +1 or -1, got {branch}")
    return branch  # type: ignore[return-value]


def _parse_positive_length(value: float, name: str) -> float:
    x = float(value)
    if not np.isfinite(x) or x <= 0.0:
        raise ValueError(f"{name} must be a finite positive length, got {value}")
    return x


def freudenstein_constants(
    a: float, b: float, c: float, d: float
) -> tuple[float, float, float]:
    """Return Freudenstein constants ``(K1, K2, K3)`` for link lengths."""
    a = _parse_positive_length(a, "a")
    b = _parse_positive_length(b, "b")
    c = _parse_positive_length(c, "c")
    d = _parse_positive_length(d, "d")
    k1 = d / a
    k2 = d / c
    k3 = (a * a - b * b + c * c + d * d) / (2.0 * a * c)
    return k1, k2, k3


def _trig_solutions(A: float, B: float, C: float) -> list[float]:
    """Solve ``A sin x + B cos x = C``.

    Returns zero or two solutions (duplicated when the discriminant is zero).
    """
    r2 = A * A + B * B
    if r2 <= _ASSEMBLY_TOL:
        return []
    r = float(np.sqrt(r2))
    if abs(C) > r + _ASSEMBLY_TOL:
        return []
    cos_alpha = float(np.clip(C / r, -1.0, 1.0))
    alpha = float(np.arccos(cos_alpha))
    phi = float(np.atan2(A, B))
    return [phi + alpha, phi - alpha]


def follower_angles_at_crank(u: float, k1: float, k2: float, k3: float) -> list[float]:
    """Return both algebraic follower solutions at crank angle ``u``."""
    A = -np.sin(u)
    B = k1 - np.cos(u)
    C = k2 * np.cos(u) - k3
    return _trig_solutions(float(A), float(B), float(C))


def crank_angles_at_follower(q: float, k1: float, k2: float, k3: float) -> list[float]:
    """Return both algebraic crank solutions at follower angle ``q``."""
    A = np.sin(q)
    B = k2 + np.cos(q)
    C = k1 * np.cos(q) + k3
    return _trig_solutions(float(A), float(B), float(C))


def select_branch_angle(solutions: Sequence[float], branch: BranchSign) -> float:
    """Select ``q_+`` (branch=+1) or ``q_-`` (branch=-1) from ``_trig_solutions``."""
    if len(solutions) < 2:
        if len(solutions) == 1:
            return float(solutions[0])
        raise ValueError("mechanism does not assemble at this configuration")
    # _trig_solutions returns [phi+alpha, phi-alpha]
    return float(solutions[0] if branch == 1 else solutions[1])


def transmission_ratio(u: float, q: float, k1: float, k2: float) -> float:
    """Analytic ``dq/du`` from the frozen Freudenstein form."""
    denom = k1 * np.sin(q) + np.sin(u - q)
    if abs(denom) <= _SINGULAR_TOL:
        raise ValueError("Jacobian singular at four-bar change point")
    numer = k2 * np.sin(u) + np.sin(u - q)
    return float(numer / denom)


def unwrap_follower_curve(angles: ArrayLike) -> NDArray[np.floating]:
    """Unwrap a follower sample sequence to a continuous real curve."""
    arr = np.asarray(angles, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"angles must be 1-D, got shape {arr.shape}")
    if arr.size == 0:
        return arr.copy()
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, arr.size):
        delta = _wrap_to_pi(float(arr[i] - arr[i - 1]))
        out[i] = out[i - 1] + delta
    return out


class PlanarFourBar(Mechanism):
    """Scalar planar four-bar map ``q = psi(u)`` on a selected algebraic branch.

    Parameters
    ----------
    a, b, c, d :
        Crank, coupler, follower, and ground lengths (strictly positive).
    branch :
        ``+1`` selects the open algebraic sheet ``q_+``; ``-1`` selects ``q_-``.
    periodic :
        Length-1 periodicity flags. Defaults to ``(True,)``.
    name :
        Identifier string.
    """

    type_key = "planar_fourbar"

    def __init__(
        self,
        a: float,
        b: float,
        c: float,
        d: float,
        *,
        branch: int = 1,
        periodic: tuple[bool, ...] | None = None,
        name: str = "planar_fourbar",
    ) -> None:
        self._a = _parse_positive_length(a, "a")
        self._b = _parse_positive_length(b, "b")
        self._c = _parse_positive_length(c, "c")
        self._d = _parse_positive_length(d, "d")
        self._branch = _parse_branch(branch)
        self._k1, self._k2, self._k3 = freudenstein_constants(
            self._a, self._b, self._c, self._d
        )
        if periodic is None:
            self._periodic: tuple[bool, ...] = (True,)
        else:
            if len(periodic) != 1:
                raise ValueError(f"periodic must have length 1, got {len(periodic)}")
            self._periodic = (bool(periodic[0]),)
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def input_dim(self) -> int:
        return 1

    @property
    def output_dim(self) -> int:
        return 1

    @property
    def lengths(self) -> tuple[float, float, float, float]:
        """Crank, coupler, follower, ground lengths ``(a, b, c, d)``."""
        return self._a, self._b, self._c, self._d

    @property
    def branch(self) -> BranchSign:
        """Selected algebraic branch ``+1`` or ``-1``."""
        return self._branch

    @property
    def freudenstein_K(self) -> tuple[float, float, float]:
        """Freudenstein constants ``(K1, K2, K3)``."""
        return self._k1, self._k2, self._k3

    def _solutions_at(self, u: float) -> list[float]:
        return follower_angles_at_crank(u, self._k1, self._k2, self._k3)

    def valid_input(self, u: ArrayLike) -> bool:
        u_vec = self._validate_input(u)
        return len(self._solutions_at(float(u_vec[0]))) > 0

    def input_to_output(self, u: ArrayLike) -> NDArray[np.floating]:
        u_vec = self._validate_input(u)
        solutions = self._solutions_at(float(u_vec[0]))
        q = select_branch_angle(solutions, self._branch)
        return np.array([q], dtype=np.float64)

    def output_jacobian(self, u: ArrayLike) -> NDArray[np.floating]:
        u_vec = self._validate_input(u)
        uu = float(u_vec[0])
        solutions = self._solutions_at(uu)
        q = select_branch_angle(solutions, self._branch)
        ratio = transmission_ratio(uu, q, self._k1, self._k2)
        return np.array([[ratio]], dtype=np.float64)

    def inverse_output(self, q: ArrayLike) -> list[NDArray[np.floating]]:
        """Return crank preimages of a follower angle.

        ``q`` may be a principal value or a lifted chart coordinate: the
        Freudenstein solve is 2-pi-periodic in the follower angle, and
        acceptance compares angles modulo 2-pi.
        """
        q_vec = self._validate_output(q)
        qq = float(q_vec[0])
        cranks = crank_angles_at_follower(qq, self._k1, self._k2, self._k3)
        preimages: list[NDArray[np.floating]] = []
        seen: list[float] = []
        for u_raw in cranks:
            u_wrapped = _wrap_to_two_pi(u_raw)
            # Keep only preimages that reproduce q on the selected branch.
            try:
                q_fwd = float(self.input_to_output([u_wrapped])[0])
            except ValueError:
                continue
            if abs(_wrap_to_pi(q_fwd - qq)) > 1e-8:
                continue
            if any(abs(_wrap_to_pi(u_wrapped - s)) <= 1e-10 for s in seen):
                continue
            seen.append(u_wrapped)
            preimages.append(np.array([u_wrapped], dtype=np.float64))
        return preimages

    def lifted_follower_curve(
        self,
        u_samples: ArrayLike,
        *,
        q_min: float,
        q_max: float,
    ) -> NDArray[np.floating]:
        """Evaluate the selected branch and lift into ``[q_min, q_max]``.

        Pointwise Freudenstein solves are principal-valued; this method
        applies the ADR-011 chart lift so the curve stays continuous across
        the principal-angle seam and agrees with ``follower_curve(...,
        unwrap=True)`` when that unwrapped image lies in the chart.
        """
        from inequality_mechanisms.spaces.output_space import lift_bounded_revolute

        u_arr = np.asarray(u_samples, dtype=np.float64)
        if u_arr.ndim != 1:
            raise ValueError(f"u_samples must be 1-D, got shape {u_arr.shape}")
        out = np.empty(u_arr.shape[0], dtype=np.float64)
        for i, uu in enumerate(u_arr):
            q_raw = float(self.input_to_output([uu])[0])
            out[i] = lift_bounded_revolute(q_raw, q_min, q_max)
        return out

    def follower_curve(
        self, u_samples: ArrayLike, *, unwrap: bool = True
    ) -> NDArray[np.floating]:
        """Evaluate the selected branch along a crank sample path.

        Parameters
        ----------
        u_samples :
            1-D crank samples.
        unwrap :
            If ``True``, return a continuously unwrapped follower curve.

        Returns
        -------
        ndarray
            Follower samples, shape ``(len(u_samples),)``.
        """
        u_arr = np.asarray(u_samples, dtype=np.float64)
        if u_arr.ndim != 1:
            raise ValueError(f"u_samples must be 1-D, got shape {u_arr.shape}")
        qs = np.empty(u_arr.shape[0], dtype=np.float64)
        for i, uu in enumerate(u_arr):
            qs[i] = float(self.input_to_output([uu])[0])
        if unwrap:
            return unwrap_follower_curve(qs)
        return qs

    def periodic_axes(self) -> tuple[bool, ...]:
        return self._periodic

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type_key,
            "a": self._a,
            "b": self._b,
            "c": self._c,
            "d": self._d,
            "branch": self._branch,
            "periodic": list(self._periodic),
            "name": self._name,
        }

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> PlanarFourBar:
        periodic_raw = data.get("periodic")
        periodic = tuple(periodic_raw) if periodic_raw is not None else None
        return cls(
            a=float(data["a"]),
            b=float(data["b"]),
            c=float(data["c"]),
            d=float(data["d"]),
            branch=int(data.get("branch", 1)),
            periodic=periodic,
            name=str(data.get("name", "planar_fourbar")),
        )


class IndependentFourBars(Mechanism):
    """Product of independent planar four-bars (diagonal Jacobian).

    Parameters
    ----------
    bars :
        Sequence of ``PlanarFourBar`` instances, one per actuator axis.
    name :
        Identifier string.
    """

    type_key = "independent_fourbars"

    def __init__(
        self,
        bars: Sequence[PlanarFourBar],
        *,
        name: str = "independent_fourbars",
    ) -> None:
        if len(bars) < 1:
            raise ValueError("bars must be non-empty")
        self._bars = tuple(bars)
        self._dim = len(self._bars)
        self._name = name

    @classmethod
    def from_lengths(
        cls,
        lengths: Sequence[tuple[float, float, float, float]],
        *,
        branch: int | Sequence[int] = 1,
        periodic: tuple[bool, ...] | None = None,
        name: str = "independent_fourbars",
    ) -> IndependentFourBars:
        """Build from per-axis ``(a, b, c, d)`` length tuples."""
        n = len(lengths)
        if n < 1:
            raise ValueError("lengths must be non-empty")
        if isinstance(branch, int):
            branches = [branch] * n
        else:
            branches = list(branch)
            if len(branches) != n:
                raise ValueError(
                    f"branch sequence must have length {n}, got {len(branches)}"
                )
        if periodic is None:
            per_axis = [(True,) for _ in range(n)]
        else:
            if len(periodic) != n:
                raise ValueError(f"periodic must have length {n}, got {len(periodic)}")
            per_axis = [(bool(p),) for p in periodic]
        bars = [
            PlanarFourBar(
                *lengths[i],
                branch=branches[i],
                periodic=per_axis[i],
                name=f"{name}[{i}]",
            )
            for i in range(n)
        ]
        return cls(bars, name=name)

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
    def bars(self) -> tuple[PlanarFourBar, ...]:
        """Independent planar four-bar factors."""
        return self._bars

    def input_to_output(self, u: ArrayLike) -> NDArray[np.floating]:
        u_vec = self._validate_input(u)
        values = [
            float(bar.input_to_output([u_vec[i]])[0])
            for i, bar in enumerate(self._bars)
        ]
        return np.array(values, dtype=np.float64)

    def output_jacobian(self, u: ArrayLike) -> NDArray[np.floating]:
        u_vec = self._validate_input(u)
        diag = np.array(
            [
                float(bar.output_jacobian([u_vec[i]])[0, 0])
                for i, bar in enumerate(self._bars)
            ],
            dtype=np.float64,
        )
        return np.diag(diag)

    def inverse_output(self, q: ArrayLike) -> list[NDArray[np.floating]]:
        q_vec = self._validate_output(q)
        per_axis = [bar.inverse_output([q_vec[i]]) for i, bar in enumerate(self._bars)]
        if any(len(opts) == 0 for opts in per_axis):
            return []
        # Cartesian product of per-axis preimages.
        preimages: list[NDArray[np.floating]] = [np.zeros(self._dim, dtype=np.float64)]
        for axis, opts in enumerate(per_axis):
            expanded: list[NDArray[np.floating]] = []
            for prefix in preimages:
                for opt in opts:
                    row = prefix.copy()
                    row[axis] = float(opt[0])
                    expanded.append(row)
            preimages = expanded
        return preimages

    def valid_input(self, u: ArrayLike) -> bool:
        u_vec = self._validate_input(u)
        return all(bar.valid_input([u_vec[i]]) for i, bar in enumerate(self._bars))

    def periodic_axes(self) -> tuple[bool, ...]:
        return tuple(bar.periodic_axes()[0] for bar in self._bars)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type_key,
            "bars": [bar.to_dict() for bar in self._bars],
            "name": self._name,
        }

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> IndependentFourBars:
        bars_data = data["bars"]
        bars = [PlanarFourBar._from_dict(item) for item in bars_data]
        return cls(bars, name=str(data.get("name", "independent_fourbars")))


register_mechanism_type(PlanarFourBar.type_key, PlanarFourBar)
register_mechanism_type(IndependentFourBars.type_key, IndependentFourBars)
