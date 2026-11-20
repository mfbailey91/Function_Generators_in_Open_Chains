"""Frozen-source V4.4 smoke, independent scientific verification, and safe writes."""

from __future__ import annotations

import copy
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

from inequality_mechanisms.audits import v4_4_artifact as audit
from inequality_mechanisms.experiments.v4 import intrinsic_velocity as consumer


@pytest.fixture(scope="module")
def smoke_package(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, dict[str, Any]]:
    isolated = tmp_path_factory.mktemp("v44_smoke")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(audit, "REPO_ROOT", isolated)
        patch.setattr(audit, "git_status_porcelain", lambda: "")
        patch.setattr(audit, "git_rev_parse_head", lambda: "a" * 40)

        def forbid_wrench(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("V4.4 must not evaluate the wrench solver")

        from inequality_mechanisms.experiments.v4 import intrinsic_static_wrench

        patch.setattr(
            intrinsic_static_wrench, "static_wrench_from_snapshot", forbid_wrench
        )
        result = consumer.generate_velocity_smoke()
    return Path(result["output"]), result


def _rows(root: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (root / "velocity_samples.jsonl").read_text().splitlines()
    ]


def test_smoke_consumes_all_60_frozen_rows_and_verifies(
    smoke_package: tuple[Path, dict[str, Any]],
) -> None:
    root, generated = smoke_package
    verified = audit.verify_v4_4_artifact(root)
    assert verified == generated
    assert verified["n_rows"] == 60
    assert verified["n_pairs"] == 20
    assert verified["n_ik_requests"] == 1440
    assert verified["n_source_failures"] == verified["n_silent_drops"] == 0
    assert verified["physical_status_counts"]["bounded_rank_deficient"] > 0
    assert verified["ik_availability_counts"]["unavailable"] > 0
    for summary in verified["policy_summary"]:
        if summary["rate_policy"] == "uniform_scale":
            assert summary["commanded_exceeding_budget"] == 0
    rows = _rows(root)
    singular = next(row for row in rows if row["capability"]["rank"] == 1)
    exact = next(
        request for request in singular["ik_requests"] if request["policy"] == "exact"
    )
    assert exact["status"] == "unavailable"
    assert exact["failure_code"] == "transmission_rank_deficient"
    assert exact["failure_detail"]["rank"] == 1
    dls = next(
        request
        for request in singular["ik_requests"]
        if request["policy"] == "damped_least_squares"
    )
    assert dls["result"]["solver_status"] == "regularized"
    assert dls["result"]["physical_status"] == "bounded_rank_deficient"


def test_review_has_shared_equal_axes_and_explicit_policy_accounting(
    smoke_package: tuple[Path, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _ = smoke_package
    svg = ElementTree.parse(root / "review.svg")
    assert svg.getroot().tag.endswith("svg")
    import matplotlib.pyplot as plt

    figures = []
    close = plt.close

    def capture(figure: Any = None) -> None:
        if hasattr(figure, "axes"):
            figures.append(figure)
        close(figure)

    monkeypatch.setattr(plt, "close", capture)
    consumer._review_svg(_rows(root))
    axes = figures[-1].axes
    assert len(axes) == 24
    for first in range(0, len(axes), 3):
        reference = axes[first]
        for axis in axes[first : first + 3]:
            assert axis.get_xlim() == axis.get_ylim() == reference.get_xlim()
            assert axis.get_aspect() == 1.0
    page = (root / "index.html").read_text()
    assert "1,440 explicit inverse-policy requests" in page
    assert "not motor ratings" in page
    assert "report_only" in page and "uniform_scale" in page
    assert 'src="review.svg"' in page


@pytest.mark.parametrize(
    "mutation",
    [
        "support",
        "ray",
        "residual",
        "physical_status",
        "saturation",
        "solver_request",
        "numeric_string",
        "bool_integer",
        "unavailable_detail",
        "failure_detail",
        "named_direction",
        "target_mismatch",
    ],
)
def test_independent_reader_rejects_false_scientific_fields(
    smoke_package: tuple[Path, dict[str, Any]], mutation: str
) -> None:
    root, _ = smoke_package
    rank = 1 if mutation == "unavailable_detail" else 2
    row = copy.deepcopy(
        next(row for row in _rows(root) if row["capability"]["rank"] == rank)
    )
    result = next(r["result"] for r in row["ik_requests"] if r["result"] is not None)
    if mutation == "support":
        row["capability"]["directional_support"]["positive_x"] += 0.5
    elif mutation == "ray":
        row["capability"]["directional_ray_speed"]["positive_x"] += 0.5
    elif mutation == "residual":
        result["residual"] = [123.0, 456.0]
    elif mutation == "physical_status":
        result["physical_status"] = "bounded_rank_deficient"
    elif mutation == "saturation":
        result["requested_saturated_channels"] = [7]
    elif mutation == "numeric_string":
        row["capability"]["actuator_corners"][0][0] = "-1.0"
    elif mutation == "bool_integer":
        result["requested_feasible"] = int(result["requested_feasible"])
    elif mutation == "unavailable_detail":
        request = next(r for r in row["ik_requests"] if r["status"] == "unavailable")
        request["failure_detail"]["rank"] = 2
    elif mutation == "failure_detail":
        request = next(r for r in row["ik_requests"] if r["status"] == "available")
        request["failure_detail"] = {"rank": 2}
    elif mutation == "named_direction":
        row["capability"]["directions"]["tangential"][0] += 1e-10
    elif mutation == "target_mismatch":
        result["target_velocity"][0] += 1e-13
    else:
        result["requested_rates"][0] += 0.5
    with pytest.raises(audit.V4_4ArtifactError):
        audit.verify_velocity_record(row)


def test_rehashed_invalid_package_still_fails_scientific_verification(
    smoke_package: tuple[Path, dict[str, Any]], tmp_path: Path
) -> None:
    source, _ = smoke_package
    for name in audit.PACKAGE_FILES | {"manifest.json"}:
        (tmp_path / name).write_bytes((source / name).read_bytes())
    rows = _rows(tmp_path)
    rows[0]["capability"]["directional_ray_speed"]["positive_x"] = 999.0
    (tmp_path / "velocity_samples.jsonl").write_text(
        "".join(audit.strict_json(row, indent=None) + "\n" for row in rows)
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    for item in manifest["files"]:
        item["sha256"] = audit.sha256((tmp_path / item["path"]).read_bytes())
    manifest["files_digest"] = audit.inventory_digest(manifest["files"])
    (tmp_path / "manifest.json").write_text(audit.strict_json(manifest))
    with pytest.raises(audit.V4_4ArtifactError, match="ray speed"):
        audit.verify_v4_4_artifact(tmp_path)


@pytest.mark.parametrize("contents", ['{"x": NaN}', '{"x": 1e999}', '{"x": 1, "x": 2}'])
def test_transport_rejects_nonfinite_and_duplicate_fields(contents: str) -> None:
    with pytest.raises(audit.V4_4ArtifactError):
        audit.read_json_text(contents)


def test_configuration_is_validated_before_any_destination_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    path = tmp_path / "bad_config.json"
    config = audit.default_velocity_config()
    config["rate_limits"] = [2.0, 1.0]
    path.write_text(audit.strict_json(config))
    with pytest.raises(audit.V4_4ArtifactError, match="config"):
        consumer.generate_velocity_smoke(config_path=path)
    assert not (tmp_path / "results").exists()


def test_preflight_refuses_dirty_and_nonempty_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "git_status_porcelain", lambda: " M modified.py")
    with pytest.raises(audit.V4_4DirtySourceError):
        audit.preflight_velocity_smoke()
    assert not (tmp_path / "results").exists()
    target = tmp_path / audit.OUTPUT_REL
    target.mkdir(parents=True)
    sentinel = target / "retained.txt"
    sentinel.write_text("keep")
    with pytest.raises(audit.V4_4ArtifactError, match="nonempty"):
        audit.preflight_velocity_smoke()
    assert sentinel.read_text() == "keep"


def test_preflight_refuses_canonical_tree_and_symlink_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical = audit.CANONICAL_REPO_ROOT
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    for candidate in (
        canonical / "results/v4_review/v4_3_intrinsic_static_wrench_followup",
        canonical / "results/v4_review/v4_3_intrinsic_static_wrench_followup/new",
        canonical / "results/v4_review",
        canonical / audit.OUTPUT_REL,
        tmp_path / audit.OUTPUT_REL / "child",
        tmp_path / audit.OUTPUT_REL.parent,
    ):
        with pytest.raises(audit.V4_4ArtifactError):
            audit.preflight_velocity_smoke(candidate)
    (tmp_path / "results").symlink_to(canonical / "results", target_is_directory=True)
    with pytest.raises(audit.V4_4ArtifactError):
        audit.preflight_velocity_smoke()
    monkeypatch.setattr(audit, "REPO_ROOT", canonical / "isolated-looking-child")
    with pytest.raises(audit.V4_4ArtifactError, match="isolated"):
        audit.preflight_velocity_smoke()


def test_source_lock_failure_precedes_mkdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(audit, "git_status_porcelain", lambda: "")
    monkeypatch.setattr(audit, "git_rev_parse_head", lambda: "b" * 40)

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise audit.V4_4ArtifactError("source lock mismatch")

    monkeypatch.setattr(consumer, "assert_v4_2b_source_lock", fail)
    with pytest.raises(audit.V4_4ArtifactError, match="source lock"):
        consumer.generate_velocity_smoke()
    assert not (tmp_path / "results").exists()


def test_cli_exposes_no_dirty_overwrite_or_arbitrary_output_switch() -> None:
    assert set(inspect.signature(consumer.generate_velocity_smoke).parameters) == {
        "config_path"
    }
    completed = subprocess.run(
        [
            sys.executable,
            str(audit.CANONICAL_REPO_ROOT / "scripts/generate_v4_4_velocity_smoke.py"),
            "--help",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "--verify" in completed.stdout
    assert "--output" not in completed.stdout
    assert "--overwrite" not in completed.stdout
    assert "--allow-dirty" not in completed.stdout
