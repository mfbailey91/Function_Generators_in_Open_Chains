"""Expansion-count figure helpers for the pilot study (IM-017)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from inequality_mechanisms.metrics.expansions import (
    paired_log_ratios_for_algorithm,
    successful_expansions,
    successful_rhos,
)

_BOX_ORDER: tuple[tuple[str, str, str], ...] = (
    ("dijkstra", "gearbox", "Dijkstra gearbox"),
    ("dijkstra", "fourbar", "Dijkstra fourbar"),
    ("astar", "gearbox", "A* gearbox"),
    ("astar", "fourbar", "A* fourbar"),
)


def _require_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required for expansion plots; "
            "install with pip install matplotlib"
        ) from exc
    return plt


def plot_raw_expansions(
    rows: Sequence[Mapping[str, Any]],
    path: Path | str,
    *,
    title: str = "Pilot Monte Carlo: expansion-count distributions",
) -> Path:
    """Write a boxplot of raw ``n_expanded`` by algorithm × mechanism."""
    plt = _require_matplotlib()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    data: list[list[int]] = []
    labels: list[str] = []
    for algorithm, mechanism, label in _BOX_ORDER:
        vals = successful_expansions(rows, algorithm=algorithm, mechanism=mechanism)
        data.append(vals)
        labels.append(label)

    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    ax.boxplot(data, tick_labels=labels, showfliers=False)
    ax.set_ylabel("Node expansions")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_normalized_expansions(
    rows: Sequence[Mapping[str, Any]],
    path: Path | str,
    *,
    title: str = "Pilot Monte Carlo: normalized expansion fractions",
) -> Path:
    """Write a boxplot of ``rho_expanded = N_expanded / N_valid_nodes``."""
    plt = _require_matplotlib()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    data: list[list[float]] = []
    labels: list[str] = []
    for algorithm, mechanism, label in _BOX_ORDER:
        vals = successful_rhos(rows, algorithm=algorithm, mechanism=mechanism)
        data.append(vals)
        labels.append(label)

    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    ax.boxplot(data, tick_labels=labels, showfliers=False)
    ax.set_ylabel(r"$\rho_{\mathrm{expanded}}$")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_paired_log_ratios(
    rows: Sequence[Mapping[str, Any]],
    path: Path | str,
    *,
    title: str = "Pilot Monte Carlo: paired node-expansion ratios",
    bins: int = 40,
) -> Path:
    """Write overlaid histograms of ``log(N_4R / N_gear)`` for Dijkstra and A*."""
    plt = _require_matplotlib()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    dijkstra_vals = paired_log_ratios_for_algorithm(rows, algorithm="dijkstra")
    astar_vals = paired_log_ratios_for_algorithm(rows, algorithm="astar")

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    plotted = False
    if dijkstra_vals:
        ax.hist(dijkstra_vals, bins=bins, alpha=0.5, label="Dijkstra", color="C0")
        plotted = True
    if astar_vals:
        ax.hist(astar_vals, bins=bins, alpha=0.5, label="A*", color="C1")
        plotted = True
    ax.axvline(0.0, color="C0", linewidth=1.5)
    ax.set_xlabel(r"$\log(N_{\mathrm{expanded, 4R}} / N_{\mathrm{expanded, gear}})$")
    ax.set_ylabel("Paired trials")
    ax.set_title(title)
    if plotted:
        ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
