"""Certified invertible operating branches (Sprint V2.2 / ADR-014).

An ``OperatingBranch`` restricts an existing ``Mechanism`` to a nonperiodic,
one-to-one domain with a unique, branch-local inverse. It is a distinct
object from ``Mechanism``: ``Mechanism.inverse_output`` keeps returning all
algebraic preimages (ADR-001, unchanged); ``OperatingBranch.inverse`` returns
exactly one input configuration, reconstructed with a deterministic,
branch-local method and checked against the forward map.

Version 2 initially supports square, axis-separable maps only
(``q_i = g_i(u_i)``, diagonal Jacobian). Certification rejects mechanisms
whose sampled Jacobian is not (numerically) diagonal instead of silently
treating a coupled map as separable.

Certification (`BranchCertificate`) is evidence from deterministic,
finite-density sampling. It is not a mathematical proof of global
injectivity or of the absence of hidden reversals between samples. See
``docs/software/architecture/audits/V2_2_BRANCH_CERTIFICATION.md``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.spaces.output_space import (
    AxisTopology,
    OutputAxis,
    OutputSpace,
)

_JACOBIAN_COUPLING_TOL = 1e-8
_BOUNDS_TOL = 1e-9
_DEFAULT_RESIDUAL_TOL = 1e-6


class BranchCertificationError(ValueError):
    """Raised when a candidate operating branch fails certification.

    Covers: failed assembly sample, output-space containment failure
    (ambiguous output chart), derivative sign change, gain below the
    configured minimum, gain above an optional configured maximum,
    forward/inverse or inverse/forward residual above tolerance,
    unsupported nonseparable (coupled) Jacobian, and non-finite values.
    """


class BranchInverseError(ValueError):
    """Raised when branch-local inversion fails or is out of range.

    Covers: output outside the branch range, a solved input outside the
    branch range, and a post-solve residual above tolerance. Non-unique
    inverse is prevented by construction (branch-local monotone solve),
    not detected after the fact.
    """


def _as_vector(x: ArrayLike, *, name: str, dim: int) -> NDArray[np.floating]:
    """Validate and convert to a finite 1-D ``float64`` vector of length ``dim``."""
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got shape {arr.shape}")
    if arr.shape[0] != dim:
        raise ValueError(f"{name} must have length {dim}, got {arr.shape[0]}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _bisect_root(
    f: Callable[[float], float],
    a: float,
    b: float,
    *,
    tol: float,
    max_iter: int,
) -> float:
    """Deterministic bracketed bisection root refine for ``f(x) = 0``.

    Requires ``f(a)`` and ``f(b)`` to have opposite signs, unless either
    endpoint already satisfies the configured residual tolerance. Terminates
    after at most ``max_iter`` iterations or once the bracket width or
    residual is within ``tol``.
    """
    fa = float(f(a))
    fb = float(f(b))
    if not np.isfinite(fa) or not np.isfinite(fb):
        raise BranchInverseError(
            f"non-finite bracket residuals: f({a})={fa}, f({b})={fb}"
        )
    # A table knot can differ from the true forward map by a few ULPs. Apply
    # the same residual contract at the initial bracket endpoints that the
    # bisection loop already applies to every midpoint.
    if abs(fa) <= tol:
        return float(a)
    if abs(fb) <= tol:
        return float(b)
    if (fa > 0.0) == (fb > 0.0):
        raise BranchInverseError(f"root not bracketed: f({a})={fa}, f({b})={fb}")
    lo, hi = float(a), float(b)
    flo = fa
    for _ in range(int(max_iter)):
        mid = 0.5 * (lo + hi)
        fmid = float(f(mid))
        if not np.isfinite(fmid):
            raise BranchInverseError(f"non-finite residual during bisection at x={mid}")
        if abs(fmid) <= tol or abs(hi - lo) <= tol:
            return mid
        if (flo > 0.0) == (fmid > 0.0):
            lo, flo = mid, fmid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _axis_forward_fn(
    mechanism: Mechanism,
    output_space: OutputSpace,
    axis: int,
    base: NDArray[np.floating],
    *,
    error_cls: type[Exception] = BranchInverseError,
) -> Callable[[float], float]:
    """Return the canonicalized scalar forward map for one axis.

    Other axes are held fixed at ``base``. This is only mathematically
    meaningful for axis-separable (diagonal-Jacobian) mechanisms, which is
    exactly the class of mechanisms this module certifies.
    """

    def f(u_i: float) -> float:
        u_full = base.copy()
        u_full[axis] = u_i
        if not mechanism.valid_input(u_full):
            raise error_cls(
                f"axis {axis} probe u_{axis}={u_i} does not assemble "
                f"(other axes held at {base.tolist()})"
            )
        q_raw = mechanism.input_to_output(u_full)
        return float(output_space.canonicalize(q_raw)[axis])

    return f


@dataclass(frozen=True, slots=True)
class BranchCertificate:
    """Evidence from deterministic sampling that a branch is invertible.

    This is evidence from finite-density sampling, not a mathematical proof
    of global injectivity: a reversal or coupling strictly between sample
    points would not be detected. Increase ``certification_samples_per_axis``
    to raise confidence.

    Attributes
    ----------
    input_lower, input_upper :
        Closed per-axis input (``u``) bounds of the branch.
    output_lower, output_upper :
        Closed per-axis output (``q``) bounds achieved on the branch, in the
        branch's ``OutputSpace`` chart.
    monotonic_sign :
        Per-axis sign of ``dq_i/du_i`` (``+1`` or ``-1``), constant on the
        branch.
    min_abs_gain, max_abs_gain :
        Per-axis minimum and maximum observed ``|dq_i/du_i|`` over the
        certification sample grid.
    max_forward_inverse_residual :
        Maximum observed ``||inverse(forward(u)) - u||_inf`` over the sample
        grid.
    max_inverse_forward_residual :
        Maximum observed ``||forward(inverse(q)) - q||_inf`` over the sample
        grid (``q`` taken as the canonicalized image of sampled ``u``).
    certification_samples_per_axis :
        Number of deterministic ``linspace`` samples used per axis
        (Cartesian product across axes).
    certification_method :
        Free-text identifier of the certification/inversion strategy, e.g.
        ``"affine_closed_form"`` or ``"fourbar_monotone_table_bisection"``.
    """

    input_lower: tuple[float, ...]
    input_upper: tuple[float, ...]
    output_lower: tuple[float, ...]
    output_upper: tuple[float, ...]
    monotonic_sign: tuple[int, ...]
    min_abs_gain: tuple[float, ...]
    max_abs_gain: tuple[float, ...]
    max_forward_inverse_residual: float
    max_inverse_forward_residual: float
    certification_samples_per_axis: int
    certification_method: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "input_lower": list(self.input_lower),
            "input_upper": list(self.input_upper),
            "output_lower": list(self.output_lower),
            "output_upper": list(self.output_upper),
            "monotonic_sign": list(self.monotonic_sign),
            "min_abs_gain": list(self.min_abs_gain),
            "max_abs_gain": list(self.max_abs_gain),
            "max_forward_inverse_residual": self.max_forward_inverse_residual,
            "max_inverse_forward_residual": self.max_inverse_forward_residual,
            "certification_samples_per_axis": self.certification_samples_per_axis,
            "certification_method": self.certification_method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BranchCertificate:
        """Deserialize from ``to_dict`` output."""
        return cls(
            input_lower=tuple(float(x) for x in data["input_lower"]),
            input_upper=tuple(float(x) for x in data["input_upper"]),
            output_lower=tuple(float(x) for x in data["output_lower"]),
            output_upper=tuple(float(x) for x in data["output_upper"]),
            monotonic_sign=tuple(int(x) for x in data["monotonic_sign"]),
            min_abs_gain=tuple(float(x) for x in data["min_abs_gain"]),
            max_abs_gain=tuple(float(x) for x in data["max_abs_gain"]),
            max_forward_inverse_residual=float(data["max_forward_inverse_residual"]),
            max_inverse_forward_residual=float(data["max_inverse_forward_residual"]),
            certification_samples_per_axis=int(data["certification_samples_per_axis"]),
            certification_method=str(data["certification_method"]),
        )


@dataclass(frozen=True, slots=True)
class AffineAxisInverse:
    """Exact closed-form inverse for one affine axis.

    ``u_i = u_ref + (q_i - q_ref) / ratio``, the exact algebraic inverse of
    ``q_i = q_ref + ratio * (u_i - u_ref)``.
    """

    ratio: float
    u_ref: float
    q_ref: float
    kind: str = field(default="affine", init=False)

    def __post_init__(self) -> None:
        if self.ratio == 0.0 or not np.isfinite(self.ratio):
            raise ValueError(f"ratio must be finite and nonzero, got {self.ratio}")

    def solve(
        self, q_i: float, forward: Callable[[float], float] | None = None
    ) -> float:
        """Return the exact affine preimage of ``q_i`` (``forward`` unused)."""
        return self.u_ref + (float(q_i) - self.q_ref) / self.ratio

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "kind": self.kind,
            "ratio": self.ratio,
            "u_ref": self.u_ref,
            "q_ref": self.q_ref,
        }


@dataclass(frozen=True, slots=True)
class MonotoneTableAxisInverse:
    """Monotone interpolation table plus bracketed bisection inverse.

    Seeds a bracket from a precomputed, strictly monotone ``(u, q)`` table,
    then refines with in-house bisection against the true scalar forward map
    supplied at call time (no SciPy). Deterministic given ``tol`` and
    ``max_iter``.
    """

    sign: int
    u_table: tuple[float, ...]
    q_table: tuple[float, ...]
    tol: float = 1e-10
    max_iter: int = 100
    kind: str = field(default="monotone_table", init=False)

    def __post_init__(self) -> None:
        if self.sign not in (1, -1):
            raise ValueError(f"sign must be +1 or -1, got {self.sign}")
        if len(self.u_table) != len(self.q_table) or len(self.u_table) < 2:
            raise ValueError("u_table and q_table must have equal length >= 2")
        q_arr = np.asarray(self.q_table, dtype=np.float64)
        u_arr = np.asarray(self.u_table, dtype=np.float64)
        if not np.all(np.isfinite(q_arr)) or not np.all(np.isfinite(u_arr)):
            raise ValueError("u_table and q_table must contain only finite values")
        diffs = np.diff(q_arr)
        if self.sign > 0 and not np.all(diffs > 0.0):
            raise ValueError("q_table must be strictly increasing when sign is +1")
        if self.sign < 0 and not np.all(diffs < 0.0):
            raise ValueError("q_table must be strictly decreasing when sign is -1")
        if float(self.tol) <= 0.0:
            raise ValueError(f"tol must be positive, got {self.tol}")
        if int(self.max_iter) < 1:
            raise ValueError(f"max_iter must be >= 1, got {self.max_iter}")

    def _bracket(self, q_i: float) -> tuple[float, float]:
        q_arr = np.asarray(self.q_table, dtype=np.float64)
        u_arr = np.asarray(self.u_table, dtype=np.float64)
        if self.sign < 0:
            q_asc = q_arr[::-1]
            u_asc = u_arr[::-1]
        else:
            q_asc = q_arr
            u_asc = u_arr
        idx = int(np.searchsorted(q_asc, float(q_i)))
        idx = max(1, min(idx, q_asc.shape[0] - 1))
        return float(u_asc[idx - 1]), float(u_asc[idx])

    def solve(self, q_i: float, forward: Callable[[float], float]) -> float:
        """Bracket from the table, then bisection-refine against ``forward``."""
        u_lo, u_hi = self._bracket(float(q_i))
        target = float(q_i)
        return _bisect_root(
            lambda u: forward(u) - target,
            u_lo,
            u_hi,
            tol=self.tol,
            max_iter=self.max_iter,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary."""
        return {
            "kind": self.kind,
            "sign": self.sign,
            "u_table": list(self.u_table),
            "q_table": list(self.q_table),
            "tol": self.tol,
            "max_iter": self.max_iter,
        }


