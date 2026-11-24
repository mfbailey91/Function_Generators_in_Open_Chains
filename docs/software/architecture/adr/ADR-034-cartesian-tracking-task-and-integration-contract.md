# ADR-034 — Cartesian tracking task and integration contract

- **Status:** accepted for Sprint V4.4 work package V4-405
- **Applies to:** V4 Column B tracking comparisons that follow the instantaneous velocity atlas
- **Related:** ADR-033 (instantaneous velocity and inverse policies); ADR-029 mounted coordinates; ADR-027 shared geometry
- **Implementation (this package):** frozen contract JSON and loader only; no runner
- **Deferred to V4-406+:** timestep integrator, tracking smoke generation, paired study, and retained tracking evidence

## Context

ADR-033 freezes instantaneous forward capability and explicit inverse/rate policies. It deliberately excludes trajectories, timesteps, feedback laws, and domain-boundary rules. V4-404 retains a full intrinsic velocity atlas on frozen V4.2B snapshots. Tracking comparisons must not invent those missing contracts ad hoc inside a runner, and they must not treat the instantaneous smoke or atlas as a temporal benchmark.

## Decision

### 1. Separate contract identity from instantaneous packages

The tracking contract is schema `v4.4.velocity.tracking.contract.v1`. Instantaneous smoke and atlas packages remain frozen and immutable. The reserved first tracking result root is

```text
results/v4_review/v4_4_velocity_tracking_smoke/
```

V4-405 forbids creating or writing that root. V4-406 may write it only through a fresh-root, clean-source preflight that refuses smoke, atlas, and other predecessor trees.

### 2. Consume the same frozen geometry source

Tracking starts from the same V4.2B source lock used by V4.4 smoke/atlas. Arms are four-bar, span-matched gearbox, and identity on shared Q. Starts are exact retained identities (`case_id`, `q_sample_id`, `grid_index`, snapshot). All three arms share the same physical start Q/X. The initial commanded actuator rate is the zero vector.

### 3. Declared Cartesian task bank in mounted X

The frozen path set is exactly:

| Path id | Geometry in mounted X |
| --- | --- |
| `axis_x` | Segment along \(+\hat e_x\) |
| `axis_y` | Segment along \(+\hat e_y\) |
| `diagonal` | Segment along the unit vector \((1,1)/\sqrt{2}\) |
| `circle_ccw` | Circle centered at the start, counterclockwise |

Path length (or circle radius) at a start sample is

\[
L = r_{\mathrm{iso}}(x_0)\,T
\]

when the local isotropic ray/speed capability \(r_{\mathrm{iso}}\) is finite and positive; otherwise the start remains an eligible sample and the run terminates with a typed outcome rather than being dropped. Task duration is fixed at \(T = 1.0\) in normalized time. This scaling is a local capability convention for regular cells, not a claim that every sample remains feasible for every policy.

### 4. Timing, integration, and refinement

- Base step: \(\Delta t = 0.01\).
- Refinement controls for later runner tests: \(\Delta t/2\) and \(\Delta t/4\).
- Integration: explicit Euler on actuator coordinates using the commanded rate at each step.
- Achieved Cartesian velocity is always the raw stored map image \(J_{xu}\dot u_{\mathrm{commanded}}\). Regularization must not redefine that residual.

### 5. Feedforward, feedback, and inverse reuse

At time \(t\),

\[
v_{\mathrm{ff}}(t)=\dot x_{\mathrm{ref}}(t),\qquad
v_{\mathrm{fb}}(t)=K_p\bigl(x_{\mathrm{ref}}(t)-x(t)\bigr),\qquad
v_{\mathrm{req}}=v_{\mathrm{ff}}+v_{\mathrm{fb}},
\]

with frozen \(K_p = 5.0\). Inverse policies and rate policies are exactly ADR-033:

- IK: `exact`, `minimum_norm`, `damped_least_squares`
- Rate: `report_only`, `uniform_scale`
- Weight: \(W = I\)
- Damping sweep for DLS: `{0.01, 0.05, 0.2}`

The documented factorial is all IK policies × both rate policies × the damping set (damping applies only to DLS). A later tracking smoke may subset that factorial only with an explicit selection record; it may not invent new policies.

### 6. Domain boundary and eligibility

Leaving the certified mounted-Q box, producing a nonfinite state, or encountering an undefined path direction is a typed terminal failure. There is no silent projection or clipping back into the box. Mechanism-specific inability to invert or continue is a retained outcome (`task_ineligible` or ADR-033 policy failure codes), never a silent drop.

### 7. Failure taxonomy

Closed terminal/diagnostic codes for the contract:

| Code | Role |
| --- | --- |
| `ok` | Completed without terminal failure |
| `start_unavailable` | Required start identity missing |
| `snapshot_invalid` | Frozen snapshot fails validation |
| `path_undefined` | Declared path geometry unavailable at the start |
| `integration_nonfinite` | Nonfinite state or command during stepping |
| `domain_boundary_exit` | Left certified mounted-Q domain |
| `exact_unavailable` | Exact IK unavailable (ADR-033) |
| `transmission_rank_deficient` | Inherited rank blocks exact solve |
| `rate_infeasible_report_only` | Diagnostic under `report_only` (not necessarily terminal) |
| `task_ineligible` | Mechanism cannot continue the declared task |
| `refinement_diverged` | Declared refinement criterion failed (runner tests) |

### 8. Metrics declared for later computation

V4-406 must be able to report, without inventing new primary scores here: RMS and peak Cartesian tracking error; peak actuator-rate utilization; residual norms before/after rate scaling; command continuity \(\max\|\Delta\dot u\|\); and the failure/boundary codes above. Instantaneous atlas cells are not substitutes for these temporal metrics.

## Acceptance and consequences

V4-405 is complete when the ADR, frozen JSON contract, loader equality checks, and contract unit tests agree, and when planning docs advance to V4-406 without creating a tracking result tree. V4.5, hardware motor claims, force-model retuning, and regeneration of frozen V4.4 instantaneous packages remain out of scope.
