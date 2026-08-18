"""Paired static-wrench atlas figures for V3.6F."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from inequality_mechanisms.experiments.v4.shared_q_atlas import SharedQSampleBank
from inequality_mechanisms.metrics.static_wrench import WrenchStateStatus

PAIRED_MECHANISMS = ("fourbar", "gearbox")
REGULAR_STATUSES = {WrenchStateStatus.REGULAR.value, WrenchStateStatus.NEAR_SINGULAR.value}


def _require_matplotlib() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def field_grid(
    records: Sequence[Mapping[str, Any]],
    *,
    mechanism_id: str,
    bank: SharedQSampleBank,
    key: str,
    regular_only: bool = True,
) -> NDArray[np.float64]:
    """Fill a Q-grid from stored cell records."""
    n0, n1 = bank.shape
    grid = np.full((n0, n1), np.nan, dtype=np.float64)
    for row in records:
        if row["mechanism_id"] != mechanism_id:
            continue
        if regular_only and row["status"] not in REGULAR_STATUSES:
            continue
        value = row.get(key)
        if value is None or (isinstance(value, float) and not np.isfinite(value)):
            continue
        i, j = row["grid_index"]
        grid[int(i), int(j)] = float(value)
    return grid


def shared_limits(*grids: NDArray[np.float64]) -> tuple[float, float]:
    """Paired four-bar/gearbox color limits from finite values only."""
    chunks = [g[np.isfinite(g)] for g in grids if np.any(np.isfinite(g))]
    if not chunks:
        return 0.0, 1.0
    vals = np.concatenate(chunks)
    vmin = float(np.min(vals))
    vmax = float(np.max(vals))
    if vmax <= vmin:
        vmax = vmin + 1e-12
    return vmin, vmax


def write_paired_heatmap(
    path,
    *,
    bank: SharedQSampleBank,
    grids: Mapping[str, NDArray[np.float64]],
    title: str,
    vmin: float,
    vmax: float,
    cmap: str = "viridis",
) -> None:
    """Write a two-panel heatmap with shared color limits."""
    plt = _require_matplotlib()
    q1 = np.unique([s.q[0] for s in bank.samples])
    q2 = np.unique([s.q[1] for s in bank.samples])
    qq1, qq2 = np.meshgrid(q1, q2, indexing="ij")
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6), squeeze=False)
    for ax, key in zip(axes[0], PAIRED_MECHANISMS):
        mesh = ax.pcolormesh(
            qq1,
            qq2,
            grids[key],
            shading="nearest",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_title(key)
        ax.set_xlabel(r"$q_1$ (rad)")
        ax.set_ylabel(r"$q_2$ (rad)")
        ax.set_aspect("equal")
        fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write_polygon_overlay(
    path,
    *,
    bank: SharedQSampleBank,
    records: Sequence[Mapping[str, Any]],
    stride: int,
    title: str,
) -> None:
    """Sparse exact polygons for regular cells; markers for non-polygons."""
    plt = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.6), squeeze=False)
    q_span = np.array(bank.inner_upper) - np.array(bank.inner_lower)
    glyph = 0.22 * float(np.min(q_span))
    shown: list[np.ndarray] = []
    for row in records:
        if row["status"] not in REGULAR_STATUSES:
            continue
        verts = row.get("vertices")
        if not verts:
            continue
        i, j = row["grid_index"]
        if int(i) % stride != 0 or int(j) % stride != 0:
            continue
        shown.append(np.asarray(verts, dtype=np.float64))
    scale = 1.0
    if shown:
        max_r = max(float(np.max(np.linalg.norm(v, axis=1))) for v in shown)
        if max_r > 0.0:
            scale = glyph / max_r
    for ax, mech in zip(axes[0], PAIRED_MECHANISMS):
        for row in records:
            if row["mechanism_id"] != mech:
                continue
            i, j = row["grid_index"]
            if int(i) % stride != 0 or int(j) % stride != 0:
                continue
            q = np.asarray(row["q"], dtype=np.float64)
            verts = row.get("vertices")
            if row["status"] in REGULAR_STATUSES and verts:
                poly = q + scale * np.asarray(verts, dtype=np.float64)
                closed = np.vstack([poly, poly[0]])
                ax.plot(closed[:, 0], closed[:, 1], color="#1d4f91", lw=0.8)
            else:
                ax.plot(q[0], q[1], marker="x", color="#a31f34", ms=5)
        ax.set_title(mech)
        ax.set_xlabel(r"$q_1$ (rad)")
        ax.set_ylabel(r"$q_2$ (rad)")
        ax.set_aspect("equal")
    fig.suptitle(title)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
