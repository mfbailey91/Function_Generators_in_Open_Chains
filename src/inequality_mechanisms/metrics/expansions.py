"""Expansion-count metrics for paired mechanism trials (IM-017).

Normalized expansion fraction is

    rho = N_expanded / N_valid_nodes

Paired log-ratio is ``log(N_fourbar / N_gearbox)`` when both sides found a
path with positive expansion counts.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def normalized_expansion(n_expanded: int, n_valid_nodes: int) -> float:
    """Return ``n_expanded / n_valid_nodes``.

    Raises
    ------
    ValueError
        If ``n_expanded < 0`` or ``n_valid_nodes <= 0``.
    """
    if int(n_expanded) < 0:
        raise ValueError(f"n_expanded must be >= 0, got {n_expanded}")
    if int(n_valid_nodes) <= 0:
        raise ValueError(f"n_valid_nodes must be > 0, got {n_valid_nodes}")
    return float(n_expanded) / float(n_valid_nodes)


def paired_log_ratio(n_fourbar: int, n_gearbox: int) -> float:
    """Return ``log(n_fourbar / n_gearbox)``.

    Raises
    ------
    ValueError
        If either count is non-positive.
    """
    if int(n_fourbar) <= 0 or int(n_gearbox) <= 0:
        raise ValueError(
            "paired log-ratio requires positive expansion counts, "
            f"got fourbar={n_fourbar}, gearbox={n_gearbox}"
        )
    return math.log(float(n_fourbar) / float(n_gearbox))


def _is_found(row: Mapping[str, Any]) -> bool:
    return bool(row.get("found"))


def _group_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row["algorithm"]), str(row["mechanism"]))


def summarize_trials(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate trial rows into per-(algorithm, mechanism) and paired stats.

    Parameters
    ----------
    rows :
        Trial records as written by the pilot runner.

    Returns
    -------
    dict
        Keys: ``by_group``, ``paired_log_ratios``, ``n_rows``, ``n_found``,
        ``n_unreachable``.
    """
    by_group: dict[str, dict[str, Any]] = {}
    expansions: dict[tuple[str, str], list[int]] = defaultdict(list)
    rhos: dict[tuple[str, str], list[float]] = defaultdict(list)
    n_found = 0
    n_unreachable = 0

    for row in rows:
        key = _group_key(row)
        label = f"{key[0]}|{key[1]}"
        if label not in by_group:
            by_group[label] = {
                "algorithm": key[0],
                "mechanism": key[1],
                "n_trials": 0,
                "n_found": 0,
                "n_unreachable": 0,
                "median_n_expanded": None,
                "mean_rho_expanded": None,
            }
        group = by_group[label]
        group["n_trials"] += 1
        if _is_found(row):
            n_found += 1
            group["n_found"] += 1
            n_exp = int(row["n_expanded"])
            expansions[key].append(n_exp)
            rho = row.get("rho_expanded")
            if rho is not None:
                rhos[key].append(float(rho))
        else:
            n_unreachable += 1
            group["n_unreachable"] += 1
            reason = row.get("failure_reason")
            if reason == "unreachable" or reason is None:
                pass

    for label, group in by_group.items():
        key = (str(group["algorithm"]), str(group["mechanism"]))
        vals = expansions.get(key, [])
        if vals:
            group["median_n_expanded"] = float(statistics.median(vals))
        rho_vals = rhos.get(key, [])
        if rho_vals:
            group["mean_rho_expanded"] = float(statistics.fmean(rho_vals))

    paired_log_ratios: dict[str, dict[str, Any]] = {}
    by_trial_algo: dict[tuple[int, str], dict[str, Mapping[str, Any]]] = defaultdict(
        dict
    )
    for row in rows:
        trial_index = int(row["trial_index"])
        algo = str(row["algorithm"])
        mech = str(row["mechanism"])
        by_trial_algo[(trial_index, algo)][mech] = row

    for (trial_index, algo), mechs in sorted(by_trial_algo.items()):
        gb = mechs.get("gearbox")
        fb = mechs.get("fourbar")
        if gb is None or fb is None:
            continue
        if not (_is_found(gb) and _is_found(fb)):
            continue
        n_gb = int(gb["n_expanded"])
        n_fb = int(fb["n_expanded"])
        if n_gb <= 0 or n_fb <= 0:
            continue
        ratio = paired_log_ratio(n_fb, n_gb)
        if algo not in paired_log_ratios:
            paired_log_ratios[algo] = {
                "algorithm": algo,
                "n_pairs": 0,
                "values": [],
                "median": None,
            }
        entry = paired_log_ratios[algo]
        entry["n_pairs"] += 1
        entry["values"].append(ratio)

    for entry in paired_log_ratios.values():
        values: list[float] = entry.pop("values")
        entry["median"] = float(statistics.median(values)) if values else None
        entry["mean"] = float(statistics.fmean(values)) if values else None

    return {
        "n_rows": len(rows),
        "n_found": n_found,
        "n_unreachable": n_unreachable,
        "by_group": by_group,
        "paired_log_ratios": paired_log_ratios,
    }


