// Promise-based client for the simulation worker (UI thread side).
//
//   import { createSimClient } from './lib/sim/client.js';
//   const sim = createSimClient();
//   await sim.loadUrl('./data/model_params.json');
//   const r = await sim.simArchetypes({ env: { mode: 'dist', preset: 'history' } }, { seed: 1 });
//
// Every method takes (opts, bankOpts?, callOpts?) where bankOpts = { n, seed, u, psi, phi }
// selects/caches the outcome bank inside the worker, and callOpts = { channel, onProgress }.
// With a `channel`, a newer call on the same channel makes older pending ones reject with
// a StaleResultError (latest-wins for slider drags); the worker still finishes them.

export class StaleResultError extends Error {
  constructor() {
    super('superseded by a newer request on the same channel');
    this.name = 'StaleResultError';
  }
}

export function createSimClient({ worker } = {}) {
  const w = worker ?? new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });
  let seq = 0;
  const pending = new Map();
  const channels = new Map();

  w.onmessage = (e) => {
    const msg = e.data;
    const p = pending.get(msg.id);
    if (!p) return;
    if (msg.progress) {
      if (!p.stale && p.onProgress) p.onProgress(msg.progress);
      return;
    }
    pending.delete(msg.id);
    if (p.channel && channels.get(p.channel) === msg.id) channels.delete(p.channel);
    if (p.stale) return p.reject(new StaleResultError());
    if (msg.ok) p.resolve(msg.result);
    else {
      const err = new Error(msg.error?.message ?? 'worker error');
      err.name = msg.error?.name ?? 'Error';
      p.reject(err);
    }
  };

  function send(message, { channel, onProgress } = {}) {
    const id = ++seq;
    if (channel) {
      const prev = channels.get(channel);
      if (prev && pending.has(prev)) pending.get(prev).stale = true;
      channels.set(channel, id);
    }
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject, channel, onProgress, stale: false });
      w.postMessage({ id, ...message });
    });
  }

  const call = (fn) => (opts = {}, bank = {}, callOpts = {}) =>
    send({ type: 'call', fn, args: [opts], bank }, callOpts);

  return {
    load: (json, precision) => send({ type: 'load', json, precision }),
    // resolve against the page, not the worker script (a worker resolves relative URLs from its own URL)
    loadUrl: (url, precision) =>
      send({ type: 'loadUrl', url: new URL(url, globalThis.document?.baseURI ?? globalThis.location?.href).href, precision }),
    buildBank: (bank = {}) => send({ type: 'call', fn: 'buildBank', args: [bank], bank }),
    styleDelta: call('styleDelta'),
    simArchetypes: call('simArchetypes'),
    archetypeCurves: call('archetypeCurves'),
    simMatchups: call('simMatchups'),
    matchupDetail: (dem, gop, opts = {}, bank = {}, callOpts = {}) =>
      send({ type: 'call', fn: 'matchupDetail', args: [dem, gop, opts], bank }, callOpts),
    simPrimary: call('simPrimary'),
    simCustom: call('simCustom'),
    believeHeatmap: call('believeHeatmap'),
    sim5: call('sim5'),
    terminate: () => w.terminate(),
  };
}
