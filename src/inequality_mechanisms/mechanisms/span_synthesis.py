"""Deterministic canonical crank-rocker synthesis for a target usable span."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

import numpy as np
from numpy.random import Generator

from inequality_mechanisms.mechanisms.fourbar import PlanarFourBar
from inequality_mechanisms.mechanisms.operating_branch import (
    BranchCertificationError,
    OperatingBranch,
)
from inequality_mechanisms.mechanisms.population import (
    follower_range,
    is_strict_crank_rocker,
)
from inequality_mechanisms.mechanisms.span_ranges import (
    OutputRangeDefinition,
    classification_for_span_deg,
    zero_centered_usable,
)
from inequality_mechanisms.mechanisms.branch_selection import (
    select_fourbar_monotonic_branch,
)

SynthesisStatus = Literal[
    "certified_primary",
    "boundary_stress_only",
    "unsupported_under_certificate",
]

PRIMARY_CERTIFICATE_NAME = "canonical_monotonic_branch_v1"
NEAR_LIMIT_CERTIFICATE_NAME = "canonical_monotonic_branch_near_limit_v1"
SYNTHESIS_SEED = 650
TARGET_SPAN_TOLERANCE_DEG = 0.25
NORMALIZED_GROUND = 1.0
GRASHOF_MARGIN = 0.0


@dataclass(frozen=True, slots=True)
class MonotonicBranchCertificateProfile:
    """Frozen select/certify knobs. Do not retune after inspecting 175°."""

    name: str
    n_samples: int = 361
    min_abs_gain: float = 0.05
    min_u_width: float = 0.3
    endpoint_margin_fraction: float = 0.05
    table_samples_per_axis: int = 65
    certification_samples_per_axis: int = 17
    residual_tol: float = 1e-6

    def to_dict(self) -> dict[str, Any]:
        """Serialize the frozen profile."""
        return {
            "name": self.name,
            "n_samples": int(self.n_samples),
            "min_abs_gain": float(self.min_abs_gain),
            "min_u_width": float(self.min_u_width),
            "endpoint_margin_fraction": float(self.endpoint_margin_fraction),
            "table_samples_per_axis": int(self.table_samples_per_axis),
            "certification_samples_per_axis": int(self.certification_samples_per_axis),
            "residual_tol": float(self.residual_tol),
        }


PRIMARY_CERTIFICATE = MonotonicBranchCertificateProfile(name=PRIMARY_CERTIFICATE_NAME)
NEAR_LIMIT_CERTIFICATE = MonotonicBranchCertificateProfile(
    name=NEAR_LIMIT_CERTIFICATE_NAME,
    min_abs_gain=0.005,
    min_u_width=0.15,
    endpoint_margin_fraction=0.002,
)


@dataclass(frozen=True, slots=True)
class OutputRangeTarget:
    """Requested usable output span."""

    span_deg: float
    center_deg: float = 0.0
    tolerance_deg: float = TARGET_SPAN_TOLERANCE_DEG


@dataclass(frozen=True, slots=True)
class CanonicalSynthesisObjective:
    """Lexicographic selection terms. Planner/wrench outcomes are forbidden."""

    maximize_worst_margin: bool = True
    gain_shape_regularizer: str = "std_abs_dq_du"


@dataclass(frozen=True, slots=True)
class CanonicalSynthesisResult:
    """Typed outcome for one target span."""

    target_span_deg: float
    status: SynthesisStatus
    certificate_profile_name: str
    seed: int
    lengths: tuple[float, float, float, float] | None
    branch_sign: int | None
    range_definition: OutputRangeDefinition | None
    u_interval_rad: tuple[float, float] | None
    q_native_interval_rad: tuple[float, float] | None
    q_offset_rad: float | None
    min_abs_dq_du: float | None
    max_abs_dq_du: float | None
    mean_abs_dq_du: float | None
    std_abs_dq_du: float | None
    endpoint_gains: tuple[float, float] | None
    worst_certified_margin: float | None
    span_error_deg: float | None
    rejected_candidate_count: int
    evaluated_candidate_count: int
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly synthesis record (no operating-branch object)."""
        return {
            "target_span_deg": float(self.target_span_deg),
            "status": self.status,
            "certificate_profile_name": self.certificate_profile_name,
            "seed": int(self.seed),
            "lengths": None if self.lengths is None else [float(x) for x in self.lengths],
            "branch_sign": self.branch_sign,
            "range_definition": (
                None if self.range_definition is None else self.range_definition.to_dict()
            ),
            "u_interval_rad": (
                None if self.u_interval_rad is None else list(self.u_interval_rad)
            ),
            "q_native_interval_rad": (
                None
                if self.q_native_interval_rad is None
                else list(self.q_native_interval_rad)
            ),
            "q_offset_rad": self.q_offset_rad,
            "min_abs_dq_du": self.min_abs_dq_du,
            "max_abs_dq_du": self.max_abs_dq_du,
            "mean_abs_dq_du": self.mean_abs_dq_du,
            "std_abs_dq_du": self.std_abs_dq_du,
            "endpoint_gains": (
                None if self.endpoint_gains is None else list(self.endpoint_gains)
            ),
            "worst_certified_margin": self.worst_certified_margin,
            "span_error_deg": self.span_error_deg,
            "rejected_candidate_count": int(self.rejected_candidate_count),
            "evaluated_candidate_count": int(self.evaluated_candidate_count),
            "failure_reason": self.failure_reason,
        }


