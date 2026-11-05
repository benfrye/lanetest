// node --test site/src/lib/sim/__tests__/
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  loadModel, buildBank, simArchetypes, archetypeCurves, simMatchups, matchupDetail, simPrimary,
  simCustom, believeHeatmap, sim5, styleDelta, dialPosterior, ARCHETYPES, Rng, substream,
} from '../engine.js';
import { distSorted, pWinDist, homePass, fullPass } from '../bank.js';
import { EcdfIndex, countLess } from '../stats.js';
import { createDispatcher } from '../worker-core.js';
import { fixtureJson, zeroStyle, stripMs, isNonDecreasing, STATES_PATH } from './helpers.js';

const FIX = fixtureJson();
const N_SMALL = 4000; // functional tests; performance tests use the full 10,000

// ------------------------------------------------------------------ schema / loading

test('fixture is schema-conforming and marked as a fixture', () => {
  assert.equal(FIX.fixture, true);
  assert.equal(FIX.meta.fixture, true);
  for (const p of Object.values(FIX.style.presets)) assert.equal(p.fixture, true);
  const m = loadModel(FIX);
  assert.equal(m.U, 56);
  assert.equal(m.evTotal, 538);
  assert.equal(m.ev.reduce((s, x) => s + x, 0), 538);
  assert.equal(m.P, 1000);
  for (const id of ['ME-1', 'ME-2', 'NE-1', 'NE-2', 'NE-3']) assert.equal(m.types[m.unitIndex.get(id)], 'district');
});

test('fixture margins come from research/states.json', () => {
  const states = JSON.parse(readFileSync(STATES_PATH, 'utf8')).rows;
  const m = loadModel(FIX);
  for (const r of states) {
    const s = m.unitIndex.get(r.id);
    const { dem_votes: d, rep_votes: rv } = r.pres2024;
    assert.ok(Math.abs(m.m24[s] - (100 * (d - rv)) / (d + rv)) < 1e-3, r.id);
    assert.equal(m.ev[s], r.electoral_votes_2028, r.id);
  }
});

test('loadModel rejects bad EV totals and k_s <= 0', () => {
  const bad = structuredClone(FIX);
  bad.units[0].ev += 1;
  assert.throws(() => loadModel(bad), /EV sum/);
  const bad2 = structuredClone(FIX);
  bad2.units[3].G = 2.1;
  assert.throws(() => loadModel(bad2), /k_s/);
  const bad3 = structuredClone(FIX);
  bad3.transfer_pi.pi_draws.pop();
  assert.throws(() => loadModel(bad3), /pi_draws/);
});

// ------------------------------------------------------------------ V1 identity

test('V1 identity: zero style, E = E24, no errors, u=ψ=φ=0 reproduces the 2024 map (Harris 226)', () => {
  for (const precision of ['f64', 'f32']) {
    const m = loadModel(zeroStyle(FIX), { precision });
    const bank = buildBank(m, { n: 200, seed: 7, u: 0, psi: 0, phi: 0, noise: false });
    const r = simArchetypes(m, bank, { env: { mode: 'point', value: m.E24 }, opponent: 'traditional', pi: { mode: 'fixed', value: 1 } });
    for (const a of ARCHETYPES) {
      const x = r.byArchetype[a];
      assert.equal(x.evHist[226], bank.n, `${a} ${precision}: every draw gives D 226 EV`);
      assert.equal(x.V, 0, 'Harris lost');
      const tol = precision === 'f64' ? 1e-9 : 1e-4;
      for (let s = 0; s < m.U; s++) {
        const id = m.ids[s];
        assert.ok(Math.abs(x.stateMeanMargin[id] - m.m24[s]) <= tol, `${id} margin`);
        assert.equal(x.stateP[id], m.m24[s] > 0 ? 1 : 0, `${id} winner`);
      }
    }
    // Harris carried ME-1 and NE-2 but not ME-2
    const ml = r.byArchetype.mainstream_liberal.stateP;
    assert.equal(ml['ME-1'], 1);
    assert.equal(ml['NE-2'], 1);
    assert.equal(ml['ME-2'], 0);
    // named matrix with homes/tracks off is identical
    const mm = simMatchups(m, bank, { env: { mode: 'point', value: m.E24 }, home: false, track: false });
    for (const c of mm.cells) assert.equal(c.pWin, 0);
  }
});

