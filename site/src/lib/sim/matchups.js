// Sim 2: named-matchup matrix and single-pairing detail (§5.5, §6.2, §6.5, §6.6).

import { REFERENCE_ARCHETYPE, homeUnits, oppTypeOf } from './model.js';
import { resolveEnv, homePass, mapPass, envCenterOf, envDraw, tippingFreq } from './bank.js';
import { styleComponents, omegaFor } from './style.js';
import { tVariant, perPWin, summarizeP, mlh, eStar, curves, swingPerDraw, CURVE_E } from './core.js';
import { median, bin5, sd, sortedCopy, quantileSorted } from './stats.js';

/** Track-record draws c_p (zero when off, missing, or fewer than 2 elections, §3.8). */
export function trackDraws(model, cand, on = true) {
  const tr = cand?.track;
  if (!on || !tr || !tr.c_draws?.length || (tr.n ?? 0) < 2) return null;
  return Float64Array.from(tr.c_draws);
}

/** Affected units and per-draw margin shifts for a (Dem home, GOP home) pair. */
export function homeSpec(model, bank, homeD, homeR, on = true) {
  const affected = [];
  const sD = [];
  const sR = [];
  if (on) {
    const add = (code, which) => {
      for (const s of homeUnits(model, code)) {
        let q = affected.indexOf(s);
        if (q < 0) { q = affected.length; affected.push(s); sD.push(0); sR.push(0); }
        if (which === 'D') sD[q] = 1; else sR[q] = 1;
      }
    };
    add(homeD, 'D');
    add(homeR, 'R');
  }
  const { mean: hm, sd: hs } = model.homeEffect;
  const zD = bank.homeZD, zR = bank.homeZR;
  const m = affected.length;
  const shiftsFor = (j, out) => {
    const HD = hm + hs * zD[j];
    const HR = hm + hs * zR[j];
    for (let q = 0; q < m; q++) out[q] = sD[q] * HD - sR[q] * HR;
  };
  // full-U variant for map passes
  const fullShift = (j, out) => {
    out.fill(0);
    const HD = hm + hs * zD[j];
    const HR = hm + hs * zR[j];
    for (let q = 0; q < m; q++) out[affected[q]] = sD[q] * HD - sR[q] * HR;
  };
  return { affected, shiftsFor, fullShift, key: on ? `${homeD ?? '-'}|${homeR ?? '-'}|${hm}|${hs}` : 'off' };
}

/** Cached threshold variant for a home pair. */
function homeVariant(model, bank, hs) {
  if (hs.affected.length === 0) return tVariant(bank);
  bank._home ??= new Map();
  let tv = bank._home.get(hs.key);
  if (!tv) {
    tv = tVariant(bank, homePass(model, bank, hs.affected, hs.shiftsFor), `home:${hs.key}`);
    bank._home.set(hs.key, tv);
  }
  return tv;
}

function getDem(model, id) {
  const c = model.dems.get(id);
  if (!c) throw new Error(`unknown Democratic candidate "${id}"`);
  return c;
}
function getGop(model, id) {
  const c = model.gops.get(id);
  if (!c) throw new Error(`unknown Republican candidate "${id}"`);
  return c;
}

/** Δ_p = π_p(δ_a,p + ω_g,p) + ρ(c_D,p − c_R,p), plus its parts. */
function pairDelta(model, dem, gop, opts) {
  const sel = opts.dial ? { dial: opts.dial } : { preset: opts.preset ?? model.defaultPreset };
  const comps = styleComponents(model, { ...sel, archetype: dem.archetype, pi: opts.pi });
  const rho = opts.rho ?? model.rho;
  const cD = trackDraws(model, dem, opts.track !== false);
  const cR = trackDraws(model, gop, opts.track !== false);
  const om = omegaFor(comps.draws, oppTypeOf(gop));
  const P = model.P;
  const Delta = new Float64Array(P);
  const style = new Float64Array(P);
  const opp = new Float64Array(P);
  const pers = new Float64Array(P);
  for (let p = 0; p < P; p++) {
    style[p] = comps.pi[p] * comps.delta[p];
    opp[p] = om ? comps.pi[p] * om[p] : 0;
    pers[p] = rho * ((cD ? cD[p] : 0) - (cR ? cR[p] : 0));
    Delta[p] = style[p] + opp[p] + pers[p];
  }
  return { Delta, style, opp, pers };
}

/**
 * simMatchups(model, bank, { dems, gops, env, pi, preset|dial, rho, home=true, track=true, onProgress })
 * Cells are row-major: dems are rows, gops are columns.
 */
