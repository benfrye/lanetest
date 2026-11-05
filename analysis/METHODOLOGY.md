# METHODOLOGY: 2026 candidate styles and 2028 viability

Status: final design, 2026-11-04 (day after the midterms). This is the single source of truth for the Python pipeline (`analysis/pipeline/`) and the browser engine (`site/src/lib/engine/`). Where this file conflicts with any `design-*.md`, this file wins. The decision log is in `analysis/methodology_decisions.md`.

The backbone is the skeptical-Bayesian design (highest judge aggregate, 21.5). It is modified to remove its directional default prior and its prior-driven statewide multiplier, and it is strengthened with the race-regression design's identification and copy-gating machinery. A few honesty devices come from the group-poststrat design.

**Conventions**
- All margins are **two-party D−R points**: `m = 100·(D−R)/(D+R)`. Positive means Democratic.
- "Shift" or "swing" is always toward D when positive.
- The reference category everywhere is a **mainstream_liberal Democrat vs a traditional Republican**.
- Intervals are 80% unless stated. 95% intervals appear only in the methods drawer.
- Every number carries `data_as_of` and is labelled **preliminary** until certification.

---

## 1. Estimands and headline questions

### 1.1 Symbols

| Symbol | Definition |
|---|---|
| `y_i` | Wave-relative race outcome: `m_i^2026 − m_i^pres2024` (current lines). |
| `raw_a` | Unadjusted mean of `y_i` over archetype-a nominees in the main sample. This is the guess-first number. |
| `δ_a` | **2026 style effect.** Expected difference in `y` between an archetype-a nominee and a mainstream liberal on the **same state ballot** (same wave), with the same 2024 lean, demographic exposure to the wave, incumbency, opponent type and office. Identified from within-state contrasts only (§3.2). |
| `β_L`, `β_P` | Structural style slopes: per step of leftness L and per unit of populist posture P. `δ_a = β_L·(L̄_a−1) + β_P·P̄_a + u_a`. |
| `γ` = (`β_PW`, `β_LY`) | Style × composition interactions: populism × white non-college share, and leftness × 18–29 share, per 10 points of share. |
| `π` | Midterm→presidential **transfer factor**. A 2028 national style effect equals `π·δ_a`. This is an assumption with a visible slider. |
| `E` | 2028 national two-party margin for a **mainstream liberal vs a traditional Republican**. This is an assumption, never inherited from 2026. |
| `u` | Turnout-geography parameter in [−1, 1] (§5.3). |
| `V_a(E)` | P(D ≥ 270 EV \| archetype a, opponent, E, π, u). |
| `ΔV_a` | `V_a − V_mainstream_liberal` under common random numbers, with an interval over parameter draws. |
| `E*_a` | **Break-even environment**: the E at which `V_a = 0.5`. Reported as an integer with an interval. |
| `B_a` | **What you'd have to believe**: the smallest `π·δ_a` that makes `ΔV_a ≤ −10` points at the default E, plus the posterior probability of a value at least that large. |

### 1.2 Headline questions the story answers

1. **Q1: Who beat the wave?** Raw `raw_a` first (a guess-first beat). Then where each archetype ran (common-support plots). Then the adjusted `δ_a` with intervals, and a decomposition of `raw_a − raw_ml` into lean, demographics, incumbency, opponent, state wave and style.
2. **Q2: Does it matter for 2028?** Win-probability-vs-E curves for all five archetypes on one chart, with `E*_a` marked. Plus `ΔV_a` at labelled environments.
3. **Q3: How much rides on assumptions?** The trust dial (prior vs data), the `π` and `u` sliders, the "what you'd have to believe" heatmap and `B_a`, and the fragility forest plot.
4. **Q4: Named matchups.** A conditional matrix of P(D win), binned to 5-point steps, with an indistinguishability banner.
5. **Q5: The primary.** Who wins the nomination under stated coalition, calendar and field assumptions.
6. **Q6: 2026 as a presidential map.** A translation, not a forecast. The default view is penalty-removed.

The headline viability triple per archetype is `(ΔV_a with interval, E*_a with interval, P(ΔV_a < −10))`. A bare `V_a` is never shown without its E and interval.

### 1.3 What the story explicitly does not answer

- Who will win in 2028. Every 2028 number is conditional on E, π and u.
- The causal effect of ideology. Archetype bundles candidate quality, recruitment, money and fit. The story's language is "in comparable races".
- Whether a named person "can" or "can't" win.
- Whether populists "win back" non-college voters. The direct group evidence is 9 Senate races, one nominee per state.
- Whether any style mobilizes nonvoters. Mobilization is not identified, so there is no parameter for it.
- Lessons from any single race (Maine, Mamdani, Spanberger). These are validation cases and story color, never estimates.
- Any style difference to a precision better than about ±2 points.

---

## 2. Data prep and inclusion rules

### 2.1 Inputs

**Already in the plan**
- `research/house/*.json`, `senate.json`, `governors.json`
- `primaries.json`, `offyear.json`, `national.json`, `nyt_voter_trends.json`, `geography.json`, `ballot_measures.json`, `states.json`
- `candidates_dem.json`, `candidates_gop.json`, `analyst_takes.json`

**Extra pulls the race schema does not contain.** Each has a day-one fallback.

| File | Content | Day-one fallback |
|---|---|---|
| `research/districts_acs.json` | ACS 2024 CVAP shares on **current (2026) lines**: race × education (WC, WNC, Black, Hispanic, Asian, Other), age (18–29, 30–44, 45–64, 65+), urbanicity. For mid-decade maps (TX, CA Prop 50, MO, NC, OH, UT and any others) aggregate block groups to the new lines with the Census block-assignment files, or use DRA demographics. | Rows lacking it get the state-level ES value plus a `es_imputed` dummy (§3.9, Level 3). |
| `research/hist_pres_states.json` | State presidential results 1992–2024 (MIT Election Data + Science Lab) | Calibrate errors on the 2016→20 and 2020→24 transitions only, with priors (§5.6). |
| `research/hist_midterm_statewide_house.json` | Statewide House two-party vote 2006–2022, uncontested seats imputed | `ψ` = 0.2 default, labelled "uncalibrated" |
| `research/cps2024_turnout.json` | National 2024 CPS turnout rate by age, race and education | `r^pres_g = 1 + 0.5·(r^mid_g − 1)`, labelled an approximation |
| `research/primary_exitpolls_2016_2020.json` | Dem primary coalition slopes (Black, young, white college) | Coalition priors N(0, 0.5²) |

### 2.2 Margin construction

- **Race rows:** `m = 100·(dem_pct − rep_pct)/(dem_pct + rep_pct)`.
- **pres2024 baseline:** if the row carries only a total-vote margin, convert with `m2 = margin / (1 − o)`. Here `o` is the district's 2024 third-party share if known, else the state's (`1 − (dem_pct+rep_pct)/100` from `states.json`).
- **State rows:** `states.json` 2024 has `dem_pct` and `rep_pct`, so compute the two-party margin directly. 2020 and 2016 rows have only a margin. Convert with national D+R shares (2020: 98.2%; 2016: 94.3%). Flag UT-2016 (McMullin) and never use it in a lean.
- **`E24`** = national two-party 2024 margin, computed from certified state totals. From `states.json` state rows it is −1.43.
- **Ranked-choice races (ME, AK):** final-round two-party margin. The first round is a robustness check.

### 2.3 Inclusion: estimation sample

| Rule | Treatment |
|---|---|
| Uncontested, or no major-party opponent | Exclude. Imputed only for Sim 5 and statewide House totals (§6.6, Sim 5). |
| Same-party general (CA/WA top-two D-v-D, R-v-R) | Exclude. Imputed like uncontested for Sim 5. |
| Dem-backed independent, or Dem withdrew (Osborn type); any third candidate ≥ 10% | Exclude. Coded `independent_backed`, descriptive only. |
| No `pres2024_margin` on current lines | Exclude until it exists. **Never** substitute old-line baselines. Report the count by archetype. |
| `house2024_margin`, `prev_seat_margin` | Used only where `lines_changed == false` **and** the prior race was contested. Robustness and placebo only. |
| Main sample | Contested D-v-R House with \|pres2024\| ≤ 20, plus all contested Senate and governor races (Nov 2026), plus 2025–26 special elections |
| Extended sample | \|pres2024\| ≤ 30 (robustness) |
| Full sample | All contested races, on the logit-share scale (robustness) |
| 2025 VA/NJ governor | Validation only. Their period intercept absorbs them, so they carry no δ information. |
| NYC mayor (Mamdani) | Validation and sign check only. Three-way, within-party, not on the margin scale. |

