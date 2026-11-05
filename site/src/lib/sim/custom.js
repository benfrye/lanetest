// Sim 4: build-your-own candidate and the "what you'd have to believe" heatmap
// (§1.1 B_a, §6.5 simCustom / believeHeatmap, §6.6 Sim 4).

import { REFERENCE_ARCHETYPE, homeUnits, oppTypeOf } from './model.js';
import { buildBank, resolveEnv, mapPass, envCenterOf, distSorted, pWinDist } from './bank.js';
import {
  styleComponents, deltaComponents, hullDistance, nearestCentroidDistance,
} from './style.js';
import { tVariant, perPWin, summarizeP, mlh, eStar, meanDelta, swingPerDraw } from './core.js';
import { homeSpec, trackDraws } from './matchups.js';
import { homePass } from './bank.js';
import { substream } from './rng.js';
import { countLess, median, mean } from './stats.js';

const EXTRAP_CENTROID_DIST = 0.5;
const EXTRAP_WIDEN = 2;

/** Live-shrunk track record draws for Sim 4 sliders: c_p ~ N(w·o, w·σ_r²/n) (§5.5). */
export function customTrackDraws(model, o, nElections) {
  const { tauC, sigmaR } = model.trackShrink;
  const n = Math.max(1, nElections | 0);
  const w = (tauC * tauC) / (tauC * tauC + (sigmaR * sigmaR) / n);
  const sdC = Math.sqrt((w * sigmaR * sigmaR) / n);
  let z = model._cache.dial.get('custom-track-z');
  if (!z) {
    const r = substream(model.meta.seed ?? 1, 'custom-track');
    z = new Float64Array(model.P);
    for (let p = 0; p < model.P; p++) z[p] = r.normal();
    model._cache.dial.set('custom-track-z', z);
  }
  const c = new Float64Array(model.P);
  for (let p = 0; p < model.P; p++) c[p] = w * o + sdC * z[p];
  return { c, w };
}

function rebank(model, bank, u) {
  if (u == null || u === bank.u) return bank;
  return buildBank(model, { n: bank.n, seed: bank.seed, u, psi: bank.psi, phi: bank.phi, precision: bank.precision, noise: bank.noise });
}

function homeTv(model, bank, hs) {
  if (hs.affected.length === 0) return tVariant(bank);
  bank._home ??= new Map();
  let tv = bank._home.get(hs.key);
  if (!tv) {
    tv = tVariant(bank, homePass(model, bank, hs.affected, hs.shiftsFor), `home:${hs.key}`);
    bank._home.set(hs.key, tv);
  }
  return tv;
}

/**
 * simCustom(model, bank, { L, P, home?, track?:{o,n}, opponent, env, pi, preset|dial, u, rho })
 * `opponent` may be 'generic' | 'maga' | 'traditional' | 'moderate' or a GOP candidate id
 * (then that Republican's home state and track record are used too).
 */
