"""Mechanism maps from input configuration space to output joint space."""

from inequality_mechanisms.mechanisms.base import (
    Mechanism,
    MechanismRegistryError,
    clear_mechanism_registry,
    register_mechanism_type,
)
from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars, PlanarFourBar
from inequality_mechanisms.mechanisms.gearbox import FixedRatioGearbox, UnitGearbox
from inequality_mechanisms.mechanisms.population import (
    CrankRockerPopulationSpec,
    follower_range,
    is_strict_crank_rocker,
    limits_from_fourbar_follower_ranges,
    sample_crank_rocker,
    sample_independent_crank_rockers,
)

__all__ = [
    "CrankRockerPopulationSpec",
    "FixedRatioGearbox",
    "IndependentFourBars",
    "Mechanism",
    "MechanismRegistryError",
    "PlanarFourBar",
    "UnitGearbox",
    "clear_mechanism_registry",
    "follower_range",
    "is_strict_crank_rocker",
    "limits_from_fourbar_follower_ranges",
    "register_mechanism_type",
    "sample_crank_rocker",
    "sample_independent_crank_rockers",
]
