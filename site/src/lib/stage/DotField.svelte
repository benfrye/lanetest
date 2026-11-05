<script>
  // The persistent stage: one canvas of race dots plus an SVG overlay for guides and
  // callouts. Positions tween between layouts; colors read from CSS tokens at draw time.
  import { onMount, untrack } from 'svelte';
  import { timer } from 'd3-timer';
  import { easeCubicInOut } from 'd3-ease';
  import { quadtree } from 'd3-quadtree';
  import { interpolateRgb } from 'd3-interpolate';
  import { LAYOUTS, fmtSigned } from './layouts.js';
  import { ARCHETYPE_BY_ID, drawShape } from '../archetypes.js';

  /** spec: { layout, params, color, highlight?: (n) => bool, annotate?: [{ id, text, dx?, dy? }], shapes? } */
  let { nodes = [], spec, interactive = false, onselect = null, tooltip = defaultTooltip } = $props();

  let wrap;
  let canvas;
  let width = $state(0);
  let height = $state(0);
  // Guides on screen right now, mid-tween included; each carries an opacity `op`.
  let guides = $state([]);
  let guideList = []; // the layout's target guides, non-reactive so drawing doesn't track them
  let guideFrom = new Map(); // key -> guide as shown when the current tween started
  let callouts = $state([]);
  let hover = $state(null);
  // Height of the key at the top of the stage; layouts start below it.
  let legendH = $state(0);
  let tokens = {};

  // Mutable animation state kept out of Svelte reactivity for speed.
  let cur = new Map();
  let target = new Map();
  let anim = null;
  let tree = null;
  const reduceMotion = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  function defaultTooltip(n) {
    const a = ARCHETYPE_BY_ID[n.archetype];
    return {
      title: n.label ?? n.id,
      lines: [
        n.dem ? `${n.dem}${a ? ` · ${a.label}` : ''}` : null,
        n.margin != null ? `Result: ${fmtSigned(Math.round(n.margin * 10) / 10)}` : null,
        n.overperf != null ? `vs. 2024 baseline: ${n.overperf > 0 ? '+' : ''}${n.overperf.toFixed(1)}` : null,
      ].filter(Boolean),
    };
  }

  function readTokens() {
    const cs = getComputedStyle(document.documentElement);
    const t = (k) => cs.getPropertyValue(k).trim();
    tokens = {
      dem: t('--dem'),
      rep: t('--rep'),
      mid: t('--mid'),
      ink: t('--ink'),
      muted: t('--muted'),
      bg: t('--bg'),
      arch: Object.fromEntries(Object.values(ARCHETYPE_BY_ID).map((a) => [a.id, t(a.token)])),
    };
    tokens.demRamp = interpolateRgb(tokens.mid, tokens.dem);
    tokens.repRamp = interpolateRgb(tokens.mid, tokens.rep);
  }

  function colorOf(n) {
    switch (spec?.color) {
      case 'archetype':
        return tokens.arch[n.archetype] ?? tokens.muted;
      case 'winner':
        return n.winner === 'D' ? tokens.dem : n.winner === 'R' ? tokens.rep : tokens.muted;
      case 'overperf':
      case 'margin': {
        const v = spec.color === 'overperf' ? n.overperf : n.margin;
        if (v == null) return tokens.muted;
        const k = Math.min(1, Math.abs(v) / (spec.colorSpan ?? 25));
        return v >= 0 ? tokens.demRamp(0.25 + 0.75 * k) : tokens.repRamp(0.25 + 0.75 * k);
      }
      default:
        return tokens.muted;
    }
  }

  function computeTarget() {
    if (!spec || !width || !height) return;
    const fn = LAYOUTS[spec.layout] ?? LAYOUTS.cloud;
    const out = fn(nodes, { width, height, legendH, ...(spec.params ?? {}) });
    target = out.pos;
    // Guides with the same key in both layouts (a lane's label, its average bar, a shared axis)
    // slide to their new spot; the rest fade out or in.
    guideList = out.guides.map((g, i) => ({ ...g, key: g.key ?? (g.type === 'tile' ? `tile:${g.text}` : `${g.type}:${i}`) }));
    guideFrom = new Map(guides.map((g) => [g.key, g]));
    const prev = cur;
    const from = new Map();
    for (const n of nodes) {
      let t = target.get(n.id);
      const c = prev.get(n.id) ?? { x: t.x, y: height + 30, r: t.r, a: 0 };
      // A dot this step doesn't use fades out where it stands instead of dropping off-screen.
      if (t.hidden && prev.has(n.id)) {
        t = { ...t, x: c.x, y: c.y };
        target.set(n.id, t);
      }
      from.set(n.id, { ...c, look: c.prevLook && c.lookMix < 0.5 ? c.prevLook : c.look });
    }
    animate(from);
  }

  function alphaOf(n, t) {
    if (t.hidden) return 0;
    if (spec?.highlight && !spec.highlight(n)) return 0.13;
    return 1;
  }

  const GEOM = ['x', 'y', 'x1', 'x2', 'y1', 'y2', 'size'];
  const TEXT = ['label', 'sub'];
  function shiftGuide(g, dx, dy) {
    const out = { ...g };
    for (const k of ['x', 'x1', 'x2']) if (typeof g[k] === 'number') out[k] = g[k] + dx;
    for (const k of ['y', 'y1', 'y2']) if (typeof g[k] === 'number') out[k] = g[k] + dy;
    if (g.ticks) out.ticks = g.ticks.map((t) => ({ ...t, ...(typeof t.x === 'number' ? { x: t.x + dx } : {}), ...(typeof t.y === 'number' ? { y: t.y + dy } : {}) }));
    return out;
  }
  function guideFrame(e) {
    const out = [];
    for (const t of guideList) {
      const f = guideFrom.get(t.key);
      if (!f) {
        // New guides fade in over the second half, after anything they replace has faded out.
        out.push({ ...t, op: Math.max(0, 2 * e - 1) });
        continue;
      }
      const g = { ...t, op: (f.op ?? 1) + (1 - (f.op ?? 1)) * e };
      // A label whose text changes (an average bar going from +11 to D+24) cross-fades.
      for (const k of TEXT) {
        const old = f.was?.[k] && (f.mix ?? 1) < 0.5 ? f.was[k] : f[k];
        if (old != null && t[k] != null && old !== t[k] && e < 1) {
          g.was = { ...g.was, [k]: old };
          g.mix = e;
        }
      }
      for (const k of GEOM) if (typeof f[k] === 'number' && typeof t[k] === 'number') g[k] = f[k] + (t[k] - f[k]) * e;
      if (t.ticks && f.ticks?.length === t.ticks.length) g.ticks = t.ticks.map((tk, i) => ({ ...tk, x: f.ticks[i].x + (tk.x - f.ticks[i].x) * e }));
      out.push(g);
    }
    const keep = new Set(guideList.map((g) => g.key));
    for (const f of guideFrom.values()) if (!keep.has(f.key) && (f.op ?? 1) * (1 - 2 * e) > 0.01) out.push({ ...f, op: (f.op ?? 1) * (1 - 2 * e) });
    return out;
  }

  function animate(from) {
    anim?.stop();
    const dur = reduceMotion ? 0 : 950;
    const n = nodes.length;
    const stagger = Math.min(320, n * 0.8);
    // Guides move on one clock that spans the dots' staggered start, so a lane's average bar
    // arrives with its dots rather than jumping ahead of them.
    const guideDur = dur + stagger;
    const order = new Map(nodes.map((d, i) => [d.id, i]));
    // Colors cross-fade too, so a step that changes what color means eases into it; a dot
    // whose shape or fill changes (circle to lane shape, filled to hollow) fades from one to
    // the other while it travels.
    const toCol = new Map();
    const mixCol = new Map();
    const toLook = new Map();
    for (const d of nodes) {
      const tc = colorOf(d);
      const f = from.get(d.id);
      const fc = f?.col ?? tc;
      toCol.set(d.id, tc);
      if (fc !== tc) mixCol.set(d.id, interpolateRgb(fc, tc));
      toLook.set(d.id, lookOf(d));
    }
    const step = (elapsed) => {
      let done = true;
      for (const d of nodes) {
        const f = from.get(d.id);
        const t = target.get(d.id);
        const delay = dur ? (order.get(d.id) / n) * stagger : 0;
        const k = dur ? Math.max(0, Math.min(1, (elapsed - delay) / dur)) : 1;
        if (k < 1) done = false;
        const e = easeCubicInOut(k);
        const ta = alphaOf(d, t);
        cur.set(d.id, {
          x: f.x + (t.x - f.x) * e,
          y: f.y + (t.y - f.y) * e,
          r: f.r + (t.r - f.r) * e,
          a: (f.a ?? 1) + (ta - (f.a ?? 1)) * e,
          col: k < 1 && mixCol.has(d.id) ? mixCol.get(d.id)(e) : toCol.get(d.id),
          look: toLook.get(d.id),
          prevLook: f.look && f.look.key !== toLook.get(d.id).key && k < 1 ? f.look : null,
          lookMix: e,
        });
      }
      guides = guideFrame(done || !guideDur ? 1 : easeCubicInOut(Math.min(1, elapsed / guideDur)));
      draw();
      if (done) {
        anim?.stop();
        anim = null;
        tree = quadtree(
          nodes.filter((d) => cur.get(d.id).a > 0.5),
          (d) => cur.get(d.id).x,
          (d) => cur.get(d.id).y,
        );
        placeCallouts();
      }
    };
    callouts = [];
    if (!dur) step(0);
    else anim = timer(step);
  }

  // How a dot is drawn at this step: its shape, and whether fill shows the outcome.
  // When color shows the Democrat's lane, fill shows the outcome: filled = won, hollow = lost,
  // faint = not yet called. Otherwise lane charts would read as if the races themselves had a lane.
  function lookOf(d) {
    const useShapes = spec?.shapes ?? spec?.color === 'archetype';
    const showsOutcome = spec?.color === 'archetype' && spec?.outcome !== false;
    const shape = useShapes ? ARCHETYPE_BY_ID[d.archetype]?.shape ?? 'circle' : 'circle';
    const fill = showsOutcome && d.winner === 'R' ? 'hollow' : showsOutcome && !d.winner ? 'faint' : 'solid';
    return { shape, fill, key: shape + fill };
  }

  function paint(ctx, look, c, col, alpha) {
    if (alpha <= 0.005) return;
    drawShape(ctx, look.shape, c.x, c.y, c.r);
    if (look.fill === 'hollow') {
      ctx.globalAlpha = alpha;
      ctx.lineWidth = Math.max(1.2, c.r * 0.38);
      ctx.strokeStyle = col;
      ctx.stroke();
    } else {
      ctx.globalAlpha = look.fill === 'faint' ? alpha * 0.35 : alpha;
      ctx.fillStyle = col;
      ctx.fill();
    }
  }

  function draw() {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, bleed * dpr, 0);
    ctx.clearRect(-bleed, 0, width + bleed, height);
    // Faded dots first so highlighted ones sit on top.
    for (const pass of [0, 1]) {
      for (const d of nodes) {
        const c = cur.get(d.id);
        if (!c || c.a <= 0.01) continue;
        const strong = c.a > 0.5;
        if ((pass === 1) !== strong) continue;
        const col = c.col ?? colorOf(d);
        const look = c.look ?? lookOf(d);
        if (c.prevLook) {
          paint(ctx, c.prevLook, c, col, c.a * (1 - c.lookMix));
          paint(ctx, look, c, col, c.a * c.lookMix);
        } else paint(ctx, look, c, col, c.a);
        if (hover && hover.id === d.id) {
          ctx.globalAlpha = 1;
          ctx.lineWidth = 2;
          ctx.strokeStyle = tokens.ink;
          ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;
  }

  function placeCallouts() {
    // Each callout tries a few spots around its dot (beside, below, above; one or two lines)
    // and takes the one that overlaps least with the stage's own labels (row labels, median /
    // mean tick labels), earlier callouts, highlighted dots and the frame. A spec dx/dy pins it.
    const CH = 6.6; // ~px per character of 12px semibold text
    const LH = 14;
    const narrow = width < 640;
    const obstacles = []; // { x0, x1, y0, y1, w }
    for (const g of guideList) {
      if (g.type === 'tick') {
        const tw = String(g.label ?? '').length * 6.5 + 6;
        obstacles.push({ x0: g.x - tw / 2, x1: g.x + tw / 2, y0: g.y1 - 16, y1: g.y1, w: 3 });
        obstacles.push({ x0: g.x - 2, x1: g.x + 2, y0: g.y1, y1: g.y2, w: 2 });
      } else if (g.type === 'rowLabel') {
        const tw = String(g.text ?? '').length * 7.6;
        const y = g.narrow ? g.y : g.y - 2;
        obstacles.push({ x0: g.x - 2, x1: g.x + tw, y0: y - 12, y1: y + 3, w: 3 });
        if (!g.narrow && g.sub) obstacles.push({ x0: g.x - 2, x1: g.x + String(g.sub).length * 6, y0: y + 3, y1: y + 17, w: 2 });
      } else if (g.type === 'groupLabel') {
        const tw = (String(g.text ?? '').length + String(g.sub ?? '').length + 1) * 7;
        obstacles.push({ x0: g.x - tw / 2, x1: g.x + tw / 2, y0: g.y - 12, y1: g.y + (g.stack ? 17 : 3), w: 3 });
      }
    }
    const dots = [];
    for (const n of nodes) {
      const c = cur.get(n.id);
      if (c && c.a > 0.5 && !c.hidden) dots.push(c);
    }
    const overlap = (a, b) => Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) * Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0));
    const split = (t) => {
      const i = t.indexOf(' (');
      if (i > 0) return [t.slice(0, i), t.slice(i + 1)];
      const mid = t.length / 2;
      let best = -1;
      for (let k = 0; k < t.length; k++) if (t[k] === ' ' && (best < 0 || Math.abs(k - mid) < Math.abs(best - mid))) best = k;
      return best > 0 ? [t.slice(0, best), t.slice(best + 1)] : [t];
    };
    const placedBoxes = [];
    const out = [];
    for (const a of spec?.annotate ?? []) {
      const c = cur.get(a.id);
      if (!c || c.a < 0.5) continue;
      const one = [a.text];
      const two = split(a.text);
      const sideLeft = narrow ? c.x > width / 2 : c.x > width * 0.62;
      const gap = c.r + 8;
      const cands = [];
      const pinned = a.dx != null || a.dy != null;
      const add = (lines, left, dx, dy, anchorAtDot = false) => cands.push({ lines, left, dx, dy, anchorAtDot });
      if (pinned) add(one, sideLeft, a.dx ?? 0, a.dy ?? 0);
      else {
        for (const left of [sideLeft, !sideLeft]) {
          add(one, left, 0, 0);
          if (two.length > 1) for (const dy of [-6, -3, 0]) add(two, left, 0, dy);
        }
        // above / below the dot, text starting at (or ending at) the dot
        for (const [lines, k] of [[one, 1], [two, 2]]) {
          if (k === 2 && two.length < 2) continue;
          add(lines, sideLeft, 0, c.r + 14, true);
          add(lines, sideLeft, 0, -(c.r + 10) - LH * (k - 1), true);
          add(lines, sideLeft, 0, c.r + 14 + LH, true);
          add(lines, sideLeft, 0, -(c.r + 10) - LH * k, true);
        }
      }
      let best = null;
      for (const [ci, cd] of cands.entries()) {
        const tw = Math.max(...cd.lines.map((l) => l.length)) * CH;
        const tx = cd.anchorAtDot ? c.x + (cd.left ? c.r : -c.r) : c.x + (cd.left ? -gap : gap) + cd.dx;
        const ty = c.y + 4 + cd.dy;
        const box = { x0: cd.left ? tx - tw : tx, x1: cd.left ? tx : tx + tw, y0: ty - 11, y1: ty + 3 + LH * (cd.lines.length - 1) };
        let score = 0;
        for (const o of obstacles) score += o.w * overlap(box, o);
        for (const b of placedBoxes) score += 3 * overlap(box, b);
        for (const d of dots) {
          if (d === c) continue;
          score += 2 * overlap(box, { x0: d.x - d.r, x1: d.x + d.r, y0: d.y - d.r, y1: d.y + d.r });
        }
        // the frame, and the ring around this callout's own dot
        const area = (box.x1 - box.x0) * (box.y1 - box.y0);
        const inside = overlap(box, { x0: 2, x1: width - 2, y0: 2, y1: height - 2 });
        score += 5 * (area - inside);
        score += 3 * overlap(box, { x0: c.x - c.r - 5, x1: c.x + c.r + 5, y0: c.y - c.r - 5, y1: c.y + c.r + 5 });
        score += ci * 0.01; // prefer earlier candidates on ties
        if (!best || score < best.score) best = { score, box, tx, ty, cd };
      }
      if (!best) continue;
      placedBoxes.push(best.box);
      out.push({ ...a, x: c.x, y: c.y, r: c.r, tx: best.tx, ty: best.ty, anchor: best.cd.left ? 'end' : 'start', lines: best.cd.lines });
    }
    callouts = out;
  }

  let origin = null; // the stage's page position at the last resize
  let bleed = 0; // how far the canvas extends left of the stage
  function resize() {
    if (!wrap) return;
    const rect = wrap.getBoundingClientRect();
    // When the stage itself moves (a full-width title card giving way to a side card), shift
    // every dot and guide by the same amount so they stay put on screen and glide from there.
    if (origin) {
      const dx = origin.left - rect.left;
      const dy = origin.top - rect.top;
      if (dx || dy) {
        for (const c of cur.values()) {
          c.x += dx;
          c.y += dy;
        }
        guides = guides.map((g) => shiftGuide(g, dx, dy));
      }
    }
    origin = { left: rect.left, top: rect.top };
    width = rect.width;
    height = rect.height;
    const dpr = window.devicePixelRatio || 1;
    // The canvas reaches left under the text column (which is transparent), so dots passing
    // that way while the stage changes size are seen, not cut off at the stage edge.
    bleed = Math.max(0, Math.round(rect.left));
    const cw = Math.round((width + bleed) * dpr);
    // The canvas can keep its total size while the stage inside it moves, so place it every
    // time; its pixel buffer is only reset when the size changes, since that clears it.
    canvas.style.left = -bleed + 'px';
    canvas.style.width = width + bleed + 'px';
    canvas.style.height = height + 'px';
    if (canvas.width !== cw || canvas.height !== Math.round(height * dpr)) {
      canvas.width = cw;
      canvas.height = Math.round(height * dpr);
    }
    draw();
  }

  function pick(ev) {
    if (!tree) return null;
    const rect = wrap.getBoundingClientRect();
    return tree.find(ev.clientX - rect.left, ev.clientY - rect.top, 16) ?? null;
  }

  function onMove(ev) {
    if (!interactive || ev.pointerType === 'touch') return;
    const n = pick(ev);
    if ((n?.id ?? null) !== (hover?.id ?? null)) {
      hover = n ? { id: n.id, node: n, ...cur.get(n.id) } : null;
      draw();
    }
  }

  function onClick(ev) {
    if (!interactive) return;
    const n = pick(ev);
    hover = n ? { id: n.id, node: n, ...cur.get(n.id) } : null;
    draw();
    if (n) {
      ev.stopPropagation();
      onselect?.(n);
    }
  }

  onMount(() => {
    readTokens();
    resize();
    const ro = new ResizeObserver(() => {
      resize();
      computeTarget();
    });
    ro.observe(wrap);
    const mq = matchMedia('(prefers-color-scheme: dark)');
    const onTheme = () => {
      readTokens();
      for (const d of nodes) {
        const c = cur.get(d.id);
        if (c) c.col = colorOf(d);
      }
      draw();
    };
    mq.addEventListener('change', onTheme);
    const mo = new MutationObserver(onTheme);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => {
      ro.disconnect();
      mq.removeEventListener('change', onTheme);
      mo.disconnect();
      anim?.stop();
    };
  });

  $effect(() => {
    // Re-run whenever the step's spec or the node set changes.
    spec;
    nodes;
    spec?.deps?.(); // lets a step re-layout when reader state it depends on changes
    legendH; // the key's height sets where the layout starts
    if (width) {
      // untracked: with reduced motion the first frame draws synchronously and reads hover etc.,
      // which would otherwise re-run the whole layout on every pointer move.
      untrack(() => {
        hover = null;
        // The step change may also move or resize the stage; pick that up before laying out,
        // so the dots don't animate toward a frame that's about to change.
        resize();
        computeTarget();
      });
    }
  });

  const DIM_PLACEHOLDER = 'Faded dots: votes still being counted, or a strong independent ran. Left out of the averages.';
  let tip = $derived(hover ? tooltip(hover.node) : null);

  // Every color encoding gets a visible key, so a step that changes what color means says so.
  const LEGENDS = {
    winner: [
      { label: 'Democrat won', color: 'var(--dem)' },
      { label: 'Republican won', color: 'var(--rep)' },
      { label: 'Not yet called', color: 'var(--muted)' },
    ],
    overperf: [
      { label: 'Democrat ran ahead of Harris', color: 'var(--dem)' },
      { label: 'Ran behind Harris', color: 'var(--rep)' },
    ],
    margin: [
      { label: 'Democratic margin', color: 'var(--dem)' },
      { label: 'Republican margin', color: 'var(--rep)' },
    ],
  };
  let legend = $derived(spec?.legend === false ? null : (LEGENDS[spec?.color] ?? null));
  // Lane charts: say what a dot is and how fill encodes the outcome (lanes are labeled on the chart).
  let outcomeKey = $derived(spec?.color === 'archetype' && spec?.outcome !== false && spec?.legend !== false);
