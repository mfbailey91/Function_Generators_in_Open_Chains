# V4.4 first slice — Velocity capability and instantaneous differential IK

- **Date:** 2026-11-20
- **Sprint state:** V4.4 active; this is the first instantaneous slice, not a sprint closeout
- **Work packages:** V4-400–V4-403
- **Decision:** [ADR-033](../adr/ADR-033-normalized-velocity-and-explicit-inverse-policies.md)
- **Next package:** V4-404 full intrinsic velocity atlas; V4-405 task/integration contract precedes tracking
- **Result root:** `results/v4_review/v4_4_velocity_ik_smoke/`
- **Clean generation source:** `7b40fc290424ec0e0b0e072cd265fe4879d2af04`
- **Retained files digest:** `891071c794689cea3a9d8654abffca176149a6ceae50b721bf7415b2c52d931c`
- **Retention:** 7 inventoried files plus the manifest; independently verified; V4-400–V4-403 complete

## What is implemented

`velocity_capability_from_snapshot` consumes the stored planar geometry snapshot and maps a finite normalized actuator-rate box into Cartesian velocity. It retains raw corner images and directional support. Directional ray speed is separate: it measures movement along the requested ray, rather than maximum projection onto it. At inherited rank loss the finite velocity image becomes lower dimensional. The explicitly truncated ray model is retained alongside the raw map; no force-set “unbounded” label is reused.

`differential_ik_from_snapshot` requires an explicit exact, minimum-norm, or damped-least-squares policy. Exact inversion is unavailable when inherited rank is insufficient. Weighted minimum norm acts within the inherited physical subspace. Positive damping regularizes the inverse without changing physical rank. Every result records requested and commanded rates, achieved motion, residuals, utilization, saturation/excess channels, weight, damping, the solver map, and the source snapshot identity.

The default `report_only` rate policy preserves unconstrained demand. Optional `uniform_scale` reduces the whole command by one recorded factor. It preserves achieved direction and records the resulting error. It does not claim to solve a box-constrained least-squares optimization.

## Fixed comparison and coverage

The smoke restores four retained V4.2B cases at five grid positions, across four-bar, span-matched gearbox, and identity on shared Q. It neither recomputes wrench nor changes geometry. Inputs are the unit actuator-rate box, identity actuator weight, unit +X/+Y/radial/tangential targets, and DLS damping `0.05`. These are reproducible mathematical comparison settings, not hardware specifications or optimized application settings.

Coverage includes the retained 175-degree boundary-stress control. These mixed smoke counts are coverage accounting, rather than primary-certified-family population estimates.

| Item | Count |
| --- | ---: |
| Cases | 4 |
| Matched physical samples | 20 |
| Snapshot records | 60 |
| Regular records | 36 |
| Near-singular records | 8 |
| Bounded rank-deficient records | 16 |
| Requested direction/inverse/rate-policy combinations | 1,440 |
| Available results | 1,312 |
| Typed exact-rank-loss unavailable results | 128 |
| Source failures / silent drops | 0 / 0 |

Each policy/rate-policy combination attempts 240 requests. Exact inversion has 176 available and 64 unavailable results for each rate policy. Minimum norm and DLS each have 240 available results per rate policy. All three uniform-scaling variants have zero commanded budget exceedances.

“Available” means the policy produced a numerical result. Target realization is measured separately by achieved velocity and residual; a projected or regularized result can have a substantial residual.

Exact and minimum-norm demand exceeds the unit budget on 141 requests per rate-policy variant; DLS demand exceeds it on 117. The exact/minimum-norm scaling count is 142 because it includes one roundoff-sized adjustment at the boundary. Exceedance uses the serialized feasibility tolerance; scaling uses the exact computed peak above one. This is an arithmetic accounting distinction, not an additional physical saturation event.

## What the smoke demonstrates

Paired plots show all three arms with common equal Cartesian axes within each physical sample, so polygon size and direction can be compared directly. The preview includes regular corner and center samples for every selected case. Policy tables show unit +X requests for those samples; complete records retain all named targets and all 60 snapshots.

The preserved center snapshots classify the four-bar as near singular and the gearbox/identity arms as rank deficient. Tiny retained coordinate differences and inherited numerical thresholds remain visible. They are diagnostic information, not evidence that a transmission removes the robot's physical singularity. Regular comparisons and near-singular diagnostics must remain distinguishable when the full atlas is added.

Among the 144 regular exact/report-only requests, the maximum achieved-velocity residual norm is about `3.64e-16`; the maximum requested normalized peak rate is about `16.40`. The 32 near-singular exact requests reach a peak demand of approximately `3.86e11` and a residual of `1.51e-5`. Those large inverse demands illustrate sensitivity near rank loss; they do not establish usable physical speed or tracking performance.

## Integrity and verification

The production generator validates the fixed configuration and frozen source, then uses a shared exact-root and clean-source preflight before any creation. It repeats the preflight before exclusive writes. Existing outputs are never deleted or overwritten. Explicit isolated test roots cannot enter the real canonical tree, an ancestor/descendant alias, or a symlink escape.

The independent reader does not call the capability or inverse solver. It joins every record to its exact retained snapshot and source identity; verifies corners, named directions, support, ray speed, inverse requests, actual achieved motion, residuals, utilization, scaling and saturation; validates typed unavailable results; checks complete pairing/accounting; and verifies every file hash. Absolute local source directories are excluded from scientific identity so the package can move between checkouts.

The first-slice acceptance includes 47 analytic/control tests and 23 smoke/guard/reader tests, scoped Ruff and mypy, and direct visual inspection of the Matplotlib output. Completed regression batches cover all 1,599 collected tests exactly once: 1,575 passed and 24 optional-OMPL skips, with no failures or errors. An earlier interrupted parallel run is excluded from those counts. The canonical smoke was generated from the clean source commit above and independently verified using `python scripts/generate_v4_4_velocity_smoke.py --verify`; all 60 rows and 1,440 requests pass, with no source failures or silent drops. V4-403 is complete. Real-browser layout/keyboard acceptance is not claimed by these checks.

## Next execution

Implement V4-404 on the same public objects: the full 17-case intrinsic velocity atlas, complete canonical-cell inspection, and paired comparisons with regular versus near-singular display policies. Assign a new guarded result root. Before V4-406 tracking, complete V4-405's explicit task timing, integration, feedback, state-boundary, and failure contracts. No trajectory tracking result, full-atlas acceptance, global mechanism ranking, or V4.5 flow result is claimed by this smoke.
