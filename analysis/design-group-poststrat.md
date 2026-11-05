# Design: group-level effects + post-stratification

Angle: estimate how each Democratic archetype changes support *within demographic groups*, then rebuild 2028 state margins by post-stratifying on each state's presidential-year electorate. Race-level overperformance supplies the **level** of each archetype effect. Group data supplies its **shape**, meaning which voters it gains or loses. State composition turns that shape into geography.

Conventions: margin = D% − R% (two-party, in points). Positive means a shift toward D. All 2026 effects are measured **relative to the wave and relative to a reference archetype** (mainstream_liberal = 0), never in absolute terms.

---

## 1. Estimands

For archetype *a* ∈ {progressive, left_populist, center_populist, mainstream_liberal, moderate}:

- **Level** λ_a: the expected change in margin, in points, from being archetype *a* rather than mainstream_liberal, holding fixed demographics, partisan baseline, state environment, incumbency and opponent type, averaged over the national 2028 presidential electorate.
- **Tilt** θ_a = (θ_a,age, θ_a,edu, θ_a,nw, θ_a,hisp, θ_a,urb): extra margin at one end of each demographic contrast versus the other. Contrasts are centered over the national presidential electorate, so tilts move votes between states without changing λ.
- **State margin** M_s,a(ν): the expected 2028 margin in state *s* for a generic archetype-*a* nominee when the national environment is ν, plus SD_s,a.
- **Headline viability** V_a(ν) = P(EV_D ≥ 270 | archetype a, ν ~ prior), reported alongside the **archetype gap** ΔV_a = V_a − V_mainstream_liberal and the tipping-point margin TP_a. The story's main number is ΔV_a with its 80% interval, not V_a. V_a mostly reflects the environment assumption.

## 2. Data prep

**Inclusion rules (race-level model):**
- Keep generals with exactly one D and one R nominee (`uncontested=false`, `same_party_general=false`). Drop races where third parties exceed 10%; check D-aligned independents (Osborn-style) separately, coded as D.
- **Partial counts:** weight 1 if `pct_expected_vote_counted ≥ 95`, 0.5 if 80–95, excluded below 80; re-run nightly. A robustness spec drops CA, WA, OR, AZ, NV and UT, where late mail moves margins systematically.
- **Main sample:** |pres2024_margin| ≤ 25. Safe seats enter only a secondary logit-scale spec, because ceilings compress shifts.
- **Classification:** races with `style_confidence < 0.6` keep their archetype at half weight in the main spec and are dropped in a robustness spec.

**Outcome.** y_r = margin_2026,r − pres2024_margin_r, both two-party and with the baseline on current lines. Secondary outcome: Δlogit of the two-party D share, which handles ceilings such as Black voters at roughly 90% D. The MS row in the 9-state table shows the ceiling: nonwhite minus white = −8, against a 9-state mean of +7.

**Redistricting.** pres2024 on current lines (DRA/Downballot recompiles) is the only baseline valid for every seat. Flag `lines_changed` (TX, CA Prop 50, MO, NC, OH, UT and any others). Use `prev_seat_margin` and `house2024_margin` only on unchanged seats, as robustness checks.

**District composition z̄_d,k.** This is a needed extra pull: ACS 2024 CD tables of CVAP by age, race × education, and urbanicity (density or Census urban share). Without it, the House data cannot inform tilts and only λ is estimable.

**State cell frame.** Cells g = race(4: White, Black, Hispanic, Asian/Other) × education(2) × age(4) = 32. Get joint VEP counts N_s,g from ACS PUMS. Fallback: rake the marginals in states.json onto a national joint seed by IPF.

**2024 cell support.** National 2024 group margins come from the NYT file as 2026 margin − shift. The implied 2024 values are:

| Group | Implied 2024 margin |
|---|---|
| 18–29 | D+9 |
| 65+ | R+1 |
| White non-college | R+33 |
| White college | D+7 |
| Hispanic | D+11 |
| Black | D+74 |

Cross-check against AP VoteCast and Pew validated data.

State cells: logit p_s,g = logit p_g + κ_s + κ_s,white·White_g. Solve κ_s so the post-stratified total reproduces the actual 2024 state margin exactly. κ_s,white is fit where 2024 state exit or VoteCast data exist; elsewhere it is predicted from white evangelical % and region and shrunk.

**2024 turnout.** t_s,g comes from CPS 2024 Voting Supplement rates by cell, scaled by a state constant so Σ N·t equals actual 2024 ballots.

## 3. Estimation

