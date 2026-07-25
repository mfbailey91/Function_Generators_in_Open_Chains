"""Tests for paired task generation (IM-015)."""

from __future__ import annotations

import numpy as np
import pytest

from inequality_mechanisms.experiments import (
    default_snap_tol,
    discrete_preimage_candidates,
    generate_paired_tasks,
    nearest_grid_indices,
    select_preimage,
)
from inequality_mechanisms.graphs import ConstrainedInputGraph, PeriodicGrid2D
from inequality_mechanisms.mechanisms import IndependentFourBars, UnitGearbox
from inequality_mechanisms.spaces import OutputJointLimits

_CR = (1.0, 2.5, 2.0, 2.0)


def _paired_graphs(
    shape: tuple[int, int] = (20, 20),
) -> tuple[ConstrainedInputGraph, ConstrainedInputGraph]:
    grid = PeriodicGrid2D(shape, wrap=(True, True))
    limits = OutputJointLimits.box(lower=[1.05, 1.05], upper=[2.2, 2.2])
    gearbox = ConstrainedInputGraph(grid, UnitGearbox(dim=2), limits)
    fourbar = ConstrainedInputGraph(
        grid,
        IndependentFourBars.from_lengths([_CR, _CR], branch=1),
        limits,
    )
    return gearbox, fourbar


class TestNearestGridIndices:
    def test_exact_sample(self) -> None:
        grid = PeriodicGrid2D((8, 8), wrap=(True, True))
        u = grid.coordinates(3, 5)
        assert nearest_grid_indices(grid, u, periodic=(True, True)) == (3, 5)

    def test_periodic_seam(self) -> None:
        grid = PeriodicGrid2D((8, 8), wrap=(True, True))
        # Just below lo+span should wrap near index 0.
        lo, hi = grid.ranges[0]
        u0 = hi - 1e-9
        u1 = grid.coordinates(0, 0)[1]
        i0, i1 = nearest_grid_indices(grid, (u0, u1), periodic=(True, True))
        assert i0 in (0, 7)
        assert i1 == 0


class TestSelectPreimage:
    def test_lex_min(self) -> None:
        rng = np.random.default_rng(0)
        assert select_preimage([9, 2, 5], policy="lex_min_node_id", rng=rng) == 2

    def test_random_deterministic(self) -> None:
        a = select_preimage([1, 2, 3], policy="random", rng=np.random.default_rng(7))
        b = select_preimage([1, 2, 3], policy="random", rng=np.random.default_rng(7))
        assert a == b

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            select_preimage([], policy="lex_min_node_id", rng=np.random.default_rng(0))


class TestGeneratePairedTasks:
    def test_matched_outputs_and_stored_preimages(self) -> None:
        gb, fb = _paired_graphs()
        assert gb.valid_node_count >= 2
        assert fb.valid_node_count >= 2
        rng = np.random.default_rng(0)
        tasks = generate_paired_tasks(
            gb,
            fb,
            n_trials=5,
            rng=rng,
            min_output_separation=0.05,
            preimage_policy="lex_min_node_id",
        )
        assert len(tasks) == 5
        for task in tasks:
            assert task.q_start.shape == (2,)
            assert task.q_goal.shape == (2,)
            assert float(np.linalg.norm(task.q_goal - task.q_start)) >= 0.05
            assert gb.node_is_valid_id(task.gearbox.start_node_id)
            assert gb.node_is_valid_id(task.gearbox.goal_node_id)
            assert fb.node_is_valid_id(task.fourbar.start_node_id)
            assert fb.node_is_valid_id(task.fourbar.goal_node_id)
            assert task.fourbar.start_node_id != task.fourbar.goal_node_id
            # Gearbox identity: selected u equals q.
            assert task.gearbox.start_u == pytest.approx(tuple(task.q_start))
            assert task.gearbox.goal_u == pytest.approx(tuple(task.q_goal))
            # Four-bar selected nodes reproduce q within snap tol.
            tol = default_snap_tol(fb.grid)
            qs = fb.mechanism.input_to_output(task.fourbar.start_u)
            qg = fb.mechanism.input_to_output(task.fourbar.goal_u)
            assert float(np.linalg.norm(qs - task.q_start)) <= tol + 1e-12
            assert float(np.linalg.norm(qg - task.q_goal)) <= tol + 1e-12

    def test_deterministic_under_seed(self) -> None:
        gb, fb = _paired_graphs()
        a = generate_paired_tasks(gb, fb, n_trials=3, rng=np.random.default_rng(42))
        b = generate_paired_tasks(gb, fb, n_trials=3, rng=np.random.default_rng(42))
        assert [t.to_dict() for t in a] == [t.to_dict() for t in b]

    def test_lex_policy_picks_min_node(self) -> None:
        gb, fb = _paired_graphs((24, 24))
        tasks = generate_paired_tasks(
            gb,
            fb,
            n_trials=1,
            rng=np.random.default_rng(1),
            preimage_policy="lex_min_node_id",
        )
        task = tasks[0]
        start_cands = discrete_preimage_candidates(
            fb, task.q_start, snap_tol=default_snap_tol(fb.grid)
        )
        goal_cands = discrete_preimage_candidates(
            fb, task.q_goal, snap_tol=default_snap_tol(fb.grid)
        )
        assert task.fourbar.start_node_id == min(start_cands)
        # Goal may skip the start node when they collide.
        assert task.fourbar.goal_node_id in goal_cands

    def test_mismatched_limits_rejected(self) -> None:
        gb, fb = _paired_graphs()
        other_limits = OutputJointLimits.box(lower=[1.0, 1.0], upper=[2.0, 2.0])
        bad_fb = ConstrainedInputGraph(fb.grid, fb.mechanism, other_limits)
        with pytest.raises(ValueError, match="limits"):
            generate_paired_tasks(gb, bad_fb, n_trials=1, rng=np.random.default_rng(0))

    def test_exhaustion_raises(self) -> None:
        gb, fb = _paired_graphs((20, 20))
        assert gb.valid_node_count >= 2
        with pytest.raises(ValueError, match="failed to sample"):
            generate_paired_tasks(
                gb,
                fb,
                n_trials=50,
                rng=np.random.default_rng(0),
                min_output_separation=100.0,
                max_sample_attempts=20,
            )
