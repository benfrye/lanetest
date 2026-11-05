// Layout functions for the dot stage. Each takes (nodes, opts) where opts carries the
// stage size and the step's layout params, and returns { pos: Map(id -> {x, y, r, hidden}),
// guides: [...] }. Guides are drawn by the SVG overlay (axes, row labels, reference lines).
// All layouts are deterministic so stepping back and forth lands on identical frames.
import { scaleLinear } from 'd3-scale';
import { format } from 'd3-format';

const fmtSigned = (v) => (v === 0 ? '0' : (v > 0 ? 'D+' : 'R+') + format('d')(Math.abs(v)));

export function dotRadius(n, width, height) {
  const area = width * height;
  const r = Math.sqrt((area * 0.12) / (Math.max(n, 1) * Math.PI));
  return Math.max(2.4, Math.min(7, r));
}

function pad(opts) {
  const narrow = opts.width < 640;
  return {
    top: Math.max(opts.padTop ?? (narrow ? 60 : 80), (opts.legendH ?? 0) + (narrow ? 40 : 42)),
    right: narrow ? 24 : 64,
    bottom: opts.padBottom ?? (narrow ? 56 : 72),
    left: opts.padLeft ?? (narrow ? 24 : 56),
  };
}

// Golden-angle spiral, sorted so related dots sit near each other.
export function cloud(nodes, opts) {
  const { width, height } = opts;
  const p = pad(opts);
  const r = dotRadius(nodes.length, width, height);
  const cx = p.left + (width - p.left - p.right) / 2;
  const cy = p.top + (height - p.top - p.bottom) / 2;
  const sorted = opts.sortBy ? [...nodes].sort((a, b) => (opts.sortBy(a) ?? 0) - (opts.sortBy(b) ?? 0)) : nodes;
  const spacing = r * 2.3;
  const pos = new Map();
  sorted.forEach((n, i) => {
    const a = i * 2.39996323;
    const d = spacing * 0.55 * Math.sqrt(i + 0.5);
    pos.set(n.id, { x: cx + d * Math.cos(a), y: cy + d * Math.sin(a), r });
  });
  return { pos, guides: [] };
}

// Places dots along x without overlap, stacking outward from a centerline (dodge).
function dodge(items, r, cy, maxSpread) {
  const placed = [];
  const step = r * 2 + 0.8;
  const out = [];
  const sorted = [...items].sort((a, b) => a.x - b.x);
  for (const it of sorted) {
    let k = 0;
    let y = cy;
    for (;;) {
      const off = k === 0 ? 0 : Math.ceil(k / 2) * step * (k % 2 ? -1 : 1);
      y = cy + off;
      const hit = placed.some((q) => Math.abs(q.x - it.x) < step && Math.abs(q.y - y) < step - 0.01);
      if (!hit || Math.abs(off) > maxSpread) break;
      k++;
    }
    const pt = { x: it.x, y };
    placed.push(pt);
    out.push({ id: it.id, x: pt.x, y: pt.y });
  }
  return out;
}

// Row bands shared by every lane chart (beeswarm and rowgrid), so a lane's label sits in the
// same spot whichever view is showing. Band heights scale with sqrt(count) so a 350-race row
// and an 8-race row both read.
function rowBands(nodes, opts, inRow = () => true) {
  const { width, height } = opts;
  const p = pad(opts);
  const rows = opts.rows ?? [{ id: '__all', label: null }];
  const rowOf = opts.rowOf ?? (() => '__all');
  const narrow = width < 640;
  const multi = rows.length > 1;
  const labelGutter = multi && !narrow ? 150 : 0;
  const x0 = p.left + labelGutter;
  const x1 = width - p.right;
  const visible = nodes.filter((n) => inRow(n) && rows.some((rw) => rw.id === rowOf(n)));
  const members = rows.map((row) => visible.filter((n) => rowOf(n) === row.id));
  const weights = members.map((m) => Math.max(1, Math.sqrt(m.length)));
  const wsum = weights.reduce((a, b) => a + b, 0);
  // On phones each row gets a 16px strip above it for its label.
  const strip = narrow && multi ? 16 : 0;
  const avail = height - p.top - p.bottom - strip * rows.length;
  let yCursor = p.top;
  const bands = rows.map((row, i) => {
    const h = (avail * weights[i]) / wsum;
    const top = yCursor;
    yCursor += h + strip;
    return { row, members: members[i], h, top, cy: top + strip + h / 2 };
  });
  return { p, rows, rowOf, narrow, x0, x1, visible, bands };
}

