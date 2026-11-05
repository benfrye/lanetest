<script>
  // Stage: where the swing ran ahead of or behind its state. One dot per county or House
  // district (geo_shifts.json): its 2024 -> 2026 swing minus the statewide swing in the same
  // race (House districts: minus the national House swing). Rows follow the file's `kinds`
  // order; the tick is the row median from the file's summary. Neutral ink marks: no party
  // or archetype colors are needed here.
  import { scaleLinear } from 'd3-scale';
  import StageFrame from './StageFrame.svelte';
  import Tip from './Tip.svelte';
  import { signed, num, asOfLabel } from './util.js';
  import { domainName, list } from './sources.js';

  let { ctx, nodes = [], title = 'Which places ran ahead of their state', ...rest } = $props();

  const geo = $derived(ctx?.data?.story?.geo ?? {});
  const places = $derived((geo.places ?? []).map((p, i) => ({ ...p, key: `${i}:${p.place}:${p.race}` })));
  const kinds = $derived(geo.kinds ?? [...new Set(places.map((p) => p.kind))]);
  const med = $derived(Object.fromEntries((geo.summary ?? []).map((s) => [s.kind, s])));

  // Kind names inside a sentence; capitalized group names (Black, Hispanic) keep their case.
  const PHRASE = { 'Small-town and rural': 'small-town and rural counties' };
  const lower = (k) => PHRASE[k] ?? (/^(Black|Hispanic|Latino|Asian)/.test(k) ? k : k.charAt(0).toLowerCase() + k.slice(1));
  const caption = $derived.by(() => {
    const s = kinds.map((k) => ({ kind: k, n: med[k]?.n ?? 0, m: med[k]?.median_relative })).filter((s) => s.m != null);
    if (!s.length) return '';
    const ahead = s.filter((x) => x.m >= 2).sort((a, b) => b.m - a.m);
    const behind = s.filter((x) => x.m <= -2).sort((a, b) => a.m - b.m);
    const even = s.filter((x) => x.m > -2 && x.m < 2);
    const parts = [];
    if (ahead.length) parts.push(`${list(ahead.map((x) => `${lower(x.kind)} (${signed(x.m, 0)})`))} ran ahead of their states`);
    if (behind.length) parts.push(`${list(behind.map((x) => lower(x.kind)))} trailed by about ${list(behind.map((x) => Math.round(Math.abs(x.m))))} points`);
    if (even.length) parts.push(`${list(even.map((x) => lower(x.kind)))} roughly matched`);
    return `By row median, ${parts.join('; ')}.`;
  });

  const fewRows = $derived((geo.summary ?? []).filter((x) => x.n <= 3).map((x) => x.kind));
  const fewNote = $derived.by(() => {
    if (!fewRows.length) return '';
    const t = list(fewRows.map(lower));
    const ns = (geo.summary ?? []).filter((x) => fewRows.includes(x.kind)).map((x) => x.n);
    const lo = Math.min(...ns);
    const hi = Math.max(...ns);
    return ` ${t.charAt(0).toUpperCase() + t.slice(1)} have only ${lo === hi ? lo : `${lo} or ${hi}`} places each.`;
  });
  const outlets = $derived([...new Set(places.map((p) => domainName(p.source, ctx)).filter(Boolean))]);
  const nationalRef = $derived(places.some((p) => /national/i.test(p.reference)));
  const source = $derived(
    `Source: ${list(outlets) || 'results pages'} (county and district results, statewide swings)${nationalRef ? '; national House swing: New York Times Voter Trends' : ''}. Relative swings: our calculation.`,
  );

  let showTable = $state(false);
  let hover = $state(null);
  let pinned = $state(null);
  const tip = $derived(pinned ?? hover);

  // Simple beeswarm: walk the row left to right, put each dot at the nearest free offset.
  function swarm(items, x, r) {
    const placed = [];
    // Dots may overlap a little (they are translucent) so a dense row stays compact.
    const step = r * 1.55;
    for (const it of [...items].sort((a, b) => a.relative - b.relative)) {
      const cx = x(it.relative);
      let dy = 0;
      for (let k = 0; k < 60; k++) {
        dy = k === 0 ? 0 : Math.ceil(k / 2) * (k % 2 ? -1 : 1) * step;
        if (!placed.some((p) => (p.cx - cx) ** 2 + (p.dy - dy) ** 2 < step * step)) break;
      }
      placed.push({ ...it, cx, dy });
    }
    return placed;
  }

  function layout(w, h) {
    const narrow = w < 560;
    const labelW = narrow ? 0 : 178;
    const medW = narrow ? 0 : 58;
    const vals = places.map((p) => p.relative);
    const lo = Math.floor(Math.min(-10, ...vals) / 10) * 10;
    const hi = Math.ceil(Math.max(10, ...vals) / 10) * 10;
    const x = scaleLinear().domain([lo, hi]).range([labelW + 10, w - medW - 10]);
    const r = narrow ? 4 : 5;
    const axisH = 34;
    const headH = narrow ? 18 : 0;
    const rows = [];
    let y = axisH;
    const swarms = kinds.map((k) => {
      const items = places.filter((p) => p.kind === k);
      const dots = swarm(items, x, r);
      const span = Math.max(0, ...dots.map((d) => Math.abs(d.dy)));
      return { k, items, dots, need: Math.max(narrow ? 30 : 40, span * 2 + r * 2 + 14) };
    });
    // Share any spare height evenly so the rows breathe on a tall stage.
    const spare = h - axisH - 6 - swarms.reduce((a, s) => a + s.need + headH, 0);
    const extra = spare > 0 ? Math.min(28, spare / Math.max(1, swarms.length)) : 0;
    for (const { k, items, dots, need } of swarms) {
      const rowH = need + extra;
      const cy = y + headH + rowH / 2;
      rows.push({ kind: k, n: items.length, med: med[k]?.median_relative ?? null, y, cy, rowH: rowH + headH, dots: dots.map((d) => ({ ...d, cy: cy + d.dy })) });
      y += rowH + headH;
    }
    const ticks = x.ticks(narrow ? 4 : 6);
    return { rows, x, r, ticks, w, h, bottom: y + 6, narrow, labelW, medW, axisH };
  }

  const all = (L) => L.rows.flatMap((rw) => rw.dots);
  function nearest(L, px, py, max = 22) {
    let best = null;
    let bd = max * max;
    for (const d of all(L)) {
      const dd = (d.cx - px) ** 2 + (d.cy - py) ** 2;
      if (dd < bd) {
        bd = dd;
        best = d;
      }
    }
    return best;
  }
  const local = (e) => {
    const b = e.currentTarget.getBoundingClientRect();
    return [e.clientX - b.left, e.clientY - b.top];
  };
  const isNat = (p) => /national/i.test(p.reference ?? '');
  const raceName = (p) => (p.race === 'House' ? 'House race' : `${p.race.toLowerCase()} race`);
  const refName = (p) => (/national/i.test(p.reference) ? 'National House swing' : `${p.reference} ${p.race === 'Governor' ? 'governor' : p.race.toLowerCase()} swing`);
  const tipLines = (p) => [
    `${p.race === 'House' ? 'House' : p.race}: swing ${signed(p.shift, 1)} toward Democrats`,
    `${refName(p)}: ${signed(p.reference_shift, 1)}`,
    `Relative: ${signed(p.relative, 1)} ${p.relative >= 0 ? 'ahead of' : 'behind'} ${/national/i.test(p.reference) ? 'the nation' : 'the state'}`,
    `Source: ${domainName(p.source, ctx)}`,
  ];
  // Keyboard: each row is one tab stop; arrow keys walk its dots.
  function onRowKey(e, row) {
    const ds = row.dots;
    if (!ds.length) return;
    const i = ds.findIndex((d) => d.key === tip?.key);
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault();
      const j = i < 0 ? 0 : (i + (e.key === 'ArrowRight' ? 1 : -1) + ds.length) % ds.length;
      hover = ds[j];
    } else if (e.key === 'Escape') {
      hover = null;
      pinned = null;
    }
  }
