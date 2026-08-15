# Kinematic Transmission Geometry

- **Status:** accepted theory framing for the planned Version 4 research program
- **Software authority:** none by itself; implementation is governed by ADR-027 and an explicitly activated sprint
- **Initial experimental scope:** planar 2R open chain with certified monotonic gearbox and four-bar transmission branches

## 1. Terminology

A **kinematic transmission** is the physical mechanism that maps actuator-side coordinates into the generalized coordinates used to describe relative motion between robot links.

A **transmission map** is its mathematical input-output relation:

\[
q=g(u)
\]

or, for several inputs and outputs,

\[
\mathbf q=g(\mathbf u).
\]

A **function generator** is the classical mechanism-theory role played by the transmission: its geometry generates a selected relationship between input and output motion.

The terms therefore have different jobs:

- **kinematic transmission** names the physical object;
- **transmission map** names its mathematical representation;
- **function generator** names what the mechanism does;
- **kinematic transmission geometry** names the geometry induced by that map in planning, velocity, force, and continuous motion generation.

The informal phrase **inequality mechanism** may remain useful when emphasizing that equal actuator increments acquire unequal output significance. It is not required as the formal class name.

## 2. The complete kinematic chain

The project preserves three spaces:

\[
\mathcal U
\xrightarrow{\;g\;}
\mathcal Q
\xrightarrow{\;f\;}
\mathcal X.
\]

Here:

- \(\mathcal U\) is actuator or mechanism-input configuration space;
- \(\mathcal Q\) is link-side output-joint configuration space;
- \(\mathcal X\) is Cartesian task space;
- \(g\) is the kinematic transmission map;
- \(f\) is open-chain forward kinematics.

For a single link-joint module, the local description is

\[
u
\xrightarrow{\;g\;}
q
\xrightarrow{\;\mathcal S\;}
G,
\]

where \(\mathcal S\) defines the permitted screw motion of the output pair, \(q\) parameterizes progress through that motion, and \(g\) defines how actuator motion traverses the output coordinate.

A direct revolute drive is the identity case:

\[
q=u.
\]

A fixed gearbox is an affine case:

\[
q=ru+b.
\]

A four-bar follower is nonlinear:

\[
q=\psi(u).
\]

A grounded single-input, single-output gearbox and a regular single-input four-bar branch are both one-degree-of-freedom mechanisms. Replacing the identity transmission with a nonlinear one does not add a robot degree of freedom; it changes the generated relationship between actuator and output motion.

## 3. Why the transmission often disappears

Conventional robot kinematics commonly begins at the generalized coordinate \(q\). A constant gearbox ratio can be absorbed into a reflected actuator coordinate, so the rigid kinematic equation can be written as though the controller commands \(q\) directly.

That coordinate choice is often harmless when the only question is link pose. It does not make the physical transmission irrelevant. The ratio remains consequential for actuator speed, actuator torque, reflected inertia, encoder resolution, limits, friction, and compliance.

A nonlinear, coupled, bounded, singular, or noninjective map cannot be globally removed while preserving actuator meaning. The present framework therefore restores the transmission layer rather than replacing conventional kinematics.

## 4. The transmission configuration manifold

A mechanism may be defined implicitly by its constraints:

\[
\mathcal C_m
=
\left\{
(u,q)\in\mathcal U\times\mathcal Q:
F_m(u,q)=0
\right\}.
\]

For a one-mobility transmission, \(\mathcal C_m\) is a one-dimensional curve embedded in the joint coordinate product \(\mathcal U\times\mathcal Q\).

For a fixed gearbox,

\[
F_G(u,q)=q-ru-b=0,
\]

so the input-output curve is affine.

For a four-bar,

\[
F_F(u,q)=0
\]

is a nonlinear loop-closure curve. On a regular branch, the implicit-function theorem gives

\[
q=g(u),
\qquad
\frac{dq}{du}=-\frac{F_u}{F_q}.
\]

This viewpoint makes several phenomena geometric rather than exceptional:

