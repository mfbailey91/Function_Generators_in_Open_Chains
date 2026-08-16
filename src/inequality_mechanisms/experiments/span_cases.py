"""Generated 17-case ordered union for the V3.6D span corpus."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars
from inequality_mechanisms.mechanisms.operating_branch import OperatingBranch
from inequality_mechanisms.mechanisms.span_registry import SpanRegistry
from inequality_mechanisms.mechanisms.span_synthesis import (
    CanonicalSynthesisResult,
    reconstruct_bar,
)
from inequality_mechanisms.mechanisms import equivalent_gearbox_branch, select_fourbar_monotonic_branch

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


def _require_supported(row: CanonicalSynthesisResult, axis: str) -> None:
    if row.status == "unsupported_under_certificate":
        raise ValueError(f"{axis} span {row.target_span_deg} is unsupported")


def _profile_gain(row: CanonicalSynthesisResult) -> float:
    if row.status == "boundary_stress_only":
        return 0.005
    return 0.05


def realize_span_case(case: SpanCase, registry: SpanRegistry) -> RealizedSpanCase:
    """Build certified four-bar and span-matched gearbox branches."""
    j1 = registry.record_for(case.span_j1_deg)
    j2 = registry.record_for(case.span_j2_deg)
    _require_supported(j1, "J1")
    _require_supported(j2, "J2")
    if j1.u_interval_rad is None or j2.u_interval_rad is None:
        raise ValueError("supported spans must record U intervals")
    bars = IndependentFourBars(
        [
            reconstruct_bar(j1),
            reconstruct_bar(j2),
        ],
        name=case.case_id,
    )
    fourbar = select_fourbar_monotonic_branch(
        bars,
        u_intervals=[j1.u_interval_rad, j2.u_interval_rad],
        min_abs_gain=min(_profile_gain(j1), _profile_gain(j2)),
        endpoint_margin_fraction=0.0,
        name=case.case_id,
    )
    gearbox = equivalent_gearbox_branch(
        fourbar, matching_rule="span", name="span_matched_gearbox"
    )
    return RealizedSpanCase(case=case, fourbar=fourbar, gearbox=gearbox, j1=j1, j2=j2)


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
