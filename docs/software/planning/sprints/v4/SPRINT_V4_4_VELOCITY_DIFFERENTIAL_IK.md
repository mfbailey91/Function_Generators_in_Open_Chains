# Sprint V4.4 — Velocity capability and differential IK

- **Status:** active; first instantaneous source slice in implementation
- **Activated:** owner instruction on 2026-11-20, following V4.3B acceptance completion
- **Authorization:** V4-400–V4-409 in `ACTIVE_SPRINT.md`; stages below are execution gates
- **Predecessor:** frozen V4.2B geometry and the V4.3B [acceptance addendum](../../../architecture/notes/V4_3B_ACCEPTANCE_ADDENDUM.md)
- **Decision:** [ADR-033](../../../architecture/adr/ADR-033-normalized-velocity-and-explicit-inverse-policies.md)
- **Execution guide:** [V4.4 Cursor roadmap](V4_4_CURSOR_IMPLEMENTATION_ROADMAP.md)
- **First fresh result root:** `results/v4_review/v4_4_velocity_ik_smoke/`
- **Full atlas and tracking roots:** assign distinct names and guards in their work packages; never reuse the smoke or any predecessor tree

## Research question

At the same mounted robot configuration, how does the transmission change the Cartesian velocity available from equal normalized actuator rates, and what actuator motion does the same requested Cartesian velocity require?

The normalized unit rate box is a common scientific comparison domain. It is not a motor specification. Preserve unconstrained inverse demand as well as optional uniform scaling into the box. Use “rate utilization” for this comparison; do not imply a hardware torque or speed limit has been measured.

## Fixed inputs

Consume `results/v4_review/v4_2b_span_controlled_corrective_closeout/` without regeneration. The source commit is `6680d648a0dc93d33f1cf34bb81cea69d6a44e80`; files digest is `ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a`; config digest is `ca632445469aa024c171fbc9d266ae58aeedf659e3ca3cbca5f16d70db1b6a9d`. Existing source-lock verification remains authoritative for the complete retained inventory.

Keep mounted Q/X, `J_g`, `J_f`, `J_xu`, rank tolerances, mechanism identities, and 17-case order. Pair four-bar, span-matched gearbox, and identity on the same physical samples. The full bank has 55,539 rows; the first smoke deliberately selects four cases × five samples × three arms = 60 rows.

## Work packages and gates

| ID | Deliverable | Acceptance gate |
| --- | --- | --- |
| V4-400 | Activation, ADR-033, source lock, normalized comparison and inverse-policy contracts | Current docs agree on V4.4 active and V4.5 held; no inherited model or evidence changes |
| V4-401 | Bounded forward velocity set API | Raw box corners/support; explicitly identified ray model; identity, anisotropic, signed, rank-one, and rank-zero controls |
| V4-402 | Exact, weighted minimum-norm, and positive-damping DLS policies | Requested/achieved motion, residuals, explicit inherited rank, SPD weights, report-only demand and uniform rate scaling |
| V4-403 | Retained-source 60-row smoke, strict transport, independent checks, guarded result package, paired preview | Clean source commit; all 60 rows and 20 physical triplets; finite and complete records; equal-axis plots; verifier; no predecessor changes |
| V4-404 | Full 17-case intrinsic velocity atlas and paired inspectors | Same-Q/Q-sample comparisons; primary scales separate regular variation from near-singular diagnostics; canonical data inspection; complete aggregation |
| V4-405 | Cartesian task and integration contract | Specify deterministic paths, start matching, feedforward/feedback, timestep/refinement, boundary behavior, failure taxonomy, and damping/rate-policy sweep before tracking generation |
| V4-406 | Tracking runner and deterministic controls | Apply declared policies consistently; record command/achieved motion and boundary events; analytical and timestep-convergence controls |
| V4-407 | Paired tracking study | RMS/peak error, rate demand/utilization, residuals, command continuity, and common task eligibility; keep physical singularity distinct from solver behavior |
| V4-408 | Independent numerical, artifact, and visual review | Mutation tests, source/identity locks, complete counts, common scales, per-cell and paired comparison checks; browser claims require observed execution |
| V4-409 | Retention, readout, and closeout | Separate clean source/evidence identities, frozen digest, tests on committed closeout, explicit limits, authorization reset |

The first patch implements V4-400–V4-403. It is a usable instantaneous geometry/IK step, not completion of the full V4.4 sprint. Proceed to V4-404 after accepting this slice; tracking must wait for the V4-405 contract.

## Scientific record

Each capability record contains the source state, raw Jacobians, inherited rank reports and provenance; positive rate limits; actuator and Cartesian corners; named normalized directions; support and ray speeds; isotropic speed; physical status; and any explicit inherited-rank ray representation.

Each inverse-policy record contains target velocity; requested and commanded rates; achieved velocity and residual before and after scaling; weight; damping; solver map and rank policy; rate utilization and feasibility; applied scale; and physical, solver, and command statuses. Unavailable exact inversion is a typed policy result, not a discarded physical sample.

The smoke uses unit +X, +Y, radial, and tangential commands wherever the direction is defined. Compare the same target and policy across all arms. Initial rates are `(1,1)`, weight is identity, and DLS damping is `0.05`; serialize these settings. No claim of tuned damping or optimal constrained control is permitted.

## Presentation and interpretation

- Use common Cartesian axes and one unit convention for paired velocity polygons. Show the identity arm as a reference with its actual values.
- Keep support and ray speed separate in legends and tables. A large projected velocity does not imply a large feasible velocity along that ray.
- Show unconstrained demand alongside rate-scaled results. Label the scale and the residual change.
- Use “bounded rank deficient” for forward velocity at rank loss. Static force unboundedness must not be copied into the velocity column.
- Give regular and near-singular diagnostics separate display ranges where required. Retain raw values and explain masks.
- Report all attempted samples and typed failures. Do not silently remove singular rows to make plots or tracking summaries cleaner.

## Required checks

Run the scoped quality gate, V4.3 acceptance regressions, V4.4 analytic and smoke tests, and the full repository regression suite before the retained first-slice commit. Independently verify the smoke after it is generated from a clean source commit. Record skipped optional capabilities accurately. Recheck the committed closeout when V4-409 is eventually reached.

All predecessor result trees are immutable. Production generation may not delete an occupied root, accept a descendant of a frozen root, evade a clean-source check through an alternate entry point, or expose a dirty/overwrite CLI escape. An isolated test seam must be explicit and protected from the real canonical tree.

## Deferred scope

V4.5 potential/continuous-flow policies, hardware motor sizing, gravity and dynamics, obstacles, 3R/6R redundancy, mechanism resynthesis, new rank thresholds, and global mechanism rankings remain outside this sprint. No null-space posture optimization is claimed for the square planar-2R initial case.
