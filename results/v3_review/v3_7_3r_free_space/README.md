# Sprint V3.7 — Planar 3R Free-Space Evidence

- bank: `free_space_planar3r_v1`
- implementation revision: `a65de24c8ec184b2812714855b656f815c621701`
- rows: 504
- OMPL solve time (s): 0.5

Position-only and full-pose estimands are summarized separately.
Dense 3D lattice search is diagnostic-only and not an evidence exit criterion.

## Task family `full_pose`

- rows: 196
- `input_linear`: status={'success': 12, 'invalid': 2}, mean J*=0.4658378358420445, mean wall=0.003798930556513369, mean ΔJ(fb−gb)=-0.12506078619726432
- `ompl_prm`: status={'success': 36, 'invalid': 6}, mean J*=0.46583783584204436, mean wall=0.3534569965300357, mean ΔJ(fb−gb)=-0.12506078619726432
- `ompl_rrt_connect`: status={'success': 36, 'invalid': 6}, mean J*=0.7400734184368745, mean wall=0.013901527654120905, mean ΔJ(fb−gb)=-0.101003145126816
- `output_linear`: status={'success': 12, 'invalid': 2}, mean J*=0.4658634705905214, mean wall=0.06565531933059295, mean ΔJ(fb−gb)=-0.1250095167003104
- `prm`: status={'success': 36, 'invalid': 6}, mean J*=0.46583783584204436, mean wall=0.3664251886980815, mean ΔJ(fb−gb)=-0.1250607861972643
- `rrt_connect`: status={'success': 36, 'invalid': 6}, mean J*=0.8471836050007264, mean wall=0.004239964150151031, mean ΔJ(fb−gb)=-0.11057289350228777

## Task family `position_only`

- rows: 308
- `input_linear`: status={'success': 20, 'invalid': 2}, mean J*=0.37463486653764944, mean wall=0.06798819793621078, mean ΔJ(fb−gb)=-0.09307379539569188
- `ompl_prm`: status={'success': 60, 'invalid': 6}, mean J*=0.3746348665376496, mean wall=6.705899059625032, mean ΔJ(fb−gb)=-0.09307379539569188
- `ompl_rrt_connect`: status={'success': 60, 'invalid': 6}, mean J*=1.0257246808987257, mean wall=0.036590448549638194, mean ΔJ(fb−gb)=-0.15119265125502807
- `output_linear`: status={'success': 20, 'invalid': 2}, mean J*=0.3746473625952153, mean wall=1.2875851083663292, mean ΔJ(fb−gb)=-0.0930488032805601
- `prm`: status={'success': 60, 'invalid': 6}, mean J*=0.3746348665376496, mean wall=1.3120561090142777, mean ΔJ(fb−gb)=-0.09307379539569187
- `rrt_connect`: status={'success': 60, 'invalid': 6}, mean J*=1.1250687290350572, mean wall=0.02546692218553896, mean ΔJ(fb−gb)=-0.14816819629686087

