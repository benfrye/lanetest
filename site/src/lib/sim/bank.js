// OutcomeBank: the break-even swing bank (METHODOLOGY §6.2).
//
// Per outcome draw j and unit s:
//   a_s,j  = m24_s + ψ·rel26_s + φ·(rel24_s − rel20_s) + ε_s,j
//   k_s    = 1 + u·(G_s − 1)                (districts use the parent state's k)
//   θ_s,j  = −a_s,j / k_s                   unit goes D when the national swing S > θ_s,j
//   t_j    = the S at which cumulative EV (thresholds ascending) first reaches ev_win
// so P(win | S) = #(t_j < S)/n is an empirical CDF lookup.

import { substream } from './rng.js';
import { countLess, countLessEq } from './stats.js';

export const DEFAULT_N = 10000;
const MAX_BANKS = 6; // LRU bound per model (each 10k bank is ~5 MB plus caches)
const MAX_DRAW_SETS = 2;

function lruGet(map, key) {
  const v = map.get(key);
  if (v !== undefined) { map.delete(key); map.set(key, v); }
  return v;
}
function lruSet(map, key, v, max) {
  map.set(key, v);
  while (map.size > max) map.delete(map.keys().next().value);
}
// §5.1: M_district = M_state + (lean_d − lean_s) + N(0, district_sd²), district_sd default 1.5

function floatArray(precision, n) {
  return precision === 'f64' ? new Float64Array(n) : new Float32Array(n);
}

/**
 * Outcome-error draws, E draws, generic-opponent uniforms and home-effect normals.
 * These depend only on (seed, n, noise), never on u/ψ/φ, so every bank built from the
 * same seed shares them (common random numbers across scenarios).
 */
function getDraws(model, n, seed, noise, precision) {
  const key = `${seed}|${n}|${noise}|${precision}`;
  const hit = lruGet(model._cache.eps, key);
  if (hit) return hit;
  const { U, K, F, sigmaIdio, parentIdx, districtSd } = model;
  const eps = floatArray(precision, n * U);
  if (noise) {
    const rng = substream(seed, 'errors');
    const f = new Float64Array(K);
    const row = new Float64Array(U);
    for (let j = 0; j < n; j++) {
      for (let k = 0; k < K; k++) f[k] = rng.normal();
      for (let s = 0; s < U; s++) {
        if (parentIdx[s] >= 0) continue;
        let e = 0;
        const off = s * K;
        for (let k = 0; k < K; k++) e += F[off + k] * f[k];
        row[s] = e + sigmaIdio[s] * rng.t5Unit();
      }
      for (let s = 0; s < U; s++) {
        if (parentIdx[s] >= 0) row[s] = row[parentIdx[s]] + districtSd[s] * rng.normal();
      }
      eps.set(row, j * U);
    }
  }

  // E draws for every non-point environment preset; one sub-stream per preset name.
  const Edraws = {};
  for (const [name, spec] of Object.entries(model.env.presets)) {
    if (spec.type === 'point') continue;
    const r = substream(seed, `env:${name}`);
    const arr = floatArray(precision, n);
    for (let j = 0; j < n; j++) {
      arr[j] = spec.type === 't' ? spec.loc + spec.scale * r.studentT(spec.df) : spec.mean + spec.sd * r.normal();
    }
    Edraws[name] = arr;
  }

  const ro = substream(seed, 'generic-opponent');
  const oppMaga = new Uint8Array(n);
  for (let j = 0; j < n; j++) oppMaga[j] = ro.uniform() < 0.5 ? 1 : 0;

  const rh = substream(seed, 'home');
  const homeZD = floatArray(precision, n);
  const homeZR = floatArray(precision, n);
  for (let j = 0; j < n; j++) {
    homeZD[j] = rh.normal();
    homeZR[j] = rh.normal();
  }

  const out = { eps, Edraws, oppMaga, homeZD, homeZR };
  lruSet(model._cache.eps, key, out, MAX_DRAW_SETS);
  return out;
}

/**
 * Accumulate EV along thresholds sorted ascending (keys[0..m-1], unit idx[0..m-1]).
 * Writes t, tip unit and tie width into `out`.
 */
