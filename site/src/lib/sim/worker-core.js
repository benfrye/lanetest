// Message dispatcher for the simulation Web Worker. Kept separate from worker.js so it
// can be unit-tested in Node without a Worker.
//
// Protocol (main → worker):
//   { id, type: 'load',    json, precision? }        parse/validate the model
//   { id, type: 'loadUrl', url,  precision? }        fetch + validate inside the worker
//   { id, type: 'call',    fn, args: [...], bank?: {n, seed, u, psi, phi} }
// Replies (worker → main):
//   { id, ok: true, result }  |  { id, ok: false, error }  |  { id, progress }

import * as E from './engine.js';

const BANK_FNS = new Set(['simArchetypes', 'archetypeCurves', 'simMatchups', 'matchupDetail', 'simCustom', 'believeHeatmap']);
const MODEL_FNS = new Set(['styleDelta', 'simPrimary', 'sim5']);

function bankSummary(b) {
  return { n: b.n, seed: b.seed, u: b.u, psi: b.psi, phi: b.phi, medianT: b.medianT, tipping: b.tipping, buildMs: b.buildMs };
}

/** Collect fresh typed-array buffers in a result for zero-copy transfer. */
function transferables(obj, out = [], seen = new Set()) {
  if (!obj || typeof obj !== 'object' || seen.has(obj)) return out;
  seen.add(obj);
  if (ArrayBuffer.isView(obj)) {
    if (!seen.has(obj.buffer)) { seen.add(obj.buffer); out.push(obj.buffer); }
    return out;
  }
  for (const v of Object.values(obj)) transferables(v, out, seen);
  return out;
}

export function createDispatcher(post, fetchImpl = globalThis.fetch) {
  const state = { model: null };

  return async function dispatch(msg) {
    const { id, type } = msg;
    try {
      if (type === 'load' || type === 'loadUrl') {
        const json = type === 'load' ? msg.json : await (await fetchImpl(msg.url)).json();
        state.model = E.loadModel(json, { precision: msg.precision });
        const m = state.model;
        post({ id, ok: true, result: { units: m.U, ev: m.evTotal, P: m.P, meta: m.meta, E24: m.E24 } });
        return;
      }
      if (type !== 'call') throw new Error(`unknown message type ${type}`);
      const model = state.model;
      if (!model) throw new Error('model not loaded');
      const { fn } = msg;
      const args = msg.args ?? [];
      let result;
      if (fn === 'buildBank') {
        result = bankSummary(E.buildBank(model, args[0] ?? msg.bank ?? {}));
      } else if (BANK_FNS.has(fn)) {
        const bank = E.buildBank(model, msg.bank ?? {});
        const opts = { ...(args[args.length - 1] ?? {}) };
        if (fn === 'simMatchups') opts.onProgress = (pr) => post({ id, progress: pr });
        const call = [...args.slice(0, -1), opts];
        if (fn === 'matchupDetail' && args.length < 3) throw new Error('matchupDetail needs (dem, gop, opts)');
        result = E[fn](model, bank, ...call);
      } else if (MODEL_FNS.has(fn)) {
        const opts = { ...(args[0] ?? {}) };
        if (fn === 'simPrimary' && opts.chain) opts.chain = { ...opts.chain, bank: E.buildBank(model, msg.bank ?? {}) };
        result = E[fn](model, opts);
      } else {
        throw new Error(`unknown engine function ${fn}`);
      }
      post({ id, ok: true, result }, transferables(result));
    } catch (err) {
      post({ id, ok: false, error: { name: err?.name ?? 'Error', message: String(err?.message ?? err) } });
    }
  };
}
