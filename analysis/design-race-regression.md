# Design: race-level regression first, then project to states

Status: draft, 2026-11-04. Only `research/nyt_voter_trends.json` exists so far; other inputs follow the brief's schema. A Python pipeline writes `site/data/params.json`; the five simulations run in vanilla JS from it.

The approach has one idea. Measure each Democratic archetype **relative to the 2026 wave in comparable races**, shrink hard, and carry the result to 2028 with an explicit **transfer factor κ** and an explicit **national environment N**. Neither is inherited from 2026.

---

## 1. Estimands

Archetypes are a ∈ {progressive, left_populist, center_populist, mainstream_liberal, moderate}, with **mainstream_liberal = 0** as the reference.

- **E1, the 2026 style effect δ_a.** The expected D−R margin difference between an archetype-a nominee and a mainstream liberal with the same state wave, 2024 lean, demographics, incumbency and Republican type. The wave sits in the intercept and state effects, so δ is relative to it.
- **E2, the 2028 national effect Δ_a = κ·δ_a.** The shift in the popular-vote margin from nominating a instead of a mainstream liberal.
- **E3, viability.** Three numbers per archetype:
  - P_a(win | N): the Electoral College win probability at N, the margin a mainstream liberal would get against a traditional Republican.
  - **The break-even environment N\*_a**: the N at which P_a = 50%. This is the headline ("a moderate needs D+1.2 to be a coin flip; a progressive D+2.9"). It does not require guessing 2028.
  - ΔP_a(N) versus mainstream liberal, using common random numbers.
- **E4, a named candidate.** The same quantities plus a home-state effect and a shrunk track record.

Everything is reported with an 80% interval.

---

## 2. Data preparation

**Unit:** one general-election race (House, Senate, governor 2026, governor 2025, special 2025–26).

**Primary outcome:** `y = margin − pres2024_margin` (current lines).

**Robustness outcomes:**
- (b) `margin − house2024_margin`
- (c) `margin − prev_seat_margin`. Use (b) and (c) only where `lines_changed == false` and the prior race was contested.
- (d) Difference in logit two-party share, which handles ceilings without a spline.

| Rule | Main fit |
|---|---|
| Uncontested by a major party | Exclude. Imputed only for Sim 5 |
| D-v-D / R-v-R (top-two) | Exclude |
| Third party ≥ 10%, or a Dem-backed independent | Exclude. Coded `independent_backed`, descriptive only |
| `pct_expected_vote_counted` < 95% or not called | Hold out and refit after the canvass. Sensitivity run imputes `final ≈ now + (1−p)(r − now)`, where r is the margin of late ballots in 2024 |
| No `pres2024_margin` on current lines | Exclude. Never use old-line baselines |
| \|pres2024\| > 30 | Exclude from the archetype fit (ceiling/floor) |
| `style_confidence` < 0.5 | Weight 0. Included in R3 |
| NYC mayor (Mamdani) | Exclude. Validation only |

Ranked-choice races (ME, AK) use the final-round margin, with the first round as robustness. The UI labels parameters "preliminary as of {timestamp}" until California and the other slow-counting states finish.

**Redistricting.** Mid-decade maps make the House 2024 and previous-seat baselines incomparable. Each row carries `lines_changed`, and only `pres2024` recomputed from precincts on 2026 lines is valid.

**Controls Z:**
- `inc_D`, `inc_R` (open is the reference)
- `rep_maga`, `rep_moderate` (traditional is the reference), plus a count of Republican `quality_flags`
- Centered shares of white non-college, white college, Black, Hispanic, ages 18–29 and 65+, and urbanicity
- Office×period effects: House-26, Senate-26, Gov-26, Gov-25, and Special by quarter. These absorb the different environments of specials and off-year races.
- The log D/R spending ratio enters only as robustness, because money follows expected competitiveness.

**Style coordinates** come from each row:
- Ideology I: left = −1, liberal = 0, moderate = 1, conservative = 2
- Posture P: establishment = 0, mixed = 0.5, populist = 1

Coders must classify from **pre-election information, blind to results**. The pipeline asserts `coded_at` < Nov 3.

---

## 3. Estimation

### 3.1 Main model (hierarchical Bayes, PyMC)

