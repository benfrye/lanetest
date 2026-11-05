<script>
  // "What if this lane really does cost votes?" (claims C8, the plain-language version of the
  // old what-you'd-have-to-believe grid). One line: Democrats' chance of winning in 2028 as the
  // nominee's lane costs or gains votes nationwide, averaged over the default range for the
  // national mood and over carry-over from midterm to presidential race (sampled π), exactly
  // as the 10-point threshold B is computed. A band marks what 2026 suggests (80% of π·δ draws).
  import { untrack } from 'svelte';
  import { scaleLinear } from 'd3-scale';
  import { ARCHETYPES, ARCHETYPE_BY_ID } from '../../lib/archetypes.js';
  import SimFrame from './SimFrame.svelte';
  import Slider from './Slider.svelte';
  import ArchWheel from './ArchWheel.svelte';
  import { pct, params, priorOnly, latest, clamp, envHistoryLabel, thinNote, lanes2028, usesHistory } from './shared.js';

  let { ctx, nodes, archetype = null } = $props();
  const ctx0 = untrack(() => ctx); // stage components are keyed per step: setup reads ctx once
  const init = untrack(() => ({ archetype }));

  const P = params(ctx0);
  const prior = priorOnly(ctx0);
  const choices = lanes2028(ctx0, ARCHETYPES).filter((a) => a.id !== 'mainstream_liberal');
  let arch = $state(init.archetype ?? (ctx0.reader?.guess && ctx0.reader.guess !== 'mainstream_liberal' ? ctx0.reader.guess : 'progressive'));

  // x: national points the lane costs (−) or gains (+)
  const X0 = -4;
  const X1 = 3;
  const XSTEP = 0.05;
  const styleGrid = Array.from({ length: Math.round((X1 - X0) / XSTEP) + 1 }, (_, i) => +(X0 + i * XSTEP).toFixed(4));

  let V = $state(null); // Float32Array over styleGrid
  let Q = $state(null); // { q10, q50, q90 } of the lane's national effect
  let B = $state(null);
  let error = $state('');
  let effect = $state(null); // slider value: national points, negative = costs votes (same direction as the chart)
  const cost = $derived(effect == null ? null : -effect);

  const go = latest(
    (o) => ctx.simReady.then(() => ctx.sim.believeHeatmap(o, {}, { channel: 'lanecost' })),
    (r) => {
      V = r.curve.V;
      Q = r.curve.quantiles;
      B = r.B;
      // Start the slider at the lane's 2026 estimate.
      effect = clamp(Math.round(Q.q50 * 10) / 10, X0, X1);
    },
    (e) => (error = e.message),
  );
  $effect(() => {
    const o = { Egrid: [0], styleGrid, archetype: arch, pi: { mode: 'sampled' }, curve: true };
    untrack(() => go(o));
  });

  function vAt(x) {
    if (!V) return null;
    const f = (x - X0) / XSTEP;
    const i = clamp(Math.floor(f), 0, V.length - 2);
    const t = clamp(f - i, 0, 1);
    return V[i] + t * (V[i + 1] - V[i]);
  }

  const label = (a) => ARCHETYPE_BY_ID[a]?.label ?? a;
  const lower = (a) => label(a).toLowerCase();
  const article = (a) => (/^[aeiou]/i.test(label(a)) ? 'an' : 'a');
  // Headline numbers: the pipeline's published C8 values (validation.json headline_2028),
  // with the browser engine as the fallback; they agree to within ~0.1 pt / 2 points.
  const published = ctx0.data?.validation?.headline_2028?.published ?? null;
  const headline = $derived.by(() => {
    const h = published?.[arch];
    if (h && h.B_threshold != null && h.P_pidelta_le_B != null) return { cost: Math.abs(h.B_threshold), prob: h.P_pidelta_le_B };
    if (B?.cost != null) return { cost: B.cost, prob: B.posteriorProb };
    return null;
  });
  const odds = (p) => {
    if (p == null) return '–';
    if (p < 0.01) return 'less than 1 in 100';
    if (p >= 0.5) return `more likely than not (${pct(p)})`;
    return `about 1 in ${Math.round(1 / p)} (${pct(p)})`;
  };
  const pts = (v) => {
    const a = Math.abs(v);
    return `${a < 0.05 ? '0' : a.toFixed(1)} ${a >= 0.95 && a < 1.05 ? 'point' : 'points'}`;
  };
  const envLabel = envHistoryLabel(ctx0);
  // Where the lane estimates come from: past elections (O-8 history preset) or 2026 alone.
  const fromHistory = usesHistory(ctx0);
  const evidence = fromHistory ? '2026 and past elections' : '2026';

  const v0 = $derived(vAt(0));
  const vNow = $derived(cost == null ? null : vAt(-cost));
  // From the rounded percentages shown, so the tiles and the difference always agree.
  const change = $derived(v0 == null || vNow == null ? null : Math.round(vNow * 100) - Math.round(v0 * 100));

  // geometry
  let w = $state(0);
  let h = $state(0);
  const narrow = $derived(w < 520);
  const M = $derived(narrow ? { l: 36, r: 12, t: 16, b: 40 } : { l: 44, r: 20, t: 18, b: 44 });
  const H = $derived(Math.max(180, h));
  const x = $derived(scaleLinear().domain([X0, X1]).range([M.l, Math.max(M.l + 60, w - M.r)]));
  const y = $derived(scaleLinear().domain([0, 1]).range([H - M.b, M.t]));
  const path = $derived.by(() => {
    if (!V) return '';
    const pts = [];
    for (let i = 0; i < styleGrid.length; i += 2) pts.push(`${x(styleGrid[i]).toFixed(1)},${y(V[i]).toFixed(1)}`);
    return `M${pts.join('L')}`;
  });
  const xTicks = $derived(x.ticks(narrow ? 5 : 8).filter(Number.isInteger));
  const tickLabel = (v) => (v === 0 ? '0' : v < 0 ? `costs ${-v}` : `gains ${v}`);
