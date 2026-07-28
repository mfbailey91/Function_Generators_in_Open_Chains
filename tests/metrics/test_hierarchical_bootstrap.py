"""Tests for hierarchical bootstrap and sample-size planning (S6-11–S6-16)."""

from __future__ import annotations

import math

import pytest

from inequality_mechanisms.metrics.hierarchical_bootstrap import (
    assert_not_task_level_iid,
    hierarchical_bootstrap_ci,
    mechanism_level_effects,
    paired_log_expansion_ratio,
    required_mechanism_count,
    sequential_precision_report,
)


def _rows() -> list[dict]:
    rows: list[dict] = []
    for m in range(3):
        for t in range(4):
            for side, n_exp in (("gearbox", 10 + m), ("fourbar", 20 + 2 * m + t)):
                rows.append(
                    {
                        "mechanism_id": f"m{m}",
                        "task_id": f"m{m}_t{t}",
                        "mechanism": side,
                        "algorithm": "dijkstra",
                        "cost_type": "output_euclidean",
                        "found": True,
                        "n_expanded": n_exp,
                    }
                )
    return rows


def test_paired_log_expansion_ratio() -> None:
    assert paired_log_expansion_ratio(0, 0) == pytest.approx(0.0)
    assert paired_log_expansion_ratio(math.e - 1.0, 0.0) == pytest.approx(1.0)


def test_mechanism_level_effects() -> None:
    summaries, exclusions = mechanism_level_effects(
        _rows(), min_accepted_tasks=2
    )
    assert not exclusions
    assert len(summaries) == 3
    assert all("task_effects" in s for s in summaries)


def test_hierarchical_bootstrap_seed_reproducible() -> None:
    summaries, _ = mechanism_level_effects(_rows(), min_accepted_tasks=1)
    a = hierarchical_bootstrap_ci(summaries, n_bootstrap=50, seed=7)
    b = hierarchical_bootstrap_ci(summaries, n_bootstrap=50, seed=7)
    assert a.estimate == pytest.approx(b.estimate)
    assert a.ci_low == pytest.approx(b.ci_low)
    assert a.ci_high == pytest.approx(b.ci_high)
    assert a.n_mechanisms == 3


def test_required_mechanism_count() -> None:
    assert required_mechanism_count(0.0, target_half_width=0.1) == 1
    m = required_mechanism_count(0.5, target_half_width=0.1)
    assert m == pytest.approx((1.96 * 0.5 / 0.1) ** 2, abs=1)


def test_sequential_precision_and_guard() -> None:
    summaries, _ = mechanism_level_effects(_rows(), min_accepted_tasks=1)
    report = sequential_precision_report(
        summaries,
        batch_size=1,
        target_ci_half_width=10.0,
        n_bootstrap=20,
        seed=0,
        min_mechanisms=1,
    )
    assert report["cluster_definition"] == "mechanism_pair"
    assert report["batches"]
    assert_not_task_level_iid(
        {"treats_tasks_as_iid": False, "cluster_definition": "mechanism_pair"}
    )
    with pytest.raises(AssertionError):
        assert_not_task_level_iid({"treats_tasks_as_iid": True})
