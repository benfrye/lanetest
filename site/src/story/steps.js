// The story: chapters and steps, built from the loaded data so no number in the copy is
// hand-typed. Wording follows the claims ledger in analysis/output/findings.md (§8).
// A step's `html` may be a function of ctx so it can react to the reader (their guess).
import { ARCHETYPES, ARCHETYPE_BY_ID, shapePath } from '../lib/archetypes.js';
import { C } from '../components/index.js';

const ORDER = ARCHETYPES.map((a) => a.id);
const rows = ARCHETYPES.map((a) => ({ id: a.id, label: a.label }));

const pts = (v, d = 0) => `${Math.abs(v).toFixed(d)}`;
// Signed points; a value that rounds to zero prints as a bare 0, never "−0".
const signed = (v, d = 0) => {
  const r = Number(v.toFixed(d));
  return r === 0 ? '0' : `${r > 0 ? '+' : '−'}${Math.abs(r).toFixed(d)}`;
};
const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : null;
};

// Inline legend chip: shape in the archetype color, label in ink.
export function chip(id) {
  const a = ARCHETYPE_BY_ID[id];
  return `<span class="chip"><svg viewBox="-7 -7 14 14" aria-hidden="true"><path d="${shapePath(a.shape, 5)}" fill="var(${a.token})"/></svg>${a.label.toLowerCase()}</span>`;
}

// A second edition leaves out the 2028 chapters (build with VITE_NO2028=1).
const NO2028 = import.meta.env?.VITE_NO2028 === '1';

