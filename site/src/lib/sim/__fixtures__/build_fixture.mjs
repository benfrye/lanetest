#!/usr/bin/env node
// Build a schema-conforming (METHODOLOGY §6.4) fixture model_params.json for engine tests.
//
//   node site/src/lib/sim/__fixtures__/build_fixture.mjs
//
// REAL inputs (research/states.json): 2024/2020/2016 margins, electoral votes incl. ME/NE
// districts, demographic shares (→ G, W̃, Ỹ, factor loadings), candidate names/archetypes/homes/
// polls/markets, 2026 Senate and governor margins.
// PLACEHOLDER (clearly marked, "fixture": true): every style/opponent/π/primary parameter draw,
// factor scales, σ_idio, rel26, the Sim 5 House margins. Do not publish numbers from this file.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { substream } from '../rng.js';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '../../../../..');
const research = (f) => JSON.parse(readFileSync(join(root, 'research', f), 'utf8'));
const OUT = join(here, 'model_params.fixture.json');

const SEED = 20261104;
const P = 1000;
const r2 = (x, d = 4) => Math.round(x * 10 ** d) / 10 ** d;

const states = research('states.json');
const rows = states.rows;

// ------------------------------------------------------------------ national margins
const nonDistrict = rows.filter((r) => r.type !== 'congressional_district');
let Dv = 0, Rv = 0;
for (const r of nonDistrict) { Dv += r.pres2024.dem_votes; Rv += r.pres2024.rep_votes; }
const E24 = (100 * (Dv - Rv)) / (Dv + Rv); // two-party, from certified state totals
const TWO_PARTY_2020 = 0.982, TWO_PARTY_2016 = 0.943; // §2.2
const M20_US = 4.45 / TWO_PARTY_2020; // Biden +4.45 total-vote → two-party
const M16_US = 2.09 / TWO_PARTY_2016; // Clinton +2.09

// ------------------------------------------------------------------ G (§5.3) from CVAP shares
const rMid = { white: 70 / 63, black: 11 / 12, hisp: 10 / 14, asian: 4 / 5, other: 4 / 5,
  y1829: 12 / 20, a3044: 21 / 25, a4564: 33 / 31, a65: 34 / 24, noncollege: 57 / 66, college: 42 / 35 };
const rPres = Object.fromEntries(Object.entries(rMid).map(([k, v]) => [k, 1 + 0.5 * (v - 1)])); // §2.1 fallback
const SHIFT_RE = { wc: 9, wnc: 14, black: 9, hisp: 28, asian: 17, other: 17 };
const SHIFT_AGE = { y1829: 32, a3044: 24, a4564: 13, a65: 6 };
const SPLIT_3044 = 0.44; // national share of 30–64 that is 30–44 (approx.)

function rawG(r) {
  const white = r.white_nh_pct_cvap;
  const wFrac = r.white_noncollege_pct_adults25 / (r.white_noncollege_pct_adults25 + r.white_college_pct_adults25);
  const cells = {
    wnc: white * wFrac * rPres.white * rPres.noncollege,
    wc: white * (1 - wFrac) * rPres.white * rPres.college,
    black: r.black_nh_pct_cvap * rPres.black,
    hisp: r.hispanic_pct_cvap * rPres.hisp,
    asian: r.asian_nh_pct_cvap * rPres.asian,
    other: r.other_nh_pct_cvap * rPres.other,
  };
  const tot = Object.values(cells).reduce((s, x) => s + x, 0);
  const Gre = Object.entries(cells).reduce((s, [k, v]) => s + (v / tot) * SHIFT_RE[k], 0);
  const mid = 100 - r.age_18_29_pct_cvap - r.age_65plus_pct_cvap;
  const ages = {
    y1829: r.age_18_29_pct_cvap * rPres.y1829,
    a3044: mid * SPLIT_3044 * rPres.a3044,
    a4564: mid * (1 - SPLIT_3044) * rPres.a4564,
    a65: r.age_65plus_pct_cvap * rPres.a65,
  };
  const ta = Object.values(ages).reduce((s, x) => s + x, 0);
  const Gage = Object.entries(ages).reduce((s, [k, v]) => s + (v / ta) * SHIFT_AGE[k], 0);
  return 0.5 * (Gre + Gage);
}
let gw = 0, gs = 0;
for (const r of nonDistrict) { gw += r.pres2024.total_votes; gs += r.pres2024.total_votes * rawG(r); }
const Gnorm = gs / gw;

