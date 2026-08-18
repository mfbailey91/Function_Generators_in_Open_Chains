"""V3.6D span-corpus export: registry, cases, characterization, manifest."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inequality_mechanisms.audits.v3_span_wrench_guard import (
    V3_6D_ALLOWED_OUTPUT_REL,
    assert_v3_6d_output_allowed,
    prepare_v3_6d_output_dir,
)
from inequality_mechanisms.experiments.span_cases import (
    generate_span_cases,
    realize_supported_cases,
)
from inequality_mechanisms.experiments.span_wrench_config import (
    DEFAULT_CONFIG_REL,
    load_span_wrench_program_config,
)
from inequality_mechanisms.mechanisms.span_registry import (
    SpanRegistry,
    build_span_registry,
)
from inequality_mechanisms.mechanisms.span_synthesis import CanonicalSynthesisResult

SCHEMA_VERSION = "v3.6d.span_corpus.v1"


def _git_revision() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, payload: Any) -> str:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    data = text.encode("utf-8")
    path.write_bytes(data)
    return _sha256_bytes(data)


def _mechanism_card(row: CanonicalSynthesisResult) -> str:
    ranges = row.range_definition
    lines = [
        f"# Span {row.target_span_deg:.0f}°",
        "",
        f"- status: `{row.status}`",
        f"- certificate: `{row.certificate_profile_name}`",
        f"- seed: `{row.seed}`",
    ]
    if row.lengths is not None:
        a, b, c, d = row.lengths
        lines.append(f"- lengths (a,b,c,d): `{a:.6f}, {b:.6f}, {c:.6f}, {d:.6f}`")
    if ranges is not None:
        lines.extend(
            [
                f"- classification: `{ranges.classification}`",
                f"- usable span: `{ranges.usable_span_deg:.4f} deg`",
                f"- usable Q (centered rad): `{list(ranges.usable_interval_rad)}`",
                f"- mechanical Q (centered rad): `{list(ranges.mechanical_interval_rad)}`",
            ]
        )
    if row.u_interval_rad is not None:
        lines.append(f"- U interval (rad): `{list(row.u_interval_rad)}`")
    if row.min_abs_dq_du is not None:
        lines.extend(
            [
                f"- |dq/du| min/mean/max/std: "
                f"`{row.min_abs_dq_du:.6g}` / `{row.mean_abs_dq_du:.6g}` / "
                f"`{row.max_abs_dq_du:.6g}` / `{row.std_abs_dq_du:.6g}`",
                f"- endpoint |dq/du|: `{list(row.endpoint_gains)}`",
                f"- worst certified margin: `{row.worst_certified_margin:.6g}`",
                f"- span error: `{row.span_error_deg:.4f} deg`",
            ]
        )
    if row.failure_reason:
        lines.append(f"- failure: {row.failure_reason}")
    lines.append("")
    return "\n".join(lines)


def _descriptor_rows(registry: SpanRegistry) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in registry.records:
        item: dict[str, Any] = record.to_dict()
        item["legacy_regression"] = False
        rows.append(item)
    return rows


def export_span_corpus(
    *,
    config_path: Path | None = None,
    output: Path | None = None,
) -> Path:
    """Write the V3.6D corpus under the guarded output root."""
    config_rel = Path(config_path) if config_path is not None else DEFAULT_CONFIG_REL
    config = load_span_wrench_program_config(config_rel)
    target = (
        Path(output)
        if output is not None
        else V3_6D_ALLOWED_OUTPUT_REL
    )
    root = prepare_v3_6d_output_dir(assert_v3_6d_output_allowed(target))
    registry = build_span_registry(seed=int(config.synthesis.deterministic_seed))
    cases = generate_span_cases()
    realized = realize_supported_cases(registry)
    checksums: dict[str, str] = {}

    checksums["registry.json"] = _write_json(root / "registry.json", registry.to_dict())
    checksums["cases.json"] = _write_json(
        root / "cases.json",
        {"count": len(cases), "cases": [row.to_dict() for row in cases]},
    )
    checksums["realized_cases.json"] = _write_json(
        root / "realized_cases.json",
        {"count": len(realized), "cases": [row.to_dict() for row in realized]},
    )
    descriptors = _descriptor_rows(registry)
    checksums["descriptors.json"] = _write_json(root / "descriptors.json", descriptors)

    csv_path = root / "descriptors.csv"
    fieldnames = [
        "target_span_deg",
        "status",
        "certificate_profile_name",
        "usable_span_deg",
        "span_error_deg",
        "min_abs_dq_du",
        "mean_abs_dq_du",
        "max_abs_dq_du",
        "std_abs_dq_du",
        "worst_certified_margin",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in registry.records:
            usable = (
                None
                if record.range_definition is None
                else record.range_definition.usable_span_deg
            )
            writer.writerow(
                {
                    "target_span_deg": record.target_span_deg,
                    "status": record.status,
                    "certificate_profile_name": record.certificate_profile_name,
                    "usable_span_deg": usable,
                    "span_error_deg": record.span_error_deg,
                    "min_abs_dq_du": record.min_abs_dq_du,
                    "mean_abs_dq_du": record.mean_abs_dq_du,
                    "max_abs_dq_du": record.max_abs_dq_du,
                    "std_abs_dq_du": record.std_abs_dq_du,
                    "worst_certified_margin": record.worst_certified_margin,
                }
            )
    checksums["descriptors.csv"] = _sha256_bytes(csv_path.read_bytes())

    cards_dir = root / "mechanism_cards"
    cards_dir.mkdir(exist_ok=True)
    index_lines = ["# V3.6D canonical span cards", ""]
    for record in registry.records:
        name = f"span_{int(record.target_span_deg):03d}.md"
        text = _mechanism_card(record)
        (cards_dir / name).write_text(text, encoding="utf-8")
        checksums[f"mechanism_cards/{name}"] = _sha256_bytes(text.encode("utf-8"))
        index_lines.append(f"- [{name}]({name}) — `{record.status}`")
    index_text = "\n".join(index_lines) + "\n"
    (cards_dir / "index.md").write_text(index_text, encoding="utf-8")
    checksums["mechanism_cards/index.md"] = _sha256_bytes(index_text.encode("utf-8"))

    comparison_lines = [
        "# Canonical span comparison",
        "",
        "| span_deg | status | usable_deg | error_deg | min|dq/du| | worst_margin |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for record in registry.records:
        usable = (
            ""
            if record.range_definition is None
            else f"{record.range_definition.usable_span_deg:.4f}"
        )
        err = "" if record.span_error_deg is None else f"{record.span_error_deg:.4f}"
        ming = "" if record.min_abs_dq_du is None else f"{record.min_abs_dq_du:.4g}"
        worst = (
            ""
            if record.worst_certified_margin is None
            else f"{record.worst_certified_margin:.4g}"
        )
        comparison_lines.append(
            f"| {record.target_span_deg:.0f} | {record.status} | {usable} | {err} | {ming} | {worst} |"
        )
    comparison = "\n".join(comparison_lines) + "\n"
    (root / "comparison.md").write_text(comparison, encoding="utf-8")
    checksums["comparison.md"] = _sha256_bytes(comparison.encode("utf-8"))

    config_hash = _sha256_bytes(config_rel.read_bytes())
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "program_id": config.program_id,
        "git_revision": _git_revision(),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config_path": config_rel.as_posix(),
        "config_sha256": config_hash,
        "registry_sha256": registry.sha256,
        "seed": config.synthesis.deterministic_seed,
        "certificate_profile": registry.certificate_profile,
        "n_cases": len(cases),
        "n_realized_cases": len(realized),
        "checksums": checksums,
        "statement": "canonical span corpus; no planner or wrench inference.",
    }
    _write_json(root / "manifest.json", manifest)
    return root
