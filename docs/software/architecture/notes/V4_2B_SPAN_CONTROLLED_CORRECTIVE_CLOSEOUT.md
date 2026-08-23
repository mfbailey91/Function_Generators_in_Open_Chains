# V4.2B span-controlled corrective closeout

**Disposition:** completed; canonical mounted-Q evidence retained
**Implementation revision:** `6680d648a0dc93d33f1cf34bb81cea69d6a44e80`
**Package:** [`results/v4_review/v4_2b_span_controlled_corrective_closeout/`](../../../../results/v4_review/v4_2b_span_controlled_corrective_closeout/)
**Work packages closed:** V4-220 through V4-229
**Contract:** 17 unique span cases; geometry `17 × 33 × 33 × 3 = 55,539` rows; 10 common-physical tasks; 170 case-task cells
**Later drafting:** Sprint V4.3 does not reopen this package and is not activated here.

## What closed

Sprint V4.2B applied the frozen V3.6D output mounts exactly once, compiled one
final paired lattice before Dijkstra/A*, classified `+inf` as unavailable local
motion while `NaN`/`-inf`/negative costs fail closed, and generated the
canonical package from a clean implementation commit. V4.2 and V4.2A remain
immutable historical diagnostics. This package is the downstream span-family
snapshot source.

Review of the generated artifact is in
[`V4_2B_CANONICAL_EVIDENCE_REVIEW.md`](V4_2B_CANONICAL_EVIDENCE_REVIEW.md).
Recorded counts include 55,539 geometry rows, 0 geometry typed failures, 0
silent drops, 2,720 planning rows, 680 typed `ompl_unavailable` rows, and 12
typed lattice `invalid` rows. Those figures are descriptive.

## Authorization

`ACTIVE_SPRINT.md` returns to **no code authorization**. Activating Sprint V4.3
or residual V3.7 requires a separate reviewed change. V4.2B completion does
not authorize later sprints.