AxisInverse = AffineAxisInverse | MonotoneTableAxisInverse


def _axis_inverse_from_dict(data: dict[str, Any]) -> AxisInverse:
    """Reconstruct a per-axis inverse strategy from ``to_dict`` output."""
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


def certify_branch(
    mechanism: Mechanism,
    output_space: OutputSpace,
    axis_inverses: Sequence[AxisInverse],
    *,
    input_lower: ArrayLike,
    input_upper: ArrayLike,
    certification_samples_per_axis: int = 9,
    min_abs_gain: float = 1e-9,
    max_abs_gain: float | None = None,
    residual_tol: float = _DEFAULT_RESIDUAL_TOL,
    certification_method: str,
) -> BranchCertificate:
    """Deterministically sample and certify a candidate operating branch.

    Samples a Cartesian grid of ``certification_samples_per_axis`` points
    per axis over the closed input box and checks: assembly validity,
    output-space containment, diagonal (axis-separable) Jacobian, constant
    derivative sign, gain bounds, forward-then-inverse and
    inverse-then-forward residuals, and finiteness throughout.

    Parameters
    ----------
    mechanism :
        Candidate mechanism, restricted to the branch box.
    output_space :
        Output chart the branch must stay inside (ADR-011).
    axis_inverses :
        Per-axis branch-local inverse strategies, one per input axis.
    input_lower, input_upper :
        Closed per-axis input box, ``input_upper > input_lower`` required.
    certification_samples_per_axis :
        Deterministic ``linspace`` sample count per axis (``>= 3``).
    min_abs_gain :
        Minimum acceptable ``|dq_i/du_i|`` on every sample.
    max_abs_gain :
        Optional maximum acceptable ``|dq_i/du_i|``.
    residual_tol :
        Maximum acceptable forward/inverse and inverse/forward residual.
    certification_method :
        Free-text identifier stored on the resulting certificate.

    Returns
    -------
    BranchCertificate
        Evidence, not proof, that the sampled branch is invertible.

    Raises
    ------
    BranchCertificationError
        If any sample fails assembly, containment, separability, sign
        consistency, gain bounds, residual tolerance, or finiteness.
    """
    dim = mechanism.input_dim
    if mechanism.output_dim != dim:
        raise BranchCertificationError(
            f"operating branches require a square map, got input_dim={dim}, "
            f"output_dim={mechanism.output_dim}"
        )
    if output_space.dim != dim:
        raise BranchCertificationError(
            f"output_space dim {output_space.dim} must equal mechanism dim {dim}"
        )
    for axis_idx, out_axis in enumerate(output_space.axes):
        if out_axis.topology is AxisTopology.PERIODIC_REVOLUTE:
            raise BranchCertificationError(
                f"operating branches require a nonperiodic bounded output chart; "
                f"axis {axis_idx} is periodic_revolute"
            )
    if len(axis_inverses) != dim:
        raise ValueError(
            f"axis_inverses must have length {dim}, got {len(axis_inverses)}"
        )

    lo = np.asarray(input_lower, dtype=np.float64)
    hi = np.asarray(input_upper, dtype=np.float64)
    if lo.shape != (dim,) or hi.shape != (dim,):
        raise ValueError(f"input_lower/input_upper must have shape ({dim},)")
    if not np.all(np.isfinite(lo)) or not np.all(np.isfinite(hi)):
        raise BranchCertificationError("input_lower/input_upper must be finite")
    if np.any(hi <= lo):
        raise BranchCertificationError(
            "input_upper must exceed input_lower on every axis, got "
            f"lower={lo.tolist()}, upper={hi.tolist()}"
        )

    n = int(certification_samples_per_axis)
    if n < 3:
        raise ValueError(f"certification_samples_per_axis must be >= 3, got {n}")
    if float(min_abs_gain) <= 0.0:
        raise ValueError(f"min_abs_gain must be positive, got {min_abs_gain}")
    if max_abs_gain is not None and float(max_abs_gain) <= float(min_abs_gain):
        raise ValueError("max_abs_gain must exceed min_abs_gain")
    if float(residual_tol) <= 0.0:
        raise ValueError(f"residual_tol must be positive, got {residual_tol}")

    chart_lower = output_space.lower
    chart_upper = output_space.upper

    base = 0.5 * (lo + hi)
    axis_forward_fns = [
        _axis_forward_fn(
            mechanism, output_space, i, base, error_cls=BranchCertificationError
        )
        for i in range(dim)
    ]

    sign = np.zeros(dim, dtype=int)
    for i in range(dim):
        q_at_lo = axis_forward_fns[i](float(lo[i]))
        q_at_hi = axis_forward_fns[i](float(hi[i]))
        if q_at_hi > q_at_lo:
            sign[i] = 1
        elif q_at_hi < q_at_lo:
            sign[i] = -1
        else:
            raise BranchCertificationError(
                f"axis {i} has zero net displacement between input bounds "
                f"({q_at_lo} at both ends)"
            )

    axis_samples = [np.linspace(lo[i], hi[i], n) for i in range(dim)]
    mesh = np.meshgrid(*axis_samples, indexing="ij")
    points = np.stack([g.reshape(-1) for g in mesh], axis=-1)

    q_canon_grid = np.empty((points.shape[0], dim), dtype=np.float64)
    gain_min = np.full(dim, np.inf)
    gain_max = np.zeros(dim)
    max_fi_resid = 0.0
    max_if_resid = 0.0

    for row in range(points.shape[0]):
        u_pt = np.asarray(points[row], dtype=np.float64)
        if not np.all(np.isfinite(u_pt)):
            raise BranchCertificationError(f"non-finite sample input u={u_pt.tolist()}")
        if not mechanism.valid_input(u_pt):
            raise BranchCertificationError(
                f"mechanism failed to assemble at certification sample "
                f"u={u_pt.tolist()}"
            )
        q_raw = mechanism.input_to_output(u_pt)
        if not np.all(np.isfinite(q_raw)):
            raise BranchCertificationError(
                f"non-finite forward output at u={u_pt.tolist()}"
            )
        q_canon = output_space.canonicalize(q_raw)
        if not (
            np.all(q_canon >= chart_lower - _BOUNDS_TOL)
            and np.all(q_canon <= chart_upper + _BOUNDS_TOL)
        ):
            raise BranchCertificationError(
                f"branch sample maps outside the configured output chart at "
                f"u={u_pt.tolist()}, q={q_canon.tolist()} (ambiguous output chart)"
            )
        q_canon_grid[row] = q_canon

        jac = np.asarray(mechanism.output_jacobian(u_pt), dtype=np.float64)
        if jac.shape != (dim, dim) or not np.all(np.isfinite(jac)):
            raise BranchCertificationError(
                f"non-finite or malformed Jacobian at u={u_pt.tolist()}"
            )
        off_diag = jac - np.diag(np.diag(jac))
        max_off = float(np.max(np.abs(off_diag))) if dim > 1 else 0.0
        if max_off > _JACOBIAN_COUPLING_TOL:
            raise BranchCertificationError(
                f"unsupported coupled (nonseparable) Jacobian at u={u_pt.tolist()}: "
                f"max off-diagonal magnitude {max_off} exceeds tolerance "
                f"{_JACOBIAN_COUPLING_TOL}"
            )
        diag = np.diag(jac)
        for i in range(dim):
            g = float(diag[i])
            if g == 0.0 or int(np.sign(g)) != int(sign[i]):
                raise BranchCertificationError(
                    f"derivative sign change on axis {i} at u={u_pt.tolist()}: "
                    f"dq/du={g}, expected sign {int(sign[i])}"
                )
            ag = abs(g)
            gain_min[i] = min(gain_min[i], ag)
            gain_max[i] = max(gain_max[i], ag)

        u_recovered = np.empty(dim, dtype=np.float64)
        for i in range(dim):
            u_recovered[i] = axis_inverses[i].solve(
                float(q_canon[i]), axis_forward_fns[i]
            )
        if not np.all(np.isfinite(u_recovered)):
            raise BranchCertificationError(
                f"non-finite branch-local inverse at q={q_canon.tolist()}"
            )
        fi_resid = float(np.max(np.abs(u_recovered - u_pt)))
        max_fi_resid = max(max_fi_resid, fi_resid)

        if not mechanism.valid_input(u_recovered):
            raise BranchCertificationError(
                f"recovered u={u_recovered.tolist()} does not assemble "
                f"(forward-then-inverse of u={u_pt.tolist()})"
            )
        q_recovered_raw = mechanism.input_to_output(u_recovered)
        q_recovered = output_space.canonicalize(q_recovered_raw)
        if not np.all(np.isfinite(q_recovered)):
            raise BranchCertificationError(
                f"non-finite forward output at recovered u={u_recovered.tolist()}"
            )
        if_resid = float(np.max(np.abs(q_recovered - q_canon)))
        max_if_resid = max(max_if_resid, if_resid)

    for i in range(dim):
        if gain_min[i] < float(min_abs_gain):
            raise BranchCertificationError(
                f"axis {i} minimum |dq/du|={gain_min[i]} is below configured "
                f"min_abs_gain={min_abs_gain}"
            )
        if max_abs_gain is not None and gain_max[i] > float(max_abs_gain):
            raise BranchCertificationError(
                f"axis {i} maximum |dq/du|={gain_max[i]} exceeds configured "
                f"max_abs_gain={max_abs_gain}"
            )
    if max_fi_resid > float(residual_tol):
        raise BranchCertificationError(
            f"forward-then-inverse residual {max_fi_resid} exceeds tolerance "
            f"{residual_tol}"
        )
    if max_if_resid > float(residual_tol):
        raise BranchCertificationError(
            f"inverse-then-forward residual {max_if_resid} exceeds tolerance "
            f"{residual_tol}"
        )

    output_lower = np.min(q_canon_grid, axis=0)
    output_upper = np.max(q_canon_grid, axis=0)

    return BranchCertificate(
        input_lower=tuple(float(x) for x in lo),
        input_upper=tuple(float(x) for x in hi),
        output_lower=tuple(float(x) for x in output_lower),
        output_upper=tuple(float(x) for x in output_upper),
        monotonic_sign=tuple(int(x) for x in sign),
        min_abs_gain=tuple(float(x) for x in gain_min),
        max_abs_gain=tuple(float(x) for x in gain_max),
        max_forward_inverse_residual=max_fi_resid,
        max_inverse_forward_residual=max_if_resid,
        certification_samples_per_axis=n,
        certification_method=str(certification_method),
    )