test('V1: the swing needed (t) with zero errors is the smallest swing that flips 44 EV', () => {
  const m = loadModel(zeroStyle(FIX), { precision: 'f64' });
  const bank = buildBank(m, { n: 10, seed: 1, psi: 0, phi: 0, noise: false });
  // D needs 270 − 226 = 44 more EV; P(win) jumps from 0 to 1 at S = t
  const t = bank.t[0];
  assert.ok(t > 0);
  const r = (E) => simArchetypes(m, bank, { env: { mode: 'point', value: E }, opponent: 'traditional', archetypes: ['moderate'] }).byArchetype.moderate.V;
  assert.equal(r(m.E24 + t), 0);
  assert.equal(r(m.E24 + t + 1e-6), 1);
});

// ------------------------------------------------------------------ determinism / CRN

test('determinism: same seed gives identical banks and outputs; a different seed differs', () => {
  const run = (seed) => {
    const m = loadModel(FIX);
    const b = buildBank(m, { n: N_SMALL, seed });
    return {
      t: Array.from(b.tRaw.slice(0, 50)),
      sim1: stripMs(simArchetypes(m, b, {})),
      sim2: stripMs(simMatchups(m, b, {})),
      custom: stripMs(simCustom(m, b, { L: 1.4, P: 0.6, home: 'PA', track: { o: 4, n: 2 }, opponent: 'maga' })),
      heat: stripMs(believeHeatmap(m, b, { archetype: 'progressive' })),
      prim: stripMs(simPrimary(m, { n: 2000, seed })),
      s5: stripMs(sim5(m, { view: 'raw', seed })),
    };
  };
  const a = run(11), b = run(11), c = run(12);
  assert.deepEqual(a, b);
  assert.notDeepEqual(a.t, c.t);
  assert.notDeepEqual(a.prim.pNominee, c.prim.pNominee);
});

test('rng: xoshiro128** stream is reproducible; normals and t5 have the right moments', () => {
  const r1 = new Rng(42), r2 = new Rng(42);
  for (let i = 0; i < 100; i++) assert.equal(r1.nextU32(), r2.nextU32());
  const r = substream(1, 'moments');
  let s = 0, s2 = 0, t2 = 0;
  const N = 200000;
  for (let i = 0; i < N; i++) {
    const z = r.normal();
    s += z; s2 += z * z;
    const t = r.t5Unit();
    t2 += t * t;
  }
  assert.ok(Math.abs(s / N) < 0.01);
  assert.ok(Math.abs(s2 / N - 1) < 0.02);
  assert.ok(Math.abs(t2 / N - 1) < 0.05, `t5 unit variance ${t2 / N}`);
});

test('CRN: banks with the same seed share outcome errors across u/ψ/φ', () => {
  const m = loadModel(FIX, { precision: 'f64' });
  const b0 = buildBank(m, { n: 500, seed: 3, u: 0, psi: 0.2 });
  const b1 = buildBank(m, { n: 500, seed: 3, u: 0.5, psi: 0.2 });
  for (let i = 0; i < b0.a.length; i++) assert.equal(b0.a[i], b1.a[i]);
  assert.notDeepEqual(Array.from(b0.theta.slice(0, 56)), Array.from(b1.theta.slice(0, 56)));
});

test('V18: δ = 0 makes archetypes identical; ΔV of the reference is exactly 0', () => {
  const m = loadModel(zeroStyle(FIX));
  const bank = buildBank(m, { n: N_SMALL, seed: 5 });
  const r = simArchetypes(m, bank, {});
  const ref = r.byArchetype.mainstream_liberal;
  for (const a of ARCHETYPES) {
    assert.equal(r.byArchetype[a].V, ref.V);
    assert.deepEqual(r.byArchetype[a].dV, [0, 0, 0]);
  }
  const m2 = loadModel(FIX);
  const r2 = simArchetypes(m2, buildBank(m2, { n: N_SMALL, seed: 5 }), {});
  assert.deepEqual(r2.byArchetype.mainstream_liberal.dV, [0, 0, 0]);
});

