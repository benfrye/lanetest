// Shared helpers for the simulation stage components (chapters 4 and 5).
// Everything numeric comes from ctx.data.params (model_params.json) or the worker; nothing
// model-specific is hard-coded here, so a re-fit with the same schema drops straight in.

import { envCenter } from '../../lib/sim/model.js';
import { StaleResultError } from '../../lib/sim/client.js';
import { STATE_TILES } from '../../lib/stage/layouts.js';

export { STATE_TILES };

// ------------------------------------------------------------------ formatting

/** National environment / margin label: D+3, R+2, Even. Rounds to `digits`. */
export function fmtE(v, digits = 0) {
  if (v == null || !Number.isFinite(v)) return '–';
  const r = Number(Math.abs(v).toFixed(digits));
  if (r === 0) return 'Even';
  return `${v > 0 ? 'D' : 'R'}+${r.toFixed(digits)}`;
}

/** Percent from a probability, integer. */
export const pct = (p) => (p == null || !Number.isFinite(p) ? '–' : `${Math.round(p * 100)}%`);

/** "44–82%" for an interval of probabilities. */
export const pctRange = ([lo, hi]) => `${Math.round(lo * 100)}–${Math.round(hi * 100)}%`;

/** Signed number with a real minus sign. */
export function signed(v, digits = 1) {
  if (v == null || !Number.isFinite(v)) return '–';
  const s = Math.abs(v).toFixed(digits);
  if (Number(s) === 0) return (0).toFixed(digits);
  return `${v > 0 ? '+' : '−'}${s}`;
}

export const fmtInt = (v) => Math.round(v).toLocaleString('en-US');

// ------------------------------------------------------------------ params helpers

export function params(ctx) {
  return ctx?.data?.params ?? {};
}

/** Center of the default environment preset (e.g. the D+3 used by the durable view). */
export function defaultEnvCenter(ctx) {
  const env = params(ctx).environment;
  if (!env) return 0;
  return envCenter(env.presets?.[env.default_preset]);
}

export function envSlider(ctx) {
  const s = params(ctx).environment?.slider ?? {};
  return { min: s.min ?? -10, max: s.max ?? 15, step: s.step ?? 0.5 };
}

export function piSlider(ctx) {
  const s = params(ctx).transfer_pi?.slider ?? {};
  return { min: s.min ?? 0.5, max: s.max ?? 2, step: s.step ?? 0.05 };
}

/** π option for the engine: reader.pi null/undefined means "sampled" (the §6.6 default). */
export function piOpt(reader) {
  const v = reader?.pi;
  return v == null || !Number.isFinite(v) ? { mode: 'sampled' } : { mode: 'fixed', value: v };
}

export function envHistory(ctx) {
  return { mode: 'dist', preset: params(ctx).environment?.default_preset ?? 'history' };
}

export function envPoint(v) {
  return { mode: 'point', value: v };
}

/** Human description of the default environment distribution, e.g. "a range centered on an even national vote". */
export function envHistoryLabel(ctx) {
  const c = defaultEnvCenter(ctx);
  return Math.abs(c) < 0.05 ? 'a range centered on an even national vote' : `a range centered on ${fmtE(c)}`;
}

