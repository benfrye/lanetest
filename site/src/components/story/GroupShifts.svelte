<script>
  // Stage: how much each voter group shifted from 2024 to 2026, by two independent sources
  // (group_sources.json): NYT Voter Trends (filled circle) and the SSRS network voter poll
  // (hollow diamond). Rows where they differ by more than 5 points get a bracket; AP Voter
  // Poll approximations (2026 margin only) are noted with "≈". No party or archetype colors:
  // the marks are distinguished by shape, in ink.
  import { scaleLinear } from 'd3-scale';
  import StageFrame from './StageFrame.svelte';
  import Tip from './Tip.svelte';
  import { margin, signed, shortAsOf } from './util.js';

  let { ctx, nodes = [], highlight = null, title = 'Who swung: two sources, 2024 → 2026', threshold = 5, ...rest } = $props();

  const gs = $derived(ctx?.data?.story?.groupSources ?? {});
  const srcs = $derived(gs.sources ?? {});
  const nytUpdated = $derived(ctx?.data?.story?.nyt?.nyt_last_updated);

  // Section for each group label; unknown labels fall into one trailing section.
  const DIM_OF = {
    Men: 'Gender', Women: 'Gender',
    '18-29': 'Age', '30-44': 'Age', '45-64': 'Age', '65+': 'Age',
    White: 'Race', Black: 'Race', Hispanic: 'Race', Asian: 'Race',
    'College degree': 'Education', 'No college degree': 'Education',
    'White, college': 'Race × education', 'White, no college': 'Race × education',
  };
  const NOUN = {
    Men: 'men', Women: 'women', '18-29': 'voters under 30', '65+': 'voters 65 and older',
    White: 'white voters', 'College degree': 'college graduates', 'No college degree': 'voters without a degree',
    'White, college': 'white college graduates', 'White, no college': 'white voters without a degree',
  };
  const noun = (g) => NOUN[g] ?? (/^\d/.test(g) ? `voters ${g}` : `${g} voters`);

  const rows = $derived(
    (gs.groups ?? []).map((g, i) => {
      const a = g.nyt?.shift ?? null;
      const b = g.ssrs?.shift ?? null;
      const gap = a != null && b != null ? a - b : null;
      return { ...g, key: g.group, i, dim: DIM_OF[g.group] ?? 'Other', a, b, gap, differs: gap != null && Math.abs(gap) > threshold };
    }),
  );
  const both = $derived(rows.filter((r) => r.gap != null));
  const agree = $derived(both.filter((r) => !r.differs).length);
  const worst = $derived([...both].sort((x, y) => Math.abs(y.gap) - Math.abs(x.gap))[0]);
  const biggest = $derived([...both].sort((x, y) => y.a + y.b - (x.a + x.b))[0]);
  const smallest = $derived([...both].sort((x, y) => x.a + x.b - (y.a + y.b))[0]);
  const caption = $derived(
    both.length
      ? `Both sources put the biggest swing among ${noun(biggest.group)} and the smallest among ${noun(smallest.group)}. They agree within ${threshold} points on ${agree} of ${both.length} groups and differ most on ${noun(worst.group)} (${signed(worst.a, 0)} vs. ${signed(worst.b, 0)}).`
      : '',
  );

  let showTable = $state(false);
  let hover = $state(null);
  let pinned = $state(null);
  const tip = $derived(pinned ?? hover);

  const tw = (s, px = 10.5) => s.length * px * 0.56;

  function layout(w, h) {
    const narrow = w < 520;
    const labelW = narrow ? 100 : 136;
    const colW = narrow ? 30 : 44;
    const valW = colW * 2 + 6;
    const axisH = 20;
    const headH = narrow ? 14 : 18;
    const dims = [...new Set(rows.map((r) => r.dim))];
    const n = rows.length;
    const avail = h - axisH - dims.length * headH - 6;
    const rowH = Math.max(narrow ? 23 : 26, Math.min(40, avail / Math.max(1, n)));
    const twoLine = rowH >= 34 && !narrow;
    let y = axisH;
    const placed = [];
    const heads = [];
    for (const d of dims) {
      heads.push({ label: d, y: y + headH - 5 });
      y += headH;
      for (const r of rows.filter((q) => q.dim === d)) {
        placed.push({ ...r, y: y + rowH / 2 });
        y += rowH;
      }
    }
    const vals = rows.flatMap((r) => [r.a, r.b]).filter((v) => v != null);
    const lo = Math.floor(Math.min(0, ...vals) / 10) * 10;
    const hi = Math.ceil(Math.max(0, ...vals) / 10) * 10;
    const x = scaleLinear().domain([lo, hi]).range([labelW + 12, w - valW - 14]);
    const ticks = x.ticks(narrow ? 3 : 6);
    return { placed, heads, x, ticks, rowH, labelW, colW, valW, w, h, bottom: y + 4, narrow, twoLine };
  }

  const enter = (e, r) => e.pointerType === 'mouse' && (hover = r);
  const toggle = (r) => (pinned = pinned?.key === r.key ? null : r);
  const side = (s) =>
    s?.shift == null
      ? null
      : s.margin_2026 == null
        ? `shift ${signed(s.shift, 0)} (margins not published)`
        : `${margin(s.margin_2024, 0)} → ${margin(s.margin_2026, 0)}, shift ${signed(s.shift, 0)}`;
  const tipLines = (r) => [
    r.nyt ? `NYT: ${side(r.nyt)}` : null,
    r.ssrs ? `Network poll: ${side(r.ssrs)}` : 'Network poll: not published',
    r.ap ? `AP Voter Poll ≈ ${margin(r.ap.margin_2026, 0)} in 2026 (${r.ap.text})` : null,
    r.gap != null ? (r.differs ? `Sources differ by ${Math.abs(r.gap)} points` : `Sources within ${Math.abs(r.gap)} ${Math.abs(r.gap) === 1 ? 'point' : 'points'}`) : null,
  ];
  const diamond = (cx, cy, s) => `M${cx},${cy - s}L${cx + s},${cy}L${cx},${cy + s}L${cx - s},${cy}Z`;
  const short = (s) => (s ?? '').replace(/\s*\(.*\)$/, '');
