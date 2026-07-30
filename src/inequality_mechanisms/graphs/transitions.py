"""Version 2 edge traces (Sprint V2.3, V2-304).

Independent of the legacy full-cycle ``graphs.edge_trace.build_edge_trace``:
this module never wraps and never leaves the certified operating branch.
``TransitionParameterization.INPUT_LINEAR`` interpolates ``u`` and derives
``q = g(u)``; ``OUTPUT_LINEAR`` interpolates ``q`` and derives
``u = g^{-1}(q)`` (ADR-015). Both endpoints of an edge are themselves
certified-branch nodes, and the branch's certified input/output boxes are
axis-aligned intervals, so linear interpolation between two in-box
endpoints stays in the box; a sample can still fail if it lands outside a
numerical tolerance near a boundary, which is recorded rather than raised.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.graphs.sampling import TransitionParameterization
from inequality_mechanisms.mechanisms.operating_branch import (
    BranchInverseError,
    OperatingBranch,
)

_DEFAULT_N_SAMPLES = 17


@dataclass(frozen=True, slots=True)
class EdgeTraceV2:
    """Full trace of one Version 2 edge under its declared parameterization.

    Attributes
    ----------
    s :
        Interpolation parameter samples in ``[0, 1]``, shape ``(n_samples,)``.
    q :
        Output-configuration samples, shape ``(n_samples, output_dim)``.
        ``nan``-filled rows mark samples where the branch could not
        recover a valid state.
    u :
        Actuator-configuration samples, shape ``(n_samples, input_dim)``.
        Same ``nan`` convention as ``q``.
    branch_valid :
        Per-sample flag: ``True`` when the primary interpolated coordinate
        (``u`` for ``INPUT_LINEAR``, ``q`` for ``OUTPUT_LINEAR``) was
        successfully mapped to its paired coordinate on the certified
        branch.
    forward_inverse_residual :
        Per-sample, best-effort round-trip residual checking the certified
        branch's self-consistency at that sample: for ``INPUT_LINEAR``,
        ``||inverse(forward(u)) - u||_inf``; for ``OUTPUT_LINEAR``,
        ``||forward(inverse(q)) - q||_inf``. ``nan`` where the primary
        sample is invalid, or where this secondary confirmatory solve
        itself fails (e.g. a rare monotone-table bracket near-miss right at
        a table breakpoint) without invalidating the already-recovered
        primary sample.
    first_invalid_index :
        Index of the first sample with ``branch_valid[i] is False``, or
        ``None`` if every sample is valid.
    """

    s: NDArray[np.float64]
    q: NDArray[np.float64]
    u: NDArray[np.float64]
    branch_valid: NDArray[np.bool_]
    forward_inverse_residual: NDArray[np.float64]
    first_invalid_index: int | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the trace to a plain dictionary."""
        return {
            "s": self.s.tolist(),
            "q": self.q.tolist(),
            "u": self.u.tolist(),
            "branch_valid": self.branch_valid.tolist(),
            "forward_inverse_residual": self.forward_inverse_residual.tolist(),
            "first_invalid_index": self.first_invalid_index,
        }


def _as_vector(x: ArrayLike, *, name: str) -> NDArray[np.float64]:
    arr = np.asarray(x, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got shape {arr.shape}")
    return arr


def build_edge_trace_v2(
    branch: OperatingBranch,
    parameterization: TransitionParameterization,
    q_a: ArrayLike,
    u_a: ArrayLike,
    q_b: ArrayLike,
    u_b: ArrayLike,
    *,
    n_samples: int = _DEFAULT_N_SAMPLES,
) -> EdgeTraceV2:
    """Build a Version 2 edge trace between two certified-branch endpoints.

    Parameters
    ----------
    branch :
        Certified operating branch both endpoints belong to.
    parameterization :
        ``INPUT_LINEAR`` interpolates ``u``; ``OUTPUT_LINEAR`` interpolates
        ``q``.
    q_a, u_a, q_b, u_b :
        Endpoint output/actuator configurations. ``u_a``/``u_b`` are used
        directly for ``INPUT_LINEAR``; ``q_a``/``q_b`` are used directly
        for ``OUTPUT_LINEAR``. The other pair is only used to size the
        output arrays and is otherwise recomputed from the branch.
    n_samples :
        Inclusive sample count along ``s in [0, 1]`` (``>= 2``).

    Returns
    -------
    EdgeTraceV2
        Sample-by-sample trace with explicit validity and residual columns.

    Raises
    ------
    ValueError
        If ``n_samples < 2`` or an endpoint has the wrong shape, or
        ``parameterization`` is not a known member.
    """
    if int(n_samples) < 2:
        raise ValueError(f"n_samples must be >= 2, got {n_samples}")
    q_a_v = _as_vector(q_a, name="q_a")
    u_a_v = _as_vector(u_a, name="u_a")
    q_b_v = _as_vector(q_b, name="q_b")
    u_b_v = _as_vector(u_b, name="u_b")
    if q_a_v.shape != q_b_v.shape:
        raise ValueError("q_a and q_b must have the same shape")
    if u_a_v.shape != u_b_v.shape:
        raise ValueError("u_a and u_b must have the same shape")

    dim_q = q_a_v.shape[0]
    dim_u = u_a_v.shape[0]
    n = int(n_samples)
    s = np.linspace(0.0, 1.0, n)
    q_out = np.full((n, dim_q), np.nan, dtype=np.float64)
    u_out = np.full((n, dim_u), np.nan, dtype=np.float64)
    valid = np.zeros(n, dtype=np.bool_)
    residual = np.full(n, np.nan, dtype=np.float64)
    first_invalid: int | None = None

    parameterization = TransitionParameterization(parameterization)
    if parameterization not in (
        TransitionParameterization.INPUT_LINEAR,
        TransitionParameterization.OUTPUT_LINEAR,
    ):  # pragma: no cover - exhaustive Enum guarded above
        raise ValueError(f"unknown transition parameterization: {parameterization!r}")

    for k in range(n):
        s_k = float(s[k])
        # Primary direction: the interpolated coordinate is ground truth;
        # the sample is valid exactly when the certified branch can recover
        # its paired coordinate from it.
        try:
            if parameterization is TransitionParameterization.INPUT_LINEAR:
                u_k = u_a_v + s_k * (u_b_v - u_a_v)
                q_k = np.asarray(branch.forward(u_k), dtype=np.float64)
            else:
                q_k = q_a_v + s_k * (q_b_v - q_a_v)
                u_k = np.asarray(branch.inverse(q_k), dtype=np.float64)
        except (ValueError, BranchInverseError):
            if first_invalid is None:
                first_invalid = k
            continue

        q_out[k] = q_k
        u_out[k] = u_k
        valid[k] = True

        # Secondary round-trip residual: a best-effort self-consistency
        # check of the certified branch at this sample. A failure here
        # (e.g. a monotone-table bracket near-miss at a breakpoint) does not
        # invalidate the already-recovered primary (q, u) pair.
        try:
            if parameterization is TransitionParameterization.INPUT_LINEAR:
                u_check = branch.inverse(q_k)
                residual[k] = float(np.max(np.abs(u_check - u_k)))
            else:
                q_check = branch.forward(u_k)
                residual[k] = float(np.max(np.abs(q_check - q_k)))
        except (ValueError, BranchInverseError):
            residual[k] = np.nan

    return EdgeTraceV2(
        s=s,
        q=q_out,
        u=u_out,
        branch_valid=valid,
        forward_inverse_residual=residual,
        first_invalid_index=first_invalid,
    )
