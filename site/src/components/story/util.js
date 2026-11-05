// Shared helpers for the story components. Every number shown comes from ctx.data;
// these only format, look things up, and read flags.
import { ARCHETYPES, ARCHETYPE_BY_ID } from '../../lib/archetypes.js';

export { ARCHETYPES, ARCHETYPE_BY_ID };

const MINUS = '−';

// Signed number: +1.2 / −3.4 / 0.0.
export function signed(v, dp = 1) {
  if (v == null || Number.isNaN(+v)) return '–';
  const r = +(+v).toFixed(dp);
  if (r === 0) return (0).toFixed(dp);
  return (r > 0 ? '+' : MINUS) + Math.abs(r).toFixed(dp);
}

// Party margin: D+4.1 / R+13.2 / even.
export function margin(v, dp = 1) {
  if (v == null || Number.isNaN(+v)) return '–';
  const r = +(+v).toFixed(dp);
  if (r === 0) return 'even';
  return (r > 0 ? 'D+' : 'R+') + Math.abs(r).toFixed(dp);
}

export function num(v, dp = 1) {
  if (v == null || Number.isNaN(+v)) return '–';
  return (+v < 0 ? MINUS : '') + Math.abs(+v).toFixed(dp);
}

const MONTHS = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];

// "2026-11-04 ~11:10 ET (NBC …)" -> "Nov. 4, 2026, ~11:10 a.m. ET"
export function shortAsOf(s) {
  if (!s) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T]+(~?)(\d{1,2}):(\d{2}))?/.exec(s);
  if (!m) return s;
  const [, y, mo, d, approx, hh, mm] = m;
  let out = `${MONTHS[+mo - 1]} ${+d}, ${y}`;
  if (hh != null) {
    const h = +hh;
    const ap = h >= 12 ? 'p.m.' : 'a.m.';
    const h12 = h % 12 === 0 ? 12 : h % 12;
    out += `, ${approx || ''}${h12}:${mm} ${ap} ET`;
  }
  return out;
}

export function dataAsOf(ctx) {
  const d = ctx?.data;
  return d?.validation?.data_as_of ?? d?.params?.meta?.data_as_of ?? d?.story?.raw?.data_as_of ?? '';
}

export function asOfLabel(ctx) {
  return shortAsOf(dataAsOf(ctx));
}

// Model status. The pipeline may ship a cleared re-fit; read every flag defensively.
export function modelStatus(ctx) {
  const d = ctx?.data ?? {};
  const flags = d.params?.copy_flags ?? {};
  const cleared = d.manifest?.params_cleared === true;
  const level = d.validation?.fit_level ?? d.params?.meta?.fit_level ?? null;
  const blocked = !cleared || flags.publish_blocked === true;
  return {
    cleared,
    blocked,
    level,
    flags,
    blockingFail: d.validation?.blocking_fail ?? [],
    blockingNotRun: d.validation?.blocking_not_run ?? [],
  };
}