</script>

<StageFrame
  {title}
  dek="Shift in each group’s margin toward Democrats, 2024 president to 2026 House, in points, as estimated by two independent sources."
  note={`${gs.note ?? ''} Preliminary; NYT estimates updated ${shortAsOf(nytUpdated)}.`}
  source={`Sources: ${srcs.nyt?.name ?? 'NYT Voter Trends'}${srcs.nyt?.method ? `, ${srcs.nyt.method}` : ''}; ${(srcs.ssrs?.name ?? 'network voter poll').replace(/^N/, 'n')}; ${srcs.ap?.name ?? 'AP Voter Poll'} (≈). ${gs.definition ?? ''}`}
  sourceShort="Sources: NYT Voter Trends, network poll (SSRS), AP (≈)."
  bind:showTable
  onbackground={() => (pinned = null)}
>
  {#snippet legend()}
    <span class="lg"><svg width="14" height="14" viewBox="-7 -7 14 14"><circle r="5" class="m-nyt" /></svg>{short(srcs.nyt?.name) || 'NYT Voter Trends'}</span>
    <span class="lg"><svg width="14" height="14" viewBox="-7 -7 14 14"><path d={diamond(0, 0, 5.5)} class="m-poll" /></svg>Network voter poll (SSRS)</span>
    <span class="lg"><b class="approx">≈</b>AP Voter Poll, 2026 margin only</span>
  {/snippet}

  {#snippet banner()}
    {#if caption}<p class="cap">{caption}</p>{/if}
  {/snippet}

  {#snippet chart(w, h)}
    {@const L = layout(w, h)}
    <svg class="plot" width={w} height={L.bottom} role="img" aria-label={`Dot plot of each group's shift toward Democrats by two sources. ${caption} Use Show as table for the numbers.`}>
      {#each L.ticks as t (t)}
        <line class={t === 0 ? 'zero' : 'grid'} x1={L.x(t)} x2={L.x(t)} y1={14} y2={L.bottom - 4} />
        <text class="tick" x={L.x(t)} y={10} text-anchor="middle">{t === 0 ? (L.narrow ? '0' : 'no shift') : signed(t, 0)}</text>
      {/each}
      <text class="tick hd" x={w - L.colW - 6} y={10} text-anchor="end">NYT</text>
      <text class="tick hd" x={w - 2} y={10} text-anchor="end">Poll</text>
      {#each L.heads as hd (hd.label)}
        <text class="dim" x={0} y={hd.y}>{hd.label}</text>
      {/each}
      {#each L.placed as r (r.key)}
        {@const active = tip?.key === r.key}
        {@const xa = r.a != null ? L.x(r.a) : null}
        {@const xb = r.b != null ? L.x(r.b) : null}
        {@const s = Math.min(5.5, L.rowH / 4.4)}
        {@const lblY = L.twoLine && r.ap ? r.y - 5 : r.y}
        <g
          class="row"
          class:active
          class:differs={r.differs}
          role="button"
          tabindex="0"
          aria-label={`${r.group}: ${tipLines(r).filter(Boolean).join('; ')}`}
          onpointerenter={(e) => enter(e, r)}
          onpointerleave={() => (hover = null)}
          onfocus={() => (hover = r)}
          onblur={() => (hover = null)}
          onclick={(e) => { e.stopPropagation(); toggle(r); }}
          onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle(r))}
        >
          <rect class="hit" x={0} y={r.y - L.rowH / 2} width={w} height={L.rowH} />
          <text class="lbl" x={L.labelW} y={lblY} dy="0.35em" text-anchor="end">{r.group}{#if r.ap && !L.twoLine}<tspan class="approx-t" dx="3">≈</tspan>{/if}</text>
          {#if r.ap && L.twoLine}
            <text class="ap" x={L.labelW} y={r.y + 9} dy="0.35em" text-anchor="end">≈ AP: {margin(r.ap.margin_2026, 0)} in 2026</text>
          {/if}
          {#if xa != null && xb != null}
            <line class="conn" x1={xa} x2={xb} y1={r.y} y2={r.y} />
          {/if}
          {#if r.differs}
            {@const x0 = Math.min(xa, xb)}
            {@const x1 = Math.max(xa, xb)}
            {@const by = r.y + s + 3}
            {@const label = L.narrow ? `differ by ${Math.abs(r.gap)}` : `sources differ by ${Math.abs(r.gap)}`}
            {@const right = x1 + 8 + tw(label) < w - L.valW - 4}
            <path class="bracket" d={`M${x0},${by - 3}V${by}H${x1}V${by - 3}`} />
            <text class="diff" x={right ? x1 + 8 : x0 - 8} y={r.y} dy="0.35em" text-anchor={right ? 'start' : 'end'}>{label}</text>
          {/if}
          {#if xb != null}<path class="m-poll" d={diamond(xb, r.y, s + 0.8)} />{/if}
          {#if xa != null}<circle class="m-nyt" cx={xa} cy={r.y} r={s} />{/if}
          <text class="val" x={w - L.colW - 6} y={r.y} dy="0.35em" text-anchor="end">{signed(r.a, 0)}</text>
          <text class="val" x={w - 2} y={r.y} dy="0.35em" text-anchor="end">{r.b != null ? signed(r.b, 0) : '–'}</text>
        </g>
      {/each}
    </svg>
    {#if tip}
      {@const tr = L.placed.find((p) => p.key === tip.key)}
      {#if tr}
        <Tip x={L.x(Math.max(tr.a ?? -Infinity, tr.b ?? -Infinity))} y={tr.y} width={w} height={Math.max(h, L.bottom)} title={tr.group} lines={tipLines(tr)} pinned={!!pinned} onclose={() => (pinned = null)} />
      {/if}
    {/if}
  {/snippet}

  {#snippet table()}
    <table>
      <caption>Margin by group, Democrat minus Republican (points). Shift = 2026 House minus 2024 president, within each source.</caption>
      <thead>
        <tr>
          <th>Group</th>
          <th class="n">NYT 2024</th><th class="n">NYT 2026</th><th class="n">NYT shift</th>
          <th class="n">Poll 2024</th><th class="n">Poll 2026</th><th class="n">Poll shift</th>
          <th class="n">AP 2026 (≈)</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as r (r.key)}
          <tr>
            <td>{r.group}</td>
            <td class="n">{margin(r.nyt?.margin_2024, 0)}</td>
            <td class="n">{margin(r.nyt?.margin_2026, 0)}</td>
            <td class="n">{signed(r.a, 0)}</td>
            <td class="n">{margin(r.ssrs?.margin_2024, 0)}</td>
            <td class="n">{margin(r.ssrs?.margin_2026, 0)}</td>
            <td class="n">{signed(r.b, 0)}</td>
            <td class="n">{r.ap ? '≈ ' + margin(r.ap.margin_2026, 0) : ''}</td>
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
  .approx {
    font-weight: 700;
    color: var(--ink);
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
  }
  .grid {
    stroke: var(--grid);
  }
  .zero {
    stroke: var(--axis);
    stroke-width: 1.5;
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
  .dim {
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    fill: var(--muted);
  }
  .row {
    cursor: pointer;
    outline: none;
  }
  .hit {
    fill: transparent;
  }
  .row:hover .hit,
  .row.active .hit,
  .row:focus-visible .hit {
    fill: var(--surface-2);
  }
  .row:focus-visible .hit {
    stroke: var(--dem);
    stroke-width: 2;
  }
  .lbl {
    font-size: 12px;
    fill: var(--ink);
  }
  .approx-t {
    font-weight: 700;
    fill: var(--ink-2);
  }
  .ap {
    font-size: 10.5px;
    fill: var(--ink-2);
  }
  .val {
    font-size: 12px;
    fill: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }
  .differs .val {
    fill: var(--ink);
    font-weight: 700;
  }
  .conn {
    stroke: var(--axis);
    stroke-width: 2;
  }
  .m-nyt {
    fill: var(--ink);
    stroke: var(--bg);
    stroke-width: 1.2;
  }
  .m-poll {
    fill: var(--bg);
    fill-opacity: 0.6;
    stroke: var(--ink);
    stroke-width: 1.6;
  }
  .bracket {
    fill: none;
    stroke: var(--ink-2);
    stroke-width: 1;
  }
  .diff {
    font-size: 10.5px;
    font-weight: 600;
    fill: var(--ink-2);
  }
  @media (max-width: 760px) {
    .cap {
      font-size: 12.5px;
      line-height: 1.35;
    }
  }
</style>
