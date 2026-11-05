<script>
  // "What you'd have to believe" (METHODOLOGY §1.1 B_a, §6.5 believeHeatmap, claims C8).
  // Grid: style effect δ (x, points of margin, as measured in 2026 House races) × transfer
  // factor π (y, how much of it carries to a presidential race). Each cell is the Democrats'
  // P(win) at the reader's environment for a national style shift π·δ, read off the engine's
  // believeHeatmap row at E = ctx.reader.env. The dots are the model's own (δ, π) draws.
  import { untrack } from 'svelte';
  import { scaleLinear } from 'd3-scale';
  import { ARCHETYPES, ARCHETYPE_BY_ID } from '../../lib/archetypes.js';
  import SimFrame from './SimFrame.svelte';
  import Slider from './Slider.svelte';
  import ArchPicker from './ArchPicker.svelte';
  import {
    fmtE, pct, signed, params, piSlider, priorOnly, latest, clamp, probFill10, defaultEnvCenter, envHistoryLabel,
  } from './shared.js';

  let { ctx, nodes, archetype = null } = $props();
  const ctx0 = untrack(() => ctx); // stage components are keyed per step: setup reads ctx once
  const init = untrack(() => ({ archetype }));

  const P = params(ctx0);
  const ps = piSlider(ctx0);
  const prior = priorOnly(ctx0);
  if (ctx0.reader && ctx0.reader.env == null) ctx0.reader.env = defaultEnvCenter(ctx0);

  // archetypes with a style effect relative to the reference (mainstream liberal is the yardstick)
  const choices = ARCHETYPES.filter((a) => a.id !== 'mainstream_liberal');
  let arch = $state(init.archetype ?? (ctx0.reader?.guess && ctx0.reader.guess !== 'mainstream_liberal' ? ctx0.reader.guess : 'progressive'));

  // axis domains from the draws (stable across archetype switches)
  const deltas = P.style?.presets?.agnostic?.delta ?? {};
  const qAll = (q) => {
    let out = q < 0.5 ? Infinity : -Infinity;
    for (const a of Object.keys(deltas)) {
      const s = [...deltas[a]].sort((x, y) => x - y);
      const v = s[Math.floor(q * (s.length - 1))];
      out = q < 0.5 ? Math.min(out, v) : Math.max(out, v);
    }
    return out;
  };
  const dLo = Math.floor(Math.min(-4, qAll(0.01) - 0.5));
  const dHi = Math.ceil(Math.max(2, qAll(0.99) + 0.5));
  const DSTEP = 0.25;
  const PSTEP = 0.05;
  const dGrid = Array.from({ length: Math.round((dHi - dLo) / DSTEP) }, (_, i) => dLo + (i + 0.5) * DSTEP);
  const pGrid = Array.from({ length: Math.round((ps.max - ps.min) / PSTEP) }, (_, i) => ps.min + (i + 0.5) * PSTEP);
  const XSTEP = 0.1;
  const xMin = Math.floor(Math.min(dLo * ps.max, dHi * ps.min, dLo * ps.min) - 1);
  const xMax = Math.ceil(Math.max(dHi * ps.max, dLo * ps.min) + 1);
  const styleGrid = Array.from({ length: Math.round((xMax - xMin) / XSTEP) + 1 }, (_, i) => +(xMin + i * XSTEP).toFixed(4));

  let row = $state(null); // Float32Array over styleGrid at E = reader.env
  let B = $state(null);
  let error = $state('');

  const go = latest(
    (o) => ctx.simReady.then(() => ctx.sim.believeHeatmap(o, {}, { channel: 'believe' })),
    (r) => {
      row = r.pWin;
      B = r.B;
    },
    (e) => (error = e.message),
  );
  $effect(() => {
    const o = {
      Egrid: [ctx.reader.env],
      styleGrid,
      archetype: arch,
      // The engine's π only feeds B.posteriorProb (the cells use the reader's π below). Claim C8
      // is computed with sampled π at the default environment, so the headline does the same.
      pi: { mode: 'sampled' },
    };
    untrack(() => go(o));
  });

  /** P(win) at national style shift x (linear interpolation on the engine row). */
  function pAt(x) {
    if (!row) return null;
    const f = (x - xMin) / XSTEP;
    const i = clamp(Math.floor(f), 0, row.length - 2);
    const t = clamp(f - i, 0, 1);
    return row[i] + t * (row[i + 1] - row[i]);
  }
  /** Smallest x at which P(win) reaches `target` (row is increasing in x). */
  function xFor(target) {
    if (!row) return null;
    for (let i = 1; i < row.length; i++) {
      if (row[i] >= target) {
        const a = row[i - 1], b = row[i];
        return styleGrid[i - 1] + (b === a ? 0 : (target - a) / (b - a)) * XSTEP;
      }
    }
    return null;
  }

  // draws for the overlay
  const piDraws = P.transfer_pi?.pi_draws ?? [];
  const draws = $derived.by(() => {
    const d = deltas[arch] ?? [];
    const fixed = ctx.reader.pi;
    return d.map((v, i) => [v, fixed == null ? piDraws[i % piDraws.length] : fixed]);
  });
  const medDelta = $derived.by(() => {
    const s = [...(deltas[arch] ?? [0])].sort((x, y) => x - y);
    return s[Math.floor(s.length / 2)];
  });
  const medPi = $derived(ctx.reader.pi ?? (() => {
    const s = [...piDraws].sort((x, y) => x - y);
    return s[Math.floor(s.length / 2)] ?? 1;
  })());

  // geometry
  let w = $state(0);
  let h = $state(0);
  const M = $derived(w < 520 ? { l: 40, r: 10, t: 22, b: 40 } : { l: 52, r: 18, t: 24, b: 44 });
  const H = $derived(Math.max(160, h));
  const x = $derived(scaleLinear().domain([dLo, dHi]).range([M.l, Math.max(M.l + 60, w - M.r)]));
  const y = $derived(scaleLinear().domain([ps.min, ps.max]).range([H - M.b, M.t]));
  const cw = $derived((x(dHi) - x(dLo)) / dGrid.length);
  const ch = $derived((y(ps.min) - y(ps.max)) / pGrid.length);

  // reference curves δ = x*/π
  const p0 = $derived(pAt(0));
  const x50 = $derived(xFor(0.5));
  const x10 = $derived(p0 == null ? null : xFor(p0 - 0.1));
  const curve = (xs) => {
    if (xs == null) return '';
    const pts = [];
    for (let k = 0; k <= 60; k++) {
      const pi = ps.min + (k / 60) * (ps.max - ps.min);
      const d = xs / pi;
      if (d >= dLo && d <= dHi) pts.push(`${x(d).toFixed(1)},${y(pi).toFixed(1)}`);
    }
    return pts.length > 1 ? `M${pts.join('L')}` : '';
  };
  const share = $derived.by(() => {
    if (x10 == null) return null;
    let c = 0;
    for (const [d, pi] of draws) if (d * pi <= x10) c++;
    return c / Math.max(1, draws.length);
  });

  // probe (hover / keyboard)
  let probe = $state(null); // { i, j }
  function fromPointer(e) {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left, py = e.clientY - r.top;
    if (px < x(dLo) || px > x(dHi) || py < y(ps.max) || py > y(ps.min)) return null;
    return { i: clamp(Math.floor((px - x(dLo)) / cw), 0, dGrid.length - 1), j: clamp(Math.floor((y(ps.min) - py) / ch), 0, pGrid.length - 1) };
  }
  function onkey(e) {
    const k = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[e.key];
    if (!k) return;
    e.preventDefault();
    const base = probe ?? { i: dGrid.findIndex((d) => d > medDelta), j: pGrid.findIndex((p) => p > medPi) };
    probe = { i: clamp(base.i + k[0], 0, dGrid.length - 1), j: clamp(base.j + k[1], 0, pGrid.length - 1) };
  }
  const probeInfo = $derived.by(() => {
    if (!probe || !row) return null;
    const d = dGrid[probe.i], pi = pGrid[probe.j];
    return { d, pi, xs: d * pi, p: pAt(d * pi) };
  });

  const label = (a) => ARCHETYPE_BY_ID[a]?.label ?? a;
  // Headline (claim C8): the pipeline's own numbers (validation.json headline_2028, computed in
  // 10_validate.py at the default environment distribution with sampled π on its float64
  // bank). The browser bank gives the same quantity to within ~0.1 pt / 2 percentage points,
  // so it is only the fallback.
  const published = ctx0.data?.validation?.headline_2028?.published ?? null;
  const headline = $derived.by(() => {
    const h = published?.[arch];
    if (h && h.B_threshold != null && h.P_pidelta_le_B != null) return { cost: Math.abs(h.B_threshold), prob: h.P_pidelta_le_B };
    if (B) return { cost: B.cost, prob: B.posteriorProb };
    return null;
  });
  const envDefaultLabel = envHistoryLabel(ctx0);
  const disagree = $derived(P.copy_flags?.models_disagree?.[arch] ? P.reveal?.adjusted?.[arch]?.delta_range_models : null);
  const xTicks = $derived(x.ticks(w < 520 ? 5 : 8).filter(Number.isInteger));
  const yTicks = $derived(y.ticks(w < 520 ? 4 : 6));
  const piText = $derived(ctx.reader.pi == null ? 'sampled' : `${(+ctx.reader.pi).toFixed(2)}×`);
  let piVal = $state(ctx0.reader?.pi ?? 1);