</script>

<SimFrame
  {ctx}
  title={`What if ${article(arch)} ${lower(arch)} really does cost votes?`}
  dek="Democrats’ chance of winning the White House in 2028, depending on how many points the nominee’s lane costs or gains them nationwide."
  banner={P.banners?.uninformative ? bannerSnip : null}
  table={tableSnip}
>
  <div class="bar">
    <ArchWheel bind:value={arch} ids={choices.map((a) => a.id)} />
  </div>

  <div class="chart" bind:clientWidth={w} bind:clientHeight={h}>
    {#if w > 0}
      <svg width={w} height={H} role="img" aria-label={headline ? `Democrats' chance of winning falls as a ${lower(arch)} nominee's cost grows; a cost of ${headline.cost.toFixed(1)} points takes about 10 points off their chances.` : 'Chance of winning by lane cost'}>
        <!-- gridlines -->
        {#each [0, 0.25, 0.5, 0.75, 1] as v (v)}
          <line class="grid" x1={M.l} x2={w - M.r} y1={y(v)} y2={y(v)} />
          <text class="tick" x={M.l - 6} y={y(v) + 4} text-anchor="end">{Math.round(v * 100)}%</text>
        {/each}
        {#each xTicks as v (v)}
          <text class="tick" x={x(v)} y={H - M.b + 16} text-anchor="middle">{narrow ? (v > 0 ? `+${v}` : v === 0 ? '0' : `−${-v}`) : tickLabel(v)}</text>
        {/each}
        <text class="axis-title" x={(M.l + w - M.r) / 2} y={H - 6} text-anchor="middle">← costs Democrats votes · points nationwide · gains votes →</text>

        {#if Q}
          <!-- what the evidence suggests -->
          {@const b0 = x(clamp(Q.q10, X0, X1))}
          {@const b1 = x(clamp(Q.q90, X0, X1))}
          <rect class="band" x={b0} y={M.t} width={Math.max(2, b1 - b0)} height={H - M.b - M.t} />
          <text class="band-label" x={(b0 + b1) / 2} y={M.t + 14} text-anchor="middle">What {fromHistory ? '2026 and past elections suggest' : '2026 suggests'}</text>
        {/if}

        {#if v0 != null}
          <!-- the yardstick: a mainstream liberal, no cost -->
          <line class="ref" x1={M.l} x2={w - M.r} y1={y(v0)} y2={y(v0)} />
          <line class="zero" x1={x(0)} x2={x(0)} y1={M.t} y2={H - M.b} />
          {#if B?.threshold != null && B.threshold >= X0}
            <line class="drop" x1={x(B.threshold)} x2={x(B.threshold)} y1={y(v0 - 0.1)} y2={H - M.b} />
            <circle class="drop-dot" cx={x(B.threshold)} cy={y(v0 - 0.1)} r="3.5" />
            <text class="lbl halo" x={x(B.threshold) - 6} y={H - M.b - 8} text-anchor="end">10 points lower</text>
          {/if}
        {/if}

        <path class="curve" d={path} />

        {#if vNow != null}
          <circle class="me" cx={x(-cost)} cy={y(vNow)} r="6" style:fill={`var(${ARCHETYPE_BY_ID[arch]?.token})`} />
        {/if}
      </svg>
    {/if}
  </div>

  {#if effect != null}
    <div class="control">
      <Slider
        label={`What if ${article(arch)} ${lower(arch)} nominee…`}
        bind:value={effect}
        min={X0}
        max={X1}
        step={0.1}
        format={(v) => (Math.abs(v) < 0.05 ? 'costs nothing' : v < 0 ? `costs ${pts(v)}` : `gains ${pts(v)}`)}
        ends={['costs votes', 'gains votes']}
      />
    </div>
  {/if}

  <div class="stats" role="status">
    <div class="stat">
      <span class="sl"><span class="sw ref-sw"></span>Mainstream liberal, no cost</span>
      <span class="sv">{pct(v0)}</span>
    </div>
    <div class="stat">
      <span class="sl"><span class="sw me-sw" style:background={`var(${ARCHETYPE_BY_ID[arch]?.token})`}></span>{label(arch)}, at the slider’s cost</span>
      <span class="sv">{pct(vNow)}{#if change != null && change !== 0}<span class="delta">{change > 0 ? '+' : '−'}{Math.abs(change)}</span>{/if}</span>
    </div>
  </div>


  {#if headline}
    <p class="big">
      To knock 10 points off Democrats’ chances, {article(arch)} {lower(arch)} nominee would have to cost about
      <b>{headline.cost.toFixed(1)} points</b> nationwide. {prior ? 'Setting the data aside, our starting assumption' : evidence} {evidence === '2026' && !prior ? 'says' : 'say'} a cost that big is <b>{headline.prob >= 0.5 ? `more likely than not (${pct(headline.prob)})` : headline.prob < 0.01 ? 'very unlikely (under 1 in 100)' : `unlikely: about 1 in ${Math.round(1 / headline.prob)} (${pct(headline.prob)})`}</b>.
    </p>
  {/if}
  {#if thinNote(ctx0, arch)}<p class="note">{thinNote(ctx0, arch)}</p>{/if}
  <p class="note">
    Both lines average over our range for 2028’s national mood ({envLabel}) and over whether a midterm effect grows or shrinks in a presidential race.
  </p>
  {#if error}<p class="error">Simulation error: {error}</p>{/if}
</SimFrame>

{#snippet bannerSnip()}
  <p class="warn">{P.banners.uninformative}</p>
{/snippet}

{#snippet tableSnip()}
  <table class="data">
    <caption>Democrats’ chance of winning in 2028 by how many points a {lower(arch)} nominee costs nationwide</caption>
    <thead><tr><th>Cost</th><th class="n">Chance of winning</th></tr></thead>
    <tbody>
      {#each [-2, -1, 0, 0.5, 1, 1.5, 2, 3, 4] as c (c)}
        <tr><td>{c === 0 ? 'None' : c > 0 ? `Costs ${pts(c)}` : `Gains ${pts(c)}`}</td><td class="n">{pct(vAt(-c))}</td></tr>
      {/each}
    </tbody>
  </table>
  {#if Q}<p class="note">What {fromHistory ? '2026 and past elections suggest' : '2026 suggests'} for a {lower(arch)} nominee: between {Q.q10 < 0 ? `costing ${pts(Q.q10)}` : `gaining ${pts(Q.q10)}`} and {Q.q90 < 0 ? `costing ${pts(Q.q90)}` : `gaining ${pts(Q.q90)}`} (80% range).</p>{/if}
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
    min-height: 200px;
  }
  .chart svg {
    position: absolute;
    inset: 0;
    display: block;
    overflow: visible;
  }
  .grid {
    stroke: var(--grid);
  }
  .band {
    fill: var(--ink);
    fill-opacity: 0.08;
  }
  .band-label {
    font-size: 11px;
    font-weight: 600;
    fill: var(--ink-2);
  }
  .ref {
    stroke: var(--muted);
    stroke-width: 1.5;
    stroke-dasharray: 5 4;
  }
  .zero {
    stroke: var(--ink);
    stroke-opacity: 0.25;
  }
  .drop {
    stroke: var(--ink-2);
    stroke-dasharray: 2 3;
  }
  .drop-dot {
    fill: var(--ink-2);
  }
  .curve {
    fill: none;
    stroke: var(--ink);
    stroke-width: 2.5;
  }
  .me {
    stroke: var(--bg);
    stroke-width: 2;
  }
  .control {
    flex: none;
  }
  .stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 10px;
    border: 1px solid var(--ring);
    border-radius: 8px;
    background: var(--surface);
  }
  .sl {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--ink-2);
  }
  .sw {
    flex: none;
    width: 14px;
    height: 0;
  }
  .ref-sw {
    border-top: 2px dashed var(--muted);
  }
  .me-sw {
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }
  .sv {
    font-size: 24px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--ink);
  }
  .delta {
    margin-left: 8px;
    font-size: 14px;
    font-weight: 600;
    color: var(--ink-2);
  }
  @media (max-width: 520px) {
    .sv {
      font-size: 20px;
    }
  }
</style>