### 2.4 Partial counts (bias, not just noise)

Let `p = pct_expected_vote_counted / 100`.

- **`p ≥ 0.95`:** used as is.
- **`0.80 ≤ p < 0.95`:** included. Two adjustments:
  - The observed `y` is treated as a noisy measurement of the final `y*`, with extra SD `sd_count = 25·(1−p)` points (5 points at p = 0.80).
  - Expected late shift: `E[y* − y_obs] = g_s·(1−p)/0.2`. The prior for `g_s` is N(m_s, 2²): `m_s = +1` for CA, WA and OR, where late mail leans D, and `m_s = 0` for AZ, NV, UT and all other states. Replace `m_s` with the state's 2024 (certified − day-after) shift if the pipeline has it.
  - `y*` is sampled as a latent variable in the Gibbs sampler (§3.4).
- **`p < 0.80`:** excluded from the main fit and included in a **provisional refit** (same machinery, with the formula extended).
- **Selection report (required):** for each archetype, the share of its main-sample races excluded for `p < 0.80`. If any archetype has > 20% excluded, its headline numbers carry a "provisional: slow-counting Western seats missing" badge (`copy_flags.provisional_archetypes`), and the provisional refit is shown beside it.
- **Do not** hard-hold-out races below 95%. That removes West Coast progressive seats non-randomly.
- **Rerun nightly.** Stamp `data_as_of`. Freeze at certification.

### 2.5 Style labels (three label sets)

The research agents are coding labels on Nov 4, after the results, so labels are exposed to post-election narratives. Mitigations:

- **Set A, agent-coded.** `ideology`, `posture`, `archetype`, `style_confidence`.
  - Each label must cite at least one source dated **before 2026-11-03**. The pipeline audits source dates; it does not assert a `coded_at` time.
  - Labels with no pre-election citation are flagged `post_hoc` and replaced by Set B where Set B exists.
- **Set B, rule-based (co-primary).**
  - Justice Democrats, CPC membership, or a Sanders/Our Revolution/WFP endorsement → `ideology = left`.
  - Blue Dog or New Democrat membership/endorsement → `moderate`.
  - Otherwise → `liberal`.
  - Posture comes from a fixed lexicon score on pre-election campaign text (anti-corporate, "billionaires", "rigged", working-class framing vs institutional framing). Thresholds are set before results are joined.
- **Set C, soft.** A probability vector over archetypes. The structural model uses the expected coordinates `E[L]`, `E[P]`.
- **Second coder.** A 20% random sample is recoded from pre-election sources with results hidden. Report Cohen's κ for archetype, ideology and posture.

**Coordinates**
- Leftness `L`: conservative −1, moderate 0, liberal 1, left 2.
- Posture `P`: establishment 0, mixed 0.5, populist 1.

**Archetype centroids** `(L̄_a, P̄_a)` are the **empirical means** of the 2026 nominees in each archetype, not assigned values. Expected values are roughly:

| Archetype | L̄ | P̄ |
|---|---|---|
| progressive | 2 | 0.25 |
| left_populist | 2 | 1 |
| center_populist | 0.5 | 1 |
| mainstream_liberal | 1 | 0 |
| moderate | 0 | 0 |

**Main fit labels:** Set A where it has a pre-election citation, else Set B. There is **no likelihood weighting by `style_confidence`**. Confidence enters only through the robustness runs: high-confidence (≥ 0.7) only, Set B only, and Set C soft.

### 2.6 Controls (X)

**Incumbency**
- `inc_D`, `inc_R` (open seat is the reference).
- `R_inc_pv`: the Republican incumbent's personal vote. It equals the incumbent's last general margin minus the same-geography presidential margin of that cycle (unchanged lines or statewide), sign-flipped to D-positive, else 0. Collins ≈ −17 enters here.
- `D_inc_pv`: the same quantity for Democratic incumbents.

**Opponent**
- `rep_maga`, `rep_moderate` (traditional is the reference).
- `rep_quality`: count of `quality_flags`. These are held elected office (+1) and scandal (−1, entered separately as `rep_scandal`).

**Baseline shape**
- Natural spline in `m^pres2024`, knots at −10, 0, +10. This handles ceilings and regression to the mean.

