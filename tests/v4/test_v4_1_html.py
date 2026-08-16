"""V4-106 disposable atlas HTML (not the retained evidence package)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inequality_mechanisms.audits import v4_artifact_guard
from inequality_mechanisms.audits.v4_artifact_guard import (
    REPO_ROOT,
    V4_0_ALLOWED_PACKAGE,
    V4_1_ALLOWED_PACKAGE,
    ArtifactPathForbiddenError,
    prepare_v4_1_output_dir,
)
from inequality_mechanisms.experiments.v4.atlas_config import (
    DEFAULT_CONFIG_REL,
    NO_INFERENCE_STATEMENT,
    load_atlas_config,
)
from inequality_mechanisms.experiments.v4.controls import build_atlas_arms
from inequality_mechanisms.experiments.v4.geometry_atlas import evaluate_atlas_sample
from inequality_mechanisms.experiments.v4.shared_q_atlas import build_shared_q_bank
from inequality_mechanisms.visualization.v4.geometry_atlas import write_atlas_html


def test_disposable_html_is_non_inferential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(v4_artifact_guard, "REPO_ROOT", tmp_path)
    config = load_atlas_config(REPO_ROOT / DEFAULT_CONFIG_REL)
    arms = build_atlas_arms(config)
    cert = arms["fourbar"].branch.certificate
    bank = build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=(3, 3),
        inset_fraction=0.01,
    )
    rows = []
    for sample in bank.samples:
        for arm in arms.values():
            rows.append(
                evaluate_atlas_sample(arm, sample, config=config, revision="test")
            )
    output = tmp_path / "results" / "v4_review" / V4_1_ALLOWED_PACKAGE
    prepare_v4_1_output_dir(output)
    html_path = write_atlas_html(
        output,
        config=config,
        arms=arms,
        bank=bank,
        rows=rows,
        manifest={"git_revision": "test", "n_samples": len(bank.samples)},
    )
    text = html_path.read_text(encoding="utf-8")
    assert NO_INFERENCE_STATEMENT in text
    assert "null control" in text.lower()
    assert "winner" not in text.lower()
    assert (output / "figures").is_dir()
    forbidden = tmp_path / "results" / "v4_review" / V4_0_ALLOWED_PACKAGE
    with pytest.raises(ArtifactPathForbiddenError):
        prepare_v4_1_output_dir(forbidden)


def test_retained_atlas_package_is_non_inferential() -> None:
    root = REPO_ROOT / "results" / "v4_review" / V4_1_ALLOWED_PACKAGE
    html = (root / "index.html").read_text(encoding="utf-8")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert NO_INFERENCE_STATEMENT in html
    assert manifest["no_inference_statement"] == NO_INFERENCE_STATEMENT
    assert manifest["n_samples"] == 1089
    assert manifest["n_failed"] == 0
    assert (root / "geometry_samples.jsonl").is_file()
    assert (root / "rank_fields.json").is_file()
