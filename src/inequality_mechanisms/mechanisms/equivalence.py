"""Equivalent-gain matching for Sprint Six linear baselines (ADR-012).

Match a four-bar transmission to an affine gearbox

    q = q_ref + r_eq * (u - u_ref)

under an explicit criterion: span (monotonic), total variation, or RMS gain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from inequality_mechanisms.mechanisms.base import Mechanism
from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars, PlanarFourBar
from inequality_mechanisms.mechanisms.gearbox import EquivalentGearbox
from inequality_mechanisms.mechanisms.monotonic import primary_monotonic_sector

MatchingRule = Literal["span", "total_variation", "rms_gain"]
SequenceIntervals = Sequence[tuple[float, float]]

BASELINE_LABELS: tuple[str, ...] = (
    "unit_gearbox",
    "span_matched_gearbox",
    "tv_matched_gearbox",
    "rms_matched_gearbox",
    "fourbar",
)

_MATCHING_TO_BASELINE: dict[str, str] = {
    "span": "span_matched_gearbox",
    "total_variation": "tv_matched_gearbox",
    "rms_gain": "rms_matched_gearbox",
}

_TWO_PI = 2.0 * np.pi

# Quantities matched under each comparison (S6-18).
MATCHED_QUANTITY_TABLE: tuple[dict[str, str], ...] = (
    {
        "comparison": "unit_gearbox vs fourbar",
        "input_span": "maybe",
        "output_span": "no",
        "mean_absolute_gain": "no",
        "rms_gain": "no",
        "topology": "no",
    },
    {
        "comparison": "span_matched_gearbox vs monotonic fourbar",
        "input_span": "yes",
        "output_span": "yes",
        "mean_absolute_gain": "related",
        "rms_gain": "not required",
        "topology": "no",
    },
    {
        "comparison": "tv_matched_gearbox vs full-cycle fourbar",
        "input_span": "yes",
        "output_span": "no",
        "mean_absolute_gain": "yes",
        "rms_gain": "no",
        "topology": "no",
    },
    {
        "comparison": "rms_matched_gearbox vs full-cycle fourbar",
        "input_span": "yes",
        "output_span": "no",
        "mean_absolute_gain": "no",
        "rms_gain": "yes",
        "topology": "no",
    },
)


def baseline_label_for_matching_rule(rule: str) -> str:
    """Map a matching rule to the Sprint Six comparison label."""
    key = str(rule).strip()
    if key not in _MATCHING_TO_BASELINE:
        raise ValueError(
            f"unknown matching_rule {rule!r}; expected one of "
            f"{sorted(_MATCHING_TO_BASELINE)}"
        )
    return _MATCHING_TO_BASELINE[key]


def baseline_label_for_mechanism(mech: Mechanism) -> str:
    """Return the Sprint Six baseline label for a mechanism instance."""
    type_key = str(getattr(mech, "type_key", ""))
    if type_key == "unit_gearbox":
        return "unit_gearbox"
    if type_key == "equivalent_gearbox":
        rule = str(getattr(mech, "matching_rule"))
        return baseline_label_for_matching_rule(rule)
    if type_key in {"independent_fourbars", "planar_fourbar"}:
        return "fourbar"
    if type_key == "fixed_ratio_gearbox":
        ratios = np.asarray(getattr(mech, "ratios"), dtype=np.float64)
        if ratios.size > 0 and np.allclose(ratios, 1.0):
            return "unit_gearbox"
        raise ValueError(
            "fixed_ratio_gearbox is not a Sprint Six named baseline; "
            "use unit_gearbox or equivalent_gearbox"
        )
    raise ValueError(f"no Sprint Six baseline label for mechanism type {type_key!r}")


@dataclass(frozen=True, slots=True)
class AxisMatchResult:
    """Per-axis matching numbers for one planar four-bar."""

    ratio: float
    u_ref: float
    q_ref: float
    u_lo: float
    u_hi: float
    q_lo: float
    q_hi: float
    total_variation: float
    rms_gain: float
    cycle_class: Literal["monotonic", "full_cycle"]


def _axis_samples(
    bar: PlanarFourBar,
    *,
    u_lo: float,
    u_hi: float,
    n_samples: int,
) -> tuple[NDArray[np.floating], NDArray[np.floating], NDArray[np.floating]]:
    """Return ``(u, q_unwrapped, dqdu)`` on ``[u_lo, u_hi]``."""
    if int(n_samples) < 16:
        raise ValueError(f"n_samples must be >= 16, got {n_samples}")
    if not (float(u_hi) > float(u_lo)):
        raise ValueError(f"require u_hi > u_lo, got [{u_lo}, {u_hi}]")
    u = np.linspace(float(u_lo), float(u_hi), int(n_samples), dtype=np.float64)
    q = bar.follower_curve(u, unwrap=True)
    ratios = np.empty(u.shape[0], dtype=np.float64)
    for i, uu in enumerate(u):
        try:
            ratios[i] = float(bar.output_jacobian([float(uu)])[0, 0])
        except ValueError:
            ratios[i] = np.nan
    return u, q, ratios


def axis_total_variation(q: ArrayLike) -> float:
    """Total variation of a 1-D output sample path."""
    arr = np.asarray(q, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise ValueError("q must be 1-D with at least two samples")
    if not np.all(np.isfinite(arr)):
        raise ValueError("q must be finite")
    return float(np.sum(np.abs(np.diff(arr))))


def axis_rms_gain(ratios: ArrayLike, *, du: float | None = None) -> float:
    """RMS of ``dq/du`` samples (trapezoidal mean of squares when ``du`` set)."""
    arr = np.asarray(ratios, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 1:
        raise ValueError("ratios must be a non-empty 1-D array")
    finite = arr[np.isfinite(arr)]
    if finite.size < 1:
        raise ValueError("ratios must contain at least one finite sample")
    if du is None or arr.size < 2 or not np.all(np.isfinite(arr)):
        return float(np.sqrt(np.mean(finite**2)))
    sq = arr**2
    trapz = getattr(np, "trapezoid", None)
    if trapz is None:
        trapz = np.trapz  # type: ignore[attr-defined]
    integral = float(trapz(sq))
    dx = float(du) / float(arr.size - 1)
    mean_sq = (integral * dx) / float(du)
    if mean_sq < 0.0:
        mean_sq = 0.0
    return float(np.sqrt(mean_sq))


def match_planar_fourbar_axis(
    bar: PlanarFourBar,
    *,
    matching_rule: MatchingRule,
    u_interval: tuple[float, float] | None = None,
    n_samples: int = 361,
    min_abs_gain: float = 0.05,
    min_u_width: float = 0.3,
) -> AxisMatchResult:
    """Compute equivalent ratio and refs for one planar four-bar axis.

    Parameters
    ----------
    bar :
        Planar four-bar on a fixed algebraic branch.
    matching_rule :
        ``span``, ``total_variation``, or ``rms_gain``.
    u_interval :
        Optional ``(u_lo, u_hi)``. For ``span``, omitted intervals select the
        primary monotonic sector. For TV/RMS, default is a full crank cycle
        ``[0, 2π]``.
    n_samples :
        Dense crank samples for quadrature / TV.
    min_abs_gain, min_u_width :
        Forwarded to monotonic-sector detection for span matching.
    """
    if not isinstance(bar, PlanarFourBar):
        raise TypeError("bar must be a PlanarFourBar")
    rule = str(matching_rule)

    if rule == "span":
        if u_interval is None:
            sector = primary_monotonic_sector(
                bar,
                n_samples=n_samples,
                min_abs_gain=min_abs_gain,
                min_u_width=min_u_width,
            )
            u_lo, u_hi = float(sector.u_lo), float(sector.u_hi)
            q_lo, q_hi = float(sector.q_lo), float(sector.q_hi)
            q_at_lo = float(bar.follower_curve([u_lo], unwrap=True)[0])
            q_at_hi = float(bar.follower_curve([u_hi], unwrap=True)[0])
            du = u_hi - u_lo
            dq = q_at_hi - q_at_lo
            if abs(du) < 1e-12:
                raise ValueError("span matching requires nonempty u interval")
            ratio = float(dq / du)
            if not np.isfinite(ratio) or abs(ratio) < 1e-15:
                raise ValueError(f"span ratio must be nonzero finite, got {ratio}")
            u_s, q_s, r_s = _axis_samples(
                bar, u_lo=u_lo, u_hi=u_hi, n_samples=n_samples
            )
            tv = axis_total_variation(q_s)
            rms = axis_rms_gain(r_s, du=du)
            return AxisMatchResult(
                ratio=ratio,
                u_ref=u_lo,
                q_ref=q_at_lo,
                u_lo=u_lo,
                u_hi=u_hi,
                q_lo=min(q_lo, q_at_lo, q_at_hi),
                q_hi=max(q_hi, q_at_lo, q_at_hi),
                total_variation=tv,
                rms_gain=rms,
                cycle_class="monotonic",
            )
        u_lo, u_hi = float(u_interval[0]), float(u_interval[1])
        u_s, q_s, r_s = _axis_samples(bar, u_lo=u_lo, u_hi=u_hi, n_samples=n_samples)
        du = u_hi - u_lo
        dq = float(q_s[-1] - q_s[0])
        ratio = float(dq / du)
        if not np.isfinite(ratio) or abs(ratio) < 1e-15:
            raise ValueError(f"span ratio must be nonzero finite, got {ratio}")
        return AxisMatchResult(
            ratio=ratio,
            u_ref=u_lo,
            q_ref=float(q_s[0]),
            u_lo=u_lo,
            u_hi=u_hi,
            q_lo=float(np.min(q_s)),
            q_hi=float(np.max(q_s)),
            total_variation=axis_total_variation(q_s),
            rms_gain=axis_rms_gain(r_s, du=du),
            cycle_class="monotonic",
        )

    if u_interval is None:
        u_lo, u_hi = 0.0, _TWO_PI
    else:
        u_lo, u_hi = float(u_interval[0]), float(u_interval[1])
    u_s, q_s, r_s = _axis_samples(bar, u_lo=u_lo, u_hi=u_hi, n_samples=n_samples)
    du = u_hi - u_lo
    tv = axis_total_variation(q_s)
    rms = axis_rms_gain(r_s, du=du)
    if rule == "total_variation":
        ratio = float(tv / du)
    elif rule == "rms_gain":
        ratio = float(rms)
    else:
        raise ValueError(f"unknown matching_rule {matching_rule!r}")
    if not np.isfinite(ratio) or abs(ratio) < 1e-15:
        raise ValueError(f"{rule} ratio must be nonzero finite, got {ratio}")
    return AxisMatchResult(
        ratio=ratio,
        u_ref=u_lo,
        q_ref=float(q_s[0]),
        u_lo=u_lo,
        u_hi=u_hi,
        q_lo=float(np.min(q_s)),
        q_hi=float(np.max(q_s)),
        total_variation=tv,
        rms_gain=rms,
        cycle_class="full_cycle",
    )


def match_equivalent_gearbox(
    fourbar: Mechanism,
    *,
    matching_rule: MatchingRule,
    u_intervals: SequenceIntervals | None = None,
    n_samples: int = 361,
    periodic: tuple[bool, ...] | None = None,
    name: str | None = None,
    min_abs_gain: float = 0.05,
    min_u_width: float = 0.3,
) -> EquivalentGearbox:
    """Build an ``EquivalentGearbox`` matched to ``fourbar``.

    Parameters
    ----------
    fourbar :
        Typically ``IndependentFourBars`` (Version 1) or a single
        ``PlanarFourBar``.
    matching_rule :
        Matching criterion.
    u_intervals :
        Optional per-axis ``(u_lo, u_hi)`` pairs. Length must equal
        ``fourbar.input_dim``.
    n_samples :
        Dense crank samples per axis.
    periodic :
        Gearbox periodicity flags; default follows the four-bar.
    name :
        Optional mechanism name; defaults to a rule-based label.
    """
    rule = str(matching_rule)
    if rule not in {"span", "total_variation", "rms_gain"}:
        raise ValueError(f"unknown matching_rule {matching_rule!r}")

    if isinstance(fourbar, IndependentFourBars):
        bars = list(fourbar.bars)
    elif isinstance(fourbar, PlanarFourBar):
        bars = [fourbar]
    else:
        raise TypeError(
            "match_equivalent_gearbox requires IndependentFourBars or PlanarFourBar, "
            f"got {type(fourbar).__name__}"
        )

    dim = len(bars)
    if u_intervals is not None and len(u_intervals) != dim:
        raise ValueError(
            f"u_intervals must have length {dim}, got {len(u_intervals)}"
        )

    axis_results: list[AxisMatchResult] = []
    for i, bar in enumerate(bars):
        interval = None if u_intervals is None else tuple(u_intervals[i])
        axis_results.append(
            match_planar_fourbar_axis(
                bar,
                matching_rule=rule,  # type: ignore[arg-type]
                u_interval=interval,
                n_samples=n_samples,
                min_abs_gain=min_abs_gain,
                min_u_width=min_u_width,
            )
        )

    ratios = np.array([a.ratio for a in axis_results], dtype=np.float64)
    u_ref = np.array([a.u_ref for a in axis_results], dtype=np.float64)
    q_ref = np.array([a.q_ref for a in axis_results], dtype=np.float64)

    if periodic is None:
        periodic = fourbar.periodic_axes()

    label = baseline_label_for_matching_rule(rule)
    mech_name = name if name is not None else label

    provenance: dict[str, Any] = {
        "matching_rule": rule,
        "baseline_label": label,
        "n_samples": int(n_samples),
        "cycle_class": axis_results[0].cycle_class,
        "axes": [
            {
                "ratio": float(a.ratio),
                "u_interval": [float(a.u_lo), float(a.u_hi)],
                "q_interval": [float(a.q_lo), float(a.q_hi)],
                "total_variation": float(a.total_variation),
                "rms_gain": float(a.rms_gain),
                "cycle_class": a.cycle_class,
            }
            for a in axis_results
        ],
        "source_fourbar": fourbar.to_dict(),
    }

    return EquivalentGearbox(
        ratios=ratios,
        u_ref=u_ref,
        q_ref=q_ref,
        matching_rule=rule,
        periodic=periodic,
        name=mech_name,
        provenance=provenance,
    )


def verify_span_match(
    gearbox: EquivalentGearbox,
    fourbar: Mechanism,
    *,
    atol: float = 1e-5,
    rtol: float = 1e-4,
    n_samples: int | None = None,
) -> dict[str, Any]:
    """Check ``ΔU`` and ``ΔQ`` agreement for a span-matched pair."""
    if gearbox.matching_rule != "span":
        raise ValueError("verify_span_match requires matching_rule == 'span'")
    n = int(
        n_samples
        if n_samples is not None
        else gearbox.provenance.get("n_samples", 361)
    )
    rematch = match_equivalent_gearbox(
        fourbar, matching_rule="span", n_samples=n
    )
    axes = list(gearbox.provenance.get("axes", []))
    if not axes:
        axes = list(rematch.provenance.get("axes", []))
    report: dict[str, Any] = {"ok": True, "axes": []}
    for i, axis in enumerate(axes):
        du = float(axis["u_interval"][1] - axis["u_interval"][0])
        u0 = np.array(
            [float(ax["u_interval"][0]) for ax in axes], dtype=np.float64
        )
        u1 = np.array(
            [float(ax["u_interval"][1]) for ax in axes], dtype=np.float64
        )
        q0 = gearbox.input_to_output(u0)
        q1 = gearbox.input_to_output(u1)
        du_gb = float(u1[i] - u0[i])
        dq_gb = float(q1[i] - q0[i])
        dq_expected = float(gearbox.ratios[i]) * du_gb
        # Four-bar output span over the matched interval (endpoint image).
        dq_fb = float(rematch.ratios[i]) * float(
            rematch.provenance["axes"][i]["u_interval"][1]
            - rematch.provenance["axes"][i]["u_interval"][0]
        )
        ratio_ok = abs(float(gearbox.ratios[i]) - float(rematch.ratios[i])) <= (
            atol + rtol * max(1.0, abs(float(rematch.ratios[i])))
        )
        span_ok = (
            abs(du_gb - du) <= atol + rtol * abs(du)
            and abs(dq_gb - dq_expected) <= atol + rtol * max(1.0, abs(dq_expected))
            and abs(abs(dq_gb) - abs(dq_fb))
            <= atol + rtol * max(1.0, abs(dq_fb))
            and ratio_ok
        )
        report["axes"].append(
            {
                "axis": i,
                "delta_u_gb": du_gb,
                "delta_u_fb": du,
                "delta_q_gb": dq_gb,
                "delta_q_fb": dq_fb,
                "ok": span_ok,
            }
        )
        if not span_ok:
            report["ok"] = False
    return report


def verify_tv_match(
    gearbox: EquivalentGearbox,
    fourbar: Mechanism,
    *,
    atol: float = 1e-4,
    rtol: float = 1e-4,
    n_samples: int = 361,
) -> dict[str, Any]:
    """Check ``r_TV * Δu ≈ TV(q_fb)`` per axis."""
    if gearbox.matching_rule != "total_variation":
        raise ValueError("verify_tv_match requires matching_rule == 'total_variation'")
    rematch = match_equivalent_gearbox(
        fourbar, matching_rule="total_variation", n_samples=n_samples
    )
    report: dict[str, Any] = {"ok": True, "axes": []}
    for i, axis in enumerate(rematch.provenance["axes"]):
        du = float(axis["u_interval"][1] - axis["u_interval"][0])
        tv = float(axis["total_variation"])
        predicted = float(gearbox.ratios[i]) * du
        axis_ok = abs(predicted - tv) <= atol + rtol * max(1.0, abs(tv))
        report["axes"].append(
            {
                "axis": i,
                "r_tv_du": predicted,
                "tv_fb": tv,
                "ok": axis_ok,
            }
        )
        if not axis_ok:
            report["ok"] = False
    return report


def verify_rms_match(
    gearbox: EquivalentGearbox,
    fourbar: Mechanism,
    *,
    atol: float = 1e-4,
    rtol: float = 1e-4,
    n_samples: int = 361,
) -> dict[str, Any]:
    """Check ``r_RMS ≈ sqrt(mean((dq/du)^2))`` per axis."""
    if gearbox.matching_rule != "rms_gain":
        raise ValueError("verify_rms_match requires matching_rule == 'rms_gain'")
    rematch = match_equivalent_gearbox(
        fourbar, matching_rule="rms_gain", n_samples=n_samples
    )
    report: dict[str, Any] = {"ok": True, "axes": []}
    for i, axis in enumerate(rematch.provenance["axes"]):
        target = float(axis["rms_gain"])
        got = float(gearbox.ratios[i])
        axis_ok = abs(got - target) <= atol + rtol * max(1.0, abs(target))
        report["axes"].append(
            {
                "axis": i,
                "r_rms": got,
                "rms_fb": target,
                "ok": axis_ok,
            }
        )
        if not axis_ok:
            report["ok"] = False
    return report


def verify_matched_graphs(
    gearbox_graph: Any,
    fourbar_graph: Any,
) -> dict[str, Any]:
    """Verify identical input-graph geometry when matched graphs are required."""
    g_grid = gearbox_graph.grid
    f_grid = fourbar_graph.grid
    shape_ok = tuple(g_grid.shape) == tuple(f_grid.shape)
    ranges_ok = np.allclose(g_grid.ranges, f_grid.ranges)
    wrap_ok = tuple(g_grid.wrap) == tuple(f_grid.wrap)
    edge_ok = int(gearbox_graph.edge_samples) == int(fourbar_graph.edge_samples)
    ok = bool(shape_ok and ranges_ok and wrap_ok and edge_ok)
    return {
        "ok": ok,
        "shape_ok": shape_ok,
        "ranges_ok": bool(ranges_ok),
        "wrap_ok": wrap_ok,
        "edge_samples_ok": edge_ok,
        "gearbox_shape": list(g_grid.shape),
        "fourbar_shape": list(f_grid.shape),
        "gearbox_wrap": list(g_grid.wrap),
        "fourbar_wrap": list(f_grid.wrap),
        "gearbox_edge_samples": int(gearbox_graph.edge_samples),
        "fourbar_edge_samples": int(fourbar_graph.edge_samples),
    }


def equivalence_summary_rows() -> list[dict[str, str]]:
    """Return the S6-18 matched-quantity summary table rows."""
    return [dict(row) for row in MATCHED_QUANTITY_TABLE]


def is_derivable_equivalent_gearbox_dict(data: Mapping[str, Any]) -> bool:
    """Return True when YAML omits ratios and expects four-bar derivation."""
    return (
        str(data.get("type", "")) == "equivalent_gearbox"
        and "ratios" not in data
        and "matching_rule" in data
    )
