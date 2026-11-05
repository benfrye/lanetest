// Loads the data snapshot in public/data and builds the shared story context (ctx).
// Every component gets the same ctx; see STORY.md "Shared reader state".
import { createSimClient } from './sim/client.js';

const STORY_FILES = {
  raw: 'raw_overperformance_by_archetype',
  oaxaca: 'oaxaca_decomposition',
  quiz: 'quiz_pairs',
  nine: 'nyt_nine_state',
  nyt: 'nyt_voter_trends',
  primaries: 'primaries_linkage',
  measures: 'ballot_measure_gaps',
  candidates: 'candidate_profiles',
  sample: 'sample_and_exclusions',
  groupSources: 'group_sources',
  geo: 'geo_shifts',
  sources: 'sources',
};

const getJSON = (path) =>
  fetch(new URL(path, document.baseURI)).then((r) => {
    if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
    return r.json();
  });

// One dot per race for the stage. Overperformance is two-party, vs Harris 2024 on current lines.
export function toNode(r) {
  const office = r.office === 'Special' ? 'House' : r.office;
  return {
    id: r.id,
    label: r.office === 'House' ? r.id : `${r.state} ${office === 'Governor' ? 'governor' : office}`,
    office: r.office,
    state: r.state,
    // fit_archetype is the audited label the model used (Set B where the agent label had no
    // pre-election evidence); use it so every chart matches the estimates.
    archetype: r.fit_archetype ?? r.archetype,
    dem: r.dem_name,
    rep: r.rep_name,
    margin: r.margin_2p ?? r.margin,
    pres24: r.pres2024_margin_2p ?? r.pres2024_margin,
    overperf: r.overperformance,
    // 'D'/'R' once called; finished specials ('final') by their margin; uncalled races stay null.
    winner: r.called === 'D' || r.called === 'R' ? r.called : r.called === 'final' && r.margin != null ? (r.margin > 0 ? 'D' : 'R') : null,
    flipped: r.flipped,
    counted: r.pct_counted,
    included: r.included_in_fit,
    exclusion: r.exclusion_reason ?? null,
  };
}

export async function loadContext() {
  const [races, params, validation, manifest, ...story] = await Promise.all([
    getJSON('data/races.json'),
    getJSON('data/model_params.json'),
    getJSON('data/validation.json'),
    getJSON('data/manifest.json'),
    ...Object.values(STORY_FILES).map((f) => getJSON(`data/story/${f}.json`)),
  ]);
  const storyData = Object.fromEntries(Object.keys(STORY_FILES).map((k, i) => [k, story[i]]));
  const raceRows = Array.isArray(races) ? races : races.races;
  // Dots: every race with a two-party result, i.e. a real D-vs-R contest.
  // 2025 off-year races are validation-only, not 2026 races, so they get no dot.
  const nodes = raceRows
    .filter((r) => r.margin != null && r.pres2024_margin != null && r.dem_name && r.rep_name)
    .filter((r) => !String(r.exclusion_reason ?? '').startsWith('validation_only'))
    .map(toNode);

  const sim = createSimClient();
  // Hand the worker the params already fetched, rather than downloading the 800 KB file twice.
  const simReady = sim.load(params);

  return {
    data: { races: raceRows, params, validation, manifest, story: storyData },
    nodes,
    sim,
    simReady,
  };
}
