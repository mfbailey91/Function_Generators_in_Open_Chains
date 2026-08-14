"""Input-side graph construction and validation."""

from inequality_mechanisms.graphs.adapters import ConstrainedInputSearchAdapter
from inequality_mechanisms.graphs.costs import (
    KNOWN_COST_TYPES,
    build_edge_cost,
    graph_output_euclidean_cost,
    input_euclidean_cost,
    output_euclidean_cost,
    output_euclidean_edge_cost,
    uniform_edge_cost,
    wrapped_input_displacement,
)
from inequality_mechanisms.graphs.embedded import (
    EmbeddedPlanningGraph,
    UniformOutputLattice,
)
from inequality_mechanisms.graphs.goal_set_query_overlay import (
    GoalAttachmentFailure,
    GoalSetQueryOverlay,
    IncompleteGoalSetAttachmentError,
    QueryAttachment,
)
from inequality_mechanisms.graphs.grid import GridNode, PeriodicGrid2D
from inequality_mechanisms.graphs.output_grid import MonotonicOutputGraph
from inequality_mechanisms.graphs.pair_invariants import (
    SharedQPairInvariantError,
    SharedQPairInvariantReport,
    assert_identical_query_overlays,
    assert_shared_q_pair_invariants,
)
from inequality_mechanisms.graphs.query_overlay import (
    QueryNode,
    QueryOverlayGraph,
    ResolvedQueryEndpoint,
    resolve_query_endpoint,
)
from inequality_mechanisms.graphs.sampled_q_query_overlay import (
    SampledQQueryAttachment,
    SampledQQueryOverlay,
    assert_identical_sampled_q_query_overlays,
)
from inequality_mechanisms.graphs.sampled_q_roadmap import (
    FrozenQSampleBank,
    SampledQRoadmapGraph,
    assert_identical_sampled_q_graphs,
    embed_paired_sampled_q_roadmaps,
    embed_sampled_q_roadmap,
    freeze_reusable_q_sample_bank,
)
from inequality_mechanisms.graphs.sampling import (
    AxisSpacingStatistics,
    SamplingDomain,
    SamplingSpecification,
    TransitionParameterization,
    compute_axis_spacing_statistics,
)
from inequality_mechanisms.graphs.topology import (
    GraphTopology,
    LatticeConnectivity,
    TensorGridTopology,
)
from inequality_mechanisms.graphs.transitions import EdgeTraceV2, build_edge_trace_v2
from inequality_mechanisms.graphs.validation import (
    ConstrainedInputGraph,
    configuration_is_valid,
    edge_is_valid,
    interpolate_input_segment,
)

__all__ = [
    "AxisSpacingStatistics",
    "ConstrainedInputGraph",
    "ConstrainedInputSearchAdapter",
    "EdgeTraceV2",
    "EmbeddedPlanningGraph",
    "FrozenQSampleBank",
    "GoalAttachmentFailure",
    "GoalSetQueryOverlay",
    "GraphTopology",
    "GridNode",
    "IncompleteGoalSetAttachmentError",
    "KNOWN_COST_TYPES",
    "LatticeConnectivity",
    "MonotonicOutputGraph",
    "PeriodicGrid2D",
    "QueryAttachment",
    "QueryNode",
    "QueryOverlayGraph",
    "ResolvedQueryEndpoint",
    "SampledQQueryAttachment",
    "SampledQQueryOverlay",
    "SampledQRoadmapGraph",
    "SamplingDomain",
    "SamplingSpecification",
    "SharedQPairInvariantError",
    "SharedQPairInvariantReport",
    "TensorGridTopology",
    "TransitionParameterization",
    "UniformOutputLattice",
    "assert_identical_query_overlays",
    "assert_identical_sampled_q_graphs",
    "assert_identical_sampled_q_query_overlays",
    "assert_shared_q_pair_invariants",
    "embed_paired_sampled_q_roadmaps",
    "embed_sampled_q_roadmap",
    "freeze_reusable_q_sample_bank",
    "build_edge_cost",
    "build_edge_trace_v2",
    "compute_axis_spacing_statistics",
    "configuration_is_valid",
    "edge_is_valid",
    "graph_output_euclidean_cost",
    "input_euclidean_cost",
    "interpolate_input_segment",
    "output_euclidean_cost",
    "output_euclidean_edge_cost",
    "resolve_query_endpoint",
    "uniform_edge_cost",
    "wrapped_input_displacement",
]
