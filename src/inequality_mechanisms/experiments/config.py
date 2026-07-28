"""Pydantic experiment configuration schema (IM-014).

Validated configs drive Version 1 Monte Carlo trials. Mechanism parameter
dicts reuse the ``Mechanism.to_dict`` / ``from_dict`` registry (ADR-002);
population four-bar trials sample lengths per ADR-009.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.mechanisms.population import CrankRockerPopulationSpec
from inequality_mechanisms.spaces.limits import OutputJointLimits

AlgorithmName = Literal["dijkstra", "astar"]
CostType = Literal["uniform", "input_euclidean", "output_euclidean"]
PreimagePolicy = Literal["lex_min_node_id", "random"]
FourBarMode = Literal["fixed", "population"]


def _ensure_mechanism_registry() -> None:
    """Import concrete mechanisms so the ADR-002 registry is populated."""
    import inequality_mechanisms.mechanisms  # noqa: F401


def _default_algorithm_names() -> list[AlgorithmName]:
    return ["dijkstra", "astar"]


class GraphConfig(BaseModel):
    """Periodic 2-D input lattice parameters."""

    model_config = ConfigDict(extra="forbid")

    shape: tuple[int, int]
    ranges: tuple[tuple[float, float], tuple[float, float]] | None = None
    wrap: tuple[bool, bool] = (True, True)
    edge_samples: int = Field(default=17, ge=2)
    match_valid_nodes: bool = Field(
        default=False,
        description=(
            "If true (IM-018), keep the four-bar on this baseline lattice and "
            "refine a gearbox lattice over the shared Q box until N_valid "
            "approximately matches (ADR-010)."
        ),
    )
    match_relative_tol: float = Field(
        default=0.1,
        gt=0.0,
        description="Allowed |N_gear - N_fourbar| / N_fourbar for equal-node mode.",
    )
    match_shape_hi: int = Field(
        default=128,
        ge=2,
        description="Upper bound on square gearbox shape during equal-node search.",
    )

    @field_validator("shape")
    @classmethod
    def _shape_ge_two(cls, value: tuple[int, int]) -> tuple[int, int]:
        if len(value) != 2 or int(value[0]) < 2 or int(value[1]) < 2:
            raise ValueError(f"shape entries must be >= 2, got {value}")
        return (int(value[0]), int(value[1]))


class LimitsConfig(BaseModel):
    """Shared output joint-limit box in Q (fixed four-bar mode only)."""

    model_config = ConfigDict(extra="forbid")

    lower: list[float]
    upper: list[float]

    @model_validator(mode="after")
    def _bounds_consistent(self) -> LimitsConfig:
        if len(self.lower) != len(self.upper):
            raise ValueError("lower and upper must have the same length")
        if len(self.lower) < 1:
            raise ValueError("limits must be non-empty")
        for lo, hi in zip(self.lower, self.upper, strict=True):
            if not (hi > lo):
                raise ValueError("each upper bound must be strictly greater than lower")
        return self

    def to_limits(self) -> OutputJointLimits:
        """Materialize ``OutputJointLimits``."""
        return OutputJointLimits.box(lower=self.lower, upper=self.upper)


def _default_cost_types() -> list[CostType]:
    return ["uniform", "input_euclidean", "output_euclidean"]


class CostConfig(BaseModel):
    """Edge-cost selection for search.

    Pilot uses ``type`` (single cost). Sprint Four factorial runs use
    ``types`` when provided; otherwise :meth:`resolved_types` returns
    ``[type]``.
    """

    model_config = ConfigDict(extra="forbid")

    type: CostType = "output_euclidean"
    types: list[CostType] | None = None

    @field_validator("types")
    @classmethod
    def _types_unique_nonempty(
        cls, value: list[CostType] | None
    ) -> list[CostType] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("cost.types must be non-empty when provided")
        if len(set(value)) != len(value):
            raise ValueError("cost.types must not contain duplicates")
        return list(value)

    def resolved_types(self) -> list[CostType]:
        """Return the cost names to run (factorial list or singleton)."""
        if self.types is not None:
            return list(self.types)
        return [self.type]


class Sprint4Config(BaseModel):
    """Sprint Four P1 study options (factorial, landscape, bootstrap)."""

    model_config = ConfigDict(extra="forbid")

    n_landscape_trials: int = Field(default=1, ge=0)
    landscape_costs: list[CostType] = Field(
        default_factory=lambda: ["output_euclidean"]
    )
    bootstrap_n_samples: int = Field(default=1000, ge=10)
    bootstrap_seed: int = 0
    bootstrap_confidence: float = Field(default=0.95, gt=0.0, lt=1.0)
    gain_epsilon: float = Field(default=0.05, gt=0.0)
    high_gain_threshold: float = Field(default=2.0, gt=0.0)
    near_reversal_epsilon: float = Field(default=0.02, gt=0.0)

    @field_validator("landscape_costs")
    @classmethod
    def _landscape_costs_unique(cls, value: list[CostType]) -> list[CostType]:
        if len(set(value)) != len(value):
            raise ValueError("sprint4.landscape_costs must not contain duplicates")
        return list(value)


class PathQualityConfig(BaseModel):
    """Sprint Five path-quality metric options (S5-05)."""

    model_config = ConfigDict(extra="forbid")

    revisit_exclusion_steps: int = Field(default=4, ge=0)
    revisit_threshold_q: float = Field(default=0.05, gt=0.0)
    revisit_threshold_x: float = Field(default=0.05, gt=0.0)
    n_representative_cards: int = Field(
        default=5,
        ge=0,
        description="Number of path-quality diagnostic cards to write.",
    )


MatchingRuleName = Literal["span", "total_variation", "rms_gain"]


class Sprint6Config(BaseModel):
    """Sprint Six equivalence / resolution / Monte Carlo options."""

    model_config = ConfigDict(extra="forbid")

    matching_n_samples: int = Field(default=361, ge=16)
    verify_equivalence: bool = True
    resolution_shapes: list[int] = Field(
        default_factory=lambda: [32, 48, 64, 96, 128]
    )
    max_relative_effect_change: float = Field(default=0.05, gt=0.0)
    require_sign_stability: bool = True
    require_component_stability: bool = True
    require_task_feasibility_stability: bool = True
    n_mechanisms: int = Field(default=4, ge=1)
    tasks_per_mechanism: int = Field(default=2, ge=1)
    min_accepted_tasks_per_mechanism: int = Field(default=1, ge=1)
    mechanism_batch_size: int = Field(default=2, ge=1)
    initial_mechanisms: int = Field(default=4, ge=1)
    target_ci_half_width: float = Field(default=0.10, gt=0.0)
    min_mechanisms: int = Field(default=4, ge=1)
    max_mechanisms: int = Field(default=200, ge=1)
    hierarchical_bootstrap_samples: int = Field(default=200, ge=10)
    hierarchical_bootstrap_seed: int = 0
    hierarchical_bootstrap_confidence: float = Field(default=0.95, gt=0.0, lt=1.0)
    confirmation_n_mechanisms: int = Field(default=2, ge=1)
    grid_anisotropy_acknowledged: bool = True

    @field_validator("resolution_shapes")
    @classmethod
    def _resolution_shapes_ok(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("sprint6.resolution_shapes must be non-empty")
        out = [int(v) for v in value]
        if any(v < 2 for v in out):
            raise ValueError("resolution_shapes entries must be >= 2")
        if len(set(out)) != len(out):
            raise ValueError("resolution_shapes must not contain duplicates")
        return out


class AlgorithmsConfig(BaseModel):
    """Search algorithms and optional heuristic validation."""

    model_config = ConfigDict(extra="forbid")

    names: list[AlgorithmName] = Field(default_factory=_default_algorithm_names)
    validate_heuristic: bool = False

    @field_validator("names")
    @classmethod
    def _names_nonempty_unique(cls, value: list[AlgorithmName]) -> list[AlgorithmName]:
        if not value:
            raise ValueError("algorithms.names must be non-empty")
        if len(set(value)) != len(value):
            raise ValueError("algorithms.names must not contain duplicates")
        return list(value)


class FourBarFixedSource(BaseModel):
    """Fixed independent four-bar serialization."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["fixed"] = "fixed"
    mechanism: dict[str, Any]

    @field_validator("mechanism")
    @classmethod
    def _has_type(cls, value: dict[str, Any]) -> dict[str, Any]:
        if "type" not in value:
            raise ValueError("mechanism dict must include a 'type' key")
        return value

    def build(self) -> Mechanism:
        """Deserialize the fixed four-bar mechanism."""
        _ensure_mechanism_registry()
        return Mechanism.from_dict(self.mechanism)


