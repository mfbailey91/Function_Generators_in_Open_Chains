# Static Wrench Capability from Kinematic Geometry

**Status:** method contract for V3.6E–V3.6F; V3.6E implemented, V3.6F atlas authorized separately
**Scope:** planar 2R, rigid, ideal, gravity-free, normalized actuator torque limits
**Kernel rule:** on this branch, \(J_g\), \(J_f\), \(J_{xu}\), rank, metric, and virtual-power identities come from V4.0 `inequality_mechanisms.transmission_geometry` ([ADR-027](../adr/ADR-027-v4-kinematic-transmission-geometry.md)). This note specifies the gravity-free static wrench set and atlas views; it does not authorize a second Jacobian implementation. Version 4 wrench software, if later activated, remains Sprint V4.3.

## 1. Purpose

This method adds no dynamic state and no gravity model. It asks what static Cartesian force vectors are compatible with declared actuator torque limits at a fixed physical mechanism state.

The result follows from the same two maps already central to the project:

\[
\mathcal U\xrightarrow{g}\mathcal Q\xrightarrow{f}\mathcal X.
\]

The mechanism map determines how actuator motion reaches the output joints. The serial-arm map determines how joint motion reaches the endpoint. Virtual work provides the dual effort map.

## 2. Differential kinematics

Let

\[
q=g(u),\qquad x=f(q).
\]

Then

\[
\dot q=J_g(u)\dot u,
\qquad
\dot x=J_f(q)\dot q,
\]

so

\[
\dot x=J_{xu}(u)\dot u,
\qquad
J_{xu}(u)=J_f(g(u))J_g(u).
\]

For independent scalar transmissions,

\[
J_g(u)=\operatorname{diag}
\left(\frac{dq_1}{du_1},\frac{dq_2}{du_2}\right).
\]

## 3. Virtual work and effort mapping

For an endpoint force

\[
w=\begin{bmatrix}F_x\\F_y\end{bmatrix},
\]

ideal virtual work gives

\[
\tau_u^\mathsf T\delta u=w^\mathsf T\delta x.
\]

Since

\[
\delta x=J_{xu}\delta u,
\]

we obtain

\[
\boxed{\tau_u=J_{xu}^\mathsf T w}
\]

or, decomposed by layer,

\[
\boxed{\tau_u=J_g^\mathsf T J_f^\mathsf T w}.
\]

The intermediate joint torque is

\[
\tau_q=J_f^\mathsf T w,
\]

and the mechanism maps it to actuator torque through

\[
\tau_u=J_g^\mathsf T\tau_q.
\]

This is why the field can be described from a **kinematic geometry perspective**: the Jacobians are geometric differentials, while virtual work supplies their transpose action on covectors.

## 4. Actuator torque box and exact force set

Declare symmetric actuator limits

\[
-\bar\tau_i\le\tau_{u,i}\le\bar\tau_i.
\]

V1 uses

\[
\bar\tau_u=[1,1]^\mathsf T
\]

in normalized units.

Let

\[
A=J_{xu}^\mathsf T.
\]

The exact force set is the intersection of actuator slabs:

\[
\boxed{
\mathcal W(u)=\{w:-\bar\tau_u\le Aw\le\bar\tau_u\}.
}
\]

This H-representation remains valid at regular and singular states.

When `A` is nonsingular, the torque box corners map to four force vertices:

\[
w_s=A^{-1}s,
\qquad
s_i\in\{-\bar\tau_i,+\bar\tau_i\}.
\]

The regular 2R force set is therefore a centrally symmetric parallelogram. A fixed-ratio gearbox changes it by a constant transmission scale. A four-bar changes it over configuration through `J_g(u)`.

## 5. Directional capacity

For a unit direction `d`, seek the largest nonnegative magnitude such that

\[
\alpha d\in\mathcal W.
\]

Each actuator inequality gives

\[
\alpha|a_i^\mathsf Td|\le\bar\tau_i,
\]

so

\[
\boxed{
\alpha^*(d)=
\min_{i:\,|a_i^\mathsf Td|>\epsilon}
\frac{\bar\tau_i}{|a_i^\mathsf Td|}.
}
\]

When every denominator is zero, the rigid ideal model reports an unbounded direction. That status must not be described as infinite practical strength.

Initial directions are:

\[
d_x=[1,0]^\mathsf T,
\qquad
d_y=[0,1]^\mathsf T.
\]

For endpoint position `x` away from the base origin,

