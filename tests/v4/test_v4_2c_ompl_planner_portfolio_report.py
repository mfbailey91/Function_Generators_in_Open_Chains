"""V4-238: question-grouped OMPL planner-portfolio report from retained files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits import v4_artifact_guard as guard
from inequality_mechanisms.audits.v4_artifact_guard import ArtifactPathForbiddenError
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
    DEFAULT_SMOKE_CONFIG_REL,
    load_ompl_portfolio_config,
)
from inequality_mechanisms.visualization.v4 import ompl_planner_portfolio as report_mod
from inequality_mechanisms.visualization.v4.ompl_planner_portfolio import (
    FAMILY_UNITS,
    INTERPRETATION_BOUNDARY,
    LEDE,
    PROHIBITED_CLAIMS,
    REPORT_SCHEMA,
    SECTION_SPECS,
    extract_row_view,
    href_targets,
    load_retained_stage,
    summarize_ompl_portfolio_stage,
    write_ompl_planner_portfolio_report,
)

CASE_ID = "span_j1_145_j2_145"
TASK_ID = "near_0"
MECH_A = "fourbar"
MECH_B = "gearbox"
RRTSTAR = "ompl_rrt_star"
BITSTAR = "ompl_bit_star"
FMT = "ompl_fmt"
KPIECE_U = "ompl_kpiece_u"
KPIECE_Q = "ompl_kpiece_q"
KPIECE_X = "ompl_kpiece_x"
PRM = "ompl_prm"
RRTCONNECT = "ompl_rrt_connect"
PDST = "ompl_pdst_u"


def _completed_worker(
    *,
    planner_id: str,
    digest: str,
    objective_cost: float,
    first_cost: float | None = None,
    checkpoints: list[dict] | None = None,
    occupancy: list[list[int]] | None = None,
    goal_id: str = "g0",
    vertices: int = 12,
) -> dict:
    family: dict = {}
    if occupancy is not None:
        family["kpiece_cell_occupancy"] = occupancy
    else:
        family["unavailable_reason"] = "kpiece_cell_stats_not_exposed_by_binding"
    extras: dict = {"family_metrics": family}
    if first_cost is not None:
        extras["first_exact_time_s"] = 0.1
        extras["first_exact_cost"] = first_cost
    result = {
        "status": STATUS_COMPLETED,
        "trajectory": {
            "states": [
                {"u": [0.0, 0.0], "q": [0.1, 0.0], "x": [0.2, 0.0]},
                {"u": [0.25, 0.1], "q": [0.2, 0.05], "x": [0.3, 0.1]},
            ]
        },
        "selected_goal_candidate": {"provenance": {"candidate_id": goal_id}},
        "objective_cost": objective_cost,
        "path_length_u": objective_cost,
        "path_length_q": objective_cost * 0.8,
        "path_length_x": objective_cost * 0.5,
        "planner_metrics": {
            "ompl": {
                "num_vertices": vertices,
                "num_edges": vertices * 2,
                "checkpoints": checkpoints or [],
            }
        },
        "provenance": {"extras": extras},
    }
    return {
        "status": STATUS_COMPLETED,
        "request_digest": digest,
        "planner_id": planner_id,
        "result": result,
    }


def _row(
    *, digest: str, planner_id: str, mechanism: str, worker: dict, role: str
) -> dict:
    return {
        "schema_version": ROW_SCHEMA,
        "request_digest": digest,
        "case_id": CASE_ID,
        "task_id": TASK_ID,
        "mechanism": mechanism,
        "planner_id": planner_id,
        "repetition": 0,
        "seed": 7,
        "role": role,
        "request": {"planner_id": planner_id},
        "worker": worker,
    }


def _write_stage(tmp_path: Path) -> Path:
    stage = tmp_path / guard.V4_2C_ALLOWED_OUTPUT_REL / "stage_a"
    (stage / "rows").mkdir(parents=True, exist_ok=True)
    (stage / "attempts").mkdir(parents=True, exist_ok=True)
    config = load_ompl_portfolio_config(DEFAULT_SMOKE_CONFIG_REL)
    write_atomic_json(stage / "resolved_config.json", config.model_dump(mode="json"))
    checkpoints = [
        {"checkpoint_s": 0.1, "ompl_exact_solution": True, "best_cost": 2.4},
        {"checkpoint_s": 0.5, "ompl_exact_solution": True, "best_cost": 1.1},
    ]
    matrix_rows: list[dict] = []
    n = 0

    def next_digest() -> str:
        nonlocal n
        n += 1
        return f"{n:064x}"

    def add_row(planner_id: str, mechanism: str, role: str, **kwargs: object) -> None:
        token = next_digest()
        record = _row(
            digest=token,
            planner_id=planner_id,
            mechanism=mechanism,
            role=role,
            worker=_completed_worker(planner_id=planner_id, digest=token, **kwargs),
        )
        write_atomic_json(stage / "rows" / f"{token}.json", record)
        matrix_rows.append(
            {
                "request_digest": token,
                "case_id": CASE_ID,
                "task_id": TASK_ID,
                "mechanism": mechanism,
                "planner_id": planner_id,
                "repetition": 0,
                "seed": 7,
                "role": role,
                "request": {"planner_id": planner_id},
            }
        )

    add_row(
        RRTSTAR,
        MECH_A,
        "primary",
        objective_cost=1.10,
        first_cost=2.40,
        checkpoints=checkpoints,
        vertices=20,
        goal_id="g0",
    )
    add_row(
        RRTSTAR,
        MECH_B,
        "primary",
        objective_cost=1.40,
        first_cost=2.80,
        checkpoints=checkpoints,
        vertices=18,
        goal_id="g1",
    )
    add_row(
        BITSTAR,
        MECH_A,
        "primary",
        objective_cost=1.20,
        first_cost=2.00,
        checkpoints=checkpoints,
    )
    add_row(
        FMT,
        MECH_A,
        "primary",
        objective_cost=1.50,
        first_cost=1.50,
        checkpoints=checkpoints,
    )
    add_row(
        KPIECE_U,
        MECH_A,
        "projection",
        objective_cost=1.30,
        occupancy=[[0, 1, 2], [3, 4, 5]],
        vertices=30,
    )
    add_row(KPIECE_Q, MECH_A, "projection", objective_cost=1.35, vertices=28)
    add_row(KPIECE_X, MECH_A, "projection", objective_cost=1.32, vertices=27)
    add_row(PRM, MECH_A, "control", objective_cost=1.05, vertices=40)
    add_row(RRTCONNECT, MECH_A, "control", objective_cost=1.08, vertices=9)

    pdst_digest = next_digest()
    pdst_row = _row(
        digest=pdst_digest,
        planner_id=PDST,
        mechanism=MECH_A,
        role="optional",
        worker={
            "status": STATUS_UNSUPPORTED_OPTIONAL,
            "request_digest": pdst_digest,
            "planner_id": PDST,
            "unavailable_reason": "optional_pdst_disabled",
            "result": None,
        },
    )
    write_atomic_json(stage / "attempts" / f"{pdst_digest}_01.json", pdst_row)
    matrix_rows.append(
        {
            "request_digest": pdst_digest,
            "case_id": CASE_ID,
            "task_id": TASK_ID,
            "mechanism": MECH_A,
            "planner_id": PDST,
            "repetition": 0,
            "seed": 7,
            "role": "optional",
            "request": {"planner_id": PDST},
        }
    )
    write_atomic_json(
        stage / "request_matrix.json",
        {
            "schema_version": MATRIX_SCHEMA,
            "config_digest": config.digest(),
            "mode": config.mode,
            "stage": config.stage_name(),
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
            "n_completed": len(list((stage / "rows").glob("*.json"))),
            "n_failed": 1,
            "n_skipped": 0,
            "completed_digests": [
                path.stem for path in sorted((stage / "rows").glob("*.json"))
            ],
            "failed_digests": [pdst_digest],
        },
    )
    write_atomic_json(
        stage / "capability_matrix.json",
        {
            "rows": [
                {
                    "feature_id": PDST,
                    "status": "unsupported",
                    "required": False,
                    "detail": "optional geometric PDST is nonblocking",
                }
            ]
        },
    )
    (stage / "notes.html").write_text(
        "<p>decoy html must not be read</p>", encoding="utf-8"
    )
    (stage / "rows" / "readme.txt").write_text("decoy", encoding="utf-8")
    return stage


@pytest.fixture
def synthetic_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    return _write_stage(tmp_path)


def test_report_reads_only_retained_json(
    synthetic_stage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    read_paths: list[Path] = []
    real = report_mod._read_json

    def wrapped(path: Path):
        read_paths.append(Path(path).resolve())
        return real(path)

    monkeypatch.setattr(report_mod, "_read_json", wrapped)
    write_ompl_planner_portfolio_report(synthetic_stage)
    assert read_paths
    for path in read_paths:
        assert path.suffix == ".json"
        assert path.name != "notes.html"
        assert path.name != "readme.txt"
        assert path.name != "index.html"


def test_plotted_rows_link_task_mechanism_planner_repetition(
    synthetic_stage: Path,
) -> None:
    payload = write_ompl_planner_portfolio_report(synthetic_stage)
    html = Path(payload["index_path"]).read_text(encoding="utf-8")
    summary = json.loads(Path(payload["summary_path"]).read_text(encoding="utf-8"))
    assert 'id="lede"' in html
    assert html.find('id="lede"') < html.find("<h1>")
    assert LEDE in html
    for figure in summary["figures"]:
        for digest in figure["row_digests"]:
            assert digest in html
    assert "rep 0" in html
    assert RRTSTAR in html
    assert MECH_A in html
    assert MECH_B in html
    assert TASK_ID in html
    assert CASE_ID in html
    assert "../rows/" in html


def test_unsupported_pdst_remains_visible(synthetic_stage: Path) -> None:
    payload = write_ompl_planner_portfolio_report(synthetic_stage)
    html = Path(payload["index_path"]).read_text(encoding="utf-8")
    summary = json.loads(Path(payload["summary_path"]).read_text(encoding="utf-8"))
    assert PDST in html
    assert "unsupported" in html.lower()
    ids = [item["planner_id"] for item in summary["unsupported_planners"]]
    assert PDST in ids
    assert FAMILY_UNITS[PDST] in html


def test_family_units_are_labeled(synthetic_stage: Path) -> None:
    payload = write_ompl_planner_portfolio_report(synthetic_stage)
    html = Path(payload["index_path"]).read_text(encoding="utf-8")
    for planner_id, unit in FAMILY_UNITS.items():
        assert planner_id in html
        assert unit in html


def test_href_integrity_and_deterministic_summary(synthetic_stage: Path) -> None:
    first = write_ompl_planner_portfolio_report(synthetic_stage)
    index = Path(first["index_path"])
    missing = [path for path in href_targets(index) if not path.exists()]
    assert missing == []
    summary_one = Path(first["summary_path"]).read_bytes()
    html_one = index.read_text(encoding="utf-8")
    second = write_ompl_planner_portfolio_report(synthetic_stage)
    assert Path(second["summary_path"]).read_bytes() == summary_one
    assert Path(second["index_path"]).read_text(encoding="utf-8") == html_one
    loaded = json.loads(summary_one)
    again = summarize_ompl_portfolio_stage(synthetic_stage)
    again["figures"] = loaded["figures"]
    assert json.loads(json.dumps(again, sort_keys=True)) == json.loads(
        json.dumps(loaded, sort_keys=True)
    )
    assert loaded["schema_version"] == REPORT_SCHEMA
    for section_id, _title in SECTION_SPECS:
        assert f'id="{section_id}"' in html_one


def test_lede_boundary_nonclaims_and_no_winner_table(synthetic_stage: Path) -> None:
    payload = write_ompl_planner_portfolio_report(synthetic_stage)
    html = Path(payload["index_path"]).read_text(encoding="utf-8")
    summary = json.loads(Path(payload["summary_path"]).read_text(encoding="utf-8"))
    assert LEDE in html
    assert INTERPRETATION_BOUNDARY in html
    for claim in PROHIBITED_CLAIMS:
        assert claim in html
    assert "winner" not in html.lower()
    assert "outperform" not in html.lower()
    assert "estimand" not in html.lower()
    assert summary["lede"] == LEDE
    assert summary["interpretation_boundary"] == INTERPRETATION_BOUNDARY
    assert summary["u_authoritative"] is True
    assert summary["free_space_direct_reference_available"] is True
    assert summary["descriptive_not_ranking"] is True
    row_path = sorted((synthetic_stage / "rows").glob("*.json"))[0]
    view = extract_row_view(json.loads(row_path.read_text(encoding="utf-8")))
    assert view["case_id"] == CASE_ID
    loaded = load_retained_stage(synthetic_stage)
    assert loaded["rows"]
    assert any(row.get("planner_id") == PDST for row in loaded["attempts"])


def test_write_outside_v4_2c_root_is_rejected(
    synthetic_stage: Path, tmp_path: Path
) -> None:
    with pytest.raises(ArtifactPathForbiddenError):
        write_ompl_planner_portfolio_report(
            synthetic_stage, output_dir=tmp_path / "elsewhere"
        )
    frozen = tmp_path / "results" / "v4_review" / guard.V4_2B_ALLOWED_PACKAGE
    frozen.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ArtifactPathForbiddenError):
        write_ompl_planner_portfolio_report(synthetic_stage, output_dir=frozen)
