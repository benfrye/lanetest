# Lane gaps in earlier House cycles vs the national environment

Built 2026-11-04. This folder is self-contained. It reads `analysis/output/races.json` (2026, read-only) and
writes only to `analysis/history/` and `research/history/`.

**Question.** In 2026 (House vote about D+13), the lane gaps relative to mainstream liberals were smaller where the
state wave was bigger (D7: leftness × wave −0.5). Here the same gaps are measured in 2018 (D+8.6) and 2022 (R+2.7),
plus 2020 (D+3.1) and 2024 (R+2.6) as a stretch. A line through the cycles gives the gap at an even environment.

## Files
| File | What it is |
|---|---|
| `research/history/house_<year>.json` | One record per district: result, prior/same-day presidential baseline on the lines in use, incumbency, personal vote, exclusion reason, Democratic nominee label with evidence, source URLs |
| `research/history/labels_<year>.json` | Merged labels (coder / rule / default), with tier, confidence, evidence, source URL and a marker-only rule label |
| `research/history/label_work/` | Rubric (`RUBRIC.md`), coder batches and raw coder outputs, tier assignments |
| `research/history/raw/` | Fetched sources: Wikipedia raw wikitext, sheet CSVs, pre-election Wikipedia revisions of caucus pages and state pages, Wayback snapshots of group endorsement pages |
| `parse_wiki.py`, `build_races.py` | Results and baselines → `house_<year>.json` |
| `caucus_markers.py`, `group_markers.py`, `endorsement_markers.py` | Pre-election marker matching |
| `prepare_batches.py`, `merge_labels.py`, `carry_labels.py` | Label tiers, coder batches, merge |
| `history_analysis.py` → `history_comparison.json` | Models and results. The `headline` key holds the main summary. |

Rebuild: `python -I build_races.py 2018 2020 2022 2024 && python -I history_analysis.py` (project venv).

## Data
- **Results.** These come from the per-state tables of the Wikipedia "<year> United States House of Representatives
  elections" pages, fetched as raw wikitext. Percentages are rounded to 0.1. For RCV races (ME-2 2018) the final round is used.
- **Baselines (2p margin on the lines in use).**
  - 2018: 2016 presidential result from the Daily Kos Elections sheet for 2016 lines (`1VfkHtz…`). PA uses the 2018
    court map, taken from the 2016 columns of the 2020-lines sheet (`1XbUXn…`). PA's lines did not change between
    2018 and 2020. Cross-check: the two sheets agree for all 404 non-PA/NC districts.
  - 2022: 2020 presidential result on 2022 lines (Downballot `1CKngqOp…`).
  - 2020: same-day 2020 presidential result (`1XbUXn…`).
  - 2024: same-day 2024 presidential result (Downballot `1ng1i…`, **integer-rounded** in the export, which adds about ±0.7 pts of noise).
- **Exclusions** (same rules as 2026): uncontested or no major-party opponent; same-party top-two; a second Democrat
  at 10% or more; any third candidate at 10% or more (first round for RCV, which excludes AK-AL 2022 because Begich had 23%).
  - Included races: 2018 392, 2020 404, 2022 396, 2024 395. 2026 (House, `included_in_fit`): 328.
- **Controls.**
  - State fixed effects, plus a restricted cubic spline in the baseline (knots −60/−10/0/10/60, O-6).
  - inc_D and inc_R. inc_R is set only when the Democrat is not also an incumbent.
  - D/R personal vote (logit scale): the previous race on unchanged lines minus the presidential margin on those lines, and 0 if the previous race was uncontested.
    - Available in 2018 (vs 2016), 2020 (vs 2018) and 2024 (unchanged districts).
    - Not available in 2022, because of redistricting.
  - **Opponent type (MAGA/moderate) is not coded for 2018–2024.** It enters only the 2026 fit; dropping it there changes little (`adjusted_no_opponent_type`).
- **National environment** (House popular vote D−R, from the Clerk via the Wikipedia infoboxes): 2018 +8.6, 2020 +3.1,
  2022 −2.7, 2024 −2.6. 2026: +13 (project figure).

