# V4.2B Corrective Program Amendment

- **Status:** accepted planning amendment; no code authorization
- **Prepared against:** `db398268bf2de7efc8ca7ab33e49d787c8b4cef4` on `Version_4_Kinematic_Transmission_Geometry`
- **Amends:** `V4_POST_V4_1_SPAN_WRENCH_PROGRAM.md` and the Version 4 sprint sequence
- **Decision owner:** `ACTIVE_SPRINT.md`

## Amendment

The post-V4.1 sequence is amended from

\[
\text{V4.2}\rightarrow\text{V4.3}
\]

to

\[
\boxed{
\text{closed V4.2/V4.2A historical evidence}
\rightarrow
\text{V4.2B corrective closeout}
\rightarrow
\text{V4.3 intrinsic wrench}
}
\]

V4.2B corrects the span-family consumer and retained-evidence contracts before any force-set calculation uses the span snapshots. It does not reopen the frozen V3.6D synthesis campaign and does not overwrite V4.2 or V4.2A.

## Downstream source of truth

After V4.2B closes:

- V4.2 and V4.2A remain immutable historical diagnostic packages;
- V4.2B becomes the canonical mounted-coordinate span snapshot package;
- V4.3 must consume V4.2B snapshot IDs, digests, and mounted Q semantics;
- V4.3 remains separately drafted and requires its own later activation.

## Reserved ranges and fresh roots

```text
V4-220–V4-229  Sprint V4.2B
V4-300–V4-309  Sprint V4.3 (still blocked)
```

```text
results/v4_review/v4_2b_span_controlled_corrective_closeout/
results/v4_review/v4_3_intrinsic_static_wrench/
```

## Frozen lineage

V4.2B may not mutate or silently regenerate:

```text
results/v3_review/
results/v4_review/v4_0_kinematic_geometry_core/
results/v4_review/v4_1_planar2r_geometry_atlas/
results/v4_review/v4_2_span_controlled_geometry_atlas/
results/v4_review/v4_2a_span_controlled_visual_audit/
```

The V3.6D registry digest and `PRIMARY_CERTIFICATE` remain unchanged.

## Authorization

This amendment and the V4.2B planning documents may land in a no-authorization commit. A separate reviewed activation change must name **V4-220–V4-229 only**. V4.3 may not be activated in the same change that closes V4.2B.