def _bar(a: float, b: float, c: float, *, branch: int, name: str) -> PlanarFourBar | None:
    if not is_strict_crank_rocker(a, b, c, NORMALIZED_GROUND, margin=GRASHOF_MARGIN):
        return None
    try:
        return PlanarFourBar(
            float(a),
            float(b),
            float(c),
            NORMALIZED_GROUND,
            branch=int(branch),
            periodic=(True,),
            name=name,
        )
    except ValueError:
        return None


def _try_certify(
    bar: PlanarFourBar,
    profile: MonotonicBranchCertificateProfile,
) -> OperatingBranch | None:
    try:
        return select_fourbar_monotonic_branch(
            bar,
            n_samples=profile.n_samples,
            min_abs_gain=profile.min_abs_gain,
            min_u_width=profile.min_u_width,
            endpoint_margin_fraction=profile.endpoint_margin_fraction,
            table_samples_per_axis=profile.table_samples_per_axis,
            certification_samples_per_axis=profile.certification_samples_per_axis,
            residual_tol=profile.residual_tol,
            name=bar.name,
        )
    except (BranchCertificationError, ValueError):
        return None


def _native_bar(branch: OperatingBranch) -> PlanarFourBar:
    mech = branch.mechanism
    bars = getattr(mech, "bars", None)
    if bars:
        return bars[0]
    if isinstance(mech, PlanarFourBar):
        return mech
    raise TypeError("expected a planar four-bar operating branch")


def _gain_samples(branch: OperatingBranch, n: int = 65) -> np.ndarray:
    lo = float(branch.certificate.input_lower[0])
    hi = float(branch.certificate.input_upper[0])
    u = np.linspace(lo, hi, int(n))
    gains = np.empty(u.shape[0], dtype=np.float64)
    for i, uu in enumerate(u):
        j = branch.jacobian([float(uu)])
        gains[i] = abs(float(j[0, 0]))
    return gains