## Labels and coverage
Same rubric as 2026 (`label_work/RUBRIC.md`), calibrated to how the 2026 coders actually applied it:
- Plain CPC membership counts as liberal.
- Blue Dog, Problem Solvers, Blue Dog PAC, or NewDem Action Fund plus centrist branding counts as moderate.
- Liberal + populist maps to left_populist.

Only pre-election evidence was allowed:
- Caucus lists come from Wikipedia revisions dated just before each election.
- Group lists come from Wayback snapshots: Our Revolution 2018-11-04, PCCC, WFP 2022, Blue Dog PAC, NewDem Action Fund 2022, Red to Blue.
- Coders were told not to use results or later caucus joins.

| Cycle | Individually researched | Rule (safe incumbent) | Default (safe challenger) | high / med / low conf |
|---|---|---|---|---|
| 2018 | 230 (all \|pres\| ≤ 20, open seats, and any race with a left/moderate marker) | 82 | 82 | 66 / 166 / 160 |
| 2022 | 222 | 89 | 85 | 58 / 192 / 146 |
| 2020 | 105 new competitive/open nominees + 196 carried from 2018 | — | 103 | 47 / 158 / 199 |
| 2024 | 103 new + 184 carried from 2022 | — | 108 | 47 / 158 / 190 |

Lane counts, main sample (progressive / left_populist / center_populist / moderate; the rest are mainstream_liberal):

| Cycle | progressive | left_populist | center_populist | moderate |
|---|---|---|---|---|
| 2018 | 16 | 19 | 4 | 67 |
| 2020 | 18 | 11 | 1 | 53 |
| 2022 | 20 | 11 | 4 | 53 |
| 2024 | 15 | 2 | 3 | 44 |
| 2026 | 18 | 9 | 1 | 51 |

### Label reliability caveats
- **Eight parallel coders did 2018/2022.** Several ran out of the shared web-search budget, and Ballotpedia and some news sites could not be fetched.
  - "verified_fetch" sometimes means a search-result summary rather than a full page.
  - Coders made different calls on borderline cases. Examples:
    - "Won't commit to Pelosi" vs "will oppose Pelosi" for moderates.
    - Problem Solvers members in safe seats.
    - Whether a left insurgent's posture is populist (Summer Lee, McLeod-Skinner) or mixed.
- **2020/2024 coders had no web search at all.** They used Wikipedia wikitext and a few news pages, so those labels are weaker.
- **Coder differences may drive the cycle pattern.** The 2026 labels were coded separately, with exposure to post-election narratives (METHODOLOGY §2.5). Some of the cycle-to-cycle variation attributed below to the environment could be coder or regime differences.
- **Safe-seat challengers with no group marker default to mainstream_liberal.** In 2026, all 435 were researched and several left_populists were deep-red long shots. The historical populist lanes are therefore probably under-counted among safe-seat challengers.
- **False marker matches were found and dropped.** Brand New Congress (its page lists the winners who beat BNC candidates) and an Our Revolution name collision (CA-53) were removed from the marker code; the coders had already ignored them.

## Method
- **Per cycle.** OLS with archetype dummies (reference: mainstream liberal) and the controls above, on the 50×Δlogit scale (main, O-6) and the margin scale.
  - SEs are CR2, clustered by state; 80% intervals use t(G−1).
  - A structural version replaces the dummies with (L−1, P) coordinates.
  - The 2026 comparison row is the same House-only OLS on `races.json`, **not** the headline Gibbs fit, which includes Senate/Governor, Mundlak terms and t errors.
- **Environment.** A stacked race-level model gives the joint covariance of the cycle gaps:
  - state×cycle fixed effects;
  - cycle-specific spline and controls;
  - lane×cycle dummies;
  - CR2 clustered by state, so repeat candidates and states are handled.

  On that, four even-environment estimates:
  - GLS of gap = a + b·env over 2018/2022/2026; a is the even-environment gap.
  - The same with a DerSimonian–Laird τ², estimated from **one** residual degree of freedom.
  - Two-point interpolation between 2018 and 2022 to env = 0 (weights 0.24/0.76).
  - The plain 2018/2022 average, which sits at env D+3.0.
