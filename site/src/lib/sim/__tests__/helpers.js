import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
export const FIXTURE_PATH = join(here, '../__fixtures__/model_params.fixture.json');
export const REAL_PATH = join(here, '../../../../../analysis/output/model_params.json');
export const STATES_PATH = join(here, '../../../../../research/states.json');

export function fixtureJson() {
  return JSON.parse(readFileSync(FIXTURE_PATH, 'utf8'));
}

export function realJson() {
  return existsSync(REAL_PATH) ? JSON.parse(readFileSync(REAL_PATH, 'utf8')) : null;
}

const zeros = (a) => (Array.isArray(a) ? a.map((x) => (Array.isArray(x) ? zeros(x) : 0)) : a);

/** Copy of a model JSON with every style / opponent / track effect set to exactly zero. */
export function zeroStyle(json) {
  const j = structuredClone(json);
  for (const pr of Object.values(j.style.presets)) {
    for (const k of ['beta_L', 'beta_P', 'beta_PW', 'beta_LY', 'omega_maga', 'omega_mod']) if (pr[k]) pr[k] = zeros(pr[k]);
    for (const grp of ['u', 'delta']) for (const a of Object.keys(pr[grp] ?? {})) pr[grp][a] = zeros(pr[grp][a]);
  }
  if (j.style.gaussian) {
    j.style.gaussian.bhat = zeros(j.style.gaussian.bhat);
    for (const k of Object.keys(j.style.gaussian.mu0)) j.style.gaussian.mu0[k] = zeros(j.style.gaussian.mu0[k]);
  }
  for (const c of [...(j.candidates_dem ?? []), ...(j.candidates_gop ?? [])]) {
    if (c.track?.c_draws) c.track.c_draws = zeros(c.track.c_draws);
  }
  return j;
}

/** Strip timing fields so results can be compared for determinism. */
export function stripMs(x) {
  return JSON.parse(JSON.stringify(x, (k, v) => {
    if (k === 'ms') return undefined;
    if (ArrayBuffer.isView(v)) return Array.from(v);
    return v;
  }));
}

export function isNonDecreasing(arr, tol = 1e-12) {
  for (let i = 1; i < arr.length; i++) if (arr[i] < arr[i - 1] - tol) return false;
  return true;
}