// ------------------------------------------------------------------ probabilities

test('probabilities: EV histograms, state P, tipping, primary outcomes sum correctly', () => {
  const m = loadModel(FIX);
  const bank = buildBank(m, { n: N_SMALL, seed: 9 });
  const r = simArchetypes(m, bank, {});
  const tipSum = Object.values(r.tipping).reduce((s, x) => s + x, 0);
  assert.ok(Math.abs(tipSum - 1) < 1e-9);
  for (const a of ARCHETYPES) {
    const x = r.byArchetype[a];
    assert.equal(x.evHist.reduce((s, v) => s + v, 0), bank.n);
    // P(≥ 270) from the map pass ≈ V from the bank pass (same draws, paired p(j) = j mod P)
    let win = 0;
    for (let e = 270; e <= 538; e++) win += x.evHist[e];
    assert.ok(Math.abs(win / bank.n - x.V) < 0.03, `${a}: map ${win / bank.n} vs bank ${x.V}`);
    assert.ok(x.V >= 0 && x.V <= 1);
    assert.ok(x.V80[0] <= x.V80[1]);
    assert.ok(x.dV[1] <= x.dV[0] && x.dV[0] <= x.dV[2]);
    assert.ok(x.Estar[1] <= x.Estar[0] && x.Estar[0] <= x.Estar[2]);
    for (const p of Object.values(x.stateP)) assert.ok(p >= 0 && p <= 1);
    assert.ok(x.pTie >= 0 && x.pTie < 0.05);
  }
  const pr = simPrimary(m, { n: 3000, seed: 2 });
  const sum = (o) => Object.values(o).reduce((s, x) => s + x, 0);
  assert.ok(Math.abs(sum(pr.pNominee) + pr.pNoMajority - 1) < 1e-9);
  assert.ok(Math.abs(sum(pr.pLane) + pr.pNoMajority - 1) < 1e-9);
  assert.ok(Math.abs(sum(pr.pPlurality) - 1) < 1e-9);
  for (const path of Object.values(pr.delegatePath)) {
    assert.ok(isNonDecreasing(path.med));
    assert.ok(path.lo.every((v, i) => v <= path.med[i] && path.med[i] <= path.hi[i]));
    assert.ok(path.med.at(-1) <= pr.totalDelegates);
  }
  const s5 = sim5(m, { view: 'durable' });
  assert.ok(s5.ev[1] <= s5.ev[0] && s5.ev[0] <= s5.ev[2]);
  for (const u of s5.units) assert.ok(u.pD >= 0 && u.pD <= 1);
});

test('distribution mode equals brute force over E draws: 1 − F_D(−Δ) = mean_j 1[E_j − E24 + Δ > t_j]', () => {
  const m = loadModel(FIX, { precision: 'f64' });
  const bank = buildBank(m, { n: 3000, seed: 4 });
  const D = distSorted(m, bank, 'history');
  const E = bank.Edraws.history;
  for (const delta of [-3, -0.5, 0, 0.7, 2.5]) {
    let w = 0;
    for (let j = 0; j < bank.n; j++) if (E[j] - m.E24 + delta > bank.tRaw[j]) w++;
    assert.ok(Math.abs(pWinDist(D, delta) - w / bank.n) < 1e-12);
  }
});

test('EcdfIndex agrees exactly with binary search', () => {
  const m = loadModel(FIX);
  const bank = buildBank(m, { n: 5000, seed: 8 });
  const ix = new EcdfIndex(bank.t);
  const r = new Rng(3);
  for (let i = 0; i < 20000; i++) {
    const x = -30 + 60 * r.uniform();
    assert.equal(ix.countLess(x), countLess(bank.t, x));
  }
  for (let i = 0; i < 2000; i += 7) assert.equal(ix.countLess(bank.t[i]), countLess(bank.t, bank.t[i]));
});

