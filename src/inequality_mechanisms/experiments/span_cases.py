"""Generated 17-case ordered union for the V3.6D span corpus."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from inequality_mechanisms.mechanisms import (
    equivalent_gearbox_branch,
    select_fourbar_monotonic_branch,
)
from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch
from inequality_mechanisms.mechanisms.output_mounting import mount_operating_branch
from inequality_mechanisms.mechanisms.span_registry import SpanRegistry
from inequality_mechanisms.mechanisms.span_synthesis import (
    CanonicalSynthesisResult,
    reconstruct_bar,
)

CORE_SPANS_DEG = (95.0, 145.0, 175.0)
BIO_SPANS_DEG = (135.0, 145.0, 150.0)


@dataclass(frozen=True, slots=True)
class SpanCase:
    """One ordered (J1, J2) assignment with membership tags."""

    case_id: str
    span_j1_deg: float
    span_j2_deg: float
    memberships: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the generated case identity."""
        return {
            "case_id": self.case_id,
            "span_j1_deg": float(self.span_j1_deg),
            "span_j2_deg": float(self.span_j2_deg),
            "memberships": list(self.memberships),
        }


def case_id_for(span_j1_deg: float, span_j2_deg: float) -> str:
    """Return the deterministic case id ``span_j1_095_j2_175``."""
    return f"span_j1_{int(round(span_j1_deg)):03d}_j2_{int(round(span_j2_deg)):03d}"


def generate_span_cases() -> tuple[SpanCase, ...]:
    """Generate the ordered 17-case union from the two 3x3 designs."""
    grouped: dict[tuple[int, int], list[str]] = {}
    order: list[tuple[int, int]] = []
    for label, spans in (
        ("core_span_sweep", CORE_SPANS_DEG),
        ("biological_refinement", BIO_SPANS_DEG),
    ):
        for j1 in spans:
            for j2 in spans:
                key = (int(round(j1)), int(round(j2)))
                if key not in grouped:
                    grouped[key] = []
                    order.append(key)
                if label not in grouped[key]:
                    grouped[key].append(label)
    cases = tuple(
        SpanCase(
            case_id=case_id_for(float(j1), float(j2)),
            span_j1_deg=float(j1),
            span_j2_deg=float(j2),
            memberships=tuple(grouped[(j1, j2)]),
        )
        for j1, j2 in sorted(order)
    )
    if len(cases) != 17:
        raise ValueError(f"expected 17 unique cases, got {len(cases)}")
    ids = [row.case_id for row in cases]
    if len(set(ids)) != 17:
        raise ValueError("case ids are not unique")
    return cases


@dataclass(frozen=True, slots=True)
class RealizedSpanCase:
    """Four-bar pair and matched gearbox for one generated case."""

    case: SpanCase
    fourbar: OperatingBranch
    gearbox: OperatingBranch
    j1: CanonicalSynthesisResult
    j2: CanonicalSynthesisResult

    def to_dict(self) -> dict[str, Any]:
        """Serialize identities and branch certificates."""
        return {
            **self.case.to_dict(),
            "j1_status": self.j1.status,
            "j2_status": self.j2.status,
            "fourbar_certificate": self.fourbar.certificate.to_dict(),
            "gearbox_certificate": self.gearbox.certificate.to_dict(),
        }


_MOUNTED_Q_ATOL = 1e-9


def _require_supported(row: CanonicalSynthesisResult, axis: str) -> None:
    if row.status == "unsupported_under_certificate":
        raise ValueError(f"{axis} span {row.target_span_deg} is unsupported")


def _require_offset(row: CanonicalSynthesisResult, axis: str) -> float:
    offset = row.q_offset_rad
    if offset is None or not math.isfinite(float(offset)):
        raise ValueError(
            f"{axis} span {row.target_span_deg} must record a finite q_offset_rad"
        )
    return float(offset)


def _profile_gain(row: CanonicalSynthesisResult) -> float:
    if row.status == "boundary_stress_only":
        return 0.005
    return 0.05


