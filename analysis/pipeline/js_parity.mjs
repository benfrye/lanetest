// V2 parity harness: runs the site's JS engine on a model_params file and prints bank-level outputs.
// Usage: node js_parity.mjs <model_params.json> <n> <seed>
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const enginePath = path.resolve(here, '../../site/src/lib/sim/engine.js');
const { loadModel, buildBank, pWinPoint } = await import(pathToFileURL(enginePath).href);
const bankMod = await import(pathToFileURL(path.resolve(here, '../../site/src/lib/sim/bank.js')).href);

const [file, nStr, seedStr] = process.argv.slice(2);
const json = JSON.parse(readFileSync(file, 'utf8'));
const n = Number(nStr), seed = Number(seedStr);
const out = {};
for (const precision of ['f64', 'f32']) {
  const m = loadModel(json, { precision });
  const b = buildBank(m, { n, seed, precision });
  const Egrid = []; for (let e = -10; e <= 20; e += 0.5) Egrid.push(e);
  const pPoint = Egrid.map((E) => pWinPoint(b.t, E - m.E24));
  const deltas = [-6, -3, -1, 0, 1, 3, 6];
  const d = bankMod.distSorted(m, b, 'history');
  const pDist = deltas.map((x) => bankMod.pWinDist(d, x));
  out[precision] = {
    E24: m.E24, tRaw: Array.from(b.tRaw), theta0: Array.from(b.theta.slice(0, m.U)),
    thetaLast: Array.from(b.theta.slice((n - 1) * m.U, n * m.U)), Egrid, pPoint, deltas, pDist,
    Ehist: Array.from(b.Edraws.history.slice(0, 50)), ids: m.ids,
  };
}
process.stdout.write(JSON.stringify(out));