</script>

<div class="field" bind:this={wrap}>
  <svg class="guides" {width} {height} aria-hidden="true">
    {#each guides.filter((g) => g.type === 'tile') as g (g.key)}
      <g opacity={g.op}>
        <rect class="tile" x={g.x} y={g.y} width={g.size} height={g.size} rx="3" style:fill={g.fill} />
        <text class="tile-label" x={g.x + 3} y={g.y + 10}>{g.text}</text>
      </g>
    {/each}
  </svg>
  <canvas
    bind:this={canvas}
    aria-hidden="true"
    onpointermove={onMove}
    onpointerleave={() => {
      hover = null;
      draw();
    }}
    onclick={onClick}
    class:interactive
  ></canvas>
  <svg class="guides" {width} {height} aria-hidden="true">
    {#each guides.filter((g) => g.type !== 'tile') as g (g.key)}
      <g opacity={g.op}>
      {#if g.type === 'axisX'}
        <line class="axis" x1={g.x1} x2={g.x2} y1={g.y} y2={g.y} />
        {#each g.ticks as t (t.label)}
          <line class="tickmark" x1={t.x} x2={t.x} y1={g.y} y2={g.y + 4} />
          <text class="tick" x={t.x} y={g.y + 17} text-anchor="middle">{t.label}</text>
        {/each}
        {#if g.label}<text class="axis-label" x={(g.x1 + g.x2) / 2} y={g.y + 36} text-anchor="middle">{g.label}</text>{/if}
      {:else if g.type === 'axisY'}
        {#each g.ticks as t (t.label)}
          <text class="tick" x={g.x - 6} y={t.y + 4} text-anchor="end">{t.label}</text>
        {/each}
        {#if g.label}<text class="axis-label" x={g.x} y={g.y2 - 12} text-anchor="start">{g.label}</text>{/if}
      {:else if g.type === 'vline'}
        <line class="ref" x1={g.x} x2={g.x} y1={g.y1} y2={g.y2} />
        {#if g.label}<text class="ref-label" x={g.x + 5} y={g.y1 + 4}>{g.label}</text>{/if}
      {:else if g.type === 'line'}
        <line class="ref" x1={g.x1} x2={g.x2} y1={g.y1} y2={g.y2} />
        {#if g.label}<text class="ref-label" x={g.x2 - 4} y={g.y2 + 14} text-anchor="end">{g.label}</text>{/if}
      {:else if g.type === 'tick'}
        <line class="median" x1={g.x} x2={g.x} y1={g.y1} y2={g.y2} />
        {#if g.was?.label}<text class="median-label" x={g.x} y={g.y1 - 4} text-anchor="middle" opacity={Math.max(0, 1 - 2 * g.mix)}>{g.was.label}</text>{/if}
        <text class="median-label" x={g.x} y={g.y1 - 4} text-anchor="middle" opacity={g.was?.label ? Math.max(0, 2 * g.mix - 1) : 1}>{g.label}</text>
      {:else if g.type === 'rowLabel'}
        <text class="row-label" x={g.x} y={g.narrow ? g.y : g.y - 2}>{g.text}</text>
        {#if !g.narrow}
          {#if g.was?.sub}<text class="row-sub" x={g.x} y={g.y + 14} opacity={Math.max(0, 1 - 2 * g.mix)}>{g.was.sub}</text>{/if}
          <text class="row-sub" x={g.x} y={g.y + 14} opacity={g.was?.sub ? Math.max(0, 2 * g.mix - 1) : 1}>{g.sub}</text>
        {/if}
      {:else if g.type === 'groupLabel'}
        <text class="row-label" x={g.x} y={g.y} text-anchor="middle">{g.text} <tspan class="row-sub" x={g.stack ? g.x : undefined} dy={g.stack ? 14 : undefined}>{g.sub}</tspan></text>
      {/if}
      </g>
    {/each}
    {#each callouts as c (c.id)}
      <g class="callout">
        <circle cx={c.x} cy={c.y} r={c.r + 4} />
        <text x={c.tx} y={c.ty} text-anchor={c.anchor}
          >{#each c.lines as l, k (k)}<tspan x={c.tx} dy={k ? 14 : 0}>{l}</tspan>{/each}</text
        >
      </g>
    {/each}
  </svg>
  {#if outcomeKey}
    <div class="legend ui" aria-label="Key" bind:clientHeight={legendH}>
      <span class="key lead">Each dot is a race, shaped and colored by the Democrat who ran.</span>
      <span class="key"><span class="swatch outline-fill"></span>Democrat won</span>
      <span class="key"><span class="swatch outline-hollow"></span>Lost</span>
      <span class="key"><span class="swatch outline-faint"></span>Not yet called</span>
      <!-- Always laid out, so the key (and the rows below it) keep one height across lane steps. -->
      <span class="key lead dim-note" class:placeholder={!spec?.dimNote}>{spec?.dimNote ?? DIM_PLACEHOLDER}</span>
    </div>
  {/if}
  {#if legend}
    <div class="legend ui" aria-label="Color key" bind:clientHeight={legendH}>
      {#each legend as item (item.label)}
        <span class="key"><span class="swatch" style:background={item.color}></span>{item.label}</span>
      {/each}
    </div>
  {/if}
  {#if tip && hover}
    <div
      class="tooltip ui"
      style:left={Math.min(hover.x + 14, width - 220) + 'px'}
      style:top={Math.max(8, hover.y - 12) + 'px'}
      role="status"
    >
      <strong>{tip.title}</strong>
      {#each tip.lines as l (l)}<div>{l}</div>{/each}
    </div>
  {/if}
</div>

<style>
  .field {
    position: absolute;
    inset: 0;
  }
  canvas {
    position: absolute;
    inset: 0;
    touch-action: manipulation;
  }
  canvas.interactive {
    cursor: crosshair;
  }
  .guides {
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: visible;
    font-family: var(--font-ui);
  }
  .axis {
    stroke: var(--axis);
  }
  .tickmark {
    stroke: var(--axis);
  }
  .tick {
    fill: var(--muted);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
  .axis-label,
  .ref-label {
    fill: var(--ink-2);
    font-size: 12px;
  }
  .ref {
    stroke: var(--ink-2);
    stroke-dasharray: 3 4;
    opacity: 0.7;
  }
  .median {
    stroke: var(--ink);
    stroke-width: 2;
  }
  .median-label {
    fill: var(--ink);
    font-size: 11px;
    font-weight: 600;
    paint-order: stroke;
    stroke: var(--bg);
    stroke-width: 4px;
    stroke-linejoin: round;
  }
  .row-label {
    fill: var(--ink);
    font-size: 13px;
    font-weight: 600;
  }
  .row-sub {
    fill: var(--muted);
    font-size: 11px;
    font-weight: 400;
  }
  .tile {
    fill: var(--surface-2);
    stroke: var(--ring);
  }
  .tile-label {
    fill: var(--muted);
    font-size: 9px;
    font-weight: 600;
  }
  .callout circle {
    fill: none;
    stroke: var(--ink);
    stroke-width: 1.5;
  }
  .callout text {
    fill: var(--ink);
    font-size: 12px;
    font-weight: 600;
    paint-order: stroke;
    stroke: var(--bg);
    stroke-width: 4px;
    stroke-linejoin: round;
  }
  .placeholder {
    visibility: hidden;
  }
  .legend {
    position: absolute;
    top: 16px;
    right: clamp(var(--gutter), 3vw, 40px);
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 4px 14px;
    max-width: calc(100% - 2 * var(--gutter));
    font-size: 12px;
    color: var(--ink-2);
    pointer-events: none;
  }
  .key {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .swatch {
    width: 9px;
    height: 9px;
    border-radius: 50%;
  }
  .outline-fill {
    background: var(--ink-2);
  }
  .outline-hollow {
    border: 2px solid var(--ink-2);
  }
  .outline-faint {
    background: var(--ink-2);
    opacity: 0.35;
  }
.dim-note {
    color: var(--muted);
  }
  .lead {
    flex-basis: 100%;
    justify-content: flex-end;
    text-align: right;
  }
  .tooltip {
    position: absolute;
    z-index: 5;
    max-width: 210px;
    padding: 8px 10px;
    border-radius: 8px;
    background: var(--surface);
    border: 1px solid var(--ring);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.18);
    font-size: 12px;
    line-height: 1.4;
    color: var(--ink-2);
    pointer-events: none;
  }
  .tooltip strong {
    display: block;
    color: var(--ink);
    font-size: 13px;
  }
</style>
