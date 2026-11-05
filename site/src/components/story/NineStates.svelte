<script>
  // Stage: NYT Times Voter Trends, nine Senate races: shift vs. 2024 by group, one small
  // multiple per state (narrow screens: one strip per group, Maine picked out).
  // Descriptive only (claims ledger C10): nine races, one Democrat each.
  import { scaleLinear } from 'd3-scale';
  import StageFrame from './StageFrame.svelte';
  import { nytSource } from './sources.js';
  import ArchChip from './ArchChip.svelte';
  import Tip from './Tip.svelte';
  import { signed, stateName, shortAsOf } from './util.js';

  const DEFAULT_GROUPS = ['Male', 'Female', 'White', 'Nonwhite', '18-29', '30-44', '45-64', '65+', 'White college', 'White non-college'];
  let { ctx, nodes = [], groups = DEFAULT_GROUPS, focus = 'ME', title = 'Nine Senate races, group by group', ...rest } = $props();

  const nine = $derived(ctx?.data?.story?.nine ?? {});
  const nyt = $derived(ctx?.data?.story?.nyt ?? {});
  const tidy = $derived(nine.tidy ?? []);
  const states = $derived([...new Set(tidy.map((r) => r.state))]);
  const tbl = $derived(Object.fromEntries((nine.table ?? []).map((r) => [r.state, r])));
  const val = $derived(Object.fromEntries(tidy.map((r) => [r.state + '|' + r.group, r.shift])));
  const natl = $derived(Object.fromEntries((nyt.groups ?? []).map((g) => [g.group, g.shift_vs_2024])));
  const shown = $derived(groups.filter((g) => states.some((s) => val[s + '|' + g] != null)));

  // Where does the focus state rank? Count groups in which it had the smallest shift.
  const lowest = $derived.by(() => {
    const out = [];
    for (const g of shown) {
      const vs = states.map((s) => val[s + '|' + g]).filter((v) => v != null);
      const f = val[focus + '|' + g];
      if (f != null && f === Math.min(...vs)) out.push(g);
    }
    return out;
  });
  const domain = $derived.by(() => {
    const v = tidy.map((r) => r.shift).concat(shown.map((g) => natl[g]).filter((x) => x != null), [0]);
    return [Math.floor(Math.min(...v) / 10) * 10, Math.ceil(Math.max(...v) / 10) * 10];
  });

  let showTable = $state(false);
  let hover = $state(null);
  let pinned = $state(null);
  const tip = $derived(pinned ?? hover);
  const toggle = (it) => (pinned = pinned?.key === it.key ? null : it);
  const disc = $derived(nine.maine_discrepancy);

  function tipLines(st, g) {
    const v = val[st + '|' + g];
    return [`${g}: ${signed(v, 0)} toward ${v >= 0 ? 'Democrats' : 'Republicans'}`, natl[g] != null ? `Nationally (House): ${signed(natl[g], 0)}` : null];
  }
  const handlers = (it) => ({
    onpointerenter: (e) => e.pointerType === 'mouse' && (hover = it),
    onpointerleave: () => (hover = null),
    onfocus: () => (hover = it),
    onblur: () => (hover = null),
    onclick: (e) => {
      e.stopPropagation();
      toggle(it);
    },
    onkeydown: (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle(it)),
  });
</script>

<StageFrame
  {title}
  dek="Shift in the 2026 Senate margin vs. the 2024 presidential margin, by group (points; right = toward Democrats)."
  note={`Preliminary NYT estimates, updated ${shortAsOf(nyt.nyt_last_updated)}. ${nine.caveat ?? ''}`}
  source={nytSource(ctx)}
  sourceShort="Source: New York Times Voter Trends."
  bind:showTable
  onbackground={() => (pinned = null)}