function rowLabelGuide(b, narrow, x, sub) {
  return {
    type: 'rowLabel',
    key: `row:${b.row.id}`,
    x,
    y: narrow ? b.top + 12 : b.cy,
    text: b.row.label,
    sub,
    narrow,
  };
}

// Beeswarm along a numeric field, optionally split into labeled rows.
// opts: { value: fn, domain: [min, max], rows?: [{ id, label }], rowOf?: fn, refLines?: [{ v, label }], axisLabel }
export function beeswarm(nodes, opts) {
  const { width, height } = opts;
  const { p, narrow, x0, x1, visible, bands } = rowBands(nodes, opts, (n) => opts.value(n) != null);
  const x = scaleLinear().domain(opts.domain).range([x0, x1]).clamp(true);
  const span = x1 - x0;
  let r = opts.radius ?? Math.min(dotRadius(visible.length, width, height) * 0.9, 5.5);
  for (const b of bands) if (b.members.length) r = Math.min(r, (Math.sqrt((b.h * span * 0.35) / b.members.length) - 0.8) / 2);
  r = Math.max(1.6, r);
  const pos = new Map();
  const guides = [];
  // Shrink the radius until every row's swarm stays inside its band.
  const rowItems = bands.map((b) => b.members.map((n) => ({ id: n.id, x: x(opts.value(n)) })));
  for (let iter = 0; iter < 8; iter++) {
    const fits = rowItems.every((items, i) => {
      const half = bands[i].h / 2 - r;
      return dodge(items, r, 0, Infinity).every((d) => Math.abs(d.y) <= half);
    });
    if (fits || r <= 1.6) break;
    r = Math.max(1.6, r * 0.88);
  }
  bands.forEach((b, i) => {
    const { row, cy } = b;
    const rowH = b.h;
    const items = rowItems[i];
    for (const d of dodge(items, r, cy, Infinity)) pos.set(d.id, { x: d.x, y: d.y, r });
    // statOf limits the row average (and the count label) to the races it covers.
    const statCount = opts.statOf ? b.members.filter((n) => opts.statOf(n)).length : null;
    if (row.label) {
      guides.push(rowLabelGuide(b, narrow, p.left, row.sub ?? (statCount != null ? `${statCount} of ${items.length} in average` : `${items.length} races`)));
    }
    if (opts.rowMedians) {
      const vals = b.members
        .filter((n) => !opts.statOf || opts.statOf(n))
        .map(opts.value)
        .sort((a, b) => a - b);
      if (vals.length) {
        // rowStat 'mean' matches copy that quotes averages; default is the median.
        const m = opts.rowStat === 'mean' ? vals.reduce((a, b) => a + b, 0) / vals.length : vals[Math.floor(vals.length / 2)];
        const fmt = opts.tickFormat ?? fmtSigned;
        guides.push({ type: 'tick', key: `tick:${row.id}`, x: x(m), y1: cy - rowH * 0.38, y2: cy + rowH * 0.38, label: fmt(Math.round(m)) });
      }
    }
  });
  for (const n of nodes) if (!pos.has(n.id)) pos.set(n.id, { x: x(0), y: height + 40, r, hidden: true });
  guides.push(axisX(x, opts, height - p.bottom + 8));
  for (const rl of opts.refLines ?? []) {
    guides.push({ type: 'vline', key: `vline:${rl.v}:${rl.label ?? ''}`, x: x(rl.v), y1: p.top - 8, y2: height - p.bottom, label: rl.label });
  }
  return { pos, guides };
}

// Scatter of two numeric fields. opts: { xValue, yValue, xDomain, yDomain, diagonal?, xLabel, yLabel }
export function scatter(nodes, opts) {
  const { width, height } = opts;
  const p = pad(opts);
  const x = scaleLinear().domain(opts.xDomain).range([p.left + 28, width - p.right]).clamp(true);
  const y = scaleLinear().domain(opts.yDomain).range([height - p.bottom, p.top]).clamp(true);
  const r = Math.min(dotRadius(nodes.length, width, height) * 0.8, 4.5);
  const pos = new Map();
  for (const n of nodes) {
    const xv = opts.xValue(n);
    const yv = opts.yValue(n);
    if (xv == null || yv == null) pos.set(n.id, { x: x(0), y: height + 40, r, hidden: true });
    else pos.set(n.id, { x: x(xv), y: y(yv), r });
  }
  const guides = [axisX(x, { ...opts, axisLabel: opts.xLabel }, height - p.bottom + 8), axisY(y, opts, p.left + 20)];
  if (opts.diagonal) {
    const [a, b] = opts.xDomain;
    guides.push({ type: 'line', x1: x(a), y1: y(a), x2: x(b), y2: y(b), label: opts.diagonal });
  }
  return { pos, guides };
}

