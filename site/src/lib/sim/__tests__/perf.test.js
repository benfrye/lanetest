// Performance against the §6.3 budgets, measured in Node on this machine.
// The budgets are for a mid-tier Android phone (desktop Chrome with a 4× CPU throttle as a proxy);
// we report raw Node timings and the ×4 proxy, and assert only the raw timing ≤ budget.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadModel, buildBank, simArchetypes, archetypeCurves, simMatchups, believeHeatmap, simPrimary } from '../engine.js';
import { fixtureJson } from './helpers.js';

const FIX = fixtureJson();
const THROTTLE = 4;

function time(fn, reps) {
  const ts = [];
  let out;
  for (let i = 0; i < reps; i++) {
    const t0 = performance.now();
    out = fn(i);
    ts.push(performance.now() - t0);
  }
  const cold = ts[0];
  const warm = ts.slice(1).sort((a, b) => a - b);
  return { cold, warm: warm[Math.floor(warm.length / 2)] ?? cold, out };
}

test('§6.3 budgets (10,000 outcome draws)', () => {
  const m = loadModel(FIX);
  const rows = [];
  const add = (op, budget, r) => rows.push({ op, budget, cold: r.cold, warm: r.warm });

  add('Build bank (10k draws, fresh seed)', 250, time((i) => buildBank(m, { n: 10000, seed: 1000 + i }), 5));
  add('Rebuild bank (new u, cached errors)', 250, time((i) => buildBank(m, { n: 10000, seed: 1000, u: 0.1 * (i + 1) }), 5));
  const bank = buildBank(m, { n: 10000, seed: 1 });
  add('Sim 1 (5 archetypes, maps + curves)', 50, time(() => simArchetypes(m, bank, {}), 7));
  add('Win-vs-E curves (5 × 31 × 1000 p)', 20, time(() => archetypeCurves(m, bank, {}), 7));
  add('Sim 2 full matrix (8 × 5 = 40 cells, homes)', 800, time(() => { bank._home = null; return simMatchups(m, bank, {}); }, 5));
  add('Sim 4 heatmap (37 E × 25 style)', 10, time(() => believeHeatmap(m, bank, { archetype: 'progressive' }), 7));
  add('Sim 3 primary (10k × 16 dates × 8 cands)', 700, time((i) => simPrimary(m, { n: 10000, seed: i }), 3));

  const fmt = (x) => x.toFixed(1).padStart(7);
  const lines = rows.map((r) =>
    `${r.op.padEnd(46)} budget ${String(r.budget).padStart(4)} ms | cold ${fmt(r.cold)} | warm ${fmt(r.warm)} | ×${THROTTLE} proxy ${fmt(r.warm * THROTTLE)} ${r.warm * THROTTLE <= r.budget ? 'OK' : 'OVER'}`);
  console.log(`\n${lines.join('\n')}\n`);
  for (const r of rows) assert.ok(r.warm <= r.budget, `${r.op}: ${r.warm.toFixed(1)} ms > ${r.budget} ms`);
});
