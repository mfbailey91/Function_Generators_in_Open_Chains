"""Static diagnostics for Version 2 embedded planning graphs (Sprint V2.3, V2-307).

Every plot consumes graph-owned arrays (``q_nodes``, ``u_nodes``,
``valid_nodes``, ``topology``) rather than recomputing forward/inverse maps
independently, mirroring ``visualization/branches.py``. Diagnostics target
the 2R (two-actuator) case: 1-D graphs render as line/point plots, 2-D
graphs render as a lattice with topology-owned edges.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.graphs.embedded import EmbeddedPlanningGraph
from inequality_mechanisms.graphs.transitions import EdgeTraceV2


def _require_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required for embedded-graph diagnostics; "
            "install with pip install matplotlib"
        ) from exc
    return plt


def _draw_lattice(
    ax: Any, graph: EmbeddedPlanningGraph, values: Any, *, color: str
) -> None:
    """Scatter ``values`` (``q_nodes`` or ``u_nodes``) with topology edges."""
    dim = values.shape[1]
    valid = graph.valid_nodes
    if dim == 1:
        y = np.zeros(values.shape[0])
        ax.scatter(values[valid, 0], y[valid], s=18, color=color, zorder=3)
        if np.any(~valid):
            ax.scatter(
                values[~valid, 0], y[~valid], s=18, color="0.7", marker="x", zorder=3
            )
        ax.set_yticks([])
        return
    if dim != 2:
        raise ValueError(f"lattice plots support dim 1 or 2, got {dim}")
    for a, b in graph.topology.iter_edges():
        if not (valid[a] and valid[b]):
            continue
        ax.plot(
            [values[a, 0], values[b, 0]],
            [values[a, 1], values[b, 1]],
            color="0.75",
            linewidth=0.6,
            zorder=1,
        )
    ax.scatter(
        values[valid, 0], values[valid, 1], s=14, color=color, zorder=3, label="valid"
    )
    if np.any(~valid):
        ax.scatter(
            values[~valid, 0],
            values[~valid, 1],
            s=14,
            color="0.7",
            marker="x",
            zorder=3,
            label="invalid",
        )


def plot_actuator_samples(
    graph: EmbeddedPlanningGraph, path_out: Path | str, *, title: str | None = None
) -> Path:
    """Plot the graph's actuator (``U``) samples with topology edges."""
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.0, 5.0))
    _draw_lattice(ax, graph, graph.u_nodes, color="C0")
    ax.set_xlabel("$u_0$")
    if graph.u_nodes.shape[1] == 2:
        ax.set_ylabel("$u_1$")
    ax.set_title(title or f"Actuator samples ({graph.sampling_domain.value} sampled)")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_output_graph(
    graph: EmbeddedPlanningGraph, path_out: Path | str, *, title: str | None = None
) -> Path:
    """Plot the graph's planning-state (``Q``) lattice with topology edges."""
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.0, 5.0))
    _draw_lattice(ax, graph, graph.q_nodes, color="C1")
    ax.set_xlabel("$q_0$")
    if graph.q_nodes.shape[1] == 2:
        ax.set_ylabel("$q_1$")
    ax.set_title(title or f"Output-state graph ({graph.sampling_domain.value} sampled)")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_axis_mapping(
    graph: EmbeddedPlanningGraph,
    axis: int,
    path_out: Path | str,
    *,
    title: str | None = None,
) -> Path:
    """Plot per-axis ``q(u)`` using the graph's own axis marginals."""
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    u_axis = graph.axis_marginal(graph.u_nodes, axis)
    q_axis = graph.axis_marginal(graph.q_nodes, axis)
    order = np.argsort(u_axis)
    fig, ax = plt.subplots(figsize=(5.0, 4.0))
    ax.plot(u_axis[order], q_axis[order], marker="o", color="C2")
    ax.set_xlabel(f"$u_{{{axis}}}$")
    ax.set_ylabel(f"$q_{{{axis}}}$")
    domain = graph.sampling_domain.value
    ax.set_title(title or f"axis {axis}: $q(u)$ ({domain} sampled)")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_spacing_statistics(
    graph: EmbeddedPlanningGraph,
    path_out: Path | str,
    *,
    quantity: str = "output",
    title: str | None = None,
) -> Path:
    """Bar chart of per-axis spacing statistics.

    Parameters
    ----------
    quantity :
        ``"output"`` reports mapped ``q`` spacing per axis (V2-302);
        ``"actuator"`` reports mapped ``u`` spacing per axis (V2-303).
    """
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    dim = len(graph.topology.shape)
    if quantity == "output":
        stats = [graph.output_axis_spacing(axis) for axis in range(dim)]
        ylabel = "output ($q$) spacing"
    elif quantity == "actuator":
        stats = [graph.actuator_axis_spacing(axis) for axis in range(dim)]
        ylabel = "actuator ($u$) spacing"
    else:
        raise ValueError(f"quantity must be 'output' or 'actuator', got {quantity!r}")

    fig, ax = plt.subplots(figsize=(5.0, 4.0))
    x = np.arange(dim)
    width = 0.25
    ax.bar(x - width, [s.minimum for s in stats], width, label="min", color="C0")
    ax.bar(x, [s.mean for s in stats], width, label="mean", color="C1")
    ax.bar(x + width, [s.maximum for s in stats], width, label="max", color="C2")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"axis {i}" for i in x])
    ax.set_ylabel(ylabel)
    ax.set_title(title or f"{quantity} spacing ({graph.sampling_domain.value} sampled)")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_sampling_mode_comparison(
    input_graph: EmbeddedPlanningGraph,
    output_graph: EmbeddedPlanningGraph,
    path_out: Path | str,
    *,
    titles: tuple[str, str] | None = None,
) -> Path:
    """Side-by-side ``Q`` lattices for uniform-input vs. uniform-output sampling."""
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    left_title, right_title = titles or ("uniform input", "uniform output")
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 5.0))
    for ax, graph, sub_title in (
        (axes[0], input_graph, left_title),
        (axes[1], output_graph, right_title),
    ):
        _draw_lattice(ax, graph, graph.q_nodes, color="C1")
        ax.set_xlabel("$q_0$")
        if graph.q_nodes.shape[1] == 2:
            ax.set_ylabel("$q_1$")
        ax.set_title(sub_title)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_edge_trace(
    trace: EdgeTraceV2, path_out: Path | str, *, title: str | None = None
) -> Path:
    """Plot ``s -> q`` and ``s -> u`` for one Version 2 edge trace."""
    plt = _require_matplotlib()
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax_q, ax_u) = plt.subplots(1, 2, figsize=(10.0, 4.0))
    for axis in range(trace.q.shape[1]):
        ax_q.plot(trace.s, trace.q[:, axis], marker=".", label=f"$q_{{{axis}}}$")
    for axis in range(trace.u.shape[1]):
        ax_u.plot(trace.s, trace.u[:, axis], marker=".", label=f"$u_{{{axis}}}$")
    if trace.first_invalid_index is not None:
        s_bad = float(trace.s[trace.first_invalid_index])
        ax_q.axvline(s_bad, color="C3", linestyle="--", linewidth=1.0)
        ax_u.axvline(s_bad, color="C3", linestyle="--", linewidth=1.0)
    ax_q.set_xlabel("$s$")
    ax_q.set_ylabel("$q$")
    ax_q.legend(loc="best", fontsize=8)
    ax_u.set_xlabel("$s$")
    ax_u.set_ylabel("$u$")
    ax_u.legend(loc="best", fontsize=8)
    fig.suptitle(title or "Edge trace")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
