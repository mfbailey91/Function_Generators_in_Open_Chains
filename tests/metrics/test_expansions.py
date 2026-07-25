"""Tests for expansion metrics (IM-017)."""

from __future__ import annotations

import math

import pytest

from inequality_mechanisms.metrics.expansions import (
    normalized_expansion,
    paired_log_ratio,
    paired_log_ratios_for_algorithm,
    summarize_trials,
    summary_table_csv,
    summary_table_rows,
)


class TestNormalizedExpansion:
    def test_nominal(self) -> None:
        assert normalized_expansion(25, 100) == pytest.approx(0.25)

    def test_rejects_nonpositive_denominator(self) -> None:
        with pytest.raises(ValueError, match="n_valid_nodes"):
            normalized_expansion(1, 0)

    def test_rejects_negative_numerator(self) -> None:
        with pytest.raises(ValueError, match="n_expanded"):
            normalized_expansion(-1, 10)


class TestPairedLogRatio:
    def test_equal_is_zero(self) -> None:
        assert paired_log_ratio(10, 10) == pytest.approx(0.0)

    def test_fourbar_smaller_is_negative(self) -> None:
        assert paired_log_ratio(1, math.e) == pytest.approx(-1.0)

    def test_rejects_nonpositive(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            paired_log_ratio(0, 5)
        with pytest.raises(ValueError, match="positive"):
            paired_log_ratio(5, 0)


def _row(
    *,
    trial: int,
    mechanism: str,
    algorithm: str,
    found: bool,
    n_expanded: int | None,
    n_valid: int = 100,
    rho: float | None = None,
    failure_reason: str | None = None,
) -> dict:
    return {
        "trial_index": trial,
        "mechanism": mechanism,
        "algorithm": algorithm,
        "found": found,
        "n_expanded": n_expanded,
        "n_valid_nodes": n_valid,
        "rho_expanded": rho,
        "failure_reason": failure_reason,
    }


class TestSummarizeTrials:
    def test_groups_and_paired_ratios(self) -> None:
        rows = [
            _row(
                trial=0,
                mechanism="gearbox",
                algorithm="dijkstra",
                found=True,
                n_expanded=100,
                rho=1.0,
            ),
            _row(
                trial=0,
                mechanism="fourbar",
                algorithm="dijkstra",
                found=True,
                n_expanded=10,
                rho=0.1,
            ),
            _row(
                trial=1,
                mechanism="gearbox",
                algorithm="dijkstra",
                found=False,
                n_expanded=3,
                failure_reason="unreachable",
            ),
            _row(
                trial=1,
                mechanism="fourbar",
                algorithm="dijkstra",
                found=True,
                n_expanded=5,
                rho=0.05,
            ),
        ]
        summary = summarize_trials(rows)
        assert summary["n_rows"] == 4
        assert summary["n_found"] == 3
        assert summary["n_unreachable"] == 1
        gb = summary["by_group"]["dijkstra|gearbox"]
        assert gb["n_found"] == 1
        assert gb["n_unreachable"] == 1
        assert gb["median_n_expanded"] == pytest.approx(100.0)
        ratios = summary["paired_log_ratios"]["dijkstra"]
        assert ratios["n_pairs"] == 1
        assert ratios["median"] == pytest.approx(math.log(0.1))

    def test_summary_table_csv_has_header(self) -> None:
        rows = [
            _row(
                trial=0,
                mechanism="gearbox",
                algorithm="astar",
                found=True,
                n_expanded=4,
                rho=0.04,
            ),
            _row(
                trial=0,
                mechanism="fourbar",
                algorithm="astar",
                found=True,
                n_expanded=2,
                rho=0.02,
            ),
        ]
        summary = summarize_trials(rows)
        table = summary_table_rows(summary)
        assert any(r["section"] == "group" for r in table)
        assert any(r["section"] == "paired_ratio" for r in table)
        csv_text = summary_table_csv(summary)
        assert csv_text.startswith("section,")
        assert "astar" in csv_text

    def test_paired_helper_skips_incomplete_pairs(self) -> None:
        rows = [
            _row(
                trial=0,
                mechanism="gearbox",
                algorithm="dijkstra",
                found=True,
                n_expanded=8,
            ),
        ]
        assert paired_log_ratios_for_algorithm(rows, algorithm="dijkstra") == []
