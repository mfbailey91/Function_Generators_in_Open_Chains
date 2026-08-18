"""Build and serialize the V4.1 atlas package from frozen config."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from inequality_mechanisms.audits.v4_artifact_guard import (
    REPO_ROOT,
    assert_v4_1_output_allowed,
    prepare_v4_1_output_dir,
)
from inequality_mechanisms.experiments.v4.atlas_config import (
    NO_INFERENCE_STATEMENT,
    Planar2RGeometryAtlasConfig,
    load_atlas_config,
)
from inequality_mechanisms.experiments.v4.controls import AtlasArm, build_atlas_arms
from inequality_mechanisms.experiments.v4.geometry_atlas import (
    AtlasRow,
    assert_shared_pose,
    evaluate_atlas_sample,
    git_revision,
)
from inequality_mechanisms.experiments.v4.rank_fields import attribution_from_row
from inequality_mechanisms.experiments.v4.shared_q_atlas import (
    SharedQSampleBank,
    build_shared_q_bank,
)
from inequality_mechanisms.visualization.v4.geometry_atlas import write_atlas_html

REQUIRED_FILES = (
    "manifest.json",
    "resolved_config.json",
    "geometry_samples.jsonl",
    "rank_fields.json",
    "index.html",
)


def _git_revision() -> str | None:
    return git_revision()


def bank_from_arms(
    config: Planar2RGeometryAtlasConfig,
    arms: Mapping[str, AtlasArm],
) -> SharedQSampleBank:
    """Build the shared-Q bank from the certified four-bar output box."""
    cert = arms["fourbar"].branch.certificate
    return build_shared_q_bank(
        cert.output_lower,
        cert.output_upper,
        shape=config.grid.shape,
        inset_fraction=config.grid.inset_fraction,
    )


def collect_atlas_rows(
    config: Planar2RGeometryAtlasConfig,
    *,
    arms: Mapping[str, AtlasArm] | None = None,
    revision: str | None = None,
) -> tuple[SharedQSampleBank, dict[str, AtlasArm], list[AtlasRow]]:
    """Evaluate every (sample, arm) pair. Preserve typed failures as rows."""
    used_arms = build_atlas_arms(config) if arms is None else dict(arms)
    bank = bank_from_arms(config, used_arms)
    used_revision = _git_revision() if revision is None else revision
    rows: list[AtlasRow] = []
    for sample in bank.samples:
        by_mech: dict[str, AtlasRow] = {}
        for mechanism_id, arm in used_arms.items():
            row = evaluate_atlas_sample(
                arm, sample, config=config, revision=used_revision
            )
            by_mech[mechanism_id] = row
            rows.append(row)
        assert_shared_pose(by_mech)
    return bank, used_arms, rows


def write_atlas_package(
    config: Planar2RGeometryAtlasConfig,
    output: Path,
    *,
    rows: list[AtlasRow] | None = None,
    arms: Mapping[str, AtlasArm] | None = None,
    bank: SharedQSampleBank | None = None,
) -> Path:
    """Write the atlas package under the guarded V4.1 root."""
    resolved = assert_v4_1_output_allowed(output)
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved = prepare_v4_1_output_dir(resolved)
    figures = resolved / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    if rows is None or arms is None or bank is None:
        bank, arms, rows = collect_atlas_rows(config)
    jsonl_path = resolved / "geometry_samples.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.to_dict()) + "\n")
    rank_records = [attribution_from_row(row).to_dict() for row in rows]
    (resolved / "rank_fields.json").write_text(
        json.dumps(rank_records, indent=2), encoding="utf-8"
    )
    resolved_config = {
        "config": config.model_dump(),
        "config_digest": config.digest(),
        "q_box": {
            "lower": list(bank.q_lower),
            "upper": list(bank.q_upper),
            "inset": list(bank.inset),
            "inner_lower": list(bank.inner_lower),
            "inner_upper": list(bank.inner_upper),
        },
        "n_samples": len(bank.samples),
        "n_rows": len(rows),
        "span_matched_ratios": list(
            arms["span_matched_gearbox"].provenance.get("ratios", [])
        ),
    }
    (resolved / "resolved_config.json").write_text(
        json.dumps(resolved_config, indent=2), encoding="utf-8"
    )
    n_failed = sum(1 for row in rows if row.failure_code is not None)
    manifest = {
        "schema_version": config.schema_version,
        "package": "v4_1_planar2r_geometry_atlas",
        "git_revision": _git_revision(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "no_inference_statement": NO_INFERENCE_STATEMENT,
        "config_digest": config.digest(),
        "n_samples": len(bank.samples),
        "n_rows": len(rows),
        "n_failed": n_failed,
        "grid": list(config.grid.shape),
        "mechanisms": list(arms.keys()),
    }
    (resolved / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    write_atlas_html(
        resolved,
        config=config,
        arms=arms,
        bank=bank,
        rows=rows,
        manifest=manifest,
    )
    return resolved


def generate_planar2r_geometry_atlas(
    *,
    config_path: Path | str,
    output: Path | str | None = None,
) -> Path:
    """Load frozen config and write the atlas package."""
    config = load_atlas_config(config_path)
    target = Path(output) if output is not None else (REPO_ROOT / config.output_dir)
    assert_v4_1_output_allowed(target)
    return write_atlas_package(config, target)
