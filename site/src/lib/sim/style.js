// Style effects per parameter draw p (METHODOLOGY §3, §5.4, §5.5, §6.5 styleDelta).

import { ARCHETYPES, REFERENCE_ARCHETYPE } from './model.js';
import { substream } from './rng.js';

// ---------------------------------------------------------------- small linear algebra

function inv(Ain) {
  const n = Ain.length;
  const A = Ain.map((r) => r.slice());
  const I = Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => (i === j ? 1 : 0)));
  for (let c = 0; c < n; c++) {
    let piv = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(A[r][c]) > Math.abs(A[piv][c])) piv = r;
    if (Math.abs(A[piv][c]) < 1e-14) throw new Error('singular matrix in trust dial');
    [A[c], A[piv]] = [A[piv], A[c]];
    [I[c], I[piv]] = [I[piv], I[c]];
    const d = A[c][c];
    for (let j = 0; j < n; j++) { A[c][j] /= d; I[c][j] /= d; }
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = A[r][c];
      if (f === 0) continue;
      for (let j = 0; j < n; j++) { A[r][j] -= f * A[c][j]; I[r][j] -= f * I[c][j]; }
    }
  }
  return I;
}

function chol(A) {
  const n = A.length;
  const L = Array.from({ length: n }, () => new Array(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j <= i; j++) {
      let s = A[i][j];
      for (let k = 0; k < j; k++) s -= L[i][k] * L[j][k];
      if (i === j) {
        if (s <= 0) throw new Error('trust dial covariance not positive definite');
        L[i][i] = Math.sqrt(s);
      } else L[i][j] = s / L[j][j];
    }
  }
  return L;
}

const matVec = (A, v) => A.map((r) => r.reduce((s, x, j) => s + x * v[j], 0));
const matAdd = (A, B, a = 1, b = 1) => A.map((r, i) => r.map((x, j) => a * x + b * B[i][j]));

/**
 * Gaussian power-prior trust dial (§3.3):
 *   Σ_post = (Σ0⁻¹/k² + α·V̂⁻¹)⁻¹,  μ_post = Σ_post·(Σ0⁻¹μ0/k² + α·V̂⁻¹b̂)
 * Returns { mu, Sigma } for [β_L, β_P, β_PW, β_LY].
 */
export function dialPosterior(model, { k = 1, alpha = 1, prior = 'agnostic' }) {
  const g = model.gaussian;
  if (!g) throw new Error('model has no style.gaussian block');
  if (g.dial_enabled === false) throw new Error('trust dial disabled by validation (V15); use a preset');
  const mu0 = g.mu0[prior];
  const S0 = g.Sigma0[prior];
  if (!mu0 || !S0) throw new Error(`no dial prior "${prior}"`);
  const S0i = inv(S0);
  const kk = k === Infinity ? 0 : 1 / (k * k);
  let precision = S0i.map((r) => r.map((x) => x * kk));
  let rhs = matVec(S0i, mu0).map((x) => x * kk);
  if (alpha > 0) {
    const Vi = inv(g.Vhat);
    precision = matAdd(precision, Vi, 1, alpha);
    rhs = rhs.map((x, i) => x + alpha * matVec(Vi, g.bhat)[i]);
  }
  const Sigma = inv(precision);
  return { mu: matVec(Sigma, rhs), Sigma };
}

function dialZ(model) {
  let z = model._cache.dial.get('z');
  if (z) return z;
  const rng = substream(model.meta.seed ?? 1, 'trust-dial');
  z = new Float64Array(model.P * 4);
  for (let i = 0; i < z.length; i++) z[i] = rng.normal();
  model._cache.dial.set('z', z);
  return z;
}