// Waffle blocks per group, laid out side by side (or stacked on narrow screens).
// Each lane's races packed into a block in the same row bands the beeswarm uses, so moving
// from this view to a beeswarm only spreads the dots out; labels stay put.
// opts: { rows, rowOf, sortBy? }
export function rowgrid(nodes, opts) {
  const { width, height } = opts;
  const { p, narrow, x0, x1, visible, bands } = rowBands(nodes, opts);
  const span = x1 - x0;
  let r = Math.min(dotRadius(visible.length, width, height), 5);
  const linesOf = (m, r) => Math.ceil(m.length / Math.max(1, Math.floor(span / (r * 2 + 2))));
  for (let i = 0; i < 12; i++) {
    if (bands.every((b) => linesOf(b.members, r) * (r * 2 + 2) <= b.h * 0.85) || r <= 1.4) break;
    r = Math.max(1.4, r * 0.9);
  }
  const cell = r * 2 + 2;
  const perRow = Math.max(1, Math.floor(span / cell));
  const pos = new Map();
  const guides = [];
  for (const b of bands) {
    const m = opts.sortBy ? [...b.members].sort((a, c) => (opts.sortBy(a) ?? 0) - (opts.sortBy(c) ?? 0)) : b.members;
    const cols = Math.min(perRow, m.length);
    const lines = Math.ceil(m.length / perRow);
    const sx = x0 + (span - cols * cell) / 2 + cell / 2;
    const sy = b.cy - ((lines - 1) * cell) / 2;
    m.forEach((n, i) => pos.set(n.id, { x: sx + (i % perRow) * cell, y: sy + Math.floor(i / perRow) * cell, r }));
    if (b.row.label) guides.push(rowLabelGuide(b, narrow, p.left, `${m.length} races`));
  }
  for (const n of nodes) if (!pos.has(n.id)) pos.set(n.id, { x: width / 2, y: height + 40, r, hidden: true });
  return { pos, guides };
}

// opts: { groups: [{ id, label }], groupOf: fn, sortBy?: fn }
export function grid(nodes, opts) {
  const { width, height } = opts;
  const p = pad(opts);
  const groups = opts.groups;
  const narrow = width < 640;
  const pos = new Map();
  const guides = [];
  const cols = narrow ? 1 : groups.length;
  const gw = (width - p.left - p.right) / cols;
  const avail = height - p.top - p.bottom;
  // Columns too narrow for "Mainstream liberal 359" on one line put the count on a second line.
  const stack = !narrow && gw < 150;
  const top = stack ? 44 : 34;
  const gap = 10;
  const members = groups.map((g) => {
    const m = nodes.filter((n) => opts.groupOf(n) === g.id);
    if (opts.sortBy) m.sort((a, b) => (opts.sortBy(a) ?? 0) - (opts.sortBy(b) ?? 0));
    return m;
  });
  // Shrink the dots until every block fits: stacked blocks share the height on phones,
  // side-by-side columns each get the full height on wider screens.
  const blockH = (m, r) => {
    const cell = r * 2 + 2;
    const perRow = Math.max(1, Math.floor((gw - 12) / cell));
    return top + Math.ceil(m.length / perRow) * cell;
  };
  let r = Math.min(dotRadius(nodes.length, width, height), 5);
  for (let i = 0; i < 12; i++) {
    const fits = narrow
      ? members.reduce((sum, m) => sum + blockH(m, r) + gap, 0) <= avail
      : members.every((m) => blockH(m, r) <= avail);
    if (fits || r <= 1.4) break;
    r = Math.max(1.4, r * 0.9);
  }
  const cell = r * 2 + 2;
  const perRow = Math.max(1, Math.floor((gw - 12) / cell));
  let oyCursor = p.top;
  groups.forEach((g, gi) => {
    const m = members[gi];
    const ox = p.left + (gi % cols) * gw;
    const oy = narrow ? oyCursor : p.top;
    const blockW = Math.min(perRow, m.length) * cell;
    const startX = ox + (gw - blockW) / 2 + r;
    m.forEach((n, i) => {
      pos.set(n.id, { x: startX + (i % perRow) * cell, y: oy + top + Math.floor(i / perRow) * cell, r });
    });
    guides.push({ type: 'groupLabel', x: ox + gw / 2, y: oy + (stack ? 12 : 16), text: g.label, sub: `${m.length}`, stack });
    oyCursor += blockH(m, r) + gap;
  });
  for (const n of nodes) if (!pos.has(n.id)) pos.set(n.id, { x: width / 2, y: height + 40, r, hidden: true });
  return { pos, guides };
}

