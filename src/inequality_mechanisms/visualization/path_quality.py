"""Path-quality diagnostic cards and Sprint Five study figures (S5-06 / S5-08)."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.visualization.paths import (
    path_inputs,
    path_outputs,
)


def _require_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "matplotlib is required for path-quality figures; "
            "install with pip install matplotlib"
        ) from exc
    return plt


def closest_nonlocal_revisit(
    points: np.ndarray,
    *,
    exclusion_steps: int,
) -> tuple[int, int, float] | None:
    """Return ``(i, j, distance)`` for the closest nonlocal revisit pair."""
    arr = np.asarray(points, dtype=np.float64)
    n = int(arr.shape[0])
    m = int(exclusion_steps)
    best: tuple[int, int, float] | None = None
    for i in range(n):
        for j in range(i + 1, n):
            if (j - i) <= m:
                continue
            d = float(np.linalg.norm(arr[i, :2] - arr[j, :2]))
            if best is None or d < best[2]:
                best = (i, j, d)
    return best


def _intersection_points(points: np.ndarray) -> list[np.ndarray]:
    """Approximate intersection midpoints for nonadjacent crossing segments."""
    from inequality_mechanisms.metrics.path_quality import segments_intersect

    arr = np.asarray(points, dtype=np.float64)
    n_seg = arr.shape[0] - 1
    mids: list[np.ndarray] = []
    for i in range(n_seg):
        for j in range(i + 2, n_seg):
            a0, a1 = arr[i], arr[i + 1]
            b0, b1 = arr[j], arr[j + 1]
            if segments_intersect(a0, a1, b0, b1):
                mids.append(0.25 * (a0[:2] + a1[:2] + b0[:2] + b1[:2]))
    return mids


def plot_path_quality_card(
    graph: ConstrainedInputGraph,
    path: Sequence[int],
    out_path: Path | str,
    *,
    metadata: Mapping[str, Any] | None = None,
    quality: Mapping[str, Any] | None = None,
    revisit_exclusion_steps: int = 4,
    title: str | None = None,
) -> Path:
    """Write a compact U / Q / X path-quality diagnostic card."""
    plt = _require_matplotlib()
    nodes = [int(n) for n in path]
    u = path_inputs(graph, nodes)
    q = path_outputs(graph, nodes)
    plant = Planar2R()
    x = np.vstack([plant.forward(qi) for qi in q])

    dest = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(12.0, 4.2))
    panels = (
        (axes[0], u, "Input U", "u0", "u1"),
        (axes[1], q, "Output Q", "q0", "q1"),
        (axes[2], x, "Cartesian X", "x", "y"),
    )
    for ax, pts, label, xlab, ylab in panels:
        ax.plot(pts[:, 0], pts[:, 1], "-o", markersize=3, linewidth=1.2)
        ax.scatter([pts[0, 0]], [pts[0, 1]], c="green", s=40, zorder=5, label="start")
        ax.scatter([pts[-1, 0]], [pts[-1, 1]], c="red", s=40, zorder=5, label="goal")
        if label != "Input U":
            for mid in _intersection_points(pts):
                ax.scatter([mid[0]], [mid[1]], c="magenta", marker="x", s=50, zorder=6)
            pair = closest_nonlocal_revisit(
                pts, exclusion_steps=revisit_exclusion_steps
            )
            if pair is not None:
                i, j, _ = pair
                ax.plot(
                    [pts[i, 0], pts[j, 0]],
                    [pts[i, 1], pts[j, 1]],
                    "--",
                    color="orange",
                    linewidth=1.0,
                    label="near-revisit",
                )
        ax.set_title(label)
        ax.set_xlabel(xlab)
        ax.set_ylabel(ylab)
        ax.set_aspect("equal", adjustable="datalim")
        ax.legend(loc="best", fontsize=7)

    meta = dict(metadata or {})
    qual = dict(quality or {})
    summary_lines = [
        f"Mechanism: {meta.get('mechanism', '?')}",
        f"Algorithm: {meta.get('algorithm', '?')}",
        f"Cost: {meta.get('cost_type', '?')}",
        "",
        f"Path edges: {qual.get('n_path_edges', meta.get('n_path_edges', '?'))}",
        f"L_U: {_fmt(qual.get('path_length_u', meta.get('path_length_u')))}",
        f"L_Q: {_fmt(qual.get('path_length_q', meta.get('path_length_q')))}",
        f"L_X: {_fmt(qual.get('path_length_x', meta.get('path_length_x')))}",
        f"R_U: {_fmt(qual.get('directness_ratio_u'))}",
        f"R_Q: {_fmt(qual.get('directness_ratio_q'))}",
        f"R_X: {_fmt(qual.get('directness_ratio_x'))}",
        f"T_Q: {_fmt(qual.get('cumulative_turning_q'))} rad",
        f"T_X: {_fmt(qual.get('cumulative_turning_x'))} rad",
        f"Q intersections: {qual.get('self_intersections_q', '?')}",
        f"X intersections: {qual.get('self_intersections_x', '?')}",
        f"Q near-revisit: {_fmt(qual.get('near_revisit_distance_q'))}",
        f"X near-revisit: {_fmt(qual.get('near_revisit_distance_x'))}",
    ]
    fig.suptitle(title or "Path quality card", fontsize=11)
    fig.text(
        0.01,
        0.5,
        "\n".join(summary_lines),
        va="center",
        ha="left",
        family="monospace",
        fontsize=7,
    )
    fig.subplots_adjust(left=0.28, right=0.98, wspace=0.35)
    fig.savefig(dest, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return dest


def _fmt(value: Any) -> str:
    if value is None:
        return "undefined"
    try:
        return f"{float(value):.4g}"
    except (TypeError, ValueError):
        return str(value)


def select_representative_trials(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_cards: int = 5,
    algorithm: str = "astar",
    cost_type: str = "output_euclidean",
) -> list[dict[str, Any]]:
    """Deterministically select representative path-quality card trials.

    Criteria (in order; duplicates skipped):

    1. median |expansion gearbox − fourbar| difference;
    2. largest Cartesian directness difference;
    3. largest cumulative-turning difference;
    4. any path with Cartesian self-intersection;
    5. smallest near-revisit distance in X.
    """
    found = [
        r
        for r in rows
        if r.get("found")
        and str(r.get("algorithm")) == algorithm
        and str(r.get("cost_type")) == cost_type
    ]
    if not found:
        found = [r for r in rows if r.get("found")]

    by_trial: dict[int, dict[str, Mapping[str, Any]]] = {}
    for row in found:
        by_trial.setdefault(int(row["trial_index"]), {})[str(row["mechanism"])] = row

    selections: list[dict[str, Any]] = []
    used: set[tuple[int, str]] = set()

    def _add(trial_index: int, mechanism: str, reason: str) -> None:
        key = (trial_index, mechanism)
        if key in used:
            return
        row = by_trial.get(trial_index, {}).get(mechanism)
        if row is None:
            return
        used.add(key)
        selections.append(
            {
                "trial_index": trial_index,
                "mechanism": mechanism,
                "algorithm": row.get("algorithm"),
                "cost_type": row.get("cost_type"),
                "reason": reason,
                "row": row,
            }
        )

    # 1. Median expansion difference (prefer fourbar row for the card).
    exp_diffs: list[tuple[float, int]] = []
    for trial_index, pair in by_trial.items():
        if "gearbox" in pair and "fourbar" in pair:
            g = pair["gearbox"].get("n_expanded")
            f = pair["fourbar"].get("n_expanded")
            if g is None or f is None:
                continue
            exp_diffs.append((abs(float(f) - float(g)), trial_index))
    if exp_diffs:
        exp_diffs.sort(key=lambda t: (t[0], t[1]))
        mid = exp_diffs[len(exp_diffs) // 2]
        _add(mid[1], "fourbar", "median_expansion_difference")

    # 2. Largest Cartesian directness difference.
    rx_diffs: list[tuple[float, int]] = []
    for trial_index, pair in by_trial.items():
        if "gearbox" not in pair or "fourbar" not in pair:
            continue
        g = pair["gearbox"].get("directness_ratio_x")
        f = pair["fourbar"].get("directness_ratio_x")
        if g is None or f is None:
            continue
        rx_diffs.append((abs(float(f) - float(g)), trial_index))
    if rx_diffs:
        rx_diffs.sort(key=lambda t: (-t[0], t[1]))
        _add(rx_diffs[0][1], "fourbar", "largest_cartesian_directness_difference")

    # 3. Largest cumulative-turning difference.
    t_diffs: list[tuple[float, int]] = []
    for trial_index, pair in by_trial.items():
        if "gearbox" not in pair or "fourbar" not in pair:
            continue
        g = pair["gearbox"].get("cumulative_turning_x")
        f = pair["fourbar"].get("cumulative_turning_x")
        if g is None or f is None:
            continue
        t_diffs.append((abs(float(f) - float(g)), trial_index))
    if t_diffs:
        t_diffs.sort(key=lambda t: (-t[0], t[1]))
        _add(t_diffs[0][1], "fourbar", "largest_cumulative_turning_difference")

    # 4. Cartesian self-intersection.
    for trial_index in sorted(by_trial):
        for mechanism, row in by_trial[trial_index].items():
            if int(row.get("self_intersections_x") or 0) > 0:
                _add(trial_index, mechanism, "cartesian_self_intersection")
                break
        if len(selections) >= max_cards:
            break

    # 5. Smallest near-revisit distance.
    revisits: list[tuple[float, int, str]] = []
    for trial_index, pair in by_trial.items():
        for mechanism, row in pair.items():
            d = row.get("near_revisit_distance_x")
            if d is None:
                continue
            revisits.append((float(d), trial_index, mechanism))
    if revisits:
        revisits.sort(key=lambda t: (t[0], t[1], t[2]))
        d, ti, mech = revisits[0]
        _add(ti, mech, "smallest_near_revisit_distance_x")

    # Fill remaining slots deterministically.
    for trial_index in sorted(by_trial):
        if len(selections) >= max_cards:
            break
        for mechanism in ("fourbar", "gearbox"):
            if len(selections) >= max_cards:
                break
            _add(trial_index, mechanism, "deterministic_fill")

    return selections[:max_cards]


def write_path_quality_bundle(
    out_dir: Path | str,
    *,
    selections: Sequence[Mapping[str, Any]],
    graphs_by_key: Mapping[tuple[Any, ...], ConstrainedInputGraph],
    revisit_exclusion_steps: int = 4,
) -> dict[str, Any]:
    """Write representative cards and ``representative_trials.json``."""
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for i, sel in enumerate(selections, start=1):
        row = sel["row"]
        trial_index = int(sel["trial_index"])
        mechanism = str(sel["mechanism"])
        graph = graphs_by_key.get((trial_index, mechanism))
        path = list(row.get("_path") or [])
        if graph is None or not path:
            continue
        name = f"representative_trial_{i:03d}.png"
        plot_path_quality_card(
            graph,
            path,
            root / name,
            metadata={
                "mechanism": mechanism,
                "algorithm": row.get("algorithm"),
                "cost_type": row.get("cost_type"),
                "n_path_edges": row.get("n_path_edges"),
                "path_length_u": row.get("path_length_u"),
                "path_length_q": row.get("path_length_q"),
                "path_length_x": row.get("path_length_x"),
            },
            quality=row,
            revisit_exclusion_steps=revisit_exclusion_steps,
            title=f"Trial {trial_index} / {mechanism} ({sel.get('reason')})",
        )
        manifest.append(
            {
                "file": name,
                "trial_index": trial_index,
                "mechanism": mechanism,
                "algorithm": row.get("algorithm"),
                "cost_type": row.get("cost_type"),
                "reason": sel.get("reason"),
            }
        )
    meta_path = root / "representative_trials.json"
    meta_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"n_cards": len(manifest), "cards": manifest}


def _paired_values(
    rows: Sequence[Mapping[str, Any]],
    field: str,
    *,
    algorithm: str = "dijkstra",
    cost_type: str | None = None,
) -> tuple[list[float], list[float]]:
    by_key: dict[tuple[Any, ...], dict[str, float]] = {}
    for row in rows:
        if not row.get("found"):
            continue
        if str(row.get("algorithm")) != algorithm:
            continue
        if cost_type is not None and str(row.get("cost_type")) != cost_type:
            continue
        val = row.get(field)
        if val is None:
            continue
        try:
            fval = float(val)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(fval):
            continue
        key = (int(row["trial_index"]), str(row.get("cost_type", "")))
        by_key.setdefault(key, {})[str(row["mechanism"])] = fval
    g_vals: list[float] = []
    f_vals: list[float] = []
    for pair in by_key.values():
        if "gearbox" in pair and "fourbar" in pair:
            g_vals.append(pair["gearbox"])
            f_vals.append(pair["fourbar"])
    return g_vals, f_vals


def plot_paired_metric_scatter(
    rows: Sequence[Mapping[str, Any]],
    field: str,
    out_path: Path | str,
    *,
    algorithm: str = "dijkstra",
    title: str | None = None,
) -> Path:
    """Scatter gearbox vs four-bar values for one metric (identity line)."""
    plt = _require_matplotlib()
    g_vals, f_vals = _paired_values(rows, field, algorithm=algorithm)
    dest = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.0, 5.0))
    if g_vals:
        ax.scatter(g_vals, f_vals, s=18, alpha=0.7)
        lo = min(min(g_vals), min(f_vals))
        hi = max(max(g_vals), max(f_vals))
        ax.plot([lo, hi], [lo, hi], "k--", linewidth=1.0)
    ax.set_xlabel(f"gearbox {field}")
    ax.set_ylabel(f"fourbar {field}")
    ax.set_title(title or f"Paired {field}")
    fig.tight_layout()
    fig.savefig(dest, dpi=120)
    plt.close(fig)
    return dest


def plot_expansions_vs_quality(
    rows: Sequence[Mapping[str, Any]],
    quality_field: str,
    out_path: Path | str,
    *,
    algorithm: str = "dijkstra",
) -> Path:
    """Scatter node expansions versus a path-quality metric."""
    plt = _require_matplotlib()
    xs: list[float] = []
    ys: list[float] = []
    for row in rows:
        if not row.get("found"):
            continue
        if str(row.get("algorithm")) != algorithm:
            continue
        n_exp = row.get("n_expanded")
        qv = row.get(quality_field)
        if n_exp is None or qv is None:
            continue
        try:
            xs.append(float(n_exp))
            ys.append(float(qv))
        except (TypeError, ValueError):
            continue
    dest = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.5, 4.0))
    if xs:
        ax.scatter(xs, ys, s=16, alpha=0.7)
    ax.set_xlabel("n_expanded")
    ax.set_ylabel(quality_field)
    ax.set_title(f"Expansions vs {quality_field}")
    fig.tight_layout()
    fig.savefig(dest, dpi=120)
    plt.close(fig)
    return dest


def plot_metric_histogram(
    rows: Sequence[Mapping[str, Any]],
    field: str,
    out_path: Path | str,
    *,
    algorithm: str = "dijkstra",
) -> Path:
    """Histogram of a metric split by mechanism."""
    plt = _require_matplotlib()
    by_mech: dict[str, list[float]] = {"gearbox": [], "fourbar": []}
    for row in rows:
        if not row.get("found"):
            continue
        if str(row.get("algorithm")) != algorithm:
            continue
        mech = str(row.get("mechanism"))
        if mech not in by_mech:
            continue
        val = row.get(field)
        if val is None:
            continue
        try:
            by_mech[mech].append(float(val))
        except (TypeError, ValueError):
            continue
    dest = Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5.5, 4.0))
    data = [by_mech["gearbox"], by_mech["fourbar"]]
    labels = ["gearbox", "fourbar"]
    if any(data):
        ax.hist(data, bins=12, label=labels, alpha=0.7)
        ax.legend()
    ax.set_xlabel(field)
    ax.set_ylabel("count")
    ax.set_title(field)
    fig.tight_layout()
    fig.savefig(dest, dpi=120)
    plt.close(fig)
    return dest


def path_quality_summary_tables(
    rows: Sequence[Mapping[str, Any]],
    *,
    algorithm: str = "dijkstra",
) -> dict[str, str]:
    """Return CSV strings for standard Sprint Five summary tables."""

    def _mean_table(fields: Sequence[str]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["mechanism", "cost_type", *fields, "n"],
        )
        writer.writeheader()
        groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
        for row in rows:
            if not row.get("found"):
                continue
            if str(row.get("algorithm")) != algorithm:
                continue
            key = (str(row["mechanism"]), str(row.get("cost_type", "")))
            groups.setdefault(key, []).append(row)
        for (mech, cost), group in sorted(groups.items()):
            out: dict[str, Any] = {
                "mechanism": mech,
                "cost_type": cost,
                "n": len(group),
            }
            for field in fields:
                vals = []
                for r in group:
                    v = r.get(field)
                    if v is None:
                        continue
                    try:
                        fv = float(v)
                    except (TypeError, ValueError):
                        continue
                    if np.isfinite(fv):
                        vals.append(fv)
                out[field] = float(np.mean(vals)) if vals else ""
            writer.writerow(out)
        return buf.getvalue()

    return {
        "path_length_summary": _mean_table(
            ["n_path_edges", "path_length_u", "path_length_q", "path_length_x"]
        ),
        "directness_summary": _mean_table(
            ["directness_ratio_u", "directness_ratio_q", "directness_ratio_x"]
        ),
        "turning_summary": _mean_table(
            ["cumulative_turning_q", "cumulative_turning_x"]
        ),
        "intersection_revisit_summary": _mean_table(
            [
                "self_intersections_q",
                "self_intersections_x",
                "near_revisit_distance_q",
                "near_revisit_distance_x",
            ]
        ),
    }