export function simCustom(model, bankIn, opts = {}) {
  const t0 = performance.now();
  const bank = rebank(model, bankIn, opts.u);
  const L = opts.L ?? 1;
  const Pc = opts.P ?? 0;
  const renv = resolveEnv(model, opts.env);
  const sel = opts.dial ? { dial: opts.dial } : { preset: opts.preset ?? model.defaultPreset };
  const rho = opts.rho ?? model.rho;

  // style at (L, P), widened ×2 around its mean when extrapolating
  const comps = styleComponents(model, { ...sel, coords: { L, P: Pc }, pi: opts.pi });
  const hullDist = hullDistance(model, L, Pc);
  const extrapolated = hullDist > 0 || nearestCentroidDistance(model, L, Pc) > EXTRAP_CENTROID_DIST;
  if (extrapolated) {
    const m = mean(comps.delta);
    const d = new Float64Array(model.P);
    for (let p = 0; p < model.P; p++) d[p] = m + EXTRAP_WIDEN * (comps.delta[p] - m);
    comps.delta = d;
  }

  // opponent: type or named Republican
  let oppType = opts.opponent ?? 'generic';
  let gop = null;
  if (model.gops.has(oppType)) {
    gop = model.gops.get(oppType);
    oppType = oppTypeOf(gop);
  }
  const cD = opts.track ? customTrackDraws(model, opts.track.o ?? 0, opts.track.n ?? 1).c : null;
  const cR = gop ? trackDraws(model, gop, true) : null;
  const pers = new Float64Array(model.P);
  for (let p = 0; p < model.P; p++) pers[p] = rho * ((cD ? cD[p] : 0) - (cR ? cR[p] : 0));
  const dc = deltaComponents(model, comps, oppType, pers);

  const hs = homeSpec(model, bank, opts.home ?? null, gop?.home ?? null, true);
  const tv = homeTv(model, bank, hs);
  const pw = perPWin(model, bank, tv, renv, dc);

  // reference: mainstream liberal, same opponent, no Dem home/track
  const refComps = styleComponents(model, { ...sel, archetype: REFERENCE_ARCHETYPE, pi: opts.pi });
  const persR = new Float64Array(model.P);
  for (let p = 0; p < model.P; p++) persR[p] = -rho * (cR ? cR[p] : 0);
  const refDc = deltaComponents(model, refComps, oppType, persR);
  const tvRef = homeTv(model, bank, homeSpec(model, bank, null, gop?.home ?? null, true));
  const pwRef = perPWin(model, bank, tvRef, renv, refDc);

  const { V, V80 } = summarizeP(pw);
  const dVp = new Float64Array(model.P);
  for (let p = 0; p < model.P; p++) dVp[p] = pw[p] - pwRef[p];
  const dMean = meanDelta(model, dc);
  const es = eStar(model, tv, dMean);
  const m = mapPass(model, bank, swingPerDraw(model, bank, renv, dc), hs.affected.length ? hs.fullShift : null);

  const styleArr = new Float64Array(model.P);
  for (let p = 0; p < model.P; p++) styleArr[p] = comps.pi[p] * comps.delta[p];
  const styleMed = median(styleArr);
  const persMed = median(pers);
  const oppMed = median(dMean) - styleMed - persMed;
  const envC = envCenterOf(bank, renv);
  const lean = -(model.E24 + bank.medianT);
  const homeV = bank.medianT - es.medT;
  const waterfall = [
    { label: 'Environment (E)', key: 'env', value: envC },
    { label: 'Electoral College lean', key: 'lean', value: lean },
    { label: 'Style', key: 'style', value: styleMed },
    { label: 'Opponent', key: 'opponent', value: oppMed },
    { label: 'Track record', key: 'track', value: persMed },
    { label: 'Home state', key: 'home', value: homeV },
  ];
  waterfall.push({ label: 'Tipping-point margin', key: 'total', value: waterfall.reduce((s, x) => s + x.value, 0), total: true });

  return {
    V, V80,
    dV: mlh(dVp),
    Estar: es.Estar,
    waterfall,
    stateP: m.stateP,
    extrapolated,
    hullDistance: hullDist,
    ms: performance.now() - t0,
  };
}

// ---------------------------------------------------------------- believe heatmap

const range = (a, b, step) => {
  const out = [];
  for (let x = a; x <= b + 1e-9; x += step) out.push(Math.round(x * 1e6) / 1e6);
  return out;
};
export const DEFAULT_EGRID = range(-6, 12, 0.5);
export const DEFAULT_STYLEGRID = range(-8, 4, 0.5);

function gaussianSmooth(grid, nx, ny, sigma = 1) {
  const r = Math.ceil(3 * sigma);
  const k = [];
  for (let i = -r; i <= r; i++) k.push(Math.exp((-0.5 * i * i) / (sigma * sigma)));
  const tmp = new Float64Array(nx * ny);
  const out = new Float64Array(nx * ny);
  for (let y = 0; y < ny; y++) {
    for (let x = 0; x < nx; x++) {
      let s = 0;
      for (let i = -r; i <= r; i++) {
        const xx = x + i;
        if (xx >= 0 && xx < nx) s += grid[y * nx + xx] * k[i + r];
      }
      tmp[y * nx + x] = s;
    }
  }
  for (let y = 0; y < ny; y++) {
    for (let x = 0; x < nx; x++) {
      let s = 0;
      for (let i = -r; i <= r; i++) {
        const yy = y + i;
        if (yy >= 0 && yy < ny) s += tmp[yy * nx + x] * k[i + r];
      }
      out[y * nx + x] = s;
    }
  }
  return out;
}