Tilt covariates z_g,k, each centered on the national 2024 presidential electorate: age (18–29 = +1, 30–44 = +⅓, 45–64 = −⅓, 65+ = −1); edu among whites (non-college +½, college −½); nw and hisp indicators; urb, a standardized density index.

**Model H (House, race-level, ecological):**

```
y_r = α + Σ_k φ_k z̄_r,k                      # demographic shape of the wave
        + u_state(r)                           # state environment, coattails; u ~ N(0, σ_u²)
        + λ_a(r) + Σ_k θ^H_a(r),k z̄_r,k        # archetype level + ecological tilt
        + β_inc Inc_r + β_open Open_r
        + β_maga MAGA_r + β_q RQualFlag_r
        + s(pres2024_r)                        # natural spline, 3 df, for ceiling/regression to mean
        + e_r,         e_r ~ N(0, σ_e² / w_r)
```

- λ_a ~ N(0, τ_λ²) with τ_λ = 3 points (partial pooling; reference fixed at 0).
- θ^H_a,k ~ N(0, 2²).
- Fit with `statsmodels` MixedLM or PyMC. A plain normal hierarchy is enough.
- φ_k absorbs the "the wave was bigger among young and Hispanic voters" pattern. Archetype effects are therefore what remains after a district's demographics predict its share of the D+13 wave.

**Model S (Senate/governor, race-level):** the same right-hand side, without the ecological tilt. Add **R-incumbent personal vote** π_R = that Republican's last margin − pres margin in the same year. For Collins this is roughly +17 from 2020. With N≈35+36 races, these models only inform λ through a joint likelihood with H, with a fixed effect for office.

**Model G (9-state Senate group table, direct tilts):** for state *s* and contrast *k*:

```
c_s,k = (shift_s,hi(k) − shift_s,lo(k)) − (nat_shift_hi(k) − nat_shift_lo(k))
c_s,k = θ_a(s),k + γ_k π_R,s + η_s,k,     η_s,k ~ N(0, ω_k²)
```

Convert to the logit scale with each group's 2024 state support before differencing. This removes ceiling artifacts like MS.

Raw contrasts available now:

| Contrast | 9-state mean | SD | Notable states |
|---|---|---|---|
| Age (18–29 − 65+) | 32 | 4.4 | ME 36, TX 40, IA/KS 27; national House: 26 |
| White non-college − white college | 3.4 | 4.9 | ME −4, MI/OH +10; national House: 5 |

Because N = 9 and some archetypes appear once, ω_k is set from the between-state SD (about 4–5 points), not estimated per archetype.

**Model M (off-year transport):** the same contrast regression on precinct or neighborhood shifts against 2024 presidential results. NYC 2025 neighborhood types (Mamdani share − Harris share, since the three-way race has no two-party meaning) inform the progressive tilt. VA and NJ 2025 precincts (Spanberger, Sherrill) inform the moderate tilt. Mamdani vs. Sherrill in adjacent Hudson/Queens neighborhoods is the cleanest same-day contrast.

**Combining tilt sources (normal-normal meta-analysis):**

```
θ_a,k = [ Σ_j θ̂^(j)_a,k / (SE_j² + ψ_j²) ] / [ 1/σ_θ² + Σ_j 1/(SE_j² + ψ_j²) ],   σ_θ = 3
```

Transport inflation ψ_j:

| Source | ψ_j |
|---|---|
| House ecological | 1.5 |
| Senate group | 1.0 |
| Off-year statewide | 2.0 |
| Mamdani | 3.0 |

λ_a is combined from H and S the same way. Exit-poll crosstabs by candidate (state exits) enter Model G as extra rows where available.

**Uncertainty.** Block bootstrap over states (B = 2000), refitting every model, gives joint draws of (λ_a, θ_a). Store the mean and covariance per archetype; the browser samples that MVN through a precomputed Cholesky factor.

**Minimum-N rules:** publish λ_a only with ≥ 15 included races across ≥ 5 states. Publish a direct tilt only with ≥ 2 states in Model G or ≥ 25 House races; otherwise θ_a,k reverts to the prior (0) and the UI says "no direct evidence: assumes the average Democrat's demographic pattern." Primary-model archetype coefficients need ≥ 4 primaries.

