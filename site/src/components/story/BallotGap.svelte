<script>
  // Stage: ballot measures vs. the Democrat at the top of the same state's ticket.
  // x = Democratic top-of-ticket margin (2026), y = the progressive side's margin on the
  // measure (= x + gap_measure_vs_dem). Above the diagonal = the measure ran ahead.
  // Populist measures are highlighted and labeled; everything is computed from the file.
  import { scaleLinear } from 'd3-scale';
  import StageFrame from './StageFrame.svelte';
  import { measuresSource, measuresShort } from './sources.js';
  import Tip from './Tip.svelte';
  import { signed, margin, num, median, shortAsOf, asOfLabel } from './util.js';

  let { ctx, nodes = [], highlight = 'populist', title = 'Ballot measures vs. the Democrat on the same ballot', ...rest } = $props();

  const all = $derived(ctx?.data?.story?.measures?.measures ?? []);
  // "Populist" here means economic populism from the left (taxes on the rich, wages) or an
  // explicit money-in-politics / anti-corruption measure. The file's own `populist` flag also
  // marks e.g. MA Question 5 (taxpayer rebates, coded conservative_economic), which is not.
  const MONEY_IN_POLITICS = /campaign finance|money in politics|corruption|transparency|contribution|political spending/i;
  const isPopulist = (m) =>
    m.populist === true && (m.valence === 'progressive_economic' || MONEY_IN_POLITICS.test(`${m.topic ?? ''} ${m.title ?? ''}`));
  const pts = $derived(
    all
      .filter((m) => m.gap_measure_vs_dem != null && m.dem_top_of_ticket_margin_2026 != null)
      .map((m) => ({
        ...m,
        key: m.id,
        x: m.dem_top_of_ticket_margin_2026,
        y: m.dem_top_of_ticket_margin_2026 + m.gap_measure_vs_dem,
        hi: highlight === 'populist' ? isPopulist(m) : typeof highlight === 'function' ? highlight(m) : false,
      })),
  );
  const skipped = $derived(all.length - pts.length);
  const pop = $derived(pts.filter((p) => p.hi));
  const stats = $derived({
    n: pop.length,
    ahead: pop.filter((p) => p.gap_measure_vs_dem > 0).length,
    med: median(pop.map((p) => p.gap_measure_vs_dem)),
    redN: pop.filter((p) => p.x < 0).length,
    redAhead: pop.filter((p) => p.x < 0 && p.gap_measure_vs_dem > 0).length,
    otherMed: median(pts.filter((p) => !p.hi).map((p) => p.gap_measure_vs_dem)),
  });

  const shortName = (m) =>
    m.id
      .replace(/-(Aug|Apr|Jun)$/, '')
      .replace(/-20\d\d$/, '')
      .replace(/-/g, ' ');

  /**
   * Global label placement for the highlighted measures: every label tries spots around its
   * dot (right, left, above, below, then further out with a leader line) and takes the one
   * that overlaps least with labels already placed (either side), all dots and the two
   * region captions. On phones the labels are numbers keyed to a list under the chart.
   */
  function placeLabels(list, x, y, { w, ph, m, numbered, others, regions }) {
    const CH = 6.4;
    const H = 13;
    const order = [...list].sort((a, b) => y(a.y) - y(b.y) || x(a.x) - x(b.x));
    const dots = [...others.map((p) => ({ cx: x(p.x), cy: y(p.y), r: 5 })), ...list.map((p) => ({ cx: x(p.x), cy: y(p.y), r: 6.5 }))];
    const boxes = [...regions];
    const ov = (a, b) => Math.max(0, Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0)) * Math.max(0, Math.min(a.y1, b.y1) - Math.max(a.y0, b.y0));
    const out = [];
    order.forEach((p, i) => {
      const text = numbered ? String(i + 1) : shortName(p);
      const tw = text.length * (numbered ? 7 : CH) + 2;
      const px = x(p.x), py = y(p.y);
      const cands = [];
      for (const dist of [10, 22, 36, 52]) {
        for (const [dx, dy] of [[1, 0], [-1, 0], [0, -1], [0, 1], [1, -1], [-1, -1], [1, 1], [-1, 1]]) {
          cands.push({ dx: dx * dist, dy: dy * (dist * 0.8 + (dy ? 4 : 0)), far: dist > 10 });
        }
      }
      let best = null;
      cands.forEach((c, k) => {
        const anchor = c.dx > 0 ? 'start' : c.dx < 0 ? 'end' : 'middle';
        const tx = px + c.dx;
        const ty = py + c.dy;
        const x0 = anchor === 'start' ? tx : anchor === 'end' ? tx - tw : tx - tw / 2;
        const box = { x0: x0 - 2, x1: x0 + tw + 2, y0: ty - H / 2 - 1, y1: ty + H / 2 + 1 };
        let s = 0;
        for (const b of boxes) s += 4 * ov(box, b);
        for (const d of dots) s += (d.cx === px && d.cy === py ? 6 : 2) * ov(box, { x0: d.cx - d.r, x1: d.cx + d.r, y0: d.cy - d.r, y1: d.cy + d.r });
        const area = (box.x1 - box.x0) * (box.y1 - box.y0);
        s += 8 * (area - ov(box, { x0: m.l, x1: w - m.r + 4, y0: m.t, y1: ph - m.b }));
        s += k * 0.6; // prefer close, simple placements
        if (!best || s < best.s) best = { s, box, tx, ty, anchor, c };
      });
      boxes.push(best.box);
      // leader from the dot's edge to the label's near edge
      const ax = best.anchor === 'start' ? best.box.x0 : best.anchor === 'end' ? best.box.x1 : best.tx;
      const ay = best.anchor === 'middle' ? (best.c.dy < 0 ? best.box.y1 : best.box.y0) : best.ty;
      out.push({ p, n: i + 1, text, tx: best.tx, ty: best.ty, anchor: best.anchor, px, py, ax, ay, lead: best.c.far });
    });
    return out;
  }

  let showTable = $state(false);
  let hover = $state(null);
  let pinned = $state(null);
  const tip = $derived(pinned ?? hover);
  const toggle = (p) => (pinned = pinned?.key === p.key ? null : p);
  const tipLines = (p) => [
    `${p.state}, ${p.year}`,
    `Progressive side: ${margin(p.y)}${p.yes_pct != null ? ` (yes ${num(p.yes_pct)}%)` : ''}`,
    `Democrat at top of ticket: ${margin(p.x)}${p.year !== 2026 ? ' (2026)' : ''}`,
    `Measure ran ${signed(p.gap_measure_vs_dem)} vs. the Democrat`,
    p.partial_count ? `Still counting${p.pct_expected_vote_counted != null ? ` (${num(p.pct_expected_vote_counted, 0)}% in)` : ''}` : null,
  ];
