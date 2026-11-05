# Findings: 2026 candidate styles (preliminary)

Generated 2026-11-05T03:06:00+00:00 from data as of 2026-11-04 ~21:52 ET (NBC refresh of uncalled/partial races; earlier races as of ~11:10 ET). Every number is preliminary. Pipeline `nogit-66c5c31c2578`.

## Bottom line

- **Fit level 3** (no Level-5 block). Lead-reviewer decisions O-1a to O-5 (2026-11-04, logged in `methodology_decisions.md`) were applied: u_a minimum 12 races from 8 states, Mundlak terms for archetype indicators, V12 threshold 1.5 SD with bracketing, V16 national-only, likelihood trial for V7, district_sd = 1.5 with JS parity.
- Levels triggered: L1 (archetypes below minimum N: left_populist, center_populist); L2 (interactions below minimum N (no district composition)); L3 (district demographics missing for 100% of rows (> 25%)).
- **Validation:** blocking FAIL = none; blocking NOT_RUN = none. `model_params.json` written.
- Models disagree for ['moderate']: those δ cells are exported as a bracket (`delta_range_models`) and copy must name both numbers. Note: the EB between-archetype variance estimate τ̂² is 0 this run, so EB shrinks every OLS-FE dummy to 0 and the bracket's lower end is 0 by construction; unshrunk OLS-FE dummies are progressive -1.2 (SE 2.3), left_populist +1.1 (SE 1.3), center_populist +4.8 (SE 1.1), moderate +2.2 (SE 1.1).

## Sample

- 403 races in the main sample (every contested race with ≥ 80% counted: House at any lean, Senate, governor, 2025–26 House specials; decision O-6), out of 520 rows loaded.
- Exclusions (counts): partial_count_lt_80pct 77, uncontested_or_no_major_party_opponent 20, no_democrat_on_ballot 1, third_candidate_ge_10pct 10, independent_backed 5, validation_only_2025_offyear 3, combined_multi_dem_vote 1. Every exclusion and its reason is in `races.json` (`exclusion_reason`).
- Archetype counts in the main sample: progressive 26 (15 states), left_populist 14 (12 states), center_populist 2 (2 states), mainstream_liberal 292 (46 states), moderate 69 (31 states). Archetype deviations u_a are estimated for ['progressive', 'moderate'] (rule: ≥ 12 races from ≥ 8 states, ≥ 5 with |m24| ≤ 10); the others are structural only. Center-populists are almost all Dem-backed independents (excluded), leaving 2.
- Partial counts: 77 races below 80% counted are out of the main fit (provisional refit only). Selection report: progressive 4/30, left_populist 2/16, center_populist 1/3, mainstream_liberal 58/350, moderate 12/81. `provisional_archetypes` = ['center_populist'].
- 39 races are uncalled in the data; 345 rows rely on NBC alone for vote shares. Uncalled races still enter if ≥ 80% counted (the call does not matter for the margin).

## Raw vs adjusted style effects (vs a mainstream liberal)

Raw means are plain margin points relative to Harris 2024. Adjusted δ is on the main model scale, 50 × Δlogit of the two-party D share: points of margin in an evenly split seat, compressed correctly in lopsided seats (decision O-6). It is what the 2028 translation uses, where the national race is near even.

Likelihood: t5 (no likelihood reached 0.75-0.85 coverage; t5 kept and V7 is non-blocking (intervals conservative)).