/** Parameter-draw structure for a preset name or a dial setting (CRN: same z for every dial). */
export function styleDraws(model, sel = {}) {
  if (sel.dial) {
    const { k = 1, alpha = 1, prior = 'agnostic' } = sel.dial;
    const key = `dial|${k}|${alpha}|${prior}`;
    const hit = model._cache.dial.get(key);
    if (hit) return hit;
    const { mu, Sigma } = dialPosterior(model, { k, alpha, prior });
    const L = chol(Sigma);
    const z = dialZ(model);
    const P = model.P;
    const cols = [new Float64Array(P), new Float64Array(P), new Float64Array(P), new Float64Array(P)];
    for (let p = 0; p < P; p++) {
      for (let i = 0; i < 4; i++) {
        let v = mu[i];
        for (let j = 0; j <= i; j++) v += L[i][j] * z[p * 4 + j];
        cols[i][p] = v;
      }
    }
    // u_a and ω are outside the 4×4 Gaussian block: they come from the matching preset.
    const base = model.presets[prior] || model.presets.agnostic;
    const out = {
      beta_L: cols[0], beta_P: cols[1],
      beta_PW: model.gateOk.PW ? cols[2] : new Float64Array(P),
      beta_LY: model.gateOk.LY ? cols[3] : new Float64Array(P),
      u: base.u, omega_maga: base.omega_maga, omega_mod: base.omega_mod,
      delta: {},
    };
    for (const a of ARCHETYPES) {
      const c = model.coords[a];
      const d = new Float64Array(P);
      for (let p = 0; p < P; p++) d[p] = out.beta_L[p] * (c.L - 1) + out.beta_P[p] * c.P + out.u[a][p];
      out.delta[a] = d;
    }
    model._cache.dial.set(key, out);
    return out;
  }
  const name = sel.preset ?? model.defaultPreset ?? 'agnostic';
  const pr = model.presets[name];
  if (!pr) throw new Error(`unknown style preset "${name}"`);
  if (model.gateOk.PW && model.gateOk.LY) return pr;
  // §3.8: interactions below minimum N are set to 0 (not prior draws) in 2028 translations.
  const key = `gated|${name}`;
  let g = model._cache.dial.get(key);
  if (!g) {
    g = {
      ...pr,
      beta_PW: model.gateOk.PW ? pr.beta_PW : new Float64Array(model.P),
      beta_LY: model.gateOk.LY ? pr.beta_LY : new Float64Array(model.P),
    };
    model._cache.dial.set(key, g);
  }
  return g;
}

/** π draws per p: sampled (exported draws, aligned with p) or fixed. */
export function piDraws(model, pi = { mode: 'sampled' }) {
  const P = model.P;
  if (pi.mode === 'fixed') {
    const v = pi.value ?? 1;
    return new Float64Array(P).fill(v);
  }
  return model.piDraws;
}

// ---------------------------------------------------------------- coordinates off the centroids

/** Inverse-distance-weighted archetype deviation u at (L, P) for each p. */
export function idwU(model, draws, L, Pc) {
  const P = model.P;
  const w = [];
  let exact = null;
  for (const a of ARCHETYPES) {
    const c = model.coords[a];
    const d2 = (c.L - L) ** 2 + (c.P - Pc) ** 2;
    if (d2 < 1e-12) exact = a;
    w.push(1 / d2);
  }
  const out = new Float64Array(P);
  if (exact) {
    out.set(draws.u[exact]);
    return out;
  }
  const W = w.reduce((s, x) => s + x, 0);
  ARCHETYPES.forEach((a, i) => {
    if (a === REFERENCE_ARCHETYPE) return; // u_ml ≡ 0 still carries weight (pulls toward 0)
    const ua = draws.u[a];
    const wi = w[i] / W;
    for (let p = 0; p < P; p++) out[p] += wi * ua[p];
  });
  return out;
}

/** δ(L, P)_p = β_L(L−1) + β_P·P + u_IDW(L, P). */
export function deltaAt(model, draws, L, Pc) {
  const u = idwU(model, draws, L, Pc);
  const d = new Float64Array(model.P);
  for (let p = 0; p < model.P; p++) d[p] = draws.beta_L[p] * (L - 1) + draws.beta_P[p] * Pc + u[p];
  return d;
}

function convexHull(points) {
  const pts = points.map((p) => [p[0], p[1]]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (pts.length < 3) return pts;
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
    lower.push(p);
  }
  const upper = [];
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
    upper.push(p);
  }
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}