**Robustness (appendix table):** leave-one-state-out (especially CA, TX, ME); leave-one-source-out for tilts; alternative baselines (prev_seat_margin, house2024, mean of pres2020/2024, on unchanged seats); logit outcome; high-confidence classifications only, plus borderline candidates moved to the adjacent archetype; competitive-only vs. all seats. Two design checks matter most:
- **Close-primary RD** (Hall extremist-penalty design): from primaries.json, progressive-vs-moderate primaries decided by < 10 points, comparing general-election y.
- **Placebo:** regress the same seat's 2024 overperformance on its 2026 nominee's archetype. A nonzero "effect" signals a district or candidate confound, not style.

## 4. Translation to 2028 states

**Presidential-year turnout:**

```
logit t^28_s,g = logit t^24_s,g + T_0 + T_age·age_g + T_nw·nw_g + μ_a·LP_g
```

- LP_g marks low-propensity cells: 18–29, non-college, Hispanic.
- μ_a (archetype mobilization) defaults to 0. The 2026 data cannot identify it until voter-file vote history is updated in 2027. It is a labeled scenario slider.
- Weights: W_s,g = N_s,g · t^28_s,g / Σ_g N_s,g · t^28_s,g.

**Support in each cell** (linear in margin, near p):

```
m_s,g,a = m^24_s,g + ν + ε_g + λ_a + Σ_k θ_a,k z_g,k + O_opp
M_s,a   = Σ_g W_s,g m_s,g,a
```

In implementation, the archetype terms are added on the logit scale and the result is converted back. A linear Jacobian is precomputed (see §5).

Because tilts are centered nationally, the archetype's state-specific bump is θ_a · (z̄_s − z̄_nat), with z̄_s = Σ_g W_s,g z_g. A young-tilting archetype gains in states with more 18–29 voters. A white-non-college-tilting one gains in WI, MI, PA, IA and OH relative to GA, AZ and NV.

**Midterm-to-presidential electorate.** Effects are estimated among midterm voters (34% aged 65+, vs. about 24% of VEP); expressing tilts per cell lets post-stratification reweight automatically.

**National environment ν.** ν is the 2028 two-party popular-vote margin minus 2024's (R+1.5), an explicit slider with prior ν ~ N(+4.5, 5²), i.e. a national margin near D+3. Out-party midterm margins have historically decayed by the next presidential race (2018 D+8.6 → 2020 D+4.5; 2010 R+6.8 → 2012 D+3.9), so D+13 is not inherited; in an open-seat 2028, only part of the incumbent-party penalty persists. The pipeline should replace this center with a 1998–2024 midterm → next-presidential regression.

**Opponent O_opp.** O_opp = β_maga·[opp = MAGA heir] from Model H/S as a level shift only. Default "generic R" = 0.5·β_maga.

**Named candidates c:**

```
M_s,c = M_s,a(c) + ρ_c·(P_c − λ_a(c))·κ_nat + H·1[s = home_c] + (H/3)·1[s in home division]
ρ_c   = σ_P² / (σ_P² + σ_noise²/n_c)      # shrinkage of the track record
```

P_c is candidate *c*'s mean overperformance of the presidential baseline across n_c past generals (candidates_dem.json). σ_P = 2 is the true spread of personal effects and σ_noise = 5 the per-race noise. κ_nat = 0.5 because only half a personal vote travels beyond the home state, where it applies in full. H ~ N(2, 1.5²) is the presidential home-state effect. GOP candidates are handled symmetrically (sign reversed, archetype ∈ {maga, traditional}).

## 5. Simulations (vanilla JS, ≤ 1 s for 10k draws on a phone)

**Shared precomputed file `params.json`:**

```json
{
  "units": [{"id":"PA","ev":19,"votes24":7.0e6,"base24":-1.7,"region":"rust",
             "Jtilt":[0.12,0.08,-0.10,-0.06,0.03],   // dM_s/dθ_k at current support (Jacobian)
             "Jturn":[...],                           // dM_s/dT_0, dT_age, dT_nw, dμ
             "Lfac":[...8 loadings...],               // group-factor loadings = W_s,g aggregated
             "sd_idio":2.0, "home_div":"MidAtl"}],    // 50 states + DC + ME1,ME2,NE1-3
  "arch": {"progressive":{"mean":[λ,θ1..θ5],"chol":[[...]],"n":..,"evidence":"direct|prior"}, "...": {}},
  "opp": {"beta_maga":{"mean":-1.5,"sd":1.0}},
  "env": {"nu_mean":4.5,"nu_sd":5.0},
  "err": {"fac_sd":[...8 group-factor SDs...],"region_sd":2.0,"state_sd":2.0,"t_df":6},
  "home": {"H_mean":2.0,"H_sd":1.5,"kappa_nat":0.5},
  "candidates": {"dem":[{"id":"...","arch":"...","home":"..","P":..,"n":..,"rho":..}],"gop":[...]}
}
```