def _score_branch(
    branch: OperatingBranch,
    profile: MonotonicBranchCertificateProfile,
    target: OutputRangeTarget,
) -> tuple[float, float, float, dict[str, Any]] | None:
    q_lo = float(branch.certificate.output_lower[0])
    q_hi = float(branch.certificate.output_upper[0])
    usable = q_hi - q_lo
    if usable <= 0.0:
        return None
    span_deg = float(np.rad2deg(usable))
    error = abs(span_deg - float(target.span_deg))
    if error > float(target.tolerance_deg):
        return None
    gains = _gain_samples(branch)
    min_g = float(np.min(gains))
    max_g = float(np.max(gains))
    mean_g = float(np.mean(gains))
    std_g = float(np.std(gains))
    gain_margin = min_g - float(profile.min_abs_gain)
    mech_lo, mech_hi = follower_range(_native_bar(branch))
    half_gap = min(q_lo - mech_lo, mech_hi - q_hi)
    worst = min(gain_margin, half_gap)
    payload = {
        "span_deg": span_deg,
        "error_deg": error,
        "q_lo": q_lo,
        "q_hi": q_hi,
        "u_lo": float(branch.certificate.input_lower[0]),
        "u_hi": float(branch.certificate.input_upper[0]),
        "mech_lo": mech_lo,
        "mech_hi": mech_hi,
        "min_g": min_g,
        "max_g": max_g,
        "mean_g": mean_g,
        "std_g": std_g,
        "endpoint_gains": (float(gains[0]), float(gains[-1])),
        "worst": worst,
        "offset": 0.5 * (q_lo + q_hi),
    }
    # Lexicographic: error already gated; maximize worst margin; minimize std.
    return (worst, -std_g, -error, payload)


def _candidate_lengths(rng: Generator) -> list[tuple[float, float, float]]:
    """Deterministic covering set biased toward both small and large rocker swing."""
    structured: list[tuple[float, float, float]] = []
    a_vals = np.concatenate(
        [
            np.linspace(0.20, 0.70, 9),
                np.linspace(0.72, 0.97, 10),
                np.array([0.98, 0.99, 0.995, 0.999]),
        ]
    )
    bc_vals = np.concatenate(
        [
            np.linspace(0.45, 1.20, 8),
            np.linspace(1.22, 2.70, 10),
        ]
    )
    for a in a_vals:
        for b in bc_vals:
            for c in bc_vals:
                structured.append((float(a), float(b), float(c)))
    extras = rng.uniform(low=[0.18, 0.40, 0.40], high=[0.98, 2.80, 2.80], size=(600, 3))
    for row in extras:
        structured.append((float(row[0]), float(row[1]), float(row[2])))
    # Known large-swing neighborhood and the normalized legacy fixture.
    structured.extend(
        [
            (0.95, 1.28, 1.28),
            (0.95, 1.54, 1.54),
            (0.90, 1.03, 1.03),
            (0.80, 1.03, 0.91),
            (0.999, 1.088, 1.088),
            (0.999, 2.265, 2.265),
        ]
    )
    return structured


def _result_from_payload(
    *,
    target: OutputRangeTarget,
    status: SynthesisStatus,
    profile: MonotonicBranchCertificateProfile,
    seed: int,
    bar: PlanarFourBar,
    payload: Mapping[str, Any],
    rejected: int,
    evaluated: int,
) -> CanonicalSynthesisResult:
    usable = float(payload["q_hi"]) - float(payload["q_lo"])
    mechanical = float(payload["mech_hi"]) - float(payload["mech_lo"])
    ranges = zero_centered_usable(
        target_span_deg=target.span_deg,
        usable_span_rad=usable,
        mechanical_span_rad=mechanical,
        classification=classification_for_span_deg(target.span_deg),
    )
    return CanonicalSynthesisResult(
        target_span_deg=float(target.span_deg),
        status=status,
        certificate_profile_name=profile.name,
        seed=int(seed),
        lengths=tuple(float(x) for x in bar.lengths),
        branch_sign=int(bar.branch),
        range_definition=ranges,
        u_interval_rad=(float(payload["u_lo"]), float(payload["u_hi"])),
        q_native_interval_rad=(float(payload["q_lo"]), float(payload["q_hi"])),
        q_offset_rad=float(payload["offset"]),
        min_abs_dq_du=float(payload["min_g"]),
        max_abs_dq_du=float(payload["max_g"]),
        mean_abs_dq_du=float(payload["mean_g"]),
        std_abs_dq_du=float(payload["std_g"]),
        endpoint_gains=tuple(payload["endpoint_gains"]),
        worst_certified_margin=float(payload["worst"]),
        span_error_deg=float(payload["error_deg"]),
        rejected_candidate_count=int(rejected),
        evaluated_candidate_count=int(evaluated),
    )