// national (turnout-weighted) shares for centring W̃, Ỹ
let wncN = 0, yN = 0;
for (const r of nonDistrict) { wncN += r.pres2024.total_votes * r.white_noncollege_pct_adults25; yN += r.pres2024.total_votes * r.age_18_29_pct_cvap; }
wncN /= gw; yN /= gw;

// ------------------------------------------------------------------ error factors (§5.6, placeholder scales)
const FACTORS = ['NE', 'RUST', 'SOUTH', 'PLAINS_MTN', 'SW', 'PACIFIC', 'WNC', 'BLACK', 'HISP', 'COLLEGE', 'EVANG', 'A65'];
const REGION = {
  NE: 'CT DE DC MA MD ME NH NJ NY RI VT', RUST: 'IL IN IA MI MN OH PA WI',
  SOUTH: 'AL AR FL GA KY LA MS NC SC TN VA WV OK', PLAINS_MTN: 'KS MO NE ND SD MT WY ID UT',
  SW: 'AZ NM NV TX CO', PACIFIC: 'CA OR WA HI AK',
};
const regionOf = {};
for (const [k, v] of Object.entries(REGION)) for (const s of v.split(' ')) regionOf[s] = k;
const demoCol = {
  WNC: 'white_noncollege_pct_adults25', BLACK: 'black_nh_pct_cvap', HISP: 'hispanic_pct_cvap',
  COLLEGE: 'bachelors_plus_pct_cvap', EVANG: 'white_evangelical_pct_adults_prri2025', A65: 'age_65plus_pct_cvap',
};
const zStats = {};
for (const [k, col] of Object.entries(demoCol)) {
  const xs = nonDistrict.map((r) => r[col]);
  const m = xs.reduce((s, x) => s + x, 0) / xs.length;
  const sd = Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1));
  zStats[k] = { m, sd };
}
const REGION_SCALE = 1.5;
const sigmaIdioOf = (ev) => Math.min(3.5, Math.max(1.5, 3.5 - 0.35 * Math.log2(ev / 3)));
function loadings(r, demoScale) {
  return FACTORS.map((f) => {
    if (REGION[f]) return regionOf[r.id] === f ? REGION_SCALE : 0;
    const z = (r[demoCol[f]] - zStats[f].m) / zStats[f].sd;
    return z * demoScale;
  });
}
// pick the demographic scale so the median state-relative SD ≈ 3.5 (target_rel_sd)
function medianSd(scale) {
  const sds = nonDistrict.map((r) => {
    const F = loadings(r, scale);
    const sig = sigmaIdioOf(r.electoral_votes_state_total_2028 ?? r.electoral_votes_2028);
    return Math.sqrt(F.reduce((s, x) => s + x * x, 0) + sig * sig);
  }).sort((a, b) => a - b);
  return sds[Math.floor(sds.length / 2)];
}
let lo = 0, hi = 3;
for (let i = 0; i < 50; i++) { const mid = (lo + hi) / 2; if (medianSd(mid) < 3.5) lo = mid; else hi = mid; }
const DEMO_SCALE = lo;

// ------------------------------------------------------------------ units
const byId = Object.fromEntries(rows.map((r) => [r.id, r]));
const units = rows.map((r) => {
  const isDist = r.type === 'congressional_district';
  const parent = isDist ? r.id.split('-')[0] : null;
  const pv = r.pres2024;
  const m24 = (100 * (pv.dem_votes - pv.rep_votes)) / (pv.dem_votes + pv.rep_votes);
  const m20raw = isDist && r.pres2020_margin_current_lines_rounded != null ? r.pres2020_margin_current_lines_rounded : r.pres2020_margin;
  const m16raw = isDist && r.pres2016_margin_current_lines_rounded != null ? r.pres2016_margin_current_lines_rounded : r.pres2016_margin;
  const m20 = m20raw / TWO_PARTY_2020;
  const m16 = m16raw / TWO_PARTY_2016;
  const src = isDist ? byId[parent] : r;
  const evState = r.electoral_votes_state_total_2028 ?? r.electoral_votes_2028;
  return {
    id: r.id,
    name: r.name,
    type: isDist ? 'district' : r.id === 'DC' ? 'dc' : 'state',
    parent,
    ev: r.electoral_votes_2028,
    m24: r2(m24), m20: r2(m20), m16: r2(m16),
    rel24: r2(m24 - E24), rel20: r2(m20 - M20_US), rel16: r2(m16 - M16_US),
    rel26: 0, // FIXTURE: no 2026 statewide House swing yet
    G: r2(rawG(r) / Gnorm),
    W_tilde: r2((r.white_noncollege_pct_adults25 - wncN) / 10),
    Y_tilde: r2((r.age_18_29_pct_cvap - yN) / 10),
    F: loadings(src, DEMO_SCALE).map((x) => r2(x)),
    sigma_idio: r2(sigmaIdioOf(isDist ? byId[parent].electoral_votes_state_total_2028 : evState)),
    ...(isDist ? { district_sd: 1.5 } : {}),
    shares: {
      wnc: r.white_noncollege_pct_adults25, wc: r.white_college_pct_adults25,
      black: r.black_nh_pct_cvap, hisp: r.hispanic_pct_cvap, asian: r.asian_nh_pct_cvap,
      y1829: r.age_18_29_pct_cvap, a65: r.age_65plus_pct_cvap,
      evang: r.white_evangelical_pct_adults_prri2025 ?? src.white_evangelical_pct_adults_prri2025,
      urban: r.urban_pct_2020_census,
    },
    turnout2024: pv.total_votes,
  };
});