`Jtilt` is the Python-computed derivative of the full logit post-stratification. Python verifies the linear approximation errs by < 0.3 points over ±2 SD of every parameter; where it does not, ship a 5-point interpolation grid instead.

**Correlated error per draw:** ν and the archetype draw (λ, θ) are shared across all states. Eight group factors ε_f ~ N(0, fac_sd_f) (young, white non-college, white college, Black, Hispanic, Asian, rural, evangelical/Mormon) load through Lfac_s, so demographically similar states co-move without a hand-set matrix. Add a region shock and an idiosyncratic Student-t(6) shock. Calibrate the SDs against 2016–2024 back-tests: a total state SD of about 6–7 points two years out, with about 70% of the variance correlated.

**Engine:** mulberry32 PRNG plus Box–Muller, Float64Array buffers, about 56 units × 20 multiply-adds per draw. Common random numbers across scenarios keep archetype differences free of Monte Carlo noise. Tallies per draw: tipping point (sort units by margin, accumulate EV from the most-D unit to ≥ 270), a separate 269–269 "tie → House" outcome, and national margin = Σ votes_s·M_s / Σ votes_s.

### S1. Archetype simulation
Inputs: `{arch, opp:"generic|maga|traditional", nu_mean, nu_sd, T0, T_age, mu}`. Defaults come from params.

Algorithm: for i in 1..10k, draw ν, (λ, θ) from the archetype MVN, ε_f, region, and idio. Then M_s = base24_s + ν + λ + Jtilt_s·θ + Jturn_s·T + Lfac_s·ε + r + e.

Outputs: P(win) with MC SE, EV histogram, popular vote vs. EC gap, tipping-point frequencies, a P(D) map, a **decomposition bar** splitting the gap from mainstream_liberal into level, tilt and turnout, and a direct/prior evidence badge per tilt.

### S2. Named matchup matrix
Inputs: `{dem_ids[], gop_ids[], nu, ...}`. Compute M_s for each pair with candidate terms, using the same 10k draws for every cell. Each draw also takes one draw of H and of each ρ-shrunk personal effect (σ = ρ_c·σ_P).

Cost is nD × nR × 10k × 56: about 34M operations for 10×6, roughly 150 ms. Fall back to 4k draws if the device benchmark is slow.

Outputs: a P(win) heatmap, per-cell 80% EV interval, row and column means, and the note "differences under 5 points are within model noise."

### S3. Democratic primary simulation
A separate group model, fit on primary electorates.

Fit (in Python) a multinomial-logit ecological model on primaries.json:

```
log(s_a,j / s_ML,j) = α_a + β_a · z̄_j + δ_cand
```

z̄_j covers district primary-electorate composition: Black share, Hispanic share, college share, age, and urbanicity. Then post-stratify on each state's Democratic primary electorate composition, using 2020/2024 exit polls or voter-file primary turnout, to get archetype strength A_s,a.

JS inputs:

```
{field:[{id,arch,home,poll_share}], calendar:"2024|traditional|custom",
 w_poll:0.5, momentum:{mean:0.3,sd:0.15}, dropout:{cum_share_lt:0.10, after:"Super Tuesday"},
 threshold:15, transfer:"ideological-adjacency matrix 5x5"}
```

Algorithm per draw: utility U_c,s = log A_s,a(c) + w_poll·log poll_c + home bonus + national candidate shock + state noise; shares are the softmax of U. Process the calendar in date order, awarding proportional delegates above 15%. After each date, add momentum to the winners' national shock, drop candidates under the threshold, and move their support through the transfer matrix (mostly to the same or adjacent archetype).

Outputs: P(nomination), P(no pledged majority), a delegate fan chart, and archetype-of-nominee probabilities (which can feed S1 as an "expected nominee" blend). Prediction-market odds are shown alongside for comparison, never used as input.

### S4. Build-your-own candidate
Fit a continuous version of Model H by replacing archetype dummies with ideology x ∈ [−1, 1] (left → conservative) and posture y ∈ [0, 1] (establishment → populist):

```
λ(x,y) = b1 x + b2 y + b3 xy;     θ_k(x,y) = c1k x + c2k y
```

The coefficients are shipped with a joint covariance.

Sliders: ideology, posture, home region, personal quality (−2..+2 SD of σ_P), ν, T0, T_age, T_nw, μ, and opponent. Runs the S1 engine. If (x, y) lies outside the convex hull of observed 2026 nominees, for example conservative-populist, the UI shows a warning that the estimate is extrapolated, and the parameter SD is doubled.

