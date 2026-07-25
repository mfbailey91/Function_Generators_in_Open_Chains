"""Crank-rocker population sampling for Monte Carlo trials (ADR-009).

Paper §12.1 filters: normalized ground length ``d``, strict Grashof crank-
rocker, full crank cycle on the selected branch, minimum follower range,
and practical transmission-ratio bounds away from change points.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.random import Generator
from numpy.typing import NDArray

from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars, PlanarFourBar
from inequality_mechanisms.spaces.limits import OutputJointLimits

_TWO_PI = 2.0 * np.pi
_DEFAULT_N_SAMPLES = 361
_BOUND_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class CrankRockerPopulationSpec:
    """Sampling and filter parameters for Version-1 crank-rockers.

    Parameters
    ----------
    d :
        Fixed ground length (paper normalizes ``d = 1``).
    length_low, length_high :
        Inclusive uniform bounds for drawing ``a``, ``b``, and ``c``.
    grashof_margin :
        Require ``s + l + margin < p + q`` (strict Grashof).
    branch :
        Algebraic sheet for constructed bars (``+1`` or ``-1``).
    min_follower_range :
        Minimum width of the selected-branch follower image (radians).
    min_abs_transmission_ratio, max_abs_transmission_ratio :
        Practical transmission-ratio bounds: require finite Jacobians with
        ``|dq/du| <= max`` everywhere and ``max|dq/du| >= min`` (near-zero
        ratios at rocker extremes are allowed).
    n_crank_samples :
        Dense samples on ``[0, 2 pi)`` for validity / range / ratio checks.
    max_draw_attempts :
        Hard cap on rejected length draws before raising.
    periodic :
        Periodicity flag for each constructed planar bar.
    name_prefix :
        Base name for sampled mechanisms.
    """

    d: float = 1.0
    length_low: float = 0.2
    length_high: float = 2.0
    grashof_margin: float = 0.05
    branch: int = 1
    min_follower_range: float = 0.5
    min_abs_transmission_ratio: float = 0.05
    max_abs_transmission_ratio: float = 20.0
    n_crank_samples: int = _DEFAULT_N_SAMPLES
    max_draw_attempts: int = 100_000
    periodic: bool = True
    name_prefix: str = "crank_rocker"

    def __post_init__(self) -> None:
        if not np.isfinite(self.d) or float(self.d) <= 0.0:
            raise ValueError(f"d must be finite and positive, got {self.d}")
        if not np.isfinite(self.length_low) or not np.isfinite(self.length_high):
            raise ValueError("length_low and length_high must be finite")
        if float(self.length_low) <= 0.0:
            raise ValueError(f"length_low must be positive, got {self.length_low}")
        if float(self.length_high) <= float(self.length_low):
            raise ValueError("length_high must be strictly greater than length_low")
        if not np.isfinite(self.grashof_margin) or float(self.grashof_margin) < 0.0:
            raise ValueError(
                f"grashof_margin must be finite and >= 0, got {self.grashof_margin}"
            )
        if int(self.branch) not in (1, -1):
            raise ValueError(f"branch must be +1 or -1, got {self.branch}")
        if (
            not np.isfinite(self.min_follower_range)
            or float(self.min_follower_range) <= 0.0
        ):
            raise ValueError(
                f"min_follower_range must be finite and positive, "
                f"got {self.min_follower_range}"
            )
        if (
            not np.isfinite(self.min_abs_transmission_ratio)
            or float(self.min_abs_transmission_ratio) <= 0.0
        ):
            raise ValueError(
                "min_abs_transmission_ratio must be finite and positive, "
                f"got {self.min_abs_transmission_ratio}"
            )
        if (
            not np.isfinite(self.max_abs_transmission_ratio)
            or float(self.max_abs_transmission_ratio)
            <= float(self.min_abs_transmission_ratio)
        ):
            raise ValueError(
                "max_abs_transmission_ratio must be finite and strictly greater "
                "than min_abs_transmission_ratio"
            )
        if int(self.n_crank_samples) < 8:
            raise ValueError(
                f"n_crank_samples must be >= 8, got {self.n_crank_samples}"
            )
        if int(self.max_draw_attempts) < 1:
            raise ValueError(
                f"max_draw_attempts must be >= 1, got {self.max_draw_attempts}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize sampler parameters."""
        return {
            "d": float(self.d),
            "length_low": float(self.length_low),
            "length_high": float(self.length_high),
            "grashof_margin": float(self.grashof_margin),
            "branch": int(self.branch),
            "min_follower_range": float(self.min_follower_range),
            "min_abs_transmission_ratio": float(self.min_abs_transmission_ratio),
            "max_abs_transmission_ratio": float(self.max_abs_transmission_ratio),
            "n_crank_samples": int(self.n_crank_samples),
            "max_draw_attempts": int(self.max_draw_attempts),
            "periodic": bool(self.periodic),
            "name_prefix": str(self.name_prefix),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrankRockerPopulationSpec:
        """Deserialize sampler parameters."""
        return cls(
            d=float(data.get("d", 1.0)),
            length_low=float(data.get("length_low", 0.2)),
            length_high=float(data.get("length_high", 2.0)),
            grashof_margin=float(data.get("grashof_margin", 0.05)),
            branch=int(data.get("branch", 1)),
            min_follower_range=float(data.get("min_follower_range", 0.5)),
            min_abs_transmission_ratio=float(
                data.get("min_abs_transmission_ratio", 0.05)
            ),
            max_abs_transmission_ratio=float(
                data.get("max_abs_transmission_ratio", 20.0)
            ),
            n_crank_samples=int(data.get("n_crank_samples", _DEFAULT_N_SAMPLES)),
            max_draw_attempts=int(data.get("max_draw_attempts", 100_000)),
            periodic=bool(data.get("periodic", True)),
            name_prefix=str(data.get("name_prefix", "crank_rocker")),
        )


def is_strict_crank_rocker(
    a: float,
    b: float,
    c: float,
    d: float,
    *,
    margin: float = 0.0,
) -> bool:
    """Return whether lengths form a strict Grashof crank-rocker.

    Requires all lengths finite and positive, ``s + l + margin < p + q``,
    and the shortest link to be the crank ``a``.
    """
    lengths = (float(a), float(b), float(c), float(d))
    if any((not np.isfinite(x)) or x <= 0.0 for x in lengths):
        return False
    if not np.isfinite(margin) or margin < 0.0:
        raise ValueError(f"margin must be finite and >= 0, got {margin}")
    ordered = sorted(lengths)
    s, p, q, longest = ordered
    if s + longest + margin >= p + q:
        return False
    return float(a) == s


def _crank_samples(n: int) -> NDArray[np.floating]:
    return np.linspace(0.0, _TWO_PI, int(n), endpoint=False)


def follower_range(
    bar: PlanarFourBar,
    *,
    n_samples: int = _DEFAULT_N_SAMPLES,
) -> tuple[float, float]:
    """Return ``(q_min, q_max)`` of the selected-branch follower curve.

    Uses an unwrapped dense crank sweep so the reported interval is the
    continuous image of one full crank revolution on the chosen sheet.
    """
    if not isinstance(bar, PlanarFourBar):
        raise TypeError("bar must be a PlanarFourBar")
    if int(n_samples) < 8:
        raise ValueError(f"n_samples must be >= 8, got {n_samples}")
    u = _crank_samples(n_samples)
    qs = bar.follower_curve(u, unwrap=True)
    return float(np.min(qs)), float(np.max(qs))


def full_crank_cycle_assembles(
    bar: PlanarFourBar,
    *,
    n_samples: int = _DEFAULT_N_SAMPLES,
) -> bool:
    """Return whether ``valid_input`` holds on a dense crank lattice."""
    u = _crank_samples(n_samples)
    return all(bar.valid_input([float(uu)]) for uu in u)


def transmission_ratio_bounds_ok(
    bar: PlanarFourBar,
    *,
    r_min: float,
    r_max: float,
    n_samples: int = _DEFAULT_N_SAMPLES,
) -> bool:
    """Return whether transmission ratios stay practical on a crank sweep.

    Requires a finite Jacobian at every sample (no change-point singularity),
    ``|dq/du| <= r_max`` everywhere, and ``max |dq/du| >= r_min`` so the
    rocker is not effectively locked. Near-zero ratios at rocker extremes
    are allowed.
    """
    if r_min <= 0.0 or r_max <= r_min:
        raise ValueError("require 0 < r_min < r_max")
    u = _crank_samples(n_samples)
    peak = 0.0
    for uu in u:
        try:
            ratio = float(bar.output_jacobian([float(uu)])[0, 0])
        except ValueError:
            return False
        mag = abs(ratio)
        if not np.isfinite(mag) or mag > r_max:
            return False
        if mag > peak:
            peak = mag
    return peak >= r_min


def passes_population_filters(
    bar: PlanarFourBar,
    spec: CrankRockerPopulationSpec,
) -> bool:
    """Return whether ``bar`` satisfies the Version-1 population filters."""
    a, b, c, d = bar.lengths
    if abs(d - float(spec.d)) > 1e-12:
        return False
    if not is_strict_crank_rocker(a, b, c, d, margin=float(spec.grashof_margin)):
        return False
    if int(bar.branch) != int(spec.branch):
        return False
    n = int(spec.n_crank_samples)
    if not full_crank_cycle_assembles(bar, n_samples=n):
        return False
    q_lo, q_hi = follower_range(bar, n_samples=n)
    if (q_hi - q_lo) < float(spec.min_follower_range):
        return False
    if not transmission_ratio_bounds_ok(
        bar,
        r_min=float(spec.min_abs_transmission_ratio),
        r_max=float(spec.max_abs_transmission_ratio),
        n_samples=n,
    ):
        return False
    return True


def sample_crank_rocker(
    rng: Generator,
    spec: CrankRockerPopulationSpec | None = None,
    *,
    name: str | None = None,
) -> PlanarFourBar:
    """Draw one crank-rocker that passes ``spec`` filters.

    Raises
    ------
    ValueError
        If ``max_draw_attempts`` is exhausted without an accepted draw.
    TypeError
        If ``rng`` is not a NumPy ``Generator``.
    """
    if not isinstance(rng, Generator):
        raise TypeError("rng must be a numpy.random.Generator")
    pop = spec if spec is not None else CrankRockerPopulationSpec()
    lo = float(pop.length_low)
    hi = float(pop.length_high)
    for _ in range(int(pop.max_draw_attempts)):
        a, b, c = (float(x) for x in rng.uniform(lo, hi, size=3))
        try:
            bar = PlanarFourBar(
                a,
                b,
                c,
                float(pop.d),
                branch=int(pop.branch),
                periodic=(bool(pop.periodic),),
                name=name or pop.name_prefix,
            )
        except ValueError:
            continue
        if passes_population_filters(bar, pop):
            return bar
    raise ValueError(
        f"failed to sample a crank-rocker after {pop.max_draw_attempts} draws"
    )


def sample_independent_crank_rockers(
    rng: Generator,
    spec: CrankRockerPopulationSpec | None = None,
    *,
    n_bars: int = 2,
    name: str | None = None,
) -> IndependentFourBars:
    """Draw ``n_bars`` independent crank-rockers under ``spec``."""
    if int(n_bars) < 1:
        raise ValueError(f"n_bars must be >= 1, got {n_bars}")
    pop = spec if spec is not None else CrankRockerPopulationSpec()
    base = name or pop.name_prefix
    bars = [
        sample_crank_rocker(rng, pop, name=f"{base}[{i}]") for i in range(int(n_bars))
    ]
    return IndependentFourBars(bars, name=base)


def limits_from_fourbar_follower_ranges(
    fourbar: IndependentFourBars,
    *,
    n_samples: int = _DEFAULT_N_SAMPLES,
    eps: float = _BOUND_EPS,
) -> OutputJointLimits:
    """Build shared Q limits from each bar's selected-branch follower range.

    The closed box uses ``[q_min + eps, q_max - eps]`` per axis when the
    shrunk width remains positive; otherwise the raw ``[q_min, q_max]`` is
    used. The same object is intended for both gearbox and four-bar graphs.
    """
    if not isinstance(fourbar, IndependentFourBars):
        raise TypeError("fourbar must be an IndependentFourBars")
    if float(eps) < 0.0 or not np.isfinite(eps):
        raise ValueError(f"eps must be finite and >= 0, got {eps}")
    lower: list[float] = []
    upper: list[float] = []
    for bar in fourbar.bars:
        q_lo, q_hi = follower_range(bar, n_samples=n_samples)
        width = q_hi - q_lo
        if width <= 0.0:
            raise ValueError("follower range must have positive width")
        if width > 2.0 * float(eps):
            lower.append(q_lo + float(eps))
            upper.append(q_hi - float(eps))
        else:
            lower.append(q_lo)
            upper.append(q_hi)
    return OutputJointLimits.box(lower=lower, upper=upper)
