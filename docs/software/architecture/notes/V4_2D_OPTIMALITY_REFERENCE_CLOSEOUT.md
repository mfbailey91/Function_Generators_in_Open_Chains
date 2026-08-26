# V4.2D optimality-reference closeout

**Disposition:** completed after reconstruction, join, packaging, and verification; V4.3 remains drafted / blocked
**Implementation revision:** `898c56f1`
**Evidence revision:** `b05b1288`
**Package:** [`results/v4_review/v4_2d_optimality_reference_report/`](../../../../results/v4_review/v4_2d_optimality_reference_report/)
**Work packages closed:** V4-240 through V4-249
**Work-package review:** [`V4_2D_IMPLEMENTATION_REVIEW.md`](V4_2D_IMPLEMENTATION_REVIEW.md)
**ADR:** [`ADR-032`](../adr/ADR-032-planner-optimality-represented-goal-reference.md)
**No-inference:** V4.2D optimality-reference report; descriptive only; not a global ranking and not a mechanism ranking; \(J^*_C\) is the V4.2C center-IK direct optimum; \(J^*_B\) is a representation-sensitivity control only.

## What closed

Sprint V4.2D reconstructed the exact V4.2C finite goal set as planar-2R IK lifts of the Cartesian-disk center and scored frozen Stage C planner rows against that mechanism-specific direct optimum. It did not rerun OMPL, mutate V4.2B/V4.2C/V4.2C-R, or activate V4.3.

The report separates:

- mechanism effect on the achievable center-IK actuator-travel optimum \(\Delta J_C^*\);
- planner gap relative to that optimum \(\epsilon=J-J^*_C\);
- index-matched discoverability contrast \(\Delta\epsilon^{\mathrm{rel}}\) (not CRN);
- final-gap split into goal-selection regret and path inefficiency.

## Frozen sources (unchanged)

```text
V4.2B files_digest=ce7bbea03c9ac9ea77bad761e371d5abcd96965e7aa55daf76269ee51469be9a
V4.2C files_digest=99ec523a706632391c85e16cae505e6cd11a6f14d15682eb711515aefcf76c93
V4.2C source revision=5320d6f336ef82615a51f7826d0febd39c18f9db
```

## Verified V4.2D package

```text
source_git_revision=898c56f1
files_digest=7a04b259aa30591d33f7a008b2ad008046afd911281090cd3b8e7a15810a20b5
n_files=30
n_reference_rows=100
n_stage_c_rows=6200
n_orphans=0
```

Primary reference matrix: 5 audit cases × 10 tasks × 2 mechanisms. Candidate identity is `<goal_sample_id>::<ik_family>`. Already-satisfied queries have \(J^*_C=0\) and are excluded from relative-gap and time-to-tolerance plots.

## Allowed conclusion

Under the frozen V4.2C center-goal representation, the span-matched gearbox and four-bar possess different exact actuator-travel references, and planner families approach those mechanism-specific references at different finite-budget rates. Quadrants of \(\Delta J_C^*\) versus \(\Delta\epsilon^{\mathrm{rel}}\) distinguish a lower/higher optimum from easier/harder discovery.

The package may not claim universal mechanism or planner superiority, obstacle-routing performance, common-random-number inference, or continuous Cartesian-goal-region optimality.

## Authorization

`ACTIVE_SPRINT.md` returns to **Code authorization: none.** Sprint V4.3 remains drafted / blocked.