def _supported_records(
    case: SpanCase, registry: SpanRegistry
) -> tuple[CanonicalSynthesisResult, CanonicalSynthesisResult]:
    j1 = registry.record_for(case.span_j1_deg)
    j2 = registry.record_for(case.span_j2_deg)
    _require_supported(j1, "J1")
    _require_supported(j2, "J2")
    if j1.u_interval_rad is None or j2.u_interval_rad is None:
        raise ValueError("supported spans must record U intervals")
    return j1, j2


def _native_fourbar_for_case(
    case: SpanCase,
    j1: CanonicalSynthesisResult,
    j2: CanonicalSynthesisResult,
) -> OperatingBranch:
    """Reconstruct native four-bars and restore recorded U intervals."""
    bars = IndependentFourBars(
        [
            reconstruct_bar(j1),
            reconstruct_bar(j2),
        ],
        name=case.case_id,
    )
    return select_fourbar_monotonic_branch(
        bars,
        u_intervals=[j1.u_interval_rad, j2.u_interval_rad],
        min_abs_gain=min(_profile_gain(j1), _profile_gain(j2)),
        endpoint_margin_fraction=0.0,
        name=case.case_id,
    )


def _assert_mounted_matches_registry(
    branch: OperatingBranch,
    j1: CanonicalSynthesisResult,
    j2: CanonicalSynthesisResult,
) -> None:
    """Require mounted certificate Q to equal frozen usable intervals."""
    cert = branch.certificate
    for axis, (label, row) in enumerate((("J1", j1), ("J2", j2))):
        if row.range_definition is None:
            raise ValueError(
                f"{label} span {row.target_span_deg} must record a range definition"
            )
        row.range_definition.assert_zero_centered()
        usable = row.range_definition.usable_interval_rad
        lo = float(cert.output_lower[axis])
        hi = float(cert.output_upper[axis])
        if abs(lo - float(usable[0])) > _MOUNTED_Q_ATOL:
            raise ValueError(f"{label} mounted output_lower {lo} != usable {usable[0]}")
        if abs(hi - float(usable[1])) > _MOUNTED_Q_ATOL:
            raise ValueError(f"{label} mounted output_upper {hi} != usable {usable[1]}")


def realize_span_case(case: SpanCase, registry: SpanRegistry) -> RealizedSpanCase:
    """Build certified four-bar and span-matched gearbox branches.

    Historical V4.2/V4.2A owner: native follower coordinates, not mounted Q.
    """
    j1, j2 = _supported_records(case, registry)
    fourbar = _native_fourbar_for_case(case, j1, j2)
    gearbox = equivalent_gearbox_branch(
        fourbar, matching_rule="span", name="span_matched_gearbox"
    )
    return RealizedSpanCase(case=case, fourbar=fourbar, gearbox=gearbox, j1=j1, j2=j2)


def realize_mounted_span_case(
    case: SpanCase, registry: SpanRegistry
) -> RealizedSpanCase:
    """Build mounted four-bar and span-matched gearbox branches.

    V4.2B owner: apply each stored ``q_offset_rad`` exactly once, then
    span-match the gearbox from the mounted branch. Does not resynthesize.
    """
    j1, j2 = _supported_records(case, registry)
    offset = (_require_offset(j1, "J1"), _require_offset(j2, "J2"))
    native = _native_fourbar_for_case(case, j1, j2)
    mounted = mount_operating_branch(native, offset)
    _assert_mounted_matches_registry(mounted, j1, j2)
    gearbox = equivalent_gearbox_branch(
        mounted, matching_rule="span", name="span_matched_gearbox"
    )
    return RealizedSpanCase(case=case, fourbar=mounted, gearbox=gearbox, j1=j1, j2=j2)


def realize_supported_cases(registry: SpanRegistry) -> tuple[RealizedSpanCase, ...]:
    """Realize every generated case whose spans are not unsupported."""
    realized: list[RealizedSpanCase] = []
    for case in generate_span_cases():
        j1 = registry.record_for(case.span_j1_deg)
        j2 = registry.record_for(case.span_j2_deg)
        if j1.status == "unsupported_under_certificate":
            continue
        if j2.status == "unsupported_under_certificate":
            continue
        realized.append(realize_span_case(case, registry))
    return tuple(realized)
