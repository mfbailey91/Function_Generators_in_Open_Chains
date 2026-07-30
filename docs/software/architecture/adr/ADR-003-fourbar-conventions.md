# ADR-003 — Planar Four-Bar Conventions

**Status:** Accepted

## Context

Version 1 compares gearboxes with planar four-bar function generators. Freudenstein forms and open/crossed branch labels vary across textbooks. The software must freeze one convention so Jacobians, preimages, and branch tracking stay consistent.

## Decision

### Geometry

Links are crank \(a\), coupler \(b\), follower \(c\), and ground \(d\), all strictly positive and finite. Input crank angle \(u=\theta_2\) and follower angle \(q=\theta_4\) are measured from the grounded base, matching the paper vector loop

\[
a e^{iu}+b e^{i\theta_3}=d+c e^{iq}.
\]

### Freudenstein form

\[
K_1=\frac{d}{a},\qquad
K_2=\frac{d}{c},\qquad
K_3=\frac{a^2-b^2+c^2+d^2}{2ac},
\]

\[
F(u,q)=K_1\cos q-K_2\cos u+K_3-\cos(u-q)=0.
\]

### Algebraic branches

Rewrite \(F=0\) as \(A\sin q+B\cos q=C\) with

\[
A=-\sin u,\qquad
B=K_1-\cos u,\qquad
C=K_2\cos u-K_3.
\]

Let \(R=\sqrt{A^2+B^2}\) and \(\phi=\mathrm{atan2}(A,B)\). When \(|C|\le R\),

\[
q_{+}=\phi+\arccos(C/R),\qquad
q_{-}=\phi-\arccos(C/R).
\]

- `branch=+1` selects \(q_{+}\) (open algebraic sheet).
- `branch=-1` selects \(q_{-}\) (crossed algebraic sheet).

Forward evaluation always uses the configured algebraic branch. Continuous tracking along a crank path unwraps successive follower samples on that same sheet so artificial \(\pm 2\pi\) jumps do not appear.

### Jacobian

\[
\frac{dq}{du}=\frac{K_2\sin u+\sin(u-q)}{K_1\sin q+\sin(u-q)}.
\]

Near change points the denominator vanishes; `output_jacobian` raises `ValueError`.

### Preimages

Given target follower \(q\), solve the dual trig equation for crank angles \(u\). All finite solutions in one fundamental period \([0,2\pi)\) are returned (typically zero or two for a crank-rocker).

### Independent joints

A planar 2R uses `IndependentFourBars`: one planar four-bar per actuator axis with a diagonal Jacobian.

## Consequences

- Tests compare analytic Jacobians to central finite differences on the frozen form.
- Changing Freudenstein signs or branch labels requires updating this ADR and revalidating IM-004–IM-007.
