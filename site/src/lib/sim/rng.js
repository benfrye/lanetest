// Seeded PRNG for the simulation engine (METHODOLOGY §6.1).
//
// xoshiro128** for uniforms, Box–Muller for normals, Marsaglia–Tsang for gamma,
// unit-variance t5 as z·sqrt(3/5)/sqrt(χ²_5/5) with χ²_5 = 2·Gamma(2.5).
//
// Common random numbers: every consumer derives an independent sub-stream from
// (seed, label) with `substream`, so e.g. the outcome-error stream of a bank is the
// same whatever u/ψ/φ are, and the E-draw stream is the same whatever the errors are.

const TWO_NEG_32 = 2 ** -32;

/** splitmix32: used only to expand a seed into xoshiro state words. */
function splitmix32(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x9e3779b9) >>> 0;
    let z = s;
    z = Math.imul(z ^ (z >>> 16), 0x85ebca6b) >>> 0;
    z = Math.imul(z ^ (z >>> 13), 0xc2b2ae35) >>> 0;
    return (z ^ (z >>> 16)) >>> 0;
  };
}

/** FNV-1a 32-bit hash of a string label, to derive sub-stream seeds. */
export function hashLabel(label) {
  let h = 0x811c9dc5;
  const s = String(label);
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

export class Rng {
  constructor(seed = 1) {
    const sm = splitmix32(seed >>> 0);
    this.s0 = sm(); this.s1 = sm(); this.s2 = sm(); this.s3 = sm();
    if ((this.s0 | this.s1 | this.s2 | this.s3) === 0) this.s0 = 1;
    this._spare = 0;
    this._hasSpare = false;
  }

  /** Next uint32 (xoshiro128**). */
  nextU32() {
    const s0 = this.s0, s1 = this.s1, s2 = this.s2, s3 = this.s3;
    const r = Math.imul(rotl(Math.imul(s1, 5), 7), 9) >>> 0;
    const t = s1 << 9;
    let n2 = s2 ^ s0;
    let n3 = s3 ^ s1;
    const n1 = s1 ^ n2;
    const n0 = s0 ^ n3;
    n2 ^= t;
    n3 = rotl(n3, 11);
    this.s0 = n0 >>> 0; this.s1 = n1 >>> 0; this.s2 = n2 >>> 0; this.s3 = n3 >>> 0;
    return r;
  }

  /** Uniform on (0, 1): never exactly 0 (safe for log). */
  uniform() {
    return (this.nextU32() + 0.5) * TWO_NEG_32;
  }

  /** Standard normal via Box–Muller (polar-free, cached pair). */
  normal() {
    if (this._hasSpare) {
      this._hasSpare = false;
      return this._spare;
    }
    const u1 = this.uniform();
    const u2 = this.uniform();
    const r = Math.sqrt(-2 * Math.log(u1));
    const th = 2 * Math.PI * u2;
    this._spare = r * Math.sin(th);
    this._hasSpare = true;
    return r * Math.cos(th);
  }

  /**
   * Standard normal by the polar (Marsaglia) form of Box–Muller: no trig, so ~2× faster.
   * Used only by the primary sim (Sim 3), which has no Python parity requirement; every
   * parity-tested path (banks, Sims 1/2/4/5) uses `normal()`. Shares the spare cache.
   */
  normalPolar() {
    if (this._hasSpare) {
      this._hasSpare = false;
      return this._spare;
    }
    let u, v, q;
    do {
      u = 2 * this.uniform() - 1;
      v = 2 * this.uniform() - 1;
      q = u * u + v * v;
    } while (q >= 1 || q === 0);
    const f = Math.sqrt((-2 * Math.log(q)) / q);
    this._spare = v * f;
    this._hasSpare = true;
    return u * f;
  }

  /** Gamma(shape, 1) by Marsaglia–Tsang (shape < 1 boosted). */
  gamma(shape) {
    if (shape < 1) {
      const g = this.gamma(shape + 1);
      return g * Math.pow(this.uniform(), 1 / shape);
    }
    const d = shape - 1 / 3;
    const c = 1 / Math.sqrt(9 * d);
    for (;;) {
      let x, v;
      do {
        x = this.normal();
        v = 1 + c * x;
      } while (v <= 0);
      v = v * v * v;
      const u = this.uniform();
      const x2 = x * x;
      if (u < 1 - 0.0331 * x2 * x2) return d * v;
      if (Math.log(u) < 0.5 * x2 + d * (1 - v + Math.log(v))) return d * v;
    }
  }

  /** Student-t with df degrees of freedom, *not* rescaled (variance df/(df-2)). */
  studentT(df) {
    const z = this.normal();
    const chi2 = 2 * this.gamma(df / 2);
    return z / Math.sqrt(chi2 / df);
  }

  /** Unit-variance t5: z·sqrt(3/5)/sqrt(χ²_5/5) (§6.1). */
  t5Unit() {
    return this.studentT(5) * SQRT_3_5;
  }
}

const SQRT_3_5 = Math.sqrt(3 / 5);

function rotl(x, k) {
  return (x << k) | (x >>> (32 - k));
}

/** Independent sub-stream for (seed, label). */
export function substream(seed, label) {
  const h = hashLabel(label);
  const s = (Math.imul((seed >>> 0) ^ 0x5bd1e995, 0x27d4eb2d) ^ h) >>> 0;
  return new Rng(s);
}

/** Draw a sample from a distribution spec as used in model_params.json. */
export function drawFromSpec(rng, spec) {
  switch (spec.type) {
    case 'point':
      return spec.value;
    case 'normal':
      return spec.mean + spec.sd * rng.normal();
    case 't':
      return spec.loc + spec.scale * rng.studentT(spec.df);
    case 'lognormal': {
      let v = Math.exp(spec.mu + spec.sigma * rng.normal());
      if (spec.clip) v = Math.min(spec.clip[1], Math.max(spec.clip[0], v));
      return v;
    }
    default:
      throw new Error(`Unknown distribution type: ${spec.type}`);
  }
}
