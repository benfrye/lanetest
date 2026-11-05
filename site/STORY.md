# The Lane Test — beat sheet

Working title: **The Lane Test: What the 2026 midterms say about which Democrat can win in 2028**

Thesis (licensed by the claims ledger, `analysis/output/findings.md` §8): every kind of Democrat surged in 2026. Raw numbers make moderates look best and progressives worst, but most of that gap is *where* they ran. Compared like with like, style moved results by about a point, except progressives, who trail by somewhere between ~1 and ~4 points depending on the model. In 2028 the national environment, not the lane, decides most outcomes. Lanes matter at the margin, which is exactly where close elections are decided.

Numbers in `{{braces}}` are filled from analysis outputs at build time (never hand-typed). If a claim's flag in `validation.json` / `findings.md` changes, the copy follows the claims ledger wording.

## Shared reader state (`ctx`)
- `ctx.data`: `{ races, story: {raw, oaxaca, quiz, nine, primaries, measures, candidates, sample}, params }`
- `ctx.sim`: the client from `src/lib/sim/client.js` (`createSimClient()`), already loaded with params.
- `ctx.reader`: `$state` object: `{ guess: archetypeId|null, quizAnswers: [], env: number (default params E center), pi: number }`. Sims read and write `env`/`pi`, so a slider moved in one chapter carries forward.

## Component contracts
- **Card components** (`step.card`): props `{ ctx, nodes, onnext, ...props }`. Render inside the text card; must fit a 380px-wide column and a 46dvh mobile bottom sheet; any internal "continue" calls `onnext`.
- **Stage components** (`step.stage = { component, props }`): props `{ ctx, nodes, ...props }`. Fill the stage area (absolute, full size), responsive from 320px to 1600px wide, own their own legend and an accessible table/text alternative (visually hidden or a "Show as table" toggle).
- All charts follow the dataviz rules in `src/app.css`: party colors (`--dem`, `--rep`) never in the same chart as archetype colors; archetypes always carry shape + label; text in ink tokens; hover tooltips on desktop, tap-to-pin on touch; reduced motion respected.

## Chapters and beats

### 1. The wave (`wave`)
1. `intro` (center card, cloud of all races, color none): Title, dek. "Every dot is a race for the House, Senate or governor on November 3, 2026."
2. `winners` (cloud, color winner): Democrats won the national House vote by {{nyt.margin}} points, a {{nyt.shift}}-point swing from 2024 (NYT Voter Trends). Flips: Senate {{senate flips}}, governors {{gov flips}}.
3. `swing` (beeswarm of overperformance vs 2024, color overperf, refLine at 0 "Harris 2024 margin"): Nearly every Democrat ran ahead of Harris. Median gain {{median}}. A handful ran behind — label 2–3 of them (GOV-VT, SEN-ME).
4. `groups` (stage component **GroupShifts**: NYT national group shifts, dot plot of 2024→2026 margin per group): the swing was biggest among young voters (+32), Hispanic voters (+28), non-college voters; smallest among 65+ (+6). This frames the coalition question.

### 2. The lanes (`lanes`)
5. `lanes-intro` (grid layout grouped by archetype, color archetype): introduce the five lanes with chips (shape+color+label) and one-line definitions from `src/lib/archetypes.js`; counts per lane. Note: we classified every nominee by how they ran (ideology × posture), see methodology.
6. `guess` (card component **GuessFirst**; stage: grid by archetype): "Before we show you: which kind of Democrat ran furthest ahead of Harris?" Five buttons. Stores `ctx.reader.guess`. Advance only after a pick (or "skip").
7. `raw` (beeswarm by archetype rows, overperformance, rowMedians): reveal raw means {{raw.*}}: moderates +{{}}, left populists +{{}}, mainstream +{{}}, progressives +{{}}. Card reacts to the reader's guess ("You picked X…").
8. `but` (scatter pres2024 margin × 2026 margin, color archetype, diagonal): "But they didn't run in the same places." Progressives cluster in blue seats; moderates in swing seats; left populists often in red states.
9. `vermont` (beeswarm, highlight progressive, annotate GOV-VT): the progressive average includes Vermont's governor race against Phil Scott, a popular Republican incumbent (−{{}} pts). Excluding it moves the progressive raw mean to {{}}.
10. `adjust` (stage component **RawVsAdjusted**: per-archetype raw mean → adjusted δ with 80% interval, animated "shrink"; Oaxaca bar breakdown on tap): after comparing like with like (same state, same lean, incumbency, opponent), the differences shrink to about a point. Progressive cell shows the bracketed range if `models_disagree`.

### 3. Like with like (`quiz`)
11. `quiz` (card component **QuizPairs**, 5 matched pairs from `quiz_pairs.json`; stage highlights the two races in the beeswarm): "Race 1 of 5: which Democrat beat their 2024 baseline by more?" Reveal after each pick; score at end; observation that style predicted the winner of the pair about as often as a coin flip (compute from the pairs).
12. `cases` (stage component **CaseStudies**: 4 small panels): Maine (Jackson vs Collins: nominee swap, Collins personal vote, NYT vs count discrepancy, C9 wording), Texas (Talarico, left populist, biggest swing {{}}), Kansas/Iowa (moderates flipped deep-red seats), 2025 contrast (Mamdani vs Spanberger/Sherrill).
13. `nine` (stage component **NineStates**: NYT 9-state Senate group shifts as a small-multiple dot plot): Maine is the outlier among older and white non-college voters; descriptive only (C10).
14. `measures` (stage component **BallotGap**): a test of hidden populist demand — left-leaning economic measures mostly ran BEHIND the Democrats on the same ballot; measures that ran ahead were mostly abortion-rights amendments.

### 4. Reading 2028 (`2028`)
15. `env-first` (stage component **ArchetypeSim** in "environment" mode: P(win) curves vs national environment E, one curve per archetype; vertical line at reader's env): "The single biggest unknown for 2028 is the national mood." E slider (default {{E center}}). Curves sit almost on top of each other.
16. `breakeven` (ArchetypeSim "breakeven" mode: E* per archetype as dots with intervals): what environment each lane needs to be a coin flip.
17. `believe` (stage component **BelieveHeatmap**: what you'd have to believe — δ penalty × π transfer grid): "For lane choice to change the outcome, you'd have to believe…" Slider π.
18. `sim-run` (ArchetypeSim "run" mode with Start Simulation button → 10,000 runs animated as unit squares stacking into an EV histogram per selected archetype; tipping-point state): reader picks a lane (default = their guess).

### 5. The field (`field`)
19. `matrix` (stage component **MatchupMatrix**: Dem contenders × GOP contenders, P(win) cells in 5-pt bins, indistinguishability banner; tap a cell → tile map + tipping point): names from `candidate_profiles.json`.
20. `primary` (stage component **PrimarySim**: run the Democratic primary 10,000 times; ranked bar of nomination share; coalition note; "polls plus priors" caveat; chained P(presidency) off by default).
21. `build` (stage component **BuildYourOwn**: ideology + posture + home region + environment + turnout sliders → map + P(win), extrapolation warning).
22. `as-pres` (stage component **AsPresident**: 2026 results as an electoral map on the tile grid; toggle raw D+13 view vs durable D+3 view vs electorate view).

### 6. What it means (`end`)
23. `conclusion` (center card, cloud colored by archetype): the takeaway in claims-ledger wording; three things to watch.
24. `method` (card component **Methodology**: plain-language note from METHODOLOGY §9, data sources, as-of time, caveats, download links to races.json).
