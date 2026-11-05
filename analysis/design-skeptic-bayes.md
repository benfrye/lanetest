# Design: Skeptical-Bayesian analysis and simulations

Angle: style effects are small until proven otherwise; 2026 is one noisy, confounded wave. Units: **two-party margin points (D−R)** (vote-share literature doubled).

---

## 1. Estimands

Reference category: **mainstream_liberal Democrat vs traditional Republican**.

| Symbol | Definition |
|---|---|
| δ_a | **Style effect** of archetype a: the expected change in a Democratic nominee's general-election margin from swapping a mainstream liberal for archetype a in the *same* district, against the same opponent, under the same environment. Measured in 2026 House and statewide races. |
| γ_a | How δ_a varies with electorate makeup, per 10 points of white non-college (WNC) share and of 18–29 share. |
| π | Presidential translation factor (assumption, default 1, range 0.5–2): 2028 style effect = π·δ_a. |
| V_a(E) | **Viability**: P(D wins ≥270 EV given archetype a, opponent type, and 2028 national environment E). |
| ΔV_a | V_a − V_mainstream_liberal, with a posterior interval. This is the headline number. |
| E*_a | **Break-even environment**: the national margin E at which V_a = 0.5. "A progressive needs an environment of D+x to be a coin flip." |
| B_a | **What you would have to believe**: the smallest π·δ_a (or γ_a) that makes ΔV_a ≤ −10 pts, and the posterior probability of that value. |

"Viability of X" = (ΔV_a with 80% interval, E*_a, P(ΔV_a < −10)); never V_a without its interval and E.

---

## 2. Data prep

**Outcome.** y_i = m_i^2026 − m_i^pres2024, where m is the two-party margin (100·(D−R)/(D+R)) and m^pres2024 is the 2024 presidential margin on the current lines. As a robustness check, use the raw margin.

**Sample tiers**
- **Main:** contested D-vs-R House races with |pres2024| ≤ 20, plus Senate and governor races.
- **Extended:** |pres2024| ≤ 30.
- **Full:** all contested races. Robustness only, because ceiling effects and low-effort campaigns make these races noisy.

**Exclude**
- Uncontested races, or races with no major-party opponent.
- Same-party generals (CA/WA top-two D-v-D).
- Races where a strong independent replaced the Democrat (e.g., an Osborn-type fusion candidacy).

**Partial counts.** p = pct_expected_vote_counted.
- p ≥ 0.95: included as is.
- 0.80 ≤ p < 0.95: included, with extra variance (sd_count = 25·(1−p) points; 5 points at p = 0.80).
- p < 0.80: excluded from the main fit and included in a "provisional" refit.
- CA, WA, OR, NV and AZ late ballots can lean one way, so counts there are *biased*, not just noisy. Require p ≥ 0.90 in those states, or add a per-state late-shift term with a N(+1, 2²) prior.
- Rerun nightly; stamp "data as of"; freeze at certification.

**Redistricting.** The baseline is always pres2024 on the *current* lines. house2024_margin and prev_seat_margin are used only where the `lines_changed` flag is false (TX, CA, MO, NC, OH, UT, etc. are flagged). Re-estimate without the redistricted states as a robustness check.

**Covariates (X_i)**
- **Incumbency:** D-inc / R-inc / open (two dummies).
- **Baseline shape:** m^pres2024 and its square. Waves compress at the extremes and swing is partly proportional.
- **Opponent:** Rep style (maga / traditional / moderate) and quality (held elected office; scandal flag).
- **Demographic-expected swing (critical):** ES_i = Σ_g s_ig·shift_g (district ACS race×education and age shares × NYT group shifts: WNC +14, Hispanic non-college +33, 18–29 +32, 65+ +6). Without it, progressives in young, Hispanic seats get credit for the wave's shape. Estimate its coefficient; don't fix it.
- **Not a main control:** spending, which is post-treatment (style drives small-dollar money, and winnable seats attract money). Robustness only.

**Classification hygiene.** Code archetypes *blind to results* from pre-election sources (endorsements: Justice Democrats, CPC, New Dems, Blue Dogs; platform; CFscores). A second coder does a 20% sample; report Cohen's κ.

---

## 3. Estimation

### 3a. Structural style parameterization (primary)

Code each nominee on two axes:
- **Leftness L:** moderate = 0, liberal = 1, left = 2 (conservative = −1).
- **Populism P:** establishment = 0, mixed = 0.5, populist = 1.

