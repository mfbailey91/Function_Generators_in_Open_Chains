"""V4-206/V4-207 disposable V4.2 HTML and V4.1 freeze after tmp export."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits import v4_artifact_guard
from inequality_mechanisms.audits.v4_artifact_guard import (
    CANONICAL_REPO_ROOT,
    V4_1_ALLOWED_PACKAGE,
    V4_2_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    prepare_v4_1_output_dir,
    v4_1_atlas_package_digest,
)
from inequality_mechanisms.experiments.v4.atlas_config import NO_INFERENCE_STATEMENT
from inequality_mechanisms.experiments.v4.span_controlled_atlas import (
    generate_span_controlled_geometry_atlas,
)
from inequality_mechanisms.experiments.v4.span_controlled_atlas_config import (
    DEFAULT_CONFIG_REL,
    FROZEN_V3_6D_DIGEST,
    SPAN_175_STATUS,
)
from inequality_mechanisms.experiments.span_cases import generate_span_cases

DIGEST_LOCK = Path(__file__).resolve().parent / "data" / "frozen_v4_1_atlas_digests.json"


def test_v4_1_atlas_digest_lock_matches_committed_package() -> None:
    lock = json.loads(DIGEST_LOCK.read_text(encoding="utf-8"))
    assert lock["schema_version"] == "v4.1.frozen_v4_1_atlas_digests.v1"
    assert lock["package"] == V4_1_ALLOWED_PACKAGE
    sha, n_files = v4_1_atlas_package_digest()
    assert n_files == lock["n_files"]
    assert sha == lock["sha256"]


def test_tmp_v4_2_export_html_and_frozen_v4_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sha_before, n_before = v4_1_atlas_package_digest()
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_2_ALLOWED_PACKAGE
    path = generate_span_controlled_geometry_atlas(
        config_path=CANONICAL_REPO_ROOT / DEFAULT_CONFIG_REL,
        output=output,
        grid_shape=(3, 3),
    )
    assert path == output.resolve()
    html = (path / "index.html").read_text(encoding="utf-8")
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    assert NO_INFERENCE_STATEMENT in html
    assert SPAN_175_STATUS in html
    assert "null control" in html.lower()
    assert "winner" not in html.lower()
    assert "outperform" not in html.lower()
    assert manifest["no_inference_statement"] == NO_INFERENCE_STATEMENT
    assert manifest["v3_6d_digest"] == FROZEN_V3_6D_DIGEST
    assert manifest["n_cases"] == 17
    assert manifest["n_samples"] == 17 * 9
    assert manifest["n_rows"] == 17 * 9 * 3
    assert manifest["n_failed"] == 0
    assert manifest["grid"] == [3, 3]
    cases = generate_span_cases()
    for case in cases:
        case_page = path / "cases" / case.case_id / "index.html"
        assert case_page.is_file()
        text = case_page.read_text(encoding="utf-8")
        assert NO_INFERENCE_STATEMENT in text
        assert "null control" in text.lower()
        assert (path / "cases" / case.case_id / "figures").is_dir()
    dual = path / "cases" / "span_j1_145_j2_145" / "index.html"
    assert "core_span_sweep" in dual.read_text(encoding="utf-8")
    assert (path / "geometry_samples.jsonl").is_file()
    assert (path / "rank_fields.json").is_file()
    assert (path / "cases.json").is_file()
    forbidden = tmp_path / "results" / "v4_review" / V4_1_ALLOWED_PACKAGE
    with pytest.raises(ArtifactPathForbiddenError):
        prepare_v4_1_output_dir(forbidden)
    sha_after, n_after = v4_1_atlas_package_digest()
    assert n_after == n_before
    assert sha_after == sha_before
    lock = json.loads(DIGEST_LOCK.read_text(encoding="utf-8"))
    assert sha_after == lock["sha256"]