| Archetype | n | Raw mean y | Adjusted δ (fitted, agnostic) | Literature | Data-only | Discount | posterior SD / prior SD |
|---|---|---|---|---|---|---|---|
| progressive | 26 | +10.5 | -0.8 (80%: -1.9 to +0.2) | -1.0 (80%: -2.0 to -0.0) | -0.8 (80%: -1.9 to +0.2) | -0.9 (80%: -2.3 to +0.5) | 0.34 |
| left_populist | 14 | +15.3 | +1.2 (80%: +0.1 to +2.4) | +1.0 (80%: -0.1 to +2.0) | +1.6 (80%: +0.3 to +2.9) | +1.0 (80%: -0.6 to +2.7) | 0.43 |
| center_populist | 2 | +16.6 | +2.8 (80%: +1.3 to +4.3) | +2.8 (80%: +1.4 to +4.2) | +3.4 (80%: +1.7 to +5.1) | +2.8 (80%: +0.7 to +4.9) | 0.41 |
| mainstream_liberal | 292 | +14.6 | reference (δ = β_P·P̄ = +0.17) | | | | |
| moderate | 69 | +17.6 | +1.2 (80%: +0.4 to +2.0) | +1.3 (80%: +0.5 to +2.1) | +1.4 (80%: +0.6 to +2.2) | +1.5 (80%: +0.3 to +2.7) | 0.28 |

- Slopes (agnostic): β_L = -1.2 (80%: -2.0 to -0.3) per step left; β_P = +1.7 (80%: +0.5 to +2.8) per unit populist posture. SD ratios: β_L 0.36, β_P 0.44 (below 0.7, so 2026 does inform the slopes).
- Center-populist δ is an extrapolation of β_P from 2 races at (L, P) = (0, 1); it is structural only and its cell is greyed.
- Opponent: facing MAGA +0.5 (80%: -0.2 to +1.3); facing a moderate R -1.4 (80%: -3.2 to +0.4). R incumbent personal vote coefficient +0.4 (80%: +0.3 to +0.5) per point.
- Statewide deviation d_L -0.9 (80%: -1.9 to +0.1), d_P +0.2 (80%: -0.9 to +1.4); statewide/House ratio for leftness +1.7 (80%: +0.8 to +3.8) (evidence beside the π slider only).
- Alternative specifications for the story (decision O-6): **R4: competitive only (|pres2024| <= 20)** (n = 211): progressive -1.5 (80%: -3.1 to -0.0), left_populist +1.0 (80%: -0.5 to +2.4), center_populist +2.1 (80%: +0.2 to +4.0), moderate +0.6 (80%: -0.4 to +1.5); **R4: competitive only, margin scale (previous headline spec)** (n = 211): progressive -1.3 (80%: -3.0 to +0.0), left_populist +1.0 (80%: -0.4 to +2.4), center_populist +2.2 (80%: +0.3 to +4.1), moderate +0.7 (80%: -0.4 to +1.6); **R1: margin scale (D-R points) with m24 spline** (n = 403): progressive -0.6 (80%: -1.6 to +0.3), left_populist +1.2 (80%: +0.1 to +2.3), center_populist +2.5 (80%: +1.0 to +3.9), moderate +1.0 (80%: +0.3 to +1.8).
- Oaxaca on the model scale (raw gap vs mainstream liberals = lean + incumbency + opponent + state wave + office + style + residual): progressive: -3.4 = lean +0.4, incumbency -1.2, opponent -0.1, state -2.0, office +0.1, style -0.6, residual +0.0; left_populist: -0.5 = lean -0.8, incumbency -0.8, opponent +0.2, state -0.0, office +0.3, style +0.9, residual -0.2; center_populist: +1.0 = lean -0.7, incumbency -0.0, opponent +0.2, state -1.3, office +0.6, style +2.4, residual -0.1; moderate: +2.0 = lean -1.0, incumbency +1.6, opponent +0.1, state -0.3, office +0.0, style +1.2, residual +0.4.
- Progressives' raw gap (-3.4) is mostly incumbency and an unexplained residual (+0.0). The incumbency term is largely one race: GOV-VT (Phil Scott's personal vote), -37 pts for that race, -1.4 of the archetype average. The residual is what the OLS-FE dummy picks up.
- Without GOV-VT (decision O-4), progressives' raw mean is +12.6 (vs +10.5 with it) and the raw gap to mainstream liberals is -1.3 (n = 25): incumbency +0.3, state -1.7, style -0.5, residual +0.2. So the raw deficit is not one Vermont race, but about half of it is.

## Diagnostics and copy flags