function accumulate(keys, idx, m, ev, evWin, tieEV, out) {
  let cum = 0;
  let prev = -Infinity;
  for (let i = 0; i < m; i++) {
    const before = cum;
    cum += ev[idx[i]];
    if (cum >= evWin) {
      out.t = keys[i];
      out.tip = idx[i];
      out.tieWidth = before === tieEV ? keys[i] - prev : 0;
      return;
    }
    prev = keys[i];
  }
  out.t = Infinity;
  out.tip = 255;
  out.tieWidth = 0;
}

/** In-place insertion sort of keys with a parallel index array (m ≤ ~60). */
function insertionSort(keys, idx, m) {
  for (let i = 1; i < m; i++) {
    const kv = keys[i];
    const iv = idx[i];
    let j = i - 1;
    while (j >= 0 && keys[j] > kv) {
      keys[j + 1] = keys[j];
      idx[j + 1] = idx[j];
      j--;
    }
    keys[j + 1] = kv;
    idx[j + 1] = iv;
  }
}

/**
 * Build (or fetch from cache) the outcome bank.
 * @param {object} model from loadModel
 * @param {{n?:number, seed?:number, u?:number, psi?:number, phi?:number,
 *          precision?:'f32'|'f64', noise?:boolean}} opts
 *   noise:false zeroes ε (identity / V1 test mode).
 */
export function buildBank(model, opts = {}) {
  const n = opts.n ?? DEFAULT_N;
  const seed = (opts.seed ?? model.meta.seed ?? 1) >>> 0;
  const u = opts.u ?? 0;
  const psi = opts.psi ?? model.lean.psi;
  const phi = opts.phi ?? model.lean.phi;
  const precision = opts.precision ?? model.precision;
  const noise = opts.noise !== false;
  if (!(u >= -1 && u <= 1)) throw new RangeError(`u must be in [-1, 1], got ${u}`);
  const { U, ev, evWin, evTotal, m24, rel24, rel20, rel26, G, parentIdx } = model;
  const key = `${seed}|${u}|${psi}|${phi}|${U}|${n}|${precision}|${noise}`;
  const cached = lruGet(model._cache.banks, key);
  if (cached) return cached;

  const t0 = performance.now();
  const draws = getDraws(model, n, seed, noise, precision);

  const k = new Float64Array(U);
  const lean = new Float64Array(U);
  for (let s = 0; s < U; s++) {
    const g = parentIdx[s] >= 0 ? G[parentIdx[s]] : G[s];
    k[s] = 1 + u * (g - 1);
    if (!(k[s] > 0)) throw new Error(`k_s <= 0 for unit ${model.ids[s]} (G=${g}, u=${u})`);
    lean[s] = m24[s] + psi * rel26[s] + phi * (rel24[s] - rel20[s]);
  }

  const a = floatArray(precision, n * U);
  const theta = floatArray(precision, n * U);
  const order = new Uint8Array(n * U);
  const tRaw = floatArray(precision, n);
  const tip = new Uint8Array(n);
  const tieWidth = floatArray(precision, n);
  const tieEV = evTotal % 2 === 0 && evWin - 1 === evTotal / 2 ? evTotal / 2 : -1;
  const keys = new Float64Array(U);
  const idx = new Uint8Array(U);
  const res = { t: 0, tip: 0, tieWidth: 0 };
  const eps = draws.eps;
  const tipCount = new Float64Array(U);

  for (let j = 0; j < n; j++) {
    const base = j * U;
    for (let s = 0; s < U; s++) {
      const av = lean[s] + eps[base + s];
      a[base + s] = av;
      const th = -av / k[s];
      theta[base + s] = th;
      keys[s] = theta[base + s]; // read back so sorting matches stored precision
      idx[s] = s;
    }
    insertionSort(keys, idx, U);
    order.set(idx, base);
    accumulate(keys, idx, U, ev, evWin, tieEV, res);
    tRaw[j] = res.t;
    tip[j] = res.tip;
    tieWidth[j] = res.tieWidth;
    tipCount[res.tip] += 1;
  }

  const t = Float64Array.from(tRaw).sort();
  const tipping = {};
  for (let s = 0; s < U; s++) if (tipCount[s] > 0) tipping[model.ids[s]] = tipCount[s] / n;

  const bank = {
    n, U, seed, u, psi, phi, precision, noise,
    k, lean, a, theta, order,
    tRaw,
    t, // sorted (Float64 for exact binary search)
    tip, tieWidth,
    tieEV,
    medianT: t[(n - 1) >> 1] * 0.5 + t[n >> 1] * 0.5,
    tipping,
    Edraws: draws.Edraws,
    oppMaga: draws.oppMaga,
    homeZD: draws.homeZD,
    homeZR: draws.homeZR,
    _dist: new Map(),
    buildMs: performance.now() - t0,
  };
  lruSet(model._cache.banks, key, bank, MAX_BANKS);
  return bank;
}

