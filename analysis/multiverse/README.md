# Multiverse: how the headline numbers move across the post-hoc choices

Decisions O-6 to O-9 (plus the R3 label choice) were all made after seeing results. This folder re-runs the headline numbers over every reasonable combination. Nothing in the pipeline, outputs, research or site was touched. The script reads `work/`, `output/validation.json` and `history/history_comparison.json` read-only.

- `run_multiverse.py` re-runs everything (about 50 s): `analysis/.venv/bin/python analysis/multiverse/run_multiverse.py`
- `multiverse.json` has one row per universe (`universes_2026`, `universes_2028`, `universes_2028_cross`), plus `summary` and `checks`
- `run_log.txt` is the console log of the last run

## Method

**2026 (24 universes = 2 samples × 2 scales × 3 label sets × 2 control sets).** Each universe is a full Gibbs fit: the same `gibbs.run_gibbs` sampler as `03_fit.py`, agnostic preset, t5 likelihood, 4 chains × (1000 warm-up + 2500 draws), Mundlak terms on. The fast OLS-FE/EB path was not needed because each fit takes about 2 s. Rule-label and high-confidence universes switch u_a off, as the 06 R3 rows do. Gap = δ_a vs mainstream liberal, shown as median [10th, 90th] of the posterior, in points on that universe's scale.
- The refit of the published spec (#1) matches `fit_meta` to within 0.03: progressive −0.93 vs −0.94, left populist +1.17 vs +1.16, moderate +1.40 vs +1.40.

**2028 (8 universes = 4 lane sources × 2 π).** All 8 use the published 2026 fit (`work/fit_agnostic.npz`, spec #1). Each runs `reference_engine.v_dist` exactly as `10_validate.headline()` does: the even environment t5(0, 5), the same bank and E seeds, and a generic opponent averaged over MAGA and non-MAGA.
- The blend × current-π universe reproduces the published P(win) exactly: ML 0.4747, progressive 0.4162, left populist 0.4121, moderate 0.5384.
- The two history sources are drawn as in `09_export` (normal, with the 80% interval widened 1.5×):
  - competitive history: `competitive.env_model.logit[a].three_cycle.fe`
  - all-seat history: `headline.even_environment[a].gls_3cycle`
- The two π settings:
  - old: LogNormal(0, 0.35) clipped to [0.5, 2] (§5.4 original)
  - current: the exported `pi_draws`, LogNormal(log 0.6, 0.45) clipped to [0.2, 1.5]
- ΔV = 100 × (P_lane − P_ML) per draw, shown as median [10th, 90th].
- Center populists are skipped.

**"Dimension effect"** = the mean, over cells with all other dimensions held fixed, of the range of the headline median across that dimension's levels.

## 2026 lane gaps vs mainstream liberal (median [80%])

| # | sample | scale | labels | swing2024 | n | progressive | left_populist | moderate |
|---|---|---|---|---|---|---|---|---|
| 1 | all | logit50 | agent | yes | 389 | -0.93 [-2.0, +0.1] | +1.17 [+0.0, +2.3] | +1.40 [+0.6, +2.2] |
| 2 | all | logit50 | agent | no | 389 | -0.75 [-1.8, +0.2] | +1.28 [+0.1, +2.4] | +1.33 [+0.6, +2.1] |
| 3 | all | logit50 | rule | yes | 389 | +0.20 [-0.3, +0.8] | +1.07 [-0.2, +2.3] | -0.15 [-0.7, +0.4] |
| 4 | all | logit50 | rule | no | 389 | +0.26 [-0.3, +0.8] | +1.04 [-0.3, +2.4] | -0.21 [-0.8, +0.4] |
| 5 | all | logit50 | high_conf | yes | 62 | +0.44 [-1.5, +2.3] | +0.60 [-1.9, +3.0] | -0.17 [-2.0, +1.7] |
| 6 | all | logit50 | high_conf | no | 62 | +0.67 [-1.3, +2.6] | +0.69 [-1.7, +3.1] | -0.36 [-2.2, +1.5] |
| 7 | all | margin | agent | yes | 389 | -0.66 [-1.6, +0.2] | +1.23 [+0.2, +2.3] | +1.23 [+0.5, +2.0] |
| 8 | all | margin | agent | no | 389 | -0.48 [-1.5, +0.4] | +1.33 [+0.3, +2.4] | +1.16 [+0.4, +1.9] |
| 9 | all | margin | rule | yes | 389 | +0.26 [-0.2, +0.8] | +1.07 [-0.2, +2.3] | -0.20 [-0.7, +0.3] |
| 10 | all | margin | rule | no | 389 | +0.30 [-0.2, +0.8] | +1.03 [-0.2, +2.3] | -0.25 [-0.8, +0.3] |
| 11 | all | margin | high_conf | yes | 62 | +0.49 [-1.3, +2.2] | +0.70 [-1.6, +3.0] | -0.16 [-1.9, +1.6] |
| 12 | all | margin | high_conf | no | 62 | +0.75 [-1.0, +2.5] | +0.84 [-1.5, +3.2] | -0.40 [-2.1, +1.4] |
| 13 | competitive | logit50 | agent | yes | 200 | -1.88 [-3.7, -0.3] | +1.03 [-0.5, +2.5] | +0.68 [-0.4, +1.7] |
| 14 | competitive | logit50 | agent | no | 200 | -1.87 [-3.6, -0.3] | +1.16 [-0.3, +2.7] | +0.65 [-0.4, +1.6] |
| 15 | competitive | logit50 | rule | yes | 200 | +0.40 [-0.3, +1.1] | +0.84 [-0.6, +2.3] | -0.35 [-1.1, +0.4] |
| 16 | competitive | logit50 | rule | no | 200 | +0.41 [-0.3, +1.1] | +0.85 [-0.6, +2.3] | -0.35 [-1.1, +0.3] |
| 17 | competitive | logit50 | high_conf | yes | 38 | -0.07 [-2.3, +2.2] | +0.03 [-2.5, +2.6] | +0.08 [-2.1, +2.3] |
| 18 | competitive | logit50 | high_conf | no | 38 | -0.04 [-2.3, +2.3] | +0.01 [-2.5, +2.6] | +0.04 [-2.1, +2.3] |
| 19 | competitive | margin | agent | yes | 200 | -1.73 [-3.5, -0.2] | +1.11 [-0.3, +2.6] | +0.75 [-0.3, +1.7] |
| 20 | competitive | margin | agent | no | 200 | -1.71 [-3.4, -0.2] | +1.23 [-0.2, +2.7] | +0.69 [-0.3, +1.7] |
| 21 | competitive | margin | rule | yes | 200 | +0.32 [-0.4, +1.0] | +0.83 [-0.6, +2.3] | -0.27 [-1.0, +0.4] |
| 22 | competitive | margin | rule | no | 200 | +0.35 [-0.3, +1.0] | +0.86 [-0.6, +2.3] | -0.30 [-1.0, +0.4] |
| 23 | competitive | margin | high_conf | yes | 38 | -0.09 [-2.3, +2.2] | +0.10 [-2.4, +2.7] | +0.14 [-2.0, +2.3] |
| 24 | competitive | margin | high_conf | no | 38 | -0.14 [-2.4, +2.1] | -0.02 [-2.5, +2.5] | +0.16 [-2.0, +2.3] |

Row 1 is the published spec. Row 19 is the old headline spec (competitive, margin scale), now with swing2024 added.

### Summary across the 24 universes (universe medians)

| gap | published (#1) | median | 10th / 90th pct | same sign as published | 80% excludes 0 | biggest mover (dimension effect) |
|---|---|---|---|---|---|---|
| progressive | -0.93 | +0.08 | -1.72 / +0.48 | 50% (12/24) | 17% | labels 1.73 (sample 0.63, scale 0.11, swing2024 0.09) |
| left_populist | +1.17 | +0.95 | +0.06 / +1.23 | 96% (23/24) | 17% | labels 0.82 (sample 0.34, swing2024 0.08, scale 0.05) |
| moderate | +1.40 | -0.05 | -0.35 / +1.21 | 50% (12/24) | 17% | labels 1.29 (sample 0.36, scale 0.08, swing2024 0.07) |

The 8 universes that use agent labels, varying only sample, scale and swing2024:

| gap | median | 10th / 90th | same sign | 80% excludes 0 | biggest mover |
|---|---|---|---|---|---|
| progressive | -1.32 | -1.87 / -0.60 | 100% | 50% (the 4 competitive) | sample 1.09 |
| left_populist | +1.20 | +1.08 / +1.30 | 100% | 50% (the 4 all-sample) | sample 0.12 ≈ swing2024 0.12 |
| moderate | +0.96 | +0.67 / +1.35 | 100% | 50% (the 4 all-sample) | sample 0.59 |

**Reading:**
- **The label set is the only choice that flips signs.** Under rule labels (Set B), progressives sit slightly ahead (+0.2 to +0.4) and moderates slightly behind (−0.15 to −0.35). One reason: Set B calls 88 nominees progressive, against 25 under the agent labels, so it measures a broader category.
- **The high-confidence subset is too small to tell anything apart.** It has 62 races (38 competitive) and only 2 left populists, so every interval spans roughly ±2.
- **With agent labels, every sign holds.** Sample is the next biggest lever: competitive-only doubles the progressive gap (about −1.8 vs about −0.7) and halves the moderate edge.
- **Scale (O-6) and the swing2024 control (O-9a) barely matter**, moving any gap by 0.2 or less.
- **The left-populist gap is the most stable sign** (positive in 23 of 24 universes), but its 80% interval excludes 0 in only 4.

## 2028 at the even environment (published 2026 fit)

P(win) is the mean. ΔV is in points of P(win) vs mainstream liberal, median [80%].

| source | π median | P(win) ML | progressive | left_populist | moderate | ΔV progressive | ΔV left_populist | ΔV moderate |
|---|---|---|---|---|---|---|---|---|
| fit_2026 | 0.99 | 0.491 | 0.406 | 0.566 | 0.582 | -7.75 [-17.2, -0.6] | +6.83 [+0.1, +16.4] | +8.55 [+2.8, +16.7] |
| fit_2026 | 0.59 | 0.478 | 0.425 | 0.527 | 0.537 | -4.66 [-11.4, -0.3] | +4.12 [+0.0, +10.9] | +5.17 [+1.6, +11.3] |
| history_competitive | 0.99 | 0.478 | 0.387 | 0.242 | 0.584 | -9.40 [-27.9, +9.5] | -25.81 [-41.5, -4.2] | +9.78 [-0.8, +22.8] |
| history_competitive | 0.59 | 0.471 | 0.409 | 0.303 | 0.539 | -5.47 [-19.4, +5.7] | -16.78 [-33.5, -2.4] | +5.78 [-0.5, +15.4] |
| history_all_seats | 0.99 | 0.478 | 0.294 | 0.255 | 0.614 | -18.92 [-36.1, -0.3] | -23.06 [-37.7, -7.5] | +12.62 [+3.2, +25.1] |
| history_all_seats | 0.59 | 0.471 | 0.343 | 0.316 | 0.558 | -11.93 [-26.6, -0.2] | -14.87 [-28.9, -4.3] | +7.66 [+1.9, +17.2] |
| blend | 0.99 | 0.484 | 0.396 | 0.400 | 0.584 | -8.14 [-22.8, +4.1] | -1.14 [-36.7, +12.8] | +8.99 [+1.5, +20.3] |
| **blend (published)** | **0.59** | **0.475** | **0.416** | **0.412** | **0.538** | **-4.90 [-15.8, +2.5]** | **-0.72 [-26.6, +8.3]** | **+5.39 [+0.9, +13.8]** |

### Summary across the 8 universes

| headline | published | median | 10th / 90th | same sign as published | source effect | π effect |
|---|---|---|---|---|---|---|
| P(win) mainstream liberal | 0.475 | 0.478 | 0.471 / 0.486 | — | 0.010 | 0.009 |
| P(win) progressive | 0.416 | 0.401 | 0.329 / 0.419 | — | 0.097 | 0.027 |
| P(win) left_populist | 0.412 | 0.358 | 0.251 / 0.538 | — | 0.274 | 0.043 |
| P(win) moderate | 0.538 | 0.570 | 0.538 / 0.593 | — | 0.027 | 0.048 |
| ΔV progressive | -4.9 | -7.9 | -14.0 / -4.8 | 100% | 9.2 | 4.3 |
| ΔV left_populist | -0.7 | -8.0 | -23.9 / +4.9 | 75% | 26.8 | 5.1 |
| ΔV moderate | +5.4 | +8.1 | +5.3 / +10.6 | 100% | 3.3 | 4.0 |

**Reading:**
- **The lane source (O-8/O-9c) decides the left-populist story.** On the 2026 fit, left populists beat mainstream liberals by about 4–7 points. On either history line they trail by 15–26. The blend lands at about −1 with an 80% range of roughly 35 points, so the published "close to a mainstream liberal" is an average of two answers that disagree, not a finding.
- **Progressives trail and moderates lead in every one of the 8 universes.**
- **π (O-9d) is a near-proportional shrink.** Moving from median 1 to median 0.6 cuts every ΔV by about 40%. It is the bigger lever only for moderate P(win). The all-seat vs competitive history choice (O-9b) mostly moves progressives (−12 vs −5 at current π).

### Secondary cross: 2026 specs propagated to 2028

`universes_2028_cross` has 96 rows: sources {fit_2026, blend} × π × all 24 2026 universes.

| source | ΔV progressive median (10th / 90th), share < 0 | ΔV left_populist | ΔV moderate |
|---|---|---|---|
| fit_2026 | +0.2 (-8.5 / +2.6), 50% | +4.1 (+0.3 / +7.0), 0% | -0.3 (-2.4 / +4.9), 50% |
| blend | -1.9 (-7.6 / +0.1), 75% | -2.9 (-8.0 / -0.5), 96% | +3.6 (+0.8 / +6.6), 0% |

## Caveats

- **Every universe gets equal weight.** Two-thirds of the 2026 universes use non-agent labels, so the pooled 2026 percentiles lean toward the rule and high-confidence results. The agent-labels-only table shows the picture without that.
- **History-based 2028 universes depend on 2026 only through ω_MAGA.** That is why the 2028 grid is crossed with a single representative 2026 spec.
