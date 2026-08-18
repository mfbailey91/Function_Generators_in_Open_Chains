# V4.2B Implementation Review and Final Closeout Gate

**Reviewed repository:** `mfbailey91/Function_Generators_in_Open_Chains`
**Reviewed main commit:** `e98ca1f5c7dcf4e21f40185d36c8ba1a6664bf7b`
**Merged change:** PR #27, “Add Version 4 kinematic geometry through V4.2B corrective implementation”
**Disposition:** architecture accepted; canonical V4.2B evidence and sprint closeout remain open

## Executive assessment

The merged V4.2B implementation fixes the central coordinate defect at the correct software boundary. The robot-facing joint coordinate is now a mounted output coordinate rather than the raw four-bar follower angle, while the native mechanism geometry and `J_g` remain intact.

The implementation also introduces the right supporting architecture:

- a dedicated output-mounting adapter;
- a mounted span-case realization owner;
- a fresh corrective atlas generator;
- one common candidate-Q lattice;
- pre-search finite-edge compilation;
- a frozen common-physical task bank;
- per-case compressed geometry rows;
- dirty-source refusal for canonical generation.

PR #27 explicitly retained V4.2B as unfinished: canonical evidence was not generated, the corrected visual audit remained follow-up, and V4-229 had not reset authorization. The current repository status is therefore consistent with an active final closeout gate rather than a completed sprint.

## Findings carried into the closeout gate

### 1. Nonfinite edge values remain over-broadly classified

The current single-arm compiler treats every nonfinite value as `unavailable_local_motion`. This conflates:

- `+inf`, which can represent the legacy unavailable-motion sentinel;
- `NaN`, which is a numerical or programming failure;
- `-inf`, which is an invalid negative cost.

The closeout must make only positive infinity an unavailable-edge sentinel. `NaN`, negative infinity, and finite negative values must fail closed.

### 2. Common candidate topology does not yet guarantee common final topology

The common-Q graph builder correctly freezes one sample bank, candidate adjacency, and valid-node mask. However, per-arm finite-edge compilation can still remove different edges after connector evaluation.

The primary paired experiment needs one joint edge-admission step so the final graph passed to Dijkstra/A* has identical edge IDs. Separate actuator costs remain attached to that one final topology.

### 3. Mounted-output proof coverage is incomplete

All-case realization tests validate zero-centered bounds and unchanged `J_g`, but the reusable adapter still needs direct tests for:

- scalar and vector offsets;
- zero-offset identity;
- finite-difference Jacobian agreement;
- serialization round trip;
- preservation of branch metadata;
- double-mount prevention.

### 4. Artifact verification is not fully fail-closed

The current verifier inventories and hashes compressed geometry files well, but several root fields are optional when they should be mandatory. Full geometry rows are also checked against a small key subset rather than deserialized through the actual strict row schema.

The closeout must require all provenance keys, require `files_digest`, enforce zero silent drops, validate the exact case set, and recursively verify both geometry and planning subpackages.

### 5. Canonical evidence has not been generated

The V4.2B result root is intentionally absent from the merged implementation checkpoint. This is correct for the implementation/evidence two-commit pattern, but it means no scientific or closeout disposition can yet be accepted.

### 6. Full regression and CI evidence is not recorded

The PR records focused V4.2B tests. The final closeout still needs:

- full pytest;
- Ruff check;
- Ruff format check;
- mypy;
- recorded environment and pass/skip counts;
- preferably a minimal GitHub Actions workflow.

### 7. Canonical project documentation remains inconsistent

The V4 sprint index and active-sprint file are current. The root README and master V4 project plan still understate or misorder the V3/V4 lineage. The closeout should normalize those documents so future automation does not reopen historical sprints or consume V4.2 instead of V4.2B.

## Accepted decisions

1. Keep the sprint identity **V4.2B**; do not create V4.2C.
2. Keep V4-220–V4-229 as the only authorized range.
3. Add ADR-030 for final paired topology and nonfinite edge semantics.
4. Treat PR #27 as an implementation checkpoint, not a closeout artifact.
5. Preserve V4.2 and V4.2A byte-for-byte as historical diagnostic evidence.
6. Require V4.3 to consume canonical V4.2B mounted-coordinate snapshots.
7. Generate evidence only from a clean implementation commit.
8. Reset authorization to none before any V4.3 activation.

## Final gate

The normative execution contract is:

```text
docs/software/planning/sprints/v4/V4_2B_FINAL_CLOSEOUT_GATE.md
```

The gate concentrates remaining work into:

- correctness hardening;
- evidence hardening;
- canonical generation;
- independent review;
- documentation normalization;
- authorization reset.

## Review outcome


a) **Architecture:** accepted.

b) **Implementation checkpoint:** accepted as a basis for continued work.

c) **Canonical evidence:** not yet available.

d) **V4.2B closeout:** not yet accepted.

e) **V4.3 activation:** blocked until all final closeout criteria pass.
