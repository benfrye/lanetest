<script>
  // Stage: per archetype, the raw gap to mainstream liberals shrinking to the adjusted
  // (like-with-like) δ with its 80% interval. Tap a row for the Oaxaca breakdown.
  // Copy follows the claims ledger (findings.md §8): C3 leads, C2 + placebo caveats
  // wherever a licensed archetype's adjusted number is shown.
  import { onMount, tick } from 'svelte';
  import { Tween } from 'svelte/motion';
  import { cubicInOut } from 'svelte/easing';
  import { scaleLinear } from 'd3-scale';
  import StageFrame from './StageFrame.svelte';
  import { resultsSource, resultsShort } from './sources.js';
  import ArchChip from './ArchChip.svelte';
  import {
    ARCHETYPES,
    signed,
    signedInt,
    asOfLabel,
    modelStatus,
    prefersReducedMotion,
    c2Sentence,
    C2_CAVEAT,
    placeboCaveat,
  } from './util.js';
  import { shapePath } from '../../lib/archetypes.js';

  let { ctx, nodes = [], phase = 'animate', selected = null, title = 'Raw averages vs. like with like', ...rest } = $props();

  const REF = 'mainstream_liberal';
  const d = $derived(ctx?.data ?? {});
  const status = $derived(modelStatus(ctx));
  const flags = $derived(d.params?.copy_flags ?? {});
  const oax = $derived(d.story?.oaxaca ?? {});
  const placebo = $derived(d.validation?.items?.V11?.numbers ?? {});

  const rows = $derived.by(() => {
    const raw = d.story?.raw?.main_sample ?? {};
    const adjAll = d.params?.reveal?.adjusted ?? {};
    const rawRef = raw[REF]?.all?.mean ?? 0;
    // The claims ledger (findings.md table, C2) quotes δ summarised over the full Gibbs chains;
    // reveal.adjusted summarises the 1,000 thinned export draws, which moves the 80% ends by
    // ~0.1. The pipeline ships the full-chain summary as the "R5: preset agnostic" robustness
    // row, so prefer it and fall back to the export draws.
    const full = Object.fromEntries(
      (d.params?.reveal?.fragility ?? []).filter((f) => /preset agnostic/i.test(f.label ?? '')).map((f) => [f.archetype, f]),
    );
    return ARCHETYPES.map((a) => {
      const isRef = a.id === REF;
      const r = raw[a.id]?.all ?? {};
      const ox = oax.by_archetype?.[a.id];
      const base = adjAll[a.id] ?? (ox?.delta_hat != null ? { med: ox.delta_hat, lo: null, hi: null } : null);
      const fc = full[a.id];
      const adj = base && fc ? { ...base, med: fc.med, lo: fc.lo, hi: fc.hi } : base;
      // Bracketed range, if a re-fit flags that models disagree for this archetype.
      const disagree = flags.models_disagree?.[a.id] === true;
      const range = adj?.delta_range_models ?? adj?.delta_range ?? adj?.range ?? flags.delta_range?.[a.id] ?? null;
      return {
        ...a,
        isRef,
        n: r.n ?? ox?.n ?? null,
        rawMean: r.mean ?? null,
        rawGap: isRef ? 0 : (ox?.raw_gap ?? (r.mean != null ? r.mean - rawRef : null)),
        // δ is measured on the model's scale (leftness centred on mainstream liberals); the
        // yardstick's own δ = β_P·P̄ is small but not zero, so it is plotted where it sits.
        adj: isRef ? { med: adj?.med ?? 0, lo: adj?.med ?? 0, hi: adj?.med ?? 0 } : adj,
        licensed: !isRef && adj?.min_n_ok === true,
        mostlyPrior: adj?.mostly_prior === true,
        disagree: disagree && Array.isArray(range) && range.length === 2,
        range,
        placeboFlag: flags.placebo_flag?.[a.id] === true,
        placebo: placebo[a.id] ?? null,
        oaxaca: ox ?? null,
      };
    });
  });

  // Phase tween: 0 = raw gap, 1 = adjusted.
  const reduce = prefersReducedMotion();
  const t = new Tween(phase === 'adjusted' ? 1 : 0, { duration: reduce ? 0 : 1100, easing: cubicInOut });
  let mode = $state(phase === 'adjusted' ? 'adjusted' : 'raw');
  function setMode(m) {
    mode = m;
    t.target = m === 'adjusted' ? 1 : 0;
  }
  onMount(() => {
    if (phase !== 'animate') return;
    const id = setTimeout(() => setMode('adjusted'), reduce ? 0 : 900);
    return () => clearTimeout(id);
  });

  let open = $state(selected);
  let panel = $state();
  async function toggleRow(id) {
    open = open === id ? null : id;
    await tick();
    if (open && panel) panel.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
  }

  let showTable = $state(false);

  const domain = $derived.by(() => {
    const v = rows.flatMap((r) => [r.rawGap, r.adj?.lo, r.adj?.hi, r.adj?.med, ...(r.disagree ? r.range : [])]).filter((x) => x != null);
    return [Math.floor(Math.min(0, ...v) - 0.5), Math.ceil(Math.max(0, ...v) + 0.5)];
  });

  // C3 range: the licensed archetypes' intervals (ledger: "give the C2 numbers as its range").
  const c3 = $derived.by(() => {
    const lic = rows.filter((r) => r.licensed && r.adj?.lo != null);
    if (!lic.length) return null;
    return { lo: Math.min(...lic.map((r) => r.adj.lo)), hi: Math.max(...lic.map((r) => r.adj.hi)) };
  });
  const quoted = $derived(rows.filter((r) => r.licensed));
  const refAdj = $derived(rows.find((r) => r.isRef)?.adj?.med ?? 0);

  const COMPONENTS = [
    ['lean', 'How blue the seat was', 'Seat lean'],
    ['incumbency', 'Incumbents on the ballot', 'Incumbents'],
    ['opponent', 'Type of Republican', 'Opponent'],
    ['state_wave', 'State’s overall swing', 'State swing'],
    ['office', 'Office (House, Senate, governor)', 'Office'],
    ['demographic', 'Demographics', 'Demographics'],
    ['style', 'Candidate style', 'Style'],
    ['residual', 'Unexplained', 'Unexplained'],
  ];
  const lerp = (a, b, k) => (a == null ? b : b == null ? a : a + (b - a) * k);
