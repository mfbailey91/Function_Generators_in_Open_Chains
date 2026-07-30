# V2.2 Branch Certification Audit

Sprint: `docs/software/planning/sprints/v2/SPRINT_V2_2_OPERATING_BRANCHES.md`
ADRs: ADR-011 (output-space semantics), ADR-014 (output-state identity on
invertible branches)

## Scope

This audit documents the `OperatingBranch` abstraction introduced in
`src/inequality_mechanisms/mechanisms/operating_branch.py` and the four-bar
selector in `src/inequality_mechanisms/mechanisms/branch_selection.py`: what
certification checks, what it does not check, how the branch-local inverse
is computed, and how a branch is serialized and identified. It does not
change `Mechanism` or `Mechanism.inverse_output` (ADR-001 all-preimages
semantics, unchanged) and does not build Version 2 graphs.

## Certification is evidence, not proof

`certify_branch` samples a deterministic Cartesian grid of
`certification_samples_per_axis` points per input axis (default `9` for
affine branches, `17` for four-bar branches) and checks, at every sample:

1. **Assembly** — `mechanism.valid_input(u)` holds.
2. **Finiteness** — the sampled input, forward output, Jacobian, and
   recovered input/output are all finite.
3. **Output-chart containment** — the canonicalized output
   `output_space.canonicalize(q)` lies within the configured chart bounds
   (within `1e-9` floating-point slack); otherwise the chart is treated as
   ambiguous for this branch and rejected.
4. **Axis separability** — the sampled Jacobian's off-diagonal magnitude is
   below `1e-8`; a coupled (nonseparable) Jacobian is rejected rather than
   silently treated as diagonal.
5. **Derivative sign consistency** — every sampled `dq_i/du_i` has the same
   sign as the sign implied by the branch's input endpoints; any sign flip
   (a hidden reversal at the sample resolution) is rejected.
6. **Gain bounds** — every sampled `|dq_i/du_i|` is `>= min_abs_gain`
   (default `1e-9` for affine, configurable per selector for four-bar) and,
   if `max_abs_gain` is set, `<= max_abs_gain`.
7. **Round-trip residuals** — at every sample, the branch-local inverse is
   evaluated on the sample's own output (`u_recovered = inverse(q)`), and
   the branch-local forward map is re-evaluated on that recovered input
   (`q_recovered = forward(u_recovered)`). Both
   `max |u_recovered - u|` (forward-then-inverse) and
   `max |q_recovered - q|` (inverse-then-forward) must be `<= residual_tol`.
8. **Endpoint consistency** — the certified output box
   (`output_lower`/`output_upper`) is the achieved min/max of the sampled
   grid, not an assumed value.

**What this does not prove:** because the grid is finite, a reversal,
coupling, or gain violation that occurs strictly *between* two adjacent
sample points is not detected. Certification is deterministic, repeatable
evidence at a chosen sample density — increasing
`certification_samples_per_axis` raises confidence but never produces a
closed-form guarantee. This is stated in the `BranchCertificate` and
`certify_branch` docstrings as well.

Periodic output axes (`AxisTopology.PERIODIC_REVOLUTE`) are rejected
outright in `certify_branch`: an operating branch is defined to be
nonperiodic and to stay inside a single bounded chart (ADR-014), so a
periodic chart is a configuration error, not a certifiable branch.

## Branch-local inverse strategies

`OperatingBranch.inverse` never calls `Mechanism.inverse_output`. It uses
one of two per-axis strategies, chosen by the factory that built the
branch:

- **`AffineAxisInverse`** (`kind="affine"`): exact closed form,
  `u_i = u_ref + (q_i - q_ref) / ratio`, for constant-gain (affine)
  mechanisms (`UnitGearbox`, `FixedRatioGearbox`, `EquivalentGearbox`). No
  root solve; the only residual is floating-point round-off.