### S5. "2026 as a presidential year"
Three toggleable views:
- **(a) Raw:** statewide 2026 House two-party vote, summing districts. Uncontested seats are imputed as pres2024 + state House swing; partial-count states are hatched. Converted to EV.
- **(b) Electorate-adjusted:** each state's implied 2026 cell support (2024 cells + national group shifts + state residual κ^26_s fit to the statewide House vote) is reweighted to presidential-year turnout W. The young and nonwhite share rises, which likely moves margins toward D.
- **(c) Penalty-adjusted:** (b) minus the out-party midterm bonus, using a slider with default = (2026 national margin − ν_mean).

Uncertainty: draws of κ^26 residual SE and group-factor errors. Outputs: three maps, EV totals, and states that flip between views.

## 6. Validation

1. **Machinery back-test (2020 → 2024):** calibrate κ on 2020, apply national 2020 → 2024 group shifts, and predict 2024 states. Compare RMSE with uniform swing. If demographic post-stratification does not beat uniform swing, ship uniform swing plus tilt only.
2. **2026 reproduction:** predict each statewide House vote and Senate margin from 2024 cells + NYT national group shifts on the midterm electorate. The residuals are the "state + candidate" signal. Check that the archetype explains part of them and that the predictions agree with NYT's state buckets.
3. **Model G leave-one-out:** predict each of the 9 states' age and education contrasts from the other 8. Report 80% interval coverage.
4. **Named cases:**
   - *Platner/Maine:* the model should reproduce ME's R shift (about −4 overall, 65+ −16) mainly through π_R (Collins). If it needs the archetype tilt, report that ME alone drives the left-populist tilt and show results without ME.
   - *Spanberger/Sherrill:* with the 2025 environment and an off-year electorate, the moderate archetype should land within the 80% interval of their margins.
   - *Mamdani:* with NYC held out, the progressive tilt should predict the sign of the neighborhood-type shifts (young renter areas up; Orthodox and some Asian and Hispanic areas relatively down). A wrong sign means the tilt does not transport.
5. **Calibration:** 5-fold-by-state House CV; 80% predictive intervals should cover 75–85%.
6. **Sanity:** with ν = 0 and archetype = reference, P(win) should be about 45–50%, given 2024's small EC bias. No archetype gap should exceed what |Δλ| ± tilts imply.

## 7. Claims and threats

**Can claim:**
- "Relative to comparable Democrats in the same wave, archetype X ran Y points ahead or behind (80% interval …)."
- "X's gains were concentrated among [groups]; applied to the 2028 map, that pattern helps or hurts in [states]."
- "Under a stated environment, the archetype gap in win probability is Z (interval)." This is likely much smaller than the swing from ν alone, which is itself a finding.

**Cannot claim:** that style *causes* the difference; that any archetype "can't win"; that populists mobilize nonvoters (μ is not identified); that Mamdani's coalition generalizes nationally; or any number to better than about ±2 points.

**Three biggest threats:**
1. **Selection on unobserved candidate quality and opponents.** Who runs where, and who they face, are not random. Collins's personal vote in Maine shows how a single opponent can masquerade as a style effect. Controls and the close-primary RD reduce this but do not eliminate it.
2. **Transport from a D+13 midterm to an open presidential race.** In a wave, anti-Trump voters may have voted D regardless of style, which compresses λ. A $2B presidential campaign defines the nominee nationally and can erase local brands or amplify them. The midterm electorate differs as well.
3. **Measurement.** The group shifts are themselves MRP estimates with priors. Style coding is noisy, which attenuates λ toward 0. Direct tilt evidence rests on 9 Senate races, so most tilts will be prior-dominated, and the UI must say so.

## 8. Reader-facing explanation (≤150 words)

> We asked a simple question: in 2026's Democratic wave, did some kinds of Democrats do better than others *with the same voters*? We compared each candidate to what their district's or state's demographics predicted, and looked at which groups (younger voters, non-college white voters, Hispanic voters) each style gained or lost. Then we applied those patterns to each state's likely 2028 presidential electorate, which is younger and more diverse than the midterm crowd. The national mood in 2028 is your choice: we don't assume 2026's landslide carries over. Each simulation runs 10,000 versions of the election, with errors that hit similar states together. Treat the results as rough: the differences between candidate styles are real but small next to the uncertainty about the national environment, and several estimates rest on only a handful of races.