```
y_i  = μ_o(i) + α_s(i) + f(pres24_i) + β'Z_i + b_I·I_i + b_P·P_i + η_a(i) + ε_i
η_a  ~ N(0, τ_η),  τ_η ~ HalfNormal(2);   η_mainstream ≡ 0
α_s  ~ N(ρ_region(s), τ_α),  τ_α ~ HalfNormal(5)
b, β ~ N(0, 3)   (standardized covariates)
f    = natural spline in pres24, knots −15, 0, +15  (ceilings / regression to the mean)
ε_i  ~ StudentT(5, 0, σ_o(i)),  σ_o ~ HalfNormal(8);  likelihood weight = style_confidence
```

**How the model handles the main problems:**
- **The wave.** α_s is the state wave, identified mainly by the state's House races. A Senate or governor nominee is therefore compared with House Democrats on the same ballot, which is the cleanest within-wave contrast available.
- **Thin cells.** The two-factor (I, P) structure lets small archetype cells borrow strength, and it maps directly onto the Build-your-own sliders.
- **Non-additive archetypes.** η_a catches cases such as left-populist ≠ left + populist.
- **Outliers.** Student-t errors stop one odd race from dominating.

Run 4 chains × 1,000 draws (R-hat < 1.01). Export 1,000 **joint** posterior draws of the archetype effects, b_I, b_P, γ_maga and γ_repmod, so the correlations between them survive in JS.

### 3.2 Cross-check

Fit OLS with state fixed effects, the same spline and controls, and archetype dummies, with CR2 SEs clustered by state. Then apply empirical-Bayes shrinkage: `τ̂² = max(0, Var(δ̂_a) − mean(se²))`, `δ̃_a = δ̂_a·τ̂²/(τ̂²+se_a²)`. Any gap of more than one posterior SD from the Bayesian estimate blocks publishing until it is reviewed.

### 3.3 Minimum-N rules

| Estimate | Minimum |
|---|---|
| Archetype deviation η_a | ≥ 15 races from ≥ 6 states |
| Archetype × office, or × Republican style | ≥ 10 per cell. Otherwise pooled |
| Archetype × demographic tilt | ≥ 25 races spanning the covariate, **and** an 80% CI that excludes 0 |

A cell below its minimum is shown greyed out ("too few races"), and its draws come from the two-factor prediction only.

### 3.4 Confounding diagnostics (required)

1. **Common support.** Show pres24, white non-college share and urbanicity by archetype. Refit on the overlap (−15 ≤ pres24 ≤ 15, propensity-trimmed). If δ moves by more than 1.5 points, the story leads with the overlap estimate.
2. **Close primaries (Hall-style).** From `primaries.json`, take races where left and moderate finished within 10 points. Regress the nominee's y on "left won", with a local-linear term in the primary margin. N ≈ 15–25, so this is a sign check only.
3. **Permutation null.** Shuffle labels within pres24 deciles, 1,000 times. If the observed b_I and b_P are not beyond the 90th percentile, the copy says "no detectable style effect".
4. **PSIS-LOO.** Compare the model with and without the style terms. If ΔELPD < 2 SE, style adds no predictive power, and the copy must say so.

### 3.5 Robustness grid (forest plot in the methods drawer)

- R1: outcomes (b), (c), (d).
- R2: leave-one-state-out, plus DFBETA for each statewide race. Maine is the obvious high-leverage race.
- R3: low-confidence rows included. Two alternative classifications: a rule-based one (Justice Dems / Sanders / CPC endorsements → left; Blue Dog / New Dem → moderate; posture from a lexicon score on ad text) and a soft one using each race's probability vector.
- R4: House only vs statewide only.
- R5: a literature prior, b_I ~ N(+1.5, 1.5), a shrunk extremism penalty.
- R6: November 2026 races only.

### 3.6 Group-level evidence (NYT nine-state Senate table)

These data cannot separate archetype from state, because each state has one nominee (N = 9). Tilts computed from `senate_shift_vs_2024_by_group`:

| | AK | IA | KS | ME | MI | MS | NC | OH | TX | US House |
|---|---|---|---|---|---|---|---|---|---|---|
| Overall shift (≈ M/F mean) | +18 | +18 | +20 | **−4** | +8 | +21 | +23 | +17 | +26 | +15 |
| White non-college − white college | +3 | +8 | +2 | **−4** | +10 | +2 | 0 | +10 | 0 | +5 |
| 18–29 − 65+ | 31 | 27 | 27 | **36** | 33 | 33 | 35 | 28 | 40 | 26 |