Archetype style effect, centered so mainstream_liberal (L=1, P=0) = 0:

```
δ(L,P,Z) = β_L·(L−1) + β_P·P + β_PW·P·W̃ + β_LY·(L−1)·Ỹ + u_a
```

- W̃ and Ỹ are the district's WNC and 18–29 shares, centered, per 10 pts.
- u_a is an archetype-specific deviation: u_a ~ N(0, τ_u²) with τ_u = 1.0. This shrinks each archetype toward the structural line, so 5 archetypes cost 4 core parameters plus small deviations.

### 3b. Race-level model

```
y_i = α_s(i) + θ_office(i) + X_i·β_X + δ(L_i,P_i,Z_i) + ε_i
ε_i ~ N(0, σ_office² + sd_count_i²)
α_s ~ N(0, σ_α²)                 state environment (random effect)
θ_office: House = 0; Senate, Gov ~ N(0, 3²)
σ_House, σ_Senate, σ_Gov: half-normal(6); statewide gets its own σ
```

Statewide races share δ via δ_statewide = λ·δ, λ ~ LogNormal(log 1.3, 0.3) (style better known statewide; N ≈ 60, so λ is mostly prior).

### 3c. Skeptical priors (literature-anchored)

| Param | Prior | Rationale |
|---|---|---|
| β_L | N(−1.5, 1.5²) per step | Left-vs-moderate prior is −3 ± 3. Hall (2015) close-primary RDDs found large extremist penalties, but local, pre-nationalization, and for very distant candidates. Split Ticket WAR and post-2012 work put ideology-linked differences at a few points. The prior mean takes the direction from the literature; the SD allows 0. |
| β_P | N(0, 1.5²) | No credible literature sign for populist posture. |
| β_PW, β_LY | N(0, 1.0²) per 10 pts | Interactions are assumed small. |
| Opponent MAGA vs traditional | N(+1, 2²) | Hall's penalty applied symmetrically. |
| τ_u | fixed 1.0 | Sensitivity range 0.5–2. |

### 3d. Computation

**Primary fit:** PyMC or NumPyro, 4 chains × 2000 draws. Check R̂ < 1.01 and divergences.

**Conjugate fallback** (numpy only, and what the browser reuses):
1. Fix σ on a grid (3 to 12 by 0.5).
2. Treat α_s as coefficients with N(0, σ_α²) priors. The model is then Gaussian-linear, so the posterior is closed form.
3. Weight the grid points by marginal likelihood.

**Data-only summary for the browser.** Marginalizing the controls under weak priors leaves Gaussian style coefficients b̂ (estimate) and V̂ (covariance). Ship b̂, V̂, μ0 and Σ0. With prior-width multiplier k and data-trust exponent α (a power prior), the browser computes, for a 4×4 system in JavaScript:

```
Σpost = (Σ0⁻¹/k² + α·V̂⁻¹)⁻¹
μpost = Σpost (Σ0⁻¹μ0/k² + α·V̂⁻¹b̂)
```

**Minimum-N rules**
- An archetype dummy estimate (u_a) is reported only with ≥15 main-sample races, including ≥5 with |pres2024| ≤ 10. Otherwise only the structural prediction is shown.
- An interaction term (β_PW, β_LY) is reported only with ≥30 races spanning ≥20 pts of W̃ or Ỹ.
- Senate and governor races are never reported as an archetype estimate on their own; only pooled.
- A candidate-specific effect needs ≥2 general elections.

### 3e. NYT 9-state Senate group evidence (descriptive layer)

For state s and group g:

```
r_sg = (shift_sg − shift_s) − (shift_g^nat − 15)
```

shift_s ≈ 0.47·Male + 0.53·Female. r_sg is the group's movement relative to its own state, net of the national House pattern. The populist thesis predicts that the education-gradient residual (HS minus Postgrad) is positive when the nominee is populist.

Preliminary numbers from the file:
- The national gradient is +8.
- MI +14, OH and IA +12 (non-college moved D more than nationally); Maine −2.
- Maine's overall shift was about −4 vs about +20 in AK/IA/KS/MS/NC/OH/TX, yet its 65+ and WNC rows sit only 3–4 pts below the national relative pattern. **Maine's gap is statewide, not group-specific**, as an incumbent's broad personal vote predicts (Collins ran ~17 pts ahead of Biden in 2020).

Fit r_grad,s = c + ψ·P_s + ζ·incumbent_opp_s + e_s with ψ ~ N(0, 3²). With N = 9, report ψ's posterior and its prior-to-posterior SD ratio. This is evidence for γ, not a standalone estimate.

