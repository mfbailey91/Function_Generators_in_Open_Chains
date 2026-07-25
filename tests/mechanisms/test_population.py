"""Tests for crank-rocker population sampling (ADR-009)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.mechanisms.fourbar import IndependentFourBars, PlanarFourBar
from inequality_mechanisms.mechanisms.population import (
    CrankRockerPopulationSpec,
    follower_range,
    is_strict_crank_rocker,
    limits_from_fourbar_follower_ranges,
    passes_population_filters,
    sample_crank_rocker,
    sample_independent_crank_rockers,
)

# Classic crank-rocker scaled so ground length d = 1.
_CR_D1 = (0.5, 1.25, 1.0, 1.0)


class TestIsStrictCrankRocker:
    def test_classic_accepted(self) -> None:
        assert is_strict_crank_rocker(*_CR_D1, margin=0.05) is True

    def test_non_grashof_rejected(self) -> None:
        # s+l = p+q change-point / non-Grashof family.
        assert is_strict_crank_rocker(1.0, 1.0, 1.0, 1.0, margin=0.05) is False

    def test_shortest_not_crank_rejected(self) -> None:
        # Grashof double-rocker: shortest is ground.
        assert is_strict_crank_rocker(2.0, 2.5, 2.0, 1.0, margin=0.05) is False

    def test_negative_margin_raises(self) -> None:
        with pytest.raises(ValueError, match="margin"):
            is_strict_crank_rocker(*_CR_D1, margin=-0.1)


class TestFollowerRangeAndFilters:
    def test_follower_range_positive_width(self) -> None:
        bar = PlanarFourBar(*_CR_D1, branch=1)
        q_lo, q_hi = follower_range(bar)
        assert q_hi > q_lo
        assert (q_hi - q_lo) > 1.0

    def test_classic_passes_default_spec(self) -> None:
        bar = PlanarFourBar(*_CR_D1, branch=1)
        assert passes_population_filters(bar, CrankRockerPopulationSpec()) is True

    def test_wrong_ground_length_rejected(self) -> None:
        bar = PlanarFourBar(1.0, 2.5, 2.0, 2.0, branch=1)
        assert passes_population_filters(bar, CrankRockerPopulationSpec()) is False


class TestSampleCrankRocker:
    def test_seeded_deterministic(self) -> None:
        a = sample_crank_rocker(np.random.default_rng(7))
        b = sample_crank_rocker(np.random.default_rng(7))
        assert a.lengths == b.lengths

    def test_samples_pass_filters_and_vary(self) -> None:
        rng = np.random.default_rng(3)
        spec = CrankRockerPopulationSpec()
        lengths = []
        for _ in range(8):
            bar = sample_crank_rocker(rng, spec)
            assert passes_population_filters(bar, spec)
            assert bar.lengths[3] == pytest.approx(1.0)
            lengths.append(bar.lengths)
        assert len(set(lengths)) >= 2

    def test_exhaustion_raises(self) -> None:
        spec = CrankRockerPopulationSpec(
            length_low=1.5,
            length_high=1.6,
            d=1.0,
            grashof_margin=0.5,
            max_draw_attempts=20,
        )
        with pytest.raises(ValueError, match="failed to sample"):
            sample_crank_rocker(np.random.default_rng(0), spec)

    def test_rejects_non_generator(self) -> None:
        with pytest.raises(TypeError, match="Generator"):
            sample_crank_rocker(np.random.RandomState(0))  # type: ignore[arg-type]


class TestIndependentAndLimits:
    def test_sample_pair_and_shared_limits(self) -> None:
        fb = sample_independent_crank_rockers(np.random.default_rng(11), n_bars=2)
        assert isinstance(fb, IndependentFourBars)
        assert len(fb.bars) == 2
        assert fb.bars[0].lengths != fb.bars[1].lengths

        limits = limits_from_fourbar_follower_ranges(fb)
        assert limits.dim == 2
        for i, bar in enumerate(fb.bars):
            q_lo, q_hi = follower_range(bar)
            assert limits.lower[i] >= q_lo - 1e-12
            assert limits.upper[i] <= q_hi + 1e-12
            assert limits.upper[i] > limits.lower[i]

    def test_spec_round_trip(self) -> None:
        spec = CrankRockerPopulationSpec(min_follower_range=0.7, grashof_margin=0.1)
        restored = CrankRockerPopulationSpec.from_dict(spec.to_dict())
        assert restored.min_follower_range == pytest.approx(0.7)
        assert restored.grashof_margin == pytest.approx(0.1)
