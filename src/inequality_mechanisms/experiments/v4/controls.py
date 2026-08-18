"""Canonical four-bar, span-matched gearbox, and identity-on-shared-Q arms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from inequality_mechanisms.adapters import planar_2r_operating_branch_robot
from inequality_mechanisms.experiments.v4.atlas_config import Planar2RGeometryAtlasConfig
from inequality_mechanisms.kinematics.planar_2r import Planar2R
from inequality_mechanisms.mechanisms import (
    IndependentFourBars,
    PlanarFourBar,
    equivalent_gearbox_branch,
    select_fourbar_monotonic_branch,
    unit_gearbox_branch,
)
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch


class AtlasControlError(ValueError):
    """Raised when null-control construction fails closed."""

    failure_code = "span_match_failed"


@dataclass(frozen=True, slots=True)
class AtlasArm:
    """One mechanism arm on the shared planar-2R robot."""

    mechanism_id: str
    branch: OperatingBranch
    robot: Any
    provenance: Mapping[str, Any]


def fourbar_branch(config: Planar2RGeometryAtlasConfig) -> OperatingBranch:
    """Certified monotonic crank-rocker pair."""
    spec = config.fourbar
    bars = [
        PlanarFourBar(
            a=spec.a, b=spec.b, c=spec.c, d=spec.d, branch=spec.branch, name="b0"
        ),
        PlanarFourBar(
            a=spec.a, b=spec.b, c=spec.c, d=spec.d, branch=spec.branch, name="b1"
        ),
    ]
    return select_fourbar_monotonic_branch(IndependentFourBars(bars))


def span_matched_ratios(fourbar: OperatingBranch) -> tuple[float, float]:
    """Return ADR-012 span ratios for the certified four-bar box."""
    cert = fourbar.certificate
    u_lo = np.asarray(cert.input_lower, dtype=np.float64)
    u_hi = np.asarray(cert.input_upper, dtype=np.float64)
    q_lo = np.asarray(cert.output_lower, dtype=np.float64)
    q_hi = np.asarray(cert.output_upper, dtype=np.float64)
    denom = u_hi - u_lo
    if np.any(denom <= 0.0):
        raise AtlasControlError("four-bar input box has non-positive span")
    ratios = (q_hi - q_lo) / denom
    return (float(ratios[0]), float(ratios[1]))


def identity_on_shared_q(fourbar: OperatingBranch) -> OperatingBranch:
    """Identity transmission whose input box is the four-bar Q box.

    This is identity-on-shared-Q, not a unit gearbox on a generic input box.
    """
    cert = fourbar.certificate
    return unit_gearbox_branch(
        2,
        input_lower=cert.output_lower,
        input_upper=cert.output_upper,
        output_space=fourbar.output_space,
        name="identity_on_shared_q",
    )


def build_atlas_arms(config: Planar2RGeometryAtlasConfig) -> dict[str, AtlasArm]:
    """Return the three atlas arms sharing planar FK and the four-bar Q box."""
    fk = Planar2R(L1=config.planar2r.L1, L2=config.planar2r.L2)
    fourbar = fourbar_branch(config)
    gearbox = equivalent_gearbox_branch(
        fourbar, matching_rule=config.matching_rule, name="span_matched_gearbox"
    )
    identity = identity_on_shared_q(fourbar)
    q_lo = np.asarray(fourbar.certificate.output_lower, dtype=np.float64)
    q_hi = np.asarray(fourbar.certificate.output_upper, dtype=np.float64)
    for arm, label in (
        (gearbox, "span_matched_gearbox"),
        (identity, "identity_on_shared_q"),
    ):
        arm_lo = np.asarray(arm.certificate.output_lower, dtype=np.float64)
        arm_hi = np.asarray(arm.certificate.output_upper, dtype=np.float64)
        if not (
            np.allclose(arm_lo, q_lo, atol=1e-12, rtol=0.0)
            and np.allclose(arm_hi, q_hi, atol=1e-12, rtol=0.0)
        ):
            raise AtlasControlError(
                f"{label} output box does not cover the four-bar Q box: "
                f"fourbar=[{q_lo.tolist()}, {q_hi.tolist()}], "
                f"{label}=[{arm_lo.tolist()}, {arm_hi.tolist()}]"
            )
    ratios = span_matched_ratios(fourbar)
    return {
        "fourbar": AtlasArm(
            mechanism_id="fourbar",
            branch=fourbar,
            robot=planar_2r_operating_branch_robot(fourbar, planar_fk=fk),
            provenance={"role": "canonical_crank_rocker"},
        ),
        "span_matched_gearbox": AtlasArm(
            mechanism_id="span_matched_gearbox",
            branch=gearbox,
            robot=planar_2r_operating_branch_robot(gearbox, planar_fk=fk),
            provenance={
                "role": "span_matched_affine_gearbox",
                "matching_rule": config.matching_rule,
                "ratios": list(ratios),
            },
        ),
        "identity_on_shared_q": AtlasArm(
            mechanism_id="identity_on_shared_q",
            branch=identity,
            robot=planar_2r_operating_branch_robot(identity, planar_fk=fk),
            provenance={
                "role": "identity_null_control",
                "note": "J_g = I on the four-bar Q box; not a ranked competitor",
            },
        ),
    }
