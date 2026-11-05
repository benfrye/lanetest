// Sim 3: Democratic primary simulation (§6.6 Sim 3, §6.5 simPrimary).
//
// Per simulated primary i (parameter draw p = i mod P):
//   κ_c = poll_weight·log(poll_c / mean poll) + N(0, kappa_sd²)
//   state utility_c,s = ζ_lane(c),p + η_lane(c),p·X_s + b_pop,p·P_c + κ_c
//                       + home_logit·1[home_c = s] + momentum·m_c + N(0, noise_sd²)
//   share = softmax over the whole field; dropped candidates' shares are reassigned,
//   lane_affinity_same of it to same-lane survivors (∝ their share), the rest to all survivors.
//   Delegates: proportional (largest remainder) among candidates ≥ threshold.
//   Dropouts after the 4th contest and after Super Tuesday: < dropout_share of delegates so far
//   and no state wins. Majority = more than half of all pledged delegates.

import { ARCHETYPE_LANE, REFERENCE_ARCHETYPE } from './model.js';
import { substream } from './rng.js';
import { buildBank, resolveEnv } from './bank.js';
import { styleComponents, deltaComponents } from './style.js';
import { perPWin, tVariant } from './core.js';
import { trackDraws } from './matchups.js';
import { sortedCopy, quantileSorted } from './stats.js';

const CHAIN_WARNING =
  'Chained estimate: multiplies a weak primary proxy by a conditional general-election scenario. ' +
  'Uncertainty compounds; not a forecast.';

function normalizeCalendar(model, calendar) {
  const pr = model.primary;
  let groups = calendar ?? 'dnc2024';
  let stIndex = null;
  if (typeof groups === 'string') {
    const c = pr.calendars?.[groups];
    if (!c?.length) throw new Error(`unknown primary calendar "${groups}"`);
    groups = c;
  } else if (groups && !Array.isArray(groups) && groups.groups) {
    stIndex = groups.superTuesday ?? null;
    groups = groups.groups;
  }
  const labels = [];
  const out = groups.map((g, i) => {
    if (Array.isArray(g)) { labels.push(g.length === 1 ? g[0] : `contest ${i + 1}`); return g; }
    labels.push(g.label ?? g.date ?? `contest ${i + 1}`);
    if (stIndex == null && /super/i.test(g.label ?? '')) stIndex = i;
    return g.states;
  });
  return { groups: out, labels, stIndex };
}

/**
 * simPrimary(model, { field, calendar, momentum, threshold, dropout, laneAffinity, n, seed, chain? })
 * chain: { bank? | bankOpts?, env, pi, preset|dial, opponent='generic', rho } → adds `chained`.
 */