// The national-mood choices a sim offers: the default range (an even vote), the post-midterm
// historical average (D+3) when the params carry it, and the reader's own fixed value.
export function envChoices(ctx, readerEnv, narrow = false) {
  const env = params(ctx).environment ?? {};
  const fixed = fmtE(readerEnv, 1);
  const out = [{ value: 'default', label: narrow ? 'Unknown' : 'Mood unknown' }];
  if (env.presets?.history && env.default_preset !== 'history') {
    out.push({ value: 'history', label: narrow ? `Past avg. ${fmtE(envCenter(env.presets.history))}` : `Past average (${fmtE(envCenter(env.presets.history))})` });
  }
  out.push({ value: 'mine', label: `Exactly ${/^even$/i.test(fixed) ? 'even' : fixed}` });
  return out;
}
export function envFor(ctx, mode, readerEnv) {
  if (mode === 'mine') return envPoint(readerEnv);
  if (mode === 'history' && params(ctx).environment?.presets?.history) return { mode: 'dist', preset: 'history' };
  return envHistory(ctx);
}
export function envLabelFor(ctx, mode, readerEnv) {
  if (mode === 'mine') return /^even$/i.test(fmtE(readerEnv, 1)) ? 'an exactly tied national vote' : `a national vote of exactly ${fmtE(readerEnv, 1)}`;
  if (mode === 'history') return `an unknown national mood leaning ${fmtE(envCenter(params(ctx).environment.presets.history))}, the post-midterm average`;
  return 'an unknown national mood';
}

/** Short "as of" text from params.meta.data_as_of ("2026-11-04 ~11:10 ET (…)"). */
export function asOf(ctx) {
  const raw = params(ctx).meta?.data_as_of ?? ctx?.data?.manifest?.synced_at ?? '';
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T]+([^()]*?))?\s*(?:\(|$)/.exec(raw);
  if (!m) return { short: raw, full: raw };
  const months = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
  const time = (m[4] ?? '').replace(/^~/, '').trim();
  const short = `${months[+m[2] - 1]} ${+m[3]}${time && !time.includes('T') ? `, ${time}` : ''}`;
  return { short, full: raw };
}

export function underReview(ctx) {
  return ctx?.data?.manifest?.params_cleared === false;
}

/** True when the published style draws are prior-only (fit level 5 / publish blocked). */
export function priorOnly(ctx) {
  const p = params(ctx);
  const src = p.style?.presets?.agnostic?.source ?? '';
  return /prior/i.test(src) || p.copy_flags?.publish_blocked === true;
}

export function unitName(ctx, id) {
  const u = params(ctx).units?.find((x) => x.id === id);
  return u?.name ?? id;
}

/** Unit metadata in params order: [{ id, name, ev, parent }]. */
export function unitList(ctx) {
  return (params(ctx).units ?? []).map((u) => ({ id: u.id, name: u.name, ev: u.ev, parent: u.parent ?? null, m24: u.m24 }));
}

export function candidateName(ctx, id) {
  const p = params(ctx);
  return (p.candidates_dem ?? []).concat(p.candidates_gop ?? []).find((c) => c.id === id)?.name ?? id;
}

export const lastName = (name) => {
  const parts = name.replace(/\s+(Jr\.|Sr\.|III|II)$/, '').split(' ');
  const base = parts[parts.length - 1];
  return /Jr\.$/.test(name) ? `${base} Jr.` : base;
};

// ------------------------------------------------------------------ sim calls

export const isStale = (e) => e instanceof StaleResultError || e?.name === 'StaleResultError';

/**
 * Coalescing caller for slider-driven sim calls: at most one request in flight per caller,
 * the latest arguments win, intermediate ones are dropped. Also uses a client channel so a
 * newer request from elsewhere on the same channel supersedes an older one.
 *   const go = latest((args) => ctx.sim.simCustom(args, {}, { channel: 'custom' }), onResult, onError)
 */
export function latest(fn, onResult, onError) {
  let inflight = false;
  let queued = null;
  let gen = 0;
  async function pump(args, g) {
    inflight = true;
    try {
      const r = await fn(args);
      if (g === gen && queued == null) onResult(r, args);
    } catch (e) {
      if (!isStale(e) && g === gen && queued == null) onError?.(e);
    } finally {
      inflight = false;
      if (queued) {
        const q = queued;
        queued = null;
        pump(q.args, q.g);
      }
    }
  }
  const call = (args) => {
    gen++;
    if (inflight) queued = { args, g: gen };
    else pump(args, gen);
  };
  call.cancel = () => {
    gen++;
    queued = null;
  };
  return call;
}