class OperatingBranch:
    """A certified, one-to-one restriction of a ``Mechanism`` (ADR-014).

    Supports square, axis-separable maps: ``q_i = g_i(u_i)`` with diagonal
    Jacobian. Distinct from ``Mechanism``: ``forward``/``inverse`` here are
    branch-local and unique, unlike ``Mechanism.input_to_output`` /
    ``inverse_output`` which are unrestricted / all-preimages respectively.

    Parameters
    ----------
    mechanism :
        Underlying square mechanism.
    output_space :
        Output chart (ADR-011) the branch is defined and certified against.
    axis_inverses :
        Per-axis branch-local inverse strategies, length ``mechanism.input_dim``.
    certificate :
        Certification evidence produced by :func:`certify_branch`.
    selector :
        Serializable metadata describing how the branch was selected
        (method name, safety margins, source parameters).
    residual_tol :
        Runtime tolerance for the post-solve forward/inverse residual check
        in :meth:`inverse`.
    """

    def __init__(
        self,
        mechanism: Mechanism,
        output_space: OutputSpace,
        *,
        axis_inverses: Sequence[AxisInverse],
        certificate: BranchCertificate,
        selector: dict[str, Any] | None = None,
        residual_tol: float = _DEFAULT_RESIDUAL_TOL,
    ) -> None:
        if mechanism.input_dim != mechanism.output_dim:
            raise BranchCertificationError(
                "operating branches require a square map (input_dim == output_dim)"
            )
        if output_space.dim != mechanism.output_dim:
            raise ValueError("output_space dimension must equal mechanism.output_dim")
        if len(axis_inverses) != mechanism.input_dim:
            raise ValueError("axis_inverses length must equal mechanism.input_dim")
        if float(residual_tol) <= 0.0:
            raise ValueError(f"residual_tol must be positive, got {residual_tol}")
        self._mechanism = mechanism
        self._output_space = output_space
        self._axis_inverses: tuple[AxisInverse, ...] = tuple(axis_inverses)
        self._certificate = certificate
        self._selector: dict[str, Any] = (
            dict(selector) if selector else {"method": "unspecified"}
        )
        self._residual_tol = float(residual_tol)

    @property
    def mechanism(self) -> Mechanism:
        """Underlying full mechanism restricted by this branch."""
        return self._mechanism

    @property
    def output_space(self) -> OutputSpace:
        """Output chart this branch is certified against."""
        return self._output_space

    @property
    def certificate(self) -> BranchCertificate:
        """Certification evidence for this branch."""
        return self._certificate

    @property
    def selector(self) -> dict[str, Any]:
        """Copy of the selection metadata (method, safety margins, ...)."""
        return dict(self._selector)

    @property
    def residual_tol(self) -> float:
        """Runtime forward/inverse residual tolerance."""
        return self._residual_tol

    def forward(self, u: ArrayLike) -> NDArray[np.floating]:
        """Return the canonicalized forward map ``q = g(u)``.

        Raises
        ------
        ValueError
            If ``u`` has the wrong shape, is non-finite, or the mechanism
            does not assemble at ``u``.
        """
        u_vec = _as_vector(u, name="u", dim=self._mechanism.input_dim)
        if not self._mechanism.valid_input(u_vec):
            raise ValueError(f"mechanism does not assemble at u={u_vec.tolist()}")
        q_raw = self._mechanism.input_to_output(u_vec)
        return self._output_space.canonicalize(q_raw)

    def jacobian(self, u: ArrayLike) -> NDArray[np.floating]:
        """Return the mechanism Jacobian at ``u``.

        Raises
        ------
        ValueError
            If ``u`` has the wrong shape, is non-finite, or the mechanism
            does not assemble at ``u``.
        """
        u_vec = _as_vector(u, name="u", dim=self._mechanism.input_dim)
        if not self._mechanism.valid_input(u_vec):
            raise ValueError(f"mechanism does not assemble at u={u_vec.tolist()}")
        return self._mechanism.output_jacobian(u_vec)

    def contains_input(self, u: ArrayLike) -> bool:
        """Return whether ``u`` lies in the closed certified input box."""
        u_vec = _as_vector(u, name="u", dim=self._mechanism.input_dim)
        lo = np.asarray(self._certificate.input_lower, dtype=np.float64)
        hi = np.asarray(self._certificate.input_upper, dtype=np.float64)
        return bool(
            np.all(u_vec >= lo - _BOUNDS_TOL) and np.all(u_vec <= hi + _BOUNDS_TOL)
        )

    def contains_output(self, q: ArrayLike) -> bool:
        """Return whether canonicalized ``q`` lies in the certified output box."""
        q_vec = _as_vector(q, name="q", dim=self._mechanism.output_dim)
        canon = self._output_space.canonicalize(q_vec)
        lo = np.asarray(self._certificate.output_lower, dtype=np.float64)
        hi = np.asarray(self._certificate.output_upper, dtype=np.float64)
        return bool(
            np.all(canon >= lo - _BOUNDS_TOL) and np.all(canon <= hi + _BOUNDS_TOL)
        )

    def inverse(self, q: ArrayLike) -> NDArray[np.floating]:
        """Return the unique branch-local preimage of ``q``.

        Uses the per-axis branch-local inverse strategy (exact affine
        closed form, or a monotone-table-seeded bracketed bisection against
        the true forward map). Never consults
        ``Mechanism.inverse_output`` / all-preimages.

        Raises
        ------
        BranchInverseError
            If ``q`` (canonicalized) is outside the branch output range, the
            solved input is outside the branch input range, or the
            post-solve residual exceeds ``residual_tol``.
        """
        q_vec = _as_vector(q, name="q", dim=self._mechanism.output_dim)
        canon = self._output_space.canonicalize(q_vec)
        lo_q = np.asarray(self._certificate.output_lower, dtype=np.float64)
        hi_q = np.asarray(self._certificate.output_upper, dtype=np.float64)
        if not (
            np.all(canon >= lo_q - _BOUNDS_TOL) and np.all(canon <= hi_q + _BOUNDS_TOL)
        ):
            raise BranchInverseError(
                f"q={q_vec.tolist()} (canonical {canon.tolist()}) is outside the "
                f"branch output range [{lo_q.tolist()}, {hi_q.tolist()}]"
            )

        base = 0.5 * (
            np.asarray(self._certificate.input_lower, dtype=np.float64)
            + np.asarray(self._certificate.input_upper, dtype=np.float64)
        )
        u = np.empty(self._mechanism.input_dim, dtype=np.float64)
        for i, strat in enumerate(self._axis_inverses):
            fwd_i = _axis_forward_fn(
                self._mechanism,
                self._output_space,
                i,
                base,
                error_cls=BranchInverseError,
            )
            u[i] = strat.solve(float(canon[i]), fwd_i)
        if not np.all(np.isfinite(u)):
            raise BranchInverseError(
                f"non-finite inverse solution for q={q_vec.tolist()}"
            )

        lo_u = np.asarray(self._certificate.input_lower, dtype=np.float64)
        hi_u = np.asarray(self._certificate.input_upper, dtype=np.float64)
        if not (np.all(u >= lo_u - _BOUNDS_TOL) and np.all(u <= hi_u + _BOUNDS_TOL)):
            raise BranchInverseError(
                f"solved u={u.tolist()} lies outside the branch input range "
                f"[{lo_u.tolist()}, {hi_u.tolist()}]"
            )

        q_check = self.forward(u)
        resid = float(np.max(np.abs(q_check - canon)))
        if not np.isfinite(resid) or resid > self._residual_tol:
            raise BranchInverseError(
                f"inverse residual {resid} exceeds tolerance {self._residual_tol} "
                f"for q={q_vec.tolist()}"
            )
        return u

    def to_dict(self) -> dict[str, Any]:
        """Serialize the mechanism, chart, selector, and certificate."""
        return {
            "mechanism": self._mechanism.to_dict(),
            "output_space": self._output_space.to_dict(),
            "axis_inverses": [a.to_dict() for a in self._axis_inverses],
            "selector": dict(self._selector),
            "residual_tol": self._residual_tol,
            "certificate": self._certificate.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OperatingBranch:
        """Deserialize from :meth:`to_dict` output.

        Reconstructs the stored certificate and axis inverses directly
        (does not recertify); the certificate remains evidence attached to
        its original sampling run.
        """
        mechanism = Mechanism.from_dict(data["mechanism"])
        output_space = OutputSpace.from_dict(data["output_space"])
        axis_inverses = tuple(
            _axis_inverse_from_dict(item) for item in data["axis_inverses"]
        )
        certificate = BranchCertificate.from_dict(data["certificate"])
        return cls(
            mechanism,
            output_space,
            axis_inverses=axis_inverses,
            certificate=certificate,
            selector=data.get("selector"),
            residual_tol=float(data.get("residual_tol", _DEFAULT_RESIDUAL_TOL)),
        )

    @property
    def branch_id(self) -> str:
        """Deterministic branch identifier hashed from canonical serialized inputs.

        Derived from the mechanism, output chart, axis-inverse parameters,
        selector metadata, and certification method/density -- not from
        floating-point object identity or the achieved certificate values.
        """
        payload = {
            "mechanism": self._mechanism.to_dict(),
            "output_space": self._output_space.to_dict(),
            "axis_inverses": [a.to_dict() for a in self._axis_inverses],
            "selector": dict(self._selector),
            "residual_tol": self._residual_tol,
            "certification_method": self._certificate.certification_method,
            "certification_samples_per_axis": (
                self._certificate.certification_samples_per_axis
            ),
            "input_lower": list(self._certificate.input_lower),
            "input_upper": list(self._certificate.input_upper),
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _affine_axis_inverses(
    mechanism: Mechanism,
    *,
    input_lower: NDArray[np.floating],
    input_upper: NDArray[np.floating],
) -> tuple[AffineAxisInverse, ...]:
    """Build exact per-axis affine inverses from a constant-gain mechanism."""
    dim = mechanism.input_dim
    q0 = np.asarray(mechanism.input_to_output(input_lower), dtype=np.float64)
    jac_lo = np.asarray(mechanism.output_jacobian(input_lower), dtype=np.float64)
    jac_hi = np.asarray(mechanism.output_jacobian(input_upper), dtype=np.float64)
    off_diag = jac_lo - np.diag(np.diag(jac_lo))
    if dim > 1 and float(np.max(np.abs(off_diag))) > _JACOBIAN_COUPLING_TOL:
        raise BranchCertificationError(
            "affine operating branches require a diagonal (axis-separable) Jacobian"
        )
    diag_lo = np.diag(jac_lo)
    diag_hi = np.diag(jac_hi)
    if not np.allclose(diag_lo, diag_hi, rtol=1e-9, atol=1e-12):
        raise BranchCertificationError(
            "affine_operating_branch requires a constant-gain mechanism; "
            f"Jacobian diagonal varies across the input range: {diag_lo.tolist()} vs "
            f"{diag_hi.tolist()}"
        )
    if np.any(diag_lo == 0.0) or not np.all(np.isfinite(diag_lo)):
        raise BranchCertificationError(
            "affine branch requires nonzero, finite per-axis gain"
        )
    return tuple(
        AffineAxisInverse(
            ratio=float(diag_lo[i]), u_ref=float(input_lower[i]), q_ref=float(q0[i])
        )
        for i in range(dim)
    )


def affine_operating_branch(
    mechanism: Mechanism,
    *,
    input_lower: ArrayLike,
    input_upper: ArrayLike,
    output_space: OutputSpace | None = None,
    certification_samples_per_axis: int = 9,
    min_abs_gain: float = 1e-9,
    max_abs_gain: float | None = None,
    residual_tol: float = 1e-9,
) -> OperatingBranch:
    """Build a certified operating branch for a constant-gain (affine) mechanism.

    Supports ``UnitGearbox``, ``FixedRatioGearbox``, and
    ``EquivalentGearbox``: any square mechanism whose Jacobian is diagonal
    and constant across the branch box. The branch-local inverse is the
    exact affine closed form (no root solve, no residual by construction
    other than floating-point round-off).

    Parameters
    ----------
    mechanism :
        Candidate affine mechanism.
    input_lower, input_upper :
        Closed per-axis input box; ``input_upper`` must exceed
        ``input_lower`` on every axis (zero range is rejected).
    output_space :
        Output chart; defaults to a prismatic box spanning the achieved
        output range at the input corners.
    certification_samples_per_axis, min_abs_gain, max_abs_gain, residual_tol :
        Forwarded to :func:`certify_branch`.

    Returns
    -------
    OperatingBranch
        Certified affine operating branch.

    Raises
    ------
    BranchCertificationError
        If the map is not square, not axis-separable, not constant-gain,
        or fails certification (including zero gain).
    ValueError
        If ``input_upper`` does not exceed ``input_lower`` on every axis.
    """
    lo = np.asarray(input_lower, dtype=np.float64)
    hi = np.asarray(input_upper, dtype=np.float64)
    dim = mechanism.input_dim
    if mechanism.output_dim != dim:
        raise BranchCertificationError(
            "operating branches require input_dim == output_dim"
        )
    if lo.shape != (dim,) or hi.shape != (dim,):
        raise ValueError(f"input_lower/input_upper must have shape ({dim},)")
    if not np.all(np.isfinite(lo)) or not np.all(np.isfinite(hi)):
        raise ValueError("input_lower/input_upper must be finite")
    if np.any(hi <= lo):
        raise BranchCertificationError(
            "input_upper must exceed input_lower on every axis (zero range is invalid)"
        )

    axis_inverses = _affine_axis_inverses(mechanism, input_lower=lo, input_upper=hi)

    if output_space is None:
        q_lo = np.asarray(mechanism.input_to_output(lo), dtype=np.float64)
        q_hi = np.asarray(mechanism.input_to_output(hi), dtype=np.float64)
        lower = np.minimum(q_lo, q_hi)
        upper = np.maximum(q_lo, q_hi)
        output_space = OutputSpace(
            axes=tuple(
                OutputAxis(
                    topology=AxisTopology.PRISMATIC,
                    lower=float(lower[i]),
                    upper=float(upper[i]),
                )
                for i in range(dim)
            )
        )

    certificate = certify_branch(
        mechanism,
        output_space,
        axis_inverses,
        input_lower=lo,
        input_upper=hi,
        certification_samples_per_axis=certification_samples_per_axis,
        min_abs_gain=min_abs_gain,
        max_abs_gain=max_abs_gain,
        residual_tol=residual_tol,
        certification_method="affine_closed_form",
    )
    return OperatingBranch(
        mechanism,
        output_space,
        axis_inverses=axis_inverses,
        certificate=certificate,
        selector={"method": "affine_exact"},
        residual_tol=residual_tol,
    )


def unit_gearbox_branch(
    dim: int,
    *,
    input_lower: ArrayLike,
    input_upper: ArrayLike,
    output_space: OutputSpace | None = None,
    name: str = "unit_gearbox",
    **kwargs: Any,
) -> OperatingBranch:
    """Build a certified operating branch for a ``UnitGearbox`` (``q = u``)."""
    from inequality_mechanisms.mechanisms.gearbox import UnitGearbox

    if dim < 1:
        raise ValueError(f"dim must be >= 1, got {dim}")
    mech = UnitGearbox(dim=dim, periodic=tuple(False for _ in range(dim)), name=name)
    return affine_operating_branch(
        mech,
        input_lower=input_lower,
        input_upper=input_upper,
        output_space=output_space,
        **kwargs,
    )


def fixed_ratio_gearbox_branch(
    ratios: ArrayLike,
    *,
    input_lower: ArrayLike,
    input_upper: ArrayLike,
    output_space: OutputSpace | None = None,
    name: str = "fixed_ratio_gearbox",
    **kwargs: Any,
) -> OperatingBranch:
    """Build a certified operating branch for a ``FixedRatioGearbox`` (``q = r*u``)."""
    from inequality_mechanisms.mechanisms.gearbox import FixedRatioGearbox

    ratios_arr = np.asarray(ratios, dtype=np.float64)
    if ratios_arr.ndim != 1 or ratios_arr.size < 1:
        raise ValueError(
            f"ratios must be a non-empty 1-D array, got shape {ratios_arr.shape}"
        )
    mech = FixedRatioGearbox(
        ratios_arr,
        periodic=tuple(False for _ in range(ratios_arr.shape[0])),
        name=name,
    )
    return affine_operating_branch(
        mech,
        input_lower=input_lower,
        input_upper=input_upper,
        output_space=output_space,
        **kwargs,
    )


def equivalent_gearbox_branch(
    reference: OperatingBranch,
    *,
    matching_rule: str = "span",
    name: str = "equivalent_gearbox",
    **kwargs: Any,
) -> OperatingBranch:
    """Build an equivalent affine gearbox branch matched to ``reference`` endpoints.

    ``r_i = (q_i_max - q_i_min) / (u_i_max - u_i_min)`` using
    ``reference.certificate`` input/output bounds (Sprint V2.2, V2-202),
    over the same input box and output chart as ``reference`` so the two
    branches are directly comparable (e.g. a four-bar branch and its
    matched affine gearbox).

    Raises
    ------
    ValueError
        If ``reference`` has zero input range on any axis (propagated from
        ``equivalent_gearbox_matching_endpoints``).
    """
    from inequality_mechanisms.mechanisms.gearbox import (
        equivalent_gearbox_matching_endpoints,
    )

    cert = reference.certificate
    dim = len(cert.input_lower)
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)
    q_lo = np.asarray(cert.output_lower, dtype=np.float64)
    q_hi = np.asarray(cert.output_upper, dtype=np.float64)
    r_eq = (q_hi - q_lo) / (u_hi - u_lo)
    mech = equivalent_gearbox_matching_endpoints(
        input_lower=cert.input_lower,
        input_upper=cert.input_upper,
        output_lower=cert.output_lower,
        output_upper=cert.output_upper,
        matching_rule=matching_rule,
        periodic=tuple(False for _ in range(dim)),
        name=name,
        provenance={
            "reference_branch_id": reference.branch_id,
            "matching_rule": matching_rule,
            "r_eq": [float(x) for x in r_eq],
            "u_min": [float(x) for x in u_lo],
            "u_max": [float(x) for x in u_hi],
            "q_min": [float(x) for x in q_lo],
            "q_max": [float(x) for x in q_hi],
            "label": "span_matched_gearbox",
        },
    )
    return affine_operating_branch(
        mech,
        input_lower=cert.input_lower,
        input_upper=cert.input_upper,
        output_space=reference.output_space,
        **kwargs,
    )
