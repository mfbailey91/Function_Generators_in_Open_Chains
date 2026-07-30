"""Tests for Sprint Five path-quality metrics (S5-02 … S5-05)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.metrics.path_quality import (
    compute_path_quality_from_trajectories,
    count_self_intersections,
    cumulative_turning,
    near_revisit_metrics,
    segments_intersect,
)


class TestDirectness:
    def test_straight_path_ratio_one(self) -> None:
        u = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        q = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        m = compute_path_quality_from_trajectories(u, q, optimal_cost=2.0)
        assert m.directness_defined_u
        assert m.directness_defined_q
        assert m.directness_ratio_u == pytest.approx(1.0)
        assert m.directness_ratio_q == pytest.approx(1.0)
        assert m.directness_ratio_u >= 1.0 - 1e-12

    def test_detour_ratio_greater_than_one(self) -> None:
        u = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
        q = u.copy()
        m = compute_path_quality_from_trajectories(u, q, optimal_cost=3.0)
        assert m.directness_ratio_u is not None
        assert m.directness_ratio_u > 1.0

    def test_coincident_projected_endpoints(self) -> None:
        # Distinct U endpoints, identical Q endpoints.
        u = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
        q = np.array([[1.0, 1.0], [1.5, 1.0], [1.0, 1.0]])
        m = compute_path_quality_from_trajectories(u, q, optimal_cost=2.0)
        assert m.directness_defined_u
        assert not m.directness_defined_q
        assert m.directness_ratio_q is None
        assert m.path_length_q > 0.0
        assert m.endpoint_displacement_q == pytest.approx(0.0)

    def test_zero_edge_path(self) -> None:
        u = np.array([[0.5, 0.5]])
        q = np.array([[0.5, 0.5]])
        m = compute_path_quality_from_trajectories(u, q, optimal_cost=0.0)
        assert m.n_path_edges == 0
        assert not m.directness_defined_u
        assert m.directness_ratio_u is None
        assert m.cumulative_turning_q == pytest.approx(0.0)
        assert m.self_intersections_q == 0


class TestCumulativeTurning:
    def test_l_shape_pi_over_two(self) -> None:
        pts = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])
        assert cumulative_turning(pts) == pytest.approx(np.pi / 2)

    def test_collinear_zero(self) -> None:
        pts = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
        assert cumulative_turning(pts) == pytest.approx(0.0)

    def test_fewer_than_three_distinct(self) -> None:
        pts = np.array([[0.0, 0.0], [1.0, 0.0]])
        assert cumulative_turning(pts) == pytest.approx(0.0)
        pts_dup = np.array([[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]])
        assert cumulative_turning(pts_dup) == pytest.approx(0.0)

    def test_zero_length_segments_skipped(self) -> None:
        pts = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 0.0], [1.0, 1.0]])
        assert cumulative_turning(pts) == pytest.approx(np.pi / 2)


class TestSelfIntersections:
    def test_simple_cross(self) -> None:
        # X shape: (0,0)-(1,1) and (0,1)-(1,0) connected through midpoints.
        pts = np.array(
            [
                [0.0, 0.0],
                [1.0, 1.0],
                [1.0, 0.0],
                [0.0, 1.0],
                [0.0, 0.5],
            ]
        )
        # Better: classic bowtie / self-crossing polyline
        cross = np.array(
            [
                [0.0, 0.0],
                [1.0, 1.0],
                [1.0, 0.0],
                [0.0, 1.0],
            ]
        )
        assert count_self_intersections(cross) == 1

    def test_adjacent_only_no_count(self) -> None:
        pts = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
        assert count_self_intersections(pts) == 0

    def test_collinear_overlap_counts(self) -> None:
        # Segments 0-1 and 2-3 overlap on the x-axis (nonadjacent).
        pts = np.array(
            [
                [0.0, 0.0],
                [2.0, 0.0],
                [3.0, 1.0],
                [1.0, 0.0],
                [-1.0, 0.0],
            ]
        )
        # segments: (0,0)-(2,0), (2,0)-(3,1), (3,1)-(1,0), (1,0)-(-1,0)
        # first and last are nonadjacent and overlap on [0,2]x{0} ∩ [-1,1]x{0}
        assert segments_intersect(
            pts[0], pts[1], pts[3], pts[4]
        )
        assert count_self_intersections(pts) >= 1

    def test_repeated_projected_points(self) -> None:
        pts = np.array(
            [
                [0.0, 0.0],
                [1.0, 0.0],
                [1.0, 1.0],
                [0.0, 1.0],
                [0.0, 0.0],  # return to start — may touch first segment end
            ]
        )
        # Nonadjacent contact at start between last segment and first:
        # last (0,1)-(0,0) shares endpoint with first (0,0)-(1,0) — counts.
        n = count_self_intersections(pts)
        assert n >= 1


class TestNearRevisit:
    def test_exclusion_window(self) -> None:
        pts = np.array(
            [
                [0.0, 0.0],
                [1.0, 0.0],
                [2.0, 0.0],
                [3.0, 0.0],
                [0.05, 0.0],  # near start, index 4
            ]
        )
        d_loose, c_loose = near_revisit_metrics(
            pts, exclusion_steps=1, threshold=0.1
        )
        assert d_loose is not None
        assert d_loose == pytest.approx(0.05)
        assert c_loose >= 1

        d_strict, c_strict = near_revisit_metrics(
            pts, exclusion_steps=4, threshold=0.1
        )
        # |4-0|=4 is not > 4, so pair excluded; no other nonlocal pairs.
        assert d_strict is None
        assert c_strict == 0

    def test_threshold_sensitivity(self) -> None:
        pts = np.array(
            [
                [0.0, 0.0],
                [1.0, 0.0],
                [2.0, 0.0],
                [3.0, 0.0],
                [4.0, 0.0],
                [0.2, 0.0],
            ]
        )
        _, c_tight = near_revisit_metrics(pts, exclusion_steps=2, threshold=0.1)
        _, c_loose = near_revisit_metrics(pts, exclusion_steps=2, threshold=0.5)
        assert c_tight == 0
        assert c_loose >= 1

    def test_short_path(self) -> None:
        pts = np.array([[0.0, 0.0], [1.0, 0.0]])
        d, c = near_revisit_metrics(pts, exclusion_steps=4, threshold=0.05)
        assert d is None
        assert c == 0