export function buildStory(ctx) {
  const { params, story, races } = ctx.data;
  const nodes = ctx.nodes;
  const nyt = story.nyt.topline;
  const raw = params.reveal.raw;
  const adj = params.reveal.adjusted;
  const flags = params.copy_flags;
  const maine = params.reveal.maine;

  const senateFlips = races.filter((r) => r.office === 'Senate' && r.flipped && r.called === 'D').length;
  const govFlips = races.filter((r) => r.office === 'Governor' && r.flipped && r.called === 'D').length;
  const contested = nodes.filter((n) => n.overperf != null);
  const ahead = contested.filter((n) => n.overperf > 0).length;
  const medGain = median(contested.map((n) => n.overperf));
  const rWon = contested.filter((n) => n.winner === 'R');
  const rAhead = rWon.filter((n) => n.overperf > 0).length;

  const vt = races.find((r) => r.id === 'GOV-VT');
  const progRows = races.filter((r) => r.included_in_fit && r.fit_archetype === 'progressive');
  const progExVt = progRows.filter((r) => r.id !== 'GOV-VT');
  const progExVtMean = progExVt.reduce((s, r) => s + r.overperformance, 0) / Math.max(1, progExVt.length);

  const prog = adj.progressive;
  const mod = adj.moderate;
  // Claims ledger C2 wording, built from the estimates: a bracket where the two models
  // disagree, "less than 1 point" under a point, otherwise the rounded gap.
  const gapPhrase = (d, ahead) => {
    const word = ahead ? 'ahead of' : 'behind';
    const range = d.delta_range_models;
    if (range) return `between ${pts(Math.min(...range.map(Math.abs)))} and about ${pts(Math.max(...range.map(Math.abs)))} ${Math.max(...range.map(Math.abs)) < 1.5 ? 'point' : 'points'} ${word} mainstream liberals, depending on the model`;
    const v = Math.abs(d.med);
    return `${v < 1 ? 'less than 1 point' : `about ${pts(v)} ${pts(v) === '1' ? 'point' : 'points'}`} ${word} mainstream liberals (likely range ${signed(d.lo)} to ${signed(d.hi)})`;
  };
  const progLine = `Progressives ran ${gapPhrase(prog, prog.med > 0)}.`;
  const modLine = `Moderates ran ${gapPhrase(mod, mod.med >= 0)}.`;
  const progGap = Math.abs(prog.med);
  const progGapText = progGap < 1 ? 'less than a point' : `about ${pts(progGap)} points`;
  // The previous headline spec, competitive seats only, as the alternative (robustness row R4).
  const compOnly = Object.fromEntries(
    (params.reveal.fragility ?? []).filter((f) => f.label === 'R4: competitive only (|pres2024| <= 20)').map((f) => [f.archetype, f]),
  );
  const altLine = compOnly.progressive && compOnly.moderate
    ? `Which races you compare matters. Count only competitive seats and the progressive gap widens to ${signed(compOnly.progressive.med, 1)} (range ${signed(compOnly.progressive.lo, 1)} to ${signed(compOnly.progressive.hi, 1)}), while moderates' edge shrinks to ${signed(compOnly.moderate.med, 1)}. Either way, the lanes sit within about 2 points of each other.`
    : '';
  // Required wherever the progressive effect is quoted (claims ledger, D5 placebo).
  const placeboNote = [
    flags.placebo_flag?.progressive
      ? ' In the progressives\' seats, a different Democrat already ran a few points ahead of Harris in 2024, so the place favored them: their gap could be larger than shown, not smaller.'
      : '',
    flags.placebo_flag?.moderate ? ' For moderates, part of the edge may be the place, not the candidate.' : '',
  ].join('');
  const blocked = flags.publish_blocked;
  // Claim C8 (validation.json headline_2028): the national cost that takes 10 points off
  // Democrats' 2028 chances, and how likely 2026 makes a progressive cost that big.
  const H28 = ctx.data.validation?.headline_2028 ?? {};
  const ev5 = ctx.data.validation?.sim5_ev ?? null;
  // O-8: the 2028 slides use lane gaps from 2018, 2022 and 2026 read at an even national mood.
  const hs = params.style?.history_summary ?? null;
  const histOn = ['history', 'blend'].includes(params.style?.default_preset) && !!hs;
  const hp = (a) => Math.max(1, Math.round(Math.abs(hs[a].even_gap)));
  const piDraws = [...(params.transfer_pi?.pi_draws ?? [])].sort((x, y) => x - y);
  const piMed = piDraws.length ? `${Math.round(piDraws[Math.floor(piDraws.length / 2)] * 10) * 10}%` : 'part';
  const estar = (a) => H28.published?.[a]?.Estar?.[0];
  const needs = (e) => (e == null ? '?' : e === 0 ? 'an even national vote' : e > 0 ? `D+${e}` : `R+${-e}`); // 2026 House vote as an EC map: raw and at the default (even) environment
  const c8 = H28.published?.progressive ?? null;
  // Mood vs. lane (validation headline_2028): a mainstream liberal's odds at the 10th and 90th
  // percentile of the default national mood, and each lane's odds over that whole range.
  const mood = H28.published?._mood ?? null;
  const pctOf = (v) => `${Math.round(v * 100)}%`;
  const moodE = (e) => (Math.abs(e) < 0.5 ? 'an even vote' : e > 0 ? `D+${Math.round(e)}` : `R+${Math.round(-e)}`);
  const oddsAt = (v) => (v < 0.03 ? 'almost no chance' : v > 0.97 ? 'near-certain' : `a ${pctOf(v)} chance`);
  const laneV = (a) => H28.published?.[a]?.V;
  const modEb = H28.ols_fe_eb_end_for_disagreeing_cells?.moderate?.dV_pts?.[0];
  const modDv = H28.published?.moderate?.dV_pts?.[0];
  const c8Cost = c8?.B_threshold != null ? Math.abs(c8.B_threshold).toFixed(1) : 'about 1.5';
  const c8OneIn = c8?.P_pidelta_le_B ? Math.round(1 / c8.P_pidelta_le_B) : 5;

  const lanesMeanSentence = ORDER.filter((a) => a !== 'center_populist')
    .map((a) => `${chip(a)} ${signed(raw[a].mean)}`)
    .join(', ');

  // Reader-facing timestamp: the snapshot date and time, without the source bookkeeping.
  const asOf = (() => {
    const m = String(params.meta.data_as_of).match(/(\d{4})-(\d{2})-(\d{2})\s*~?(\d{1,2}):(\d{2})\s*ET/);
    if (!m) return 'Nov. 4, 2026';
    const h = +m[4];
    return `Nov. ${+m[3]}, ${m[1]}, about ${h > 12 ? h - 12 : h}:${m[5]} ${h >= 12 ? 'p.m.' : 'a.m.'} ET`;
  })();

  const asOfShort = asOf.replace(/, about.*/, '');

  const chapters = [
    { id: 'wave', title: 'The wave' },
    { id: 'lanes', title: 'The lanes' },
    { id: 'quiz', title: 'Like with like' },
    { id: 'who', title: 'Who moved' },
    { id: '2028', title: 'Reading 2028' },
    { id: 'field', title: 'The field' },
    { id: 'end', title: 'What it means' },
  ];

  const swingParams = {
    value: (n) => n.overperf,
    domain: [-20, 40],
    refLines: [{ v: 0, label: 'Same margin as Harris 2024' }],
    axisLabel: 'Democratic margin vs. Harris 2024 in the same place, points',
    tickFormat: (v) => (v === 0 ? '0' : `${v > 0 ? '+' : '−'}${Math.abs(v)}`),
  };
  // Lane charts keep every race in its row, but the averages (and the copy) cover only the
  // model's sample: contested races with counts >= 80% and no strong third candidate. Races
  // outside it are faded rather than removed, so nothing disappears between steps.
  const laneParams = {
    ...swingParams,
    rows,
    rowOf: (n) => n.archetype,
    statOf: (n) => n.included,
    rowMedians: true,
    rowStat: 'mean',
    refLines: [{ v: 0 }],
  };
  // Median 2024 Harris margin where each lane's nominees ran (all contested races).
  const leanLabel = (a) => {
    const m = median(nodes.filter((n) => n.archetype === a && n.pres24 != null).map((n) => n.pres24));
    if (m == null) return 'n/a';
    const r = Math.round(m);
    return r === 0 ? 'even' : `${r > 0 ? 'Harris' : 'Trump'} +${Math.abs(r)}`;
  };
  const inAverage = (n) => n.included;
  // County/district swings relative to their state (geo_shifts.json summary medians).
  const geoMed = Object.fromEntries((story.geo?.summary ?? []).map((g) => [g.kind, g.median_relative]));
  const geoPts = (k) => `${Math.abs(Math.round(geoMed[k]))}`;
  const geoLine = story.geo
    ? `Heavily Hispanic districts ran about ${geoPts('Heavily Hispanic districts')} points ahead of the national swing. Small-town and rural counties mostly tracked their states. Black-majority counties swung about ${geoPts('Black-majority counties')} points less than their states, where Democrats were already near their ceiling.`
    : '';
  // Source lines for the dot-chart steps (their charts have no frame of their own).
  const SRC_RESULTS = '<p class="note">Source: 2026 results from NBC News and AP results pages and state election offices, as of ' + asOfShort + '; 2024 presidential margins by district from The Downballot and Wikipedia.</p>';
  const SRC_LANES = '<p class="note">Source: results as above; candidate lanes are our classification from endorsements, caucus memberships and campaign coverage (see methodology).</p>';
  const dimNote = 'Faded dots: votes still being counted, or a strong independent ran. Left out of the averages.';
  const offScale = (id) => {
    const n = nodes.find((d) => d.id === id);
    const v = n?.overperf;
    const out = v != null && (v < swingParams.domain[0] || v > swingParams.domain[1]);
    return out ? ` (${signed(v)}, off scale)` : '';
  };

  const steps = [
    {
      id: 'intro',
      chapter: 'wave',
      cardMode: 'center',
      stage: { layout: 'cloud', color: 'none' },
      html: `<h2>The Lane Test</h2>
        <p class="big">Democrats ran every kind of candidate in 2026: democratic socialists, Sanders-style populists, Blue Dogs, party regulars. Nearly all of them ran ahead of Kamala Harris's 2024 showing.</p>
        <p>${NO2028 ? 'So what does that say about which kind of Democrat can win?' : 'So which kind should they run in 2028?'} Every dot here is one race for the House, Senate or governor in 2026, plus a handful of House special elections held since 2025.</p>
        <p class="note">Preliminary results as of ${asOf}. Counting continues, especially in the West.</p>`,
    },
    {
      id: 'winners',
      chapter: 'wave',
      stage: { layout: 'cloud', color: 'winner', params: { sortBy: (n) => -(n.margin ?? 0) } },
      html: `<p>Democrats won the national House vote by about <strong>${nyt.margin} points</strong>, according to New York Times estimates — a <strong>${nyt.shift_vs_2024}-point</strong> swing from Donald Trump's 2024 win.</p>
        <p>They flipped ${senateFlips} Senate seats and ${govFlips} governorships, including in Texas, Ohio, Iowa and Kansas.</p>`,
    },
    {
      id: 'swing',
      chapter: 'wave',
      interactive: true,
      stage: {
        layout: 'beeswarm',
        color: 'winner',
        params: swingParams,
        annotate: [{ id: 'SEN-TX', text: 'Texas Senate' }, { id: 'GOV-VT', text: `Vermont governor${offScale('GOV-VT')}` }],
      },
      html: `<p>How did each Democrat do compared with Kamala Harris's 2024 result in the same state or district? Dots right of the dashed line did better than she did; dots to the left did worse.</p>
        <p>${ahead} of ${contested.length} Democrats ran ahead of her; the typical one beat her margin by <strong>${pts(medGain)} points</strong>. Even in races Republicans won, ${rAhead} of ${rWon.length} moved toward Democrats.</p>
        <p class="note">Hover or tap a dot for the race.</p>`,
    },
    {
      id: 'lanes-intro',
      chapter: 'lanes',
      stage: { layout: 'rowgrid', color: 'archetype', params: { rows, rowOf: (n) => n.archetype } },
      html: `<p>What kind of Democrat ran in each race? We put every Democratic nominee, winners and losers alike, into one of five lanes based on how they campaigned: where they stood on policy, and whether they ran as outsiders or as part of the establishment. Hollow shapes are races the Democrat lost.</p>
        <p>${ARCHETYPES.map((a) => `${chip(a.id)}: ${a.blurb}`).join('<br/>')}</p>`,
    },
    {
      id: 'guess',
      chapter: 'lanes',
      interactive: true,
      stage: { layout: 'rowgrid', color: 'archetype', params: { rows, rowOf: (n) => n.archetype } },
      html: `<p>Before we show you: which kind of Democrat ran furthest ahead of Harris?</p>`,
      plainHtml: `<p>Before we show you: which kind of Democrat ran furthest ahead of Harris? Make a guess, then read on.</p>`,
      card: { component: C.GuessFirst },
    },
    {
      id: 'raw',
      chapter: 'lanes',
      interactive: true,
      stage: { layout: 'beeswarm', color: 'archetype', params: laneParams, highlight: inAverage, dimNote },
      html: (c) => {
        const order = ORDER.filter((a) => a !== 'center_populist').sort((a, b) => raw[b].mean - raw[a].mean);
        const g = c.reader.guess;
        const reaction = !g
          ? ''
          : g === order[0]
            ? `<p>You picked ${chip(g)}. On the raw numbers, you're right.</p>`
            : `<p>You picked ${chip(g)}. On the raw numbers, it was ${chip(order[0])}.</p>`;
        return `${reaction}<p>Average gain over Harris, by lane, across contested races: ${lanesMeanSentence}.</p>
          <p>Taken at face value, moderates win and progressives trail. Center populists are too few to call — most ran as independents, which we leave out.</p>`;
      },
    },
    {
      id: 'vermont',
      chapter: 'lanes',
      interactive: true,
      stage: {
        layout: 'beeswarm',
        color: 'archetype',
        params: laneParams,
        highlight: (n) => n.included && n.archetype === 'progressive',
        annotate: [{ id: 'GOV-VT', text: `Vermont governor${offScale('GOV-VT')}` }],
      },
      html: `<p>And one race drags the progressive average down hard: Vermont's governor race against Phil Scott, a popular Republican incumbent. The Democrat finished ${pts(Math.abs(vt?.overperformance ?? 0))} points <em>behind</em> Harris.</p>
        <p>Without it, progressives averaged ${signed(progExVtMean)} — still last, but closer.</p>`,
    },
    {
      id: 'but',
      chapter: 'lanes',
      interactive: true,
      stage: {
        layout: 'beeswarm',
        color: 'archetype',
        params: {
          value: (n) => n.pres24,
          domain: [-50, 50],
          rows,
          rowOf: (n) => n.archetype,
          rowMedians: true,
          refLines: [{ v: 0, label: 'Even in 2024' }],
          axisLabel: "Harris's 2024 margin where each Democrat ran (beyond 50 points shown at the edge)",
          tickFormat: (v) => (v === 0 ? 'Even' : `${v > 0 ? 'D' : 'R'}+${Math.abs(v)}`),
        },
      },
      html: `<p>But they didn't run in the same places. Here each race is placed by how Harris did in that state or district in 2024; the line marks the middle race in each lane.</p>
        <p>Progressives mostly ran where Harris won big (median ${leanLabel('progressive')}). Left and center populists mostly ran where Trump won big (${leanLabel('left_populist')} and ${leanLabel('center_populist')}). Moderates ran in swing territory (${leanLabel('moderate')}).</p>
        <p>That matters because a wave plays out differently in a deep-red state than in a safe blue seat. So raw averages alone can't tell us which lane did best.</p>`,
    },
    {
      id: 'adjust',
      chapter: 'lanes',
      interactive: true,
      // Floats over the lane averages (faded), which the next step picks back up.
      stage: { component: C.RawVsAdjusted, overlay: true, under: { layout: 'beeswarm', color: 'archetype', params: laneParams, highlight: inAverage, dimNote } },
      html: `<p>So we compared like with like: each nominee against mainstream liberals in similar seats in the same state, with the same incumbency and the same kind of Republican.</p>
        ${flags.no_predictive_gain ? '<p>The gaps mostly collapse: in 2026 we found no detectable difference between styles.</p>' : '<p>The gaps mostly collapse.</p>'}
        <p>Within that range: ${progLine} ${modLine} Left and center populists are too few to estimate on their own.</p>
        ${altLine && !histOn ? `<p>${altLine}</p>` : ''}
        ${histOn ? `<p>That's in a wave. Adding 2018 and 2022, in competitive seats, progressives trail mainstream liberals by about ${hp('progressive')} ${hp('progressive') === 1 ? 'point' : 'points'}, left populists by about ${hp('left_populist')}, and moderates run about ${hp('moderate')} ahead.</p>` : ''}
        <p class="note">Comparable races, not cause and effect; preliminary.${placeboNote}</p>
        ${blocked ? '<p class="note">Model under review: these estimates are preliminary and may change.</p>' : ''}`,
    },

    {
      id: 'quiz',
      chapter: 'quiz',
      interactive: true,
      stage: {
        layout: 'beeswarm',
        color: 'archetype',
        params: laneParams,
        highlight: (n) => ctx.reader.quizPair?.includes(n.id) ?? n.included,
        annotate: [],
        deps: () => ctx.reader.quizPair,
      },
      html: `<p>Try it yourself. Each pair below ran in places Harris did about equally well, with the same incumbency and the same kind of Republican opponent.</p>`,
      card: { component: C.QuizPairs, props: { onpair: (ids) => (ctx.reader.quizPair = ids) } },
    },
    {
      id: 'cases',
      chapter: 'quiz',
      interactive: true,
      stage: { component: C.CaseStudies },
      html: `<p>Four races that people will argue about.</p>
        <p>In Maine, ${maine.nominee} replaced the original nominee in July and beat Susan Collins. Democrats gained far less there than elsewhere — which looks like Collins's personal vote, not a populism penalty. One race can't separate the candidate from the opponent.</p>`,
    },
    {
      id: 'groups',
      chapter: 'who',
      interactive: true,
      stage: { component: C.GroupShifts },
      html: `<p>Lanes are one way to read 2026. Voters are another. The surge wasn't even across groups. Both the Times's estimates and the network exit poll put the biggest swing among voters under 30, and big swings among Hispanic and Asian voters.</p>
        <p>The two sources disagree on a few groups, most on Asian and older voters, and only on voters 65 and older do they point in opposite directions. So we show both.</p>`,
    },
    {
      id: 'geo',
      chapter: 'who',
      interactive: true,
      stage: { component: C.GeoShifts },
      html: `<p>Places tell the same story from another angle. Each dot is a county or district, compared with its own state's swing in the same race.</p>
        <p>${geoLine}</p>
        <p class="note">A sample of places, not every county; counting continues.</p>`,
    },
    {
      id: 'nine',
      chapter: 'who',
      interactive: true,
      stage: { component: C.NineStates },
      html: `<p>The Times estimated how each group voted in nine Senate races. The pattern holds almost everywhere: the youngest voters swung furthest, the oldest the least.</p>
        <p>Maine is the outlier: in the Times’s estimates, voters 65 and older and white voters without a degree moved toward Republicans there, even as Jackson won. Nine races are a description, not proof of a lane effect.</p>`,
    },
    {
      id: 'measures',
      chapter: 'who',
      interactive: true,
      stage: { component: C.BallotGap },
      html: `<p>Was there a hidden appetite for populist economics that candidates failed to tap? Ballot measures are one test.</p>
        <p>Mostly not. California's tax on high earners, Colorado's graduated income tax and Oklahoma's $15 minimum wage (on a June ballot) all ran <em>behind</em> the Democrat at the top of the ticket.</p>
        <p>Where the progressive side ran far ahead, it was a mix: abortion rights, campaign-contribution limits in Alaska, and Republican-backed measures voters rejected in red states.</p>`,
    },

    {
      id: 'env-first',
      chapter: '2028',
      interactive: true,
      stage: { component: C.ArchetypeSim, props: { mode: 'environment' } },
      html: `<p>Now carry this to 2028. The biggest unknown isn't the candidate. It's the national mood.</p>
        <p>Each line is one lane's chance of winning the Electoral College as the national environment shifts. Drag the slider.</p>
        ${histOn ? `<p>The lines sit close together. Adding ordinary years to 2026's wave, the progressive and left-populist lines sit slightly to the right (they need a slightly better year) and the moderate line slightly to the left. In a lopsided year none of that matters; in a close one it might. (Center populists are too rare to measure.)</p>` : `<p>The lines bunch together. The progressive line sits slightly to the right, a gap of ${progGapText}: in a lopsided year it hardly matters; in a very close one it could. (The center-populist line rests on just two races.)</p>`}
        <p class="note">Based on comparable House races${histOn ? ' in 2018, 2022 and 2026' : ' in 2026'}, not cause and effect.${placeboNote}</p>
        <p class="note">${params.banners.not_forecast}</p>`,
    },
    {
      id: 'breakeven',
      chapter: '2028',
      interactive: true,
      stage: { component: C.ArchetypeSim, props: { mode: 'breakeven' } },
      html: `<p>Another way to see it: how good a national environment does each lane need to make the race a coin flip?</p>
        ${histOn ? `<p>A mainstream liberal needs about ${needs(estar('mainstream_liberal'))}. A moderate can get there at ${needs(estar('moderate'))}, while a progressive needs ${needs(estar('progressive'))} and a left populist ${needs(estar('left_populist'))} Center populists are left out: too few ran in any year to measure.</p>` : '<p>Every lane needs roughly an even national vote, give or take a point or two. The differences sit inside the uncertainty of the estimates.</p>'}
        <p class="note">Ranges are in the chart.${placeboNote}</p>`,
    },
    {
      id: 'believe',
      chapter: '2028',
      interactive: true,
      stage: { component: C.LaneCost },
      html: `<p>Suppose a progressive nominee really does cost Democrats votes. How much would it take to matter?</p>
        <p>Drag the slider to try different costs. A small cost barely moves Democrats' chances. To knock about 10 points off them, a progressive would have to cost ${c8Cost} points nationwide, and ${c8?.P_pidelta_le_B >= 0.5 ? `${histOn ? '2026 and past elections suggest' : '2026 suggests'} a cost that big is more likely than not (about ${pctOf(c8.P_pidelta_le_B)})` : `${histOn ? '2026 and past elections suggest' : '2026 suggests'} a cost that big is unlikely: about a 1 in ${c8OneIn} chance`}.</p>
        ${histOn ? '<p>Left populists look similar. Moderates point the other way: they have usually run a little ahead.</p>' : '<p>For moderates and populists, 2026 points the other way: if anything, they gained votes.</p>'}
        ${placeboNote ? `<p class="note">${placeboNote.trim()}</p>` : ''}`,
    },
    {
      id: 'sim-run',
      chapter: '2028',
      interactive: true,
      stage: { component: C.ArchetypeSim, props: { mode: 'run' } },
      html: `<p>What would 2028 look like with each kind of Democrat? Pick one on the wheel and press start: we play out the election 10,000 times.</p>
        <p>Look how wide the pile is. Democrats win some runs in a landslide and lose others badly. That's the national mood: nobody knows yet whether 2028 will be a good year or a bad one for Democrats${mood ? ` (anything from about ${moodE(mood.E10)} to ${moodE(mood.E90)} is plausible)` : ''}, so each run rolls the dice on it. That matters more than anything else.</p>
        ${laneV('mainstream_liberal') != null ? `<p>Now spin the wheel and the pile slides: a mainstream liberal wins ${pctOf(laneV('mainstream_liberal'))} of runs, a moderate ${pctOf(laneV('moderate'))}, a progressive ${pctOf(laneV('progressive'))}${laneV('left_populist') != null ? ` and a left populist ${pctOf(laneV('left_populist'))}` : ''}. That's the lane${histOn ? ', measured across ordinary years rather than 2026\'s wave alone' : ''}. The mood swings things far more; the lane could matter only in a close race.</p>` : ''}
`,
    },

    {
      id: 'matrix',
      chapter: 'field',
      interactive: true,
      stage: { component: C.MatchupMatrix },
      html: () => {
        // Biggest track-record credit and penalty on each side, for the examples in the copy.
        const med = (c) => {
          const d = [...(c.track?.c_draws ?? [0])].sort((a, b) => a - b);
          return d[Math.floor(d.length / 2)] ?? 0;
        };
        const byRec = (list) => [...(list ?? [])].filter((c) => c.include_default !== false).sort((a, b) => med(b) - med(a));
        const dRec = byRec(params.candidates_dem);
        const gRec = byRec(params.candidates_gop);
        const last = (n) => n.split(' ').slice(-1)[0];
        const ex = dRec.length && gRec.length
          ? `; ${last(dRec[0].name)} and ${gRec[0].name} gain the most, ${last(dRec[dRec.length - 1].name)} loses the most`
          : '';
        return `<p>That was a typical Democrat of each kind. Here are the actual names: every likely Democrat against every likely Republican, each pairing played out thousands of times from the same unknown national mood.</p>
        <p>What separates the cells: <strong>lane</strong> (a point or so: left-leaning Democrats a little behind, moderates a little ahead), <strong>track record</strong> (how far each candidate has run ahead of or behind their own party before, adjusted for good and bad years${ex}), <strong>Republican type</strong> (Trump-style candidates ran slightly worse in 2026) and <strong>home state</strong> (a boost at home, which only matters in a swing state).</p>
        <p>Blue: the Democrat wins more often; red: the Republican. Tap a cell for the breakdown.</p>`;
      },
    },
    {
      id: 'primary',
      chapter: 'field',
      interactive: true,
      stage: { component: C.PrimarySim },
      html: `<p>But first a Democrat has to win the nomination. This runs the primary calendar 10,000 times from current polls plus some basic assumptions about how campaigns rise and fall.</p>
        <p class="note">${params.banners.primary_weak_proxy}</p>`,
    },
    {
      id: 'build',
      chapter: 'field',
      interactive: true,
      stage: { component: C.StateLadder },
      html: `<p>So where does a lane actually make a difference? Here every state is lined up from most Democratic to most Republican, each as wide as its electoral votes. Democrats need to get past the 270 line.</p>
        <p>The dotted line shows how far your candidate gets: the states they're favored to carry. Drag the national mood and it races across the ladder. Spin the wheel and it moves only a few states, but in a close year those are exactly the states sitting at 270.</p>
        <p>A lane moves every state by about the same amount, like the national mood does; we don't have the district data to test whether a style plays better in some states, so the model assumes it doesn't. So the lane matters in one place: the handful of close states listed under the chart.</p>`,
    },
    {
      id: 'as-pres',
      chapter: 'field',
      interactive: true,
      stage: { component: C.AsPresident },
      html: `<p>One last way to read November: as if it had picked a president. Color each state by how it voted for the House, add up the electoral votes, and 2026 is a Democratic landslide.</p>
        <p>But that was a wave year. Switch the map to an even year: each state keeps its 2026 lean, but the national vote is reset to a tie. The landslide disappears${ev5?.durable != null ? `: Democrats fall to about ${ev5.durable} electoral votes, ${ev5.durable >= 270 ? 'barely enough' : 'just short of the 270 they need'}` : ''}, and the race comes down to the usual handful of swing states.</p>
        <p>That's the whole story in one map. The national mood decides most of it. But in a close year, the few points a nominee gains or loses in states like Pennsylvania, Michigan and Wisconsin are exactly what the lanes are fighting over.</p>`,
    },

    {
      id: 'conclusion',
      chapter: 'end',
      cardMode: 'center',
      stage: { layout: 'beeswarm', color: 'archetype', params: laneParams, highlight: inAverage, dimNote },
      html: `<h2>What 2026 says</h2>
        <p class="big">Every lane surged in 2026, and in a wave that big the differences between them nearly vanished: progressives, moderates and party regulars all landed within about a point of each other.</p>
        ${histOn ? `<p>Ordinary years add a little. In competitive seats across 2018, 2022 and 2026, read at an even national mood, Democrats running further left trailed mainstream liberals by about ${hp('progressive')} to ${hp('left_populist')} points, and moderates ran about ${hp('moderate')} ahead. In presidential-year House races the gaps were only about half as big, so our 2028 numbers blend 2026 with that history and carry about ${piMed} of the gap over to a presidential race.</p>
        <p>So the lane probably matters a little, most likely favoring moderates over the left, though the ranges still include no effect at all. In a very close 2028 that could decide the race. But the national mood matters far more: across its likely range it takes a Democrat from ${mood ? `${oddsAt(mood.V_ml_at_E10)} to ${oddsAt(mood.V_ml_at_E90)}` : 'a long shot to a near-lock'}.</p>` : `<p>For 2028, the national mood still matters most: across its likely range it takes a Democrat from ${mood ? `${oddsAt(mood.V_ml_at_E10)} to ${oddsAt(mood.V_ml_at_E90)}` : 'a long shot to a near-lock'}. In a close year, the lane could still tip it.</p>`}
        <p>Watch three things: whether 2028's mood looks more like 2026 or 2024, whether young and Hispanic voters stay with Democrats, and whether a populist message travels without a wave behind it.</p>
        <p class="note">Comparable races, not cause and effect; preliminary results.</p>`,
    },
    {
      id: 'method',
      chapter: 'end',
      cardMode: 'wide',
      stage: { layout: 'tiles', color: 'archetype' },
      // The html only shows in plain-article mode; the interactive card renders Methodology.
      plainHtml: `<p>How we did this: every 2026 Democratic nominee was classified by how they ran (ideology and outsider-or-insider posture). For each race we compared the 2026 margin with Harris's 2024 margin in the same place, then compared each lane with mainstream liberals on the same ballot, in seats of similar partisanship, accounting for incumbency and the Republican opponent. The 2028 simulations translate those estimates under stated assumptions; they are not forecasts. Results are preliminary as of ${asOf}. Full data: <a href="data/races.json">races.json</a>.</p>`,
      card: { component: C.Methodology },
    },
  ];

  // Append each dot-chart step's source line to its card text.
  const SRC = {
    winners: '<p class="note">Source: national vote from New York Times Voter Trends; flips from NBC News and AP race calls, as of ' + asOfShort + '.</p>',
    swing: SRC_RESULTS,
    'lanes-intro': SRC_LANES,
    raw: SRC_RESULTS + SRC_LANES,
    but: SRC_RESULTS,
    vermont: SRC_RESULTS,
  };
  for (const st of steps) {
    const extra = SRC[st.id];
    if (!extra || !st.html) continue;
    const h = st.html;
    st.html = typeof h === 'function' ? (c) => h(c) + extra : h + extra;
  }

  // The chart steps between the quiz and the ending float on the same card over the faded lane
  // averages, so the dots stay on screen and the card swaps its chart in place from step to step.
  const laneUnder = { layout: 'beeswarm', color: 'archetype', params: laneParams, highlight: inAverage, dimNote };
  for (const st of steps) {
    if (['cases', 'groups', 'geo', 'nine', 'measures'].includes(st.id) && st.stage?.component) {
      st.stage = { ...st.stage, overlay: true, under: laneUnder };
    }
  }
  if (!NO2028) return { chapters, steps };
  // ---- No-2028 edition: the history chart gets its own step, the 2028 chapters go, and the
  // ending answers the question from the evidence alone.
  const cc = params.style?.history_summary?.competitive_cycles ?? {};
  const ys = Object.keys(cc).sort();
  const gapsOf = (a) => ys.map((y) => cc[y].gaps[a]?.est).filter((v) => v != null);
  const rng = (a) => {
    const g = gapsOf(a);
    return g.length ? [Math.min(...g), Math.max(...g)] : null;
  };
  const r1 = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${Math.abs(Math.round(v))}`;
  const modR = rng('moderate'), progR = rng('progressive'), lpR = rng('left_populist');
  const modAhead = gapsOf('moderate').filter((v) => v > 0).length;
  const historyStep = {
    id: 'history',
    chapter: 'lanes',
    interactive: true,
    // Same floating card as the step before, over the same faded lane averages.
    stage: { component: C.LaneHistory, overlay: true, under: { layout: 'beeswarm', color: 'archetype', params: laneParams, highlight: inAverage, dimNote } },
    html: `<p>2026 was a wave, and a wave can blur the differences between Democrats. So we went back to earlier House elections, gave every competitive-seat Democrat a lane the same way, and ran the same comparison.</p>
      <p>The picture is noisy: in any one year only a handful of progressives or left populists ran in close seats.</p>
      ${modR ? `<p>Moderates ran ahead of or even with mainstream liberals in ${modAhead} of ${ys.length} elections, by up to ${pts(modR[1])} points. Progressives ranged from ${r1(progR[0])} to ${r1(progR[1])}, mostly close to even. Left populists swung from ${r1(lpR[0])} to ${r1(lpR[1])}: too erratic to call.</p>` : ''}
      <p class="note">Same comparison as the 2026 one, on competitive seats only (presidential margin within 20 points). Lanes for earlier years were coded from endorsements and caucus memberships before each election.</p>`,
  };
  const keep = steps.filter((st) => !['2028', 'field'].includes(st.chapter));
  keep.splice(keep.findIndex((st) => st.id === 'adjust') + 1, 0, historyStep);
  const concl = keep.find((st) => st.id === 'conclusion');
  concl.html = `<h2>What 2026 says</h2>
    <p class="big">Every kind of Democrat surged in 2026, and compared like with like, the differences between them nearly vanished: progressives ran about a point behind mainstream liberals, moderates about a point ahead.</p>
    <p>Earlier elections point the same way, faintly. Moderates have usually run a little ahead in close seats; progressives a little behind or even. Left populists swing too much from year to year to call either way.</p>
    <p>So is a progressive or a populist unelectable? Nothing here says so. Is a moderate safer? Slightly, maybe, by a point or two: enough to matter in a coin-flip race, but small next to the national mood, which lifted the typical Democrat ${pts(medGain)} points over Harris in a single cycle.</p>
    <p>Watch three things: whether 2028's mood looks more like 2026 or 2024, whether young and Hispanic voters stay with Democrats, and whether a populist message travels without a wave behind it.</p>
    <p class="note">Comparable races, not cause and effect; preliminary results.</p>`;
  return { chapters: chapters.filter((c) => !['2028', 'field'].includes(c.id)), steps: keep };
}
