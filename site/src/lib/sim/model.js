// loadModel: validate a model_params.json (METHODOLOGY §6.4) and turn it into the
// typed-array structure the engine works on.

export const ARCHETYPES = ['progressive', 'left_populist', 'center_populist', 'mainstream_liberal', 'moderate'];
export const REFERENCE_ARCHETYPE = 'mainstream_liberal';
export const STYLE_PRESETS = ['agnostic', 'literature', 'discount', 'data_only'];

/** Default lane for each archetype in the primary sim (used when a candidate has no `lane`). */
export const ARCHETYPE_LANE = {
  progressive: 'left',
  left_populist: 'left',
  mainstream_liberal: 'mainstream',
  center_populist: 'moderate',
  moderate: 'moderate',
};

export class ModelError extends Error {
  constructor(msg) {
    super(`model_params: ${msg}`);
    this.name = 'ModelError';
  }
}

function req(cond, msg) {
  if (!cond) throw new ModelError(msg);
}

function isNum(x) {
  return typeof x === 'number' && Number.isFinite(x);
}

function numArray(arr, len, what) {
  req(Array.isArray(arr) || ArrayBuffer.isView(arr), `${what} must be an array`);
  if (len != null) req(arr.length === len, `${what} has length ${arr.length}, expected ${len}`);
  const out = new Float64Array(arr.length);
  for (let i = 0; i < arr.length; i++) {
    const v = arr[i];
    req(isNum(v), `${what}[${i}] is not a finite number`);
    out[i] = v;
  }
  return out;
}

/** Center of an environment preset (point value / t loc / normal mean). */
export function envCenter(spec) {
  if (!spec) return 0;
  if (spec.type === 'point') return spec.value;
  if (spec.type === 't') return spec.loc;
  if (spec.type === 'normal') return spec.mean;
  throw new ModelError(`unknown environment preset type ${spec.type}`);
}

/** Map a GOP candidate style to the engine's opponent type. */
export function oppTypeOf(g) {
  const t = (g.opp_type || g.style || '').toLowerCase();
  if (t.startsWith('maga')) return 'maga';
  if (t === 'moderate') return 'moderate';
  return 'traditional';
}

/**
 * Validate and index a model_params.json object.
 * @param {object} json parsed model_params.json
 * @param {{precision?: 'f32'|'f64'}} [opts]
 */
