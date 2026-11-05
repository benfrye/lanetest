// Runs only when the pipeline has written analysis/output/model_params.json.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadModel, buildBank, simArchetypes, simMatchups, simCustom, believeHeatmap, simPrimary, sim5, ARCHETYPES } from '../engine.js';
import { realJson, zeroStyle, isNonDecreasing } from './helpers.js';

const REAL = realJson();

test('real model_params.json: loads, V1 identity, sims run', { skip: REAL ? false : 'analysis/output/model_params.json not present yet' }, () => {
  const m = loadModel(REAL);
  assert.equal(m.evTotal, 538);

  const z = loadModel(zeroStyle(REAL), { precision: 'f64' });
  const b0 = buildBank(z, { n: 50, seed: 1, psi: 0, phi: 0, u: 0, noise: false });
  const r0 = simArchetypes(z, b0, { env: { mode: 'point', value: z.E24 }, opponent: 'traditional' });
  assert.equal(r0.byArchetype.mainstream_liberal.evHist[226], 50);

  const bank = buildBank(m, { n: 10000, seed: m.meta.seed ?? 1 });
  const r = simArchetypes(m, bank, {});
  for (const a of ARCHETYPES) assert.ok(isNonDecreasing(r.byArchetype[a] && r.curves.byArchetype[a].mean));
  if (m.dems.size && m.gops.size) assert.ok(simMatchups(m, bank, {}).cells.length > 0);
  simCustom(m, bank, { L: 1, P: 0.5 });
  believeHeatmap(m, bank, { archetype: 'progressive' });
  if (m.primary) simPrimary(m, { n: 2000 });
  if (m.sim5) sim5(m, {});
});