export function prefersReducedMotion() {
  return typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function finePointer() {
  return typeof matchMedia !== 'undefined' && matchMedia('(hover: hover) and (pointer: fine)').matches;
}

export function raceById(ctx, id) {
  return (ctx?.data?.races ?? []).find((r) => r.id === id) ?? null;
}

export const median = (arr) => {
  const a = arr.filter((v) => v != null && !Number.isNaN(v)).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = a.length >> 1;
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
};

// Spread labels vertically so none overlap; returns new y per item (same order).
export function dodge(ys, gap, lo = -Infinity, hi = Infinity) {
  const idx = ys.map((y, i) => ({ y, i })).sort((a, b) => a.y - b.y);
  for (let k = 1; k < idx.length; k++) if (idx[k].y < idx[k - 1].y + gap) idx[k].y = idx[k - 1].y + gap;
  const over = idx.length ? idx[idx.length - 1].y - hi : 0;
  if (over > 0) {
    idx[idx.length - 1].y -= over;
    for (let k = idx.length - 2; k >= 0; k--) if (idx[k].y > idx[k + 1].y - gap) idx[k].y = idx[k + 1].y - gap;
  }
  if (idx.length && idx[0].y < lo) {
    idx[0].y = lo;
    for (let k = 1; k < idx.length; k++) if (idx[k].y < idx[k - 1].y + gap) idx[k].y = idx[k - 1].y + gap;
  }
  const out = new Array(ys.length);
  for (const o of idx) out[o.i] = o.y;
  return out;
}

// Race id -> short readable label ("SEN-TX" -> "Texas Senate").
const STATE_NAMES = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California', CO: 'Colorado', CT: 'Connecticut',
  DE: 'Delaware', FL: 'Florida', GA: 'Georgia', HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa',
  KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts', MI: 'Michigan',
  MN: 'Minnesota', MS: 'Mississippi', MO: 'Missouri', MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire',
  NJ: 'New Jersey', NM: 'New Mexico', NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio',
  OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina', SD: 'South Dakota',
  TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont', VA: 'Virginia', WA: 'Washington', WV: 'West Virginia',
  WI: 'Wisconsin', WY: 'Wyoming', DC: 'D.C.',
};
export const stateName = (ab) => STATE_NAMES[ab] ?? ab;

export function raceLabel(id) {
  if (!id) return '';
  let m = /^SEN-([A-Z]{2})(-special)?$/.exec(id);
  if (m) return `${stateName(m[1])} Senate${m[2] ? ' (special)' : ''}`;
  m = /^GOV-([A-Z]{2})$/.exec(id);
  if (m) return `${stateName(m[1])} governor`;
  m = /^SPECIAL-([A-Z]{2})-(\d+)-(\d{4})-(\d{2})$/.exec(id);
  if (m) return `${m[1]}-${m[2]} (special, ${MONTHS[+m[4] - 1]} ${m[3]})`;
  return id;
}

// The model's (audited) label for a race row.
export const archOfRace = (r) => r?.fit_archetype ?? r?.archetype ?? null;

const roundInt = (v) => {
  const r = Math.round(v);
  return r === 0 ? 0 : r; // no "-0"
};
const signedInt = (v) => {
  const r = roundInt(v);
  return r > 0 ? `+${r}` : r < 0 ? `−${Math.abs(r)}` : '0';
};
const aboutPts = (v) => (Math.abs(v) < 1 ? 'less than 1 point' : `about ${Math.abs(roundInt(v))} point${Math.abs(roundInt(v)) === 1 ? '' : 's'}`);

// Claims-ledger C2 sentence, built from the fitted interval (findings.md §8).
export function c2Sentence(label, adj) {
  if (!adj) return '';
  const dir = adj.med >= 0 ? 'ahead of' : 'behind';
  return `In comparable races, on the same ballot, ${label.toLowerCase()} nominees ran ${aboutPts(adj.med)} ${dir} mainstream liberals (range ${signedInt(adj.lo)} to ${signedInt(adj.hi)}).`;
}
export const C2_CAVEAT = 'These compare similar races; they are not cause and effect, and they are preliminary.';

// Claims-ledger D5 placebo caveat, built from validation.json V11 numbers.
export function placeboCaveat(pl, deltaMed) {
  if (!pl || pl.placebo == null) return '';
  const dir = pl.placebo >= 0 ? 'ahead of' : 'behind';
  const same = Math.sign(pl.placebo) === Math.sign(deltaMed);
  const tail = same
    ? 'so part of this may be the place, not the candidate.'
    : `so these seats tend to run ${pl.placebo >= 0 ? 'ahead of' : 'behind'} the top of the ticket anyway, and the real gap could be larger than shown, not smaller.`;
  return `In ${pl.n} of these seats, a different Democrat (the 2024 House candidate) already ran ${aboutPts(pl.placebo)} ${dir} Harris, ${tail}`;
}
export { signedInt };