>
  {#snippet legend()}
    <span class="lg"><svg width="12" height="12" viewBox="-6 -6 12 12"><circle r="4" class="dot" /></svg>Group shift in that state</span>
    <span class="lg"><svg width="12" height="12" viewBox="-6 -6 12 12"><line y1="-5" y2="5" class="nat" /></svg>Same group nationally (House)</span>
    <span class="lg">Top right: the state’s overall shift</span>
  {/snippet}

  {#snippet chart(w, h)}
    {@const capH = 46}
    {@const multiples = w >= 560 && h >= 330}
    {@const x0 = scaleLinear().domain(domain)}
    {#if multiples}
      {@const compact = w < 800}
      {@const labelW = compact ? 92 : 112}
      {@const gap = 12}
      {@const cols = 3}
      {@const rowsN = Math.ceil(states.length / cols)}
      {@const pw = (w - labelW - gap * (cols - 1)) / cols}
      {@const headH = 34}
      {@const axisH = 14}
      <!-- at least 12px per group row so the 10px row labels never overlap -->
      {@const ph = Math.max(150, headH + axisH + 6 + shown.length * 12, (h - capH - gap * (rowsN - 1)) / rowsN)}
      {@const rh = (ph - headH - axisH - 6) / shown.length}
      {@const x = x0.copy().range([16, pw - 16])}
      {@const ticks = x.ticks(pw > 220 ? 5 : 3)}
      <svg class="plot" width={w} height={rowsN * ph + (rowsN - 1) * gap} role="img" aria-label="Small multiples of group shifts in nine Senate races. Use Show as table for the numbers.">
        {#each states as st, i (st)}
          {@const cx = labelW + (i % cols) * (pw + gap)}
          {@const cy = Math.floor(i / cols) * (ph + gap)}
          {@const isF = st === focus}
          {@const row = tbl[st] ?? {}}
          <g transform={`translate(${cx},${cy})`}>
            <rect class="pbg" class:focus={isF} width={pw} height={ph} rx="8" />
            <text class="st" x="8" y="15">{stateName(st)}</text>
            <text class="ov" x={pw - 8} y="15" text-anchor="end">{pw < 220 ? '' : 'overall '}{signed(row.overall_shift)}</text>
            <foreignObject x="6" y="18" width={pw - 12} height="16">
              <div class="who">{#if pw >= 220}{row.dem_nominee ?? ''} {/if}{#if row.archetype}<ArchChip id={row.archetype} size={9} />{/if}</div>
            </foreignObject>
            {#each ticks as tk (tk)}
              <line class={tk === 0 ? 'zero' : 'gl'} x1={x(tk)} x2={x(tk)} y1={headH} y2={ph - axisH} />
              <text class="tick" x={x(tk)} y={ph - 3} text-anchor="middle">{signed(tk, 0)}</text>
            {/each}
            {#each shown as g, j (g)}
              {@const v = val[st + '|' + g]}
              {@const y = headH + 3 + j * rh + rh / 2}
              {@const it = { key: st + '|' + g, st, g, px: cx + x(v ?? 0), py: cy + y }}
              {#if v != null}
                <g class="hitg" class:active={tip?.key === it.key} role="button" tabindex="0" aria-label={`${stateName(st)}, ${tipLines(st, g).filter(Boolean).join('; ')}`} {...handlers(it)}>
                  <rect class="hit" x="0" y={y - rh / 2} width={pw} height={rh} />
                  {#if natl[g] != null}<line class="nat" x1={x(natl[g])} x2={x(natl[g])} y1={y - rh * 0.4} y2={y + rh * 0.4} />{/if}
                  <line class="stem" x1={x(0)} x2={x(v)} y1={y} y2={y} />
                  <circle class="dot" class:focus={isF} cx={x(v)} cy={y} r={Math.min(4.5, rh / 2.6)} />
                </g>
              {/if}
            {/each}
          </g>
        {/each}
        {#each Array(rowsN) as _, ri (ri)}
          {#each shown as g, j (g)}
            {@const y = ri * (ph + gap) + headH + 3 + j * rh + rh / 2}
            <text class="gl-lbl" class:em={lowest.includes(g)} x={labelW - 6} y={y} dy="0.35em" text-anchor="end">{compact ? g.replace('non-college', 'non-coll.').replace(' college', ' coll.') : g}</text>
          {/each}
        {/each}
      </svg>
    {:else}
      {@const labelW = 106}
      {@const rh = Math.max(22, Math.min(30, (h - capH - 20) / shown.length))}
      {@const x = x0.copy().range([labelW + 8, w - 10])}
      {@const ticks = x.ticks(4)}
      <svg class="plot" width={w} height={20 + shown.length * rh} role="img" aria-label="Group shifts in nine Senate races, Maine highlighted. Use Show as table for the numbers.">
        {#each ticks as tk (tk)}
          <line class={tk === 0 ? 'zero' : 'gl'} x1={x(tk)} x2={x(tk)} y1="16" y2={20 + shown.length * rh} />
          <text class="tick" x={x(tk)} y="11" text-anchor="middle">{signed(tk, 0)}</text>
        {/each}
        {#each shown as g, j (g)}
          {@const y = 20 + j * rh + rh / 2}
          <text class="gl-lbl" class:em={lowest.includes(g)} x={labelW - 4} y={y} dy="0.35em" text-anchor="end">{g}</text>
          {#if natl[g] != null}<line class="nat" x1={x(natl[g])} x2={x(natl[g])} y1={y - 7} y2={y + 7} />{/if}
          {#each states.filter((s) => s !== focus) as st (st)}
            {#if val[st + '|' + g] != null}<circle class="dot other" cx={x(val[st + '|' + g])} cy={y} r="3.5" />{/if}
          {/each}
          {#if val[focus + '|' + g] != null}
            {@const it = { key: focus + '|' + g, st: focus, g, px: x(val[focus + '|' + g]), py: y }}
            <g class="hitg" role="button" tabindex="0" aria-label={`${stateName(focus)}, ${tipLines(focus, g).filter(Boolean).join('; ')}`} {...handlers(it)}>
              <rect class="hit" x="0" y={y - rh / 2} width={w} height={rh} />
              <circle class="dot focus" cx={it.px} cy={y} r="5.5" />
              {#if j === 0}<text class="flab" x={it.px} y={y - 8} text-anchor="middle">{focus}</text>{/if}
            </g>
          {/if}
        {/each}
      </svg>
    {/if}
    <p class="cap">
      {#if lowest.length}
        {stateName(focus)}’s shift was the smallest of the nine in {lowest.length} of {shown.length} groups shown{#if lowest.length <= 4} ({lowest.join(', ')}){/if}.
      {/if}
      {#if disc && focus === 'ME'}
        These NYT estimates imply {signed(disc.nyt_9state_implied)} in Maine overall; the count so far has {signed(disc.senate_json_y_two_party)}. Both are preliminary.
      {/if}
    </p>
    {#if tip}
      <Tip x={tip.px} y={tip.py} width={w} height={h} title={stateName(tip.st)} lines={tipLines(tip.st, tip.g)} pinned={!!pinned} onclose={() => (pinned = null)} />
    {/if}
  {/snippet}

  {#snippet table()}
    <table>
      <caption>Shift vs. 2024 by group, points (positive = toward Democrats)</caption>
      <thead>
        <tr><th>Group</th>{#each states as st (st)}<th class="n">{st}</th>{/each}<th class="n">US</th></tr>
      </thead>
      <tbody>
        {#each [...new Set(tidy.map((r) => r.group))] as g (g)}
          <tr><td>{g}</td>{#each states as st (st)}<td class="n">{signed(val[st + '|' + g], 0)}</td>{/each}<td class="n">{natl[g] != null ? signed(natl[g], 0) : ''}</td></tr>
        {/each}
        <tr><th>Overall</th>{#each states as st (st)}<th class="n">{signed(tbl[st]?.overall_shift)}</th>{/each}<th></th></tr>
        <tr><td>Democratic nominee</td>{#each states as st (st)}<td>{tbl[st]?.dem_nominee ?? ''}</td>{/each}<td></td></tr>
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
  .pbg {
    fill: var(--surface);
    stroke: var(--ring);
  }
  .pbg.focus {
    stroke: var(--ink);
    stroke-width: 1.5;
  }
  .st {
    font-size: 13px;
    font-weight: 700;
    fill: var(--ink);
  }
  .ov {
    font-size: 11px;
    fill: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }
  .who {
    font-size: 10.5px;
    color: var(--ink-2);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
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
    font-size: 10px;
    fill: var(--muted);
  }
  .gl-lbl {
    font-size: 11px;
    fill: var(--ink-2);
  }
  .gl-lbl.em {
    fill: var(--ink);
    font-weight: 700;
  }
  .stem {
    stroke: var(--axis);
    stroke-width: 1;
  }
  .dot {
    fill: var(--ink-2);
    stroke: var(--surface);
    stroke-width: 1;
  }
  .dot.focus {
    fill: var(--ink);
  }
  .dot.other {
    fill: var(--muted);
    opacity: 0.7;
    stroke: var(--bg);
  }
  .nat {
    stroke: var(--muted);
    stroke-width: 2;
  }
  .flab {
    font-size: 10px;
    font-weight: 700;
    fill: var(--ink);
  }
  .hitg {
    cursor: pointer;
    outline: none;
  }
  .hit {
    fill: transparent;
  }
  .hitg:hover .hit,
  .hitg.active .hit,
  .hitg:focus-visible .hit {
    fill: var(--surface-2);
  }
  .hitg:focus-visible .hit {
    stroke: var(--dem);
    stroke-width: 2;
  }
  .cap {
    margin: 8px 0 0;
    font-size: 12px;
    line-height: 1.4;
    color: var(--ink-2);
  }
</style>
