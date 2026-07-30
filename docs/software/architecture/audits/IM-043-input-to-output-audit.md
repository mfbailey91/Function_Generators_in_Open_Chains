# IM-043 — `input_to_output()` call-site audit (S3-04)

Sprint 3 Day-1 inventory and Day-5 closeout for graph-facing raw-output usage.

## Classification key

| Class | Meaning |
| --- | --- |
| **mechanism-internal** | Permitted; implements or wraps \(g_m\) |
| **graph-facing** | Must migrate to `ConstrainedInputGraph.raw_output` / `output` / `output_displacement` |
| **construction helper** | Permitted with explicit label; used before a graph instance exists |
| **graph-free helper** | Permitted with explicit label; unit tests / no-graph contexts |
| **test / diagnostic** | Permitted; mechanism tests or labeled diagnostics |

## Day-1 inventory (before migration)

### Mechanism-internal (permitted)

| Location | Notes |
| --- | --- |
| `mechanisms/base.py` | Protocol / ABC |
| `mechanisms/gearbox.py` | Implementation |
| `mechanisms/fourbar.py` | Implementation + lift helpers calling self |
| `mechanisms/_testing.py` | Test double |

### Graph-facing (to migrate)

| Location | Notes |
| --- | --- |
| `graphs/costs.py` → `output_euclidean_cost` | Called from search with a graph available |
| `search/core.py` | Default edge cost via `output_euclidean_cost(mech, …)` |
| `search/cost_to_go.py` | Same pattern |
| `graphs/validation.py` → `output_at` | Should own raw via `raw_output` |

### Construction / graph-free helpers (label, keep)

| Location | Notes |
| --- | --- |
| `graphs/validation.py` → `configuration_is_valid` | Used during `ConstrainedInputGraph` construction |
| `graphs/costs.py` (after migration) | Keep for tests without a graph |

### Tests (permitted)

| Location | Notes |
| --- | --- |
| `tests/mechanisms/*` | Mechanism contract tests |
| `tests/graphs/test_validation.py` | Mechanism double + direct checks |
| `tests/experiments/test_tasks.py` | Residual spot-checks |
| `tests/mechanisms/test_fourbar_lift.py` | Lift diagnostics |

## Day-5 closeout (after IM-042)

| Location | Class after migration |
| --- | --- |
| `ConstrainedInputGraph.raw_output` | **mechanism access via graph boundary** |
| `ConstrainedInputGraph.output` / `output_at` | Canonical path (`canonicalize ∘ raw_output`) |
| `ConstrainedInputGraph.output_displacement` | Authoritative graph-facing distance |
| `search/core.py`, `search/cost_to_go.py` | Use `graph.output_displacement` |
| `graphs/costs.output_euclidean_cost` | **graph-free helper** (labeled); not used by search defaults |
| `configuration_is_valid` | **construction helper** (labeled) |
| Mechanism modules | Unchanged, permitted |
| Tests | Unchanged, permitted |

### Unresolved graph-facing raw-output calls

None after IM-042. Search and default edge costs route through the graph boundary.

## S3-01 / S3-02 confirmation

- **ADR-011** remains authoritative (chart-center lift). Amended only to document graph ownership (IM-042).
- **`to_mechanism_native`** not required for P0 migration; deferred.
