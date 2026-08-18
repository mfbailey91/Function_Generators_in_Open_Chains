# Sprint V4.2A — Span-Controlled Planar 2R Visual Planning Audit

- **Status:** completed; V4-210–V4-219 closed; `ACTIVE_SPRINT.md` returns to no authorization
- **Depends on:** closed V4.2 geometry atlas (V4-200–V4-208); frozen V3.6D registry; frozen V3.6B audit contract; no-authorization predecessor
- **Blocks:** nothing (V4.3 remains separately blocked)
- **Reserved work packages:** V4-210–V4-219
- **Does not reuse:** V4-200–V4-208, V4-300–V4-309
- **Artifact target:** `results/v4_review/v4_2a_span_controlled_visual_audit/`
- **Predecessor geometry:** [`results/v4_review/v4_2_span_controlled_geometry_atlas/`](../../../../results/v4_review/v4_2_span_controlled_geometry_atlas/)
- **Visual-audit analogue:** [Sprint V3.6B](../v3/SPRINT_V3_6B_PLANAR2R_VISUAL_AUDIT.md)

## Sprint purpose

Produce a trial-scoped, offline HTML visual audit of the frozen V3.6D span family using the V3.6B planner set, task IDs, and page contract. Consume the hashed registry; do not resynthesize. Pair four-bar versus span-matched gearbox only. Identity-on-shared-\(Q\) remains a geometry null control from V4.2 and is not a third planner arm.

This sprint is implementation introspection and review. It is not a population experiment, a ranking of mechanisms, a V4.2 geometry regeneration, or Sprint V4.3.

## Sprint question

> How do the certified span-family transmissions appear, trial by trial, under the frozen V3.6 free-space tasks and the V3.6B planner set?

## Frozen inputs

- V3.6D package `results/v3_review/v3_6d_span_corpus/` (registry digest locked);
- V3.6B audit contract: tasks `near_0`–`far_4`, seed `7`, lattice `32\times 32` Chebyshev-1, planner list, \(\Delta z=z_F-z_G\);
- frozen bank `configs/v3/free_space_planar2r_v2.json` (`reuse_only`);
- V4.2 case identities (17 unique ordered assignments). Do not rewrite the V4.2 package.

Cores \(\{95^\circ,145^\circ,175^\circ\}\) and bio \(\{135^\circ,145^\circ,150^\circ\}\) are the D family. 175° remains `boundary_stress_only`. `PRIMARY_CERTIFICATE` is not mutated.

## Start semantics

V3.6 v2 resolves `start_u_frac` on the authoring four-bar, then shares that \(q\). Span cases have different certified \(Q\) boxes, so the legacy numeric `start_q` is not portable. V4.2A re-resolves shared start \(q\) **per case** on that case’s V3.6D four-bar using the same frozen `start_u_frac`, then the gearbox inverse. Cartesian disks and represented goal points stay the frozen X-space bank. Fail closed on pair-invariant mismatches within a case. Do not drop or replace a task after seeing planner outcomes.

## Non-goals

- inferential statistics or stochastic repetition estimates;
- ranking mechanisms;
- identity-on-shared-\(Q\) as a planner arm;
- changing the V3.6 bank or regenerating V3.6B/C/D or V4.0–V4.2 packages;
- V4.3 wrench, velocity/IK, gravity, 3R, obstacles, or MoveIt;
- a single dashboard that visually mixes all ten trials across cases.

## Work packages

## V4-210 — Contract landing and artifact-guard extension

Land this sprint. After activation, extend `v4_artifact_guard.py` so V4.2A writers may write only:

```text
results/v4_review/v4_2a_span_controlled_visual_audit/
```

Refuse V4.0, V4.1, frozen V4.2, every `results/v3_review/` package, sibling V4 packages, and arbitrary paths.

## V4-211 — Frozen config

Add `configs/v4/planar2r_span_controlled_visual_audit_v1.json` with pydantic `extra="forbid"`. Lock the V3.6D digest. Reject gravity/payload keys. Freeze the ten task IDs, seed 7, lattice shape, planner set, animation policy, and \(\Delta z\) convention.

## V4-212 — Per-case arms and lattices

Consume `realize_span_case` from the frozen registry. Wrap four-bar and span-matched gearbox as `SamplingSmokeArm` named `fourbar` / `gearbox`. Build paired lattices from those branches (`build_paired_lattice_arms_from_branches`). Do not change the default V3.6B smoke pair.

## V4-213 — Pair/task resolver

Reuse the corrected V3.6 loader with per-case arms. Re-resolve shared start \(q\) from frozen `start_u_frac`. Fail closed on shared Q lattice, start tip, and candidate-ordering mismatches within a case. Optional `lattice_arms=` on `resolve_audit_trials` so V3.6B tests keep the default pair.

## V4-214 — Planner runs and panels

Reuse `run_planner_for_trial`, mapping/graph/search panel writers, and V3.6B animation policy. Static print panels are authoritative. OMPL rows are marked unavailable rather than omitted. Failures remain on the trial page.

## V4-215 — Two-matrix HTML audit

Root `index.html` shows core \(3\times 3\), biological \(3\times 3\), 175° classification, links to case audits, and the no-inference statement. Each case has a V3.6B-style index (ten trial links + \(\Delta L_U\) table) and one self-contained page per trial in the V3.6B section order.

## V4-216 — Tests

Guard, D digest, 17 case ids, 175 typed, synthesis not invoked, per-case pair invariants, shared \(w_Q\)/\(w_X\), HTML contract. Tests use `tmp_path`, one certified case, one or two tasks, 8×8 lattice, `--skip-animations`. Prove V3.6B config/tests unchanged and V4.2 files byte-unchanged after a V4.2A tmp export.

## V4-217 — Retained artifact

Generate the full 17-case × 10-task package at the frozen 32×32 audit lattice.

## V4-218 — Project-index canvas

Update the project-index canvas Planning tab: keep V3.6C aggregates as the legacy ~78° pair; add a span-family case/task gallery over V4.2A `summary.json`. HTML trial pages remain the visual source of truth.

## V4-219 — Closeout and authorization reset

Write a closeout note. Return `ACTIVE_SPRINT.md` to no authorization. Do not activate V4.3 in the same change.

## Compact Cursor prompt

> Implement only Sprint V4.2A work packages V4-210–V4-219 after `ACTIVE_SPRINT.md` authorizes them. Preserve closed V4.0/V4.1/V4.2 and frozen V3.6D–F. Consume the V3.6D registry by digest; do not resynthesize. Run the V3.6B visual-audit contract on the 17 unique span assignments with four-bar vs span-matched gearbox. Write only `results/v4_review/v4_2a_span_controlled_visual_audit/`. Do not implement V4.3, velocity, gravity, 3R, or MoveIt.
