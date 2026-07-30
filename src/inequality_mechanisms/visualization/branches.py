"""Static diagnostics for certified operating branches (Sprint V2.2, V2-207).

Every plot here consumes an already-built, already-certified
``OperatingBranch`` -- the same object graphs would use -- rather than
recomputing forward/inverse maps independently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.mechanisms.operating_branch import (
    BranchInverseError,
    OperatingBranch,
)


def _require_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required for branch diagnostics; "
            "install with pip install matplotlib"
        ) from exc
    return plt


def _axis_probe_base(branch: OperatingBranch) -> NDArray[np.floating]:
    """Return the branch input-box midpoint used to hold other axes fixed."""
    cert = branch.certificate
    lo = np.asarray(cert.input_lower, dtype=np.float64)
    hi = np.asarray(cert.input_upper, dtype=np.float64)
    return 0.5 * (lo + hi)


def _axis_curve(
    branch: OperatingBranch,
    axis: int,
    *,
    n_samples: int,
) -> tuple[NDArray[np.floating], NDArray[np.floating], NDArray[np.floating]]:
    """Return ``(u_samples, q_axis, dqdu_axis)`` sweeping one axis of ``branch``."""
    cert = branch.certificate
    base = _axis_probe_base(branch)
    u_lo = float(cert.input_lower[axis])
    u_hi = float(cert.input_upper[axis])
    u_samples = np.linspace(u_lo, u_hi, int(n_samples))
    q_axis = np.empty(u_samples.shape[0], dtype=np.float64)
    dqdu_axis = np.empty(u_samples.shape[0], dtype=np.float64)
    for i, u_i in enumerate(u_samples):
        u_full = base.copy()
        u_full[axis] = u_i
        q_axis[i] = float(branch.forward(u_full)[axis])
        dqdu_axis[i] = float(branch.jacobian(u_full)[axis, axis])
    return u_samples, q_axis, dqdu_axis


def _inverse_residual_curve(
    branch: OperatingBranch,
    axis: int,
    *,
    n_samples: int,
) -> tuple[NDArray[np.floating], NDArray[np.floating]]:
    """Return ``(q_samples, residual)`` for round-trip ``forward(inverse(q))``."""
    cert = branch.certificate
    base_u = _axis_probe_base(branch)
    base_q = branch.forward(base_u)
    q_lo = float(cert.output_lower[axis])
    q_hi = float(cert.output_upper[axis])
    q_samples = np.linspace(q_lo, q_hi, int(n_samples))
    residual = np.full(q_samples.shape[0], np.nan, dtype=np.float64)
    for i, q_i in enumerate(q_samples):
        q_full = base_q.copy()
        q_full[axis] = q_i
        try:
            u_recovered = branch.inverse(q_full)
        except BranchInverseError:
            continue
        q_check = branch.forward(u_recovered)
        residual[i] = float(abs(q_check[axis] - q_i))
    return q_samples, residual


def plot_operating_branch(
    branch: OperatingBranch,
    path_out: Path | str,
    *,
    matched_affine: OperatingBranch | None = None,
    n_samples: int = 200,
    title: str | None = None,
) -> Path:
    """Write per-axis operating-branch diagnostic panels to ``path_out``.

    Three rows of panels (one column per input axis):

    1. ``q(u)`` with the certified input/output bounds and, if
       ``matched_affine`` is given, its affine gearbox line for comparison;
    2. ``dq/du`` with the certified minimum-gain threshold;
    3. forward/inverse round-trip residual sampled across the output range.

    Parameters
    ----------
    branch :
        Certified operating branch to diagnose.
    path_out :
        Destination PNG path.
    matched_affine :
        Optional matched affine gearbox branch (e.g. from
        ``equivalent_gearbox_branch``) drawn as a reference line on the
        ``q(u)`` panel.
    n_samples :
        Samples per axis for each curve.
    title :
        Optional figure super-title.

    Returns
    -------
    Path
        The written PNG path.
    """
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    cert = branch.certificate
    dim = branch.mechanism.input_dim
    if int(n_samples) < 2:
        raise ValueError(f"n_samples must be >= 2, got {n_samples}")

    fig, axes = plt.subplots(3, dim, figsize=(4.5 * dim, 10.0), squeeze=False)

    for axis in range(dim):
        u_samples, q_axis, dqdu_axis = _axis_curve(branch, axis, n_samples=n_samples)

        ax_q = axes[0][axis]
        ax_q.plot(u_samples, q_axis, color="C0", linewidth=2.0, label="branch $q(u)$")
        ax_q.axvline(cert.input_lower[axis], color="0.4", linestyle="--", linewidth=1.0)
        ax_q.axvline(cert.input_upper[axis], color="0.4", linestyle="--", linewidth=1.0)
        ax_q.axhline(cert.output_lower[axis], color="0.4", linestyle=":", linewidth=1.0)
        ax_q.axhline(cert.output_upper[axis], color="0.4", linestyle=":", linewidth=1.0)
        if matched_affine is not None:
            base = _axis_probe_base(matched_affine)
            q_line = np.empty(u_samples.shape[0], dtype=np.float64)
            for i, u_i in enumerate(u_samples):
                u_full = base.copy()
                u_full[axis] = u_i
                q_line[i] = float(matched_affine.forward(u_full)[axis])
            ax_q.plot(
                u_samples,
                q_line,
                color="C1",
                linewidth=1.5,
                linestyle="--",
                label="matched affine gearbox",
            )
        ax_q.set_xlabel(f"$u_{{{axis}}}$")
        ax_q.set_ylabel(f"$q_{{{axis}}}$")
        ax_q.set_title(f"axis {axis}: $q(u)$")
        ax_q.legend(loc="best", fontsize=7)

        ax_gain = axes[1][axis]
        ax_gain.plot(
            u_samples, np.abs(dqdu_axis), color="C0", linewidth=2.0, label=r"$|dq/du|$"
        )
        ax_gain.axhline(
            cert.min_abs_gain[axis],
            color="C3",
            linestyle="--",
            linewidth=1.0,
            label="min gain threshold",
        )
        ax_gain.set_xlabel(f"$u_{{{axis}}}$")
        ax_gain.set_ylabel(r"$|dq/du|$")
        ax_gain.set_title(f"axis {axis}: gain")
        ax_gain.legend(loc="best", fontsize=7)

        q_samples, residual = _inverse_residual_curve(branch, axis, n_samples=n_samples)
        ax_res = axes[2][axis]
        ax_res.semilogy(
            q_samples,
            np.clip(residual, 1e-300, None),
            color="C2",
            linewidth=2.0,
            label="round-trip residual",
        )
        ax_res.axhline(
            branch.residual_tol,
            color="C3",
            linestyle="--",
            linewidth=1.0,
            label="residual_tol",
        )
        ax_res.set_xlabel(f"$q_{{{axis}}}$")
        ax_res.set_ylabel(r"$|g(g^{-1}(q)) - q|$")
        ax_res.set_title(f"axis {axis}: inverse residual")
        ax_res.legend(loc="best", fontsize=7)

    fig.suptitle(title or f"Operating branch diagnostics ({cert.certification_method})")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
