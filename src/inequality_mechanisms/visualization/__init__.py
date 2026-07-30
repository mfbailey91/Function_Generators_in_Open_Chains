"""Plotting and figure helpers for analysis notebooks."""

from inequality_mechanisms.visualization.branches import plot_operating_branch
from inequality_mechanisms.visualization.embedded_graphs import (
    plot_actuator_samples,
    plot_axis_mapping,
    plot_edge_trace,
    plot_embedded_q_path,
    plot_embedded_u_path,
    plot_output_graph,
    plot_sampling_mode_comparison,
    plot_spacing_statistics,
)
from inequality_mechanisms.visualization.expansions import (
    plot_normalized_expansions,
    plot_paired_log_ratios,
    plot_raw_expansions,
)
from inequality_mechanisms.visualization.path_lengths import (
    plot_path_length_q,
    plot_path_length_x,
)
from inequality_mechanisms.visualization.paths import (
    cost_from_start,
    path_inputs,
    path_outputs,
    plot_cartesian_path,
    plot_input_path,
    plot_output_path,
)
from inequality_mechanisms.visualization.v2_expansions import (
    plot_v2_expansions_by_alpha,
    plot_v2_expansions_by_mechanism,
)

__all__ = [
    "cost_from_start",
    "path_inputs",
    "path_outputs",
    "plot_actuator_samples",
    "plot_axis_mapping",
    "plot_cartesian_path",
    "plot_edge_trace",
    "plot_embedded_q_path",
    "plot_embedded_u_path",
    "plot_input_path",
    "plot_normalized_expansions",
    "plot_operating_branch",
    "plot_output_graph",
    "plot_output_path",
    "plot_paired_log_ratios",
    "plot_path_length_q",
    "plot_path_length_x",
    "plot_raw_expansions",
    "plot_sampling_mode_comparison",
    "plot_spacing_statistics",
    "plot_v2_expansions_by_alpha",
    "plot_v2_expansions_by_mechanism",
]
