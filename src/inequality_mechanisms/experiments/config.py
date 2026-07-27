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


class CostConfig(BaseModel):
    """Edge-cost selection for search."""

    model_config = ConfigDict(extra="forbid")

    type: CostType = "output_euclidean"


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

    def build_gearbox(self) -> Mechanism:
        """Deserialize the gearbox mechanism."""
        _ensure_mechanism_registry()
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
        Edge-cost family (Version 1: output Euclidean).
    algorithms :
        Forward search algorithms to run on each paired task.
    trials :
        Number of matched start/goal tasks and preimage selection policy.
    """

    model_config = ConfigDict(extra="forbid")

    seed: int
    mechanisms: MechanismPairConfig
    graph: GraphConfig
    limits: LimitsConfig | None = None
    cost: CostConfig = Field(default_factory=CostConfig)
    algorithms: AlgorithmsConfig = Field(default_factory=AlgorithmsConfig)
    trials: TrialsConfig

    @model_validator(mode="after")
    def _dims_and_limits_agree(self) -> ExperimentConfig:
        gb = self.mechanisms.build_gearbox()
        if gb.input_dim != 2 or gb.output_dim != 2:
            raise ValueError("gearbox must have input_dim == output_dim == 2")

        mode = self.mechanisms.fourbar_mode
        if mode == "fixed":
            if self.limits is None:
                raise ValueError("limits are required when fourbar.mode == 'fixed'")
            fb = self.mechanisms.build_fourbar()
            if fb.input_dim != 2 or fb.output_dim != 2:
                raise ValueError("fourbar must have input_dim == output_dim == 2")
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