def _unsupported(
    target: OutputRangeTarget,
    profile: MonotonicBranchCertificateProfile,
    seed: int,
    rejected: int,
    evaluated: int,
    reason: str,
) -> CanonicalSynthesisResult:
    return CanonicalSynthesisResult(
        target_span_deg=float(target.span_deg),
        status="unsupported_under_certificate",
        certificate_profile_name=profile.name,
        seed=int(seed),
        lengths=None,
        branch_sign=None,
        range_definition=None,
        u_interval_rad=None,
        q_native_interval_rad=None,
        q_offset_rad=None,
        min_abs_dq_du=None,
        max_abs_dq_du=None,
        mean_abs_dq_du=None,
        std_abs_dq_du=None,
        endpoint_gains=None,
        worst_certified_margin=None,
        span_error_deg=None,
        rejected_candidate_count=int(rejected),
        evaluated_candidate_count=int(evaluated),
        failure_reason=reason,
    )


def _evaluate_pool(
    profile: MonotonicBranchCertificateProfile,
    seed: int,
    rng: Generator,
) -> tuple[int, int, list[tuple[PlanarFourBar, dict[str, Any]]]]:
    """Certify the deterministic candidate pool once."""
    rejected = 0
    evaluated = 0
    pool: list[tuple[PlanarFourBar, dict[str, Any]]] = []
    dummy = OutputRangeTarget(span_deg=90.0, tolerance_deg=1e9)
    for a, b, c in _candidate_lengths(rng):
        for branch_sign in (1, -1):
            bar = _bar(a, b, c, branch=branch_sign, name="span_candidate")
            if bar is None:
                rejected += 1
                continue
            evaluated += 1
            mech_lo, mech_hi = follower_range(bar)
            mechanical_deg = float(np.rad2deg(mech_hi - mech_lo))
            if mechanical_deg < 94.5:
                rejected += 1
                continue
            certified = _try_certify(bar, profile)
            if certified is None:
                rejected += 1
                continue
            scored = _score_branch(certified, profile, dummy)
            if scored is None:
                rejected += 1
                continue
            _worst, _neg_std, _neg_err, payload = scored
            pool.append((bar, payload))
    return rejected, evaluated, pool


def _select_from_pool(
    *,
    target: OutputRangeTarget,
    status: SynthesisStatus,
    profile: MonotonicBranchCertificateProfile,
    seed: int,
    pool: Sequence[tuple[PlanarFourBar, Mapping[str, Any]]],
    rejected: int,
    evaluated: int,
) -> CanonicalSynthesisResult | None:
    best: tuple[float, float, float, PlanarFourBar, Mapping[str, Any]] | None = None
    for bar, payload in pool:
        error = abs(float(payload["span_deg"]) - float(target.span_deg))
        if error > float(target.tolerance_deg):
            continue
        key = (float(payload["worst"]), -float(payload["std_g"]), -error)
        if best is None or key > best[:3]:
            updated = dict(payload)
            updated["error_deg"] = error
            best = (key[0], key[1], key[2], bar, updated)
    if best is None:
        return None
    return _result_from_payload(
        target=target,
        status=status,
        profile=profile,
        seed=seed,
        bar=best[3],
        payload=best[4],
        rejected=rejected,
        evaluated=evaluated,
    )


