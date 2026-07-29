"""Strict Version 2 experiment configuration schema (Sprint V2.4, V2-401).

Version 2 configs must be unambiguous: ``architecture_version: 2`` is
required, ``planning_space`` must be ``output``, branch topology must be
nonperiodic, and cost/heuristic pairs must be drawn from a documented
compatible table (ADR-016). This module never accepts a Version 1 config
and never silently infers Version 2 semantics; :func:`load_v2_experiment_config`
first runs the raw-mapping architecture gate
(:func:`inequality_mechanisms.experiments.architecture.classify_architecture_version`)
so mixed V1/V2 fields are rejected before typed validation even starts.

Uses pydantic (already a Version 1 dependency) for consistency with
``experiments/config.py`` rather than introducing a second validation
style.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from inequality_mechanisms.experiments.architecture import (
    ArchitectureCompatibilityError,
    classify_architecture_version,
)

MechanismComparisonName = Literal["fourbar_vs_equivalent_affine_gearbox"]
BranchSelectionName = Literal["monotonic_interval"]
SamplingDomainName = Literal["input", "output"]
CostName = Literal[
    "uniform",
    "output_euclidean",
    "input_euclidean",
    "actuator_travel",
    "gain_resolution",
]
HeuristicName = Literal["zero", "uniform_step", "output_euclidean", "input_euclidean"]
TaskSourceName = Literal["fixed_output_pairs"]
MatchingRuleName = Literal["span", "total_variation", "rms_gain"]
AlgorithmName = Literal["dijkstra", "astar"]

#: Default compatible A* heuristic for each known Version 2 cost name.
_DEFAULT_HEURISTIC: dict[str, str] = {
    "uniform": "uniform_step",
    "output_euclidean": "output_euclidean",
    "input_euclidean": "input_euclidean",
    "actuator_travel": "input_euclidean",
    "gain_resolution": "zero",
}

#: Allowed heuristic names for each cost name (``zero`` always allowed).
_COMPATIBLE_HEURISTICS: dict[str, frozenset[str]] = {
    "uniform": frozenset({"uniform_step", "zero"}),
    "output_euclidean": frozenset({"output_euclidean", "zero"}),
    "input_euclidean": frozenset({"input_euclidean", "zero"}),
    "actuator_travel": frozenset({"input_euclidean", "zero"}),
    "gain_resolution": frozenset({"zero"}),
}


class V2ConfigError(ValueError):
    """Raised when a Version 2 config mapping fails strict validation."""


class FourBarLinkConfig(BaseModel):
    """Crank-rocker link lengths shared by every axis of the comparison."""

    model_config = ConfigDict(extra="forbid")

    a: float = Field(gt=0.0)
    b: float = Field(gt=0.0)
    c: float = Field(gt=0.0)
    d: float = Field(gt=0.0)
    branch: Literal[1, -1] = 1


def _default_fourbar() -> FourBarLinkConfig:
    return FourBarLinkConfig(a=1.0, b=2.5, c=2.0, d=2.0, branch=1)


def _default_algorithms() -> list[AlgorithmName]:
    return ["dijkstra", "astar"]


class V2MechanismsConfig(BaseModel):
    """Mechanism-pair comparison selection.

    Version 2.4 supports exactly one comparison: a certified monotonic
    four-bar operating branch against its endpoint-matched equivalent
    affine gearbox branch (the null-control pair per
    ``docs/software/PROJECT_PLAN.md``).
    """

    model_config = ConfigDict(extra="forbid")

    comparison: MechanismComparisonName
    dim: int = Field(default=2, ge=1)
    fourbar: FourBarLinkConfig = Field(default_factory=_default_fourbar)
    matching_rule: MatchingRuleName = "span"


class V2BranchConfig(BaseModel):
    """Branch selection and certification parameters (ADR-014)."""

    model_config = ConfigDict(extra="forbid")

    selection: BranchSelectionName
    certification_samples_per_axis: int = Field(default=17, ge=3)
    minimum_abs_gain: float = Field(gt=0.0)
    inverse_tolerance: float = Field(gt=0.0)
    endpoint_margin_fraction: float = Field(default=0.02, ge=0.0, lt=0.5)
    max_abs_gain: float | None = Field(default=None, gt=0.0)
    n_samples: int = Field(default=361, ge=16)
    min_u_width: float = Field(default=0.3, gt=0.0)
    table_samples_per_axis: int = Field(default=65, ge=4)


class V2SamplingConfig(BaseModel):
    """Uniform-``U`` or uniform-``Q`` sampling of the branch (ADR-015)."""

    model_config = ConfigDict(extra="forbid")

    domain: SamplingDomainName
    shape: list[int]
    include_endpoints: bool = True

    @field_validator("shape")
    @classmethod
    def _shape_ok(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("sampling.shape must be non-empty")
        out = [int(n) for n in value]
        if any(n < 2 for n in out):
            raise ValueError(f"sampling.shape entries must be >= 2, got {out}")
        return out

    @field_validator("include_endpoints")
    @classmethod
    def _endpoints_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError(
                "Version 2 samplers always sample closed-interval endpoints "
                "(EmbeddedPlanningGraph uses linspace(..., endpoint=True)); "
                "include_endpoints: false is not supported"
            )
        return value


class V2ObjectiveConfig(BaseModel):
    """Edge cost and compatible A* heuristic selection (V2-404)."""

    model_config = ConfigDict(extra="forbid")

    cost: CostName
    heuristic: HeuristicName | None = None

    @model_validator(mode="after")
    def _heuristic_compatible(self) -> V2ObjectiveConfig:
        allowed = _COMPATIBLE_HEURISTICS[self.cost]
        requested = self.heuristic
        if requested is not None and requested not in allowed:
            raise ValueError(
                f"heuristic {requested!r} is incompatible with cost "
                f"{self.cost!r}; allowed: {sorted(allowed)}"
            )
        return self

    def resolved_heuristic(self) -> str:
        """Return the explicit heuristic, or the documented default for ``cost``."""
        if self.heuristic is not None:
            return str(self.heuristic)
        return _DEFAULT_HEURISTIC[self.cost]


class V2EdgeValidationConfig(BaseModel):
    """Edge trace sampling density for diagnostics (unrelated to search cost)."""

    model_config = ConfigDict(extra="forbid")

    samples: int = Field(default=17, ge=2)


class V2OutputPair(BaseModel):
    """One explicit requested output start/goal pair."""

    model_config = ConfigDict(extra="forbid")

    start_q: list[float]
    goal_q: list[float]

    @model_validator(mode="after")
    def _dims_match(self) -> V2OutputPair:
        if len(self.start_q) != len(self.goal_q):
            raise ValueError("start_q and goal_q must have the same length")
        if len(self.start_q) < 1:
            raise ValueError("start_q/goal_q must be non-empty")
        return self


class V2TasksConfig(BaseModel):
    """Requested output-space task specification (V2-402).

    There is no preimage-selection policy in Version 2 (ADR-014): a
    ``preimage_policy`` field here is rejected by ``extra='forbid'``, and no
    equivalent field is defined by this model. When ``pairs`` is omitted,
    the runner deterministically draws ``trials`` uniform random output
    pairs from the reference branch's certified output box using the
    top-level ``seed`` (no resampling after a rejected match, per V2-403).
    """

    model_config = ConfigDict(extra="forbid")

    source: TaskSourceName
    output_tolerance: float = Field(ge=0.0)
    use_query_overlays: bool = Field(
        default=False,
        description=(
            "If true, resolve exact query endpoints using QueryOverlayGraph "
            "(no snapping)."
        ),
    )
    pairs: list[V2OutputPair] | None = None


class V2ExperimentConfig(BaseModel):
    """Top-level, strict Version 2 experiment configuration (ADR-016).

    Parameters
    ----------
    architecture_version :
        Must be exactly ``2``; Version 1 configs never set this field.
    result_schema_version :
        Must be exactly ``2`` (a distinct series from Version 1 sprint
        schemas, per ADR-016).
    planning_space :
        Must be ``"output"`` for Version 2 (ADR-014).
    """

    model_config = ConfigDict(extra="forbid")

    architecture_version: Literal[2]
    result_schema_version: Literal[2] = 2
    planning_space: Literal["output"]
    mechanisms: V2MechanismsConfig
    branch: V2BranchConfig
    sampling: V2SamplingConfig
    objective: V2ObjectiveConfig
    edge_validation: V2EdgeValidationConfig = Field(
        default_factory=V2EdgeValidationConfig
    )
    tasks: V2TasksConfig
    algorithms: list[AlgorithmName] = Field(default_factory=_default_algorithms)
    seed: int
    trials: int = Field(ge=1)

    @field_validator("algorithms")
    @classmethod
    def _algorithms_nonempty_unique(
        cls, value: list[AlgorithmName]
    ) -> list[AlgorithmName]:
        if not value:
            raise ValueError("algorithms must be non-empty")
        if len(set(value)) != len(value):
            raise ValueError("algorithms must not contain duplicates")
        return list(value)

    @model_validator(mode="after")
    def _sampling_shape_matches_dim(self) -> V2ExperimentConfig:
        if len(self.sampling.shape) != self.mechanisms.dim:
            raise ValueError(
                "sampling.shape length "
                f"({len(self.sampling.shape)}) must match mechanisms.dim "
                f"({self.mechanisms.dim})"
            )
        return self


def _reject_v1_only_fields(raw: dict[str, Any]) -> None:
    """Reject Version 1-only fields that ``extra='forbid'`` cannot see.

    ``tasks.preimage_policy`` is rejected structurally (``V2TasksConfig``
    has no such field and forbids extras), but we also check here so the
    error message names the Version 1 concept explicitly rather than a
    generic "extra fields not permitted".
    """
    tasks = raw.get("tasks")
    if isinstance(tasks, dict) and "preimage_policy" in tasks:
        raise V2ConfigError(
            "tasks.preimage_policy is Version 1-only; Version 2 has no "
            "preimage-selection policy (ADR-014) -- omit it"
        )
    graph = raw.get("graph")
    if isinstance(graph, dict) and "wrap" in graph:
        wraps = graph["wrap"]
        seq = list(wraps) if isinstance(wraps, (list, tuple)) else [wraps]
        if any(bool(w) for w in seq):
            raise V2ConfigError(
                "Version 2 branch topology must be nonperiodic (wrap all "
                "false); found a wrapped graph.wrap entry"
            )
    branch = raw.get("branch")
    if isinstance(branch, dict) and branch.get("selection") == "full_cycle":
        raise V2ConfigError(
            "branch.selection: full_cycle is Version 1-only full-cycle "
            "topology; Version 2 requires a nonperiodic monotonic_interval "
            "branch (ADR-014)"
        )


def validate_v2_config_mapping(raw: dict[str, Any]) -> V2ExperimentConfig:
    """Validate a raw mapping (already loaded from YAML/JSON) as Version 2.

    Runs the shared ADR-016 architecture gate first so mixed Version
    1/Version 2 fields are rejected with a consistent message before typed
    field validation, then applies the strict Version 2 pydantic schema.

    Raises
    ------
    V2ConfigError
        If the raw mapping is not a mapping, mixes Version 1/2 semantics,
        or is not classified as Version 2.
    pydantic.ValidationError
        If typed fields fail schema validation (missing/invalid fields,
        bad cost/heuristic combination, dimension mismatch, etc.).
    """
    if not isinstance(raw, dict):
        raise V2ConfigError(f"config root must be a mapping, got {type(raw).__name__}")
    try:
        version = classify_architecture_version(raw)
    except ArchitectureCompatibilityError as exc:
        raw_arch = raw.get("architecture_version", None)
        # The test suite expects a stable error message whenever the raw
        # config is not a Version-2 config because of `architecture_version`,
        # even when the mixed-field gate trips earlier in
        # `classify_architecture_version`.
        if raw_arch != 2 and raw_arch != "2":
            raise V2ConfigError(
                "not a Version 2 config (missing or non-2 architecture_version); "
                "use the Version 1 loader for architecture_version: 1 configs"
            ) from exc
        raise V2ConfigError(str(exc)) from exc
    if version != 2:
        raise V2ConfigError(
            "not a Version 2 config (missing or non-2 architecture_version); "
            "use the Version 1 loader for architecture_version: 1 configs"
        )
    _reject_v1_only_fields(raw)
    return V2ExperimentConfig.model_validate(raw)


def load_v2_experiment_config(path: Path | str) -> V2ExperimentConfig:
    """Load and strictly validate a Version 2 experiment config from YAML.

    Parameters
    ----------
    path :
        Path to a YAML document.

    Returns
    -------
    V2ExperimentConfig

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    V2ConfigError
        If the raw mapping is not Version 2 or mixes Version 1/2 semantics.
    pydantic.ValidationError
        If typed fields fail schema validation.
    """
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return validate_v2_config_mapping(raw)


def v2_experiment_config_to_yaml(config: V2ExperimentConfig) -> str:
    """Serialize a validated Version 2 config to a YAML string."""
    payload = config.model_dump(mode="python")
    return str(yaml.safe_dump(payload, sort_keys=False))
