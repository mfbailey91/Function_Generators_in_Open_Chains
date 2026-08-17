# V3.6D canonical span corpus review

**Status:** review complete — scientific exit criteria met; no regeneration authorized
**Sprint reviewed:** V3.6D (V3-650–V3-659)
**Artifact reviewed:** `results/v3_review/v3_6d_span_corpus/`
**Implementation commit:** `f9edbdf`
**Follow-up:** none. V3.6E and V3.6F already consumed this registry. Do not retune `PRIMARY_CERTIFICATE`, do not regenerate the D package, and do not open V4.2 or residual V3.7 from this note.

This is a defect-first review of the shipped corpus against [SPRINT_V3_6D](../../planning/sprints/v3/SPRINT_V3_6D_CANONICAL_SPAN_CORPUS.md) and [V3_6D_SPAN_CORPUS_CLOSEOUT.md](V3_6D_SPAN_CORPUS_CLOSEOUT.md). A finding is actionable only if it is a contract miss, silent convention change, weak test that can hide regeneration, or provenance error.

## Contract table

| Work package | Verdict | Notes |
| --- | --- | --- |
| V3-650 guards | Pass | D writes only `results/v3_review/v3_6d_span_corpus/`; tests refuse frozen V3, V4.0/V4.1, E/F, and arbitrary paths |
| V3-651 ranges | Pass | Zero-centered usable Q; usable ⊂ mechanical; 175 classified `near_limit_stress` |
| V3-652/653 synthesis + registry | Pass | Seed 650; one hashed record per `{95,135,145,150,175}`; legacy `(1, 2.5, 2, 2)` absent; content hash verifies |
| V3-654 gearboxes | Pass | 17 realized pairs; U/Q endpoints and average ratio match |
| V3-655 cases | Pass | Generated 17 IDs; `(145,145)` tagged both studies |
| V3-656 cards | Gap | Cards have spans, U, `|dq/du|` stats, endpoints, margins; missing `|du/dq|`, log-gain/curvature, change-point |
| V3-657 tests | Gap | Core invariants exist; committed artifact is not hash-locked; one tautology |
| V3-658 exporter/config | Pass | Strict config rejects gravity keys; exporter wrote registry, cards, comparison, checksums |
| V3-659 provenance | Gap | Artifact `git_revision` is authorization `d85f87a`; source + D/E/F artifacts landed together in `f9edbdf` |

Sprint exit items 1–5 and 7 hold. Item 6 (generate from a clean implementation revision, separate artifact commit) does not.

## 175° inspection

| | |
| --- | --- |
| Status | `boundary_stress_only` / `canonical_monotonic_branch_near_limit_v1` |
| Lengths | `(0.999, 1.713, 1.713, 1.0)`, `d=1` |
| Usable | 174.883° (error 0.117° ≤ 0.25°) |
| Mechanical leftover | ~0.24° |
| `min \|dq/du\|` | 0.107 (above the **primary** floor 0.05) |
| Worst margin | 0.00190 (near-limit `endpoint_margin_fraction=0.002`) |
| U interval | `[0.099, 6.236]` rad (~351° of crank travel) |

175° did not fail the primary gain floor. It failed the primary **endpoint trim**: a 5% U shrink on this near-full-cycle crank would cut several degrees of Q and miss the 0.25° window. The near-limit profile is a separate frozen object; `PRIMARY_CERTIFICATE` remains `min_abs_gain=0.05`, `endpoint_margin_fraction=0.05`, `min_u_width=0.3`.

Primary family (all `certified_primary`):

| span | usable | error | min \|dq/du\| | worst margin |
| ---: | ---: | ---: | ---: | ---: |
| 95 | 94.818 | 0.182 | 0.138 | 0.0259 |
| 135 | 135.041 | 0.041 | 0.128 | 0.0262 |
| 145 | 145.150 | 0.150 | 0.080 | 0.0233 |
| 150 | 150.163 | 0.163 | 0.085 | 0.0251 |

`GRASHOF_MARGIN=0.0` in synthesis (not `PopulationSpec`’s 0.05) is an explicit named constant. That is why 145/150/175 exist at all. Leave it.

## Ranked findings

### 1. Committed registry is not test-locked

**Finding: contract gap (V3-657).** D tests call `build_span_registry(seed=650)` and never compare `sha256` to `results/v3_review/v3_6d_span_corpus/registry.json`. E/F read the committed file. A later synthesis edit can pass D tests while leaving E/F on a stale corpus.

**Closeout consequence:** if regeneration is ever authorized, add one hash-equality test. Do not regenerate D now.

### 2. V3-659 process miss

**Finding: provenance gap.** Manifest records `d85f87a` (D authorization only). Implementation, D/E/F artifacts, and closeout were one commit (`f9edbdf`). That does not change the numbers.

**Closeout consequence:** do not regenerate to restamp `git_revision`. Treat the shipped package as frozen.

### 3. Incomplete V3-656 descriptors and one tautological assert

**Finding: documentation/test gap.** `assert ids == sorted(ids) or True` is a tautology (17-id uniqueness and config seed match still hold). V3-656’s `|du/dq|`, curvature, and change-point were never exported.

**Closeout consequence:** neither affects the 17-case identities E/F already consumed. Do not reopen D to add descriptors.

## Non-goals

This note does not authorize hash-lock tests, tautology fixes, descriptor export, `span_synthesis.py` changes, `PRIMARY_CERTIFICATE` retune, V3.6E/F rewrites, V4.2, or residual V3.7.