</script>

<StageFrame
  {title}
  dek="Each dot is a measure: the progressive side’s margin against the Democratic margin at the top of the same state’s ticket. Above the line, the measure ran ahead of the Democrat."
  note={`Preliminary, as of ${asOfLabel(ctx)}; many measures are still counting.${skipped ? ` ${skipped} measures without comparable margins are not shown.` : ''}`}
  source={measuresSource(ctx)}
  sourceShort={measuresShort(ctx)}
  bind:showTable
  onbackground={() => (pinned = null)}
>
  {#snippet legend()}
    <span class="lg"><svg width="14" height="14" viewBox="-7 -7 14 14"><circle r="5" class="dot hi" /></svg>Populist measure (taxes on the rich, wages, money in politics)</span>
    <span class="lg"><svg width="14" height="14" viewBox="-7 -7 14 14"><circle r="4" class="dot" /></svg>Other measure</span>
  {/snippet}

  {#snippet chart(w, h)}
    {@const narrow = w < 560}
    {@const capH = (narrow ? 64 : 44) + (w < 480 ? 36 : 0)}
    {@const m = { l: narrow ? 34 : 44, r: narrow ? 8 : 16, t: 8, b: 34 }}
    {@const ph = Math.max(220, h - capH)}
    {@const xs = pts.map((p) => p.x)}
    {@const ys = pts.map((p) => p.y)}
    {@const xd = [Math.floor(Math.min(...xs, 0) / 10) * 10, Math.ceil(Math.max(...xs, 0) / 10) * 10]}
    {@const yd = [Math.floor(Math.min(...ys, xd[0]) / 10) * 10, Math.ceil(Math.max(...ys, xd[1]) / 10) * 10]}
    {@const x = scaleLinear().domain(xd).range([m.l, w - m.r])}
    {@const y = scaleLinear().domain(yd).range([ph - m.b, m.t])}
    {@const xt = x.ticks(narrow ? 4 : 6)}
    {@const yt = y.ticks(narrow ? 5 : 7)}
    {@const numbered = w < 480}
    {@const placed = placeLabels(pop, x, y, { w, ph, m, numbered, others: pts.filter((p) => !p.hi), regions: [
      { x0: m.l + 6, x1: m.l + 6 + 205, y0: m.t + 1, y1: m.t + 15 },
      { x0: w - m.r - 6 - 75, x1: w - m.r - 6, y0: ph - m.b - 19, y1: ph - m.b - 5 },
    ] })}
    <svg class="plot" width={w} height={ph} role="img" aria-label={`Scatter of ${pts.length} ballot measures. Use Show as table for the numbers.`}>
      {#each xt as t (t)}
        <line class={t === 0 ? 'zero' : 'gl'} x1={x(t)} x2={x(t)} y1={m.t} y2={ph - m.b} />
        <text class="tick" x={x(t)} y={ph - m.b + 14} text-anchor="middle">{margin(t, 0)}</text>
      {/each}
      {#each yt as t (t)}
        <line class={t === 0 ? 'zero' : 'gl'} x1={m.l} x2={w - m.r} y1={y(t)} y2={y(t)} />
        <text class="tick" x={m.l - 5} y={y(t)} dy="0.32em" text-anchor="end">{signed(t, 0)}</text>
      {/each}
      <text class="axl" x={(m.l + w - m.r) / 2} y={ph - 4} text-anchor="middle">Democrat’s margin at the top of the ticket →</text>
      <!-- y = x: the measure ran even with the Democrat -->
      <line class="diag" x1={x(Math.max(xd[0], yd[0]))} y1={y(Math.max(xd[0], yd[0]))} x2={x(Math.min(xd[1], yd[1]))} y2={y(Math.min(xd[1], yd[1]))} />
      <text class="rg" x={m.l + 6} y={m.t + 12}>↑ Measure ran ahead of the Democrat</text>
      <text class="rg" x={w - m.r - 6} y={ph - m.b - 8} text-anchor="end">Ran behind ↓</text>
      {#each pts.filter((p) => !p.hi) as p (p.key)}
        <g class="pt" class:active={tip?.key === p.key} role="button" tabindex="0" aria-label={`${p.title}. ${tipLines(p).filter(Boolean).join('; ')}`}
          onpointerenter={(e) => e.pointerType === 'mouse' && (hover = p)} onpointerleave={() => (hover = null)} onfocus={() => (hover = p)} onblur={() => (hover = null)}
          onclick={(e) => { e.stopPropagation(); toggle(p); }} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle(p))}>
          <circle class="hit" cx={x(p.x)} cy={y(p.y)} r="10" />
          <circle class="dot" cx={x(p.x)} cy={y(p.y)} r="4" />
        </g>
      {/each}
      {#each placed as l (l.p.key)}
        {#if l.lead}<line class="lead" x1={l.px} y1={l.py} x2={l.ax} y2={l.ay} />{/if}
        <text class="plab" class:num={numbered} x={l.tx} y={l.ty} dy="0.32em" text-anchor={l.anchor}>{l.text}</text>
      {/each}
      {#each pop as p (p.key)}
        <g class="pt" class:active={tip?.key === p.key} role="button" tabindex="0" aria-label={`${p.title}. ${tipLines(p).filter(Boolean).join('; ')}`}
          onpointerenter={(e) => e.pointerType === 'mouse' && (hover = p)} onpointerleave={() => (hover = null)} onfocus={() => (hover = p)} onblur={() => (hover = null)}
          onclick={(e) => { e.stopPropagation(); toggle(p); }} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle(p))}>
          <circle class="hit" cx={x(p.x)} cy={y(p.y)} r="12" />
          <circle class="dot hi" cx={x(p.x)} cy={y(p.y)} r="5.5" />
        </g>
      {/each}
    </svg>
    {#if numbered && placed.length}
      <ol class="keylist">
        {#each [...placed].sort((a, b) => a.n - b.n) as l (l.p.key)}<li><b>{l.n}</b> {shortName(l.p)}</li>{/each}
      </ol>
    {/if}
    <p class="cap">
      {#if stats.n}
        {stats.ahead} of {stats.n} populist measures ran ahead of the Democrat on the same ballot; the median one ran {signed(stats.med)} points{#if stats.otherMed != null}{' '}(other measures: {signed(stats.otherMed)}){/if}.
        {#if stats.redN}Where the Democrat trailed, {stats.redAhead} of {stats.redN} ran ahead.{/if}
      {/if}
    </p>
    {#if tip}
      <Tip x={x(tip.x)} y={y(tip.y)} width={w} height={h} title={tip.title} lines={tipLines(tip)} pinned={!!pinned} onclose={() => (pinned = null)} />
    {/if}
  {/snippet}

  {#snippet table()}
    <table>
      <caption>Ballot measures: progressive side’s margin vs. the Democrat at the top of the ticket (points)</caption>
      <thead><tr><th>Measure</th><th>State</th><th>Populist</th><th class="n">Progressive side</th><th class="n">Democrat</th><th class="n">Gap</th></tr></thead>
      <tbody>
        {#each [...pts].sort((a, b) => Number(b.hi) - Number(a.hi) || b.gap_measure_vs_dem - a.gap_measure_vs_dem) as p (p.key)}
          <tr>
            <td>{p.title}{p.partial_count ? ' (counting)' : ''}{p.year !== 2026 ? ` (${p.year})` : ''}</td>
            <td>{p.state}</td>
            <td>{p.hi ? 'Yes' : ''}</td>
            <td class="n">{margin(p.y)}</td>
            <td class="n">{margin(p.x)}</td>
            <td class="n">{signed(p.gap_measure_vs_dem)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/snippet}
</StageFrame>

<style>
  .lg {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .plot {
    display: block;
    overflow: visible;
    font-family: var(--font-ui);
  }
  .gl {
    stroke: var(--grid);
  }
  .zero {
    stroke: var(--axis);
    stroke-width: 1.5;
  }
  .tick {
    font-size: 10.5px;
    fill: var(--muted);
  }
  .axl {
    font-size: 11px;
    fill: var(--ink-2);
  }
  .diag {
    stroke: var(--ink-2);
    stroke-width: 1.5;
    stroke-dasharray: 5 4;
  }
  .rg {
    font-size: 11px;
    fill: var(--ink-2);
    font-weight: 600;
    paint-order: stroke;
    stroke: var(--bg);
    stroke-width: 4px;
  }
  .dot {
    fill: var(--bg);
    stroke: var(--muted);
    stroke-width: 1.5;
  }
  .dot.hi {
    fill: var(--ink);
    stroke: var(--bg);
    stroke-width: 2;
  }
  .hit {
    fill: transparent;
  }
  .pt {
    cursor: pointer;
    outline: none;
  }
  .pt:hover .dot,
  .pt.active .dot {
    stroke: var(--ink);
  }
  .pt:focus-visible .hit {
    stroke: var(--dem);
    stroke-width: 2;
  }
  .lead {
    stroke: var(--axis);
    stroke-width: 1;
  }
  .plab {
    font-size: 11px;
    font-weight: 600;
    fill: var(--ink);
    paint-order: stroke;
    stroke: var(--bg);
    stroke-width: 3px;
  }
  .plab.num {
    font-size: 11.5px;
    font-weight: 700;
  }
  .keylist {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 12px;
    margin: 4px 0 0;
    padding: 0;
    list-style: none;
    font-size: 11.5px;
    color: var(--ink-2);
  }
  .keylist b {
    color: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  .cap {
    margin: 6px 0 0;
    font-size: 12px;
    line-height: 1.4;
    color: var(--ink-2);
  }
</style>