// ------------------------------------------------------------------ placeholder parameter draws
const rng = substream(SEED, 'fixture');
const N = (m, s) => Array.from({ length: P }, () => r2(m + s * rng.normal()));
const ARCH = ['progressive', 'left_populist', 'center_populist', 'mainstream_liberal', 'moderate'];
const COORDS = {
  progressive: { L: 2, P: 0.25 }, left_populist: { L: 2, P: 1 }, center_populist: { L: 0.5, P: 1 },
  mainstream_liberal: { L: 1, P: 0 }, moderate: { L: 0, P: 0 },
};
function preset(spec) {
  const o = {
    fixture: true,
    beta_L: N(spec.bL[0], spec.bL[1]), beta_P: N(spec.bP[0], spec.bP[1]),
    beta_PW: N(0, 0.3), beta_LY: N(0, 0.3),
    u: {}, delta: {},
    omega_maga: N(spec.om[0], spec.om[1]), omega_mod: N(spec.omod[0], spec.omod[1]),
    sd_ratio: { beta_L: spec.ratio, beta_P: spec.ratio },
  };
  for (const a of ARCH) {
    o.u[a] = a === 'mainstream_liberal' ? Array(P).fill(0) : N(0, spec.tau);
    o.delta[a] = o.beta_L.map((b, p) => r2(b * (COORDS[a].L - 1) + o.beta_P[p] * COORDS[a].P + o.u[a][p]));
  }
  return o;
}
const presets = {
  agnostic: preset({ bL: [-0.4, 0.9], bP: [0.3, 1.0], om: [0.8, 1.2], omod: [-0.5, 1.2], tau: 0.4, ratio: 0.45 }),
  literature: preset({ bL: [-1.1, 0.7], bP: [0.2, 0.9], om: [1.0, 1.1], omod: [-0.8, 1.1], tau: 0.4, ratio: 0.4 }),
  discount: preset({ bL: [-0.3, 1.2], bP: [0.2, 1.3], om: [0.6, 1.5], omod: [-0.4, 1.5], tau: 0.5, ratio: 0.6 }),
  data_only: preset({ bL: [-0.45, 1.0], bP: [0.35, 1.1], om: [0.8, 1.3], omod: [-0.5, 1.3], tau: 0.4, ratio: 0 }),
};
const cov = (cols) => {
  const m = cols.map((c) => c.reduce((s, x) => s + x, 0) / c.length);
  return cols.map((a, i) => cols.map((b, j) => r2(a.reduce((s, x, p) => s + (x - m[i]) * (b[p] - m[j]), 0) / (P - 1))));
};
const doCols = ['beta_L', 'beta_P', 'beta_PW', 'beta_LY'].map((k) => presets.data_only[k]);
const gaussian = {
  fixture: true,
  names: ['beta_L', 'beta_P', 'beta_PW', 'beta_LY'],
  bhat: doCols.map((c) => r2(c.reduce((s, x) => s + x, 0) / P)),
  Vhat: cov(doCols),
  mu0: { agnostic: [0, 0, 0, 0], literature: [-1.5, 0, 0, 0] },
  Sigma0: {
    agnostic: [[4, 0, 0, 0], [0, 4, 0, 0], [0, 0, 0.25, 0], [0, 0, 0, 0.25]],
    literature: [[2.25, 0, 0, 0], [0, 2.25, 0, 0], [0, 0, 0.25, 0], [0, 0, 0, 0.25]],
  },
  dial_enabled: true,
};
const pi_draws = Array.from({ length: P }, () => r2(Math.min(2, Math.max(0.5, Math.exp(0.35 * rng.normal())))));