They have three uses only:
- (i) A direction check on any race-level archetype × white-non-college slope. Maine's −4, with a populist nominee against a moderate Republican incumbent, is a counterexample to report.
- (ii) Their spread (SD ≈ 4) sets the prior SD for the optional demographic tilt τ_{a,k}.
- (iii) Labelled story color.

They are never used to estimate δ.

---

## 4. Translation to 2028 states

The units are 50 states, DC, ME-1/2 and NE-1/2/3.

```
Lean_s = L24_s + φ·(L24_s − L20_s) + ψ·(swing26_s − swing26_US),    L_t,s = pres_t,s − pres_t,US

m_s = N + Lean_s
    + κ·(δ_a + ω_g)                                   style + GOP-type effect
    + 1[tilt]·κ·Σ_k τ_a,k·(share_s,k − share_US,k)    optional, off by default
    + κ_c·c_c + h·1[s = home]                         named candidates only
    + T_s + e_s
```

| Parameter | Default | Why |
|---|---|---|
| φ, trend persistence | 0 (slider 0–0.5) | Weak historical support |
| ψ, persistence of 2026 state deviations | Regress the presidential (t+2) state swing on the midterm (t) statewide House swing for 2006/08 … 2022/24. Expect about 0.1–0.3; else 0 | Midterm deviations partly persist |
| κ | Drawn from N(0.8, 0.25), truncated [0, 1.5], once per simulation | Down-ballot style partly reflects a personal vote. National nominees are better known, which raises κ, but partisanship dominates, which lowers it. Unknown, so sampled |
| ω_g | γ_maga or γ_repmod from §3 (traditional = 0) | |
| N presets | 2024 rerun −1.5; **midterm decay** 13 − d̄ ≈ D+8 ± 4 (d̄ ≈ 5 from out-party decays 2006–22 of about 0.7, 10.7, 7.8, 4.1 and 1.2, recomputed from Clerk data); neutral 0; unknown N(+2, 6) | The 2028 environment is an assumption |
| σ_N | 3 | Election-day national error within a scenario |

**Turnout.** The baseline electorate is the **2024 presidential** one, embedded in the 2024 lean. 2026 enters only as relative effects, which is the main protection against the older, more educated midterm electorate. The sliders are Δyouth and Δnon-college share (points):

```
T_s = Σ_k Δshare_k·(share_s,k/share_US,k)·(GM_k + 1[tilt]·τ_a,k − N)
```

GM_k is the group's 2024 margin from `national.json`. Turnout separates archetypes only when the tilt is on.

**Named candidates.**

```
r_c,k = margin − same-geography pres baseline − mean same-party/office overperformance that year
c_c   = B_c·(mean_k r_c,k − δ_a(c)),   B_c = τ_c²/(τ_c² + σ_r²/n_c)
```

- τ_c, the SD of true personal effects (≈ 2–3), comes from the covariance of incumbents' residuals across cycles.
- σ_r is the race residual SD by office.
- κ_c defaults to 0.5, because a statewide brand is partly local.
- h ~ N(1.5, 1.0) in the home state.

Republicans get the same treatment with the sign flipped. Polls and markets feed only Sim 3.

**Correlated error.**

```
e_s = Σ_f Λ_s,f·z_f + σ_s·ε_s
```

- Use F = 6 factors: white non-college, white college, Black, Hispanic, evangelical, region.
- Fit Λ to state-relative presidential swings for 1992–2024, scaled so the median state SD is about 3 points.
- σ_s is 1.5–3.5, larger for small states.
- Districts: m = m_state + (district − state lean) + N(0, 1.5).

Python exports Λ (56×6) and σ_s, so JS never factorizes a matrix.

---

## 5. Simulations (vanilla JS)

**Engine.**
- PRNG: seeded xoshiro128\*\*, with Box–Muller normals and `Float32Array`s, run in a Web Worker.
- Each draw j uses one stream: posterior index p, κ, N noise, z_f, ε_s. That stream is **reused across archetypes and candidates** (common random numbers), so differences reflect parameters, not noise.
- Cost: 10,000 draws × 62 normals plus a 56-element sort ≈ 4M operations, about 100 ms on a phone.
- Tipping point: sort by m_s descending, accumulate EV to ≥ 270. A 269–269 tie is its own category.

**`params.json` skeleton:**