### 3f. Robustness (all shown in a "how fragile is this" panel)

- **Leave-one-out:** each state, each Senate race, each archetype's 3 highest-leverage races, CA, redistricted states.
- **Alternative baselines:** prev_seat_margin; house2024 (unchanged lines only); 0.75·pres24 + 0.25·pres20.
- **Alternative classifications:**
  - high-confidence only;
  - an endorsement-only objective coding;
  - a **label-noise simulation** that randomly flips 15% of labels 500 times and reports the attenuation of β.
- **Placebo:** replace y with the 2024 outcome (house2024 − pres2024) in the same districts. A "progressive effect" in 2024 means persistent district features, not style. Subtract it, or flag it.
- **Alternative samples:** tiers; raw margin; with spending.
- **Prior sensitivity:** k ∈ {0.5, 1, 2, 4}, plus a flat prior.

---

## 4. Translation to 2028 states

State margin for an archetype-a Democrat vs Republican type r, in draw d:

```
M_s = E + B_s + T_s(u) + π·[δ_a + γ_a·(Z_s − Z̄)] − π·ω_r + c_c + H_c,s − H_r,s + ε_s
```

**E: national environment.** National popular-vote margin for a mainstream liberal vs a traditional Republican. Default prior is t5 with center D+3 and scale 6. It is an explicit slider, −10 to +15, with uncertainty scale 3–9.
- Regressing next presidential margin on prior midterm House margin (1994–2022, n = 8; re-verify inputs) gives slope 0.17 ± 0.25, predicting ~D+5 ± 5.5. The slope is indistinguishable from zero, so we center at D+3 rather than inherit the wave.

**B_s: state lean relative to the nation.**

```
B_s = 0.7·rel24 + 0.2·rel20 + 0.1·rel16 + η·(rel_shift26_s)
```

- rel = state margin − national margin.
- rel_shift26_s = state 2026 statewide House swing − national swing.
- η defaults to 0.25. Calibrate it by regressing state relative presidential swing on the prior midterm's relative swing (2006→08, 2010→12, 2014→16, 2018→20, 2022→24).
- ME/NE districts use district presidential margins.

**T_s(u): turnout composition.**

```
T_s = u·[(Σ_g w^pres_sg m^26_g − Σ_g w^mid_sg m^26_g) − national analogue]
```

- w = states.json demographics × turnout ratios (midterm from NYT voters/VEP, e.g. 18–29 12/20, 65+ 34/24; presidential from CPS 2024).
- u ∈ [−1, 1], default 0: +1 = 2026 group preferences carry to presidential-only voters; −1 = they lean R as in 2024. Moves AZ/NV/GA relative to ME/PA/FL.

**Opponent (ω_r).** MAGA-heir vs traditional takes the posterior of the House opponent coefficient. The generic Republican is a 50/50 mix.

**Named candidates**
- **Track record:** ô_c is the mean overperformance vs the presidential baseline across the candidate's n_c general elections, net of the archetype mean, incumbency and that year's environment. It is shrunk:

```
c_c = ρ·w_c·ô_c,  w_c = τ_c²/(τ_c² + σ_o²/n_c)
```

  - τ_c = 1.5 is the true candidate-specific SD.
  - σ_o = 5 for statewide races and 6 for House.
  - ρ = 0.5 compresses for presidential nationalization.
  - Three statewide races give w = 0.21: a +10 overperformer earns about +1.
- **Home state:** H ~ N(+2, 1.5²) in the nominee's home state, and +0.5 for the VP's. Applied to both parties.

**Errors: factor model, precomputed.**

```
ε_s = Σ_k F_sk f_k + σ_idio·v_s
f_k ~ N(0, 1);  v_s ~ t5
```

- Each column F_k is a standardized state loading × a scale. The k are 6 regions plus WNC, Black, Hispanic, college, evangelical and 65+.
- Calibrate the scales on 2000–2024 residuals of state relative swing, targeting a total state SD of about 3.5 and correlations of about 0.6–0.8 between similar states.
- Parameter uncertainty (δ, γ, ω, λ) is drawn per simulation from its posterior MVN. Through γ it loads onto the WNC and 18–29 factors, so it is correlated across states automatically.

---

## 5. Simulations (vanilla JS, Web Worker, seeded xoshiro128**)