</script>

<StageFrame
  {title}
  deks={[
    'Each lane’s average gain compared with mainstream liberals, in points of margin vs. Harris 2024.',
    `Each lane’s like-with-like style effect, in points of margin vs. Harris 2024. Mainstream liberals are the yardstick; their slight populist lean alone puts them at ${signed(refAdj, 1)}.`,
  ]}
  dekIndex={mode === 'raw' ? 0 : 1}
  note={`Preliminary, as of ${asOfLabel(ctx)}. Intervals are 80%.`}
  source={resultsSource(ctx)}
  sourceShort={resultsShort(ctx)}
  bind:showTable
>
  {#snippet legend()}
    <div class="seg" role="group" aria-label="Comparison">
      <button aria-pressed={mode === 'raw'} onclick={(e) => { e.stopPropagation(); setMode('raw'); }}>Raw average</button>
      <button aria-pressed={mode === 'adjusted'} onclick={(e) => { e.stopPropagation(); setMode('adjusted'); }}>Like with like</button>
    </div>
  {/snippet}

  {#snippet banner()}
    {#if status.blocked}
      <p class="review">Under review: the adjusted estimates come from a model that has not yet cleared its checks. Treat them as provisional, not findings.</p>
    {/if}
  {/snippet}

  {#snippet chart(w, h)}
    {@const narrow = w < 560}
    {@const labelW = narrow ? 112 : 170}
    {@const valW = narrow ? 76 : 130}
    {@const plotW = Math.max(80, w - labelW - valW - 16)}
    {@const x = scaleLinear().domain(domain).range([8, plotW - 8])}
    {@const ticks = x.ticks(narrow ? 4 : 8)}
    {@const k = t.current}
    {@const rowH = Math.max(46, Math.min(72, (h - 170) / rows.length))}
    <div class="grid" style:--label={labelW + 'px'} style:--val={valW + 'px'}>
      <div class="axis" aria-hidden="true">
        <span></span>
        <svg width={plotW} height="22">
          {#each ticks as tk (tk)}
            <text x={x(tk)} y="14" text-anchor="middle" class="tick">{tk === 0 ? '0' : signed(tk, 0)}</text>
          {/each}
        </svg>
        <span class="vh">{mode === 'raw' ? 'Raw gap' : 'Adjusted'}</span>
      </div>
      {#each rows as r (r.id)}
        {@const xm = x(lerp(r.rawGap, r.adj?.med, k))}
        {@const dim = !r.isRef && !r.licensed && k > 0.5}
        <button
          class="row"
          class:open={open === r.id}
          class:dim
          style:height={rowH + 'px'}
          disabled={r.isRef}
          aria-expanded={r.isRef ? undefined : open === r.id}
          aria-label={r.isRef
            ? `${r.label}: the yardstick, average gain ${signed(r.rawMean)} points; on the adjusted scale it sits at ${signed(r.adj?.med)}.`
            : `${r.label}, ${r.n} races. Raw gap ${signed(r.rawGap)}; adjusted ${signed(r.adj?.med)} (80%: ${signed(r.adj?.lo)} to ${signed(r.adj?.hi)}). Show breakdown.`}
          onclick={(e) => { e.stopPropagation(); toggleRow(r.id); }}
        >
          <span class="lab">
            <ArchChip id={r.id} size={13} />
            <span class="sub">{r.isRef ? 'the yardstick' : `${r.n} races`}{#if !r.isRef && !r.licensed}{narrow ? '' : ' · too few for own estimate'}{/if}</span>
          </span>
          <svg width={plotW} height={rowH} aria-hidden="true">
            {#each ticks as tk (tk)}<line class={tk === 0 ? 'zero' : 'gl'} x1={x(tk)} x2={x(tk)} y1="0" y2={rowH} />{/each}
            {#if !r.isRef}
              <!-- ghost of the raw position -->
              {#if r.rawGap != null && k > 0.02}
                <line class="trail" x1={x(r.rawGap)} x2={xm} y1={rowH / 2} y2={rowH / 2} />
                <path transform={`translate(${x(r.rawGap)},${rowH / 2})`} d={shapePath(r.shape, 5.5)} class="ghost" />
              {/if}
              {#if r.adj?.lo != null}
                <line
                  class="ci"
                  class:dashed={!r.licensed}
                  x1={x(r.adj.lo)}
                  x2={x(r.adj.hi)}
                  y1={rowH / 2}
                  y2={rowH / 2}
                  style:stroke={`var(${r.token})`}
                  style:opacity={k}
                />
              {/if}
              {#if r.disagree}
                <g style:opacity={k}>
                  <path class="bracket" d={`M${x(r.range[0])},${rowH / 2 - 12}v-4H${x(r.range[1])}v4`} />
                </g>
              {/if}
            {/if}
            <path transform={`translate(${r.isRef ? x(lerp(0, r.adj?.med, k)) : xm},${rowH / 2})`} d={shapePath(r.shape, 7)} class="mark" style:fill={`var(${r.token})`} />
          </svg>
          <span class="val tabular">
            {#if r.isRef && k < 0.5}
              <span class="big">0</span>
              <span class="sub">avg gain {signed(r.rawMean)}</span>
            {:else if r.isRef}
              <span class="big">{signed(r.adj?.med)}</span>
              <span class="sub">yardstick</span>
            {:else if k < 0.5}
              <span class="big">{signed(r.rawGap)}</span>
              <span class="sub">avg gain {signed(r.rawMean)}</span>
            {:else}
              <span class="big">{signed(r.adj?.med)}{r.licensed && r.placeboFlag ? '*' : ''}</span>
              {#if r.disagree}
                <span class="sub">models: {signed(r.range[0])} to {signed(r.range[1])}</span>
              {:else if r.adj?.lo != null}
                <span class="sub">{signed(r.adj.lo)} to {signed(r.adj.hi)}</span>
              {/if}
            {/if}
          </span>
        </button>
        {#if open === r.id && r.oaxaca}
          {@const parts = COMPONENTS.map(([key, long, short]) => ({ key, label: narrow ? short : long, v: r.oaxaca[key] ?? 0 })).filter((p) => p.key !== 'demographic' || p.v !== 0)}
          {@const span = Math.max(1, ...parts.map((p) => Math.abs(p.v)), Math.abs(r.rawGap ?? 0))}
          {@const bw = Math.max(80, Math.min(260, w - (narrow ? 170 : 290)))}
          {@const bx = scaleLinear().domain([-span, span]).range([0, bw])}
          {@const vt = oax.excluding_GOV_VT?.[r.id]}
          <div class="panel" bind:this={panel}>
            <p class="ph">Where the {signed(r.rawGap)}-point raw gap comes from</p>
            <ul class="bars">
              {#each parts as p (p.key)}
                <li>
                  <span class="bl">{p.label}</span>
                  <svg width={bw} height="14" aria-hidden="true">
                    <line class="zero" x1={bx(0)} x2={bx(0)} y1="0" y2="14" />
                    <rect
                      x={Math.min(bx(0), bx(p.v))}
                      y="3"
                      width={Math.max(1, Math.abs(bx(p.v) - bx(0)))}
                      height="8"
                      rx="2"
                      style:fill={p.key === 'style' ? `var(${r.token})` : 'var(--muted)'}
                    />
                  </svg>
                  <span class="bv tabular">{signed(p.v)}</span>
                </li>
              {/each}
              <li class="total">
                <span class="bl">Raw gap</span>
                <svg width={bw} height="14" aria-hidden="true">
                  <line class="zero" x1={bx(0)} x2={bx(0)} y1="0" y2="14" />
                  <rect x={Math.min(bx(0), bx(r.rawGap))} y="2" width={Math.max(1, Math.abs(bx(r.rawGap) - bx(0)))} height="10" rx="2" class="tot" />
                </svg>
                <span class="bv tabular">{signed(r.rawGap)}</span>
              </li>
            </ul>
            {#if vt}
              <p class="pn">
                Without Vermont’s governor race (a popular Republican incumbent), the progressive raw average is {signed(vt.raw_mean_progressive)}
                and the gap is {signed(vt.raw_gap)} ({vt.n} races).
              </p>
            {/if}
            {#if r.licensed}
              <p class="pn">{c2Sentence(r.label, r.adj)} {C2_CAVEAT}</p>
              {#if r.placeboFlag}<p class="pn">{placeboCaveat(r.placebo, r.adj.med)}</p>{/if}
            {:else}
              <p class="pn">Too few {r.label.toLowerCase()} races for their own estimate; the adjusted number is what the model predicts from candidate style alone{r.mostlyPrior ? ', and it mostly reflects our starting assumption' : ''}.</p>
            {/if}
          </div>
        {/if}
      {/each}
    </div>

    {#if k > 0.5}
      <div class="foot">
        {#if status.blocked}
          <p>{d.params?.banners?.uninformative ?? ''}</p>
        {:else if flags.no_predictive_gain && c3}
          <p class="lead">
            We found no detectable difference between styles once we compared like with like; the range runs from {signedInt(c3.lo)} to {signedInt(c3.hi)} points.
            That doesn't prove style never matters, only that any effect was too small to measure this year.
          </p>
        {/if}
        {#if !status.blocked}
          {#each quoted.filter((r) => r.placeboFlag) as r (r.id)}
            <p class="fn">* {r.label}: {placeboCaveat(r.placebo, r.adj.med)}</p>
          {/each}
          {#if quoted.length}<p class="fn">{C2_CAVEAT} Tap a row for the breakdown.</p>{/if}
        {/if}
      </div>
    {:else}
      <p class="foot fn">Tap a row to see what explains each gap.</p>
    {/if}
  {/snippet}

  {#snippet table()}
    <table>
      <caption>Gap to mainstream liberals, points of margin vs. Harris 2024</caption>
      <thead>
        <tr><th>Lane</th><th class="n">Races</th><th class="n">Avg gain</th><th class="n">Raw gap</th><th class="n">Adjusted</th><th class="n">80% range</th></tr>
      </thead>
      <tbody>
        {#each rows as r (r.id)}
          <tr>
            <td>{r.label}{r.isRef ? ' (yardstick)' : ''}{!r.isRef && !r.licensed ? ' (too few races for own estimate)' : ''}</td>
            <td class="n">{r.n ?? '–'}</td>
            <td class="n">{signed(r.rawMean)}</td>
            <td class="n">{r.isRef ? '0' : signed(r.rawGap)}</td>
            <td class="n">{r.isRef ? `reference (${signed(r.adj?.med, 2)})` : signed(r.adj?.med)}</td>
            <td class="n">{r.isRef ? '' : r.disagree ? `models: ${signed(r.range[0])} to ${signed(r.range[1])}` : `${signed(r.adj?.lo)} to ${signed(r.adj?.hi)}`}</td>
          </tr>
        {/each}
      </tbody>
    </table>
    {#each rows.filter((r) => r.oaxaca) as r (r.id)}
      <table>
        <caption>{r.label}: breakdown of the raw gap</caption>
        <tbody>
          {#each COMPONENTS as [key, label] (key)}
            <tr><td>{label}</td><td class="n">{signed(r.oaxaca[key] ?? 0)}</td></tr>
          {/each}
          <tr><th>Raw gap</th><th class="n">{signed(r.rawGap)}</th></tr>
        </tbody>
      </table>
    {/each}
    {#if !status.blocked}
      {#each quoted as r (r.id)}
        <p class="fn">{c2Sentence(r.label, r.adj)} {C2_CAVEAT} {r.placeboFlag ? placeboCaveat(r.placebo, r.adj.med) : ''}</p>
      {/each}
    {/if}
  {/snippet}
</StageFrame>

<style>
  .seg {
    display: inline-flex;
    border: 1px solid var(--ring);
    border-radius: 999px;
    overflow: hidden;
    background: var(--surface);
  }
  .seg button {
    min-height: 44px;
    padding: 0 14px;
    border: 0;
    background: none;
    color: var(--ink-2);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }
  .seg button[aria-pressed='true'] {
    background: var(--ink);
    color: var(--bg);
  }
  .review {
    margin: 0;
    padding: 6px 10px;
    border-left: 3px solid var(--axis);
    background: var(--surface-2);
    color: var(--ink-2);
    font-size: 12px;
  }
  .grid {
    display: flex;
    flex-direction: column;
  }
  .axis,
  .row {
    display: grid;
    grid-template-columns: var(--label) 1fr var(--val);
    align-items: center;
    column-gap: 8px;
  }
  .axis svg {
    overflow: visible;
  }
  .tick {
    font-size: 11px;
    fill: var(--muted);
  }
  .vh {
    font-size: 11px;
    color: var(--muted);
    font-weight: 600;
    text-align: right;
  }
  .row {
    width: 100%;
    padding: 0;
    border: 0;
    border-top: 1px solid var(--grid);
    background: none;
    text-align: left;
    cursor: pointer;
    color: var(--ink);
  }
  .row:disabled {
    cursor: default;
    opacity: 1;
  }
  .row:not(:disabled):hover,
  .row.open {
    background: var(--surface-2);
  }
  .row svg {
    overflow: visible;
  }
  .lab {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding-left: 4px;
    font-size: 13px;
    min-width: 0;
  }
  .sub {
    font-size: 11px;
    color: var(--muted);
    white-space: nowrap;
  }
  .gl {
    stroke: var(--grid);
  }
  .zero {
    stroke: var(--axis);
    stroke-width: 1.5;
  }
  .mark {
    stroke: var(--bg);
    stroke-width: 1.5;
  }
  .ghost {
    fill: none;
    stroke: var(--muted);
    stroke-width: 1.2;
    stroke-dasharray: 2 2;
  }
  .trail {
    stroke: var(--muted);
    stroke-width: 1;
    stroke-dasharray: 1 3;
  }
  .ci {
    stroke-width: 3;
    stroke-linecap: round;
  }
  .ci.dashed {
    stroke-dasharray: 4 3;
  }
  .bracket {
    fill: none;
    stroke: var(--ink-2);
    stroke-width: 1.2;
  }
  .row.dim .mark {
    opacity: 0.55;
  }
  .val {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    padding-right: 4px;
  }
  .big {
    font-size: 15px;
    font-weight: 700;
  }
  .panel {
    margin: 0 0 6px;
    padding: 10px 12px;
    background: var(--surface-2);
    border-radius: 0 0 var(--radius) var(--radius);
  }
  .ph {
    margin: 0 0 6px;
    font-weight: 600;
    font-size: 12px;
  }
  .bars {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .bars li {
    display: grid;
    grid-template-columns: minmax(0, 210px) auto 44px;
    justify-content: start;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--ink-2);
    padding: 1px 0;
  }
  .bars li.total {
    border-top: 1px solid var(--axis);
    margin-top: 3px;
    padding-top: 3px;
    color: var(--ink);
    font-weight: 600;
  }
  .tot {
    fill: var(--ink-2);
  }
  .bv {
    text-align: right;
  }
  .bl {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pn {
    margin: 8px 0 0;
    font-size: 12px;
    line-height: 1.4;
    color: var(--ink-2);
  }
  .foot {
    margin-top: 10px;
  }
  .foot p {
    margin: 0 0 4px;
  }
  .lead {
    font-size: 13px;
    line-height: 1.4;
    color: var(--ink);
  }
  .fn {
    font-size: 11px;
    line-height: 1.4;
    color: var(--ink-2);
  }
  @media (max-width: 560px) {
    .seg button {
      padding: 0 10px;
      font-size: 12px;
    }
    .lab {
      font-size: 12px;
    }
  }
</style>
