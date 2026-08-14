"""Paired Q-side actuator-metric panels for V3-636."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from inequality_mechanisms.audits.metrics import (
    EPS,
    ActuatorMetricOnQRecord,
    LatticeMetricBundle,
    ellipse_semi_axes_from_eigenvalues,
)

PRIMARY_FIELD = "sqrt_kappa"

FIELD_SPECS: tuple[tuple[str, str, str], ...] = (
    ("sqrt_kappa", "sqrt_kappa", r"$\sqrt{\kappa}$ (directional actuator-cost ratio)"),
    ("kappa", "kappa", r"$\kappa(M_Q^{(U)})$"),
    ("lambda_min", "lambda_min", r"$\lambda_{\min}$"),
    ("lambda_max", "lambda_max", r"$\lambda_{\max}$"),
    ("sqrt_det", "sqrt_det", r"$\sqrt{\det M_Q^{(U)}}$"),
)


def _require_matplotlib() -> Any:
    import matplotlib.pyplot as plt

    return plt


def field_values(
    fields: Sequence[ActuatorMetricOnQRecord],
    attr: str,
) -> list[float]:
    """Extract finite field scalars from actuator-metric records."""
    return [float(getattr(f, attr)) for f in fields]


def shared_log_norm_limits(
    *value_groups: Sequence[float],
    eps: float = EPS,
) -> tuple[float, float]:
    """Return shared positive ``(vmin, vmax)`` for paired LogNorm panels."""
    vals: list[float] = []
    for group in value_groups:
        for v in group:
            if np.isfinite(v) and float(v) > 0.0:
                vals.append(float(v))
    if not vals:
        return float(eps), 1.0
    vmin = float(min(vals))
    vmax = float(max(vals))
    vmin = max(vmin, eps)
    if vmax <= vmin:
        vmax = vmin * (1.0 + 1e-6)
    return vmin, vmax


def _draw_sparse_ellipses(
    ax: Any,
    fields: Sequence[ActuatorMetricOnQRecord],
    *,
    stride: int,
    scale: float,
) -> None:
    from matplotlib.patches import Ellipse

    if stride < 1:
        stride = 1
    for idx, f in enumerate(fields):
        if idx % stride != 0:
            continue
        if len(f.q) < 2 or len(f.eigenvectors) < 2:
            continue
        axes = ellipse_semi_axes_from_eigenvalues((f.lambda_min, f.lambda_max))
        # Eigenvectors are columns of eigh; index 0 ↔ lambda_min, -1 ↔ lambda_max.
        v_min = np.asarray(f.eigenvectors[0], dtype=np.float64)
        angle = float(np.degrees(np.arctan2(v_min[1], v_min[0])))
        # Ellipse width/height are full axis lengths along the angle direction.
        width = 2.0 * float(axes[0]) * scale
        height = 2.0 * float(axes[1]) * scale
        ell = Ellipse(
            xy=(f.q[0], f.q[1]),
            width=width,
            height=height,
            angle=angle,
            fill=False,
            edgecolor="0.2",
            linewidth=0.6,
            alpha=0.85,
            zorder=4,
        )
        ax.add_patch(ell)


def write_actuator_metric_on_q_panels(
    *,
    bundles: Mapping[str, LatticeMetricBundle],
    out_dir: Path,
    task_id: str,
    mechanisms: Sequence[str] = ("fourbar", "gearbox"),
    ellipse_stride: int = 8,
    ellipse_scale: float = 0.04,
    cmap: str = "magma",
) -> dict[str, Path]:
    """Write paired LogNorm actuator-metric-on-Q panels with shared color limits.

    Fresh asset keys use ``actuator_metric_*`` names. Panels are never labeled
    ``cond(M_Q)``. Ellipses use semi-axes ``1/sqrt(lambda_i)`` and are drawn
    sparsely on the primary ``sqrt_kappa`` field only.
    """
    plt = _require_matplotlib()
    from matplotlib.colors import LogNorm

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, Path] = {}

    mech_list = [m for m in mechanisms if m in bundles and bundles[m].fields]
    if len(mech_list) < 1:
        return assets

    for key, attr, title in FIELD_SPECS:
        groups = [field_values(bundles[m].fields, attr) for m in mech_list]
        vmin, vmax = shared_log_norm_limits(*groups)
        norm = LogNorm(vmin=vmin, vmax=vmax)
        for mech in mech_list:
            fields = bundles[mech].fields
            fig, ax = plt.subplots(figsize=(5.5, 5.0), constrained_layout=True)
            xs = [f.q[0] for f in fields]
            ys = [f.q[1] for f in fields]
            cs = field_values(fields, attr)
            sc = ax.scatter(xs, ys, c=cs, s=14, cmap=cmap, norm=norm, zorder=3)
            if key == PRIMARY_FIELD:
                _draw_sparse_ellipses(
                    ax,
                    fields,
                    stride=ellipse_stride,
                    scale=ellipse_scale,
                )
            fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
            ax.set_title(f"{task_id}/{mech}: actuator_metric_on_q — {title}")
            ax.set_xlabel("q1")
            ax.set_ylabel("q2")
            ax.set_aspect("equal", adjustable="datalim")
            path = out_dir / f"{task_id}__{mech}__actuator_metric_{key}.png"
            fig.savefig(path, dpi=120)
            plt.close(fig)
            assets[f"{mech}_actuator_metric_{key}"] = path

    # Record shared limits used for the primary paired field.
    primary_groups = [field_values(bundles[m].fields, PRIMARY_FIELD) for m in mech_list]
    assets_meta_vmin, assets_meta_vmax = shared_log_norm_limits(*primary_groups)
    limits_path = out_dir / f"{task_id}__actuator_metric_shared_log_limits.json"
    limits_path.write_text(
        json.dumps(
            {
                "field": PRIMARY_FIELD,
                "vmin": assets_meta_vmin,
                "vmax": assets_meta_vmax,
                "mechanisms": list(mech_list),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assets["actuator_metric_shared_log_limits"] = limits_path
    return assets


__all__ = [
    "FIELD_SPECS",
    "PRIMARY_FIELD",
    "field_values",
    "shared_log_norm_limits",
    "write_actuator_metric_on_q_panels",
]