// ------------------------------------------------------------------ color scales (tokens only)

// Party diverging scale: --rep … --mid … --dem, mixed in OKLab. Returns CSS color strings.
const mix = (tok, amt) => (amt <= 0 ? 'var(--mid)' : amt >= 100 ? `var(${tok})` : `color-mix(in oklab, var(${tok}) ${amt}%, var(--mid))`);

/** Win-probability bins (P(D)). Symmetric around 50%. */
export const PROB_BINS = [
  { lo: 0, hi: 0.05, label: 'R ≥95%', fill: mix('--rep', 100) },
  { lo: 0.05, hi: 0.2, label: 'R 80–95%', fill: mix('--rep', 66) },
  { lo: 0.2, hi: 0.4, label: 'R 60–80%', fill: mix('--rep', 34) },
  { lo: 0.4, hi: 0.6, label: 'Toss-up', fill: mix('--rep', 0) },
  { lo: 0.6, hi: 0.8, label: 'D 60–80%', fill: mix('--dem', 34) },
  { lo: 0.8, hi: 0.95, label: 'D 80–95%', fill: mix('--dem', 66) },
  { lo: 0.95, hi: 1.0001, label: 'D ≥95%', fill: mix('--dem', 100) },
];
export function probFill(p) {
  if (p == null || !Number.isFinite(p)) return 'var(--surface-2)';
  return (PROB_BINS.find((b) => p >= b.lo && p < b.hi) ?? PROB_BINS[PROB_BINS.length - 1]).fill;
}

/** Margin bins (D-positive points). */
export const MARGIN_BINS = [
  { lo: -Infinity, hi: -15, label: 'R 15+', fill: mix('--rep', 100) },
  { lo: -15, hi: -5, label: 'R 5–15', fill: mix('--rep', 66) },
  { lo: -5, hi: -1, label: 'R 1–5', fill: mix('--rep', 34) },
  { lo: -1, hi: 1, label: 'Within 1', fill: mix('--rep', 0) },
  { lo: 1, hi: 5, label: 'D 1–5', fill: mix('--dem', 34) },
  { lo: 5, hi: 15, label: 'D 5–15', fill: mix('--dem', 66) },
  { lo: 15, hi: Infinity, label: 'D 15+', fill: mix('--dem', 100) },
];
export function marginFill(m) {
  if (m == null || !Number.isFinite(m)) return 'var(--surface-2)';
  return (MARGIN_BINS.find((b) => m >= b.lo && m < b.hi) ?? MARGIN_BINS[MARGIN_BINS.length - 1]).fill;
}

/** Continuous P(win) fill in 10-point steps (heatmap). */
export function probFill10(p) {
  if (p == null || !Number.isFinite(p)) return 'var(--surface-2)';
  const b = Math.min(9, Math.max(0, Math.floor(p * 10))); // 0..9
  const d = b - 4.5; // −4.5..4.5
  const amt = Math.round((Math.abs(d) - 0.5) * 25); // 0,25,50,75,100
  return d < 0 ? mix('--rep', amt) : mix('--dem', amt);
}

// ------------------------------------------------------------------ misc

