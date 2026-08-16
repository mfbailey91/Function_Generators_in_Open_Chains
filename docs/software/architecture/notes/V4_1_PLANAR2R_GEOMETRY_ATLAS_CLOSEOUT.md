# V4.1 planar-2R intrinsic geometry atlas closeout

**Disposition:** generated; non-inferential retained evidence
**Implementation / generation revision:** `c2e44524e3502589dd6848d31477dfdb0a04bb54` (working tree also contains V4-100–V4-108 source at generation time)
**Atlas package:** [`results/v4_review/v4_1_planar2r_geometry_atlas/`](../../../../results/v4_review/v4_1_planar2r_geometry_atlas/)
**Config digest:** `6cf6abf50418f84f2c779d8cd7987f882e6f12454ab053fe3a06decd2a8ca1ac`
**Work packages closed:** V4-100 through V4-108
**Grid:** \(33\times 33\) shared \(Q\) (1089 samples, 3267 rows, 0 failed)

## Review conclusion

Sprint V4.1 consumes the V4.0 geometry kernel over one frozen shared-\(Q\) grid for:

- the canonical crank-rocker \(a=1,b=2.5,c=2,d=2\);
- its span-matched affine gearbox;
- identity-on-shared-\(Q\) as a null control, not a ranked competitor.

Every atlas row is a V4.0 `geometry_snapshot`. Rank attribution distinguishes \(J_g\), \(J_f\), and \(J_{xu}\). The HTML states **intrinsic geometry atlas; no mechanism performance inference.** Frozen V3 packages and the V4.0 smoke package were not rewritten.

## V4.0 carryover (unchanged)

- `state_tolerance` pass-through remains deferred.
- `pullback_metric` SPD tightening remains deferred until before V4.4.
- Independent finite-difference helpers remain test-only (`tests/v4/jacobian_finite_difference.py`).

## Authorization

`ACTIVE_SPRINT.md` returns to **no code authorization**. Activating Sprint V4.2 or residual V3.7 requires a separate reviewed change. V4.1 completion does not authorize later sprints.