/** Marching squares on cell-centre values; returns polylines in data coordinates. */
function marchingSquares(f, nx, ny, level, xAt, yAt) {
  const segs = [];
  const interp = (x1, y1, v1, x2, y2, v2) => {
    const t = v1 === v2 ? 0.5 : (level - v1) / (v2 - v1);
    return [x1 + t * (x2 - x1), y1 + t * (y2 - y1)];
  };
  for (let y = 0; y < ny - 1; y++) {
    for (let x = 0; x < nx - 1; x++) {
      const v0 = f[y * nx + x], v1 = f[y * nx + x + 1], v2 = f[(y + 1) * nx + x + 1], v3 = f[(y + 1) * nx + x];
      const c = (v0 >= level ? 1 : 0) | (v1 >= level ? 2 : 0) | (v2 >= level ? 4 : 0) | (v3 >= level ? 8 : 0);
      if (c === 0 || c === 15) continue;
      const e = {
        b: () => interp(x, y, v0, x + 1, y, v1),
        r: () => interp(x + 1, y, v1, x + 1, y + 1, v2),
        t: () => interp(x, y + 1, v3, x + 1, y + 1, v2),
        l: () => interp(x, y, v0, x, y + 1, v3),
      };
      const table = {
        1: [['l', 'b']], 2: [['b', 'r']], 3: [['l', 'r']], 4: [['r', 't']],
        5: [['l', 'b'], ['r', 't']], 6: [['b', 't']], 7: [['l', 't']], 8: [['t', 'l']],
        9: [['t', 'b']], 10: [['b', 'r'], ['t', 'l']], 11: [['t', 'r']], 12: [['r', 'l']],
        13: [['r', 'b']], 14: [['b', 'l']],
      };
      for (const [p, q] of table[c]) segs.push([e[p](), e[q]()]);
    }
  }
  // join segments into polylines
  const key = (pt) => `${pt[0].toFixed(6)},${pt[1].toFixed(6)}`;
  const adj = new Map();
  segs.forEach((s, i) => {
    for (const pt of s) {
      const k = key(pt);
      if (!adj.has(k)) adj.set(k, []);
      adj.get(k).push(i);
    }
  });
  const used = new Uint8Array(segs.length);
  const lines = [];
  for (let i = 0; i < segs.length; i++) {
    if (used[i]) continue;
    used[i] = 1;
    const line = [segs[i][0], segs[i][1]];
    for (const dir of [1, -1]) {
      for (;;) {
        const end = dir === 1 ? line[line.length - 1] : line[0];
        const next = (adj.get(key(end)) || []).find((j) => !used[j]);
        if (next == null) break;
        used[next] = 1;
        const s = segs[next];
        const other = key(s[0]) === key(end) ? s[1] : s[0];
        if (dir === 1) line.push(other); else line.unshift(other);
      }
    }
    lines.push(line.map(([gx, gy]) => [xAt(gx), yAt(gy)]));
  }
  lines.sort((a, b) => b.length - a.length);
  return lines;
}

/**
 * believeHeatmap(model, bank, { Egrid, styleGrid, archetype, pi, preset|dial, coords?, reader?, env?, curve? })
 * pWin is laid out E-major: pWin[iE * styleGrid.length + iS] = P(D ≥ 270 | E, national style shift x).
 * The style axis is the total national style effect x = π·δ (traditional opponent, no home/track).
 */
