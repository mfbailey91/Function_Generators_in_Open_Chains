# V4.3B Cursor implementation roadmap

Use with [SPRINT_V4_3B_INTRINSIC_STATIC_WRENCH_FOLLOWUP.md](SPRINT_V4_3B_INTRINSIC_STATIC_WRENCH_FOLLOWUP.md) and [ACTIVE_SPRINT.md](../../ACTIVE_SPRINT.md).

## Sequence

1. **V4-320** — Authorize V4-320–323; guard writes to `v4_3_intrinsic_static_wrench_followup/` only; freeze original and corrective roots.
2. **V4-321** — Tighten `corrective_v2` row validation: nonnegative residuals, polygon structure/order, per-direction sensitivity gating. Adversarial tests must reject the review integrity mutations.
3. **V4-322** — Primary directional heatmaps use regular-finite shared scales; labeled diagnostic views retain near-singular finite values.
4. **V4-323** — Aggregate diagnostic failures in `validation.json`; reconcile stale V4.3A wording; clean-commit; generate/verify/retain follow-up package; closeout and authorization reset.

## Reproduction

```bash
python scripts/generate_v4_3_intrinsic_static_wrench.py --config configs/v4/intrinsic_static_wrench_v1.json
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench_followup
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench_corrective
python scripts/verify_v4_3_artifact.py results/v4_review/v4_3_intrinsic_static_wrench
```
