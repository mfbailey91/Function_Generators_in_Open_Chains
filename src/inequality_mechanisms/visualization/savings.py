"""A* savings figure helpers (S4-07)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _require_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required for savings plots; "
            "install with pip install matplotlib"
        ) from exc
    return plt


def _save(fig: Any, path_out: Path | str, plt: Any) -> Path:
    out = Path(path_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_astar_vs_dijkstra_expansions(
    savings_rows: Sequence[Mapping[str, Any]],
    path_out: Path | str,
) -> Path:
    """Scatter A* expansions versus Dijkstra expansions."""
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(5.5, 5.0))
    for mech, marker in (("gearbox", "o"), ("fourbar", "s")):
        xs = [
            float(r["n_expanded_dijkstra"])
            for r in savings_rows
            if r.get("mechanism") == mech
        ]
        ys = [
            float(r["n_expanded_astar"])
            for r in savings_rows
            if r.get("mechanism") == mech
        ]
        if xs:
            ax.scatter(xs, ys, marker=marker, alpha=0.7, label=mech)
    if savings_rows:
        hi = max(
            max(float(r["n_expanded_dijkstra"]) for r in savings_rows),
            max(float(r["n_expanded_astar"]) for r in savings_rows),
        )
        ax.plot([0, hi], [0, hi], color="0.5", lw=1.0, ls="--", label="y=x")
    ax.set_xlabel("Dijkstra expansions")
    ax.set_ylabel("A* expansions")
    ax.set_title("A* vs Dijkstra expansions")
    ax.legend(fontsize=8)
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()
    return _save(fig, path_out, plt)


def plot_savings_by_mechanism_cost(
    savings_rows: Sequence[Mapping[str, Any]],
    path_out: Path | str,
) -> Path:
    """Boxplot of A* savings by mechanism and cost type."""
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    labels: list[str] = []
    data: list[list[float]] = []
    for mech in ("gearbox", "fourbar"):
        for cost in sorted({str(r["cost_type"]) for r in savings_rows}):
            vals = [
                float(r["s_a"])
                for r in savings_rows
                if r.get("mechanism") == mech and str(r["cost_type"]) == cost
            ]
            if vals:
                labels.append(f"{mech}\n{cost}")
                data.append(vals)
    if data:
        try:
            ax.boxplot(data, tick_labels=labels, showfliers=False)
        except TypeError:  # matplotlib < 3.9
            ax.boxplot(data, labels=labels, showfliers=False)
    else:
        ax.text(0.5, 0.5, "no savings pairs", ha="center", va="center")
    ax.axhline(0.0, color="0.5", lw=0.8)
    ax.set_ylabel(r"$S_A = 1 - N_{A*}/N_D$")
    ax.set_title("A* savings by mechanism and cost")
    fig.tight_layout()
    return _save(fig, path_out, plt)


def _scatter_vs_savings(
    savings_rows: Sequence[Mapping[str, Any]],
    x_field: str,
    path_out: Path | str,
    *,
    xlabel: str,
    title: str,
) -> Path:
    plt = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    any_points = False
    for mech, marker in (("gearbox", "o"), ("fourbar", "s")):
        xs: list[float] = []
        ys: list[float] = []
        for r in savings_rows:
            if r.get("mechanism") != mech:
                continue
            x = r.get(x_field)
            if x is None:
                continue
            try:
                xf = float(x)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(xf):
                continue
            xs.append(xf)
            ys.append(float(r["s_a"]))
        if xs:
            any_points = True
            ax.scatter(xs, ys, marker=marker, alpha=0.7, label=mech)
    if not any_points:
        ax.text(0.5, 0.5, f"no {x_field} values", ha="center", va="center")
    else:
        ax.legend(fontsize=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(r"$S_A$")
    ax.set_title(title)
    fig.tight_layout()
    return _save(fig, path_out, plt)


def plot_heuristic_strength_vs_savings(
    savings_rows: Sequence[Mapping[str, Any]],
    path_out: Path | str,
) -> Path:
    """Scatter mean heuristic strength versus A* savings."""
    return _scatter_vs_savings(
        savings_rows,
        "mean_heuristic_strength",
        path_out,
        xlabel="mean heuristic strength",
        title="Heuristic strength vs A* savings",
    )


def plot_edge_cost_variance_vs_savings(
    savings_rows: Sequence[Mapping[str, Any]],
    path_out: Path | str,
) -> Path:
    """Scatter edge-cost variance versus A* savings."""
    return _scatter_vs_savings(
        savings_rows,
        "edge_cost_variance",
        path_out,
        xlabel="edge-cost variance",
        title="Edge-cost variance vs A* savings",
    )


def plot_path_length_vs_savings(
    savings_rows: Sequence[Mapping[str, Any]],
    path_out: Path | str,
    *,
    length_field: str = "path_length_q",
) -> Path:
    """Scatter path length versus A* savings."""
    return _scatter_vs_savings(
        savings_rows,
        length_field,
        path_out,
        xlabel=length_field,
        title=f"{length_field} vs A* savings",
    )
