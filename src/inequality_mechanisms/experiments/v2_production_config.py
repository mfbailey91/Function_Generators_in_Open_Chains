"""Single-solver Version 2 production Monte Carlo configuration (V2-902).

Production configs are distinct from diagnostic :class:`V2ExperimentConfig`
and shared-Q study configs. They require a scalar ``search.algorithm`` and
reject solver lists. V2.10 science configs accept only ``dijkstra``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from inequality_mechanisms.experiments.v2_config import (
    V2BranchConfig,
    V2EdgeValidationConfig,
    V2SamplingConfig,
)

ProductionStageName = Literal[
    "smoke",
    "hardware_calibration",
    "resolution_calibration",
    "task_count_calibration",
    "variance_pilot",
    "production",
    "high_resolution_confirmation",
    "build_sample_bank",
    "merge_only",
]
MatchingRuleName = Literal["span"]
CostName = Literal["actuator_travel"]


class V2ProductionConfigError(ValueError):
    """Raised when a production config mapping fails validation."""


class V2ProductionSearchConfig(BaseModel):
    """Exactly one graph solver for the campaign."""

    model_config = ConfigDict(extra="forbid")

    algorithm: Literal["dijkstra"]


class V2ProductionExecutionConfig(BaseModel):
    """Machine-safety and resume policy."""

    model_config = ConfigDict(extra="forbid")

    workers: int = Field(default=1, ge=1, le=16)
    tasks_parallel_within_mechanism: bool = False
    numerical_threads_per_worker: int = Field(default=1, ge=1, le=8)
    checkpoint_unit: Literal["mechanism_pair"] = "mechanism_pair"
    atomic_shards: bool = True
    resume: bool = True
    max_estimated_memory_fraction: float = Field(default=0.65, gt=0.0, lt=1.0)
    require_override_above_limit: bool = True
    memory_override: bool = False
    progress_interval_s: float = Field(default=30.0, ge=1.0)
    parent_rss_bytes: int = Field(default=256 * 1024 * 1024, ge=1)
    memory_margin_bytes: int = Field(default=512 * 1024 * 1024, ge=0)
    worker_peak_rss_bytes: int | None = Field(default=None, ge=1)
    pair_build_retries: int = Field(default=1, ge=0, le=3)

    @field_validator("tasks_parallel_within_mechanism")
    @classmethod
    def _serial_tasks(cls, value: bool) -> bool:
        if value:
            raise ValueError(
                "execution.tasks_parallel_within_mechanism must be false in V2.10"
            )
        return value

    @field_validator("atomic_shards")
    @classmethod
    def _atomic_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("execution.atomic_shards must be true")
        return value


class V2ProductionPopulationConfig(BaseModel):
    """Staged mechanism/task cardinality targets."""

    model_config = ConfigDict(extra="forbid")

    smoke_mechanisms: int = Field(default=2, ge=1)
    calibration_mechanisms: int = Field(default=8, ge=1)
    variance_pilot_mechanisms: int = Field(default=50, ge=1)
    minimum_production_mechanisms: int = Field(default=100, ge=1)
    maximum_production_mechanisms: int = Field(default=500, ge=1)
    production_batch_size: int = Field(default=25, ge=1)
    candidate_tasks_per_mechanism: list[int] = Field(
        default_factory=lambda: [8, 12, 16]
    )
    tasks_per_mechanism: int | None = Field(default=None, ge=1)
    candidate_pool_multiplier: int = Field(default=4, ge=1)
    confirmation_fraction: float = Field(default=0.15, gt=0.0, le=1.0)
    candidate_resolutions: list[int] = Field(
        default_factory=lambda: [32, 48, 64, 96, 128]
    )
    production_shape_n: int | None = Field(default=None, ge=2)

    @field_validator("candidate_tasks_per_mechanism")
    @classmethod
    def _task_candidates(cls, value: list[int]) -> list[int]:
        out = [int(v) for v in value]
        if not out:
            raise ValueError("candidate_tasks_per_mechanism must be non-empty")
        if any(v < 1 for v in out):
            raise ValueError("candidate_tasks_per_mechanism entries must be >= 1")
        return out

    @field_validator("candidate_resolutions")
    @classmethod
    def _resolutions(cls, value: list[int]) -> list[int]:
        out = [int(v) for v in value]
        if not out:
            raise ValueError("candidate_resolutions must be non-empty")
        if any(v < 2 for v in out):
            raise ValueError("candidate_resolutions entries must be >= 2")
        return out

    @model_validator(mode="after")
    def _cardinality_order(self) -> V2ProductionPopulationConfig:
        if self.minimum_production_mechanisms > self.maximum_production_mechanisms:
            raise ValueError(
                "minimum_production_mechanisms must be <= maximum_production_mechanisms"
            )
        if (
            self.tasks_per_mechanism is not None
            and self.tasks_per_mechanism not in self.candidate_tasks_per_mechanism
            and self.tasks_per_mechanism not in {2, 4}
        ):
            # Smoke / calibration may use smaller K than the production candidates.
            pass
        return self


class V2ProductionStoppingConfig(BaseModel):
    """Transparent sequential-precision stopping rule."""

    model_config = ConfigDict(extra="forbid")

    minimum_mechanisms: int = Field(default=100, ge=1)
    batch_size: int = Field(default=25, ge=1)
    maximum_mechanisms: int = Field(default=500, ge=1)
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    target_ci_half_width_log_ratio: float = Field(default=0.05, gt=0.0)
    stable_batches_required: int = Field(default=3, ge=1)
    max_relative_estimate_change: float = Field(default=0.05, gt=0.0)
    hierarchical_bootstrap_samples: int = Field(default=200, ge=10)
    hierarchical_bootstrap_seed: int = 0


class V2ProductionVisualizationConfig(BaseModel):
    """Post-search visualization bounds."""

    model_config = ConfigDict(extra="forbid")

    production_path_samples: int = Field(default=5, ge=0)
    render_during_search: bool = False
    generate_canvas_after_run: bool = True

    @field_validator("render_during_search")
    @classmethod
    def _no_inline_render(cls, value: bool) -> bool:
        if value:
            raise ValueError(
                "visualization.render_during_search must be false "
                "during production search"
            )
        return value


class V2ProductionStudyMeta(BaseModel):
    """Study identity and sample-bank pointer."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["production_monte_carlo_dijkstra"] = "production_monte_carlo_dijkstra"
    stage: ProductionStageName = "smoke"
    sample_bank: str | None = None
    calibration_decisions: str | None = None
    objective_cost: CostName = "actuator_travel"