```json
{"version":"2026-11-04-prelim",
 "style_coords":{"progressive":[-1,0.25],"left_populist":[-1,1],"center_populist":[0.75,1],"mainstream_liberal":[0,0],"moderate":[1,0]},
 "posterior":{"n":1000,"delta":[[5 values]],"bI":[],"bP":[],"gamma_maga":[],"gamma_repmod":[]},
 "kappa":{"mean":0.8,"sd":0.25,"lo":0,"hi":1.5},
 "env":{"presets":{"rerun2024":-1.5,"decay":8,"neutral":0,"unknown":[2,6]},"sigma_N":3},
 "lean":{"phi":0,"psi":0.2},
 "units":[{"id":"PA","ev":19,"L24":0,"L20":0,"swing26":0,"sigma":2.4,"Lambda":[6],"shares":{},"parent":null}],
 "turnout":{"GM":{}}, "tilt":{"enabled":false,"tau":{}},
 "candidates_dem":[{"id":"","archetype":"","home":"","c_draws":[],"poll":0}],
 "candidates_gop":[{"id":"","style":"maga","home":"","c_draws":[]}],
 "home_bonus":[1.5,1.0], "kappa_c":0.5}
```

**Sim 1, archetype vs a generic, MAGA-heir or traditional Republican.**
- **Algorithm:** for each of 10,000 draws, sample p, κ, N_j = N + σ_N·z₀, z and ε. Compute m_s for all five archetypes and record EV, win and tipping point.
- **Parameters:** `{opponent, N, sigma_N, kappa:"sampled"|value, tilt, phi, psi, turnout:{dy,dnc}}`.
- **Outputs:**
  - The win probability per archetype.
  - EV histograms.
  - **Win-probability-vs-N curves** (31 N values from −10 to +20, 2,000 draws each), with N\*_a marked.
  - The top tipping-point states.
  - A mean-margin map.
  - ΔP versus mainstream, with an 80% interval taken across posterior-draw batches.

**Sim 2, named matrix.**
- **Algorithm:** for each (Dem c, GOP g) cell, run 4,000 common-random-number draws using δ_a(c) + κ_c·c_c + h, ω_style(g) plus g's own shrunk effect, and h_g. About 40 cells, roughly 1 s, rendered progressively.
- **Parameters:** Sim 1's plus `{kappa_c, home_bonus, track_record:on}`.
- **Outputs:**
  - A heat matrix of P(D) with 80% intervals.
  - A row average weighted by GOP nomination odds.
  - A click-through to the cell's map and a decomposition bar (environment, tipping-state lean, style, personal, home).

**Sim 3, Democratic primary.**
- **Coalition fit** on `primaries.json` (N ≈ 40): logit(left-camp share) = λ₀ + λ·X + u_state, where X has at most 4 standardized covariates (Black share, white college share, 18–29, urbanicity), with λ ~ N(0, 0.5). Fit a parallel equation for the populist share.
- **Simulation:**
  1. Start each candidate at β_c = logit(poll) + N(0, 0.5).
  2. For each calendar date (editable; default is the 2024 DNC order, labelled an assumption), compute `share_c,s = softmax(β_c + λ_lane(c)·X_s + 0.8·home + N(0, 0.3))`.
  3. Allocate delegates proportionally among candidates at ≥ 15%.
  4. Apply momentum: `β_c += 0.5·mean(share − expected)`.
  5. After Super Tuesday, a candidate under 10% of delegates drops out. Their support moves 60% to the same lane and the rest pro rata.
- **Parameters:** `{field, calendar, momentum, viability, dropout, lane_affinity}`.
- **Outputs:**
  - Nomination probability by candidate and by archetype.
  - The delegate path.
  - P(contested convention).
  - P(Dem wins the presidency) = Σ_c P(nominee c)·P(win | c), using Sim 2.

**Sim 4, build your own candidate.**
- **Sliders:**
  - I ∈ [−1, 1.5]
  - P ∈ [0, 1]
  - Home state
  - N and σ_N
  - Turnout
  - κ
  - Opponent
- **Effect:** δ(I, P) = b_I·I + b_P·P + inverse-distance-weighted η from nearby archetypes, per posterior draw.
- **Extrapolation guard:** if the point is more than 0.5 from every observed archetype coordinate, or I > 1, the band is hatched with "outside the 2026 data, a guess".
- **Outputs:** Sim 1 outputs for the custom candidate against mainstream, plus a δ(I, P) contour with the 2026 races scattered on it.