- **π (stretch).** The mean of the 2020 and 2024 gaps divided by the mean of the 2018 and 2022 gaps. Mean environments are similar (+0.25 vs +2.95). The interval comes from a joint-normal simulation.

## Results (main sample, 50×Δlogit; points vs mainstream liberal; 80% intervals)

**Per cycle (n in lane):**
| Lane | 2018 (D+8.6) | 2022 (R+2.7) | 2026 House OLS (D+13) | 2020 (D+3.1, pres) | 2024 (R+2.6, pres) |
|---|---|---|---|---|---|
| progressive | −1.4 [−5.7, +2.9] n16 | −3.9 [−6.2, −1.6] n20 | +1.3 [−1.8, +4.4] n18 | −2.0 [−4.6, +0.6] n18 | −0.4 [−2.1, +1.4] n15 |
| left_populist | +1.8 [−0.1, +3.7] n19 | −5.1 [−7.4, −2.9] n11 | +2.2 [−0.2, +4.7] n9 | −0.6 [−3.0, +1.7] n11 | −2.7 [−8.5, +3.1] n2 |
| center_populist | −1.8 [−4.7, +1.2] n4 | +3.6 [−2.4, +9.7] n4 | +5.8 (n1) | n1 | n3 |
| moderate | +3.2 [+1.9, +4.4] n67 | +1.7 [+0.6, +2.8] n53 | +2.6 [+0.8, +4.3] n51 | +0.3 [−0.9, +1.5] n53 | +1.7 [+0.8, +2.6] n44 |
| β_L (per step left) | −2.8 [−4.0, −1.5] | −2.5 [−3.8, −1.2] | −2.2 [−4.4, 0.0] | | |
| β_P (populist vs establishment) | +3.6 [+1.6, +5.5] | −1.8 [−3.6, −0.1] | +4.7 [+1.7, +7.7] | | |

**At an even national environment:**
| Lane | Slope per pt of env | GLS 3-cycle even gap | 2018/22 interpolation | 2018/22 average |
|---|---|---|---|---|
| progressive | +0.28 [+0.14, +0.42] | **−2.9 [−4.8, −1.0]** | −3.3 [−5.8, −0.8] | −2.6 [−5.6, +0.3] |
| left_populist | +0.53 [+0.30, +0.75] | **−3.7 [−5.4, −1.9]** | −3.5 [−5.2, −1.7] | −1.7 [−3.1, −0.3] |
| center_populist | (n = 4, 4, 1) | −0.7 [−5.0, +3.6]; RE +1.9 [−4.9, +8.7] | +2.4 [−2.2, +6.9] | +0.9 [−2.3, +4.2] |
| moderate | +0.10 [+0.02, +0.19] | **+1.9 [+0.9, +2.8]** | +2.0 [+1.0, +3.0] | +2.4 [+1.4, +3.4] |
| β_L | −0.02 [−0.10, +0.06] | −2.4 [−3.4, −1.3] | −2.5 | −2.6 |
| β_P | +0.44 [+0.28, +0.60] | −0.5 [−1.9, +0.9] | −0.6 | +0.9 |

The margin scale is similar but slightly smaller: progressive −2.3, left_populist −3.3, moderate +1.7.

**Sensitivity of the even-environment gap (logit, GLS 3-cycle):**
| Sample | progressive | left_populist | moderate |
|---|---|---|---|
| main | −2.9 | −3.7 | +1.9 |
| competitive only (\|pres\| ≤ 20) | −1.3 [−3.1, +0.5] (slope ≈ 0) | −4.2 [−6.7, −1.8] | +1.5 [+0.4, +2.5] |
| researched labels only (2018/22) | −2.5 [−4.6, −0.4] | −3.3 [−5.3, −1.3] | +2.1 [+0.9, +3.2] |
| medium/high confidence only | −3.6 [−5.5, −1.8] | −3.8 [−5.7, −1.9] | +0.9 [−0.2, +2.0] |
| marker-only rule labels (2018/22) | −3.1 [−4.2, −1.9] | −2.4 [−4.3, −0.6] | +0.8 [0.0, +1.7] |
| Huber robust | −2.5 [−3.8, −1.3] | −2.8 [−4.1, −1.6] | +1.3 [+0.6, +2.1] (RE +1.8) |

