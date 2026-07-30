# Version 1 baseline freeze

**Status:** Frozen for Version 2 rearchitecture  
**Architecture:** Version 1 (ADR-001 input-state identity)  
**Freeze date:** 2026-07-29

## Reviewed revision

| Field | Value |
| --- | --- |
| Branch | `v2-rearchitecture` |
| Commit | `b25f9a8b7780ca8c7ad6293c56f131e9c63ed56c` |
| Subject | Clean up docs redirects, duplicate figures, and V1 backlog. |
| Preferred tag | `v1-input-state-baseline` (created after golden fixtures land on this freeze lineage) |

Version 2 must preserve Version 1 golden regressions relative to this lineage.
Later commits may add Version 2 code beside Version 1; they must not reinterpret
these fixtures.

## Accepted ADRs (Version 1 authority)

- ADR-001 — Search in Input Configuration Space
- ADR-002 — Mechanism Protocol
- ADR-003 — Planar Four-Bar Conventions
- ADR-004 — Shared Output Limits and Edge Validation
- ADR-005 — Search Expansion Semantics
- ADR-006 — Experiment Configuration Schema
- ADR-007 — Experiment Run Registry
- ADR-008 — Pilot Reproduction Outputs
- ADR-009 — Crank-Rocker Population
- ADR-010 — Equal Valid-Node Mode
- ADR-011 — Output Configuration Space Semantics
- ADR-012 — Equivalent-Gain Gearbox Matching
- ADR-013 — Production Graph Resolution Selection

Version 2 ADRs (014–016) apply only when `architecture_version: 2` is declared.

## Representative configurations

| Config | Role |
| --- | --- |
| `configs/pilot.v1.yaml` | Primary Monte Carlo pilot |
| `configs/pilot.equal_nodes.v1.yaml` | Equal valid-node mode |
| `configs/pilot.cost_uniform.v1.yaml` | Uniform cost ablation |
| `configs/pilot.cost_input.v1.yaml` | Input Euclidean cost ablation |
| `configs/sprint4.smoke.v1.yaml` | Sprint Four smoke |
| `configs/sprint5.smoke.v1.yaml` | Sprint Five smoke |
| `configs/sprint6.equivalence.smoke.v1.yaml` | Sprint Six equivalence smoke |
| `tests/golden_v1/data/fixture_v1_config.yaml` | Small serialization fixture |

## Golden fixtures

| Fixture | Path |
| --- | --- |
| Unit gearbox open grid | `tests/golden_v1/data/fixture_unit_gearbox.json` |
| Four-bar input-state graph | `tests/golden_v1/data/fixture_fourbar.json` |
| Config round trip | `tests/golden_v1/data/fixture_v1_config.yaml` |

These encode expected paths, costs, and expansion counters for deterministic
search. They are the regression oracle Version 2 refactors must keep green.

## Reproduction commands

Deterministic tests (required for any Version 2 change touching search/graphs):

```bash
pytest tests/golden_v1
pytest tests/search tests/graphs tests/spaces
pytest
ruff check .
ruff format --check .
mypy src
```

Pilot / sprint smoke entry points (Version 1 loaders only):

```bash
python -m inequality_mechanisms.experiments.pilot --config configs/pilot.v1.yaml
# sprint-specific scripts and smoke configs under configs/sprint*.v1.yaml
```

Exact pilot CLI flags follow ADR-008 and the package entry points present at the
frozen revision. Large Monte Carlo outputs are **not** golden.

## Known provisional findings and limitations

- Sprint Four monotonic uniform-\(\mathcal Q\) control (`MonotonicOutputGraph`) is an experimental comparison under ADR-001; it is not Version 2 certified-branch identity.
- Pilot and Sprint 4–6 Monte Carlo image/HTML bundles are stochastic or machine-dependent and are not exact golden tests.
- Runtime and wall-clock metrics are environment-dependent.
- Hierarchical bootstrap intervals depend on trial sampling and seed; store configuration with results rather than treating interval endpoints as goldens.
- Equal-node matching (ADR-010) can change gearbox lattice shape; comparisons must record matched shapes.

## Artifacts that are not golden

- `results/**` Monte Carlo trial packages and figures
- Canvas HTML bundles and large diagnostic image sets
- Any run whose seed, dirty-tree flag, or dependency versions are unset
- Stochastic population draws without a fixed sample bank

## Preservation rule

No existing Version 1 configuration may silently acquire Version 2 semantics.
Missing `architecture_version` continues to mean Version 1 (ADR-016).
