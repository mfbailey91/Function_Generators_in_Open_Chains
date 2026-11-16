"""V4-308: inventory helpers, verifier fail-closed checks, clean-source gate."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_3_artifact import (
    MANIFEST_NAME,
    V4_3ArtifactError,
    case_wrench_rel,
    files_digest,
    inventory_file,
    inventory_package_files,
    snapshot_predecessor_integrity,
    verify_v4_3_artifact,
)
from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_3_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    DirtySourceError,
    assert_v4_3_output_root_empty,
    assert_v4_3_source_clean,
)
from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
    MANIFEST_SCHEMA_VERSION,
    ROW_SCHEMA_VERSION,
)

STUB_SHA = "c" * 40


def _write_minimal_case(root: Path, case_id: str, *, n_rows: int = 3) -> None:
    case_dir = root / "cases" / case_id
    fig = case_dir / "figures"
    fig.mkdir(parents=True, exist_ok=True)
    for name in ("scalar.png", "polygons.png", "identity_scalar.png"):
        (fig / name).write_bytes(b"\x89PNG\r\n\x1a\n" + name.encode())
    rows = []
    for i in range(n_rows):
        mech = ("fourbar", "span_matched_gearbox", "identity_on_shared_q")[i % 3]
        rows.append(
            {
                "schema_version": ROW_SCHEMA_VERSION,
                "case_id": case_id,
                "q_sample_id": f"q_{i}",
                "mechanism_id": mech,
                "grid_index": [i, 0],
            }
        )
    wrench_path = case_dir / Path(case_wrench_rel(case_id)).name
    with gzip.open(wrench_path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    (case_dir / "summary.json").write_text("{}\n", encoding="utf-8")
    (case_dir / "index.html").write_text("<html></html>\n", encoding="utf-8")


def test_files_digest_is_order_independent() -> None:
    a = [{"path": "b.json", "sha256": "a" * 64}, {"path": "a.json", "sha256": "b" * 64}]
    b = list(reversed(a))
    assert files_digest(a) == files_digest(b)


def test_inventory_file_counts_gzip_rows(tmp_path: Path) -> None:
    rel = "cases/c1/wrench_samples.jsonl.gz"
    path = tmp_path / rel
    path.parent.mkdir(parents=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "schema_version": ROW_SCHEMA_VERSION,
                    "case_id": "c1",
                    "q_sample_id": "q0",
                    "mechanism_id": "fourbar",
                    "grid_index": [0, 0],
                }
            )
            + "\n"
        )
    record = inventory_file(tmp_path, rel)
    assert record["row_count"] == 1
    assert record["compression"] == "gzip"


def test_verify_missing_manifest_raises(tmp_path: Path) -> None:
    with pytest.raises(V4_3ArtifactError, match="missing manifest"):
        verify_v4_3_artifact(tmp_path)


def test_verify_rejects_manifest_self_inclusion(tmp_path: Path) -> None:
    from inequality_mechanisms.audits.v4_2b_artifact import expected_case_ids
    from inequality_mechanisms.experiments.v4.intrinsic_static_wrench_config import (
        FROZEN_V4_2B_N_GEOMETRY_ROWS,
    )

    root = tmp_path / "pkg"
    root.mkdir()
    for name in (
        "README.md",
        "config_resolved.json",
        "environment.json",
        "source_lock.json",
        "schema.json",
        "cases.json",
        "smoke_selection.json",
        "validation.json",
        "coverage.json",
        "predecessor_integrity.json",
        "methods.md",
        "biological_reference_pointer.md",
        "index.html",
    ):
        payload = "{}\n" if name.endswith(".json") else "x\n"
        (root / name).write_text(payload, encoding="utf-8")
    (root / "assets").mkdir()
    (root / "assets" / "atlas.css").write_text("body{}\n", encoding="utf-8")
    (root / "assets" / "atlas.js").write_text(";\n", encoding="utf-8")
    (root / "fixtures").mkdir()
    (root / "fixtures" / "analytic_expectations.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (root / "fixtures" / "analytic_results.json").write_text(
        "{}\n", encoding="utf-8"
    )
    case_ids = expected_case_ids()
    for cid in case_ids:
        _write_minimal_case(root, cid, n_rows=3)
    records = inventory_package_files(root, case_ids)
    records.append(
        {
            "path": MANIFEST_NAME,
            "sha256": "0" * 64,
            "byte_count": 1,
            "row_count": None,
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "media_type": "application/json",
            "compression": "none",
        }
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "package": V4_3_ALLOWED_PACKAGE,
        "manifest_inventory_rule": "exclude_self",
        "source_git_revision": STUB_SHA,
        "source_git_dirty": False,
        "config_digest": "d" * 64,
        "case_ids": list(case_ids),
        "n_rows": FROZEN_V4_2B_N_GEOMETRY_ROWS,
        "n_typed_failures": 0,
        "n_silent_drops": 0,
        "files": records,
        "files_digest": files_digest(records),
    }
    (root / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(V4_3ArtifactError, match="exclude itself"):
        verify_v4_3_artifact(root)


def test_nonempty_porcelain_raises_dirty_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard

    monkeypatch.setattr(
        v4_artifact_guard, "git_status_porcelain", lambda **kwargs: "?? leftover.txt\n"
    )
    with pytest.raises(DirtySourceError, match="dirty-source V4.3"):
        assert_v4_3_source_clean()


def test_empty_porcelain_returns_head(monkeypatch: pytest.MonkeyPatch) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard

    monkeypatch.setattr(v4_artifact_guard, "git_status_porcelain", lambda **kwargs: "")
    monkeypatch.setattr(
        v4_artifact_guard, "git_rev_parse_head", lambda **kwargs: STUB_SHA
    )
    assert assert_v4_3_source_clean() == STUB_SHA


def test_nonempty_canonical_root_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard

    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_3_ALLOWED_PACKAGE
    output.mkdir(parents=True)
    sentinel = output / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(ArtifactPathForbiddenError, match="non-empty"):
        assert_v4_3_output_root_empty(output)
    assert sentinel.is_file()


def test_snapshot_predecessor_integrity_includes_v4_2b() -> None:
    payload = snapshot_predecessor_integrity()
    assert payload["v4_2b_files_digest"]
    assert "v4_2b" in payload["packages"]
    assert payload["packages"]["v4_2b"]["n_git_tracked_files"] > 0


def test_subset_generator_writes_wrench_samples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard as guard
    from inequality_mechanisms.visualization.v4.intrinsic_static_wrench import (
        generate_intrinsic_static_wrench_package,
    )

    monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
    root = tmp_path / "results" / "v4_review" / V4_3_ALLOWED_PACKAGE
    package = generate_intrinsic_static_wrench_package(
        output=root,
        case_ids=["span_j1_145_j2_145"],
        require_full_corpus=False,
    )
    assert Path(package["output"]) == root.resolve()
    wrench = root / "cases" / "span_j1_145_j2_145" / "wrench_samples.jsonl.gz"
    assert wrench.is_file()
    assert (root / MANIFEST_NAME).is_file()
    assert (root / "fixtures" / "analytic_results.json").is_file()
    assert (root / "predecessor_integrity.json").is_file()
    assert (root / "environment.json").is_file()
    manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert MANIFEST_NAME not in {item["path"] for item in manifest["files"]}
    assert any(
        item["path"].endswith("wrench_samples.jsonl.gz")
        for item in manifest["files"]
    )
    assert package["n_rows"] == 33 * 33 * 3
    assert package["n_typed_failures"] == 0


def test_canonical_dirty_source_refuses_without_mkdir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from inequality_mechanisms.audits.v4_artifact_guard import (
        canonical_v4_3_retained_root,
    )
    from inequality_mechanisms.visualization.v4 import intrinsic_static_wrench as viz

    output = canonical_v4_3_retained_root()
    assert not output.exists() or not any(output.glob("**/*"))

    def _raise_dirty() -> str:
        raise DirtySourceError("Refusing dirty-source V4.3 generation")

    monkeypatch.setattr(viz, "assert_v4_3_source_clean", _raise_dirty)
    with pytest.raises(DirtySourceError, match="dirty-source"):
        viz.generate_intrinsic_static_wrench_package(
            output=output,
            case_ids=["span_j1_145_j2_145"],
            require_full_corpus=False,
        )
    assert not output.exists() or not any(output.glob("**/*"))