**π (presidential-year / midterm gap):**
- The only reasonably determined ratio is the leftness slope: **β_L π ≈ 0.54 (80% 0.29–1.02)** on the logit scale; 0.52 on the margin scale; 0.46 with Huber.
- The moderate gap gives 0.41 (0.09–0.98).
- The progressive and left_populist ratios are undetermined: their intervals span 0 to above 1, and 2024 has only 2 left_populists.

## How to read this against 2026
- **Same specification, three midterms.** The progressive and left_populist gaps move with the environment: −4 to −5 in R+2.7 2022, about −1 to +2 in D+8.6 2018, and +1 to +2 in D+13 2026.
  - The fitted line puts both at about **−3 points in an even environment**. 2026's House-only estimates are +1.3 and +2.2 on this OLS specification.
  - So the 2026 numbers (headline Gibbs: progressive −0.8, left_populist +1.3) **probably overstate left-lane viability in a neutral year by about 3–4 points**. That is consistent with the D7 compression finding.
- **The moderate advantage is steadier:** about +2 at even (slope +0.1/pt), close to its 2026 range (0 to +1.3 Gibbs, +2.6 OLS).
- **Split by component:** the leftness penalty (β_L ≈ −2.4 per step) is stable across all three cycles. What moves with the environment is the **populist posture** term: +3.6 in 2018, −1.8 in 2022, +4.7 in 2026. Outsider/populist campaigns did well in wave years and badly in the R-leaning year.
- **Center_populist cannot be estimated historically** (4, 4 and 1 races). Nothing here supports or refutes the 2026 +2.9.

## Caveats (read before quoting)
1. **Three environments, one line.** Each "slope" rests on three cycle estimates, and τ² is estimated from a single residual degree of freedom.
   - The GLS intervals count only sampling noise. They do not count cycle-specific shocks unrelated to the environment, such as 2022's abortion/candidate-quality story or the 2018 Trump-backlash composition.
   - The honest interval for the even-environment gap is wider than shown, and the 2018/2022-only versions differ by up to 2 points (left_populist: −3.5 interpolated vs −1.7 averaged).
2. **Environment is confounded with the label regime** (separate coders per cycle, and 2026 coded after the results) and with the controls. 2022 has no personal-vote control; opponent type is 2026-only.
3. **Small lanes.**
   - left_populist has 19 / 11 / 9 races, and the 2018 group includes WV-3 Ojeda (+44 overperformance). The Huber fit softens it to −2.8.
   - center_populist and the 2024 left_populists are not estimable.
4. **Competitive-only flattens the progressive slope.** Restricted to |pres| ≤ 20, the progressive slope is about 0 and the even gap is −1.3 [−3.1, +0.5].
   - Much of the progressive environment slope comes from safe-seat incumbents (Omar, AOC, Bowman, Bush ran −13 to −21 in 2022).
   - The left_populist and moderate results hold in the competitive sample.
5. **π here is down-ballot, not top of ticket.** It measures how House-candidate style shows up against a same-day presidential baseline (ticket-splitting). It is not how a presidential nominee's style would play.
   - Residual SDs are also smaller in presidential years: 4.7 and 4.0 vs 5.3 and 4.9.
   - Treat 0.5 as weak evidence that the π prior's median of 1 is high for down-ballot transfer, not as an estimate of π itself.
6. **Rounding.** 2024 baselines are integer-rounded, and Wikipedia results are rounded to 0.1.
7. **Data provenance.**
   - All numbers come from fetched files under `research/history/raw/` (Wikipedia raw wikitext, sheet CSV exports, pre-election Wikipedia revisions, Wayback snapshots).
   - Results were not cross-checked against state certification files.
   - The Our Revolution 2018 and PCCC 2018 snapshots are dated 2018-11-04 and 2018-11-10. The second lists only pre-election endorsements.
