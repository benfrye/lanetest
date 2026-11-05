<script>
  // Stage: lane gaps vs mainstream liberals in competitive House seats (|pres| <= 20), one row per
  // election year, grouped by lane (analysis/history, exported as style.history_summary.competitive_cycles).
  // Midterms filled, presidential years hollow; bars are 80% ranges. Same 50×Δlogit scale as the 2026 fit.
  import StageFrame from './StageFrame.svelte';
  import { scaleLinear } from 'd3-scale';
  import { ARCHETYPE_BY_ID, shapePath } from '../../lib/archetypes.js';
  import { signed, asOfLabel } from './util.js';

  let { ctx, nodes = [] } = $props();
  const cc = $derived(ctx?.data?.params?.style?.history_summary?.competitive_cycles ?? {});
  const LANES = ['progressive', 'left_populist', 'moderate'];
  const years = $derived(Object.keys(cc).sort());
  const envLabel = (e) => (Math.abs(e) < 0.5 ? 'even' : e > 0 ? `D+${Math.round(e)}` : `R+${Math.round(-e)}`);
  const groups = $derived(
    LANES.map((a) => ({
      a,
      rows: years.filter((y) => cc[y].gaps[a]).map((y) => ({ y, env: cc[y].env, pres: cc[y].presidential, ...cc[y].gaps[a] })),
    })),
  );
  const domain = [-10, 8];
  let showTable = $state(false);
</script>

<StageFrame
  title="Lane gaps in close House races, 2018–2026"
  dek="Each lane's margin compared with mainstream liberals in competitive seats, by election. Filled: midterms; hollow: presidential years. Bars show the likely range; n = races, where few."
  note={`Competitive seats only (presidential margin within 20 points). 2026 preliminary, as of ${asOfLabel(ctx)}.`}
  source="Source: House results from Wikipedia and state offices; district presidential results from The Downballot; lanes are our classification. Our analysis."
  bind:showTable
>
  {#snippet chart(w, h)}
    {@const labW = w < 520 ? 92 : 150}
    {@const rowH = Math.max(20, Math.min(30, (h - 60) / (groups.reduce((s, g) => s + g.rows.length, 0) + groups.length * 1.4)))}
    {@const x = scaleLinear().domain(domain).range([labW + 8, w - 50]).clamp(true)}
    {@const H = 30 + groups.reduce((s, g) => s + (g.rows.length + 1.4) * rowH, 0)}
    <svg width={w} height={H} role="img" aria-label="Lane gaps by election year; see the table for the numbers.">
      {#each [-8, -4, 0, 4, 8] as t (t)}
        <line class={t === 0 ? 'zero' : 'grid'} x1={x(t)} x2={x(t)} y1="18" y2={H} />
        <text class="tick" x={x(t)} y="12" text-anchor="middle">{t === 0 ? 'same' : signed(t, 0)}</text>
      {/each}
      {#each groups as g, gi (g.a)}
        {@const y0 = 24 + groups.slice(0, gi).reduce((s, q) => s + (q.rows.length + 1.4) * rowH, 0)}
        {@const arch = ARCHETYPE_BY_ID[g.a]}
        <g transform="translate(0,{y0})">
          <path transform="translate(8,{rowH * 0.5})" d={shapePath(arch.shape, 5)} style:fill="var({arch.token})" />
          <text class="lane" x="18" y={rowH * 0.5 + 4}>{arch.label}</text>
          {#each g.rows as r, i (r.y)}
            {@const cy = rowH * (i + 1.4)}
            <text class="yr" x={labW} y={cy + 4} text-anchor="end">{r.y} ({envLabel(r.env)})</text>
            <line class="rng" x1={x(r.lo80)} x2={x(r.hi80)} y1={cy} y2={cy} style:stroke="var({arch.token})" />
            <circle cx={x(r.est)} cy={cy} r="5" class:hollow={r.pres} style:stroke="var({arch.token})" style:fill={r.pres ? 'var(--bg)' : `var(${arch.token})`} />
            {#if r.n < 8}<text class="n" x={w} y={cy + 4} text-anchor="end">n={r.n}</text>{/if}
          {/each}
        </g>
      {/each}
    </svg>
    <p class="axis">← behind mainstream liberals · points of margin · ahead →</p>
  {/snippet}

  {#snippet table()}
    <table>
      <caption>Lane gap vs mainstream liberals, competitive House seats (points; 80% range)</caption>
      <thead><tr><th>Lane</th><th>Year</th><th>National vote</th><th class="n">Gap</th><th class="n">Range</th><th class="n">Races</th></tr></thead>
      <tbody>
        {#each groups as g (g.a)}
          {#each g.rows as r (r.y)}
            <tr><td>{ARCHETYPE_BY_ID[g.a].label}</td><td>{r.y}{r.pres ? ' (pres.)' : ''}</td><td>{envLabel(r.env)}</td><td class="n">{signed(r.est)}</td><td class="n">{signed(r.lo80)} to {signed(r.hi80)}</td><td class="n">{r.n}</td></tr>
          {/each}
        {/each}
      </tbody>
    </table>
  {/snippet}
</StageFrame>

<style>
  svg {
    display: block;
    overflow: visible;
    font-family: var(--font-ui);
  }
  .grid {
    stroke: var(--grid);
  }
  .zero {
    stroke: var(--ink-2);
    stroke-dasharray: 3 3;
  }
  .tick,
  .yr,
  .n {
    font-size: 11px;
    fill: var(--muted);
  }
  .yr {
    fill: var(--ink-2);
  }
  .lane {
    font-size: 13px;
    font-weight: 600;
    fill: var(--ink);
  }
  .rng {
    stroke-width: 2;
    opacity: 0.6;
  }
  circle {
    stroke-width: 2;
  }
  .axis {
    margin: 4px 0 0;
    text-align: center;
    font-size: 11.5px;
    color: var(--ink-2);
  }
  .n {
    font-size: 10.5px;
  }
</style>