/** P(win | point S) = #(t_j < S)/n for a sorted t array. */
export function pWinPoint(tSorted, S) {
  return countLess(tSorted, S) / tSorted.length;
}

/** Sorted D_j = E_j − E24 − t_j for a distribution preset (cached per t variant). */
export function distSorted(model, bank, preset, tRaw = bank.tRaw, tag = 'base') {
  const key = `${preset}|${tag}`;
  let d = bank._dist.get(key);
  if (d) return d;
  const E = bank.Edraws[preset];
  if (!E) throw new Error(`no E draws for preset "${preset}" (point presets use mode:'point')`);
  d = new Float64Array(bank.n);
  for (let j = 0; j < bank.n; j++) d[j] = E[j] - model.E24 - tRaw[j];
  d.sort();
  bank._dist.set(key, d);
  return d;
}

/** P(win | Δ) in distribution mode: 1 − F_D(−Δ). */
export function pWinDist(dSorted, delta) {
  return 1 - countLessEq(dSorted, -delta) / dSorted.length;
}

/**
 * Resolve an env option into either {mode:'point', E} or {mode:'dist', preset}.
 * Accepts {mode:'point', value} | {mode:'point', preset} | {mode:'dist', preset?}.
 */
export function resolveEnv(model, env = {}) {
  const presets = model.env.presets;
  if (env.mode === 'point' || (env.mode == null && env.value != null)) {
    if (env.value != null) return { mode: 'point', E: env.value };
    const spec = presets[env.preset];
    if (!spec) throw new Error(`unknown environment preset ${env.preset}`);
    if (spec.type === 'point') return { mode: 'point', E: spec.value, preset: env.preset };
    return { mode: 'point', E: spec.type === 't' ? spec.loc : spec.mean, preset: env.preset };
  }
  const name = env.preset ?? model.env.default_preset;
  const spec = presets[name];
  if (!spec) throw new Error(`unknown environment preset ${name}`);
  if (spec.type === 'point') return { mode: 'point', E: spec.value, preset: name };
  return { mode: 'dist', preset: name };
}

/** E for outcome draw j under a resolved env. */
export function envDraw(bank, renv, j) {
  return renv.mode === 'point' ? renv.E : bank.Edraws[renv.preset][j];
}

/** Center of a resolved env (point value or sample mean of the E draws). */
export function envCenterOf(bank, renv) {
  if (renv.mode === 'point') return renv.E;
  const E = bank.Edraws[renv.preset];
  let s = 0;
  for (let j = 0; j < E.length; j++) s += E[j];
  return s / E.length;
}

/**
 * Re-accumulate thresholds with per-draw shifts on a few units (home effects, §6.2).
 * shiftsFor(j, out) fills out[q] = margin shift (D-positive points) for affected[q].
 * Returns { tRaw, tip } for the modified bank. O(U) per draw via a merge with the
 * bank's stored sort order.
 */