def summary_table_rows(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten ``summarize_trials`` output into CSV-oriented row dicts."""
    rows: list[dict[str, Any]] = []
    by_group = summary.get("by_group", {})
    if not isinstance(by_group, Mapping):
        raise TypeError("summary['by_group'] must be a mapping")
    for label in sorted(by_group.keys()):
        g = by_group[label]
        rows.append(
            {
                "section": "group",
                "algorithm": g["algorithm"],
                "mechanism": g["mechanism"],
                "n_trials": g["n_trials"],
                "n_found": g["n_found"],
                "n_unreachable": g["n_unreachable"],
                "median_n_expanded": g["median_n_expanded"],
                "mean_rho_expanded": g["mean_rho_expanded"],
                "paired_log_ratio_median": None,
                "paired_log_ratio_n_pairs": None,
            }
        )
    ratios = summary.get("paired_log_ratios", {})
    if not isinstance(ratios, Mapping):
        raise TypeError("summary['paired_log_ratios'] must be a mapping")
    for algo in sorted(ratios.keys()):
        r = ratios[algo]
        rows.append(
            {
                "section": "paired_ratio",
                "algorithm": r["algorithm"],
                "mechanism": "fourbar/gearbox",
                "n_trials": None,
                "n_found": None,
                "n_unreachable": None,
                "median_n_expanded": None,
                "mean_rho_expanded": None,
                "paired_log_ratio_median": r["median"],
                "paired_log_ratio_n_pairs": r["n_pairs"],
            }
        )
    return rows


def summary_table_csv(summary: Mapping[str, Any]) -> str:
    """Serialize summary table rows as CSV text."""
    rows = summary_table_rows(summary)
    fieldnames = [
        "section",
        "algorithm",
        "mechanism",
        "n_trials",
        "n_found",
        "n_unreachable",
        "median_n_expanded",
        "mean_rho_expanded",
        "paired_log_ratio_median",
        "paired_log_ratio_n_pairs",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def successful_expansions(
    rows: Iterable[Mapping[str, Any]],
    *,
    algorithm: str,
    mechanism: str,
) -> list[int]:
    """Return ``n_expanded`` for found trials matching algorithm/mechanism."""
    out: list[int] = []
    for row in rows:
        if str(row.get("algorithm")) != algorithm:
            continue
        if str(row.get("mechanism")) != mechanism:
            continue
        if not _is_found(row):
            continue
        out.append(int(row["n_expanded"]))
    return out


def successful_rhos(
    rows: Iterable[Mapping[str, Any]],
    *,
    algorithm: str,
    mechanism: str,
) -> list[float]:
    """Return ``rho_expanded`` for found trials matching algorithm/mechanism."""
    out: list[float] = []
    for row in rows:
        if str(row.get("algorithm")) != algorithm:
            continue
        if str(row.get("mechanism")) != mechanism:
            continue
        if not _is_found(row):
            continue
        rho = row.get("rho_expanded")
        if rho is None:
            continue
        out.append(float(rho))
    return out


def paired_log_ratios_for_algorithm(
    rows: Sequence[Mapping[str, Any]],
    *,
    algorithm: str,
) -> list[float]:
    """Paired ``log(N_4R / N_gear)`` values for one algorithm."""
    by_trial: dict[int, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        if str(row.get("algorithm")) != algorithm:
            continue
        by_trial[int(row["trial_index"])][str(row["mechanism"])] = row

    values: list[float] = []
    for trial_index in sorted(by_trial.keys()):
        mechs = by_trial[trial_index]
        gb = mechs.get("gearbox")
        fb = mechs.get("fourbar")
        if gb is None or fb is None:
            continue
        if not (_is_found(gb) and _is_found(fb)):
            continue
        n_gb = int(gb["n_expanded"])
        n_fb = int(fb["n_expanded"])
        if n_gb <= 0 or n_fb <= 0:
            continue
        values.append(paired_log_ratio(n_fb, n_gb))
    return values
