# Sprint V2.9 evidence summary — U-distance-only shared-Q paired study

**Run id:** `v2_9_shared_q_paired_u_2r`  
**Package:** `results/v2_9_shared_q_paired_u_2r/`  
**Config:** `configs/v2/shared_q_paired_u_2r.yaml`  
**Smoke:** `results/v2_9_shared_q_paired_u_smoke/` (`configs/v2/shared_q_paired_u_smoke.yaml`)  
**Cardinality:** 5 pairs × 3 tasks × 1 cost (`actuator_travel`) × 2 mechanisms = **30** Dijkstra trials; **15** paired comparisons (four-bar vs span-matched); **0** failures.  
**Dashboard:** open `results/v2_9_shared_q_paired_u_2r/index.html` locally.

This run uses **raw** Euclidean actuator distance between attached U states as the only planning cost. There is no \(Q\) term, \(\alpha\), planner-side normalization, or unit-gearbox arm.

## Objective

```yaml
objective:
  cost: actuator_travel
  heuristic: zero   # Dijkstra reference
```

Edge cost: \(c_U^{(m)}(a,b)=\|u_m(q_b)-u_m(q_a)\|_2\).  
Reporting also stores \(\widehat L_U = L_U / \|u_{\max}-u_{\min}\|_2\) as `cost_norm_u` without affecting search.

## Headline results

| Task | Identical Q-paths (FB vs GB) | Mean \|Δ\(L_U\)\| |
| --- | ---: | ---: |
| `cross_range` | 0/5 | 0.787 |
| `joint1_dominant` | 0/5 | 0.475 |
| `joint2_dominant` | 3/5 | 0.486 |
| **All** | **3/15** | — |

Under actuator-only optimization, four-bar and span-matched gearbox almost never share the selected output path on the long diagonal task. Joint-2–dominant tasks sometimes still agree (pairs 01, 04, 05).

## Pair × task detail (four-bar vs span-matched)

| Pair | Task | Same Q-path | Δ expansions (FB−GB) | Δ cost (FB−GB) | \(L_U\) FB | \(L_U\) GB | \(L_Q\) FB | \(L_Q\) GB |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| pair_01 | cross_range | N | 0 | −0.759 | 3.216 | 3.975 | 1.179 | 1.179 |
| pair_01 | joint1_dominant | N | 0 | −0.463 | 2.055 | 2.518 | 0.747 | 0.747 |
| pair_01 | joint2_dominant | Y | 0 | −0.463 | 2.055 | 2.518 | 0.747 | 0.747 |
| pair_02 | cross_range | N | −5 | −0.782 | 3.304 | 4.086 | 1.634 | 1.634 |
| pair_02 | joint1_dominant | N | −5 | −0.477 | 2.111 | 2.588 | 1.035 | 1.035 |
| pair_02 | joint2_dominant | N | −5 | −0.477 | 2.111 | 2.588 | 1.035 | 1.035 |
| pair_03 | cross_range | N | −5 | −0.816 | 3.491 | 4.306 | 1.929 | 1.929 |
| pair_03 | joint1_dominant | N | −4 | −0.498 | 2.230 | 2.728 | 1.222 | 1.222 |
| pair_03 | joint2_dominant | N | −4 | −0.498 | 2.230 | 2.728 | 1.222 | 1.222 |
| pair_04 | cross_range | N | −2 | −0.794 | 3.558 | 4.352 | 1.888 | 1.888 |
| pair_04 | joint1_dominant | N | +1 | −0.472 | 2.210 | 2.682 | 1.012 | 1.012 |
| pair_04 | joint2_dominant | Y | −1 | −0.499 | 2.345 | 2.843 | 1.407 | 1.407 |
| pair_05 | cross_range | N | −3 | −0.786 | 3.403 | 4.189 | 1.648 | 1.648 |
| pair_05 | joint1_dominant | N | −5 | −0.467 | 2.137 | 2.604 | 0.924 | 0.924 |
| pair_05 | joint2_dominant | Y | −1 | −0.493 | 2.219 | 2.711 | 1.182 | 1.182 |

Negative Δ cost means the four-bar path is cheaper in raw actuator travel than the span-matched gearbox on the same shared \(Q\) graph. Several cases keep the same \(L_Q\) while choosing different node sequences (equal output length, different route).

## Interpretation notes

- **Mechanism effect under pure \(U\):** actuator costs separate immediately; 12/15 comparisons select different Q-paths.
- **Task dependence:** joint-2–dominant is the only template with any path agreement (3/5). Cross-range never agrees.
- **Search effort:** expansion deltas are modest (typically 0 to −5). Fewer expansions alone do not imply a better robot.
- **\(Q\)/\(X\) consequences:** output and Cartesian lengths remain reported as non-objective measurements of the actuator-optimal paths.

## Dashboard sections

- Three task sections with five pair columns each
- Metric tables: cost, expansions, raw \(L_U\), reporting \(\widehat L_U\), \(L_Q\), \(L_X\)
- Shared Q/U lattices, \(q(u)\) transmission maps, Q/U/Cartesian path figures
- Paired comparison table (no alpha selector or divergence-onset-by-alpha plot)

## Relation to V2.8

V2.8 evidenced the normalized \(Q/U\) blend and \(\alpha\) sweep (`results/v2_8_shared_q_paired_2r_qu/`). V2.9 isolates the planning-control claim with actuator travel alone on the same five pairs and restores all three task templates.
