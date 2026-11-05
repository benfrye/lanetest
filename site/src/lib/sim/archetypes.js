// Sim 1: archetype win-probability curves, E*, ΔV, state maps (§6.2, §6.5, §6.6).

import { ARCHETYPES, REFERENCE_ARCHETYPE } from './model.js';
import { resolveEnv, mapPass, fullPass, envCenterOf, tippingFreq } from './bank.js';
import { styleComponents, deltaComponents } from './style.js';
import { tVariant, perPWin, meanDelta, summarizeP, mlh, eStar, curves, swingPerDraw, CURVE_E } from './core.js';
import { median } from './stats.js';

/** Margin shift per unit from the tilt term (§5.1) for archetype a under draws. */
function tiltShiftFn(model, comps, a) {
  const { coords } = model;
  const { draws, pi } = comps;
  const Pbar = coords[a].P;
  const Lm1 = coords[a].L - 1;
  const P = model.P;
  const { Wt, Yt, U } = model;
  return (j, out) => {
    const p = j % P;
    const cPW = pi[p] * draws.beta_PW[p] * Pbar;
    const cLY = pi[p] * draws.beta_LY[p] * Lm1;
    for (let s = 0; s < U; s++) out[s] = cPW * Wt[s] + cLY * Yt[s];
  };
}

function tiltIsZero(comps) {
  const { draws } = comps;
  for (let p = 0; p < draws.beta_PW.length; p++) if (draws.beta_PW[p] !== 0 || draws.beta_LY[p] !== 0) return false;
  return true;
}

/**
 * simArchetypes(model, bank, opts)
 * opts: { env:{mode,value?|preset?}, opponent:'generic'|'maga'|'traditional', pi:{mode,value?},
 *         preset | dial, tilt=false, archetypes?: string[], map=true }
 */
export function simArchetypes(model, bank, opts = {}) {
  const t0 = performance.now();
  const renv = resolveEnv(model, opts.env);
  const opponent = opts.opponent ?? 'generic';
  const list = opts.archetypes ?? ARCHETYPES;
  const sel = opts.dial ? { dial: opts.dial } : { preset: opts.preset ?? model.defaultPreset };
  const wantMap = opts.map !== false;

  const per = {};
  for (const a of new Set([REFERENCE_ARCHETYPE, ...list])) {
    const comps = styleComponents(model, { ...sel, archetype: a, pi: opts.pi });
    const dc = deltaComponents(model, comps, opponent);
    let tv = tVariant(bank);
    let shiftFn = null;
    if (opts.tilt && !tiltIsZero(comps)) {
      // Tilt on: thresholds depend on p → paired brute force with p(j) = j mod P (§6.2).
      shiftFn = tiltShiftFn(model, comps, a);
      tv = tVariant(bank, fullPass(model, bank, shiftFn), `tilt:${a}:${JSON.stringify(sel)}:${JSON.stringify(opts.pi ?? null)}`);
    }
    per[a] = { comps, dc, tv, shiftFn, pw: perPWin(model, bank, tv, renv, dc) };
  }

  const envC = envCenterOf(bank, renv);
  const byArchetype = {};
  const curveOut = { E: CURVE_E.slice(), byArchetype: {} };
  const ref = per[REFERENCE_ARCHETYPE];
  for (const a of list) {
    const r = per[a];
    const { V, V80 } = summarizeP(r.pw);
    const dVp = new Float64Array(model.P);
    let below = 0;
    for (let p = 0; p < model.P; p++) {
      dVp[p] = r.pw[p] - ref.pw[p];
      if (dVp[p] < -0.1) below++;
    }
    const dMean = meanDelta(model, r.dc);
    const es = eStar(model, r.tv, dMean);
    // decomposition of the median tipping-point margin: env + lean + style + opponent
    const styleOnly = new Float64Array(model.P);
    for (let p = 0; p < model.P; p++) styleOnly[p] = r.comps.pi[p] * r.comps.delta[p];
    const styleMed = median(styleOnly);
    const oppMed = median(dMean) - styleMed;
    const out = {
      V, V80,
      dV: mlh(dVp),
      pDVbelowMinus10: below / model.P,
      Estar: es.Estar,
      decomposition: { env: envC, lean: -(model.E24 + es.medT), style: styleMed, opponent: oppMed },
    };
    if (wantMap) {
      const S = swingPerDraw(model, bank, renv, r.dc);
      const m = mapPass(model, bank, S, r.shiftFn);
      out.evHist = m.evHist;
      out.pTie = m.pTie;
      out.stateP = m.stateP;
      out.stateMeanMargin = m.stateMeanMargin;
    }
    byArchetype[a] = out;
    curveOut.byArchetype[a] = curves(model, r.tv, r.dc);
  }
  return {
    byArchetype,
    tipping: opts.tilt ? tippingFreq(model, per[list[0]].tv.tip) : bank.tipping,
    curves: curveOut,
    tiltApprox: !!opts.tilt,
    ms: performance.now() - t0,
  };
}

/** Only the curves (cheap path for slider drags): 5 × 31 E × P binary searches. */
export function archetypeCurves(model, bank, opts = {}) {
  const t0 = performance.now();
  const opponent = opts.opponent ?? 'generic';
  const sel = opts.dial ? { dial: opts.dial } : { preset: opts.preset ?? model.defaultPreset };
  const tv = tVariant(bank);
  const byArchetype = {};
  for (const a of opts.archetypes ?? ARCHETYPES) {
    const comps = styleComponents(model, { ...sel, archetype: a, pi: opts.pi });
    byArchetype[a] = curves(model, tv, deltaComponents(model, comps, opponent), opts.E ?? CURVE_E);
  }
  return { E: (opts.E ?? CURVE_E).slice(), byArchetype, ms: performance.now() - t0 };
}