// Tile-grid map: one square per state, member dots packed inside it.
export const STATE_TILES = {
  AK: [0, 0], ME: [11, 0],
  VT: [10, 1], NH: [11, 1],
  WA: [1, 2], ID: [2, 2], MT: [3, 2], ND: [4, 2], MN: [5, 2], WI: [6, 2], MI: [8, 2], NY: [9, 2], MA: [10, 2], RI: [11, 2],
  OR: [1, 3], NV: [2, 3], WY: [3, 3], SD: [4, 3], IA: [5, 3], IL: [6, 3], IN: [7, 3], OH: [8, 3], PA: [9, 3], NJ: [10, 3], CT: [11, 3],
  CA: [1, 4], UT: [2, 4], CO: [3, 4], NE: [4, 4], MO: [5, 4], KY: [6, 4], WV: [7, 4], VA: [8, 4], MD: [9, 4], DE: [10, 4],
  AZ: [2, 5], NM: [3, 5], KS: [4, 5], AR: [5, 5], TN: [6, 5], NC: [7, 5], SC: [8, 5], DC: [9, 5],
  HI: [0, 6], OK: [4, 6], LA: [5, 6], MS: [6, 6], AL: [7, 6], GA: [8, 6],
  TX: [4, 7], FL: [9, 7],
};

export function tiles(nodes, opts) {
  const { width, height } = opts;
  const p = pad(opts);
  const cols = 12;
  const rows = 8;
  const size = Math.min((width - p.left - p.right) / cols, (height - p.top - p.bottom) / rows);
  const ox = p.left + (width - p.left - p.right - size * cols) / 2;
  const oy = p.top + (height - p.top - p.bottom - size * rows) / 2;
  const byState = new Map();
  for (const n of nodes) {
    const s = opts.stateOf ? opts.stateOf(n) : n.state;
    if (!byState.has(s)) byState.set(s, []);
    byState.get(s).push(n);
  }
  const pos = new Map();
  const guides = [];
  // One dot = one race, so every tile uses the same dot size, set by the busiest state.
  const label = 12;
  const inner = size - 6;
  const maxCount = Math.max(1, ...[...byState.values()].map((m) => m.length));
  const k = Math.ceil(Math.sqrt(maxCount * (inner / (inner - label))));
  const cell = inner / k;
  const r = Math.max(1.2, Math.min(cell / 2 - 0.5, opts.maxR ?? 6));
  for (const [st, [c, rw]] of Object.entries(STATE_TILES)) {
    const tx = ox + c * size;
    const ty = oy + rw * size;
    const members = byState.get(st) ?? [];
    guides.push({ type: 'tile', x: tx + 1, y: ty + 1, size: size - 2, text: st, fill: opts.tileFill ? opts.tileFill(st) : null });
    members.forEach((n, i) => {
      pos.set(n.id, { x: tx + 3 + cell * ((i % k) + 0.5), y: ty + 3 + label + cell * (Math.floor(i / k) + 0.5), r });
    });
  }
  for (const n of nodes) if (!pos.has(n.id)) pos.set(n.id, { x: width / 2, y: height + 40, r: 3, hidden: true });
  return { pos, guides };
}

function axisX(x, opts, y) {
  const ticks = (opts.ticks ?? x.ticks(opts.width < 640 ? 5 : 8)).map((v) => ({ x: x(v), label: (opts.tickFormat ?? fmtSigned)(v) }));
  // Same ticks → the axis slides; different ticks → the old axis fades out and the new one in.
  return { type: 'axisX', key: `axisX:${ticks.map((t) => t.label).join(',')}`, y, x1: x.range()[0], x2: x.range()[1], ticks, label: opts.axisLabel };
}

function axisY(y, opts, x) {
  const ticks = y.ticks(5).map((v) => ({ y: y(v), label: (opts.tickFormat ?? fmtSigned)(v) }));
  return { type: 'axisY', x, y1: y.range()[0], y2: y.range()[1], ticks, label: opts.yLabel };
}

export const LAYOUTS = { cloud, beeswarm, rowgrid, scatter, grid, tiles };
export { fmtSigned };