class V2ProductionConfig(BaseModel):
    """Top-level production Monte Carlo configuration."""

    model_config = ConfigDict(extra="forbid")

    architecture_version: Literal[2]
    result_schema_version: Literal[2] = 2
    production_schema_version: Literal[1] = 1
    planning_space: Literal["output"]
    seed: int
    study: V2ProductionStudyMeta
    search: V2ProductionSearchConfig
    execution: V2ProductionExecutionConfig = Field(
        default_factory=V2ProductionExecutionConfig
    )
    population: V2ProductionPopulationConfig = Field(
        default_factory=V2ProductionPopulationConfig
    )
    stopping: V2ProductionStoppingConfig = Field(
        default_factory=V2ProductionStoppingConfig
    )
    visualization: V2ProductionVisualizationConfig = Field(
        default_factory=V2ProductionVisualizationConfig
    )
    branch: V2BranchConfig
    sampling: V2SamplingConfig
    edge_validation: V2EdgeValidationConfig = Field(
        default_factory=V2EdgeValidationConfig
    )
    matching_rule: MatchingRuleName = "span"
    tasks_output_tolerance: float = Field(default=100.0, ge=0.0)

    @model_validator(mode="after")
    def _output_sampling(self) -> V2ProductionConfig:
        if self.sampling.domain != "output":
            raise ValueError("production Monte Carlo requires sampling.domain: output")
        if len(self.sampling.shape) != 2:
            raise ValueError(
                "production Monte Carlo currently requires 2R sampling.shape"
            )
        return self


def _reject_solver_lists(raw: dict[str, Any]) -> None:
    search = raw.get("search")
    if not isinstance(search, dict):
        return
    if "algorithms" in search:
        raise V2ProductionConfigError(
            "search.algorithms lists are forbidden; "
            "use scalar search.algorithm: dijkstra"
        )
    algorithm = search.get("algorithm")
    if algorithm is not None and algorithm != "dijkstra":
        raise V2ProductionConfigError(
            "V2.10 production configs require search.algorithm: dijkstra, "
            f"got {algorithm!r}"
        )


def validate_v2_production_config_mapping(raw: dict[str, Any]) -> V2ProductionConfig:
    """Validate a raw mapping as a production Monte Carlo config."""
    if not isinstance(raw, dict):
        raise V2ProductionConfigError(
            f"config root must be a mapping, got {type(raw).__name__}"
        )
    if raw.get("architecture_version") not in {2, "2"}:
        raise V2ProductionConfigError("architecture_version must be 2")
    _reject_solver_lists(raw)
    study = raw.get("study")
    if isinstance(study, dict) and "alphas" in study:
        raise V2ProductionConfigError(
            "production configs must not set study.alphas (actuator_travel only)"
        )
    objective = raw.get("objective")
    if isinstance(objective, dict) and objective.get("alpha") is not None:
        raise V2ProductionConfigError("production configs must not set objective.alpha")
    try:
        return V2ProductionConfig.model_validate(raw)
    except V2ProductionConfigError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise V2ProductionConfigError(str(exc)) from exc


def load_v2_production_config(path: Path | str) -> V2ProductionConfig:
    """Load and validate a production YAML config."""
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return validate_v2_production_config_mapping(raw)


def v2_production_config_to_yaml(config: V2ProductionConfig) -> str:
    """Serialize a validated production config."""
    return str(yaml.safe_dump(config.model_dump(mode="python"), sort_keys=False))