export function prefersReducedMotion() {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Read CSS custom properties off an element (canvas drawing). */
export function tokens(el, names) {
  const cs = getComputedStyle(el);
  return Object.fromEntries(names.map((n) => [n, cs.getPropertyValue(n).trim()]));
}

/** Subscribe to color-scheme changes; returns an unsubscribe fn. */
export function onSchemeChange(fn) {
  if (typeof matchMedia !== 'function') return () => {};
  const mq = matchMedia('(prefers-color-scheme: dark)');
  mq.addEventListener('change', fn);
  return () => mq.removeEventListener('change', fn);
}

/** Small deterministic PRNG (mulberry32) for UI-only shuffles. */
export function prng(seed = 1) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Quantile of an integer histogram (index = value). */
export function histQuantile(hist, q) {
  let n = 0;
  for (let i = 0; i < hist.length; i++) n += hist[i];
  const target = q * (n - 1);
  let cum = 0;
  for (let v = 0; v < hist.length; v++) {
    cum += hist[v];
    if (cum > target) return v;
  }
  return hist.length - 1;
}

export const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

// ------------------------------------------------------------------ claims-ledger gates

/** Upper 0.9 quantile of a Student t (Cornish–Fisher expansion; fine for df ≥ 3). */
function t90(df) {
  const z = 1.2815516;
  if (!Number.isFinite(df) || df > 1e6) return z;
  const z3 = z ** 3, z5 = z ** 5;
  return z + (z3 + z) / (4 * df) + (5 * z5 + 16 * z3 + 3 * z) / (96 * df * df);
}

/** Width of the 80% interval of the default environment distribution (points). */
export function envWidth80(ctx) {
  const env = params(ctx).environment;
  const s = env?.presets?.[env.default_preset];
  if (!s) return 0;
  if (s.type === 't') return 2 * s.scale * t90(s.df);
  if (s.type === 'normal') return 2 * 1.2815516 * s.sd;
  return 0;
}

/**
 * C7 ("How good a year 2028 is matters more than which kind of Democrat runs") is licensed
 * when the E 80% width > 2 × max_a of the 80% upper bound of |π·δ_a| (claims ledger §8).
 */
export function c7Licensed(ctx, preset = 'agnostic') {
  const p = params(ctx);
  const d = p.style?.presets?.[preset]?.delta;
  const pi = p.transfer_pi?.pi_draws;
  if (!d || !pi) return false;
  let worst = 0;
  for (const a of Object.keys(d)) {
    const arr = d[a].map((x, i) => Math.abs(x * pi[i % pi.length])).sort((x, y) => x - y);
    worst = Math.max(worst, arr[Math.floor(0.9 * (arr.length - 1))]);
  }
  return envWidth80(ctx) > 2 * worst;
}

/** The four exact style presets (the continuous trust dial is offered only when dial_enabled). */
export const PRESET_LABELS = {
  agnostic: 'Agnostic',
  literature: 'Literature',
  discount: 'Discounted',
  data_only: '2026 data only',
};
export function presetOptions(ctx) {
  return Object.keys(params(ctx).style?.presets ?? { agnostic: 1 }).map((k) => ({ value: k, label: PRESET_LABELS[k] ?? k }));
}

/** Caveat for a lane whose estimate rests on too few 2026 races to stand on its own. */
// O-9: the 2028 lane estimates use past elections (history or the 2026+history blend) and
// leave out center populists, who are too rare in every cycle to estimate.
export function usesHistory(ctx) {
  return ['history', 'blend'].includes(params(ctx).style?.default_preset);
}
export function lanes2028(ctx, list) {
  return usesHistory(ctx) ? list.filter((a) => (a.id ?? a) !== 'center_populist') : list;
}

export function thinNote(ctx, lane) {
  const st = params(ctx).style ?? {};
  const name = ARCH_LABEL[lane] ?? lane;
  if (usesHistory(ctx)) {
    // Past elections fill in every lane except center populists, who are rare in every year.
    return lane === 'center_populist'
      ? `${name}s are too rare to measure, in 2026 or in past elections, so their number comes from the model's overall pattern. Treat it as a rough guess.`
      : '';
  }
  const c = st.coords?.[lane];
  if (!c || c.min_n_ok !== false) return '';
  return `${name}s rest on only ${c.n} ${c.n === 1 ? 'race' : 'races'} from 2026, so their number comes mostly from the model's overall pattern, not their own results. Treat it as a rough guess.`;
}
const ARCH_LABEL = { progressive: 'Progressive', left_populist: 'Left populist', center_populist: 'Center populist', mainstream_liberal: 'Mainstream liberal', moderate: 'Moderate' };