**Shared engine:**
1. Draw per simulation: E, f (12 values), v (56 values), and parameters (Cholesky of a ≤8-dim posterior).
2. Compute M_s for 56 units (50 states, DC, ME-1/2, NE-1/2/3).
3. Allocate 538 EV (2020 apportionment holds through 2028).
4. Record the tipping point: sort units by M, accumulate EV from the most-D unit to 270.

10k draws × 56 units × 12 factors ≈ 7M multiply-adds, under 100 ms on a phone. Use common random numbers across scenarios so differences are not Monte Carlo noise. A 269–269 tie is shown separately.

**params.json (shared)**
```json
{"units":[{"id":"PA","ev":19,"B":-2.1,"Z":{"wnc":0.47,"y1829":0.19},"T_vec":0.4,"F":[...12]}],
 "E":{"center":3,"scale":6,"df":5},
 "style":{"mu0":[-1.5,0,0,0],"Sigma0":[[...]],"bhat":[...],"Vhat":[[...]],
          "names":["beta_L","beta_P","beta_PW","beta_LY"],"tau_u":1.0,"u_post":{"progressive":[m,sd],...}},
 "archetypes":{"progressive":{"L":2,"P":0.25},"left_populist":{"L":2,"P":1},
   "center_populist":{"L":0.5,"P":1},"mainstream_liberal":{"L":1,"P":0},"moderate":{"L":0,"P":0}},
 "opp":{"maga_heir":[m,sd],"traditional":[0,0]},
 "pi":{"default":1,"min":0.5,"max":2},"sigma_idio":2.5,"tie_rule":"separate"}
```

### Sim 1: Archetype simulator
- **Inputs:** archetype (or all 5), opponent (generic / Vance-type MAGA heir / Rubio-type traditional), E, u, π, and a **trust dial**: Skeptic (k 0.5, α 0.5), Agnostic (1, 1), Believer (3, 1), Data only (flat prior).
- **Outputs:** V_a with 80% interval; EV histogram; tipping-point frequencies; state map; ΔV_a forest plot; prior-vs-posterior strip for π·δ_a.
- **Interval for V_a:** use 200 parameter draws × 2,000 state draws (400k unit-draws) to separate parameter from outcome uncertainty.

### Sim 2: Named matchup matrix
- Dem rows × GOP columns, common E/f/v draws; inputs from candidates_*.json (archetype, home state, ô_c, n_c).
- **Cell display:** P(D win) binned to 5-point steps, plus median national margin. Hover gives a decomposition: archetype, track record, home state, opponent type.
- **Banner:** "Cells within 6 pts are statistically indistinguishable under our assumptions." It is computed from the parameter-draw SD of the cell differences.

### Sim 3: Democratic primary
- **Fit (Python):** on the 2026 primaries, model candidate log-share ratios:

```
log(s_ij/s̄_i) = ζ_a + η_a·Z_i + q_j
```

  - Z_i = Black share and white-college share of the district's Dem primary electorate.
  - Candidate quality q_j ~ N(0, 0.6²), with dummies for incumbency and money lead.
  - Prior means for η come from 2016/2020 primary exit polls: Black voters lean establishment; young voters and white-college liberals lean progressive. Prior SD is 0.5.
- **Browser, per draw:**
  1. Draw κ_c ~ N(0.3·log(poll_c/mean), 0.7²).
  2. Walk an editable calendar of state order and dates. Default is a 2024-like order (SC, NH, NV, MI) with alternatives.
  3. Compute shares: s_cs ∝ exp(ζ_a + η_a·Z_s^prim + κ_c + h_cs + μ·mom_c + e_cs), with e ~ N(0, 0.3²).
  4. mom_c = early-state delegate share minus 1/n.
  5. Allocate proportional delegates with a 15% threshold.
  6. After the 4th contest and after Super Tuesday, a candidate with <10% of delegates and no wins drops out. Their share is redistributed through a lane-affinity matrix (same archetype gets 0.6).
- **Outputs:** P(nominee), P(nominee archetype), P(no pledged majority), chained P(D wins) = Σ_a P(archetype a)·V_a.
- **Warning:** 40 House primaries weakly proxy a national primary; κ noise is deliberately wide.

### Sim 4: Build your own candidate
- **Sliders:** leftness L (0–2, continuous), populism P (0–1), home state (dropdown), track-record overperformance (−5 to +10, shrunk live), opponent, E, u, π, trust dial.
- **Calculation:** uses only the structural equation (no u_a), so it stays continuous.
- **Outputs:** V; a waterfall from E to national margin (environment → style → home → track record); the map; and a **"what you'd have to believe" heatmap**:
  - x axis = E (−6 to +12), y axis = π·δ (−8 to +4);
  - cells show P(win) from 2,000 draws per cell in a worker;
  - posterior 50% and 90% contours are overlaid, plus the reader's current point.

