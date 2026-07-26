"""Sprint 3 diagnostic package (mapping, traces, plots, canvas bundle)."""

from inequality_mechanisms.diagnostics.mapping import (
    AxisMappingDiagnostic,
    OutputMappingDiagnostic,
    inspect_raw_output,
    mapping_curve,
)
from inequality_mechanisms.diagnostics.plots import (
    basin_metrics,
    build_mapping_atlas_curve,
    classify_lattice_edge,
    input_euclidean_cost,
    plot_edge_density_differences,
    plot_edge_microscope,
    plot_mapping_atlas,
    plot_search_basin,
    plot_task_preimages,
    plot_topology_panels,
    uniform_edge_cost,
)
from inequality_mechanisms.graphs.edge_trace import (
    EdgeSamplePoint,
    EdgeTrace,
    build_edge_trace,
    winding_number,
)

__all__ = [
    "AxisMappingDiagnostic",
    "EdgeSamplePoint",
    "EdgeTrace",
    "OutputMappingDiagnostic",
    "basin_metrics",
    "build_edge_trace",
    "build_mapping_atlas_curve",
    "classify_lattice_edge",
    "input_euclidean_cost",
    "inspect_raw_output",
    "mapping_curve",
    "plot_edge_density_differences",
    "plot_edge_microscope",
    "plot_mapping_atlas",
    "plot_search_basin",
    "plot_task_preimages",
    "plot_topology_panels",
    "uniform_edge_cost",
    "winding_number",
]