export function simPrimary(model, opts = {}) {
  const t0 = performance.now();
  const pr = model.primary;
  if (!pr) throw new Error('model has no primary block');
  const S = pr.settings ?? {};
  const field = (opts.field ?? [...model.dems.values()].filter((c) => c.include_default !== false).map((c) => c.id))
    .map((id) => {
      const c = model.dems.get(id);
      if (!c) throw new Error(`unknown Democratic candidate "${id}"`);
      return c;
    });
  const C = field.length;
  if (C < 1) throw new Error('empty primary field');
  const n = opts.n ?? 10000;
  const seed = (opts.seed ?? model.meta.seed ?? 1) >>> 0;
  const momentumCoef = opts.momentum ?? S.momentum ?? 0.5;
  const threshold = opts.threshold ?? S.threshold ?? 0.15;
  const laneAff = opts.laneAffinity ?? S.lane_affinity_same ?? 0.6;
  const dropoutOn = opts.dropout !== false;
  const dropShare = (typeof opts.dropout === 'object' && opts.dropout.share) || S.dropout_share || 0.1;
  const pollW = S.poll_weight ?? 0.3;
  const kappaSd = S.kappa_sd ?? 0.7;
  const noiseSd = S.noise_sd ?? 0.3;
  const homeLogit = S.home_logit ?? 0.8;

  // states
  const stIdx = new Map(pr.states.map((s, i) => [s.id, i]));
  const NS = pr.states.length;
  const nCov = pr.covariates?.length ?? (pr.states[0]?.X?.length ?? 0);
  const X = new Float64Array(NS * nCov);
  const dels = new Int32Array(NS);
  pr.states.forEach((s, i) => {
    dels[i] = s.delegates;
    for (let q = 0; q < nCov; q++) X[i * nCov + q] = s.X[q];
  });
  const cal = normalizeCalendar(model, opts.calendar);
  const groups = cal.groups.map((g) => g.map((id) => {
    const i = stIdx.get(id);
    if (i == null) throw new Error(`calendar state "${id}" not in primary.states`);
    return i;
  }));
  const NG = groups.length;
  const groupStart = new Int32Array(NG + 1);
  groups.forEach((g, i) => { groupStart[i + 1] = groupStart[i] + g.length; });
  const groupFlat = Int32Array.from(groups.flat());
  const groupDel = groups.map((g) => g.reduce((s, i) => s + dels[i], 0));
  let totalDel = 0;
  for (const g of groupDel) totalDel += g;
  const majority = S.majority > 0 ? S.majority : Math.floor(totalDel / 2) + 1;
  let stIndex = cal.stIndex;
  if (stIndex == null) {
    let best = -1;
    groupDel.forEach((d, i) => { if (d > best) { best = d; stIndex = i; } });
  }
  const after = (typeof opts.dropout === 'object' && opts.dropout.after) || S.dropout_after || ['4th', 'super_tuesday'];
  const dropAt = new Uint8Array(NG);
  for (const a of after) {
    if (a === 'super_tuesday') dropAt[stIndex] = 1;
    else {
      const k = parseInt(a, 10);
      if (k >= 1 && k <= NG) dropAt[k - 1] = 1;
    }
  }

  // candidates
  const lanes = pr.lanes ?? ['left', 'mainstream', 'moderate'];
  const laneOf = field.map((c) => c.lane ?? ARCHETYPE_LANE[c.archetype] ?? 'mainstream');
  const laneIdx = laneOf.map((l) => {
    const k = lanes.indexOf(l);
    if (k < 0) throw new Error(`candidate lane "${l}" not in primary.lanes`);
    return k;
  });
  const Pc = field.map((c) => c.P ?? model.coords[c.archetype]?.P ?? 0);
  const homeS = field.map((c) => (c.home != null && stIdx.has(c.home) ? stIdx.get(c.home) : -1));
  const polls = field.map((c) => Math.max(0.5, c.poll_nat_primary ?? 0));
  const meanPoll = polls.reduce((s, x) => s + x, 0) / C;
  const pollTerm = polls.map((p) => pollW * Math.log(p / meanPoll));

  // parameter draws
  const Pn = model.P;
  // lane × state part of the utility per parameter draw: ζ_lane,p + η_lane,p·X_s (mainstream = 0)
  const NL = lanes.length;
  const laneState = new Float64Array(Pn * NL * NS);
  lanes.forEach((lane, li) => {
    if (lane === 'mainstream') return;
    const z = pr.zeta?.[lane];
    const e = pr.eta?.[lane];
    for (let p = 0; p < Pn; p++) {
      const off = (p * NL + li) * NS;
      const zp = z?.length ? z[p] : 0;
      const row = e?.length ? e[p] : null;
      for (let s = 0; s < NS; s++) {
        let v = zp;
        if (row) for (let q = 0; q < nCov; q++) v += row[q] * X[s * nCov + q];
        laneState[off + s] = v;
      }
    }
  });
  const bPop = pr.populist_term !== false && pr.b_populist?.length ? pr.b_populist : null;

  const rng = substream(seed, 'primary');
  const winsMaj = new Float64Array(C);
  const winsPlur = new Float64Array(C);
  let noMaj = 0;
  const hist = Array.from({ length: C * NG }, () => new Uint32Array(totalDel + 1));

  const util = new Float64Array(C);
  const share = new Float64Array(C);
  const active = new Uint8Array(C);
  const D = new Int32Array(C);
  const W = new Int32Array(C);
  const mom = new Float64Array(C);
  const kappa = new Float64Array(C);
  const dateShare = new Float64Array(C);
  const base = new Float64Array(C * NS); // per-(c, s) deterministic part for this p
  const alloc = new Float64Array(C);
  const rem = new Float64Array(C);
  const laneActiveShare = new Float64Array(lanes.length);
  const laneDropShare = new Float64Array(lanes.length);
  const momTerm = new Float64Array(C);

  for (let i = 0; i < n; i++) {
    const p = i % Pn;
    for (let c = 0; c < C; c++) {
      kappa[c] = pollTerm[c] + kappaSd * rng.normalPolar();
      const li = laneIdx[c];
      const zc = (bPop ? bPop[p] * Pc[c] : 0) + kappa[c];
      const off = (p * NL + li) * NS;
      for (let s = 0; s < NS; s++) base[c * NS + s] = zc + laneState[off + s];
      if (homeS[c] >= 0) base[c * NS + homeS[c]] += homeLogit;
    }
    active.fill(1);
    D.fill(0);
    W.fill(0);
    mom.fill(0);
    let allocated = 0;
    let nActive = C;

    for (let g = 0; g < NG; g++) {
      dateShare.fill(0);
      let gDel = 0;
      for (let c = 0; c < C; c++) momTerm[c] = momentumCoef * mom[c];
      const gEnd = groupStart[g + 1];
      for (let gi = groupStart[g]; gi < gEnd; gi++) {
        const s = groupFlat[gi];
        // softmax over the full field (utilities are O(1) logits, so no max-shift is needed;
        // fall back to the shifted form if anything is extreme)
        let z = 0;
        let extreme = false;
        for (let c = 0; c < C; c++) {
          const u = base[c * NS + s] + momTerm[c] + noiseSd * rng.normalPolar();
          util[c] = u;
          if (u > 600 || u < -600) extreme = true;
        }
        if (extreme) {
          let mx = -Infinity;
          for (let c = 0; c < C; c++) if (util[c] > mx) mx = util[c];
          for (let c = 0; c < C; c++) { share[c] = Math.exp(util[c] - mx); z += share[c]; }
        } else {
          for (let c = 0; c < C; c++) { share[c] = Math.exp(util[c]); z += share[c]; }
        }
        const iz = 1 / z;
        for (let c = 0; c < C; c++) share[c] *= iz;
        // reassign dropped candidates' support
        if (nActive < C) {
          // O(C + lanes): same-lane survivors get lane_affinity of their lane's dropped share
          // (∝ share), everything else is spread over all survivors (∝ share).
          let actTot = 0;
          laneActiveShare.fill(0);
          laneDropShare.fill(0);
          for (let c = 0; c < C; c++) {
            if (active[c]) { actTot += share[c]; laneActiveShare[laneIdx[c]] += share[c]; }
            else laneDropShare[laneIdx[c]] += share[c];
          }
          let general = 0;
          for (let l = 0; l < NL; l++) {
            const same = laneActiveShare[l] > 0 ? laneAff : 0;
            general += (1 - same) * laneDropShare[l];
          }
          const gScale = general / actTot;
          for (let c = 0; c < C; c++) {
            if (!active[c]) { share[c] = 0; continue; }
            const l = laneIdx[c];
            share[c] += share[c] * (gScale + (laneAff * laneDropShare[l]) / laneActiveShare[l]);
          }
        }
        // threshold + proportional allocation (largest remainder)
        let mxS = 0, win = -1;
        for (let c = 0; c < C; c++) if (share[c] > mxS) { mxS = share[c]; win = c; }
        if (win >= 0) W[win]++;
        const thr = mxS >= threshold ? threshold : 0.5 * mxS;
        let vTot = 0;
        for (let c = 0; c < C; c++) if (share[c] >= thr) vTot += share[c];
        const Ds = dels[s];
        let given = 0;
        for (let c = 0; c < C; c++) {
          const q = share[c] >= thr ? (Ds * share[c]) / vTot : 0;
          alloc[c] = Math.floor(q);
          rem[c] = share[c] >= thr ? q - alloc[c] : -1;
          given += alloc[c];
        }
        for (let left = Ds - given; left > 0; left--) {
          let b = -1, bv = -0.5;
          for (let c = 0; c < C; c++) if (rem[c] > bv) { bv = rem[c]; b = c; }
          if (b < 0) break;
          alloc[b] += 1;
          rem[b] = -1;
        }
        for (let c = 0; c < C; c++) {
          D[c] += alloc[c];
          dateShare[c] += Ds * share[c];
        }
        allocated += Ds;
        gDel += Ds;
      }
      // momentum: log ratio of this date's (delegate-weighted) vote share to an even split
      if (gDel > 0) {
        for (let c = 0; c < C; c++) {
          if (!active[c]) continue;
          mom[c] = Math.log(Math.max(1e-3, dateShare[c] / gDel) * nActive);
        }
      }
      for (let c = 0; c < C; c++) hist[c * NG + g][D[c]]++;
      // dropouts
      if (dropoutOn && dropAt[g] && nActive > 1) {
        let leader = 0;
        for (let c = 1; c < C; c++) if (D[c] > D[leader]) leader = c;
        for (let c = 0; c < C; c++) {
          if (!active[c] || c === leader) continue;
          if (D[c] < dropShare * allocated && W[c] === 0) {
            active[c] = 0;
            nActive--;
            mom[c] = 0;
          }
        }
      }
    }
    // outcome
    let leader = 0;
    for (let c = 1; c < C; c++) if (D[c] > D[leader]) leader = c;
    winsPlur[leader]++;
    if (D[leader] >= majority) winsMaj[leader]++;
    else noMaj++;
  }

  const pNominee = {};
  const pPlurality = {};
  const pLane = Object.fromEntries(lanes.map((l) => [l, 0]));
  field.forEach((c, k) => {
    pNominee[c.id] = winsMaj[k] / n;
    pPlurality[c.id] = winsPlur[k] / n;
    pLane[laneOf[k]] = (pLane[laneOf[k]] ?? 0) + winsMaj[k] / n;
  });

  const qFromHist = (h, q) => {
    const target = q * (n - 1);
    let cum = 0;
    for (let v = 0; v < h.length; v++) {
      cum += h[v];
      if (cum > target) return v;
    }
    return h.length - 1;
  };
  const delegatePath = {};
  field.forEach((c, k) => {
    const med = [], lo = [], hi = [];
    for (let g = 0; g < NG; g++) {
      const h = hist[k * NG + g];
      med.push(qFromHist(h, 0.5));
      lo.push(qFromHist(h, 0.1));
      hi.push(qFromHist(h, 0.9));
    }
    delegatePath[c.id] = { med, lo, hi };
  });

  const out = {
    pNominee,
    pLane,
    pNoMajority: noMaj / n,
    pPlurality,
    delegatePath,
    dates: cal.labels,
    totalDelegates: totalDel,
    majority,
    superTuesdayIndex: stIndex,
  };

  if (opts.chain) {
    // Chained P(D wins presidency): nominee = delegate leader; Σ_c P(lead_c)·P(win | c, p).
    const ch = opts.chain;
    const bank = ch.bank ?? buildBank(model, ch.bankOpts ?? {});
    const renv = resolveEnv(model, ch.env);
    const sel = ch.dial ? { dial: ch.dial } : { preset: ch.preset ?? model.defaultPreset };
    const rho = ch.rho ?? model.rho;
    const tv = tVariant(bank);
    const tot = new Float64Array(Pn);
    field.forEach((c, k) => {
      const wgt = winsPlur[k] / n;
      if (wgt === 0) return;
      const comps = styleComponents(model, { ...sel, archetype: c.archetype ?? REFERENCE_ARCHETYPE, pi: ch.pi });
      const cd = trackDraws(model, c, ch.track !== false);
      const extra = cd ? cd.map((x) => rho * x) : null;
      const pw = perPWin(model, bank, tv, renv, deltaComponents(model, comps, ch.opponent ?? 'generic', extra));
      for (let p = 0; p < Pn; p++) tot[p] += wgt * pw[p];
    });
    const s = sortedCopy(tot);
    out.chained = {
      pDemWins: tot.reduce((a, b) => a + b, 0) / Pn,
      p80: [quantileSorted(s, 0.1), quantileSorted(s, 0.9)],
      warning: CHAIN_WARNING,
    };
  }
  out.ms = performance.now() - t0;
  return out;
}
