"""V4.2B Phase 9: dirty-source refusal and empty canonical-root policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from inequality_mechanisms.audits.v4_artifact_guard import (
    V4_2B_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    DirtySourceError,
    assert_v4_2b_output_root_empty,
    assert_v4_2b_source_clean,
    git_rev_parse_head,
)

STUB_SHA = "b" * 40


def test_nonempty_porcelain_raises_dirty_source_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard

    monkeypatch.setattr(
        v4_artifact_guard, "git_status_porcelain", lambda **kwargs: "?? leftover.txt\n"
    )
    with pytest.raises(DirtySourceError, match="dirty-source"):
        assert_v4_2b_source_clean()


def test_dirty_source_does_not_create_or_delete_output_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.experiments.v4 import span_controlled_corrective as mod

    output = tmp_path / "pkg"
    output.mkdir()
    sentinel = output / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")

    def _raise_dirty() -> str:
        raise DirtySourceError("Refusing dirty-source V4.2B generation")

    monkeypatch.setattr(mod, "_is_canonical_v4_2b_write", lambda path: True)
    monkeypatch.setattr(mod, "assert_v4_2b_source_clean", _raise_dirty)
    with pytest.raises(DirtySourceError, match="dirty-source"):
        mod._begin_v4_2b_write(output)
    assert sentinel.is_file()
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_empty_porcelain_returns_head(monkeypatch: pytest.MonkeyPatch) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard

    monkeypatch.setattr(v4_artifact_guard, "git_status_porcelain", lambda **kwargs: "")
    monkeypatch.setattr(
        v4_artifact_guard, "git_rev_parse_head", lambda **kwargs: STUB_SHA
    )
    assert assert_v4_2b_source_clean() == STUB_SHA


def test_nonempty_canonical_root_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard

    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_2B_ALLOWED_PACKAGE
    output.mkdir(parents=True)
    sentinel = output / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(ArtifactPathForbiddenError, match="non-empty"):
        assert_v4_2b_output_root_empty(output)
    assert sentinel.is_file()


def test_tmp_path_write_skips_dirty_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.experiments.v4 import span_controlled_corrective as mod

    monkeypatch.setattr(
        mod, "git_status_porcelain", lambda **kwargs: "?? leftover.txt\n"
    )
    output = tmp_path / "pkg"
    output.mkdir()
    (output / "stale.txt").write_text("old", encoding="utf-8")
    sha, dirty = mod._begin_v4_2b_write(output)
    assert dirty is True
    assert sha
    assert output.is_dir()
    assert not (output / "stale.txt").exists()


def test_canonical_write_records_clean_source_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inequality_mechanisms.audits import v4_artifact_guard
    from inequality_mechanisms.experiments.v4 import span_controlled_corrective as mod

    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    output = tmp_path / "results" / "v4_review" / V4_2B_ALLOWED_PACKAGE
    monkeypatch.setattr(mod, "canonical_v4_2b_retained_root", lambda: output.resolve())
    monkeypatch.setattr(mod, "assert_v4_2b_source_clean", lambda: STUB_SHA)
    sha, dirty = mod._begin_v4_2b_write(output.resolve())
    assert dirty is False
    assert sha == STUB_SHA
    assert output.resolve().is_dir()


def test_git_rev_parse_head_is_hex() -> None:
    sha = git_rev_parse_head()
    assert len(sha) == 40
    int(sha, 16)