export function homePass(model, bank, affected, shiftsFor) {
  const { n, U, theta, order, k } = bank;
  const { ev, evWin } = model;
  const m = affected.length;
  const tRaw = new Float64Array(n);
  const tip = new Uint8Array(n);
  const tieWidth = new Float64Array(n);
  if (m === 0) {
    tRaw.set(bank.tRaw);
    tip.set(bank.tip);
    tieWidth.set(bank.tieWidth);
    return { tRaw, tip, tieWidth };
  }
  const isAff = new Uint8Array(U);
  for (const s of affected) isAff[s] = 1;
  const shift = new Float64Array(m);
  const nk = new Float64Array(m);
  const ni = new Uint8Array(m);
  const tieEV = bank.tieEV;
  for (let j = 0; j < n; j++) {
    const base = j * U;
    shiftsFor(j, shift);
    for (let q = 0; q < m; q++) {
      const s = affected[q];
      nk[q] = theta[base + s] - shift[q] / k[s];
      ni[q] = s;
    }
    insertionSort(nk, ni, m);
    let cum = 0, prev = -Infinity, qi = 0, done = false;
    let tj = Infinity, tipj = 255, tw = 0;
    for (let pos = 0; pos <= U && !done; pos++) {
      let th, s;
      if (pos < U) {
        s = order[base + pos];
        if (isAff[s]) continue;
        th = theta[base + s];
      } else {
        th = Infinity;
        s = -1;
      }
      while (qi < m && nk[qi] <= th) {
        const before = cum;
        cum += ev[ni[qi]];
        if (cum >= evWin) {
          tj = nk[qi]; tipj = ni[qi]; tw = before === tieEV ? nk[qi] - prev : 0;
          done = true;
          break;
        }
        prev = nk[qi];
        qi++;
      }
      if (done || s < 0) break;
      const before = cum;
      cum += ev[s];
      if (cum >= evWin) {
        tj = th; tipj = s; tw = before === tieEV ? th - prev : 0;
        done = true;
        break;
      }
      prev = th;
    }
    tRaw[j] = tj;
    tip[j] = tipj;
    tieWidth[j] = tw;
  }
  return { tRaw, tip, tieWidth };
}

/**
 * Full re-sort pass with per-draw margin shifts on every unit (tilt mode, §6.2).
 * shiftFor(j, out) fills out[s] = margin shift for every unit s.
 */
export function fullPass(model, bank, shiftFor) {
  const { n, U, theta, k } = bank;
  const { ev, evWin } = model;
  const tRaw = new Float64Array(n);
  const tip = new Uint8Array(n);
  const tieWidth = new Float64Array(n);
  const keys = new Float64Array(U);
  const idx = new Uint8Array(U);
  const sh = new Float64Array(U);
  const res = { t: 0, tip: 0, tieWidth: 0 };
  for (let j = 0; j < n; j++) {
    const base = j * U;
    shiftFor(j, sh);
    for (let s = 0; s < U; s++) {
      keys[s] = theta[base + s] - sh[s] / k[s];
      idx[s] = s;
    }
    insertionSort(keys, idx, U);
    accumulate(keys, idx, U, ev, evWin, bank.tieEV, res);
    tRaw[j] = res.t;
    tip[j] = res.tip;
    tieWidth[j] = res.tieWidth;
  }
  return { tRaw, tip, tieWidth };
}

/**
 * Map pass: per-draw national swing S_j (+ optional per-unit margin shifts) →
 * state P(D), mean margin, EV histogram, P(269 tie), tipping frequencies.
 * @param {Float64Array} S national swing per draw
 * @param {(j:number, out:Float64Array)=>void} [shiftFor] per-unit margin shifts
 */
export function mapPass(model, bank, S, shiftFor) {
  const { n, U, a, k } = bank;
  const { ev, evTotal } = model;
  const winCount = new Float64Array(U);
  const marginSum = new Float64Array(U);
  const evHist = new Int32Array(evTotal + 1);
  const sh = new Float64Array(U);
  for (let j = 0; j < n; j++) {
    const base = j * U;
    const Sj = S[j];
    if (shiftFor) shiftFor(j, sh);
    let evD = 0;
    for (let s = 0; s < U; s++) {
      const M = a[base + s] + k[s] * Sj + (shiftFor ? sh[s] : 0);
      marginSum[s] += M;
      if (M > 0) {
        winCount[s] += 1;
        evD += ev[s];
      }
    }
    evHist[evD] += 1;
  }
  const stateP = {};
  const stateMeanMargin = {};
  for (let s = 0; s < U; s++) {
    stateP[model.ids[s]] = winCount[s] / n;
    stateMeanMargin[model.ids[s]] = marginSum[s] / n;
  }
  const pTie = evTotal % 2 === 0 ? evHist[evTotal / 2] / n : 0;
  return { stateP, stateMeanMargin, evHist, pTie };
}

/** Tipping-unit frequencies from a tip array. */
export function tippingFreq(model, tip) {
  const c = new Float64Array(model.U);
  for (let j = 0; j < tip.length; j++) if (tip[j] < model.U) c[tip[j]] += 1;
  const out = {};
  for (let s = 0; s < model.U; s++) if (c[s] > 0) out[model.ids[s]] = c[s] / tip.length;
  return out;
}