test('home-effect merge pass equals a full re-sort with the same shifts', () => {
  const m = loadModel(FIX, { precision: 'f64' });
  const bank = buildBank(m, { n: 2000, seed: 6 });
  const aff = [m.unitIndex.get('NE'), m.unitIndex.get('NE-1'), m.unitIndex.get('NE-2'), m.unitIndex.get('NE-3'), m.unitIndex.get('PA')];
  const shift = (j) => [2 + Math.sin(j), 2 + Math.sin(j), 2 + Math.sin(j), 2 + Math.sin(j), -1.5 * Math.cos(j)];
  const hp = homePass(m, bank, aff, (j, out) => shift(j).forEach((v, q) => { out[q] = v; }));
  const fp = fullPass(m, bank, (j, out) => { out.fill(0); shift(j).forEach((v, q) => { out[aff[q]] = v; }); });
  for (let j = 0; j < bank.n; j++) {
    assert.equal(hp.tRaw[j], fp.tRaw[j]);
    assert.equal(hp.tip[j], fp.tip[j]);
  }
});

// ------------------------------------------------------------------ monotonicity

test('monotonicity: higher E never lowers P(win) (curves, point V, matrix, heatmap, custom)', () => {
  const m = loadModel(FIX);
  const bank = buildBank(m, { n: N_SMALL, seed: 21 });
  const c = archetypeCurves(m, bank, {});
  for (const a of ARCHETYPES) {
    for (const k of ['med', 'lo', 'hi', 'mean']) assert.ok(isNonDecreasing(c.byArchetype[a][k]), `${a} ${k}`);
  }
  const cMaga = archetypeCurves(m, bank, { opponent: 'maga', pi: { mode: 'fixed', value: 1.5 } });
  for (const a of ARCHETYPES) assert.ok(isNonDecreasing(cMaga.byArchetype[a].mean));

  const Es = [-6, -3, 0, 2, 4, 7, 10];
  let prev = null;
  for (const E of Es) {
    const r = simArchetypes(m, bank, { env: { mode: 'point', value: E }, map: false });
    const mm = simMatchups(m, bank, { env: { mode: 'point', value: E } });
    const cu = simCustom(m, bank, { L: 1.2, P: 0.4, home: 'MI', opponent: 'jd-vance', env: { mode: 'point', value: E } });
    const cur = { arch: ARCHETYPES.map((a) => r.byArchetype[a].V), cells: mm.cells.map((x) => x.pWin), custom: cu.V };
    if (prev) {
      cur.arch.forEach((v, i) => assert.ok(v >= prev.arch[i] - 1e-12, `arch ${i} at E=${E}`));
      cur.cells.forEach((v, i) => assert.ok(v >= prev.cells[i] - 1e-12, `cell ${i} at E=${E}`));
      assert.ok(cur.custom >= prev.custom - 1e-12);
    }
    prev = cur;
  }
  // larger style effect never lowers P(win) either
  const h = believeHeatmap(m, bank, { archetype: 'left_populist' });
  const nS = h.styleGrid.length;
  for (let i = 0; i < h.Egrid.length; i++) {
    for (let k = 0; k < nS; k++) {
      if (i > 0) assert.ok(h.pWin[i * nS + k] >= h.pWin[(i - 1) * nS + k]);
      if (k > 0) assert.ok(h.pWin[i * nS + k] >= h.pWin[i * nS + k - 1]);
    }
  }
});

// ------------------------------------------------------------------ API surface details