\[
d_r=\frac{x}{\|x\|},
\qquad
d_t=\begin{bmatrix}-d_{r,y}\\d_{r,x}\end{bmatrix}.
\]

## 6. Primary scalar: centered isotropic capacity

The radius of the largest origin-centered Euclidean force disk inside the exact set is

\[
\boxed{
r_{\mathrm{iso}}
=
\min_{i:\,\|a_i\|_2>\epsilon}
\frac{\bar\tau_i}{\|a_i\|_2}.
}
\]

This equals the minimum directional capacity over all unit directions. It is the primary scalar heatmap because it answers:

> What force magnitude can the ideal arm generate in every planar direction at this configuration, under the normalized actuator box?

It does not answer payload capacity, safety, structural strength, or biological strength.

## 7. Singular and near-singular states

At rank loss, the H-representation can become unbounded along a Cartesian direction that produces no actuator virtual work. The rigid kinematic model has no link compliance, bearing capacity, or buckling limit to bound that direction.

Required statuses distinguish:

- `regular`;
- `near_singular`;
- `rank_deficient`;
- `unbounded_ideal_direction`;
- `invalid_mechanism_state`.

Source values remain unclipped. Plots may use display limits only when the mask and unclipped value are retained.

## 8. Mechanism endpoints and ideal mechanical advantage

For a scalar transmission,

\[
\tau_q=\frac{\tau_u}{dq/du}.
\]

As a rocker approaches reversal,

\[
|dq/du|\rightarrow0,
\]

so ideal output torque amplification and output resolution rise while output speed and infinitesimal motion authority fall. The same geometry can therefore produce an apparently high static-capability region and a near-toggle warning at the same location.

The atlas must expose both facts. It may not label the exact reversal as a superior operating point.

## 9. Relation to `actuator_metric_on_q`

The motion metric already used in the V3.6C audit is

\[
M_Q^{(U)}
=J_{g^{-1}}^\mathsf TJ_{g^{-1}}
=J_g^{-\mathsf T}J_g^{-1}.
\]

It satisfies

\[
ds_U^2=dq^\mathsf TM_Q^{(U)}dq.
\]

Under a Euclidean actuator-torque ball, the ideal joint-torque ellipsoid is dual:

\[
\tau_q^\mathsf T\left(M_Q^{(U)}\right)^{-1}\tau_q\le1.
\]

Thus directions that are locally expensive in actuator travel correspond, under the idealized dual norm, to larger joint-torque axes. The exact V3.6E method nevertheless uses the actuator torque **box**, because independent actuator limits map to a polytope rather than an ellipsoid.

## 10. Configuration-space evaluation

For every shared Q-grid point in a span case:

1. verify Q is inside the common usable interval;
2. inverse-lift Q to the mechanism-specific U state;
3. compute `J_g(u)`;
4. compute `J_f(q)`;
5. form `J_xu=J_f@J_g`;
6. construct the H-representation;
7. classify rank/status;
8. compute regular vertices where defined;
9. compute `r_iso` and named directional capacities;
10. serialize unclipped values and diagnostic margins.

Four-bar and matched gearbox use the same Q grid and actuator torque limits.

## 11. Scope boundary

The initial field excludes:

- gravity and payload weight;
- acceleration and inertia;
- Coriolis/centrifugal effects;
- contact friction and environmental constraints;
- motor thermal/current-duration limits;
- transmission efficiency;
- compliance, backlash, and friction;
- link, bearing, pin, tendon, or bone strength;
- passive torques and muscle force-length/force-velocity effects.

A gravity-aware model would shift or otherwise alter available actuator margin and is not a transparent extension of the present normalized field. It requires a new named method and ADR.

## 12. Literature position

Force polytopes and force ellipsoids are established robot-capability representations. The present contribution is not the invention of the force polytope. It is the explicit composition of that static capability map with the project’s actuator-to-joint function generator and its presentation over the same configuration-space corpus used to study mechanism-induced planning geometry.

Key starting references:

- P. Chiacchio, Y. Bouffard-Vercelli, and F. Pierrot, “Force polytope and force ellipsoid for redundant manipulators,” *Journal of Robotic Systems*, 14(8), 613–620, 1997. DOI: `10.1002/(SICI)1097-4563(199708)14:8<613::AID-ROB3>3.0.CO;2-P`.
- R. Orsolino et al., “Application of Wrench-Based Feasibility Analysis to the Online Trajectory Optimization of Legged Robots,” *IEEE Robotics and Automation Letters*, 2018. DOI: `10.1109/LRA.2018.2836441`.