export function loadModel(json, opts = {}) {
  req(json && typeof json === 'object', 'not an object');
  for (const k of ['meta', 'national', 'units', 'errors', 'environment', 'transfer_pi', 'lean', 'style']) {
    req(json[k] != null, `missing top-level key "${k}"`);
  }
  const precision = opts.precision || 'f32';
  req(precision === 'f32' || precision === 'f64', `precision must be f32|f64`);

  const P = json.meta.n_param_draws;
  req(Number.isInteger(P) && P > 0, 'meta.n_param_draws must be a positive integer');

  // ---- national
  const nat = json.national;
  req(isNum(nat.E24), 'national.E24 missing');
  const evTotal = nat.ev_total ?? 538;
  const evWin = nat.ev_win ?? Math.floor(evTotal / 2) + 1;

  // ---- errors
  const factorNames = json.errors.factor_names;
  req(Array.isArray(factorNames) && factorNames.length > 0, 'errors.factor_names missing');
  const K = factorNames.length;

  // ---- units
  const unitsIn = json.units;
  req(Array.isArray(unitsIn) && unitsIn.length > 0, 'units must be a non-empty array');
  const U = unitsIn.length;
  req(U <= 255, 'too many units for Uint8 tipping index');
  const ids = unitsIn.map((u) => u.id);
  const unitIndex = new Map(ids.map((id, i) => [id, i]));
  req(unitIndex.size === U, 'duplicate unit ids');

  const ev = new Int32Array(U);
  const m24 = new Float64Array(U);
  const rel24 = new Float64Array(U);
  const rel20 = new Float64Array(U);
  const rel26 = new Float64Array(U);
  const G = new Float64Array(U);
  const Wt = new Float64Array(U);
  const Yt = new Float64Array(U);
  const sigmaIdio = new Float64Array(U);
  const districtSd = new Float64Array(U);
  const districtSdDefault = isNum(json.errors.district_sd) ? json.errors.district_sd : 1.5; // §5.1
  const F = new Float64Array(U * K);
  const parentIdx = new Int16Array(U).fill(-1);
  const types = [];
  let evSum = 0;
  unitsIn.forEach((u, i) => {
    req(typeof u.id === 'string', `units[${i}].id missing`);
    req(['state', 'district', 'dc'].includes(u.type), `units[${u.id}].type must be state|district|dc`);
    types.push(u.type);
    req(Number.isInteger(u.ev) && u.ev > 0, `units[${u.id}].ev must be a positive integer`);
    ev[i] = u.ev;
    evSum += u.ev;
    req(isNum(u.m24), `units[${u.id}].m24 missing`);
    m24[i] = u.m24;
    rel24[i] = isNum(u.rel24) ? u.rel24 : u.m24 - nat.E24;
    rel20[i] = isNum(u.rel20) ? u.rel20 : 0;
    rel26[i] = isNum(u.rel26) ? u.rel26 : 0;
    req(isNum(u.G), `units[${u.id}].G missing`);
    // k_s = 1 + u(G_s − 1) must stay > 0 for every |u| ≤ 1, i.e. 0 < G < 2 (§6.2).
    req(u.G > 0 && u.G < 2, `units[${u.id}].G = ${u.G} would allow k_s <= 0`);
    G[i] = u.G;
    Wt[i] = isNum(u.W_tilde) ? u.W_tilde : 0;
    Yt[i] = isNum(u.Y_tilde) ? u.Y_tilde : 0;
    if (u.type === 'district') {
      req(unitIndex.has(u.parent), `district ${u.id} has unknown parent ${u.parent}`);
      // per-unit district_sd (pipeline convention) → errors.district_sd → 1.5
      districtSd[i] = isNum(u.district_sd) ? u.district_sd : districtSdDefault;
    } else {
      req(Array.isArray(u.F) && u.F.length === K, `units[${u.id}].F must have ${K} loadings`);
      for (let k = 0; k < K; k++) {
        req(isNum(u.F[k]), `units[${u.id}].F[${k}] not a number`);
        F[i * K + k] = u.F[k];
      }
      req(isNum(u.sigma_idio) && u.sigma_idio >= 0, `units[${u.id}].sigma_idio missing`);
      sigmaIdio[i] = u.sigma_idio;
    }
  });
  unitsIn.forEach((u, i) => {
    if (u.type === 'district') {
      const p = unitIndex.get(u.parent);
      req(unitsIn[p].type !== 'district', `district ${u.id}: parent must be a state`);
      parentIdx[i] = p;
    }
  });
  req(evSum === evTotal, `EV sum is ${evSum}, expected ${evTotal}`);

  // children of each state (ME/NE districts), used for home-state effects
  const children = Array.from({ length: U }, () => []);
  for (let i = 0; i < U; i++) if (parentIdx[i] >= 0) children[parentIdx[i]].push(i);

  // ---- environment
  const env = json.environment;
  req(env.presets && typeof env.presets === 'object', 'environment.presets missing');
  for (const [name, spec] of Object.entries(env.presets)) {
    req(['point', 't', 'normal'].includes(spec.type), `environment.presets.${name}.type invalid`);
  }
  req(env.presets[env.default_preset], 'environment.default_preset not among presets');

  // ---- transfer π
  const tp = json.transfer_pi;
  const piDraws = numArray(tp.pi_draws, P, 'transfer_pi.pi_draws');

  // ---- lean
  const lean = { psi: json.lean.psi ?? 0.2, phi: json.lean.phi ?? 0, phiMax: json.lean.phi_max ?? 0.5 };

  // ---- style
  const st = json.style;
  req(st.coords && st.presets, 'style.coords / style.presets missing');
  const coords = {};
  for (const a of ARCHETYPES) {
    const c = st.coords[a];
    req(c && isNum(c.L) && isNum(c.P), `style.coords.${a} missing L/P`);
    coords[a] = { L: c.L, P: c.P, n: c.n ?? 0, nStates: c.n_states ?? 0, minNOk: c.min_n_ok !== false };
  }
  const presets = {};
  for (const [name, pr] of Object.entries(st.presets)) {
    const o = {
      beta_L: numArray(pr.beta_L, P, `style.presets.${name}.beta_L`),
      beta_P: numArray(pr.beta_P, P, `style.presets.${name}.beta_P`),
      beta_PW: pr.beta_PW?.length ? numArray(pr.beta_PW, P, `style.presets.${name}.beta_PW`) : new Float64Array(P),
      beta_LY: pr.beta_LY?.length ? numArray(pr.beta_LY, P, `style.presets.${name}.beta_LY`) : new Float64Array(P),
      omega_maga: numArray(pr.omega_maga, P, `style.presets.${name}.omega_maga`),
      omega_mod: pr.omega_mod?.length ? numArray(pr.omega_mod, P, `style.presets.${name}.omega_mod`) : new Float64Array(P),
      u: {},
      delta: {},
    };
    for (const a of ARCHETYPES) {
      const uArr = pr.u?.[a];
      o.u[a] = a === REFERENCE_ARCHETYPE || !uArr?.length || !coords[a].minNOk
        ? new Float64Array(P)
        : numArray(uArr, P, `style.presets.${name}.u.${a}`);
      // δ_a,p: prefer the exported derived draws; else derive δ = β_L(L̄−1) + β_P·P̄ + u.
      const d = pr.delta?.[a];
      if (d?.length) o.delta[a] = numArray(d, P, `style.presets.${name}.delta.${a}`);
      else {
        const arr = new Float64Array(P);
        for (let p = 0; p < P; p++) arr[p] = o.beta_L[p] * (coords[a].L - 1) + o.beta_P[p] * coords[a].P + o.u[a][p];
        o.delta[a] = arr;
      }
    }
    o.sdRatio = pr.sd_ratio || {};
    presets[name] = o;
  }
  req(presets.agnostic, 'style.presets.agnostic missing');
  // Which preset the 2028 sims use when a call names none (O-8: history-based when exported).
  const defaultPreset = presets[st.default_preset] ? st.default_preset : 'agnostic';
  const interactions = st.interactions || {};
  const gateOk = {
    PW: !!interactions.beta_PW?.gate_passed,
    LY: !!interactions.beta_LY?.gate_passed,
  };

  // ---- candidates
  const dems = new Map();
  (json.candidates_dem || []).forEach((c, i) => {
    req(c.id, `candidates_dem[${i}].id missing`);
    req(ARCHETYPES.includes(c.archetype), `candidates_dem.${c.id}.archetype "${c.archetype}" unknown`);
    if (c.track?.c_draws?.length) numArray(c.track.c_draws, P, `candidates_dem.${c.id}.track.c_draws`);
    dems.set(c.id, c);
  });
  const gops = new Map();
  (json.candidates_gop || []).forEach((c, i) => {
    req(c.id, `candidates_gop[${i}].id missing`);
    if (c.track?.c_draws?.length) numArray(c.track.c_draws, P, `candidates_gop.${c.id}.track.c_draws`);
    gops.set(c.id, c);
  });

  return {
    json,
    meta: json.meta,
    precision,
    P,
    U,
    K,
    ids,
    names: unitsIn.map((u) => u.name ?? u.id),
    types,
    unitIndex,
    ev,
    m24, rel24, rel20, rel26, G, Wt, Yt, sigmaIdio, districtSd, F, parentIdx, children,
    E24: nat.E24,
    evTotal,
    evWin,
    env,
    piSpec: tp.sampled,
    piDraws,
    lean,
    coords,
    hull: Array.isArray(st.hull) ? st.hull : null,
    presets,
    defaultPreset,
    gaussian: st.gaussian || null,
    gateOk,
    dems,
    gops,
    homeEffect: { mean: json.home_effect?.mean ?? 2, sd: json.home_effect?.sd ?? 1.5, vp: json.home_effect?.vp ?? 0.5 },
    rho: json.rho?.default ?? 0.5,
    trackShrink: { tauC: json.track_shrinkage?.tau_c ?? 2, sigmaR: json.track_shrinkage?.sigma_r ?? 5 },
    primary: json.primary || null,
    sim5: json.sim5 || null,
    _cache: { banks: new Map(), eps: new Map(), dial: new Map() },
  };
}

/** Unit indices covered by a home-state code: the state plus its districts (ME/NE). */
export function homeUnits(model, code) {
  if (!code) return [];
  const i = model.unitIndex.get(code);
  if (i == null) return [];
  return [i, ...model.children[i]];
}