// ------------------------------------------------------------------ candidates
const nameToCode = Object.fromEntries(nonDistrict.map((r) => [r.name.toLowerCase(), r.id]));
const homeCode = (h) => {
  if (!h || /\/|not verified/i.test(String(h))) return null; // ambiguous homes → none
  const first = String(h).split(/[(/]/)[0].trim().toLowerCase();
  return nameToCode[first] ?? null;
};
const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[^\w\s-]/g, '').trim().replace(/[\s.]+/g, '-');
const TAU_C = 2, SIGMA_R = 5;
function track(values) {
  const v = values.filter((x) => typeof x === 'number');
  const n = v.length;
  if (n === 0) return { o_hat: 0, n: 0, w: 0, c_draws: Array(P).fill(0), fixture: true };
  const o = v.reduce((s, x) => s + x, 0) / n;
  const w = TAU_C ** 2 / (TAU_C ** 2 + SIGMA_R ** 2 / n);
  const sd = Math.sqrt((w * SIGMA_R ** 2) / n);
  return { o_hat: r2(o, 2), n, w: r2(w), c_draws: n >= 2 ? N(w * o, sd) : Array(P).fill(0), fixture: true };
}
const L_OF = { conservative: -1, moderate: 0, liberal: 1, left: 2 };
const P_OF = { establishment: 0, mixed: 0.5, populist: 1 };
const demsIn = research('candidates_dem.json').candidates;
const demRank = [...demsIn].sort((a, b) => (b.market_prob?.value ?? 0) - (a.market_prob?.value ?? 0)).map((c) => c.name);
const candidates_dem = demsIn.map((c) => {
  const polls = (c.primary_polling ?? []).map((p) => p.pct).filter((x) => typeof x === 'number');
  return {
    id: slug(c.name),
    name: c.name,
    archetype: c.archetype,
    L: L_OF[c.ideology] ?? 1,
    P: P_OF[c.posture] ?? 0,
    home: homeCode(c.home_state),
    // wave years (2026) excluded: the fixture cannot wave-adjust them (§5.5)
    track: track((c.track_record ?? []).filter((t) => t.year !== 2026).map((t) => t.overperformance)),
    poll_nat_primary: polls.length ? r2(polls.reduce((s, x) => s + x, 0) / polls.length, 2) : 0,
    market_nom: r2((c.market_prob?.value ?? 0) / 100),
    include_default: demRank.indexOf(c.name) < 8,
  };
});
const gopsIn = research('candidates_gop.json').candidates;
const gopRank = [...gopsIn].sort((a, b) => (b.market_prob?.avg ?? 0) - (a.market_prob?.avg ?? 0)).map((c) => c.name);
const candidates_gop = gopsIn.map((c) => ({
  id: slug(c.name),
  name: c.name,
  opp_type: c.style?.startsWith('maga') ? 'maga' : c.style === 'moderate' ? 'moderate' : 'traditional',
  home: homeCode(c.home_state),
  track: track((c.track_record ?? []).map((t) => t.overperformance_vs_baseline_pts)),
  market_nom: r2((c.market_prob?.avg ?? 0) / 100),
  include_default: gopRank.indexOf(c.name) < 5,
}));

// ------------------------------------------------------------------ primary (placeholder coalition model)
const primStates = nonDistrict;
const covCols = [['black', 'black_nh_pct_cvap'], ['white_college', 'white_college_pct_adults25'], ['y1829', 'age_18_29_pct_cvap'], ['urban', 'urban_pct_2020_census']];
const covStats = covCols.map(([, col]) => {
  const xs = primStates.map((r) => r[col]);
  const m = xs.reduce((s, x) => s + x, 0) / xs.length;
  return { m, sd: Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1)) };
});
const TOTAL_PLEDGED = 3936;
const demVotesTot = primStates.reduce((s, r) => s + r.pres2024.dem_votes, 0);
const prStates = primStates.map((r) => {
  const ev = r.electoral_votes_state_total_2028 ?? r.electoral_votes_2028;
  return {
    id: r.id,
    delegates: Math.max(6, Math.round(TOTAL_PLEDGED * (0.5 * ev / 538 + 0.5 * r.pres2024.dem_votes / demVotesTot))),
    X: covCols.map(([, col], q) => r2((r[col] - covStats[q].m) / covStats[q].sd)),
  };
});
// approximate 2024 DNC order (SC first) and a "traditional" Iowa/NH-first order — both FIXTURE
const MID = [['GA', 'MS', 'WA'], ['AZ', 'FL', 'IL', 'KS', 'OH'], ['LA', 'MO'], ['ND'], ['CT', 'DE', 'NY', 'RI', 'WI'],
  ['AK', 'HI', 'WY'], ['PA'], ['IN'], ['MD', 'NE', 'WV'], ['KY', 'OR', 'ID'], ['MT', 'NJ', 'NM', 'SD', 'DC']];
