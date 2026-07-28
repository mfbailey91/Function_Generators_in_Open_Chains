"""Configuration-driven experiment runners and registries."""

from inequality_mechanisms.experiments.config import (
    AlgorithmsConfig,
    CostConfig,
    ExperimentConfig,
    FourBarFixedSource,
    FourBarPopulationSource,
    GraphConfig,
    LimitsConfig,
    MechanismPairConfig,
    PathQualityConfig,
    Sprint4Config,
    Sprint6Config,
    TrialsConfig,
    experiment_config_to_yaml,
    load_experiment_config,
)
from inequality_mechanisms.experiments.equal_nodes import (
    gearbox_grid_over_limits,
    match_gearbox_to_fourbar_valid_count,
)
from inequality_mechanisms.experiments.canvas import (
    collect_canvas_payload,
    render_monte_carlo_canvas_html,
    resolve_run_for_canvas,
    write_monte_carlo_canvas,
)
from inequality_mechanisms.experiments.pilot import run_pilot
from inequality_mechanisms.experiments.schema import (
    RESULT_SCHEMA_VERSION,
    SPRINT5_RESULT_SCHEMA_VERSION,
    SPRINT6_RESULT_SCHEMA_VERSION,
)
from inequality_mechanisms.experiments.sprint4 import run_sprint4
from inequality_mechanisms.experiments.sprint4_qgrid import run_sprint4_qgrid
from inequality_mechanisms.experiments.sprint5 import run_sprint5
from inequality_mechanisms.experiments.sprint5_canvas import (
    collect_sprint5_canvas_payload,
    render_sprint5_canvas_html,
    write_sprint5_canvas,
)
from inequality_mechanisms.experiments.sprint6 import run_sprint6
from inequality_mechanisms.experiments.sprint6_canvas import (
    collect_sprint6_canvas_payload,
    render_sprint6_canvas_html,
    write_sprint6_canvas,
)
from inequality_mechanisms.experiments.registry import (
    ExperimentRun,
    RunRegistryError,
    capture_environment,
    capture_revision,
    create_run,
    default_results_root,
    dump_manifest,
    generate_run_id,
    list_runs,
    load_run,
    validate_run_id,
)
from inequality_mechanisms.experiments.setup import (
    PairedGraphs,
    build_paired_graphs,
    build_paired_graphs_from_parts,
)
from inequality_mechanisms.experiments.tasks import (
    EndpointResidual,
    PairedTask,
    SelectedPreimages,
    default_snap_tol,
    discrete_preimage_candidates,
    generate_paired_tasks,
    nearest_grid_indices,
    select_preimage,
)

__all__ = [
    "AlgorithmsConfig",
    "CostConfig",
    "EndpointResidual",
    "ExperimentConfig",
    "ExperimentRun",
    "FourBarFixedSource",
    "FourBarPopulationSource",
    "GraphConfig",
    "LimitsConfig",
    "MechanismPairConfig",
    "PairedGraphs",
    "PairedTask",
    "PathQualityConfig",
    "RESULT_SCHEMA_VERSION",
    "SPRINT5_RESULT_SCHEMA_VERSION",
    "SPRINT6_RESULT_SCHEMA_VERSION",
    "RunRegistryError",
    "SelectedPreimages",
    "Sprint4Config",
    "Sprint6Config",
    "TrialsConfig",
    "build_paired_graphs",
    "build_paired_graphs_from_parts",
    "capture_environment",
    "capture_revision",
    "collect_canvas_payload",
    "create_run",
    "default_results_root",
    "default_snap_tol",
    "discrete_preimage_candidates",
    "dump_manifest",
    "experiment_config_to_yaml",
    "gearbox_grid_over_limits",
    "generate_paired_tasks",
    "generate_run_id",
    "list_runs",
    "load_experiment_config",
    "load_run",
    "match_gearbox_to_fourbar_valid_count",
    "nearest_grid_indices",
    "render_monte_carlo_canvas_html",
    "resolve_run_for_canvas",
    "run_pilot",
    "run_sprint4",
    "run_sprint4_qgrid",
    "run_sprint5",
    "run_sprint6",
    "collect_sprint5_canvas_payload",
    "render_sprint5_canvas_html",
    "write_sprint5_canvas",
    "collect_sprint6_canvas_payload",
    "render_sprint6_canvas_html",
    "write_sprint6_canvas",
    "select_preimage",
    "validate_run_id",
    "write_monte_carlo_canvas",
]