- a monotonic operating branch is a regular graph over \(u\);
- a follower reversal is a projection singularity;
- multiple actuator preimages are folds of the configuration curve under projection into \(Q\);
- assembly branches are distinct components or sheets of the mechanism configuration set.

## 5. Tangent maps: velocity pushforward

Differentiate the transmission:

\[
\dot{\mathbf q}
=
J_g(\mathbf u)\dot{\mathbf u},
\qquad
J_g=\frac{\partial g}{\partial \mathbf u}.
\]

Differentiate forward kinematics:

\[
\dot{\mathbf x}
=
J_f(\mathbf q)\dot{\mathbf q}.
\]

The actuator-to-task Jacobian is therefore

\[
\boxed{
J_{xu}(\mathbf u)
=
J_f(g(\mathbf u))J_g(\mathbf u)
}
\]

and

\[
\dot{\mathbf x}=J_{xu}\dot{\mathbf u}.
\]

The transmission changes local Cartesian velocity capability even when the open-chain link geometry \(f\) is unchanged.

## 6. Cotangent maps: force and gradient pullback

A Cartesian wrench \(\mathbf F\) pulls back to output-joint effort as

\[
\boldsymbol\tau_q=J_f^\mathsf T\mathbf F.
\]

The output-joint effort then pulls back through the transmission:

\[
\boxed{
\boldsymbol\tau_u
=
J_g^\mathsf T\boldsymbol\tau_q
=
J_{xu}^\mathsf T\mathbf F.
}
\]

A scalar potential follows the same transpose chain. For \(\Phi_X(\mathbf x)\),

\[
\boxed{
\nabla_u(\Phi_X\circ f\circ g)
=
J_g^\mathsf T J_f^\mathsf T\nabla_x\Phi_X.
}
\]

Static forces and potential gradients share this mathematical structure because both are covectors.

## 7. Metrics and mobility

Let actuator motion be measured with a positive-definite weight \(W_u\):

\[
 ds_U^2=d\mathbf u^\mathsf T W_u d\mathbf u.
\]

On a regular square branch,

\[
 d\mathbf u=J_g^{-1}d\mathbf q.
\]

Actuator travel expressed on output-joint space is therefore

\[
\boxed{
M_Q^{(U)}
=
J_g^{-\mathsf T}W_uJ_g^{-1}
}
\]

such that

\[
 ds_U^2
=
 d\mathbf q^\mathsf T M_Q^{(U)}d\mathbf q.
\]

The dual mobility field is

\[
\boxed{
B_Q^{(U)}
=
J_gW_u^{-1}J_g^\mathsf T.
}
\]

When \(J_g\) is square and full rank,

\[
B_Q^{(U)}=
\left(M_Q^{(U)}\right)^{-1}.
\]

The metric answers:

> How actuator-expensive is a local output displacement?

The mobility answers:

> How much output motion is generated by a unit actuator-space descent or velocity command?

Neither quantity is inherently good or bad. Application requirements determine whether a local direction should be mechanically cheap, mechanically precise, high speed, or high force.

## 8. Singularities are first-class results

The initial Version 4 geometry kernel must not hide rank loss with an undocumented pseudoinverse.

At a rank-deficient transmission state:

- the forward velocity map \(J_g\) remains meaningful;
- the mobility \(J_gW_u^{-1}J_g^\mathsf T\) remains positive semidefinite;
- the inverse actuator metric is not finite in all output directions;
- inverse instantaneous kinematics may be infeasible or ill-conditioned;
- a potential gradient may produce no actuator command in a blocked output direction;
- static mechanical advantage may approach an ideal singular limit.

The software must report rank, singular values, tolerances, and the operation that failed. Pseudoinverse-based behavior may be added later only under an explicitly named regularization policy.

## 9. The four fundamental columns

### 9.1 Global planning and cost-to-go

The transmission affects:

- physical state topology and preimages;
- actuator path length;
- edge and local-motion cost;
- cost-to-go geometry;
- planner effort and selected goal state.

The existing graph, direct-planner, roadmap, tree, and OMPL work belongs to this column.

### 9.2 Inverse instantaneous kinematics and velocity capability

The central map is