const ST = ['AL', 'AR', 'CA', 'CO', 'IA', 'ME', 'MA', 'MN', 'NC', 'OK', 'TN', 'TX', 'UT', 'VT', 'VA'];
const dnc2024 = [['SC'], ['NH'], ['NV'], ['MI'], ST, ...MID];
const traditional = [['IA'], ['NH'], ['NV'], ['SC'], ST.filter((s) => s !== 'IA').concat('MI'), ...MID];
const dateIdx = Object.fromEntries(dnc2024.flatMap((g, i) => g.map((s) => [s, i])));
prStates.forEach((s) => { s.date_dnc2024 = `fixture-contest-${dateIdx[s.id] + 1}`; });
const primary = {
  fixture: true,
  lanes: ['left', 'mainstream', 'moderate'], populist_term: true,
  covariates: covCols.map(([k]) => k),
  zeta: { left: N(-0.1, 0.3), moderate: N(-0.2, 0.3) },
  eta: {
    left: Array.from({ length: P }, () => [-0.3, 0.1, 0.25, 0.15].map((m) => r2(m + 0.2 * rng.normal()))),
    moderate: Array.from({ length: P }, () => [0.1, -0.1, -0.2, -0.15].map((m) => r2(m + 0.2 * rng.normal()))),
  },
  b_populist: N(0.1, 0.3),
  states: prStates,
  calendars: { dnc2024, traditional },
  settings: {
    poll_weight: 0.3, kappa_sd: 0.7, noise_sd: 0.3, home_logit: 0.8, momentum: 0.5, threshold: 0.15,
    dropout_after: ['4th', 'super_tuesday'], dropout_share: 0.1, lane_affinity_same: 0.6, majority: 0,
  },
  validation: { brier_model: 0, brier_baseline: 0, coalition_enabled: true },
};

// ------------------------------------------------------------------ Sim 5 (placeholder House; real Senate/Gov)
const twoParty = (d, r) => r2((100 * (d - r)) / (d + r), 2);
const raceRows = (file) => (research(file).races ?? [])
  .filter((x) => x.result && typeof x.result.dem_pct === 'number' && typeof x.result.rep_pct === 'number' && !x.uncontested && !x.same_party_general)
  .map((x) => ({ id: x.state, margin: twoParty(x.result.dem_pct, x.result.rep_pct), pct_counted: x.result.pct_expected_vote_counted ?? null }));
const SLOW = new Set(['CA', 'WA', 'OR', 'AZ', 'NV', 'UT']);
const HOUSE26_NAT = 13;
const sim5 = {
  fixture: true,
  units: units.filter((u) => u.type !== 'district').map((u) => {
    const pct = SLOW.has(u.id) ? 85 : 99;
    return {
      id: u.id,
      house26: r2(u.m24 + (HOUSE26_NAT - E24) + 3 * rng.normal(), 2), // FIXTURE
      house26_sd: SLOW.has(u.id) ? 2.5 : 1.0,
      pct_counted: pct,
      imputed_share: 0.05,
      electorate_adj: r2(-4 * (u.G - 1), 3), // FIXTURE
      hatched: pct < 90,
    };
  }),
  national_house26: HOUSE26_NAT,
  durable_phi_default: 1,
  senate: raceRows('senate.json'),
  governor: raceRows('governors.json'),
};

