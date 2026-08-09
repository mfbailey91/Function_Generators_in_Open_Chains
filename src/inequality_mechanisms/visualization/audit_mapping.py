"""Mechanism transmission mapping panels for V3.6B (V3-624)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np

from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch
from inequality_mechanisms.visualization.branches import (
    plot_branch_axis_transmission,
    plot_operating_branch,
)


def _require_matplotlib() -> Any:
    import matplotlib.pyplot as plt

    return plt


def write_mapping_panels(
    *,
    labeled_branches: Mapping[str, OperatingBranch],
    out_dir: Path,
    task_id: str,
    n_samples: int = 201,
) -> dict[str, Path]:
    """Write q(u), u(q), and dq/du panels for the mechanism pair."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, Path] = {}

    path_qu = out_dir / f"{task_id}__shared__q_of_u.png"
    plot_branch_axis_transmission(
        labeled_branches,
        path_qu,
        n_samples=n_samples,
        title=f"{task_id}: q(u) by axis",
    )
    assets["q_of_u"] = path_qu

    # Per-mechanism operating-branch diagnostics (includes inverse residual).
    for name, branch in labeled_branches.items():
        path = out_dir / f"{task_id}__{name}__operating_branch.png"
        matched = labeled_branches.get("gearbox") if name == "fourbar" else None
        plot_operating_branch(branch, path, matched_affine=matched, n_samples=n_samples)
        assets[f"{name}_operating_branch"] = path

    # Explicit dq/du and u(q) panels.
    plt = _require_matplotlib()
    fig, axes = plt.subplots(2, 2, figsize=(8.5, 7.0), constrained_layout=True)
    for axis in (0, 1):
        ax_dq = axes[0, axis]
        ax_uq = axes[1, axis]
        for name, branch in labeled_branches.items():
            cert = branch.certificate
            base = 0.5 * (
                np.asarray(cert.input_lower, dtype=np.float64)
                + np.asarray(cert.input_upper, dtype=np.float64)
            )
            u = np.linspace(float(cert.input_lower[axis]), float(cert.input_upper[axis]), n_samples)
            dq = np.empty_like(u)
            q = np.empty_like(u)
            for i, ui in enumerate(u):
                u_full = base.copy()
                u_full[axis] = ui
                q[i] = float(branch.forward(u_full)[axis])
                dq[i] = float(branch.jacobian(u_full)[axis, axis])
            ax_dq.plot(u, dq, label=name)
            ax_uq.plot(q, u, label=name)
        ax_dq.set_title(f"dq{axis+1}/du{axis+1}")
        ax_dq.set_xlabel(f"u{axis+1}")
        ax_dq.legend(fontsize=8)
        ax_uq.set_title(f"u{axis+1}(q{axis+1})")
        ax_uq.set_xlabel(f"q{axis+1}")
        ax_uq.legend(fontsize=8)
    path_diff = out_dir / f"{task_id}__shared__dqdu_u_of_q.png"
    fig.suptitle(f"{task_id}: transmission differentials")
    fig.savefig(path_diff, dpi=120)
    plt.close(fig)
    assets["dqdu_u_of_q"] = path_diff
    return assets


__all__ = ["write_mapping_panels"]
