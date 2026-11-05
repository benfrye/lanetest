// Simulation engine public API (METHODOLOGY §6.5). Pure ES modules, no dependencies.
// All functions are pure given (model, bank, opts) and deterministic for a fixed seed.
// Run them inside the Web Worker (worker.js / client.js) so the UI thread never blocks.

export { loadModel, ARCHETYPES, REFERENCE_ARCHETYPE, ModelError } from './model.js';
export { buildBank, pWinPoint, resolveEnv } from './bank.js';
export { styleDelta, dialPosterior } from './style.js';
export { simArchetypes, archetypeCurves } from './archetypes.js';
export { simMatchups, matchupDetail } from './matchups.js';
export { simPrimary } from './primary.js';
export { simCustom, believeHeatmap } from './custom.js';
export { sim5 } from './sim5.js';
export { Rng, substream } from './rng.js';