### Sim 5: 2026 as a presidential year
- **Steps, per state:**
  1. Aggregate 2026 House votes.
  2. Impute uncontested seats as pres2024 + the state's mean contested swing, with votes scaled by the 2024 presidential ratio.
  3. Apply three toggles:
     - raw;
     - presidential electorate: T_s with u = 1, then u = 0;
     - "durable share": subtract φ × (2026 national − E_default), φ ∈ [0, 1], to remove the out-party midterm penalty.
- **Outputs:** three maps with EV totals, φ slider, label "a translation, not a forecast"; states with p < 0.9 hatched.

---

## 6. Validation

1. **2024 back-test.** Fit B from 2016/2020 only, set E = −1.5 and δ = 0 (Harris as mainstream liberal), and simulate 2024. Targets:
   - Trump 312 EV within the 80% EV interval;
   - about 80% of states within their 80% intervals;
   - Brier score better than uniform swing.
   - Repeat for 2020 from 2012/2016.
2. **2026 posterior predictive.** For each race, compare y to its predictive interval. Check that coverage is 80% ± 5. Plot residuals vs p counted, pres2024, ES_i and state. A residual trend vs ES_i means the demographic control is mis-specified.
3. **Spanberger and Sherrill (2025).** Predict from VA/NJ pres2024 + the 2025 environment (mean special-election overperformance from offyear.json) + δ_moderate.
   - The useful contrast is the **same-ballot comparison**: Spanberger vs the VA LG and AG nominees share an environment, so their difference isolates candidate effects (archetype plus scandal).
   - Check whether δ̂ is consistent with that within-ballot gap.
4. **Mamdani.** This is a three-way, within-party general, so it is excluded from estimation. As a check, the sign of β_LY should match the neighborhood pattern of gains in young, renter-heavy areas. If β_LY is null but neighborhood gains are large, report the tension.
5. **Platner / Maine.** Predict with the Collins incumbency term (her 2020 overperformance of about +17, shrunk) and δ_left_populist. If the prediction covers the actual result **with δ = 0**, the story says Maine is explained by the incumbent, not the style. Show the posterior split between incumbency and style.
6. **Engine checks:** P(win) monotone in E; δ = 0 makes archetypes identical; seeded reproducibility; 10k draws < 1 s on a mid-tier Android; JS matches the Python reference to 1e-9 at the same seed.

---

## 7. What the story can and cannot claim

**Can claim:** "Net of lean, incumbency, opponent and the wave's demographic shape, styles performed within about X points"; "consistent with a Y-point penalty to a Z-point bonus"; "under E, archetype changes 2028 win probability by ΔV (interval)"; "E and π matter more than style"; break-even environments.

**Cannot claim:** that a progressive or populist *can't* or *will* win; that any 2028 individual's effect is measured; that populism "wins back" non-college voters (9 Senate races, Maine points the other way); single-race causal effects; anything from statewide races alone.

**Three biggest threats to validity**
1. **Selection on unobservables.** Who runs where, candidate quality (DCCC-recruited veterans tend to be moderates), and primary electorates are all correlated with style. The controls and the placebo help, but residual confounding could easily be ±2 points, which is the size of the effect we're looking for.
2. **Midterm-to-presidential translation.** House style ≠ presidential perceived ideology. A presidential nominee faces $1B+ of definition advertising, a nationalized electorate, and no midterm penalty. π is an unestimated assumption and often dominates the result.
3. **Measurement.** Noisy, possibly post-hoc labels attenuate δ toward zero, which can make a skeptical prior look confirmed; late Western counts bias early estimates.

---

## 8. Reader-facing explanation (≤150 words)

> Did Democrats who ran as progressives, populists or moderates do better in 2026? We compared each candidate with what you'd expect from their district's 2024 presidential vote, the size of this year's wave, who their opponent was, and who lives there. We started from what decades of research suggest, which is that a candidate's style usually moves the result only a few points, and let 2026 change that belief only as much as its noisy evidence allows. The answer comes with a wide margin of error, and we show it. Then we simulated 2028 thousands of times. Two assumptions matter most: how good a year 2028 is for Democrats, and whether a style that worked in a House race works the same way for president. You can move both sliders. Watch which one changes the answer more.