test('styleDelta: archetype, coords, opponents, π modes, trust dial', () => {
  const m = loadModel(FIX, { precision: 'f64' });
  const d0 = styleDelta(m, { archetype: 'progressive', opponent: 'traditional', pi: { mode: 'fixed', value: 1 } });
  const raw = m.presets.agnostic.delta.progressive;
  for (let p = 0; p < m.P; p++) assert.ok(Math.abs(d0[p] - raw[p]) < 1e-12);
  // on a centroid, coords reproduce the archetype
  const dc = styleDelta(m, { coords: { L: 2, P: 0.25 }, opponent: 'traditional', pi: { mode: 'fixed', value: 1 } });
  // (fixture δ draws are rounded to 1e-4 after being derived from rounded β/u draws)
  for (let p = 0; p < m.P; p++) assert.ok(Math.abs(dc[p] - raw[p]) < 2e-4);
  // generic = mean of traditional and MAGA
  const dg = styleDelta(m, { archetype: 'moderate', opponent: 'generic' });
  const dt = styleDelta(m, { archetype: 'moderate', opponent: 'traditional' });
  const dm = styleDelta(m, { archetype: 'moderate', opponent: 'maga' });
  for (let p = 0; p < m.P; p += 37) assert.ok(Math.abs(dg[p] - 0.5 * (dt[p] + dm[p])) < 1e-9);
  // π fixed scales linearly
  const d2 = styleDelta(m, { archetype: 'progressive', opponent: 'traditional', pi: { mode: 'fixed', value: 2 } });
  for (let p = 0; p < m.P; p += 41) assert.ok(Math.abs(d2[p] - 2 * d0[p]) < 1e-9);
  // dial: α = 0 → prior; huge α → data (b̂)
  const prior = dialPosterior(m, { k: 1, alpha: 0, prior: 'literature' });
  assert.ok(Math.abs(prior.mu[0] - -1.5) < 1e-9);
  const data = dialPosterior(m, { k: 1, alpha: 1e6, prior: 'agnostic' });
  m.gaussian.bhat.forEach((b, i) => assert.ok(Math.abs(data.mu[i] - b) < 1e-3));
  const dd = styleDelta(m, { dial: { k: 2, alpha: 0.5, prior: 'agnostic' }, archetype: 'left_populist' });
  assert.equal(dd.length, m.P);
});

test('sim outputs carry the §6.5 fields', () => {
  const m = loadModel(FIX);
  const bank = buildBank(m, { n: N_SMALL, seed: 1 });
  const r = simArchetypes(m, bank, {});
  assert.equal(r.curves.E.length, 31);
  assert.equal(r.curves.E[0], -10);
  assert.equal(r.curves.E[30], 20);
  for (const a of ARCHETYPES) {
    const x = r.byArchetype[a];
    for (const k of ['V', 'V80', 'dV', 'pDVbelowMinus10', 'Estar', 'evHist', 'pTie', 'stateP', 'stateMeanMargin', 'decomposition']) assert.ok(k in x, k);
    assert.equal(x.evHist.length, 539);
    assert.ok(x.Estar.every(Number.isInteger));
    assert.deepEqual(Object.keys(x.decomposition).sort(), ['env', 'lean', 'opponent', 'style']);
  }
  const mm = simMatchups(m, bank, {});
  assert.equal(mm.cells.length, 40);
  for (const c of mm.cells) {
    assert.equal(Math.round(c.pWinBinned * 20), c.pWinBinned * 20);
    assert.ok(Math.abs(c.pWinBinned - c.pWin) <= 0.025 + 1e-12);
    assert.deepEqual(Object.keys(c.decomposition).sort(), ['env', 'home', 'opponent', 'personal', 'style', 'tippingLean']);
  }
  assert.ok(mm.indistinguishable.thresholdPts > 0);
  assert.equal(Object.keys(mm.rowAvgByMarket).length, 8);
  const md = matchupDetail(m, bank, 'jon-ossoff', 'marco-rubio', {});
  assert.ok(Math.abs(Object.values(md.tipping).reduce((s, x) => s + x, 0) - 1) < 1e-9);
  assert.equal(md.evHist.length, 539);
  // Sim 4: inside the hull vs extrapolated
  const inside = simCustom(m, bank, { L: 1, P: 0 });
  assert.equal(inside.extrapolated, false);
  assert.equal(inside.hullDistance, 0);
  const outside = simCustom(m, bank, { L: 0, P: 1 });
  assert.equal(outside.extrapolated, true);
  assert.ok(outside.hullDistance > 0);
  assert.equal(inside.waterfall.at(-1).key, 'total');
  const sumParts = inside.waterfall.slice(0, -1).reduce((s, w) => s + w.value, 0);
  assert.ok(Math.abs(sumParts - inside.waterfall.at(-1).value) < 1e-9);
  // heatmap + B
  const h = believeHeatmap(m, bank, { archetype: 'progressive' });
  assert.equal(h.pWin.length, 37 * 25);
  assert.ok(h.contours.p50.length > 2 && h.contours.p90.length > 2);
  if (h.B.threshold != null) assert.ok(h.B.threshold < 0 && h.B.posteriorProb >= 0 && h.B.posteriorProb <= 1);
  // Sim 5 views
  for (const view of ['raw', 'electorate', 'durable']) {
    const s = sim5(m, { view });
    assert.equal(s.units.length, 56);
  }
  const sen = sim5(m, { view: 'raw', source: 'senate' });
  assert.ok(sen.units.some((u) => u.fallback) && sen.units.some((u) => !u.fallback));
  // primary chained only on request
  assert.equal(simPrimary(m, { n: 500 }).chained, undefined);
  const ch = simPrimary(m, { n: 500, chain: { bank } }).chained;
  assert.ok(ch.pDemWins > 0 && ch.pDemWins < 1 && ch.warning.length > 0);
});

