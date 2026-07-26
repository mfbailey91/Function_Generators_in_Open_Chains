"""Materialize paired constrained graphs from an experiment config."""

from __future__ import annotations

from dataclasses import dataclass

from inequality_mechanisms.experiments.config import ExperimentConfig
from inequality_mechanisms.graphs.grid import PeriodicGrid2D
from inequality_mechanisms.graphs.validation import ConstrainedInputGraph
from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.spaces.limits import OutputJointLimits
from inequality_mechanisms.spaces.output_space import OutputSpace


@dataclass(frozen=True, slots=True)
class PairedGraphs:
    """Gearbox / four-bar constrained graphs under shared Q limits.

    Attributes
    ----------
    grid :
        Baseline / four-bar lattice (native mode: identical to ``gearbox_grid``).
    gearbox_grid, fourbar_grid :
        Per-mechanism U lattices (may differ under equal-node mode).
    limits :
        Shared output joint limits (ADR-004).
    output_space :
        Shared output chart (ADR-011); matches ``limits`` for Version 1.
    gearbox, fourbar :
        Filtered graphs for each mechanism.
    gearbox_mechanism, fourbar_mechanism :
        Deserialized mechanism instances.
    match_meta :
        Optional equal-node matching metadata for trial records.
    """

    grid: PeriodicGrid2D
    limits: OutputJointLimits
    gearbox: ConstrainedInputGraph
    fourbar: ConstrainedInputGraph
    gearbox_mechanism: Mechanism
    fourbar_mechanism: Mechanism
    gearbox_grid: PeriodicGrid2D | None = None
    fourbar_grid: PeriodicGrid2D | None = None
    match_meta: dict | None = None
    output_space: OutputSpace | None = None

    def __post_init__(self) -> None:
        if self.gearbox_grid is None:
            object.__setattr__(self, "gearbox_grid", self.grid)
        if self.fourbar_grid is None:
            object.__setattr__(self, "fourbar_grid", self.grid)
        if self.output_space is None:
            object.__setattr__(self, "output_space", self.gearbox.output_space)


def build_paired_graphs_from_parts(
    *,
    grid: PeriodicGrid2D,
    limits: OutputJointLimits,
    gearbox_mechanism: Mechanism,
    fourbar_mechanism: Mechanism,
    edge_samples: int,
    gearbox_grid: PeriodicGrid2D | None = None,
    match_meta: dict | None = None,
) -> PairedGraphs:
    """Build paired constrained graphs from already-materialized parts.

    When ``gearbox_grid`` is omitted, both mechanisms share ``grid`` (native
    mode). Equal-node mode passes a refined gearbox lattice separately.
    """
    gb_grid = grid if gearbox_grid is None else gearbox_grid
    space = OutputSpace.from_limits(limits)
    gearbox = ConstrainedInputGraph(
        gb_grid,
        gearbox_mechanism,
        limits,
        edge_samples=edge_samples,
        output_space=space,
    )
    fourbar = ConstrainedInputGraph(
        grid,
        fourbar_mechanism,
        limits,
        edge_samples=edge_samples,
        output_space=space,
    )
    return PairedGraphs(
        grid=grid,
        limits=limits,
        gearbox=gearbox,
        fourbar=fourbar,
        gearbox_mechanism=gearbox_mechanism,
        fourbar_mechanism=fourbar_mechanism,
        gearbox_grid=gb_grid,
        fourbar_grid=grid,
        match_meta=match_meta,
        output_space=space,
    )


def build_paired_graphs(config: ExperimentConfig) -> PairedGraphs:
    """Build shared grid and paired constrained graphs from ``config``.

    Fixed four-bar mode uses absolute ``config.limits``. Population mode is
    not supported here; the pilot builds per-trial graphs instead.

    Parameters
    ----------
    config :
        Validated experiment configuration with ``fourbar.mode == 'fixed'``.

    Returns
    -------
    PairedGraphs
        Materialized lattice and both mechanism graphs.

    Raises
    ------
    TypeError
        If ``config`` is not an ``ExperimentConfig``.
    ValueError
        If four-bar mode is ``population`` or limits are missing.
    """
    if not isinstance(config, ExperimentConfig):
        raise TypeError("config must be an ExperimentConfig")
    if config.mechanisms.fourbar_mode != "fixed":
        raise ValueError(
            "build_paired_graphs requires mechanisms.fourbar.mode == 'fixed'; "
            "population mode builds graphs per trial in run_pilot"
        )
    if config.limits is None:
        raise ValueError("limits are required for fixed four-bar mode")

    graph_cfg = config.graph
    ranges = None if graph_cfg.ranges is None else graph_cfg.ranges
    grid = PeriodicGrid2D(
        graph_cfg.shape,
        ranges=ranges,
        wrap=graph_cfg.wrap,
    )
    limits = config.limits.to_limits()
    gearbox_mech = config.mechanisms.build_gearbox()
    fourbar_mech = config.mechanisms.build_fourbar()
    return build_paired_graphs_from_parts(
        grid=grid,
        limits=limits,
        gearbox_mechanism=gearbox_mech,
        fourbar_mechanism=fourbar_mech,
        edge_samples=graph_cfg.edge_samples,
    )