export function believeHeatmap(model, bank, opts = {}) {
  const t0 = performance.now();
  const Egrid = opts.Egrid ?? DEFAULT_EGRID;
  const styleGrid = opts.styleGrid ?? DEFAULT_STYLEGRID;
  const nE = Egrid.length, nS = styleGrid.length;
  const t = bank.t;
  const n = t.length;
  const pWin = new Float32Array(nE * nS);
  for (let i = 0; i < nE; i++) {
    const x0 = Egrid[i] - model.E24;
    for (let k = 0; k < nS; k++) pWin[i * nS + k] = countLess(t, x0 + styleGrid[k]) / n;
  }

  // posterior draws of π·δ_a (or at custom coords)
  const sel = opts.dial ? { dial: opts.dial } : { preset: opts.preset ?? model.defaultPreset };
  const archetype = opts.archetype ?? REFERENCE_ARCHETYPE;
  const comps = styleComponents(model, { ...sel, ...(opts.coords ? { coords: opts.coords } : { archetype }), pi: opts.pi });
  const P = model.P;
  const sx = new Float64Array(P);
  for (let p = 0; p < P; p++) sx[p] = comps.pi[p] * comps.delta[p];

  // contours: 40×40 histogram of (E prior draw, π_p·δ_a,p), Gaussian-smoothed, HDR levels
  const NB = 40;
  const ePreset = model.env.presets[model.env.default_preset].type === 'point' ? null : model.env.default_preset;
  const contours = { p50: [], p90: [], p50All: [], p90All: [] };
  if (ePreset) {
    const Ed = bank.Edraws[ePreset];
    // histogram window: the heatmap window widened to cover the central 99% of the draws,
    // so the 90% region is not cut off by the grid (the UI clips lines to the heatmap)
    const qs = (arr) => { const s = Float64Array.from(arr).sort(); return [s[Math.floor(0.005 * s.length)], s[Math.floor(0.995 * s.length)]]; };
    const [eq0, eq1] = qs(Ed);
    const [sq0, sq1] = qs(sx);
    const x0 = Math.min(Egrid[0], eq0), x1 = Math.max(Egrid[nE - 1], eq1);
    const y0 = Math.min(styleGrid[0], sq0), y1 = Math.max(styleGrid[nS - 1], sq1);
    const hx = (x1 - x0) / NB, hy = (y1 - y0) / NB;
    const hist = new Float64Array(NB * NB);
    for (let j = 0; j < bank.n; j++) {
      const ix = Math.floor((Ed[j] - x0) / hx);
      const iy = Math.floor((sx[j % P] - y0) / hy);
      if (ix >= 0 && ix < NB && iy >= 0 && iy < NB) hist[iy * NB + ix] += 1;
    }
    const sm = gaussianSmooth(hist, NB, NB, 1);
    // total mass includes draws outside the window so the HDR levels are honest
    let inWin = 0;
    for (let i = 0; i < sm.length; i++) inWin += sm[i];
    const total = bank.n * (inWin / Math.max(1e-12, hist.reduce((s, v) => s + v, 0)));
    const sorted = Float64Array.from(sm).sort().reverse();
    const levelFor = (q) => {
      let c = 0;
      for (let i = 0; i < sorted.length; i++) {
        c += sorted[i];
        if (c >= q * total) return sorted[i];
      }
      return sorted[sorted.length - 1];
    };
    const xAt = (g) => x0 + (g + 0.5) * hx;
    const yAt = (g) => y0 + (g + 0.5) * hy;
    contours.p50All = marchingSquares(sm, NB, NB, levelFor(0.5), xAt, yAt);
    contours.p90All = marchingSquares(sm, NB, NB, levelFor(0.9), xAt, yAt);
    contours.p50 = contours.p50All[0] ?? [];
    contours.p90 = contours.p90All[0] ?? [];
  }

  const renvDefault = resolveEnv(model, opts.env ?? { mode: 'dist', preset: model.env.default_preset });
  const reader = {
    x: opts.reader?.x ?? envCenterOf(bank, renvDefault),
    y: opts.reader?.y ?? median(sx),
  };

  // B_a: the smallest cost x* < 0 with V(x*) − V(0) ≤ −10 points at the default E (§1.1)
  const Vx = (x) => renvDefault.mode === 'point'
    ? countLess(t, renvDefault.E - model.E24 + x) / n
    : pWinDist(distSorted(model, bank, renvDefault.preset), x);
  const V0 = Vx(0);
  let threshold = null;
  if (Vx(-40) <= V0 - 0.1) {
    let lo = -40, hi = 0; // V(lo) ≤ target < V(hi)
    for (let it = 0; it < 60; it++) {
      const mid = 0.5 * (lo + hi);
      if (Vx(mid) <= V0 - 0.1) lo = mid; else hi = mid;
    }
    threshold = lo;
  }
  let cnt = 0;
  if (threshold != null) for (let p = 0; p < P; p++) if (sx[p] <= threshold) cnt++;

  // opts.curve: the same V(x) the threshold uses (default environment, averaged over its
  // uncertainty) at every styleGrid point, plus quantiles of the π·δ draws, for a one-line
  // "chance vs. cost" chart that agrees with B by construction.
  let curve = null;
  if (opts.curve) {
    const sorted = Float64Array.from(sx).sort();
    const q = (f) => sorted[Math.min(P - 1, Math.floor(f * (P - 1)))];
    curve = { V: Float32Array.from(styleGrid, (x) => Vx(x)), quantiles: { q10: q(0.1), q50: q(0.5), q90: q(0.9) } };
  }

  return {
    Egrid: Egrid.slice(),
    styleGrid: styleGrid.slice(),
    layout: 'E-major',
    pWin,
    contours,
    reader,
    B: { threshold, cost: threshold == null ? null : -threshold, posteriorProb: threshold == null ? 0 : cnt / P, V0 },
    curve,
    ms: performance.now() - t0,
  };
}

export { homeUnits };