- D1 overlap: 395/403 races on common support; no δ moved > 1.5 → `lead_with_overlap = false`. (Propensity uses state-level demographics.)
- D2 OLS-FE + EB: progressive OLS -1.2 (SE 2.3) → EB +0.0 vs Gibbs -0.8 (1.0 SD, gated); left_populist OLS +1.1 (SE 1.3) → EB +0.0 vs Gibbs +1.3 (1.5 SD, gated); center_populist OLS +4.8 (SE 1.1) → EB +0.0 vs Gibbs +2.8 (2.5 SD, n<10 not gated); moderate OLS +2.2 (SE 1.1) → EB +0.0 vs Gibbs +1.3 (2.0 SD, gated). Review aid: Gibbs with every u_a switched on gives progressive -0.7 (80%: -1.8 to +0.2); Huber-weighted OLS-FE gives -1.6. The first run (u_progressive switched off by the 15-race rule, no archetype Mundlak terms) had a 2.5-SD progressive gap; decisions O-1a/O-1b closed most of it.
- D3 Freedman–Lane: Wald 20.1, p = 0.001 → `no_detectable_effect = False`.
- D4 grouped CV: ΔELPD = 5.6 (SE 3.7); below 2·SE → `no_predictive_gain = True` (borderline).
- D5 placebo (2024 House − pres on unchanged lines, new nominees): progressive +4.1 (n 11); left_populist -0.3 (n 5); center_populist n/a (n 1); moderate +0.3 (n 20) → `placebo_flag` = {'progressive': True, 'left_populist': False, 'center_populist': False, 'moderate': False}. Progressive seats already ran ~3 pts ahead of Harris in 2024 with other nominees.
- D6 close-primary RD (sign check, n = 13): more-left winner -18.7 (80%: -51.7 to +14.4); no tension flagged.
- D7 wave compression: leftness × state wave -0.5 (80%: -0.9 to -0.1); posture × wave +0.2 (80%: -0.5 to +0.8). The leftness interval excludes 0, so the π tooltip should say style differences were smaller where the wave was bigger (as an OLS-FE robustness model).
- `direction_depends_on_prior` = all false (agnostic, literature and data-only agree in sign). `label_reliability = low_posture`. `maine_explained_by_incumbent = True`.
- Label fragility (R3): Set B rule labels give progressive +0.2 (80%: -0.3 to +0.7) and moderate -0.1 (80%: -0.7 to +0.4); strict source-date audit labels shrink every δ toward 0. Label-flip attenuation A = 0.53 (β_L), 0.42 (β_P): effects may be understated if labels are noisy. Agent-vs-rules κ (archetype) 0.41; proxy second coder κ 0.67 (archetype), 0.51 (posture).
- Label sets actually available: A (agent) yes; B (rule-based) implemented from the evidence text, not raw campaign text; C (soft) constructed from confidence; no blind second coder (primaries.json used as a non-blind proxy, n = 65). Source-date audit: only 25 main-sample labels cite a dated pre-election URL; 42 more have a pre-election primary record; 37 labels with no pre-election evidence were replaced by Set B.

## Validation (§7)

