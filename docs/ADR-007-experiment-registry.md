# ADR-007 — Experiment Run Registry

**Status:** Accepted

## Context

Project plan M4 and the experiments reproducibility rules require every Monte
Carlo run to store config, seed, code revision, environment, and results.
IM-014/015 define *what* to run; IM-016 defines *where* and *how* that
provenance is persisted so pilot reproduction and later ablations remain
auditable.

## Decision

Runs are registered under `results/<run_id>/` via
`inequality_mechanisms.experiments.registry`.

### Layout

| Path | Role |
| --- | --- |
| `manifest.json` | Run id, status, seed, timestamps, embedded revision/environment snapshots, output index |
| `config.yaml` | Frozen validated `ExperimentConfig` |
| `revision.json` | Package version + best-effort git commit / dirty flag |
| `environment.json` | Interpreter, platform, tracked dependency versions |
| `outputs/` | Machine-readable artifacts registered by logical name |

### Lifecycle

Statuses: `created` → `running` → `completed` | `failed`.

- `create_run` refuses an existing directory (`FileExistsError`).
- A **completed** run is immutable: further writes raise `RunRegistryError`.
- Failed runs stay writable so partial trial records and failure reasons can
  be preserved (experiments rule: do not drop failed trials).

### Outputs

`write_json`, `write_text`, and `append_jsonl` write under `outputs/` and
update `manifest.outputs` (`name → relative path`). Binary artifacts already
on disk (e.g. PNG figures) are indexed with `register_output`. Analysis must
load these artifacts; it must not rewrite them on completed runs.

Pilot reproduction (IM-017 / ADR-008) registers at least: `trials`,
`summary`, `summary_table`, `graph_meta`, `expansions_raw`,
`expansions_normalized`, and `expansions_ratio`.

### Failure behavior

| Condition | Behavior |
| --- | --- |
| Duplicate `run_id` / existing directory | `FileExistsError` |
| Mutate completed run | `RunRegistryError` |
| Missing / malformed manifest | `FileNotFoundError` / `RunRegistryError` |
| Invalid `run_id` characters | `ValueError` |
| Git unavailable | Revision fields null + `git_error` string; run still created |

## Consequences

Benefits:

- one directory per run carries everything needed to reproduce analysis;
- completed results cannot be silently overwritten;
- trial JSONL can record successes and failures uniformly.

Costs:

- callers must choose stable output names;
- git capture is best-effort and may be absent in non-repo environments.
