# V4.3B acceptance addendum

- **Date:** 2026-11-20
- **Scope:** V4-324–V4-325, completing the owner's requested corrections before V4.4
- **Reviewed baseline:** `989633c6266e2ad68d47868dd4c72d21251d195c`
- **Frozen B source:** `731ae301962da8efbdd2d6262dc4fca0548a104a`
- **Frozen B evidence:** `ddfb26d5`; package `results/v4_review/v4_3_intrinsic_static_wrench_followup/`
- **Frozen B files digest:** `124d6c7b5701129d2f91a25dae2b6beabd546ba2498d11577b9d424a2b6cb7d6`
- **Status:** completed; V4-324–V4-325 closed, frozen evidence unchanged, V4.4 separately active

## Acceptance findings and corrections

The B package resolved the earlier regular-plot scale failure and missing diagnostic aggregates. An additional review found narrow integrity and UI gaps. This addendum preserves the historical B closeout and records the later source corrections without rewriting any retained package.

| Scope | Evidence and correction |
| --- | --- |
| Direction-specific capacity validation | A small nonbinding actuator projection no longer exempts a stable ray. Sensitive rays receive an active-projection uncertainty interval rather than skipping capacity checks: arbitrary zero/unit/huge values, gross factor errors, and unjustified unbounded labels fail. Named directions must match retained X within normalization roundoff, preventing a rotated direction with a matching fabricated capacity from bypassing validation. |
| Near-singular polygon integrity | Distinct convex vertices alone did not establish that they were the force image of the effort-box corners. The verifier now checks mapped corners and declared residuals against retained geometry with a scale-aware floating-point allowance. Distinct but incorrectly scaled near polygons fail. |
| Reported residual integrity | Plausible fabricated residuals, including a regular signed H-representation residual of `-0.5`, previously passed. The verifier recomputes residuals, compares the reports within a floating-error bound, and checks detail fields and the diagnostic outcome. |
| Rank representation | A rank-deficient force set could carry an invented closed polygon. Closed four-corner polygons now require inherited rank two; absent-polygon diagnostics must match rank loss. |
| Portable verification profile | Profile selection depended on a directory basename. It now uses the retained resolved configuration, so downloading or renaming a B package preserves its verification contract. Historical v1 and v2 acceptance is restricted to their exact pinned manifests and file digests; a rehashed B package cannot downgrade itself to v2. |
| Diagnostic selector | All four full-finite diagnostic figures existed, but no selector entries exposed them. The case viewer now exposes them and maps each to the correct stored directional value and paired comparison. |
| Lifecycle regression | Historical closeout checks continue to prohibit reauthorizing closed work packages while permitting the owner's separately activated V4.4 work. |

## Scientific acceptance

The read-only retained-artifact audit checked all 17 cases and all 55,539 canonical rows. Every B canonical row matches its A predecessor and the inline inspector data. No geometry, force model, rank tolerance, or raw scientific value changed.

| Classification | Count |
| --- | ---: |
| Regular | 53,856 |
| Near singular | 561 |
| Unbounded force set | 1,122 |
| All rows | 55,539 |
| Near-singular vertex-diagnostic failures | 539 |
| Regular vertex-diagnostic failures | 0 |

All primary directional ranges use regular, eligible, finite values. Minimum distinct regular viridis colors across the 17 cases are 70 for +X, 46 for +Y, 32 for radial, and 74 for tangential. This verifies that near-singular outliers no longer flatten the regular fields. Full-finite diagnostic ranges remain separate and preserve those outliers.

The new polygon audit allowance is `8 * eps * (abs(A) @ abs(vertices) + torque_limits)`. It accounts for cancellation and cross-platform arithmetic when checking that serialized geometry is possible. The retained diagnostic threshold remains `1e-9`, and all 539 numerical diagnostic failures remain failures. No scientific rank threshold or outcome flag was retuned to make the acceptance gate pass.

For sensitive rays, each effort projection has an allowance of `16 * eps * (abs(A) @ abs(d))`. Finite capacities must place their reciprocal within the attainable interval of active normalized projections. The accepted force API's `1e-12` active-projection cutoff is unchanged. If uncertainty straddles that cutoff, finite/unbounded ambiguity is allowed only within the corresponding bounded reciprocal interval. The finite reciprocal floor cannot collapse to zero. A scan of all 222,156 named directions in each A/B package found a maximum reconstruction discrepancy of one machine epsilon; the named-vector audit now permits normalization roundoff instead of a loose `1e-12` direction perturbation.

## Verification and retained evidence

Focused tests include unchanged B verification after relocating the package; rehashed missing diagnostic assets and profile downgrade; fabricated near polygons, diagnostics, and rank-one polygons; stable-ray counterexamples; and actual execution of the diagnostic view controls in Node. Historical A/original-package positives, output-root protection, and full repository regressions are part of the combined acceptance gate.

The completed regression batches cover all **1,599 collected tests exactly once: 1,575 passed and 24 skipped, with no failures or errors**. All skips require unavailable optional OMPL bindings. The V4.3 group contributes 151 passes and the V4.4 group 70 passes (47 core and 23 smoke tests). An earlier interrupted parallel run is excluded from these totals. Scoped Ruff, formatting, and strict mypy gates pass. The original, A, and B whole-package closeout verifications pass, including the relocated B positive control.

The B package remains exactly frozen. Its 17 committed HTML case pages therefore retain the historical selector version. The source correction is exercised by the executable Node gate and can be reviewed in a derived preview; it is not a claim that frozen pages were edited. No successful real-browser keyboard/layout E2E run is claimed.

With the combined gate complete, V4.4 proceeds under [ADR-033](../adr/ADR-033-normalized-velocity-and-explicit-inverse-policies.md) and its [sprint](../../planning/sprints/v4/SPRINT_V4_4_VELOCITY_DIFFERENTIAL_IK.md). V4.5 remains held.