// ------------------------------------------------------------------ assemble
const now = new Date().toISOString();
const model = {
  fixture: true,
  meta: {
    version: 'fixture-2026-11-04', generated_at: now, data_as_of: states.as_of, preliminary: true, fit_level: 0,
    seed: SEED, pipeline_commit: 'fixture', n_param_draws: P, fixture: true,
    notes: [
      'FIXTURE for engine tests only. Unit geography/margins/EVs are real (research/states.json); all style, opponent, pi, primary and Sim 5 House parameters are placeholders.',
      `E24 computed from state two-party totals: ${r2(E24, 3)}.`,
    ],
  },
  national: { E24: r2(E24, 4), ev_total: 538, ev_win: 270 },
  units: units.map(({ turnout2024, ...u }) => u),
  errors: {
    factor_names: FACTORS, idio_df: 5, calibrated: false, target_rel_sd: 3.5, district_sd: 1.5, fixture: true,
    backtest: { cov80_2016: 0, cov80_2020: 0, cov80_2024: 0 },
  },
  environment: {
    default_preset: 'history',
    presets: {
      rerun2024: { type: 'point', value: -1.4 },
      neutral: { type: 'point', value: 0 },
      history: { type: 't', df: 5, loc: 3, scale: 5 },
      regress26: { type: 'normal', mean: 5.3, sd: 5.6 },
      wave_holds: { type: 'point', value: 13, warning: 'larger than any presidential margin since 1984' },
    },
    slider: { min: -10, max: 15, step: 0.5 },
  },
  transfer_pi: {
    default_mode: 'sampled',
    sampled: { type: 'lognormal', mu: 0, sigma: 0.35, clip: [0.5, 2] },
    slider: { min: 0.5, max: 2, step: 0.05 },
    evidence: { statewide_house_ratio: [0, 0, 0], wave_compression: { L: [0, 0, 0], P: [0, 0, 0] }, historical_pres_mid_ratio: null },
    pi_draws,
  },
  turnout_u: { default: 0, min: -1, max: 1, offered_as: 'scenario' },
  lean: { psi: 0.2, psi_calibrated: false, phi: 0, phi_max: 0.5 },
  style: {
    fixture: true,
    coords: Object.fromEntries(ARCH.map((a) => [a, { ...COORDS[a], n: 0, n_states: 0, min_n_ok: true }])),
    hull: [[0, 0], [1, 0], [2, 0.25], [2, 1], [0.5, 1]],
    presets,
    gaussian,
    interactions: { beta_PW: { gate_passed: false, badge: 'prior' }, beta_LY: { gate_passed: false, badge: 'prior' } },
    tilt_default_on: false,
  },
  reveal: {
    fixture: true,
    raw: Object.fromEntries(ARCH.map((a) => [a, { mean: 0, n: 0, dist_m24: [], dist_wnc: [], dist_y1829: [], dist_urban: [] }])),
    adjusted: Object.fromEntries(ARCH.map((a) => [a, { med: 0, lo: 0, hi: 0 }])),
    decomposition: Object.fromEntries(ARCH.map((a) => [a, { lean: 0, demographic: 0, incumbency: 0, opponent: 0, state_wave: 0, style: 0, residual: 0 }])),
    quiz_pairs: [],
    fragility: [],
    maine: { pred_with_delta: [0, 0, 0], pred_delta0: [0, 0, 0], actual: 0, share_incumbency: [0, 0, 0] },
    nyt9: {},
  },
  copy_flags: {
    no_detectable_effect: false, no_predictive_gain: false, lead_with_overlap: false, publish_blocked: false,
    placebo_flag: {}, direction_depends_on_prior: {}, provisional_archetypes: [], maine_explained_by_incumbent: null,
    label_reliability: 'ok',
  },
  candidates_dem,
  candidates_gop,
  home_effect: { mean: 2.0, sd: 1.5, vp: 0.5 },
  rho: { default: 0.5, min: 0, max: 1 },
  track_shrinkage: { tau_c: TAU_C, sigma_r: SIGMA_R, fixture: true },
  primary,
  sim5,
  banners: {
    not_forecast: 'These are scenarios under stated assumptions, not forecasts.',
    preliminary: 'Preliminary: some states are still counting.',
    primary_weak_proxy: '40 House primaries are a weak proxy for a national primary.',
  },
};

writeFileSync(OUT, JSON.stringify(model));
const evD = units.filter((u) => u.m24 > 0).reduce((s, u) => s + u.ev, 0);
const Gs = units.map((u) => u.G);
console.log(`wrote ${OUT}`);
console.log(`units=${units.length} EV=${units.reduce((s, u) => s + u.ev, 0)} HarrisEV=${evD} E24=${E24.toFixed(3)} G∈[${Math.min(...Gs)}, ${Math.max(...Gs)}] demoScale=${DEMO_SCALE.toFixed(3)}`);
