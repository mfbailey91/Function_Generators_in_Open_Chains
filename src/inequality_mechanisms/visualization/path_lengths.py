"""Path-length distribution figure helpers for Monte Carlo / pilot runs."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

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
            "matplotlib is required for path-length plots; "
            "install with pip install matplotlib"
        ) from exc
    return plt


def _is_found(row: Mapping[str, Any]) -> bool:
    found = row.get("found")
    if found is None:
        return True
    return bool(found)


def successful_path_lengths(
    rows: Sequence[Mapping[str, Any]],
    field: str,
    *,
    algorithm: str,
    mechanism: str,
) -> list[float]:
    """Return finite ``field`` values for found trials matching algorithm/mechanism."""
    out: list[float] = []
    for row in rows:
        if str(row.get("algorithm")) != algorithm:
            continue
        if str(row.get("mechanism")) != mechanism:
            continue
        if not _is_found(row):
            continue
        raw = row.get(field)
        if raw is None:
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(val):
            continue
        out.append(val)
    return out


def plot_path_length_distributions(
    rows: Sequence[Mapping[str, Any]],
    field: str,
    path: Path | str,
    *,
    title: str,
    ylabel: str,
) -> Path:
    """Write a boxplot of ``field`` by algorithm × mechanism."""
    plt = _require_matplotlib()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    data: list[list[float]] = []
    labels: list[str] = []
    for algorithm, mechanism, label in _BOX_ORDER:
        vals = successful_path_lengths(
            rows, field, algorithm=algorithm, mechanism=mechanism
        )
        data.append(vals)
        labels.append(label)

    fig, ax = plt.subplots(figsize=(8.0, 4.5))
    ax.boxplot(data, tick_labels=labels, showfliers=False)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_path_length_q(
    rows: Sequence[Mapping[str, Any]],
    path: Path | str,
    *,
    title: str = "Pilot Monte Carlo: joint path length L_Q",
) -> Path:
    """Write a boxplot of joint/output path length ``path_length_q``."""
    return plot_path_length_distributions(
        rows,
        "path_length_q",
        path,
        title=title,
        ylabel=r"$L_Q$",
    )


def plot_path_length_x(
    rows: Sequence[Mapping[str, Any]],
    path: Path | str,
    *,
    title: str = "Pilot Monte Carlo: end-effector path length L_X",
) -> Path:
    """Write a boxplot of end-effector path length ``path_length_x``."""
    return plot_path_length_distributions(
        rows,
        "path_length_x",
        path,
        title=title,
        ylabel=r"$L_X$",
    )
