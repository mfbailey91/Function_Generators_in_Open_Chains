"""Tests for sampling provenance records (Sprint V2.3, V2-301)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.graphs.sampling import (
    SamplingDomain,
    SamplingSpecification,
    TransitionParameterization,
    compute_axis_spacing_statistics,
)


class TestSamplingEnums:
    def test_sampling_domain_values(self) -> None:
        assert SamplingDomain.INPUT.value == "input"
        assert SamplingDomain.OUTPUT.value == "output"

    def test_transition_parameterization_values(self) -> None:
        assert TransitionParameterization.INPUT_LINEAR.value == "input_linear"
        assert TransitionParameterization.OUTPUT_LINEAR.value == "output_linear"


class TestSamplingSpecification:
    def test_basic_construction(self) -> None:
        spec = SamplingSpecification(
            domain=SamplingDomain.INPUT,
            shape=(5, 7),
            endpoint=True,
            axis_lower=(-1.0, 0.0),
            axis_upper=(1.0, 2.0),
        )
        assert spec.ndim == 2
        assert spec.shape == (5, 7)
        samples0 = spec.axis_samples(0)
        assert samples0 == pytest.approx(np.linspace(-1.0, 1.0, 5))
        samples1 = spec.axis_samples(1)
        assert samples1 == pytest.approx(np.linspace(0.0, 2.0, 7))

    def test_shape_entry_too_small_rejected(self) -> None:
        with pytest.raises(ValueError, match=">= 2"):
            SamplingSpecification(
                domain=SamplingDomain.OUTPUT,
                shape=(1,),
                endpoint=True,
                axis_lower=(0.0,),
                axis_upper=(1.0,),
            )

    def test_length_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            SamplingSpecification(
                domain=SamplingDomain.OUTPUT,
                shape=(3, 3),
                endpoint=True,
                axis_lower=(0.0,),
                axis_upper=(1.0,),
            )

    def test_nonpositive_span_rejected(self) -> None:
        with pytest.raises(ValueError, match="axis_upper must exceed"):
            SamplingSpecification(
                domain=SamplingDomain.OUTPUT,
                shape=(3,),
                endpoint=True,
                axis_lower=(1.0,),
                axis_upper=(1.0,),
            )

    def test_serialization_round_trip(self) -> None:
        spec = SamplingSpecification(
            domain=SamplingDomain.OUTPUT,
            shape=(4,),
            endpoint=True,
            axis_lower=(-2.0,),
            axis_upper=(2.0,),
        )
        restored = SamplingSpecification.from_dict(spec.to_dict())
        assert restored == spec


class TestAxisSpacingStatistics:
    def test_uniform_samples_have_ratio_one(self) -> None:
        samples = np.linspace(0.0, 10.0, 11)
        stats = compute_axis_spacing_statistics(samples, axis=0)
        assert stats.minimum == pytest.approx(1.0)
        assert stats.maximum == pytest.approx(1.0)
        assert stats.mean == pytest.approx(1.0)
        assert stats.std == pytest.approx(0.0, abs=1e-12)
        assert stats.max_to_min_ratio == pytest.approx(1.0)

    def test_nonuniform_samples_have_ratio_above_one(self) -> None:
        samples = np.array([0.0, 1.0, 3.0, 7.0], dtype=np.float64)
        stats = compute_axis_spacing_statistics(samples, axis=1)
        assert stats.axis == 1
        assert stats.minimum == pytest.approx(1.0)
        assert stats.maximum == pytest.approx(4.0)
        assert stats.max_to_min_ratio == pytest.approx(4.0)

    def test_degenerate_zero_spacing_gives_infinite_ratio(self) -> None:
        samples = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        stats = compute_axis_spacing_statistics(samples, axis=0)
        assert stats.minimum == pytest.approx(0.0)
        assert stats.max_to_min_ratio == float("inf")

    def test_too_few_samples_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least two"):
            compute_axis_spacing_statistics([1.0], axis=0)

    def test_non_1d_rejected(self) -> None:
        with pytest.raises(ValueError, match="1-D"):
            compute_axis_spacing_statistics([[1.0, 2.0], [3.0, 4.0]], axis=0)