test('tilt on: gated-off interactions leave results unchanged; gated-on runs the brute-force path', () => {
  const m = loadModel(FIX);
  const bank = buildBank(m, { n: N_SMALL, seed: 2 });
  const off = simArchetypes(m, bank, { map: false });
  const on = simArchetypes(m, bank, { tilt: true, map: false });
  for (const a of ARCHETYPES) assert.equal(on.byArchetype[a].V, off.byArchetype[a].V);
  const j = structuredClone(FIX);
  j.style.interactions.beta_PW.gate_passed = true;
  j.style.interactions.beta_LY.gate_passed = true;
  const m2 = loadModel(j);
  const b2 = buildBank(m2, { n: N_SMALL, seed: 2 });
  const t = simArchetypes(m2, b2, { tilt: true });
  assert.equal(t.tiltApprox, true);
  assert.equal(t.byArchetype.mainstream_liberal.V, simArchetypes(m2, b2, { map: false }).byArchetype.mainstream_liberal.V);
  for (const a of ARCHETYPES) assert.ok(isNonDecreasing(t.curves.byArchetype[a].mean));
});

// ------------------------------------------------------------------ worker protocol

test('worker dispatcher: load, call, progress, errors', async () => {
  const msgs = [];
  const dispatch = createDispatcher((m) => msgs.push(m));
  await dispatch({ id: 1, type: 'load', json: FIX });
  assert.equal(msgs[0].ok, true);
  assert.equal(msgs[0].result.units, 56);
  await dispatch({ id: 2, type: 'call', fn: 'simArchetypes', args: [{}], bank: { n: 2000, seed: 1 } });
  assert.equal(msgs.at(-1).id, 2);
  assert.ok(msgs.at(-1).result.byArchetype.progressive.V > 0);
  await dispatch({ id: 3, type: 'call', fn: 'simMatchups', args: [{}], bank: { n: 2000, seed: 1 } });
  const prog = msgs.filter((x) => x.id === 3 && x.progress);
  assert.equal(prog.length, 8);
  assert.equal(msgs.at(-1).result.cells.length, 40);
  await dispatch({ id: 4, type: 'call', fn: 'matchupDetail', args: ['jon-ossoff', 'jd-vance', {}], bank: { n: 2000, seed: 1 } });
  assert.equal(msgs.at(-1).ok, true);
  await dispatch({ id: 5, type: 'call', fn: 'nope', args: [] });
  assert.equal(msgs.at(-1).ok, false);
  await dispatch({ id: 6, type: 'call', fn: 'simPrimary', args: [{ n: 500, chain: {} }], bank: { n: 2000, seed: 1 } });
  assert.ok(msgs.at(-1).result.chained.pDemWins > 0);
});