def production_config_digest(config: V2ProductionConfig) -> str:
    """Return a stable hex digest of the scientific config payload."""
    payload = config.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def is_v2_production_mapping(raw: dict[str, Any]) -> bool:
    """Return whether a raw YAML mapping is a production Monte Carlo config."""
    study = raw.get("study")
    if not isinstance(study, dict):
        return False
    return study.get("name") == "production_monte_carlo_dijkstra"


def stage_mechanism_count(config: V2ProductionConfig, stage: str | None = None) -> int:
    """Return the configured mechanism-pair count for a stage."""
    name = stage or config.study.stage
    pop = config.population
    mapping = {
        "smoke": pop.smoke_mechanisms,
        "hardware_calibration": pop.calibration_mechanisms,
        "resolution_calibration": pop.calibration_mechanisms,
        "task_count_calibration": pop.calibration_mechanisms,
        "variance_pilot": pop.variance_pilot_mechanisms,
        "production": pop.maximum_production_mechanisms,
        "high_resolution_confirmation": max(
            1, int(round(pop.minimum_production_mechanisms * pop.confirmation_fraction))
        ),
        "build_sample_bank": pop.maximum_production_mechanisms,
        "merge_only": 0,
    }
    if name not in mapping:
        raise V2ProductionConfigError(f"unknown production stage {name!r}")
    return int(mapping[name])


def stage_task_count(config: V2ProductionConfig, stage: str | None = None) -> int:
    """Return tasks-per-mechanism for a stage."""
    name = stage or config.study.stage
    if config.population.tasks_per_mechanism is not None:
        return int(config.population.tasks_per_mechanism)
    if name == "smoke":
        return 2
    if name == "hardware_calibration":
        return 4
    if name == "task_count_calibration":
        return int(max(config.population.candidate_tasks_per_mechanism))
    return int(config.population.candidate_tasks_per_mechanism[0])


STAGES_REQUIRING_CALIBRATION_DECISIONS = frozenset(
    {"production", "variance_pilot", "high_resolution_confirmation"}
)
STAGES_REQUIRING_CALIBRATED_PEAK_RSS = frozenset(
    {"production", "variance_pilot", "high_resolution_confirmation"}
)


def next_confirmation_shape_n(config: V2ProductionConfig) -> int:
    """Return the next higher candidate resolution above the accepted production n."""
    accepted = int(
        config.population.production_shape_n
        if config.population.production_shape_n is not None
        else config.sampling.shape[0]
    )
    higher = [
        int(n)
        for n in sorted(config.population.candidate_resolutions)
        if int(n) > accepted
    ]
    return higher[0] if higher else accepted


def load_calibration_decisions(path: Path | str) -> dict[str, Any]:
    """Load a calibration decision directory or JSON file."""
    target = Path(path)
    if target.is_dir():
        payload: dict[str, Any] = {}
        for name in ("resolution_decision.json", "task_count_decision.json"):
            candidate = target / name
            if candidate.is_file():
                payload[name.replace(".json", "")] = json.loads(
                    candidate.read_text(encoding="utf-8")
                )
        if not payload:
            raise V2ProductionConfigError(f"no calibration decisions in {target}")
        return payload
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise V2ProductionConfigError(
            f"calibration decisions must be a mapping: {target}"
        )
    return data


def apply_calibration_decisions(
    config: V2ProductionConfig,
    decisions: Mapping[str, Any],
) -> V2ProductionConfig:
    """Return a copy of ``config`` with recorded n and K applied."""
    shape_n = config.population.production_shape_n
    tasks_k = config.population.tasks_per_mechanism
    resolution = decisions.get("resolution_decision") or decisions.get("resolution")
    task_count = decisions.get("task_count_decision") or decisions.get("task_count")
    if (
        isinstance(resolution, Mapping)
        and resolution.get("production_shape_n") is not None
    ):
        shape_n = int(resolution["production_shape_n"])
    if (
        isinstance(task_count, Mapping)
        and task_count.get("tasks_per_mechanism") is not None
    ):
        tasks_k = int(task_count["tasks_per_mechanism"])
    return config.model_copy(
        update={
            "population": config.population.model_copy(
                update={
                    "production_shape_n": shape_n,
                    "tasks_per_mechanism": tasks_k,
                }
            )
        }
    )


def assert_calibration_decisions_present(
    config: V2ProductionConfig,
    stage: str,
    *,
    decisions: Mapping[str, Any] | None = None,
) -> None:
    """Refuse production-scale stages that lack recorded n/K decisions."""
    if stage not in STAGES_REQUIRING_CALIBRATION_DECISIONS:
        return
    has_n = config.population.production_shape_n is not None
    has_k = config.population.tasks_per_mechanism is not None
    has_artifact = bool(
        decisions is not None
        or config.study.calibration_decisions
        or (has_n and has_k and config.study.sample_bank)
    )
    if has_artifact and has_n and has_k:
        return
    raise V2ProductionConfigError(
        f"stage {stage!r} requires recorded calibration decisions "
        "(study.calibration_decisions, --apply-decisions, or a frozen sample bank "
        "with production_shape_n and tasks_per_mechanism)"
    )
