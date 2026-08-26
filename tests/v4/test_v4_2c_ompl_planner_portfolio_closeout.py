"""V4-239: package extracts, calibration lock, and artifact verifier."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits import v4_artifact_guard as guard
from inequality_mechanisms.audits.v4_2c_artifact import (
    FROZEN_STAGE_ROWS,
    V4_2CArtifactError,
    package_ompl_planner_portfolio,
    verify_v4_2c_artifact,
    write_calibration_selection,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    ArtifactPathForbiddenError,
    DirtySourceError,
)
from inequality_mechanisms.benchmarks.ompl_process_worker_v4_2c import (
    STATUS_COMPLETED,
    STATUS_UNSUPPORTED_OPTIONAL,
    write_atomic_json,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio import (
    MATRIX_SCHEMA,
    PROGRESS_SCHEMA,
    ROW_SCHEMA,
)
from inequality_mechanisms.experiments.v4.ompl_planner_portfolio_config import (
    CALIBRATION_SELECTION_SCHEMA,
    DEFAULT_CALIBRATION_CONFIG_REL,
    DEFAULT_SMOKE_CONFIG_REL,
    load_ompl_portfolio_config,
)

PDST = "ompl_pdst_u"


def _row(*, digest: str, planner_id: str, mechanism: str, status: str) -> dict:
    worker: dict = {
        "status": status,
        "request_digest": digest,
        "planner_id": planner_id,
        "result": None,
    }
    if status == STATUS_COMPLETED:
        worker["result"] = {
            "status": STATUS_COMPLETED,
            "objective_cost": 1.0,
            "path_length_u": 1.0,
            "planner_metrics": {
                "ompl": {
                    "num_vertices": 4,
                    "num_edges": 3,
                    "checkpoints": [
                        {
                            "checkpoint_s": 0.1,
                            "ompl_exact_solution": True,
                            "best_cost": 1.0,
                        }
                    ],
                }
            },
            "selected_goal_candidate": {"provenance": {"candidate_id": "g0"}},
            "trajectory": {
                "states": [{"u": [0.0, 0.0], "q": [0.0, 0.0], "x": [0.0, 0.0]}]
            },
            "provenance": {"extras": {"family_metrics": {}}},
        }
    else:
        worker["unavailable_reason"] = "optional_pdst_disabled"
    return {
        "schema_version": ROW_SCHEMA,
        "request_digest": digest,
        "case_id": "span_j1_145_j2_145",
        "task_id": "near_0",
        "mechanism": mechanism,
        "planner_id": planner_id,
        "repetition": 0,
        "seed": 7,
        "role": "optional" if planner_id == PDST else "primary",
        "request": {"planner_id": planner_id},
        "worker": worker,
    }


def _write_stage(
    root: Path,
    *,
    name: str,
    config_rel: Path,
    extra_rows: list[dict],
) -> None:
    stage = root / name
    (stage / "rows").mkdir(parents=True, exist_ok=True)
    (stage / "attempts").mkdir(parents=True, exist_ok=True)
    config = load_ompl_portfolio_config(config_rel)
    write_atomic_json(stage / "resolved_config.json", config.model_dump(mode="json"))
    matrix_rows = []
    for index, record in enumerate(extra_rows):
        digest = str(record["request_digest"])
        dest_dir = stage / (
            "attempts" if record["worker"]["status"] != STATUS_COMPLETED else "rows"
        )
        suffix = (
            f"_{index:02d}.json" if dest_dir.name == "attempts" else f"{digest}.json"
        )
        write_atomic_json(dest_dir / suffix, record)
        matrix_rows.append(
            {
                "request_digest": digest,
                "case_id": record["case_id"],
                "task_id": record["task_id"],
                "mechanism": record["mechanism"],
                "planner_id": record["planner_id"],
                "repetition": 0,
                "seed": 7,
                "role": record["role"],
                "request": record["request"],
            }
        )
    write_atomic_json(
        stage / "request_matrix.json",
        {
            "schema_version": MATRIX_SCHEMA,
            "config_digest": config.digest(),
            "mode": config.mode,
            "stage": name,
            "n_rows": len(matrix_rows),
            "rows": matrix_rows,
        },
    )
    write_atomic_json(
        stage / "progress.json",
        {
            "schema_version": PROGRESS_SCHEMA,
            "config_digest": config.digest(),
            "n_rows": len(matrix_rows),
            "n_completed": sum(
                1 for row in extra_rows if row["worker"]["status"] == STATUS_COMPLETED
            ),
            "n_failed": sum(
                1 for row in extra_rows if row["worker"]["status"] != STATUS_COMPLETED
            ),
            "n_skipped": 0,
        },
    )


@pytest.fixture
def package_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    root = tmp_path / guard.V4_2C_ALLOWED_OUTPUT_REL
    root.mkdir(parents=True)
    completed = _row(
        digest="1" * 64,
        planner_id="ompl_rrt_star",
        mechanism="fourbar",
        status=STATUS_COMPLETED,
    )
    pdst = _row(
        digest="2" * 64,
        planner_id=PDST,
        mechanism="fourbar",
        status=STATUS_UNSUPPORTED_OPTIONAL,
    )
    _write_stage(
        root,
        name="stage_a",
        config_rel=DEFAULT_SMOKE_CONFIG_REL,
        extra_rows=[completed],
    )
    _write_stage(
        root,
        name="stage_b",
        config_rel=DEFAULT_CALIBRATION_CONFIG_REL,
        extra_rows=[completed],
    )
    _write_stage(
        root,
        name="stage_c",
        config_rel=DEFAULT_SMOKE_CONFIG_REL,
        extra_rows=[completed, pdst],
    )
    cal = load_ompl_portfolio_config(DEFAULT_CALIBRATION_CONFIG_REL)
    write_calibration_selection(
        root / "stage_b" / "calibration_selection.json",
        calibration_config_digest=cal.digest(),
    )
    return root


def test_v4_2c_closeout_keeps_v4_3_unauthorized() -> None:
    text = (
        CANONICAL_REPO_ROOT / "docs" / "software" / "planning" / "ACTIVE_SPRINT.md"
    ).read_text(encoding="utf-8")
    assert "**Code authorization:** none." in text
    assert "Sprint V4.2C is **completed**" in text
    assert "Sprint V4.3 remains **drafted / blocked**" in text
    assert "Do not implement V4.3 / V4-300+" in text


def test_package_and_verify_synthetic_root(package_root: Path) -> None:
    summary = package_ompl_planner_portfolio(
        package_root,
        source_git_revision="a" * 40,
        allow_dirty=True,
    )
    assert (package_root / "manifest.json").is_file()
    assert (package_root / "index.html").is_file()
    assert (package_root / "calibration" / "selection.json").is_file()
    assert (package_root / "audit" / "failures.jsonl.gz").is_file()
    html = (package_root / "index.html").read_text(encoding="utf-8")
    assert PDST in html
    assert "winner" not in html.lower()
    checked = verify_v4_2c_artifact(
        package_root,
        require_frozen_matrix=False,
        require_predecessor=False,
    )
    assert checked["files_digest"] == summary["files_digest"]
    assert checked["n_files"] == summary["n_files"]


def test_frozen_matrix_gate_rejects_synthetic_counts(package_root: Path) -> None:
    package_ompl_planner_portfolio(
        package_root,
        source_git_revision="a" * 40,
        allow_dirty=True,
    )
    with pytest.raises(V4_2CArtifactError, match="n_rows_stage_a"):
        verify_v4_2c_artifact(
            package_root,
            require_frozen_matrix=True,
            require_predecessor=False,
        )
    assert FROZEN_STAGE_ROWS["stage_a"] == 32


def test_calibration_selection_and_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    digest = load_ompl_portfolio_config(DEFAULT_CALIBRATION_CONFIG_REL).digest()
    path = (
        tmp_path
        / guard.V4_2C_ALLOWED_OUTPUT_REL
        / "stage_b"
        / "calibration_selection.json"
    )
    written = write_calibration_selection(path, calibration_config_digest=digest)
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["schema_version"] == CALIBRATION_SELECTION_SCHEMA
    assert payload["calibration_config_digest"] == digest
    frozen = tmp_path / "results" / "v4_review" / guard.V4_2B_ALLOWED_PACKAGE / "x.json"
    with pytest.raises(ArtifactPathForbiddenError):
        write_calibration_selection(frozen, calibration_config_digest=digest)


def test_packaging_refuses_non_package_leftovers(
    package_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "inequality_mechanisms.audits.v4_2c_artifact.git_status_porcelain",
        lambda: "?? v4_2c_ompl_planner_portfolio_planning_bundle/\n",
    )
    monkeypatch.setattr(
        "inequality_mechanisms.audits.v4_2c_artifact.git_rev_parse_head",
        lambda: "b" * 40,
    )
    with pytest.raises(DirtySourceError, match="planning_bundle"):
        package_ompl_planner_portfolio(package_root)
