"""Version 2 expansion-count figures for shared-Q paired studies (Sprint V2.8)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _require_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required for expansion plots; "
            "install with pip install matplotlib"
        ) from exc
    return plt


def _mechanism_ids_present(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    present = {str(r.get("mechanism_id", "")) for r in rows}
    order = [
        "fourbar",
        "span_matched_gearbox",
        "equivalent_affine_gearbox",
        "unit_gearbox",
    ]
    ids = [m for m in order if m in present]
    if "span_matched_gearbox" in ids and "equivalent_affine_gearbox" in ids:
        ids = [m for m in ids if m != "equivalent_affine_gearbox"]
    return ids


_LABELS = {
    "fourbar": "Four-bar",
    "span_matched_gearbox": "Span-matched gearbox",
    "equivalent_affine_gearbox": "Matched gearbox",
    "unit_gearbox": "Unit gearbox",
}


def plot_v2_expansions_by_mechanism(
    rows: Sequence[Mapping[str, Any]],
    path: Path | str,
    *,
    title: str = "Shared-Q study: node expansions by mechanism",
    algorithm: str = "dijkstra",
) -> Path:
    """Boxplot of ``n_expanded`` for four-bar vs span-matched gearbox."""
    plt = _require_matplotlib()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    mech_ids = _mechanism_ids_present(rows)
    data: list[list[float]] = []
    labels: list[str] = []
    for mechanism_id in mech_ids:
        vals = [
            float(r["n_expanded"])
            for r in rows
            if bool(r.get("found", False))
            and str(r.get("algorithm", "")) == algorithm
            and str(r.get("mechanism_id", "")) == mechanism_id
            and isinstance(r.get("n_expanded"), (int, float))
        ]
        data.append(vals)
        labels.append(_LABELS.get(mechanism_id, mechanism_id))

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    if any(data):
        ax.boxplot(data, tick_labels=labels, showfliers=False)
    ax.set_ylabel("Node expansions")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=10)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_v2_expansions_by_alpha(
    rows: Sequence[Mapping[str, Any]],
    path: Path | str,
    *,
    title: str = "Shared-Q study: expansions vs alpha",
    algorithm: str = "dijkstra",
) -> Path:
    """Grouped boxplots of expansions by alpha for each mechanism."""
    plt = _require_matplotlib()
    from matplotlib.patches import Patch

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    alphas = sorted(
        {
            float(r["alpha"])
            for r in rows
            if r.get("alpha") is not None and bool(r.get("found", False))
        }
    )
    mech_ids = _mechanism_ids_present(rows)
    colors = ["C0", "C1", "C2", "C3"]
    n_mech = max(len(mech_ids), 1)

    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    width = 0.8 / n_mech
    positions: list[float] = []
    data: list[list[float]] = []
    xticks: list[float] = []
    xticklabels: list[str] = []

    for i, alpha in enumerate(alphas):
        for j, mechanism_id in enumerate(mech_ids):
            vals = [
                float(r["n_expanded"])
                for r in rows
                if bool(r.get("found", False))
                and str(r.get("algorithm", "")) == algorithm
                and str(r.get("mechanism_id", "")) == mechanism_id
                and r.get("alpha") is not None
                and abs(float(r["alpha"]) - alpha) < 1e-12
                and isinstance(r.get("n_expanded"), (int, float))
            ]
            pos = float(i) + (j - 0.5 * (n_mech - 1)) * width
            positions.append(pos)
            data.append(vals)
        xticks.append(float(i))
        xticklabels.append(f"{alpha:g}")

    if data:
        bp = ax.boxplot(data, positions=positions, widths=width * 0.9, showfliers=False)
        for idx, box in enumerate(bp.get("boxes", [])):
            box.set_color(colors[(idx % n_mech) % len(colors)])

    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels)
    ax.set_xlabel(r"$\alpha$ (Q weight)")
    ax.set_ylabel("Node expansions")
    ax.set_title(title)
    handles = [
        Patch(color=colors[j % len(colors)], label=_LABELS.get(mid, mid))
        for j, mid in enumerate(mech_ids)
    ]
    if handles:
        ax.legend(handles=handles, loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