\[
\dot{\mathbf x}=J_{xu}\dot{\mathbf u}.
\]

Minimum actuator-rate inverse kinematics is

\[
\dot{\mathbf u}^{*}
=
\arg\min_{\dot{\mathbf u}}
\frac12\dot{\mathbf u}^\mathsf TW_u\dot{\mathbf u}
\]

subject to a Cartesian velocity task. Expressed in \(Q\), this is a metric-weighted problem using \(M_Q^{(U)}\).

The initial 2R case exposes rate demand, conditioning, directional velocity limits, damping behavior, and saturation. Redundancy and null-space selection require the later 3R extension and must not be claimed from 2R alone.

### 9.3 Static wrench capability

Given actuator effort limits \(\mathcal T_u\), the feasible Cartesian wrench set is

\[
\mathcal W_x(q)
=
\left\{
\mathbf F:
J_{xu}(q)^\mathsf T\mathbf F\in\mathcal T_u
\right\}.
\]

The 2R planar case permits exact force polygons, directional wrench margins, and clean attribution of capability loss to \(J_g\), \(J_f\), or their composite.

### 9.4 Potential fields and continuous flow

For a potential \(\Phi_Q(q)\), Euclidean actuator-space descent gives

\[
\dot{\mathbf u}
=-W_u^{-1}J_g^\mathsf T\nabla_q\Phi_Q,
\]

and therefore

\[
\boxed{
\dot{\mathbf q}
=-B_Q^{(U)}\nabla_q\Phi_Q.
}
\]

For a Cartesian potential,

\[
\dot{\mathbf x}
=-J_{xu}W_u^{-1}J_{xu}^\mathsf T\nabla_x\Phi_X.
\]

A covariant control must also be included. On a regular invertible branch, a Riemannian gradient using the pulled-back metric can cancel pure coordinate reparameterization. That control distinguishes physical actuator weighting from artifacts caused only by a change of coordinates.

## 10. Application-conditioned interpretation

Every column follows the same evidence ladder:

\[
\boxed{
\text{intrinsic transmission atlas}
\rightarrow
\text{application task distribution}
\rightarrow
\text{solver or controller}
\rightarrow
\text{paired outcome metrics}
}
\]

The intrinsic atlas describes the mechanism without judging it. The application distribution defines what the robot must do. The solver or controller consumes the geometry. Paired outcome metrics then determine whether a redistribution of capability is useful for that application.

Examples include:

- rapid free-space transit followed by precise terminal capture;
- Cartesian tracking under actuator-rate limits;
- holding or pushing in preferred directions;
- reactive docking or obstacle avoidance;
- choosing a terminal state with useful force or resolution margin.

No nonlinear transmission is globally better. A low-gain region may improve resolution and force while increasing actuator-rate demand and slowing reactive flow. The trade is the result, not a defect in the experiment.

## 11. Initial planar-2R role

The planar 2R robot remains the controlled exploratory system because it provides:

- analytic forward and inverse kinematics;
- a square composite Jacobian that is easy to inspect;
- exact visualization in \(U\), \(Q\), and \(X\);
- exact or near-exact controls for velocity and force sets;
- low-cost dense atlases and paired Monte Carlo;
- continuity with the existing planning evidence.

Its limits must remain explicit:

- it does not expose redundant inverse-kinematics null spaces;
- planar wrenches are not full spatial wrenches;
- rigid kinematics omits friction, compliance, inertia, and dynamics;
- certified monotonic branches omit multiple-preimage topology.

The purpose of the 2R program is to validate the common geometry and causal interpretation before increasing dimension or physical complexity.

## 12. Working statement of the theory

> An open-chain manipulator is actuated through kinematic transmissions. Each transmission generates a map from actuator coordinates to link-side joint coordinates. Conventional fixed ratios are often absorbed into coordinate scaling, causing this layer to disappear from pure pose kinematics. Restoring the map reveals a common geometry that governs distance, velocity, inverse kinematics, force transmission, potential flow, sampling, and local resolution. The mechanism does not merely move the joint; it defines the geometry through which the joint is actuated.