- **`MonotoneTableAxisInverse`** (`kind="monotone_table"`): a precomputed,
  strictly monotone `(u, q)` table (built at selection time from the
  mechanism's own follower curve) seeds a bracket via `searchsorted`, then
  an in-house bracketed bisection (`_bisect_root`, no SciPy) refines the
  root against the *true* scalar forward map at call time. Deterministic
  given `tol` and `max_iter`; the caller (`certify_branch` or
  `OperatingBranch.inverse`) always re-checks the residual after solving.

Both strategies operate on one axis at a time with the other axes held
fixed, which is only meaningful because certification has already rejected
coupled (nonseparable) Jacobians — see "Axis separability" above.

## Four-bar branch selection (`branch_selection.py`)

`select_fourbar_monotonic_branch` builds a certified branch from an
existing continuous four-bar follower curve, per independent axis:

1. The Freudenstein algebraic branch (`PlanarFourBar.branch`, `+1`/`-1`) is
   fixed at four-bar construction time and is **not** re-selected here;
   "one fixed assembly mode" refers to that existing choice.
2. Candidate monotonic crank intervals are found by reusing
   `mechanisms.monotonic.find_monotonic_sectors` (Sprint Four) unchanged.
3. The selected interval is shrunk by `endpoint_margin_fraction` at both
   ends, moving away from the near-zero-gain sector boundary.
4. The follower curve is unwrapped (`follower_curve(..., unwrap=True)`,
   continuous, not principal-value) over the shrunk interval and
   canonicalized into a dedicated `AxisTopology.BOUNDED_REVOLUTE`
   `OutputSpace` chart sized exactly to the achieved range. This is what
   lets a branch whose raw output crosses the `±π` principal-value seam
   remain continuous in its own chart (ADR-011's `lift_bounded_revolute`
   handles the wrap; see `tests/operating_branches/test_fourbar_branches.py`
   for a seam-crossing regression case).
5. Strict derivative sign consistency across the interpolation table is
   verified; any sign change (reversal) inside the interval is rejected
   before certification even runs.
6. `certify_branch` is run against a nonperiodic copy of the mechanism
   (`periodic=False` on every axis, via `open_axis_independent_fourbars`),
   which also rejects gain too close to `min_abs_gain`.

The resulting `OperatingBranch`'s underlying mechanism never uses
full-cycle wraparound.

## Serialization and branch IDs

`OperatingBranch.to_dict()` / `from_dict()` serialize the underlying
mechanism, the output chart, the per-axis inverse strategies, the selector
metadata (method name and parameters), the runtime residual tolerance, and
the certificate. `from_dict` reconstructs the stored certificate directly;
it does not recertify, so a deserialized branch's certificate remains
evidence attached to its original sampling run.

`OperatingBranch.branch_id` is a SHA-256 hex digest of a canonical JSON
payload (`sort_keys=True`, fixed separators) built from the mechanism,
output chart, axis-inverse parameters, selector metadata, residual
tolerance, and certification method/density/input-bounds — deliberately
excluding the achieved certificate values (gains, residuals, output
bounds), so the ID identifies *how the branch was specified*, not the
floating-point outcome of a particular certification run.

## Known limitations / deviations from the sprint sketch

- The sprint's `OperatingBranch.to_dict()` sketch does not show a
  `from_dict` counterpart explicitly but says "from_dict / certify factory
  helpers as needed" — both `OperatingBranch.from_dict` and
  `BranchCertificate.from_dict` were added to support the required
  serialization round-trip tests.
- `certify_branch` and the factories accept `max_abs_gain=None` (unbounded)
  by default; only `min_abs_gain` is required, matching "gain above an
  optional configured maximum" in the sprint's failure-behavior list.
- Coupling rejection uses an absolute off-diagonal-magnitude tolerance
  (`1e-8`) rather than a relative one, since axis-separable branches in
  this sprint (gearboxes, independent four-bars) have Jacobians with
  well-scaled diagonal entries; a relative tolerance may be needed if a
  future branch type has widely varying per-axis gain magnitudes.