export function simMatchups(model, bank, opts = {}) {
  const t0 = performance.now();
  const demIds = opts.dems ?? [...model.dems.values()].filter((c) => c.include_default !== false).map((c) => c.id);
  const gopIds = opts.gops ?? [...model.gops.values()].filter((c) => c.include_default !== false).map((c) => c.id);
  const renv = resolveEnv(model, opts.env);
  const envC = envCenterOf(bank, renv);
  const homeOn = opts.home !== false;
  const base = tVariant(bank);
  const leanBase = -(model.E24 + bank.medianT);

  const cells = [];
  const pws = [];
  for (let i = 0; i < demIds.length; i++) {
    const dem = getDem(model, demIds[i]);
    for (let k = 0; k < gopIds.length; k++) {
      const gop = getGop(model, gopIds[k]);
      const pd = pairDelta(model, dem, gop, opts);
      const hs = homeSpec(model, bank, dem.home, gop.home, homeOn);
      const tv = homeVariant(model, bank, hs);
      const comps = [{ weight: 1, Delta: pd.Delta }];
      const pw = perPWin(model, bank, tv, renv, comps);
      const { V, V80 } = summarizeP(pw);
      // median national two-party margin E_j + Δ_p(j)
      const nat = new Float64Array(bank.n);
      for (let j = 0; j < bank.n; j++) nat[j] = envDraw(bank, renv, j) + pd.Delta[j % model.P];
      const medT = 0.5 * (tv.tSorted[(bank.n - 1) >> 1] + tv.tSorted[bank.n >> 1]);
      cells.push({
        dem: dem.id,
        gop: gop.id,
        pWin: V,
        pWinBinned: bin5(V),
        pWin80: V80,
        medMargin: median(nat),
        decomposition: {
          env: envC,
          tippingLean: leanBase,
          style: median(pd.style),
          opponent: median(pd.opp),
          personal: median(pd.pers),
          home: bank.medianT - medT,
        },
      });
      pws.push(pw);
    }
    if (opts.onProgress) opts.onProgress({ rowsDone: i + 1, rows: demIds.length, cells: cells.slice() });
  }

  // Indistinguishability (§6.6): adjacent cells whose per-p difference has an 80% interval covering 0.
  const nc = gopIds.length;
  const pairs = [];
  const sds = [];
  const diff = new Float64Array(model.P);
  const consider = (x, y) => {
    for (let p = 0; p < model.P; p++) diff[p] = pws[x][p] - pws[y][p];
    const s = sortedCopy(diff);
    const lo = quantileSorted(s, 0.1), hi = quantileSorted(s, 0.9);
    sds.push(1.28 * sd(diff) * 100);
    if (lo <= 0 && hi >= 0) pairs.push([x, y]);
  };
  for (let i = 0; i < demIds.length; i++) {
    for (let k = 0; k < nc; k++) {
      const x = i * nc + k;
      if (k + 1 < nc) consider(x, x + 1);
      if (i + 1 < demIds.length) consider(x, x + nc);
    }
  }
  const thresholdPts = sds.length ? median(Float64Array.from(sds)) : 0;

  // Row averages weighted by GOP nomination market prices (equal weights if none).
  const mk = gopIds.map((id) => Math.max(0, getGop(model, id).market_nom ?? 0));
  const mkSum = mk.reduce((s, x) => s + x, 0);
  const w = mk.map((x) => (mkSum > 0 ? x / mkSum : 1 / gopIds.length));
  const rowAvgByMarket = {};
  demIds.forEach((id, i) => {
    let s = 0;
    for (let k = 0; k < nc; k++) s += w[k] * cells[i * nc + k].pWin;
    rowAvgByMarket[id] = s;
  });

  return {
    cells,
    indistinguishable: { thresholdPts, pairs },
    rowAvgByMarket,
    ms: performance.now() - t0,
  };
}

/**
 * matchupDetail: Sim 1 output shape for one pairing, including tipping frequencies.
 * dV compares with a mainstream-liberal Democrat with no track record or home state
 * against the same Republican (GOP home and track kept).
 */
export function matchupDetail(model, bank, demId, gopId, opts = {}) {
  const t0 = performance.now();
  const dem = getDem(model, demId);
  const gop = getGop(model, gopId);
  const renv = resolveEnv(model, opts.env);
  const homeOn = opts.home !== false;

  const pd = pairDelta(model, dem, gop, opts);
  const hs = homeSpec(model, bank, dem.home, gop.home, homeOn);
  const tv = homeVariant(model, bank, hs);
  const comps = [{ weight: 1, Delta: pd.Delta }];
  const pw = perPWin(model, bank, tv, renv, comps);

  const refDem = { id: '_ref', archetype: REFERENCE_ARCHETYPE, home: null, track: null };
  const pdRef = pairDelta(model, refDem, gop, opts);
  const hsRef = homeSpec(model, bank, null, gop.home, homeOn);
  const tvRef = homeVariant(model, bank, hsRef);
  const pwRef = perPWin(model, bank, tvRef, renv, [{ weight: 1, Delta: pdRef.Delta }]);

  const { V, V80 } = summarizeP(pw);
  const dVp = new Float64Array(model.P);
  let below = 0;
  for (let p = 0; p < model.P; p++) {
    dVp[p] = pw[p] - pwRef[p];
    if (dVp[p] < -0.1) below++;
  }
  const es = eStar(model, tv, pd.Delta);
  const S = swingPerDraw(model, bank, renv, comps);
  const m = mapPass(model, bank, S, hs.affected.length ? hs.fullShift : null);
  return {
    dem: dem.id,
    gop: gop.id,
    V, V80,
    dV: mlh(dVp),
    pDVbelowMinus10: below / model.P,
    Estar: es.Estar,
    evHist: m.evHist,
    pTie: m.pTie,
    stateP: m.stateP,
    stateMeanMargin: m.stateMeanMargin,
    decomposition: {
      env: envCenterOf(bank, renv),
      lean: -(model.E24 + bank.medianT),
      style: median(pd.style),
      opponent: median(pd.opp),
      personal: median(pd.pers),
      home: bank.medianT - es.medT,
    },
    tipping: tippingFreq(model, tv.tip),
    curves: { E: CURVE_E.slice(), ...curves(model, tv, comps) },
    ms: performance.now() - t0,
  };
}