**Demographic-expected swing (the wave's shape).** Two separate terms with **estimated** coefficients. They are never summed, which avoids double-counting overlapping partitions.
- `ES_re_i = Σ_g c_ig·shift_g` over race×education cells. Shifts from NYT: WC 9, WNC 14, Black 9, Hispanic 28, Asian 17, Other 17.
- `ES_age_i` over age cells: 18–29 32, 30–44 24, 45–64 13, 65+ 6.
- `c_ig` are district CVAP shares weighted by the NYT midterm turnout ratios `r^mid_g = voters_g / vep_g`:

| Group | r^mid_g |
|---|---|
| White | 70/63 |
| Black | 11/12 |
| Hispanic | 10/14 |
| Asian | 4/5 |
| Other | 4/5 |
| 18–29 | 12/20 |
| 30–44 | 21/25 |
| 45–64 | 33/31 |
| 65+ | 34/24 |
| Non-college | 57/66 |
| College | 42/35 |

- Both terms are centered on the national value.

**Office × period intercepts:** House-26 (reference), Senate-26, Gov-26, and Special by half-year.

**Not controls (post-treatment):** spending, and the D/R spending ratio. They appear in robustness only.

---

## 3. Style-effect estimation

### 3.1 Main model (correlated random effects, Gibbs)

```
y*_i = μ_{o(i)} + α_{s(i)} + f(m24_i) + X_i'β_X + b_re·ES_re_i + b_age·ES_age_i
       + λ_L·L̄_s(i) + λ_P·P̄_s(i)                                  # Mundlak terms
       + β_L·(L_i − 1) + β_P·P_i
       + β_PW·P_i·W̃_i + β_LY·(L_i − 1)·Ỹ_i                          # §4, gated
       + 1[statewide_i]·(d_L·(L_i − 1) + d_P·P_i)                   # statewide deviation
       + u_{a(i)} + ε_i

y_obs,i = y*_i − g_s(i)·(1−p_i)/0.2 + e_count,i,   e_count ~ N(0, sd_count_i²)
ε_i     ~ t_5(0, σ_{o(i)})    (scale mixture: ε_i | ω_i ~ N(0, σ_o²/ω_i), ω_i ~ Gamma(2.5, 2.5))
α_s     ~ N(0, σ_α²)
u_a     ~ N(0, τ_u²),  u_mainstream_liberal ≡ 0
```

**How the terms work**

- **Wave-relative identification.**
  - `α_s` is the state wave. It is identified mainly by the state's House races.
  - The Mundlak terms (`L̄_s`, `P̄_s` = the state means of the style coordinates over included races) make `β_L` and `β_P` **within-state** estimators. This holds even though `α_s` is correlated with archetype (progressives cluster in CA, NY and MA).
  - A Senate or governor nominee is therefore compared with the House Democrats on the same ballot. Between-state variation in style is discarded in the main fit and reported only as robustness.
- **Statewide deviation.** `d_L`, `d_P` ~ N(0, 1²) replace the skeptic design's prior-driven λ multiplier. The posterior ratio `(β_L + d_L)/β_L` is reported as **evidence on salience**: whether style matters more in better-known races. It is shown beside the π slider and **not** fed into π automatically.
- **Two-factor structure plus shrunk deviations.** `u_a` captures non-additivity, for example left-populist ≠ left + populist. Five archetypes cost two slopes plus small deviations.
- **Partial counts.** The latent `y*` and the late-shift `g_s` implement §2.4.

### 3.2 Priors

**Default = "Agnostic", zero-centered.** The judges required this: the literature prior must never be passed off as a 2026 finding.

| Parameter | Agnostic (default) | Literature preset | Notes |
|---|---|---|---|
| `β_L` (per step) | N(0, 2²) | N(−1.5, 1.5²) | Literature: Hall close-primary RDDs, Split Ticket WAR |
| `β_P` | N(0, 2²) | N(0, 1.5²) | No credible literature sign |
| `β_PW`, `β_LY` (per 10 pts) | N(0, 0.5²) | N(0, 0.5²) | SD from the NYT nine-state gradient spread (§4.2). Sensitivity check at 1.0. |
| `d_L`, `d_P` | N(0, 1²) | N(0, 1²) | |
| `τ_u` | HalfNormal(1), sampled on a 1-D grid 0.02–4 | same | Sensitivity checks at fixed 0.5 and 2 |
| `rep_maga` effect `ω_maga` | N(0, 2²) | N(+1, 2²) | Positive means facing MAGA helps D |
| `rep_moderate` effect `ω_mod` | N(0, 2²) | N(−1, 2²) | |
| `b_re`, `b_age` | N(1, 1²) | same | 1 means the wave's shape transmits fully |
| `X` coefficients (centered) | N(0, 5²) | same | |
| `μ_o` | N(0, 10²) | same | |
| `σ_α²` | Scaled-Inv-χ²(3, 3²) | same | |
| `σ_o²` (by office) | Scaled-Inv-χ²(4, 6²) | same | |
| `g_s` | N(m_s, 2²) | same | Prior only; not updated |

### 3.3 Trust dial presets

Each preset is a **separate exact Python fit**, exported as joint draws:

| Preset | Prior | Data weight α |
|---|---|---|
| Agnostic (default) | as above | 1 |
| Literature | literature column | 1 |
| Discount 2026 | Agnostic prior | power prior α = 0.5. Treats 2026 data as worth half, because of label noise and confounding. |
| Data only | flat on `β_L`, `β_P`, `β_PW`, `β_LY` | 1 |

**Continuous dial.** The browser also has a continuous dial using a Gaussian power-prior update on the 4×4 style block:

```
Σ_post = (Σ0⁻¹/k² + α·V̂⁻¹)⁻¹
μ_post = Σ_post·(Σ0⁻¹μ0/k² + α·V̂⁻¹b̂)
```

- `b̂` and `V̂` come from the Data-only fit (the style block's posterior mean and covariance with the other parameters marginalized).
- **Validation:** at each preset, the Gaussian dial must reproduce the exact preset draws' means within 0.1 SD and SDs within 10%. If it fails, the continuous dial is disabled and only the four presets are offered.

**Prior-to-posterior SD ratio.** Shown on every style coefficient as `posterior SD / prior SD`. A ratio above 0.7 forces the badge "mostly prior: 2026 barely informs this".

### 3.4 Computation (numpy-only primary path)

The system `python3` (3.15.2) has **no numpy**. The pipeline runs in `analysis/.venv`, created with `uv venv --python 3.12` plus `numpy` and `scipy`, pinned in `analysis/requirements.txt`. PyMC is **optional** and used only as a cross-check if it installs.

**Primary sampler:** a hand-written blocked Gibbs sampler (`pipeline/gibbs.py`).

1. Draw `y*_i | rest`. Normal, combining the measurement and model precisions.
2. Draw the stacked coefficients `[μ, α, β_X, b, λ, β_L, β_P, β_PW, β_LY, d, u, f-spline] | rest`. Multivariate normal, with weights `ω_i/σ_o²`.
3. Draw `ω_i | rest`: `Gamma((5+1)/2, (5 + r_i²/σ_o²)/2)`.
4. Draw `σ_o² | rest` and `σ_α² | rest`. Scaled-Inv-χ².
5. Draw `τ_u | u`. Griddy Gibbs on a 200-point grid.
6. Draw `g_s` from its prior.

**Run settings and convergence**
- 4 chains × (1,000 warm-up + 2,500 draws).
- Pass requires R̂ < 1.01 and bulk ESS > 400 for `β_L`, `β_P`, `δ_a`, `ω`.
- Export **1,000 thinned joint draws** per preset.

**Derived quantities per draw:** `δ_a = β_L·(L̄_a−1) + β_P·P̄_a + u_a`, and the archetype ΔV inputs.

**Reference implementation.** `pipeline/reference_engine.py` re-implements the browser engine in float64 for the JS parity test (§7).

### 3.5 Raw vs adjusted (the story's first reveal)

Export the following for each archetype:
- `raw_a`, `n_a`, `n_states_a`.
- Distributions of `m24`, WNC share, 18–29 share, Hispanic share and urbanicity (the common-support plots).
- `δ_a` with interval.
- A Oaxaca-style decomposition at posterior means:

```
raw_a − raw_ml = Σ_k β̂_k·(X̄_a,k − X̄_ml,k)    [lean / demographic ES / incumbency+pv / opponent / state wave α̂]
               + δ̂_a + residual
```

**Quiz pairs.** Export 8–12 matched pairs for the guess-first quiz. Each pair is two nominees of different archetypes with \|Δm24\| ≤ 3, the same incumbency status and the same Rep style, chosen by a seeded random draw (not hand-picked). Export their `y`.

### 3.6 Confounding diagnostics (required; each drives a copy flag)

| # | Diagnostic | Rule → flag |
|---|---|---|
| D1 | **Overlap refit.** Multinomial propensity of archetype on (m24, ES_re, ES_age, WNC, urbanicity, incumbency, region). Trim to the common support [0.05, 0.95] for each archetype vs mainstream liberal, then refit. | If any `δ_a` moves by > 1.5 pts or > 1 posterior SD, the story leads with the overlap estimate (`lead_with_overlap`). |
| D2 | **OLS state-FE cross-check.** Same controls, archetype dummies, CR2 SEs clustered by state. Empirical-Bayes shrinkage `δ̃_a = δ̂_a·τ̂²/(τ̂² + se_a²)`. | A gap of > 1 posterior SD from the Gibbs `δ_a` → `publish_blocked` until reviewed. |
| D3 | **Freedman–Lane permutation.** Fit the reduced model without style terms. Permute its residuals within state, refit the full OLS-FE, record the Wald statistic for (`β_L`, `β_P`). 2,000 permutations. | p > 0.10 → `no_detectable_effect` (copy must say "no detectable style effect"). Estimates are still shown. |
| D4 | **Grouped CV.** 10 folds by state. Predictive log density with vs without style terms. | ΔELPD < 2·SE → `no_predictive_gain` (copy: "style adds no detectable predictive power"). |
| D5 | **2024 placebo.** On unchanged-line seats where the 2026 D nominee is **not** the 2024 D nominee, regress `house24 − pres24` on the 2026 nominee's archetype with the same non-2026 controls. | Placebo with the same sign and ≥ 50% of `|δ_a|`, or \|placebo\| ≥ 1.5 → `placebo_flag[a]`. Show `δ_a − placebo_a` as a forest row and mention it in the copy. |
| D6 | **Close-primary RD (sign check).** From `primaries.json`: races where a more-left (ΔL ≥ 1) and a less-left candidate finished top two within 10 pts. Regress the nominee's general `y` on "more-left won", local-linear in the primary margin. | Report sign and interval in the fragility panel. Never estimated into δ. If the sign is opposite to `β_L` and its 80% interval excludes 0, report "tension". |
| D7 | **Wave compression.** Add `(L_i−1)·α̂_s` and `P_i·α̂_s` interactions (robustness model). | Report the slopes. If the 80% interval of either excludes 0, the π slider tooltip says "style differences were smaller/larger where the wave was bigger". |

### 3.7 Robustness grid (the "how fragile is this" forest plot)

All runs share the same 1,000-draw export format and are summarized as `δ_a` (median, 80%).

- **R1, outcomes:** `margin − house24`, `margin − prev_seat` (unchanged lines only); Δlogit two-party share; raw margin with m24 controls.
- **R2, leave-out:** leave one state out (Maine highlighted); each statewide race's DFBETA; each archetype's 3 highest-leverage races; CA out; all redistricted states out.
- **R3, labels:**
  - Set B only.
  - High-confidence only.
  - Set C soft.
  - **Label-flip simulation:** flip 15% of labels uniformly 500 times and report the attenuation factor `A = E[β_flip]/β`.
  - **SIMEX** correction using the misclassification rate implied by the second-coder κ. Robustness row only.
- **R4, samples:** House only; statewide only; Nov 2026 only (no specials); extended (≤ 30); full (logit); provisional (p ≥ 0.5).
- **R5, priors:** the four presets; `k ∈ {0.5, 1, 2, 4}`; `τ_u` ∈ {0.5, 2}; `σ_γ` = 1.0.
- **R6, between-state:** random effects without Mundlak terms (uses between-state variation).
- **R7, with spending** (post-treatment, labelled as such).

**Prior-sensitivity rule.** If the sign of any headline `δ_a` differs between Agnostic and Data-only, or between Agnostic and Literature, then `direction_depends_on_prior[a] = true`. The copy must then say the direction depends on assumptions.

### 3.8 Minimum-N rules

| Estimate | Minimum | Below minimum |
|---|---|---|
| Archetype deviation `u_a` | ≥ 15 main-sample races from ≥ 6 states, ≥ 5 with \|m24\| ≤ 10 | `u_a ≡ 0`. Structural prediction only. Cell greyed "too few races". |
| Interaction `β_PW` / `β_LY` | ≥ 30 races with P > 0 (or L ≠ 1) spanning ≥ 20 pts of the covariate, from ≥ 8 states | Term set to 0 (not prior draws) in all 2028 translations. Tilt toggle disabled. |
| Statewide deviation `d` | ≥ 25 statewide contested races | `d ≡ 0` |
| Any archetype × office or × Rep-style cell | ≥ 10 | Pooled |
| Senate/governor-only archetype estimate | Never reported alone | |
| Named-candidate track record | ≥ 2 general elections | `c_c = 0` |
| Primary lane coalition slope | ≥ 10 primaries featuring the lane, from ≥ 5 states | Slope = prior mean |

**No estimate is ever gated on "interval excludes 0".** Estimates are shrunk and shown with intervals and evidence badges.

### 3.9 Fallback ladder (if the data are thinner than hoped)

The pipeline evaluates the levels in order. It records `fit_level` in `meta`, and the UI states it.

| Level | Trigger | Model |
|---|---|---|
| 0 | All inputs present | §3.1 as written |
| 1 | Some archetypes below minimum N | Those `u_a ≡ 0`. Greyed cells. |
| 2 | Interactions below minimum N | `γ ≡ 0`. Tilt disabled. |
| 3 | District demographics missing for some rows | Missing rows use state-level ES plus an `es_imputed` dummy. If > 25% of rows are missing, drop ES entirely and rely on the spline, the Mundlak/state effects and urbanicity (if present). Banner: "the wave's demographic shape is only partly controlled". |
| 4 | < 80 labeled contested main-sample races, **or** archetype κ < 0.4 | Single leftness factor with 3 levels (left / mainstream / moderate). P is dropped. Populist archetypes are shown as "not separately estimable". |
| 5 | `publish_blocked` unresolved, or placebo ≥ \|effect\| for every archetype | **"2026 is uninformative" mode.** Style draws come from the Agnostic prior only. Copy: "2026 doesn't tell us; here's what you'd have to believe". The Sim 4 heatmap becomes the centerpiece. |

---

## 4. Group-level (demographic) style interactions

### 4.1 What is and is not estimable

| Question | Source | Estimable? | Use |
|---|---|---|---|
| Does populist posture do better in whiter, non-college districts? (`β_PW`) | Race-level House + statewide, within-state, district composition | **Weakly.** Ecological, with common support limited (populists sit in rural or red seats). | Gated (§3.8). Shrunk N(0, 0.5²). Enters maps only when the reader turns on "tilt", with a **direct (2026 races)** badge. |
| Does leftness do better in younger districts? (`β_LY`) | Same | **Weakly.** Progressives sit almost only in young, diverse seats. | Same gating and badge |
| Which voter groups each archetype gained or lost | NYT nine Senate states | **No.** N = 9, one nominee per state; archetype is confounded with state, opponent and personal brand. | Direction checks and prior SD only |
| National group margins | NYT, `national.json` | Not style-specific (one national vote) | Wave-shape controls (ES) and turnout geography (G_s, §5.3) |
| Neighborhood patterns (Mamdani, NYC) | `offyear.json` | No (three-way, within-party) | Sign check on `β_LY` only |
| VA/NJ 2025 county types | `offyear.json`, `geography.json` | No | Sign check on the moderate archetype only |
| Populist mobilization of nonvoters | — | **Not identified** | No parameter. Listed as a non-claim. |

Only **two pre-registered interactions** are ever fit. No archetype × group tilt matrices (rejected group-poststrat Model H).

### 4.2 NYT nine-state Senate layer (descriptive)

**State-relative residual for state s, group g:**

```
r_sg = (shift_sg − shift_s) − (shift_g^nat − 15)
shift_s = 0.47·Male_s + 0.53·Female_s
```

**Education gradient residual:** `(HS − Postgrad)_s − 8`. The national gradient is 18 − 10 = 8.

These were checked against `nyt_voter_trends.json`. Gradient columns are in points of shift; the populist label is taken from the race data at fit time.

| State | Overall shift | WNC − WC | 18–29 − 65+ | Education gradient residual | r_65+ | r_WNC |
|---|---|---|---|---|---|---|
| AK | +18.4 | +3 | 31 | −1 | −6.4 | −0.4 |
| IA | +17.8 | +8 | 27 | +4 | +0.2 | +2.2 |
| KS | +20.4 | +2 | 27 | −3 | −1.4 | −0.4 |
| **ME** | **−3.7** | **−4** | 36 | **−10** | −3.3 | −3.3 |
| MI | +7.2 | +10 | 33 | +6 | −0.2 | +2.8 |
| MS | +20.8 | +2 | 33 | −2 | −0.8 | −1.8 |
| NC | +22.9 | 0 | 35 | −4 | −4.9 | +0.1 |
| OH | +16.7 | +10 | 28 | +4 | +1.3 | +4.3 |
| TX | +25.9 | 0 | 40 | +3 | −8.9 | −7.9 |
| SD across states | — | 4.9 | 4.4 | 5.1 | — | — |

**Uses**

1. **Prior SD for `γ`.** A between-state SD of about 5 points in the group gradient, which also contains non-style state factors, bounds style-driven tilt at about 0.1 × 5 = **0.5 points per 10 points of share**. That gives `σ_γ` = 0.5, with a sensitivity check at 1.0.
2. **Direction checks.**
   - Fit `grad_s = c + ψ_P·P_s + ζ·R_inc_pv_s + e_s`, ψ_P ~ N(0, 3²), N = 9.
   - Report ψ_P's posterior and its prior-to-posterior SD ratio.
   - If the sign of ψ_P opposes `β_PW` and both 80% intervals exclude 0, report "tension".
3. **Maine reading.**
   - Maine's group residuals (−3.3, −3.3) are **smaller** than Texas's (−8.9, −7.9) and comparable to North Carolina's 65+ value. Maine's distinctive feature is its **overall** level (−3.7 vs about +16 to +26 elsewhere).
   - The gap is statewide, not group-specific. That is consistent with an incumbent's broad personal vote (Collins), which enters through `R_inc_pv`. The formal test is validation V6.
4. **Story color**, labelled "in these nine races".

Never used: to estimate `δ_a`, to set a tilt that drives the map, or to support "populists win back non-college voters".

---

## 5. 2028 translation

### 5.1 State margin equation

For unit s (50 states, DC, ME-1, ME-2, NE-1, NE-2, NE-3; 538 EV) in draw j with parameter draw `p = p(j)`:

```
M_s,j = m24_s + ψ·rel26_s + φ·(rel24_s − rel20_s)
        + k_s·S_j
        + [tilt on]·π_p·(β_PW,p·P̄·W̃_s + β_LY,p·(L̄−1)·Ỹ_s)
        + H_D·1[s = home_D] − H_R·1[s = home_R]
        + ε_s,j

S_j = E_j + Δ_p − E24                   national swing from 2024
Δ_p = π_p·(δ_a,p + ω_opp,p) + ρ·(c_D,p − c_R,p)
k_s = 1 + u·(G_s − 1)
```

- `m24_s`: the 2024 two-party margin.
- `rel_t,s = m_t,s − m_t,US`.
- `rel26_s` = the state's 2026 statewide House swing minus the national swing, with uncontested seats imputed (§6.6, Sim 5).
- The default lean is `m24_s` with `φ = 0` and `ψ = 0.2`. Alternative weights (0.7·rel24 + 0.2·rel20 + 0.1·rel16) are robustness only. If `hist_pres_states.json` exists, the weights are re-fit by back-test, constrained to be ≥ 0 and to sum to 1.
- **District units:** `M = M_state + (lean_district − lean_state) + N(0, 1.5²)`.

### 5.2 National environment E (explicit, never inherited)

**Default: `E ~ t_5(loc = +3, scale = 5)`** (SD ≈ 6.5, deliberately wide).

**Justification.** Regress the next presidential two-party margin on the prior midterm House margin, 1994–2022 (n = 8, recomputed here):

| Quantity | Value |
|---|---|
| Slope | 0.17 ± 0.25 |
| Intercept | 3.1 |
| Residual SD | 4.1 |
| Prediction at D+13 | D+5.3, predictive SD 5.6 |

- The slope is indistinguishable from 0.
- D+13 lies outside the historical x-range (max D+8.6).
- So the center is the historical post-midterm mean (D+2.9 ≈ 3) rather than the extrapolated regression value.

**Presets (labelled buttons)**

| Preset | E |
|---|---|
| "2024 rerun" | −1.4 |
| "Neutral" | 0 |
| "History-based default" | t5(3, 5) |
| "Regression on 2026" | N(5.3, 5.6²) |
| "2026 wave holds" | +13, labelled "larger than any presidential margin since 1984" |

The race-regression "midterm decay D+8" preset is **dropped**. Its decay list omitted 1994→96 and treated decay as additive.

**Modes**
- **point:** E is exact. Used for the curves, `E*` and the heatmap.
- **distribution:** E is drawn from the preset per outcome draw. Used for headline `V_a`.

### 5.3 Turnout geography u

`G_s` is the state's exposure to the 2026 swing pattern under the **presidential** electorate:

```
G_s = 0.5·(G_s^re + G_s^age)
G_s^re = Σ_g c^pres_sg·shift_g      (race×edu cells, §2.6 shifts)
G_s^age analogous
```

- `c^pres_sg` = state CVAP shares (`states.json`) × `r^pres_g` (CPS 2024). The fallback `r^pres_g` is given in §2.1.
- For age, 30–44 and 45–64 are split from 30–64 using the national ratio.
- G_s is normalized so the 2024-turnout-weighted national mean of `G_s` is 1, which makes `Σ w_s k_s = 1`.

**Meaning of u**
- `u = 0` (default): uniform swing.
- `u = +1`: the 2024→2028 swing is distributed like 2026's demographic swing, and presidential-only voters share it. AZ, NV and TX move more.
- `u = −1`: the mirror case. The low-propensity groups that broke R in 2024 do not come along.

**Justification for the default.** Uniform swing is historically about as accurate as demographic swing. The 2024 and 2026 group patterns point in opposite directions. The back-test V3 decides whether `u ≠ 0` is even offered as more than a scenario.

### 5.4 Transfer factor π (visible, sampled by default)

- **Slider** 0.5–2 with a "sampled" mode, which is the default for headline intervals.
- **Sampled distribution:** `π ~ LogNormal(0, 0.35)` clipped to [0.5, 2]. The median is 1 and the 80% range is 0.64–1.57.
- **Fixed mode:** fixed at the slider value.

**Why median 1.** There is no evidence for net attenuation or net amplification:
- Attenuation forces: nationalized partisanship, and the nominee being defined by $1B+ of ads.
- Amplification forces: salience, and ideology becoming known to every voter.

**Evidence shown beside the slider**
- The statewide/House ratio from §3.1.
- The D7 wave-compression slopes.
- When available (Tier B, before final publication): the ratio of the ideology coefficient in presidential-year vs midterm-year House races, 2018/2020/2022/2024, using CFscore or endorsement coding. If that ratio's 80% interval excludes 1, re-center the π distribution on it and log the decision.

`π` multiplies style and opponent-type effects. It does **not** multiply `E`, home-state effects or track records, which have their own discounts.

### 5.5 Opponent, named candidates, home state

**Opponent**
- `ω_opp`: traditional = 0; MAGA-heir = `ω_maga` draws.
- **Generic Republican:** Bernoulli(0.5) MAGA per outcome draw, a mixture.

**Track record (both parties)**
- Raw residual per general election k: `r_c,k = margin_k − same-geography pres baseline_k − mean same-party/same-office overperformance that year`. This is wave-relative.
- Average: `ô_c = mean_k r_c,k − δ_a(c)` (Democrats), so the archetype is not double-counted.
- Shrinkage: `c_c = w_c·ô_c`, with `w_c = τ_c²/(τ_c² + σ_r²/n_c)`.
  - `σ_r`: the office residual SD from §3.1.
  - **`τ_c` is estimated** from the covariance of incumbents' 2024 and 2026 House residuals (same incumbent, unchanged lines, pres-relative, wave-adjusted): `τ̂_c² = Cov(r_24, r_26)`.
  - If fewer than 40 qualifying incumbents, or a non-positive estimate: `τ_c = 2`, with sensitivity checks at {1, 3}.
- **Nationalization discount:** `ρ = 0.5`, with slider 0–1.
- **Uncertainty:** each candidate gets `c_draws` (1,000): N(`w_c·ô_c`, `w_c·σ_r²/n_c`), propagated.
- **Example:** three statewide races with τ_c = 2 and σ_r = 5 give w = 0.32, so a +10 overperformer earns about +1.6 nationally after ρ.

**Home state**
- `H ~ N(+2, 1.5²)` margin points in the nominee's home state, for both parties, drawn per outcome draw.
- A VP home effect of +0.5 applies only if a VP is specified (off by default).

**Polls and markets** are not inputs to Sims 1, 2, 4 or 5. They are shown beside Sim 2 and Sim 3 for comparison only. Sim 3 uses national primary polls as a noisy starting strength.

### 5.6 Correlated state errors

```
ε_s,j = Σ_k F_sk·f_k,j + σ_idio,s·v_s,j,   f ~ N(0,1),  v ~ t_5 (scaled to unit variance)
```

- **Factors (12):** 6 regions (Northeast, Rust Belt, South, Plains/Mountain, Southwest, Pacific) and 6 demographics (WNC, Black, Hispanic, college, white evangelical, 65+).
- **Loadings:** demographic loading = the state's z-scored share × `scale_k`; region loading = indicator × `scale_k`.
- **Calibration** (`pipeline/05_errors.py`): maximum likelihood on state-relative presidential swings `rel_t − rel_{t−4}`, 2000–2024.
  - Target median state-relative SD about 3–3.5.
  - Correlations between similar states about 0.6–0.8.
  - If only 2016/2020/2024 are available: `scale_k ~ HalfNormal(1.5)` priors, total SD fixed at 3.5, labelled "uncalibrated".
- **σ_idio** 1.5–3.5, larger for small states.
- Python exports `F` (56×12) and `σ_idio`. JS never factorizes a matrix.
- **No separate national error term.** National uncertainty lives entirely in E (distribution mode). In point mode E is exact, so P(win | E) is a clean curve.

---

## 6. Simulation engine spec (browser)

### 6.1 Architecture

- Vanilla ES module `site/src/lib/engine/engine.js`, run inside a Web Worker (`worker.js`). No dependencies.
- **PRNG:** seeded xoshiro128\*\*, Box–Muller normals.
- **t5 draws:** `z·sqrt(3/5)/sqrt(χ²_5/5)`, with `χ²_5 = 2·Gamma(2.5)` via Marsaglia–Tsang.
- **Typed arrays:** `Float32Array` in production and `Float64Array` in `precision:'f64'` test mode.
- Params file: `analysis/output/model_params.json`, copied at build time to `site/static/data/model_params.json`.

### 6.2 Core performance trick: the break-even swing bank

With tilt off and no home effects, every style, opponent, track-record, π and E term enters only through the scalar national swing `S`.

**Per outcome draw j (cached in an `OutcomeBank`):**
- `a_s,j = m24_s + ψ·rel26_s + φ·(rel24_s − rel20_s) + ε_s,j`.
- Unit s goes D when `S > θ_s,j = −a_s,j / k_s`.
- Note `k_s > 0` because `G_s` ∈ (0.5, 1.5) and \|u\| ≤ 1. Assert this.
- Sort the 56 thresholds and accumulate EV in ascending order. The threshold at which the cumulative EV reaches 270 is `t_j`, the swing D needs. The unit at that threshold is the tipping unit `tip_j`.
- If a 269 exactly occurs at the crossing, record `tieWidth_j` = the interval of S in which EV = 269.

**Then, for any uniform Δ:**
- Point E: `P(win | E, p) = F_t(E − E24 + Δ_p)`, where `F_t` is the empirical CDF of the sorted `t` array, by binary search.
- Distribution E: precompute `D_j = E_j − E24 − t_j` (sorted). Then `P(win | p) = 1 − F_D(−Δ_p)`.
- **Parameter vs outcome uncertainty separate exactly:** `V_a = mean_p P(win | p)`. Interval = quantiles over the 1,000 parameter draws `p`. `ΔV_a,p` uses the same p for both archetypes (common random numbers).
- **E\*:** `E*_a,p = E24 + median(t) − Δ_a,p`. Report the median and 80% interval over p, rounded to integers.
- **Tipping-point frequency** is a property of the bank. With uniform effects it does not depend on the archetype, and the copy may say so.
- **State P(D)** for archetype a: `mean_j 1[S_j > θ_s,j]`, at 10k × 56 compares.

**Non-uniform terms**
- **Home effects:** for draw j, shift the affected unit's threshold by `−H/k_s` and re-accumulate. This is O(56) per draw and only for affected cells.
- **Tilt on:** thresholds depend on p. Fall back to paired brute force, with `p(j) = j mod 1000`, one sort per draw.

### 6.3 Budgets (mid-tier Android, Chrome 4× CPU throttle on desktop as a proxy)

| Operation | Size | Budget |
|---|---|---|
| Build bank | 10,000 draws × (12 + 56 t5) normals + 56×12 MACs + one 56-sort | ≤ 250 ms (once per `{seed, u, ψ, φ}`) |
| Sim 1 | 5 archetypes × 1,000 p × binary search; map 5 × 560k compares | ≤ 50 ms |
| Win-vs-E curves | 5 × 31 E values × 1,000 p, binary search | ≤ 20 ms |
| Sim 2 | 40 cells; home-effect re-accumulation 40 × 10,000 × 56 | ≤ 800 ms, rendered progressively |
| Sim 4 heatmap | 37 E × 25 style cells, binary search per cell | ≤ 10 ms |
| Sim 3 | 10,000 primaries × ~25 dates × ≤ 10 candidates | ≤ 700 ms |

### 6.4 `model_params.json` schema

```jsonc
{
  "meta": {
    "version": "2026-11-04-prelim-1", "generated_at": "ISO", "data_as_of": "ISO",
    "preliminary": true, "fit_level": 0, "seed": 20261104,
    "pipeline_commit": "sha", "n_param_draws": 1000, "notes": []
  },
  "national": { "E24": -1.43, "ev_total": 538, "ev_win": 270 },

  "units": [{
    "id": "PA", "name": "Pennsylvania", "type": "state",        // "state" | "district" | "dc"
    "parent": null, "ev": 19,
    "m24": -1.72, "m20": 1.17, "m16": -0.75,                     // two-party
    "rel24": -0.29, "rel20": -3.3, "rel26": 0.8,
    "G": 0.97,                                                   // §5.3, normalized
    "W_tilde": 1.2, "Y_tilde": -0.3,                             // centered per-10-pt shares for tilt
    "F": [/* 12 loadings */], "sigma_idio": 2.2,
    "shares": { "wnc": 0, "wc": 0, "black": 0, "hisp": 0, "asian": 0,
                "y1829": 0, "a65": 0, "evang": 0, "urban": 0 }
  }],

  "errors": {
    "factor_names": ["NE","RUST","SOUTH","PLAINS_MTN","SW","PACIFIC","WNC","BLACK","HISP","COLLEGE","EVANG","A65"],
    "idio_df": 5, "calibrated": true, "target_rel_sd": 3.5,
    "backtest": { "cov80_2016": 0.0, "cov80_2020": 0.0, "cov80_2024": 0.0 }
  },

  "environment": {
    "default_preset": "history",
    "presets": {
      "rerun2024": { "type": "point", "value": -1.4 },
      "neutral":   { "type": "point", "value": 0 },
      "history":   { "type": "t", "df": 5, "loc": 3, "scale": 5 },
      "regress26": { "type": "normal", "mean": 5.3, "sd": 5.6 },
      "wave_holds":{ "type": "point", "value": 13, "warning": "..." }
    },
    "slider": { "min": -10, "max": 15, "step": 0.5 }
  },

  "transfer_pi": {
    "default_mode": "sampled",
    "sampled": { "type": "lognormal", "mu": 0, "sigma": 0.35, "clip": [0.5, 2] },
    "slider": { "min": 0.5, "max": 2, "step": 0.05 },
    "evidence": {
      "statewide_house_ratio": [0, 0, 0],                       // [median, lo80, hi80]
      "wave_compression": { "L": [0,0,0], "P": [0,0,0] },
      "historical_pres_mid_ratio": null
    },
    "pi_draws": [/* 1000, sampled-mode draws aligned with param draws */]
  },
  "turnout_u": { "default": 0, "min": -1, "max": 1, "offered_as": "scenario" },  // or "validated"
  "lean": { "psi": 0.2, "psi_calibrated": false, "phi": 0, "phi_max": 0.5 },

  "style": {
    "coords": { "progressive": { "L": 2.0, "P": 0.25, "n": 0, "n_states": 0, "min_n_ok": true } /* ×5 */ },
    "hull": [[0, 0] /* convex hull of nominee (L, P) with ≥5 races nearby */],
    "presets": {
      "agnostic": {
        "beta_L": [], "beta_P": [], "beta_PW": [], "beta_LY": [],
        "u": { "progressive": [] /* ... */ },
        "delta": { "progressive": [] /* derived, 1000 each */ },
        "omega_maga": [], "omega_mod": [],
        "sd_ratio": { "beta_L": 0.0, "beta_P": 0.0 }
      },
      "literature": { /* same */ }, "discount": { /* same */ }, "data_only": { /* same */ }
    },
    "gaussian": {
      "names": ["beta_L", "beta_P", "beta_PW", "beta_LY"],
      "bhat": [], "Vhat": [[]],
      "mu0": { "agnostic": [], "literature": [] }, "Sigma0": { "agnostic": [[]], "literature": [[]] },
      "dial_enabled": true
    },
    "interactions": {
      "beta_PW": { "gate_passed": false, "badge": "prior" },
      "beta_LY": { "gate_passed": false, "badge": "prior" }
    },
    "tilt_default_on": false
  },

  "reveal": {
    "raw": { "progressive": { "mean": 0, "n": 0, "dist_m24": [], "dist_wnc": [], "dist_y1829": [], "dist_urban": [] } },
    "adjusted": { "progressive": { "med": 0, "lo": 0, "hi": 0 } },
    "decomposition": { "progressive": { "lean": 0, "demographic": 0, "incumbency": 0, "opponent": 0, "state_wave": 0, "style": 0, "residual": 0 } },
    "quiz_pairs": [{ "a": { "name": "", "district": "", "archetype": "", "y": 0 }, "b": {} }],
    "fragility": [{ "label": "Leave out Maine", "archetype": "left_populist", "med": 0, "lo": 0, "hi": 0 }],
    "maine": { "pred_with_delta": [0,0,0], "pred_delta0": [0,0,0], "actual": 0, "share_incumbency": [0,0,0] },
    "nyt9": { /* §4.2 table */ }
  },

  "copy_flags": {
    "no_detectable_effect": false, "no_predictive_gain": false, "lead_with_overlap": false,
    "publish_blocked": false, "placebo_flag": {}, "direction_depends_on_prior": {},
    "provisional_archetypes": [], "maine_explained_by_incumbent": null,
    "label_reliability": "ok"                                    // "ok" | "low_posture" | "low"
  },

  "candidates_dem": [{
    "id": "", "name": "", "archetype": "", "L": 0, "P": 0, "home": "XX",
    "track": { "o_hat": 0, "n": 0, "w": 0, "c_draws": [] },
    "poll_nat_primary": 0, "market_nom": 0, "include_default": true
  }],
  "candidates_gop": [{
    "id": "", "name": "", "opp_type": "maga",                    // "maga" | "traditional"
    "home": "XX", "track": {}, "market_nom": 0
  }],
  "home_effect": { "mean": 2.0, "sd": 1.5, "vp": 0.5 },
  "rho": { "default": 0.5, "min": 0, "max": 1 },

  "primary": {
    "lanes": ["left", "mainstream", "moderate"], "populist_term": true,
    "covariates": ["black", "white_college", "y1829", "urban"],
    "zeta": { "left": [], "moderate": [] }, "eta": { "left": [[]], "moderate": [[]] },
    "b_populist": [],
    "states": [{ "id": "SC", "delegates": 0, "X": [0,0,0,0], "date_dnc2024": "2028-02-03" }],
    "calendars": { "dnc2024": [["SC"], ["NH"], ["NV"], ["MI"], ["ST: ..."]], "traditional": [] },
    "settings": {
      "poll_weight": 0.3, "kappa_sd": 0.7, "noise_sd": 0.3, "home_logit": 0.8,
      "momentum": 0.5, "threshold": 0.15, "dropout_after": ["4th", "super_tuesday"],
      "dropout_share": 0.10, "lane_affinity_same": 0.6, "majority": 0
    },
    "validation": { "brier_model": 0, "brier_baseline": 0, "coalition_enabled": true }
  },

  "sim5": {
    "units": [{ "id": "PA", "house26": 0, "house26_sd": 0, "pct_counted": 0,
                "imputed_share": 0, "electorate_adj": 0, "hatched": false }],
    "national_house26": 0, "durable_phi_default": 1,
    "senate": [{ "id": "", "margin": 0 }], "governor": []
  },

  "banners": { "not_forecast": "...", "preliminary": "...", "primary_weak_proxy": "..." }
}
```

### 6.5 JS API

All functions are pure given `(model, bank, opts)`. All are deterministic for a fixed seed.

```ts
loadModel(json): Model                                  // validates schema, asserts k_s > 0, EV sum 538

buildBank(model, { n = 10000, seed, u = 0, psi, phi }): OutcomeBank
  // { a: Float32Array(n*56), theta: Float32Array(n*56), t: Float32Array(n) sorted copy + raw,
  //   tip: Uint8Array(n), tieWidth: Float32Array(n), Edraws?: per preset }
  // cached on key {seed, u, psi, phi, nUnits}

styleDelta(model, { preset | dial: { k, alpha, prior: 'agnostic' | 'literature' },
                    archetype? | coords?: { L, P },
                    opponent: 'generic' | 'maga' | 'traditional',
                    pi: { mode: 'sampled' | 'fixed', value? } }): Float32Array(1000)
  // π_p·(δ_a,p + ω_p). For generic, returns per-p mean over Bernoulli(0.5), with mixture
  // handled in the bank pass. Coords off the 5 centroids: inverse-distance-weighted u.

simArchetypes(model, bank, { env: { mode: 'point' | 'dist', value? | preset? }, opponent, pi,
                             preset | dial, tilt = false }):
  { byArchetype: { [a]: {
      V: number, V80: [lo, hi],
      dV: [med, lo, hi], pDVbelowMinus10: number,
      Estar: [med, lo, hi],                                 // integers
      evHist: Int32Array(539), pTie: number,
      stateP: Record<id, number>, stateMeanMargin: Record<id, number>,
      decomposition: { env, lean, style, opponent } } },
    tipping: Record<id, number>,                            // bank property (tilt off)
    curves: { E: number[31] /* -10..20 */, byArchetype: { [a]: { med: number[], lo: number[], hi: number[] } } },
    ms: number }

simMatchups(model, bank, { dems: id[], gops: id[], env, pi, preset, rho, home = true, track = true }):
  { cells: [{ dem, gop, pWin, pWinBinned /* 5-pt */, pWin80: [lo, hi], medMargin,
              decomposition: { env, tippingLean, style, opponent, personal, home } }],
    indistinguishable: { thresholdPts: number, pairs: [[i, j]] },  // param-draw SD of cell diffs
    rowAvgByMarket: Record<demId, number>, ms }

matchupDetail(model, bank, dem, gop, opts): /* Sim 1 output shape for one pairing incl. tipping */

simPrimary(model, { field: id[], calendar: 'dnc2024' | 'traditional' | Custom,
                    momentum, threshold, dropout, laneAffinity, n = 10000, seed }):
  { pNominee: Record<id, number>, pLane: Record<lane, number>, pNoMajority: number,
    delegatePath: { [id]: { med: number[], lo: number[], hi: number[] } },
    chained?: { pDemWins: number, p80: [lo, hi], warning: string } }   // only when requested

simCustom(model, bank, { L, P, home?, track?: { o, n }, opponent, env, pi, preset | dial, u }):
  { V, V80, dV, Estar, waterfall: [{ label, value }], stateP,
    extrapolated: boolean, hullDistance: number }
  // Outside the hull, or > 0.5 from every centroid: draws are widened ×2 around their mean,
  // and the UI hatches "outside the 2026 data, a guess".

believeHeatmap(model, bank, { Egrid = [-6..12 step 0.5], styleGrid = [-8..4 step 0.5], archetype, pi }):
  { pWin: Float32Array(Egrid × styleGrid), contours: { p50: [[x, y]], p90: [[x, y]] },
    reader: { x, y }, B: { threshold: number, posteriorProb: number } }
  // Contours: 2-D histogram (40×40, Gaussian-smoothed) of (E prior draw, π_p·δ_a,p).

sim5(model, { view: 'raw' | 'electorate' | 'durable', u = 0, phi = 1, source: 'house' | 'senate' | 'governor',
              n = 2000, seed }):
  { units: [{ id, margin, sd, pD, hatched }], ev: [med, lo, hi], flipsVs2024: id[], ms }
```

### 6.6 Sim-specific rules

**Sim 1 (archetypes)**
- Default: env = history (distribution), π sampled, opponent generic, preset Agnostic, u = 0, tilt off.
- Show all five curves, `E*` integers with intervals, the ΔV forest, and the prior-vs-posterior strip of `π·δ_a`.
- Opponent toggle: Vance-type MAGA heir / Rubio-type traditional.

**Sim 2 (matchup matrix)**
- P(win) binned to 5-point steps.
- **Indistinguishability banner:** for horizontally and vertically adjacent cells, compute the parameter-draw distribution of the difference. If its 80% interval includes 0, the pair is indistinguishable. Banner text: "cells within X points are statistically indistinguishable", where X = the median over pairs of 1.28·SD.
- Tipping-point detail is computed only for the clicked cell.

**Sim 3 (primary)**
- **Python fit:** a conditional-logit share model on `primaries.json` races:
  - `P(j) ∝ exp(ζ_lane(j) + η_lane(j)'Z_i + b_pop·P_j + q_j)`.
  - Mainstream is the reference lane.
  - ≤ 4 covariates.
  - `Z_i` = district primary-electorate composition, approximated by district CVAP × national Dem-primary participation rates by group.
  - Priors on `η` from the 2016/2020 primary exit polls with SD 0.5; otherwise N(0, 0.5²).
  - `q_j` ~ N(0, 0.6²), with incumbency and money-lead dummies.
- **Browser:** start strength `κ_c = 0.3·log(poll_c/mean) + N(0, 0.7²)`.
  - The calendar is editable. The default "DNC 2024 order" is labelled an assumption.
  - State share = softmax(`ζ + η'Z_s + b_pop·P_c + κ_c + 0.8·home + 0.5·momentum + N(0, 0.3²)`).
  - Delegates are proportional among candidates at ≥ 15%.
  - Dropouts happen after the 4th contest and after Super Tuesday (< 10% of delegates and no wins), with 60% of their support going to the same lane.
  - Majority = more than half of pledged delegates, else "no pledged majority".
- **Chained `P(D wins presidency)`** is off by default. It appears only behind a "combine with the general" button, with a compounding-uncertainty warning and its interval. It is never headlined.
- Prediction markets are shown beside it, never as input.
- Warning: "40 House primaries are a weak proxy for a national primary."

**Sim 4 (build your own)**
- **Sliders:**
  - L 0–2 (continuous)
  - P 0–1
  - home state
  - track record o ∈ [−5, +10] with n ∈ {1..5}, shrunk live with `w(n)` and ρ
  - opponent
  - E, u, π
  - trust dial
- **Outputs:**
  - A waterfall: E → style → opponent → track record → home.
  - The `δ(L, P)` contour with the 2026 nominees scattered on it.
  - The "what you'd have to believe" heatmap with the reader's point, the 50% and 90% posterior contours, and `B_a`.

**Sim 5 (2026 as a presidential year)**
- **Raw view:**
  - Statewide House two-party margin from the district votes.
  - Uncontested and D-v-D seats imputed as `m24_district + state mean contested swing`, with votes = 2024 presidential votes × the state's 2026/2024 turnout ratio.
  - SD from imputation plus partial counts.
  - Units below 90% counted are hatched.
- **Electorate view:** `house26_s + u_e·[Σ_g (c^pres_sg − c^mid_sg)·m^26_g − national analogue]`, with `u_e` ∈ [−1, 1] (default 1 in this view, slider visible) and `m^26_g` the NYT group margins.
- **Durable view (default):** `house26_s − φ·(house26_US − E_default_center)`, with φ ∈ [0, 1] and default 1. That is 2026 geography at a D+3 environment.
- Every view carries the "a translation, not a forecast" banner and lists the states that flip between views.

---

## 7. Validation and back-tests (`pipeline/10_validate.py` → `analysis/output/validation.json`)

Each item has a status of PASS, FAIL or REPORT. A FAIL on a **blocking** item stops `09_export.py` from writing `model_params.json` unless `--override <item>` is logged in `methodology_decisions.md`.

| ID | Test | Pass criterion | Blocking |
|---|---|---|---|
| V1 | **Identity.** δ = 0, E = E24, u = 0, ψ = φ = 0, ε = 0, no home | Every unit margin = 2024 two-party margin (±1e-9); EV_D = 226 | Yes |
| V2 | **JS ↔ Python parity.** Same seed, `precision:'f64'` | All Sim 1/2/4/5 outputs within 1e-9; f32 mode P(win) within 0.002 | Yes |
| V3 | **Error calibration back-test.** Fit loadings and scales through t−1; predict state-relative margins for 2016, 2020 and 2024 given the realized national margin | Pooled 80% coverage 75–85%. Correlated 2016 WI/MI/PA miss inside the simulated spread (≥ 5% of draws miss all three by ≥ the realized amount). Log score beats independent-error uniform swing with the same marginal SD. | Yes |
| V4 | **2024 EC back-test.** B from 2016/2020, E = −1.4 point, δ = 0 | Trump 312 inside the 80% EV interval; Brier ≤ uniform swing | Yes |
| V5 | **u back-test.** G-weighted swing 2020→24 using 2020 composition and national 2020→24 group shifts | If RMSE is not below uniform swing, `turnout_u.offered_as = "scenario"` and the tooltip says it lost the back-test | No (sets flag) |
| V6 | **Maine.** Refit without ME. Predict Platner `y` (a) with `δ_left_populist` + `R_inc_pv` + α_ME from House, (b) with δ = 0 | If the 80% interval of (b) covers the actual: `maine_explained_by_incumbent = true`. If (a) misses: copy "mostly unexplained by archetype". Report the posterior split incumbency/style. | No (sets flag) |
| V7 | **Posterior predictive.** All main-sample races | 80% coverage 75–85%. Residual slope vs p, m24, ES_re, ES_age: 80% interval includes 0 or \|slope\| < 0.1 | Yes (coverage); report (slopes) |
| V8 | **Leave-statewide-out.** Predict each Senate/governor race from its state's House races (α̂_s) + δ | Coverage 70–90%; MAE with style terms ≤ MAE without + 0.2 | No (report; feeds copy if style worsens) |
| V9 | **Spanberger same-ballot.** VA gov margin − mean(VA LG, AG) margins vs predicted (`δ_moderate − δ_LG/AG archetypes`) ± τ_c | Inside the 80% interval → "consistent"; else report | No |
| V10 | **Mamdani sign.** Neighborhood shifts (young renters up, etc.) vs sign of `β_LY` | Report agreement or "tension" | No |
| V11 | **Placebo.** D5 | Any `placebo_flag` → shown in copy | No (sets flag) |
| V12 | **OLS-FE+EB vs Gibbs.** D2 | All `δ_a` within 1 posterior SD | Yes (`publish_blocked`) |
| V13 | **Labels.** κ(agent, second coder), κ(agent, rules) | ≥ 0.6: ok. 0.4–0.6 on posture: `low_posture` (P estimates badged). < 0.4 on archetype: Level 4. | Sets fit level |
| V14 | **Label-flip attenuation** | Report A. If A < 0.6, the copy notes effects may be understated. | No |
| V15 | **Trust-dial Gaussian validity** | §3.3 tolerance | Disables dial |
| V16 | **Sim 5 consistency** | National aggregated House margin within 1.5 of the topline (NYT D+13, with as-of caveat); ≥ 90% of states in the NYT leader-share bucket | Yes |
| V17 | **Sim 3.** In-sample Brier on 2026 primaries vs baseline (endorsement/money leader wins; else equal shares). Tier B: 2020 back-test from January 2020 polls gives P(Biden) ≥ 15%. | Fails → `coalition_enabled = false` (η at prior means), copy "polls plus priors" | No (sets flag) |
| V18 | **Engine invariants** | P(win) monotone in E; δ = 0 makes archetypes identical; same seed is reproducible; budgets in §6.3 met on a throttled run | Yes |
| V19 | **Convergence** | R̂ < 1.01, ESS > 400 for style parameters, every preset | Yes |
| V20 | **Partial-count selection** | §2.4 report produced | Sets `provisional_archetypes` |

---

## 8. Claims ledger

The copy may only use the templates below. Bracketed values come from `model_params.json`. Each claim's conditions are evaluated from `copy_flags` and `validation.json` at build time (`site/src/lib/copy.js`).

| # | Allowed claim (template) | Condition | Mandatory caveat |
|---|---|---|---|
| C1 | "[Archetype] Democrats beat Harris's 2024 margin in their districts by [raw_a] points on average." | Always (descriptive) | "But they ran in very different places" (followed by the common-support reveal) |
| C2 | "In comparable races, on the same ballot, [archetype] nominees ran [δ̂] points [ahead of/behind] mainstream liberals (range [lo] to [hi])." | `publish_blocked = false`; min N met; not `no_detectable_effect` | "Comparable races, not cause and effect: style is bundled with candidate quality and who chose to run. Preliminary as of [date]." If `lead_with_overlap`, use the overlap estimate and say "among districts where both kinds of Democrats ran". |
| C3 | "We found no detectable difference between styles once we compared like with like; the range runs from [lo] to [hi]." | `no_detectable_effect` or `no_predictive_gain` (**required** wording then) | "No detectable difference is not proof of no difference." |
| C4 | "The direction of this result depends on what you assume going in." | `direction_depends_on_prior[a]` (**required**) | Show the trust dial |
| C5 | "A [archetype] Democrat needs roughly a D+[E*] national environment to be a coin flip (range D+[lo] to D+[hi]); a mainstream liberal needs D+[E*_ml]." | Always, integers only | "Assumes a style effect in 2028 the same size as in 2026 House races (adjustable)." |
| C6 | "In a [preset] environment, picking [archetype] over a mainstream liberal changes the Democrats' Electoral College odds by about [ΔV] points (range [lo] to [hi])." | Always; preset named | "Under these assumptions; not a forecast." |
| C7 | "How good a year 2028 is matters more than which kind of Democrat runs." | Width of the 80% interval of E (default) > 2 × max_a 80% upper bound of \|π·δ_a\| | Point readers to the sliders |
| C8 | "For a [archetype] to be a clear liability (−10 points of win probability), you'd have to believe its style costs at least [B_a] points nationally; 2026 puts the chance of that at [prob]." | Always | — |
| C9 | "Maine's swing toward Republicans looks like Susan Collins's personal vote, not a populism penalty." | `maine_explained_by_incumbent = true` | "One race; the model can't separate the candidate from the opponent." Else (a misses): "Maine is mostly unexplained by candidate style." **Never** "populism failed in Maine". |
| C10 | "In the nine Senate races the Times broke down by group, [pattern]." | Descriptive, from §4.2 | "Nine races, one Democrat each: we can't tell style from state." |
| C11 | "In [district-type] districts, [archetype] did relatively [better/worse]." | Interaction gate passed **and** the tilt is direct-badged | "Based on [n] races; district averages, not individual voters." |
| C12 | "Under these assumptions, [Dem] vs [GOP] is [binned P] for Democrats." | Matrix context only | The indistinguishability banner; "not a forecast of any person's chances" |
| C13 | "In 10,000 simulated primaries, [lane] candidates win [p]% of the time." | V17 status shown | "A weak proxy: based on [n] House primaries and early polls." The chained general-election number appears only with the compounding warning. |
| C14 | "If the 2026 House vote were a presidential map, Democrats would win [EV]; at a more typical environment, [EV_durable]." | Always | "A translation, not a forecast; the midterm electorate is older and whiter." |
| C15 | "Spanberger ran [x] points ahead of her own ticket-mates on the same ballot." | V9 computed | "One race; consistent/inconsistent with our moderate estimate." |
| C16 | "Small samples: these estimates could move as [states] finish counting." | `provisional_archetypes` non-empty | — |

**Forbidden in any copy, chart title or alt text**
- "can't win" or "will win"
- "proves", "shows that style causes"
- "progressives/populists/moderates are more electable" without C2/C6 conditions and an interval
- "populists win back working-class voters"
- "mobilizes nonvoters"
- Any lesson drawn from one race
- Any style number with a decimal in the headline (integers in headlines; one decimal allowed in the methods drawer)
- Any `V_a` without its E and interval
- Pre-committed findings ("real but small")

---

## 9. Plain-language methodology note (for readers)

> **How we did this.** Democrats gained almost everywhere in 2026, so the real question isn't who did well but who did better than the wave. For every House, Senate and governor race, we compared the Democrat's margin with how the same place voted for president in 2024. Then we compared candidates of different styles (progressive, populist, mainstream liberal, moderate) who were on the same state ballot, in places with similar partisanship and demographics, facing similar Republicans. That matters because progressives mostly ran in young, diverse, deep-blue districts and moderates in swing suburbs. Raw averages mix up the candidate with the place.
>
> Small numbers of races give jumpy answers, so we pull every estimate toward "no difference" unless the evidence is strong, and we show the range, not just the middle. Some Western states are still counting, so every number is preliminary.
>
> To look ahead to 2028, we simulated the Electoral College 10,000 times, letting similar states move together as they have historically. Three things nobody knows are left to you: how good a year 2028 is for Democrats (we do not assume 2026's landslide carries over), how much of a midterm candidate's edge survives a presidential campaign, and whether presidential-year voters behave like 2026's. Move them and watch which one changes the answer most. These are scenarios under stated assumptions, not forecasts. They can't tell you whether any particular person would win.