**Sim 5, 2026 as a presidential year.**
- **Data:** statewide 2026 House margin, with uncontested seats imputed as pres24_d + national swing + α̂_s at district turnout. Senate and governor variants are tabs.
- **Map:** m_s = pres24_s + swing26_s ("raw D+13"). The toggle **neutralize the midterm** gives m_s = pres24_s + (swing26_s − swing26_US) + (N − pres24_US).
- **Uncertainty:** imputation plus partial-count SD (0.5–3), 2,000 independent draws.
- **Parameters:** `{source, neutralize, N}`.
- **Outputs:**
  - EV total.
  - Flips versus 2024.
  - Swing dot plot.
  - A banner: "Midterm electorates are older and more educated; not a forecast."

---

## 6. Validation

1. **Identity test (CI).** With δ = 0, κ = 1, N = −1.5, φ = ψ = 0 and no errors, m_s equals the 2024 margins and EV_D = 226.
2. **Error calibration.** Fit Λ on 1992–2012 and predict 2016, 2020 and 2024 from the prior lean plus the realized national margin. 80% intervals should cover 75–85%. Correlated misses (WI/MI/PA in 2016) should be inside the simulated spread.
3. **2026 out-of-sample.** Predict each Senate and governor race with its state's statewide races left out (House-based α̂_s, plus δ). Target MAE under 4 points and coverage of 70–90%. Compare against the model without style terms.
4. **Cases.**
   - **Spanberger and Sherrill (2025).** The interval predicted with the Gov-25 effect must contain the actual result.
   - **Platner (Maine).** Check whether left_populist + Republican incumbent + `rep_moderate` + Maine's House-based α reproduce the shift toward Republicans without Maine in the fit. If they do not, the copy says Maine is "mostly unexplained by archetype", not "populism failed".
   - **Mamdani.** Out of scope. The check is qualitative: the neighborhood shifts in `offyear.json` should agree in sign with the age and race tilts.
5. **Sim 5.** The aggregated House margin must be within 1 point of the `national.json` topline. Statewide margins must agree with the NYT leader-share buckets.
6. **Sim 3.** In-sample Brier score on the 2026 primaries, against a "poll leader wins" baseline.

---

## 7. Claims, limits, threats

**Can claim:**
- "In comparable 2026 races, after accounting for lean, incumbency, demographics, opponent and the state wave, [archetype] ran X points (80% range L to U) ahead of or behind mainstream liberals."
- "At environment N that moves Electoral College odds by ΔP."
- "[Archetype] needs about N\* to be a coin flip."

Every 2028 number is conditional on N, κ and the leans.

**Cannot claim:**
- Causation (quality, recruitment and fit are bundled into the archetype).
- That a named candidate "would lose".
- Forecasts.
- Lessons from any single race.
- Group claims beyond "in these nine races".
- Estimates for cells below the minimum N.

**The three biggest threats:**

1. **Unmeasured selection.** Populists are recruited where establishment Democrats look hopeless, progressives win safe or changing seats, and quality and money track both. *Mitigation:* the overlap estimate, close primaries, the permutation null, and "comparable races" language.
2. **Transfer from midterm to presidential race (κ, N).** National nominees are defined by national media, not local fit, and the midterm electorate and out-party bonus do not carry over. *Mitigation:* lead with N\* and the win-probability-vs-N curves, and sample κ.
3. **Thin, noisy classification.** There are about 70 statewide races, and "populist" is a judgement call. One race (Maine) can move a cell, and narratives can contaminate labels. *Mitigation:* blind pre-election coding, two-factor pooling, alternative classifications, DFBETAs, minimum-N greying, and holding out races until the canvass is done.

---

## 8. Reader-facing explanation

> **How this works.** We compared each 2026 Democratic nominee's result with how the same place voted for president in 2024. Then we asked whether progressives, populists, moderates and mainstream liberals ran ahead of or behind similar candidates in similar places, against similar Republicans, on the same ballot. That matters because Democrats gained almost everywhere. Small groups of races give unreliable answers, so we pull estimates toward zero unless the evidence is strong. We then carry those differences into 2028. You choose how good a year it is for Democrats and how much of a midterm candidate's edge survives a presidential race, because nobody knows either. Each scenario runs 10,000 times, with states moving together as they historically have. Take the ranges seriously: a two-point style difference can decide the winner, and so can uncertainty of that size.
