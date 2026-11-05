// Sim 5: 2026 as a presidential map — a translation, not a forecast (§6.6 Sim 5).

import { envCenter } from './model.js';
import { substream } from './rng.js';
import { quantileSorted } from './stats.js';

/**
 * sim5(model, { view:'raw'|'electorate'|'durable', u, phi, source:'house'|'senate'|'governor', n=2000, seed })
 * - raw:        house26_s
 * - electorate: house26_s + u_e·electorate_adj_s      (u_e defaults to 1 in this view)
 * - durable:    house26_s − φ·(house26_US − E_default_center)   (φ defaults to sim5.durable_phi_default)
 * Senate/governor sources use the race margin where a race exists and fall back to the House
 * margin elsewhere (flagged `fallback: true`).
 */
export function sim5(model, opts = {}) {
  const t0 = performance.now();
  const s5 = model.sim5;
  if (!s5) throw new Error('model has no sim5 block');
  const view = opts.view ?? 'durable';
  const source = opts.source ?? 'house';
  const n = opts.n ?? 2000;
  const seed = (opts.seed ?? model.meta.seed ?? 1) >>> 0;
  const uE = opts.u ?? (view === 'electorate' ? 1 : 0);
  const phi = opts.phi ?? s5.durable_phi_default ?? 1;
  const Ecenter = envCenter(model.env.presets[model.env.default_preset]);
  const natShift = (s5.national_house26 ?? 0) - Ecenter;

  const byId = new Map((s5.units ?? []).map((u) => [u.id, u]));
  const race = source === 'house' ? null : new Map((s5[source] ?? []).map((r) => [r.id, r]));
  const { U, ids, m24, parentIdx, ev } = model;
  const margin = new Float64Array(U);
  const sdv = new Float64Array(U);
  const hatched = new Array(U).fill(false);
  const fallback = new Array(U).fill(false);

  const baseFor = (s) => {
    const row = byId.get(ids[s]);
    if (row) {
      return {
        m: row.house26, sd: row.house26_sd ?? 0, adj: row.electorate_adj ?? 0,
        hatch: !!row.hatched || (row.pct_counted != null && row.pct_counted < 0.9),
      };
    }
    const p = parentIdx[s];
    if (p >= 0) {
      const pr = baseFor(p);
      return { ...pr, m: pr.m + (m24[s] - m24[p]) };
    }
    throw new Error(`sim5.units has no row for ${ids[s]}`);
  };

  for (let s = 0; s < U; s++) {
    const b = baseFor(s);
    let m = b.m;
    let sdx = b.sd;
    if (race) {
      const r = race.get(ids[s]) ?? (parentIdx[s] >= 0 ? null : null);
      if (r) {
        m = r.margin;
        sdx = r.sd ?? b.sd;
      } else fallback[s] = true;
    }
    if (view === 'electorate') m += uE * b.adj;
    else if (view === 'durable') m -= phi * natShift;
    margin[s] = m;
    sdv[s] = sdx;
    hatched[s] = b.hatch;
  }

  // independent normal draws per unit (districts share their parent's draw)
  const rng = substream(seed, `sim5:${source}`);
  const z = new Float64Array(U);
  const wins = new Float64Array(U);
  const evs = new Float64Array(n);
  for (let j = 0; j < n; j++) {
    for (let s = 0; s < U; s++) if (parentIdx[s] < 0) z[s] = rng.normal();
    let evD = 0;
    for (let s = 0; s < U; s++) {
      const zz = parentIdx[s] >= 0 ? z[parentIdx[s]] : z[s];
      if (margin[s] + sdv[s] * zz > 0) {
        wins[s]++;
        evD += ev[s];
      }
    }
    evs[j] = evD;
  }
  evs.sort();
  const units = [];
  const flips = [];
  for (let s = 0; s < U; s++) {
    units.push({ id: ids[s], margin: margin[s], sd: sdv[s], pD: wins[s] / n, hatched: hatched[s], ...(race ? { fallback: fallback[s] } : {}) });
    if ((margin[s] > 0) !== (m24[s] > 0)) flips.push(ids[s]);
  }
  return {
    view, source,
    units,
    ev: [quantileSorted(evs, 0.5), quantileSorted(evs, 0.1), quantileSorted(evs, 0.9)],
    flipsVs2024: flips,
    ms: performance.now() - t0,
  };
}
