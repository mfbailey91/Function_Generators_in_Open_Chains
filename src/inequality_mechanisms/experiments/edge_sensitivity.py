"""Edge-validation sampling sensitivity study (IM-037).

Compares constrained-graph and search metrics across
``edge_samples ∈ {5, 9, 17, 33, 65}`` on a fixed paired trial setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.random import Generator

from inequality_mechanisms.experiments.tasks import generate_paired_tasks
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox
from inequality_mechanisms.mechanisms.population import (
    limits_from_fourbar_follower_ranges,
)
from inequality_mechanisms.search.dijkstra import dijkstra
from inequality_mechanisms.spaces.output_space import OutputSpace

DEFAULT_EDGE_SAMPLE_GRID: tuple[int, ...] = (5, 9, 17, 33, 65)


@dataclass(frozen=True, slots=True)
class EdgeSensitivityRow:
    """One edge_samples setting and its graph / search metrics."""

    edge_samples: int
    n_valid_nodes_gearbox: int
    n_valid_nodes_fourbar: int
    n_valid_edges_gearbox: int
    n_valid_edges_fourbar: int
    n_components_gearbox: int
    n_components_fourbar: int
    task_feasible: bool
    cost_gearbox: float | None
    cost_fourbar: float | None
    n_expanded_gearbox: int | None
    n_expanded_fourbar: int | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON / CSV writers."""
        return {
            "edge_samples": self.edge_samples,
            "n_valid_nodes_gearbox": self.n_valid_nodes_gearbox,
            "n_valid_nodes_fourbar": self.n_valid_nodes_fourbar,
            "n_valid_edges_gearbox": self.n_valid_edges_gearbox,
            "n_valid_edges_fourbar": self.n_valid_edges_fourbar,
            "n_components_gearbox": self.n_components_gearbox,
            "n_components_fourbar": self.n_components_fourbar,
            "task_feasible": self.task_feasible,
            "cost_gearbox": self.cost_gearbox,
            "cost_fourbar": self.cost_fourbar,
            "n_expanded_gearbox": self.n_expanded_gearbox,
            "n_expanded_fourbar": self.n_expanded_fourbar,
        }


def run_edge_sensitivity(
    *,
    lengths: tuple[tuple[float, float, float, float], ...] = (
        (1.0, 2.5, 2.0, 2.0),
        (1.0, 2.5, 2.0, 2.0),
    ),
    shape: tuple[int, int] = (16, 16),
    seed: int = 0,
    edge_samples_grid: tuple[int, ...] = DEFAULT_EDGE_SAMPLE_GRID,
    rng: Generator | None = None,
) -> list[EdgeSensitivityRow]:
    """Run the IM-037 sensitivity sweep on one fixed mechanism pair.

    Task endpoints are sampled once at ``edge_samples=17`` (or the middle
    grid value) and reused so feasibility / cost changes reflect graph
    filtering, not task resampling.
    """
    if rng is None:
        rng = np.random.default_rng(int(seed))
    fourbar = IndependentFourBars.from_lengths(list(lengths), branch=1)
    limits = limits_from_fourbar_follower_ranges(fourbar, n_samples=181)
    space = OutputSpace.from_limits(limits)
    grid = PeriodicGrid2D(shape, wrap=(True, True))
    gearbox = UnitGearbox(dim=2)

    # Reference graphs for a shared task.
    ref_samples = 17 if 17 in edge_samples_grid else edge_samples_grid[len(edge_samples_grid) // 2]
    gb_ref = ConstrainedInputGraph(
        grid, gearbox, limits, edge_samples=ref_samples, output_space=space
    )
    fb_ref = ConstrainedInputGraph(
        grid, fourbar, limits, edge_samples=ref_samples, output_space=space
    )
    tasks = generate_paired_tasks(
        gb_ref, fb_ref, n_trials=1, rng=rng, min_output_separation=0.05
    )
    task = tasks[0]

    rows: list[EdgeSensitivityRow] = []
    for n_samples in edge_samples_grid:
        gb = ConstrainedInputGraph(
            grid, gearbox, limits, edge_samples=int(n_samples), output_space=space
        )
        fb = ConstrainedInputGraph(
            grid, fourbar, limits, edge_samples=int(n_samples), output_space=space
        )
        # Re-validate selected nodes under the new filter.
        gb_ok = gb.node_is_valid_id(task.gearbox.start_node_id) and gb.node_is_valid_id(
            task.gearbox.goal_node_id
        )
        fb_ok = fb.node_is_valid_id(task.fourbar.start_node_id) and fb.node_is_valid_id(
            task.fourbar.goal_node_id
        )
        cost_gb = cost_fb = None
        exp_gb = exp_fb = None
        feasible = False
        if gb_ok and fb_ok:
            r_gb = dijkstra(gb, task.gearbox.start_node_id, task.gearbox.goal_node_id)
            r_fb = dijkstra(fb, task.fourbar.start_node_id, task.fourbar.goal_node_id)
            feasible = bool(r_gb.found and r_fb.found)
            if r_gb.found:
                cost_gb = float(r_gb.cost)
                exp_gb = int(r_gb.n_expanded)
            if r_fb.found:
                cost_fb = float(r_fb.cost)
                exp_fb = int(r_fb.n_expanded)
        rows.append(
            EdgeSensitivityRow(
                edge_samples=int(n_samples),
                n_valid_nodes_gearbox=gb.valid_node_count,
                n_valid_nodes_fourbar=fb.valid_node_count,
                n_valid_edges_gearbox=gb.valid_edge_count(),
                n_valid_edges_fourbar=fb.valid_edge_count(),
                n_components_gearbox=gb.connected_component_count(),
                n_components_fourbar=fb.connected_component_count(),
                task_feasible=feasible,
                cost_gearbox=cost_gb,
                cost_fourbar=cost_fb,
                n_expanded_gearbox=exp_gb,
                n_expanded_fourbar=exp_fb,
            )
        )
    return rows


def edge_sensitivity_stable(
    rows: list[EdgeSensitivityRow],
    *,
    from_samples: int = 17,
) -> bool:
    """Return whether metrics stabilize for ``edge_samples >= from_samples``.

    Stability means identical valid-node counts, component counts, and
    nonincreasing valid-edge counts as sampling densifies, with unchanged
    task feasibility among those rows.
    """
    subset = [r for r in rows if r.edge_samples >= from_samples]
    if len(subset) < 2:
        return True
    base = subset[0]
    for row in subset[1:]:
        if row.n_valid_nodes_gearbox != base.n_valid_nodes_gearbox:
            return False
        if row.n_valid_nodes_fourbar != base.n_valid_nodes_fourbar:
            return False
        if row.n_components_gearbox != base.n_components_gearbox:
            return False
        if row.n_components_fourbar != base.n_components_fourbar:
            return False
        if row.n_valid_edges_gearbox > base.n_valid_edges_gearbox:
            return False
        if row.n_valid_edges_fourbar > base.n_valid_edges_fourbar:
            return False
        if row.task_feasible != base.task_feasible:
            return False
        base = row
    return True


def rows_to_csv(rows: list[EdgeSensitivityRow]) -> str:
    """Format sensitivity rows as CSV text."""
    if not rows:
        return ""
    keys = list(rows[0].to_dict().keys())
    lines = [",".join(keys)]
    for row in rows:
        payload = row.to_dict()
        lines.append(",".join("" if payload[k] is None else str(payload[k]) for k in keys))
    return "\n".join(lines) + "\n"
