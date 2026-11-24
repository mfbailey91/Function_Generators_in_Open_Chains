# V4.4 implementation roadmap

Use [ACTIVE_SPRINT.md](../../ACTIVE_SPRINT.md) for current authorization and [the sprint](SPRINT_V4_4_VELOCITY_DIFFERENTIAL_IK.md) for acceptance. [ADR-033](../../../architecture/adr/ADR-033-normalized-velocity-and-explicit-inverse-policies.md) owns the scientific policy.

## 1. Accept the instantaneous slice

Review `metrics/velocity.py` and the 60-row retained-source consumer. Check support versus ray speed, raw versus inherited-rank maps, weighted minimum norm, positive-damping DLS, and the requested/commanded distinction. Run:

```bash
python scripts/check_v4_3a_quality.py
python scripts/check_v4_4_quality.py
pytest -q tests/v4/test_v4_4_velocity.py tests/v4/test_v4_4_smoke.py
pytest -q
```

Use the retained smoke's `index.html`, records, and manifest for review. Do not rerun generation into its occupied tree. The production script is `scripts/generate_v4_4_velocity_smoke.py`; it requires a clean source commit and an absent or empty authorized result root. Verification is read-only and can be repeated.

## 2. Extend the same objects to the intrinsic atlas — V4-404

Consume all 17 cases through the existing frozen-row adapter. Add a distinct guarded atlas root and schema before generation. Preserve every source row and the physical pairing key. Show true-scale common-axis polygons, direction-specific support and ray-speed fields, actuator demand, physical rank/conditioning, and explicit diagnostic views. Provide cell inspection and paired differences from canonical data, not recomputed browser geometry. Regular scales must not be flattened by near-singular extremes.

Production entry points: `scripts/generate_v4_4_velocity_atlas.py` writes only `results/v4_review/v4_4_intrinsic_velocity_atlas/` from a clean source into an empty root. The smoke package remains frozen and is refused by atlas preflight.

Accept analytic controls and complete counts first. Generate only from a clean source commit, then verify independently and retain evidence separately.

## 3. Specify tracking before building it — V4-405

Write a small deterministic task contract with declared Cartesian paths, shared start/end criteria, initial physical-state matching, task timing, integration step, refinement test, feedback law, domain-boundary handling, and typed failure outcomes. Specify a common target-speed and damping/rate-policy sweep. Treat any mechanism-specific loss of task eligibility as an outcome rather than filtering it away.

The instantaneous smoke is not a tracking benchmark. Do not infer RMS error, temporal stability, or command continuity from it.

## 4. Implement, compare, and close — V4-406–V4-409

Implement the runner against that contract; add analytic and timestep controls; then run paired tasks and summarize requested versus achieved motion. Review the independent artifact verifier and all visual semantics. Keep source and evidence commits separate, publish the exact source and package digests, rerun regression gates on the committed closeout, and reset authorization only when the complete sprint is closed. V4.5 needs a separate owner activation.

## V4.3B acceptance dependency

The [acceptance addendum](../../../architecture/notes/V4_3B_ACCEPTANCE_ADDENDUM.md) records the remaining verifier and diagnostic-selector fixes after the frozen B package. It preserves the original B files and numerical diagnostics. Do not regenerate B to make its frozen HTML look like newer source.