</script>

<StageFrame
  {title}
  dek="Each dot is a county or House district: its 2024 → 2026 swing minus its state’s swing in the same race. Right of the line, the place swung harder toward Democrats than its state."
  note={`${(geo.caveats ?? []).join(' ')}${fewNote} Preliminary, as of ${asOfLabel(ctx)}.`}
  {source}
  sourceShort={`Source: ${list(outlets) || 'results pages'}; our calculation.`}
  bind:showTable
  onbackground={() => (pinned = null)}
>
  {#snippet legend()}
    <span class="lg"><svg width="12" height="12" viewBox="-6 -6 12 12"><circle r="4.5" class="dot" /></svg>One place</span>
    <span class="lg"><svg width="12" height="14" viewBox="-6 -7 12 14"><line y1="-6" y2="6" class="med" /></svg>Median of the row</span>
  {/snippet}

  {#snippet banner()}
    {#if caption}<p class="cap">{caption}</p>{/if}
  {/snippet}

  {#snippet chart(w, h)}
    {@const L = layout(w, h)}
    {@const x0 = L.x(0)}
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
    <svg
      class="plot"
      width={w}
      height={L.bottom}
      onpointermove={(e) => e.pointerType === 'mouse' && (hover = nearest(L, ...local(e)))}
      onpointerleave={() => (hover = null)}
      onclick={(e) => {
        e.stopPropagation();
        const d = nearest(L, ...local(e), 26);
        pinned = d && pinned?.key !== d.key ? d : null;
      }}
    >
      <title>Dot plot of county and district swings relative to their states. {caption}</title>
      {#each L.ticks as t (t)}
        <line class={t === 0 ? 'zero' : 'grid'} x1={L.x(t)} x2={L.x(t)} y1={L.axisH - 6} y2={L.bottom - 4} />
        {#if t !== 0}<text class="tick" x={L.x(t)} y={L.axisH - 10} text-anchor="middle">{signed(t, 0)}</text>{/if}
      {/each}
      <text class="zlbl" x={x0} y={11} text-anchor="middle">Same swing as its state</text>
      <text class="tick" x={x0} y={L.axisH - 10} text-anchor="middle">0</text>
      {#if !L.narrow}
        <text class="tick hd" x={w - 2} y={L.axisH - 10} text-anchor="end">Median</text>
      {/if}
      {#each L.rows as row (row.kind)}
        <!-- One tab stop per row; arrow keys walk its dots and show each one's details. -->
        <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
        <g
          class="row"
          role="group"
          tabindex="0"
          aria-label={`${row.kind}, ${row.n} ${row.n === 1 ? 'place' : 'places'}, median ${signed(row.med, 1)} relative to the state. Use the arrow keys to read each place.`}
          onkeydown={(e) => onRowKey(e, row)}
          onblur={() => (hover = null)}
        >
          <rect class="band" x={0} y={row.y} width={w} height={row.rowH} />
          {#if L.narrow}
            <text class="lbl" x={0} y={row.y + 12}>{row.kind} <tspan class="n">n = {row.n} · median {signed(row.med, 1)}</tspan></text>
          {:else}
            <text class="lbl" x={L.labelW - 4} y={row.cy - 6} text-anchor="end">{row.kind}</text>
            <text class="n" x={L.labelW - 4} y={row.cy + 9} text-anchor="end">n = {row.n}</text>
            <text class="medv" x={w - 2} y={row.cy} dy="0.35em" text-anchor="end">{signed(row.med, 1)}</text>
          {/if}
          {#each row.dots as d (d.key)}
            <circle class="dot" class:on={tip?.key === d.key} cx={d.cx} cy={d.cy} r={L.r} />
          {/each}
          {#if row.med != null}
            {@const span = L.r + 7}
            <line class="med" x1={L.x(row.med)} x2={L.x(row.med)} y1={row.cy - span} y2={row.cy + span} />
          {/if}
        </g>
      {/each}
    </svg>
    {#if tip}
      {@const td = all(L).find((d) => d.key === tip.key)}
      {#if td}
        <Tip x={td.cx} y={td.cy} width={w} height={Math.max(h, L.bottom)} title={td.place} lines={tipLines(td)} pinned={!!pinned} onclose={() => (pinned = null)} />
      {/if}
    {/if}
  {/snippet}

  {#snippet table()}
    <table>
      <caption>Swing toward Democrats, 2024 president → 2026, in points. Relative = place’s swing minus the state’s (House: the nation’s) swing in the same race.</caption>
      <thead>
        <tr><th>Place</th><th>Kind</th><th>Race</th><th class="n">Swing</th><th class="n">State swing</th><th class="n">Relative</th><th>Source</th></tr>
      </thead>
      <tbody>
        {#each kinds as k (k)}
          {#each places.filter((p) => p.kind === k).sort((a, b) => b.relative - a.relative) as p (p.key)}
            <tr>
              <td>{p.place}</td><td>{p.kind}</td><td>{p.race}</td>
              <td class="n">{signed(p.shift, 1)}</td>
              <td class="n">{signed(p.reference_shift, 1)}{isNat(p) ? ' (U.S.)' : ''}</td>
              <td class="n">{signed(p.relative, 1)}</td>
              <td><a href={p.source} target="_blank" rel="noopener">{domainName(p.source, ctx).replace(/ results pages$/, '')}</a></td>
            </tr>
          {/each}
        {/each}
      </tbody>
    </table>
  {/snippet}
</StageFrame>

<style>
  td a {
    color: var(--ink);
    text-underline-offset: 2px;
  }
  .lg {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .cap {
    margin: 0;
    max-width: 62rem;
    color: var(--ink);
    font-family: var(--font-prose);
    font-size: 14px;
    line-height: 1.4;
  }
  .plot {
    display: block;
    overflow: visible;
    font-family: var(--font-ui);
    cursor: default;
    touch-action: pan-y;
  }
  .grid {
    stroke: var(--grid);
  }
  .zero {
    stroke: var(--ink-2);
    stroke-width: 1.25;
  }
  .tick {
    font-size: 11px;
    fill: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .hd {
    font-weight: 600;
    fill: var(--ink-2);
  }
  .zlbl {
    font-size: 11px;
    font-weight: 600;
    fill: var(--ink-2);
  }
  .row {
    outline: none;
  }
  .band {
    fill: transparent;
    stroke: none;
  }
  .row:focus-visible .band {
    fill: var(--surface-2);
    stroke: var(--dem);
    stroke-width: 2;
  }
  .lbl,
  .n {
    paint-order: stroke;
    stroke: var(--bg);
    stroke-width: 4px;
    stroke-linejoin: round;
  }
  .lbl {
    font-size: 12.5px;
    font-weight: 600;
    fill: var(--ink);
  }
  .n {
    font-size: 11px;
    font-weight: 400;
    fill: var(--muted);
  }
  .medv {
    font-size: 12px;
    font-weight: 600;
    fill: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  .dot {
    fill: var(--ink-2);
    fill-opacity: 0.55;
    stroke: var(--bg);
    stroke-width: 1;
  }
  .dot.on {
    fill: var(--ink);
    fill-opacity: 1;
    stroke: var(--ink);
    stroke-width: 2;
  }
  line.med {
    stroke: var(--ink);
    stroke-width: 2.5;
    stroke-linecap: round;
  }
  @media (max-width: 760px) {
    .cap {
      font-size: 12.5px;
      line-height: 1.35;
    }
  }
</style>