class FourBarPopulationSource(BaseModel):
    """Per-trial crank-rocker population sampler (ADR-009)."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["population"] = "population"
    n_bars: int = Field(default=2, ge=1)
    d: float = 1.0
    length_low: float = 0.2
    length_high: float = 2.0
    grashof_margin: float = 0.05
    branch: int = 1
    min_follower_range: float = 0.5
    min_abs_transmission_ratio: float = 0.05
    max_abs_transmission_ratio: float = 20.0
    n_crank_samples: int = 361
    max_draw_attempts: int = 100_000
    periodic: bool = True
    name_prefix: str = "crank_rocker"

    def to_spec(self) -> CrankRockerPopulationSpec:
        """Materialize the sampler specification."""
        return CrankRockerPopulationSpec(
            d=float(self.d),
            length_low=float(self.length_low),
            length_high=float(self.length_high),
            grashof_margin=float(self.grashof_margin),
            branch=int(self.branch),
            min_follower_range=float(self.min_follower_range),
            min_abs_transmission_ratio=float(self.min_abs_transmission_ratio),
            max_abs_transmission_ratio=float(self.max_abs_transmission_ratio),
            n_crank_samples=int(self.n_crank_samples),
            max_draw_attempts=int(self.max_draw_attempts),
            periodic=bool(self.periodic),
            name_prefix=str(self.name_prefix),
        )


def _normalize_fourbar_source(value: Any) -> Any:
    """Accept legacy bare mechanism dicts as ``mode: fixed``."""
    if not isinstance(value, dict):
        return value
    if "mode" in value:
        return value
    if "type" in value:
        return {"mode": "fixed", "mechanism": value}
    return value


class MechanismPairConfig(BaseModel):
    """Paired gearbox and four-bar sources."""

    model_config = ConfigDict(extra="forbid")

    gearbox: dict[str, Any]
    fourbar: FourBarFixedSource | FourBarPopulationSource

    @field_validator("gearbox")
    @classmethod
    def _gearbox_has_type(cls, value: dict[str, Any]) -> dict[str, Any]:
        if "type" not in value:
            raise ValueError("mechanism dict must include a 'type' key")
        return value

    @field_validator("fourbar", mode="before")
    @classmethod
    def _coerce_fourbar(cls, value: Any) -> Any:
        return _normalize_fourbar_source(value)

    def gearbox_needs_derivation(self) -> bool:
        """Return True when equivalent gearbox ratios must be derived."""
        from inequality_mechanisms.mechanisms.equivalence import (
            is_derivable_equivalent_gearbox_dict,
        )

        return is_derivable_equivalent_gearbox_dict(self.gearbox)

    def build_gearbox(self, fourbar: Mechanism | None = None) -> Mechanism:
        """Deserialize the gearbox mechanism.

        When ``type: equivalent_gearbox`` omits ``ratios``, derive them from
        ``fourbar`` using ``matching_rule`` (ADR-012).
        """
        _ensure_mechanism_registry()
        if self.gearbox_needs_derivation():
            if fourbar is None:
                raise ValueError(
                    "equivalent_gearbox without ratios requires a four-bar "
                    "for match_equivalent_gearbox"
                )
            from inequality_mechanisms.mechanisms.equivalence import (
                match_equivalent_gearbox,
            )

            rule = str(self.gearbox["matching_rule"])
            n_samples = int(self.gearbox.get("n_samples", 361))
            periodic_raw = self.gearbox.get("periodic")
            periodic = tuple(periodic_raw) if periodic_raw is not None else None
            name = self.gearbox.get("name")
            return match_equivalent_gearbox(
                fourbar,
                matching_rule=rule,  # type: ignore[arg-type]
                n_samples=n_samples,
                periodic=periodic,
                name=None if name is None else str(name),
            )
        return Mechanism.from_dict(self.gearbox)

    def build_fourbar(self) -> Mechanism:
        """Deserialize a fixed four-bar mechanism.

        Raises
        ------
        TypeError
            If the four-bar source is population-sampled.
        """
        if not isinstance(self.fourbar, FourBarFixedSource):
            raise TypeError(
                "build_fourbar requires mechanisms.fourbar.mode == 'fixed'; "
                "population mode samples lengths per trial"
            )
        return self.fourbar.build()

    @property
    def fourbar_mode(self) -> FourBarMode:
        """Return ``fixed`` or ``population``."""
        return self.fourbar.mode  # type: ignore[return-value]

    def population_spec(self) -> CrankRockerPopulationSpec:
        """Return the crank-rocker sampler spec.

        Raises
        ------
        TypeError
            If the four-bar source is fixed.
        """
        if not isinstance(self.fourbar, FourBarPopulationSource):
            raise TypeError(
                "population_spec requires mechanisms.fourbar.mode == 'population'"
            )
        return self.fourbar.to_spec()


class TrialsConfig(BaseModel):
    """Paired task sampling parameters."""

    model_config = ConfigDict(extra="forbid")

    n_trials: int = Field(ge=1)
    min_output_separation: float = Field(default=0.0, ge=0.0)
    preimage_policy: PreimagePolicy = "lex_min_node_id"
    max_sample_attempts: int = Field(default=10_000, ge=1)
    snap_output_tol: float | None = Field(
        default=None,
        description=(
            "Explicit max d_Q(g(u_snapped), q) when snapping continuous "
            "preimages (IM-036). None uses default_snap_tol; the realized "
            "tolerance is stored on each PairedTask."
        ),
    )
    require_reachable: bool = Field(
        default=False,
        description=(
            "If true, discard tasks where either mechanism has no path "
            "(Dijkstra connectivity) until n_trials reachable pairs are kept."
        ),
    )
    n_path_samples: int = Field(
        default=0,
        ge=0,
        description=(
            "Write U/Q/Cartesian path PNGs for the first k kept trials "
            "(0 disables)."
        ),
    )


class ExperimentConfig(BaseModel):
    """Top-level Version 1 experiment configuration.

    Parameters
    ----------
    seed :
        Master RNG seed for mechanism and task sampling.
    mechanisms :
        Gearbox serialization plus fixed or population four-bar source.
    graph :
        Shared input lattice shape (both mechanisms use the same grid
        geometry in the native pilot mode).
    limits :
        Absolute shared output joint limits. Required for ``fixed`` four-bar
        mode; forbidden for ``population`` mode (limits come from each
        sampled four-bar's follower ranges).
    cost :
        Edge-cost family (``type`` for single-cost pilot; optional ``types``
        for Sprint Four factorial runs).
    algorithms :
        Forward search algorithms to run on each paired task.
    trials :
        Number of matched start/goal tasks and preimage selection policy.
    sprint4 :
        Optional Sprint Four P1 options (landscape, bootstrap, gain
        thresholds). Defaults apply when omitted.
    path_quality :
        Optional Sprint Five path-quality options (revisit window and
        thresholds). Defaults apply when omitted.
    sprint6 :
        Optional Sprint Six equivalence / resolution / hierarchical Monte
        Carlo options (ADR-012 / ADR-013). Defaults apply when omitted.
    """

    model_config = ConfigDict(extra="forbid")

    seed: int
    mechanisms: MechanismPairConfig
    graph: GraphConfig
    limits: LimitsConfig | None = None
    cost: CostConfig = Field(default_factory=CostConfig)
    algorithms: AlgorithmsConfig = Field(default_factory=AlgorithmsConfig)
    trials: TrialsConfig
    sprint4: Sprint4Config = Field(default_factory=Sprint4Config)
    path_quality: PathQualityConfig = Field(default_factory=PathQualityConfig)
    sprint6: Sprint6Config = Field(default_factory=Sprint6Config)

    @model_validator(mode="after")
    def _dims_and_limits_agree(self) -> ExperimentConfig:
        mode = self.mechanisms.fourbar_mode
        if mode == "fixed":
            if self.limits is None:
                raise ValueError("limits are required when fourbar.mode == 'fixed'")
            fb = self.mechanisms.build_fourbar()
            if fb.input_dim != 2 or fb.output_dim != 2:
                raise ValueError("fourbar must have input_dim == output_dim == 2")
            gb = self.mechanisms.build_gearbox(fb)
            if gb.input_dim != 2 or gb.output_dim != 2:
                raise ValueError("gearbox must have input_dim == output_dim == 2")
            if self.limits.to_limits().dim != gb.output_dim:
                raise ValueError("limits.dim must equal mechanism output_dim")
        else:
            if self.limits is not None:
                raise ValueError(
                    "limits must be omitted when fourbar.mode == 'population'; "
                    "shared Q limits are taken from each sampled four-bar's "
                    "follower ranges"
                )
            src = self.mechanisms.fourbar
            assert isinstance(src, FourBarPopulationSource)
            if int(src.n_bars) != 2:
                raise ValueError("population fourbar.n_bars must be 2 for Version 1")
            # Construct the spec so invalid population numbers fail at load time.
            src.to_spec()
            if self.mechanisms.gearbox_needs_derivation():
                rule = str(self.mechanisms.gearbox.get("matching_rule", ""))
                if rule not in {"span", "total_variation", "rms_gain"}:
                    raise ValueError(
                        "equivalent_gearbox matching_rule must be one of "
                        "{span, total_variation, rms_gain}"
                    )
            else:
                gb = self.mechanisms.build_gearbox()
                if gb.input_dim != 2 or gb.output_dim != 2:
                    raise ValueError(
                        "gearbox must have input_dim == output_dim == 2"
                    )
        return self


def load_experiment_config(path: Path | str) -> ExperimentConfig:
    """Load and validate an experiment config from YAML.

    Parameters
    ----------
    path :
        Path to a YAML document matching ``ExperimentConfig``.

    Returns
    -------
    ExperimentConfig
        Validated configuration.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the YAML root is not a mapping.
    pydantic.ValidationError
        If fields fail schema validation.
    """
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"config root must be a mapping, got {type(raw).__name__}")
    return ExperimentConfig.model_validate(raw)


def experiment_config_to_yaml(config: ExperimentConfig) -> str:
    """Serialize a validated config to a YAML string."""
    payload = config.model_dump(mode="python")
    dumped = yaml.safe_dump(payload, sort_keys=False)
    return str(dumped)