export function getHull(model) {
  if (model.hull && model.hull.length >= 3) return model.hull;
  return convexHull(ARCHETYPES.map((a) => [model.coords[a].L, model.coords[a].P]));
}

function pointInPolygon(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function segDist(x, y, [x1, y1], [x2, y2]) {
  const dx = x2 - x1, dy = y2 - y1;
  const l2 = dx * dx + dy * dy;
  let t = l2 ? ((x - x1) * dx + (y - y1) * dy) / l2 : 0;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(x - (x1 + t * dx), y - (y1 + t * dy));
}

/** Distance from (L, P) to the hull (0 when inside or on the boundary). */
export function hullDistance(model, L, Pc) {
  const poly = getHull(model);
  let d = Infinity;
  for (let i = 0; i < poly.length; i++) d = Math.min(d, segDist(L, Pc, poly[i], poly[(i + 1) % poly.length]));
  if (d < 1e-9) return 0;
  return pointInPolygon(L, Pc, poly) ? 0 : d;
}

export function nearestCentroidDistance(model, L, Pc) {
  let d = Infinity;
  for (const a of ARCHETYPES) d = Math.min(d, Math.hypot(model.coords[a].L - L, model.coords[a].P - Pc));
  return d;
}

// ---------------------------------------------------------------- the public styleDelta

/** Opponent effect ω per p for an opponent type ('traditional' → 0). */
export function omegaFor(draws, opponent) {
  if (opponent === 'maga') return draws.omega_maga;
  if (opponent === 'moderate') return draws.omega_mod;
  return null;
}

/**
 * Per-p style components used by every sim.
 * Returns { delta, pi, omegaMaga, omegaMod, draws } with Float64Array(P) entries.
 */
export function styleComponents(model, opts = {}) {
  const draws = styleDraws(model, opts.dial ? { dial: opts.dial } : { preset: opts.preset });
  let delta;
  if (opts.coords) delta = deltaAt(model, draws, opts.coords.L, opts.coords.P);
  else {
    const a = opts.archetype ?? REFERENCE_ARCHETYPE;
    if (!draws.delta[a]) throw new Error(`unknown archetype "${a}"`);
    delta = draws.delta[a];
  }
  return { delta, pi: piDraws(model, opts.pi), draws };
}

/**
 * styleDelta (§6.5): π_p·(δ_a,p + ω_p) per parameter draw.
 * For opponent 'generic' returns the per-p mean over the Bernoulli(0.5) MAGA mixture,
 * π_p·(δ_a,p + 0.5·ω_maga,p); the sims evaluate the mixture exactly.
 */
export function styleDelta(model, opts = {}) {
  const { delta, pi, draws } = styleComponents(model, opts);
  const P = model.P;
  const out = model.precision === 'f64' ? new Float64Array(P) : new Float32Array(P);
  const opp = opts.opponent ?? 'generic';
  const om = opp === 'generic' ? draws.omega_maga : omegaFor(draws, opp);
  const wt = opp === 'generic' ? 0.5 : 1;
  for (let p = 0; p < P; p++) out[p] = pi[p] * (delta[p] + (om ? wt * om[p] : 0));
  return out;
}

/**
 * Opponent mixture components for the bank pass: [{ weight, Delta: Float64Array(P) }].
 * Generic → two components (traditional, MAGA) at 0.5 each.
 * `extra` (Float64Array P or null) is added to every component (track records).
 */
export function deltaComponents(model, comps, opponent, extra = null) {
  const { delta, pi, draws } = comps;
  const P = model.P;
  const build = (om) => {
    const d = new Float64Array(P);
    for (let p = 0; p < P; p++) d[p] = pi[p] * (delta[p] + (om ? om[p] : 0)) + (extra ? extra[p] : 0);
    return d;
  };
  if (opponent === 'generic' || opponent == null) {
    return [
      { weight: 0.5, opp: 'traditional', Delta: build(null) },
      { weight: 0.5, opp: 'maga', Delta: build(draws.omega_maga) },
    ];
  }
  return [{ weight: 1, opp: opponent, Delta: build(omegaFor(draws, opponent)) }];
}
