// Shared evaluation helpers on top of the bank: per-parameter-draw win probabilities,
// curves, E*, and the per-draw national swing for map passes.

import { EcdfIndex, sortIntKeys } from './stats.js';
import { distSorted, pWinDist, envDraw } from './bank.js';
import { quantileSorted, sortedCopy, mean } from './stats.js';

export const CURVE_E = Array.from({ length: 31 }, (_, i) => i - 10); // −10..20

/** A threshold variant: the bank itself or a home/tilt re-accumulation. */
export function tVariant(bank, pass = null, tag = 'base') {
  if (!pass) {
    bank._index ??= new EcdfIndex(bank.t);
    return { tRaw: bank.tRaw, tSorted: bank.t, tip: bank.tip, tag: 'base', index: bank._index };
  }
  const tSorted = Float64Array.from(pass.tRaw).sort();
  return { tRaw: pass.tRaw, tSorted, tip: pass.tip, tag, index: new EcdfIndex(tSorted) };
}

/**
 * P(win | p) for each parameter draw, mixing opponent components exactly.
 * Point E: F_t(E − E24 + Δ_p). Distribution E: 1 − F_D(−Δ_p).
 */
export function perPWin(model, bank, tv, renv, comps) {
  const P = model.P;
  const out = new Float64Array(P);
  if (renv.mode === 'point') {
    const x0 = renv.E - model.E24;
    const n = tv.tSorted.length;
    const ix = tv.index;
    for (const c of comps) {
      const D = c.Delta;
      for (let p = 0; p < P; p++) out[p] += c.weight * (ix.countLess(x0 + D[p]) / n);
    }
  } else {
    const Ds = distSorted(model, bank, renv.preset, tv.tRaw, tv.tag);
    for (const c of comps) {
      const D = c.Delta;
      for (let p = 0; p < P; p++) out[p] += c.weight * pWinDist(Ds, D[p]);
    }
  }
  return out;
}

/** Weighted mean Δ_p across opponent components (used for E* and decompositions). */
export function meanDelta(model, comps) {
  const d = new Float64Array(model.P);
  for (const c of comps) for (let p = 0; p < model.P; p++) d[p] += c.weight * c.Delta[p];
  return d;
}

/** Summaries of a per-p probability array. */
export function summarizeP(pw) {
  const s = sortedCopy(pw);
  return { V: mean(pw), V80: [quantileSorted(s, 0.1), quantileSorted(s, 0.9)], sorted: s };
}

/** [med, lo, hi] with lo/hi the 10th/90th percentiles. */
export function mlh(arr) {
  const s = sortedCopy(arr);
  return [quantileSorted(s, 0.5), quantileSorted(s, 0.1), quantileSorted(s, 0.9)];
}

/** E*_p = E24 + median(t) − Δ_p (§6.2), summarized as integers [med, lo, hi]. */
export function eStar(model, tv, dMean) {
  const n = tv.tSorted.length;
  const medT = 0.5 * (tv.tSorted[(n - 1) >> 1] + tv.tSorted[n >> 1]);
  const e = new Float64Array(model.P);
  for (let p = 0; p < model.P; p++) e[p] = model.E24 + medT - dMean[p];
  const [m, lo, hi] = mlh(e);
  const ri = (x) => Math.round(x) + 0; // + 0 turns −0 into 0
  return { Estar: [ri(m), ri(lo), ri(hi)], EstarExact: [m, lo, hi], medT, draws: e };
}

/**
 * Point-mode win curves over Egrid: per E, med/lo/hi (10–90%) and mean over p.
 * Equal-weight opponent components (the usual case) are evaluated on integer ECDF counts
 * with a radix sort for the quantiles; the result is identical to the float path.
 */
export function curves(model, tv, comps, Egrid = CURVE_E) {
  const P = model.P;
  const n = tv.tSorted.length;
  const ix = tv.index;
  const med = [], lo = [], hi = [], mn = [];
  const nc = comps.length;
  const equal = comps.every((c) => Math.abs(c.weight - 1 / nc) < 1e-12) && nc * n < 65536;
  const keys = new Int32Array(P);
  const tmp = new Int32Array(P);
  const buf = new Float64Array(P);
  for (const E of Egrid) {
    const x0 = E - model.E24;
    let s;
    let total = 0;
    if (equal) {
      keys.fill(0);
      for (const c of comps) {
        const D = c.Delta;
        for (let p = 0; p < P; p++) keys[p] += ix.countLess(x0 + D[p]);
      }
      for (let p = 0; p < P; p++) total += keys[p];
      sortIntKeys(keys, tmp);
      const scale = 1 / (nc * n);
      s = { length: P, at: (i) => keys[i] * scale };
      total *= scale;
    } else {
      buf.fill(0);
      for (const c of comps) {
        const D = c.Delta;
        for (let p = 0; p < P; p++) buf[p] += c.weight * (ix.countLess(x0 + D[p]) / n);
      }
      for (let p = 0; p < P; p++) total += buf[p];
      const sorted = sortedCopy(buf);
      s = { length: P, at: (i) => sorted[i] };
    }
    const q = (pq) => {
      const h = (P - 1) * pq;
      const a = Math.floor(h);
      const b = Math.min(P - 1, a + 1);
      return s.at(a) + (h - a) * (s.at(b) - s.at(a));
    };
    med.push(q(0.5));
    lo.push(q(0.1));
    hi.push(q(0.9));
    mn.push(total / P);
  }
  return { med, lo, hi, mean: mn };
}

/**
 * National swing per outcome draw, S_j = E_j − E24 + Δ_{p(j)}, p(j) = j mod P.
 * The generic-opponent mixture uses the bank's per-draw Bernoulli(0.5).
 */
export function swingPerDraw(model, bank, renv, comps) {
  const n = bank.n;
  const S = new Float64Array(n);
  const P = model.P;
  const generic = comps.length === 2;
  for (let j = 0; j < n; j++) {
    const p = j % P;
    const c = generic ? comps[bank.oppMaga[j] ? 1 : 0] : comps[0];
    S[j] = envDraw(bank, renv, j) - model.E24 + c.Delta[p];
  }
  return S;
}