</script>

<SimFrame
  {ctx}
  title="What you'd have to believe"
  dek="Each cell: the Democrats' chance at your environment if a style effect of a given size (across) carries over to a presidential race at a given rate (up)."
  banner={P.banners?.uninformative ? bannerSnip : null}
>
  <div class="bar">
    <ArchPicker bind:value={arch} ids={choices.map((a) => a.id)} compact={w > 0 && w < 560} />
  </div>
  <div class="chart" bind:clientWidth={w} bind:clientHeight={h}>
    {#if w > 0}
      <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
      <svg
        width={w}
        height={H}
        role="img"
        tabindex="0"
        aria-label={`Win probability by style effect and transfer factor for a ${label(arch).toLowerCase()} Democrat at ${fmtE(ctx.reader.env, 1)}. Use arrow keys to read cells.`}
        onpointermove={(e) => (probe = fromPointer(e))}
        onpointerdown={(e) => (probe = fromPointer(e))}
        onpointerleave={(e) => e.pointerType === 'mouse' && (probe = null)}
        onkeydown={onkey}
        onblur={() => (probe = null)}
      >
        {#if row}
          <g shape-rendering="crispEdges">
            {#each pGrid as pi, j (j)}
              {#each dGrid as d, i (i)}
                <rect x={x(dLo) + i * cw} y={y(ps.min) - (j + 1) * ch} width={cw + 0.5} height={ch + 0.5} style:fill={probFill10(pAt(d * pi))} />
              {/each}
            {/each}
          </g>
        {/if}
        <!-- axes -->
        {#each xTicks as v (v)}
          <line class="tickmark" x1={x(v)} x2={x(v)} y1={H - M.b} y2={H - M.b + 4} />
          <text class="tick" x={x(v)} y={H - M.b + 16} text-anchor="middle">{signed(v, 0)}</text>
        {/each}
        {#each yTicks as v (v)}
          <text class="tick" x={M.l - 6} y={y(v) + 4} text-anchor="end">{+v.toFixed(2)}×</text>
        {/each}
        <text class="axis-title" x={(M.l + w - M.r) / 2} y={H - 6} text-anchor="middle">{w < 560 ? '← costs · Style effect, points · gains →' : '← costs votes · Style effect in 2026 House races, points · gains votes →'}</text>
        <line class="zero" x1={x(0)} x2={x(0)} y1={M.t} y2={H - M.b} />
        <!-- reference curves -->
        <path d={curve(x50)} class="c50" />
        <path d={curve(x10)} class="c10" />
        {#if x50 != null}
          {@const pl = [0.12, 0.25, 0.4, 0.55].map((f) => ps.min + f * (ps.max - ps.min)).find((pi) => x50 / pi >= dLo + 1 && x50 / pi <= dHi)}
          {#if pl != null}<text class="lbl halo" x={x(x50 / pl) - 6} y={y(pl) + 4} text-anchor="end">Coin flip</text>{/if}
        {/if}
        {#if x10 != null && x10 / ps.max >= dLo && x10 / ps.max <= dHi}
          <text class="lbl halo" x={x(x10 / ps.max) - 4} y={M.t + 12} text-anchor="end">−10 pts</text>
        {/if}
        <!-- draws -->
        <g class="draws">
          {#each draws as [d, pi], k (k)}
            {#if d >= dLo && d <= dHi}<circle cx={x(d)} cy={y(clamp(pi, ps.min, ps.max))} r="1.4" />{/if}
          {/each}
        </g>
        <!-- reader point: median δ at the current π -->
        <g transform="translate({x(clamp(medDelta, dLo, dHi))},{y(clamp(medPi, ps.min, ps.max))})">
          <circle r="7" class="me-ring" />
          <circle r="3" class="me" />
        </g>
        <text class="lbl halo" x={x(clamp(medDelta, dLo, dHi)) + 11} y={y(clamp(medPi, ps.min, ps.max)) - 9} font-weight="600">2026 estimate</text>
        {#if probeInfo}
          <rect class="probe" x={x(dLo) + probe.i * cw} y={y(ps.min) - (probe.j + 1) * ch} width={cw} height={ch} />
        {/if}
      </svg>
      {#if probeInfo}
        <div class="tip" style:left="{clamp(x(probeInfo.d) + 12, 4, w - 210)}px" style:top="{clamp(y(probeInfo.pi) - 70, 0, H - 80)}px">
          Style effect <b>{signed(probeInfo.d, 1)}</b> × transfer <b>{probeInfo.pi.toFixed(2)}</b><br />
          = national shift {signed(probeInfo.xs, 1)} pts<br />
          Democrats' chance at {fmtE(ctx.reader.env, 1)}: <b>{pct(probeInfo.p)}</b>
        </div>
      {/if}
    {/if}
  </div>
  <div class="legend" aria-hidden="true">
    <span>Democrats' chance</span>
    <span class="end">0%</span>
    {#each [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95] as v (v)}<i style:background={probFill10(v)}></i>{/each}
    <span class="end r">100%</span>
    <span class="k"><svg width="14" height="10"><circle cx="7" cy="5" r="1.8" class="dotkey" /></svg>model draws</span>
    <span class="k"><svg width="18" height="10"><line x1="0" x2="18" y1="5" y2="5" class="c10" /></svg>10-pt drop</span>
  </div>
  <div class="controls">
    <Slider
      label="Transfer to a presidential race (π)"
      bind:value={piVal}
      min={ps.min}
      max={ps.max}
      step={ps.step}
      format={(v) => (ctx.reader.pi == null ? (w < 560 ? 'sampled' : `sampled (median ${medPi.toFixed(2)}×)`) : `${(+v).toFixed(2)}×`)}
      oninput={(v) => (ctx.reader.pi = v)}
      ends={['half as big', 'twice as big']}
    />
    {#if ctx.reader.pi != null}
      <button class="btn ghost" onclick={() => { ctx.reader.pi = null; piVal = 1; }}>Use sampled π</button>
    {/if}
  </div>
  {#if headline}
    <p class="big" role="status">
      In the model's default environment ({envDefaultLabel}), for a {label(arch).toLowerCase()} Democrat to be a clear liability
      (−10 points of win probability), you'd have to believe the style costs at least
      <b>{headline.cost == null ? '–' : headline.cost.toFixed(1)}</b> points nationally;
      {prior ? 'with 2026 set aside, the prior' : '2026'} puts the chance of a cost that large at <b>{pct(headline.prob)}</b>.
    </p>
    {#if share != null}
      <p class="note">The cells and the 10-point line use your environment instead: at {fmtE(ctx.reader.env, 1)} with π {piText}, {pct(share)} of the model's draws fall left of that line.</p>
    {/if}
  {/if}
  {#if disagree}
    <p class="note">Two models disagree on this estimate: {signed(disagree[0], 1)} vs {signed(disagree[1], 1)} points.</p>
  {/if}
  {#if error}<p class="error">Simulation error: {error}</p>{/if}

  {#snippet table()}
    <table class="data">
      <caption>Democrats' chance at {fmtE(ctx.reader.env, 1)}, {label(arch).toLowerCase()}, by style effect and transfer</caption>
      <thead>
        <tr><th scope="col">Transfer π</th>{#each [-4, -3, -2, -1, 0, 1, 2] as d (d)}<th scope="col">{signed(d, 0)} pts</th>{/each}</tr>
      </thead>
      <tbody>
        {#each [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2].filter((v) => v >= ps.min && v <= ps.max) as pi (pi)}
          <tr>
            <th scope="row">{pi.toFixed(2)}×</th>
            {#each [-4, -3, -2, -1, 0, 1, 2] as d (d)}<td>{pct(pAt(d * pi))}</td>{/each}
          </tr>
        {/each}
      </tbody>
    </table>
    <p class="note">2026 estimate for this type: style effect {signed(medDelta, 1)} points (median of the model's draws).</p>
  {/snippet}

  {#snippet notes()}
    <p>Style effect relative to a party-default nominee, as measured in 2026 House races. A transfer of 1× means the same size in 2028.</p>
  {/snippet}
</SimFrame>

{#snippet bannerSnip()}
  <p class="warn">{P.banners.uninformative}</p>
{/snippet}

<style>
  .bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .chart {
    position: relative;
    flex: 1 1 auto;
    min-height: 220px;
  }
  .chart svg {
    position: absolute;
    inset: 0;
    display: block;
    overflow: visible;
    touch-action: pan-y;
  }
  .chart svg:focus-visible {
    outline-offset: -2px;
  }
  .tickmark {
    stroke: var(--axis);
  }
  .zero {
    stroke: var(--ink);
    stroke-opacity: 0.35;
    stroke-width: 1;
  }
  .c50 {
    fill: none;
    stroke: var(--ink);
    stroke-width: 1.5;
    stroke-dasharray: 5 4;
  }
  .c10 {
    fill: none;
    stroke: var(--ink);
    stroke-width: 2;
  }
  .draws circle,
  .dotkey {
    fill: var(--ink);
    fill-opacity: 0.4;
  }
  .me-ring {
    fill: none;
    stroke: var(--ink);
    stroke-width: 2;
  }
  .me {
    fill: var(--ink);
  }
  .probe {
    fill: none;
    stroke: var(--ink);
    stroke-width: 1.5;
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 2px;
    font-size: 11px;
    color: var(--ink-2);
  }
  .legend > span:first-child {
    margin-right: 6px;
  }
  .legend i {
    width: 14px;
    height: 10px;
  }
  .end {
    margin: 0 3px;
    font-variant-numeric: tabular-nums;
  }
  .end.r {
    margin-right: 14px;
  }
  .k {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-right: 10px;
  }
  @media (max-width: 760px) {
    .chart {
      min-height: 200px;
    }
  }
</style>