def synthesize_canonical_crank_rocker(
    target: OutputRangeTarget,
    certificate: MonotonicBranchCertificateProfile = PRIMARY_CERTIFICATE,
    objective: CanonicalSynthesisObjective | None = None,
    seed: int = SYNTHESIS_SEED,
    *,
    allow_near_limit: bool = False,
    near_limit_certificate: MonotonicBranchCertificateProfile = NEAR_LIMIT_CERTIFICATE,
    rng: Generator | None = None,
) -> CanonicalSynthesisResult:
    """Search for one deterministic canonical crank-rocker at ``target``.

    The primary certificate is never mutated after a miss. ``175`` may fall
    through to a separately frozen near-limit profile when
    ``allow_near_limit`` is true.
    """
    del objective
    engine = rng if rng is not None else np.random.default_rng(int(seed))
    rejected, evaluated, pool = _evaluate_pool(certificate, seed, engine)
    selected = _select_from_pool(
        target=target,
        status="certified_primary",
        profile=certificate,
        seed=seed,
        pool=pool,
        rejected=rejected,
        evaluated=evaluated,
    )
    if selected is not None:
        return selected
    if allow_near_limit and abs(float(target.span_deg) - 175.0) <= 1e-9:
        fallback_pool_seed = np.random.default_rng(int(seed) + 175)
        n_rejected, n_eval, n_pool = _evaluate_pool(
            near_limit_certificate, seed, fallback_pool_seed
        )
        fallback = _select_from_pool(
            target=target,
            status="boundary_stress_only",
            profile=near_limit_certificate,
            seed=seed,
            pool=n_pool,
            rejected=rejected + n_rejected,
            evaluated=evaluated + n_eval,
        )
        if fallback is not None:
            return fallback
        return _unsupported(
            target,
            certificate,
            seed,
            rejected + n_rejected,
            evaluated + n_eval,
            "no candidate satisfied primary or near-limit certificates",
        )
    return _unsupported(
        target,
        certificate,
        seed,
        rejected,
        evaluated,
        "no candidate satisfied the frozen primary certificate",
    )


def synthesize_span_family(
    spans_deg: Sequence[float] = (95.0, 135.0, 145.0, 150.0, 175.0),
    *,
    seed: int = SYNTHESIS_SEED,
    tolerance_deg: float = TARGET_SPAN_TOLERANCE_DEG,
) -> dict[float, CanonicalSynthesisResult]:
    """Synthesize every unique target from one shared primary candidate pool."""
    rng = np.random.default_rng(int(seed))
    rejected, evaluated, pool = _evaluate_pool(PRIMARY_CERTIFICATE, seed, rng)
    out: dict[float, CanonicalSynthesisResult] = {}
    for span in spans_deg:
        target = OutputRangeTarget(span_deg=float(span), tolerance_deg=tolerance_deg)
        allow_near = abs(float(span) - 175.0) <= 1e-9
        selected = _select_from_pool(
            target=target,
            status="certified_primary",
            profile=PRIMARY_CERTIFICATE,
            seed=seed,
            pool=pool,
            rejected=rejected,
            evaluated=evaluated,
        )
        if selected is not None:
            out[float(span)] = selected
            continue
        if allow_near:
            out[float(span)] = synthesize_canonical_crank_rocker(
                target,
                allow_near_limit=True,
                seed=seed,
            )
        else:
            out[float(span)] = _unsupported(
                target,
                PRIMARY_CERTIFICATE,
                seed,
                rejected,
                evaluated,
                "no candidate satisfied the frozen primary certificate",
            )
    return out


def reconstruct_bar(result: CanonicalSynthesisResult) -> PlanarFourBar:
    """Rebuild the accepted four-bar from a synthesis record."""
    if result.lengths is None or result.branch_sign is None:
        raise ValueError("cannot reconstruct an unsupported synthesis result")
    a, b, c, d = result.lengths
    return PlanarFourBar(
        a, b, c, d, branch=int(result.branch_sign), periodic=(True,), name="reconstructed"
    )


def reconstruct_branch(
    result: CanonicalSynthesisResult,
    profile: MonotonicBranchCertificateProfile | None = None,
) -> OperatingBranch:
    """Recertify the accepted four-bar under the recorded profile."""
    if result.status == "unsupported_under_certificate":
        raise ValueError("unsupported synthesis has no operating branch")
    if profile is None:
        profile = (
            NEAR_LIMIT_CERTIFICATE
            if result.status == "boundary_stress_only"
            else PRIMARY_CERTIFICATE
        )
    bar = reconstruct_bar(result)
    branch = _try_certify(bar, profile)
    if branch is None:
        raise ValueError("recorded lengths failed recertification")
    return branch