| Item | Status | Blocking | Key numbers |
|---|---|---|---|
| V1 Identity (delta=0, E=E24, u=psi=phi=eps=0) | PASS | yes | EV_D 226, max dev 0.0e+00 |
| V2 JS <-> Python parity | PASS | yes | Partial scope: the bank and P(win) primitives that every Sim uses are exact; full Sim-object parity still to d |
| V3 Error calibration back-test | PASS | yes | pooled 80% coverage 0.79; correlated log score -244.1 vs independent -255.6 |
| V4 2024 EC back-test from 2020 base | PASS | yes | D EV 80% [213.0, 241.0] contains 226; Brier 0.0084 vs 0.0091 |
| V5 u back-test | NOT_RUN | no | No 2020->24 national group shifts on disk; turnout_u.offered_as = 'scenario' and the tooltip must say the back |
| V6 Maine (refit without SEN-ME) | REPORT | no | δ=0 prediction +0.8 (80%: -6.7 to +8.2) vs actual -0.2 (NYT-implied -3.7); incumbency share 0.88 |
| V7 Posterior predictive coverage (main sample) | FAIL | no | coverage 0.888 (target 0.75–0.85) |
| V8 Leave-statewide-out | PASS | no | coverage 0.89; MAE 4.05 vs 4.20 |
| V9 Spanberger same-ballot | NOT_RUN | no | offyear.json has no 2025 VA Lt. Governor / Attorney General margins; C15 is therefore not licensed. |
| V10 Mamdani sign check vs beta_LY | REPORT | no | No beta_LY estimate to compare. offyear.json subgroup notes (Jackson Heights +20 vs Harris share; South Asian  |
| V11 Placebo (D5) | REPORT | no | progressive placebo +4.1 (flag) |
| V12 OLS-FE + EB vs Gibbs (D2) | REPORT | yes | progressive gap 1.0 SD |
| V13 Label agreement (kappa) | REPORT | no | proxy κ archetype 0.67, posture 0.51 |
| V14 Label-flip attenuation | REPORT | no | A = 0.53, 0.42 |
| V15 Trust-dial Gaussian validity | FAIL | no |  |
| V16 Sim 5 consistency (national margin) | PASS | yes | national D+13.8 vs NYT D+13.1 (ok); bucket match 82% (< 90%) |
| V16b Sim 5 NYT leader-share buckets (by eye) | REPORT | no | District vote totals are not on disk: districts are equal-weighted within a state and states weighted by 2024  |
| V17 Sim 3 Brier | REPORT | no | Brier 0.535 vs baseline 0.470 |
| V18 Engine invariants | PASS | yes | Invariants checked on the Python reference engine; the JS test suite (invariants, §6.3 budgets in Node, real-p |
| V19 Convergence | PASS | yes | max R̂ 1.0010, min ESS 4372 |
| V20 Partial-count selection report | REPORT | no | excluded p<0.80: progressive 4/30, left_populist 2/16, center_populist 1/3, mainstream_liberal 58/350, moderate 12/81 |

Notes: V7 over-covers (0.888); no likelihood reached 0.75-0.85 coverage; t5 kept and V7 is non-blocking (intervals conservative). V16 national margin passes; the by-eye bucket match (82%) is REPORT only (V16b). V2 covers the bank and P(win) layers exactly; full Sim-object parity is not yet tested.

## Claims ledger (§8): what the copy may say now

- **C1 licensed** (descriptive): e.g. "Moderate Democrats beat Harris's 2024 margin in their districts by 18 points on average" (progressive 11, 13 without Vermont's governor race; left-populist 15, mainstream liberal 15), always followed by "But they ran in very different places."
- **C2 licensed for progressive**: "In comparable races, on the same ballot, progressive nominees ran less than 1 point behind mainstream liberals (range -2 to 0)" + the mandatory caveat (comparable races, not cause and effect; preliminary). **Placebo caveat required:** "In these seats a different Democrat already ran about 4 points ahead of Harris in 2024 (placebo, n = 11 seats), so the place favoured the opposite direction; the style gap could be larger than shown, not smaller."
- **C2 licensed for moderate as a bracket** (models disagree: Gibbs +1.3, OLS-FE/EB +0.0): "In comparable races, on the same ballot, moderate nominees ran between 0 and about 1 point ahead of mainstream liberals, depending on the model" + the mandatory caveat. The OLS-FE/EB end is 0 because the EB between-archetype variance estimate is 0 (every OLS dummy is shrunk fully); the unshrunk OLS-FE dummy is +2.2 (SE 1.1).
- C2 not licensed for ['left_populist', 'center_populist'] (below the minimum N for their own deviation; structural prediction only).
- **C3 required wording** (`no_predictive_gain = True`): "style adds no detectable predictive power" / "We found no detectable difference between styles once we compared like with like; the range runs from [lo] to [hi]", with "No detectable difference is not proof of no difference." **Tension for the desk:** C2's conditions also hold for the archetypes above, and D3's permutation test detects the style slopes (p = 0.001); the slopes explain in-sample variation but do not improve out-of-state prediction by 2 SE (ΔELPD 5.6, SE 3.7). Because C3 is marked required, lead with C3 and give the C2 numbers as its range.
- **C4 not required** (direction vs prior).
- **C5 licensed** (integers): E* = progressive D+1 (even to D+3), left_populist D+1 (R+1 to D+5), center_populist even (R+3 to D+6), mainstream_liberal even (even to D+1), moderate even (R+2 to even). Center-populist numbers are a 2-race extrapolation of β_P.
- **C6 licensed** (even environment, generic opponent): ΔV vs mainstream liberal = progressive -4 pts (-15 to +3), left_populist -0 pts (-27 to +10), center_populist +5 pts (-33 to +19), moderate +5 pts (+1 to +12).
- **C7 licensed**: E 80% width 14.8 vs 2 × max |π·δ| upper bound 8.7.
- **C8 licensed**: a style must cost at least 1.4 pts nationally (π·δ ≤ -1.4) to cut win probability by 10 points at the default environment; 2026 puts the chance of a cost that large at 20% (progressive), 35% (left_populist), 33% (center_populist), 0% (moderate).
- **Placebo caveats (D5, required wherever these archetypes' effects are quoted):** progressive: In these seats a different Democrat already ran about 4 points ahead of Harris in 2024 (placebo, n = 11 seats), so the place favoured the opposite direction; the style gap could be larger than shown, not smaller.
- **C9 licensed**: "Maine's swing toward Republicans looks like Susan Collins's personal vote, not a populism penalty" with "One race; the model can't separate the candidate from the opponent." Caveat for the desk: the race file shows Jackson slightly *ahead* of Harris (+0.5 two-party at 86% counted), while the NYT nine-state table implies a 3.7-point shift toward R. The δ = 0 interval covers both. Never "populism failed in Maine".
- **C10 licensed** (descriptive, nine races). Between-state SDs reproduce §4.2 (WNC−WC 4.9, 18–29 vs 65+ 4.4, education gradient 5.1).
- **C11 not licensed** (interaction gates closed: no district composition).
- **C12 licensed** in matrix context only. **C13** licensed with V17 shown: coalition model disabled, so "polls plus priors".
- **C14 licensed**: the 2026 House vote as a presidential map gives Democrats 432 EV; at a even environment (durable view) 238 EV. National House margin D+13.8 (two-party; NYT D+13.1).
- **C15 not licensed** (V9 not run: no VA LG/AG margins).
- **C16 licensed**: provisional archetypes ['center_populist'] (West Coast and other slow counts).

## Known data issues carried through

- Maine Senate: nominee is Troy Jackson (left_populist; Platner won the primary and withdrew). See the C9 caveat for the NYT-vs-race-file discrepancy (also in validation.json `data_issues`).
- Uncalled races named in the brief: SEN-AK (partial_count_lt_80pct (provisional refit only)); SEN-MS (in main fit); GOV-KS (in main fit); GOV-AK (third_candidate_ge_10pct (aggregate other_pct >= 10)); ME-2 (in main fit); TN-4 (in main fit); TN-9 (in main fit); VA-5 (in main fit); NC-3 (in main fit); NC-5 (in main fit); NC-7 (in main fit).
- Dem-backed independents (NE Osborn, ID Achilles, SD Bengs, MT Bodnar, AK-AL Hill) are excluded and descriptive only; Montana's split anti-GOP vote (Bodnar 37.3 + Bankhead 11.9) is also excluded.
- No district demographics (Level 3): ES terms dropped; common-support plots use state-level shares; interactions gated off.
- Candidate track records before 2025 use national environment constants that are not in the research files (listed in candidate_profiles.json); verify before publishing named-candidate numbers.
- E24 from certified state totals is −1.50 two-party, not the −1.43 quoted in METHODOLOGY.
