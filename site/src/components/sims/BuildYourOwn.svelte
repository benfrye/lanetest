<script>
  import { untrack } from 'svelte';
  // Sim 4 (METHODOLOGY §6.5 simCustom, §6.6 Sim 4). Build a hypothetical nominee:
  // ideology L (0 center … 2 left), posture P (0 establishment … 1 populist), home state,
  // opponent, environment (ctx.reader.env), turnout geography u, style preset → state map,
  // P(win) with interval, break-even E*, and the margin waterfall. Outside the 2026 data hull
  // the engine widens the style draws ×2 and we show the extrapolation warning.
  //
  // Two panels never share colors: the (L, P) pad carries archetype marks (shape + color +
  // label); the map carries party colors.
  import { scaleLinear } from 'd3-scale';
  import { ARCHETYPES, ARCHETYPE_BY_ID, shapePath } from '../../lib/archetypes.js';
  import SimFrame from './SimFrame.svelte';
  import Slider from './Slider.svelte';
  import Segmented from './Segmented.svelte';
  import TileMap from './TileMap.svelte';
  import {
    fmtE, pct, pctRange, signed, params, envSlider, piOpt, envPoint, defaultEnvCenter, latest, clamp,
    presetOptions, unitList,
  } from './shared.js';

  let { ctx, nodes } = $props();
  const ctx0 = untrack(() => ctx); // stage components are keyed per step: setup reads ctx once

  const P = params(ctx0);
  const es = envSlider(ctx0);
  const tu = P.turnout_u ?? { min: -1, max: 1, default: 0 };
  const coords = P.style?.coords ?? {};
  const hull = P.style?.hull ?? [];
  const presets = presetOptions(ctx0);
  const states = unitList(ctx0).filter((u) => !u.parent).sort((a, b) => a.name.localeCompare(b.name));
  if (ctx0.reader && ctx0.reader.env == null) ctx0.reader.env = defaultEnvCenter(ctx0);

  // start at the reader's guessed archetype (or the reference)
  const start = coords[ctx0.reader?.guess] ?? coords.mainstream_liberal ?? { L: 1, P: 0 };
  let L = $state(+clamp(start.L, 0, 2).toFixed(2));
  let Pp = $state(+clamp(start.P, 0, 1).toFixed(2));
  let home = $state('');
  let opponent = $state('generic');
  let u = $state(tu.default ?? 0);
  let preset = $state('agnostic');

  let res = $state(null);
  let error = $state('');
  const go = latest(
    (o) => ctx.simReady.then(() => ctx.sim.simCustom(o, {}, { channel: 'custom' })),
    (r) => (res = r),
    (e) => (error = e.message),
  );
  $effect(() => {
    go({
      L,
      P: Pp,
      home: home || null,
      opponent,
      env: envPoint(ctx.reader.env),
      pi: piOpt(ctx.reader),
      preset,
      u,
    });
  });

  // ---- (L, P) pad
  let pw = $state(0);
  const PH = $derived(clamp(Math.round(pw * 0.5), 150, 220));
  const PM = { l: 30, r: 14, t: 14, b: 34 };
  const px = $derived(scaleLinear().domain([2, 0]).range([PM.l, Math.max(PM.l + 50, pw - PM.r)]));
  const py = $derived(scaleLinear().domain([0, 1]).range([PH - PM.b, PM.t]));
  const hullPath = $derived(hull.length ? `M${hull.map(([l, p]) => `${px(l)},${py(p)}`).join('L')}Z` : '');
  let drag = false;
  function setFrom(e) {
    const r = e.currentTarget.getBoundingClientRect();
    L = +clamp(px.invert(e.clientX - r.left), 0, 2).toFixed(2);
    Pp = +clamp(py.invert(e.clientY - r.top), 0, 1).toFixed(2);
  }
  const homeName = $derived(states.find((s) => s.id === home)?.name ?? '');
  const total = $derived(res?.waterfall?.find((d) => d.total));
  const oppOptions = [
    { value: 'generic', label: 'Generic' },
    { value: 'maga', label: 'MAGA heir' },
    { value: 'traditional', label: 'Traditional' },
  ];
  const voteLabel = (e) => (Math.abs(e) < 0.05 ? 'exactly even' : fmtE(e, 1));
  const uFmt = (v) => (Math.abs(v) < 1e-9 ? 'evenly' : v > 0 ? `${Math.round(v * 100)}% like 2026` : `${Math.round(-v * 100)}% the opposite`);
  const nearest = $derived.by(() => {
    let best = null;
    for (const a of ARCHETYPES) {
      const c = coords[a.id];
      if (!c) continue;
      const d = Math.hypot(c.L - L, c.P - Pp);
      if (!best || d < best.d) best = { id: a.id, d };
    }
    return best;
  });
</script>

<SimFrame
  {ctx}
  title="Build your own nominee"
  dek="Set where your candidate sits and the conditions they face. The map and odds follow the model."
>
  <div class="layout">
    <section class="result" aria-live="polite">
      {#if res}
        <p class="headline">
          <span class="pw tabular" class:extrap={res.extrapolated}>{pct(res.V)}</span>
          <span class="pwtext">chance of reaching 270 with a national vote of {voteLabel(ctx.reader.env)}<br /><span class="sub">Likely range {pctRange(res.V80)} · a coin flip at {Math.abs(res.Estar[0]) < 0.5 ? 'an even national vote' : `about ${fmtE(res.Estar[0])}`}</span></span>
        </p>
        <p class="note vsref">
          {#if Math.round(res.dV[0] * 100) === 0}About the same as a typical mainstream liberal. Under these assumptions; not a forecast.{:else}{Math.abs(Math.round(res.dV[0] * 100))} points {res.dV[0] > 0 ? 'better' : 'worse'} than a typical mainstream liberal from no particular state (could be {signed(res.dV[1] * 100, 0)} to {signed(res.dV[2] * 100, 0)}). Under these assumptions; not a forecast.{/if}
        </p>
        <!-- Both messages share one grid cell, so the slot keeps the taller one's height and
             nothing below moves when the candidate crosses the edge of the 2026 data. -->
        <div class="fit-slot" role="status">
          <p class="warn" class:off={!res.extrapolated} aria-hidden={!res.extrapolated}><b>Outside the 2026 data, a guess.</b> No 2026 nominee ran with this mix, so the style effect is extrapolated and its uncertainty is doubled.</p>
          <p class="inside" class:off={res.extrapolated} aria-hidden={res.extrapolated}><b>Inside the 2026 data.</b> Real 2026 nominees ran with a mix like this, so the estimate rests on actual results.</p>
        </div>
        <TileMap {ctx} values={res.stateP} kind="prob" label="Each state's chance for your candidate" maxHeight={260} />
      {:else if error}
        <p class="error">Simulation error: {error}</p>
      {:else}
        <p class="note">Simulating…</p>
      {/if}
    </section>

    <section class="inputs">
      <div class="pad" bind:clientWidth={pw}>
        {#if pw > 0}
          <!-- svelte-ignore a11y_no_static_element_interactions -->
          <svg
            width={pw}
            height={PH}
            role="img"
            aria-label={`Candidate position: ideology ${L.toFixed(2)} of 2, populism ${Pp.toFixed(2)} of 1${res?.extrapolated ? ', outside the 2026 data' : ''}. Use the sliders below to move it.`}
            onpointerdown={(e) => { drag = true; e.currentTarget.setPointerCapture?.(e.pointerId); setFrom(e); }}
            onpointermove={(e) => drag && setFrom(e)}
            onpointerup={() => (drag = false)}
            onpointercancel={() => (drag = false)}
            style="touch-action: none"
          >
            <defs>
              <pattern id="byo-hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="6" style:stroke="var(--axis)" stroke-width="1.2" />
              </pattern>
            </defs>
            <rect x={px(2)} y={py(1)} width={px(0) - px(2)} height={py(0) - py(1)} fill="url(#byo-hatch)" />
            <path d={hullPath} class="hull" />
            <text class="lbl-2 halo" x={px(2) + 4} y={py(0) - 6}>Hatched: outside the 2026 data</text>
            <text class="tick" x={px(2)} y={PH - PM.b + 15} text-anchor="start">← Left</text>
            <text class="tick" x={px(0)} y={PH - PM.b + 15} text-anchor="end">Center →</text>
            <text class="axis-title" x={(px(2) + px(0)) / 2} y={PH - 4} text-anchor="middle">Ideology</text>
            <text class="tick" transform="translate({PM.l - 10},{(py(0) + py(1)) / 2}) rotate(-90)" text-anchor="middle">Establishment → Populist</text>
            {#each ARCHETYPES as a (a.id)}
              {@const c = coords[a.id]}
              {#if c}
                <g transform="translate({px(c.L)},{py(c.P)})">
                  <path d={shapePath(a.shape, 5.5)} style:fill="var({a.token})" style:stroke="var(--bg)" stroke-width="1.5" />
                </g>
              {/if}
            {/each}
            <g transform="translate({px(L)},{py(Pp)})">
              <circle r="11" class="me-ring" />
              <circle r="4" class="me" />
            </g>
          </svg>
          <div class="padlegend">
            {#each ARCHETYPES as a (a.id)}
              <span class="pk"><svg width="11" height="11" viewBox="-6 -6 12 12" aria-hidden="true"><path d={shapePath(a.shape, 4.5)} style:fill="var({a.token})" /></svg>{a.label}</span>
            {/each}
            <span class="pk"><svg width="12" height="12" viewBox="-6 -6 12 12" aria-hidden="true"><circle r="4.5" class="me-ring" /></svg>Yours{nearest && nearest.d < 0.15 ? ` (≈ ${ARCHETYPE_BY_ID[nearest.id].label.toLowerCase()})` : ''}</span>
          </div>
        {/if}
      </div>

      <div class="grid">
        <Slider label="Ideology" bind:value={L} min={0} max={2} step={0.05} format={(v) => (+v).toFixed(2)} ends={['center', 'left']} />
        <Slider label="Posture" bind:value={Pp} min={0} max={1} step={0.05} format={(v) => (+v).toFixed(2)} ends={['establishment', 'populist']} />
        <Slider
          label="National mood"
          bind:value={ctx.reader.env}
          min={es.min}
          max={es.max}
          step={es.step}
          format={(v) => fmtE(+v, 1)}
          ends={[fmtE(es.min), fmtE(es.max)]}
        />
        <Slider
          label="Where the swing lands"
          bind:value={u}
          min={tu.min ?? -1}
          max={tu.max ?? 1}
          step={0.1}
          format={uFmt}
          ends={['opposite of 2026', 'like 2026']}
          hint="Toward 'like 2026', states with more young and Hispanic voters (Arizona, Nevada, Texas) swing more. A what-if, not tested on past elections."
        />
        <div class="field">
          <label for="byo-home">Home state (about +2 points there)</label>
          <select id="byo-home" bind:value={home}>
            <option value="">None</option>
            {#each states as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
          </select>
        </div>
        <div class="field">
          <label for="byo-opp">Republican opponent</label>
          <select id="byo-opp" bind:value={opponent}>
            {#each oppOptions as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
          </select>
        </div>
        {#if presets.length > 1}
          <div class="field wide">
            <span class="flabel">How much to trust 2026</span>
            <Segmented label="Style-effect preset" options={presets} bind:value={preset} small />
          </div>
        {/if}
      </div>
    </section>
  </div>

  {#snippet table()}
    {#if res}
      <table class="data">
        <caption>Your candidate: ideology {L.toFixed(2)}, posture {Pp.toFixed(2)}{homeName ? `, from ${homeName}` : ''}, at {fmtE(ctx.reader.env, 1)}</caption>
        <tbody>
          <tr><th scope="row">Chance of winning</th><td>{pct(res.V)} (80% range {pctRange(res.V80)})</td></tr>
          <tr><th scope="row">Coin-flip environment</th><td>{fmtE(res.Estar[0])} ({fmtE(res.Estar[1])} to {fmtE(res.Estar[2])})</td></tr>
          <tr><th scope="row">Outside 2026 data</th><td>{res.extrapolated ? 'Yes (a guess)' : 'No'}</td></tr>
          {#each res.waterfall as d (d.key)}
            <tr><th scope="row">{d.total ? 'Tipping-point margin' : d.label}</th><td>{signed(d.value, 1)} pts</td></tr>
          {/each}
        </tbody>
      </table>
      <table class="data">
        <caption>Chance by state</caption>
        <thead><tr><th scope="col">State</th><th scope="col">Chance for your candidate</th></tr></thead>
        <tbody>
          {#each unitList(ctx) as s (s.id)}<tr><th scope="row">{s.name}</th><td>{pct(res.stateP[s.id])}</td></tr>{/each}
        </tbody>
      </table>
    {/if}
  {/snippet}

  {#snippet notes()}
    {#if res && total}
      <p>
        Margin at the tipping-point state, median:
        {#each res.waterfall.filter((d) => !d.total) as d, i (d.key)}{i ? ' · ' : ''}{d.label.replace(' (E)', '')} {signed(d.value, 1)}{/each}
        = <b>{signed(total.value, 1)}</b>.
      </p>
    {/if}
  {/snippet}
</SimFrame>

<style>
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
    gap: 14px 24px;
    align-items: start;
  }
  .result {
    display: grid;
    gap: 8px;
    order: 2;
  }
  .inputs {
    display: grid;
    gap: 10px;
    order: 1;
  }
  .headline {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 0;
  }
  .pw {
    font-size: 40px;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
    padding: 2px 4px;
    border-radius: 6px;
  }
  /* This line wraps or not depending on the numbers, so hold its longest height: two lines,
     three on phones. */
  .vsref {
    min-height: 2.8em;
  }
  @container (max-width: 520px) {
    .vsref {
      min-height: 4.2em;
    }
  }
  .fit-slot {
    display: grid;
  }
  .fit-slot > p {
    grid-area: 1 / 1;
    margin: 0;
    transition: opacity 0.25s;
  }
  .fit-slot > .off {
    opacity: 0;
    visibility: hidden;
  }
  .inside {
    padding: 7px 10px;
    border-left: 3px solid var(--ring);
    border-radius: 0 6px 6px 0;
    color: var(--ink-2);
    font-size: 12.5px;
  }
  .pw.extrap {
    background: repeating-linear-gradient(45deg, var(--grid) 0 2px, transparent 2px 6px);
  }
  .pwtext {
    font-size: 14px;
    line-height: 1.3;
  }
  .sub {
    font-size: 12.5px;
    color: var(--ink-2);
  }
  .pad {
    position: relative;
    width: 100%;
  }
  .pad svg {
    display: block;
    overflow: visible;
    cursor: crosshair;
  }
  .hull {
    fill: var(--bg);
    stroke: var(--axis);
    stroke-width: 1;
  }
  .me-ring {
    fill: none;
    stroke: var(--ink);
    stroke-width: 2;
  }
  .me {
    fill: var(--ink);
  }
  .padlegend {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 10px;
    font-size: 11px;
    color: var(--ink-2);
  }
  .pk {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
  }
  .pk svg {
    overflow: visible;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 6px 16px;
  }
  .field {
    display: grid;
    gap: 3px;
    align-content: start;
    font-size: 12.5px;
    color: var(--ink-2);
    font-weight: 500;
  }
  .field.wide {
    grid-column: 1 / -1;
  }
  .field label,
  .flabel {
    color: var(--ink-2);
  }
  select {
    min-height: 44px;
    padding: 0 10px;
    border: 1px solid var(--axis);
    border-radius: 9px;
    background: var(--surface);
    color: var(--ink);
    font: 600 14px var(--font-ui);
    max-width: 100%;
  }
  @container (max-width: 760px) {
    .layout {
      grid-template-columns: minmax(0, 1fr);
    }
    .result {
      order: 1;
    }
    .inputs {
      order: 2;
    }
  }
  @container (max-width: 420px) {
    .grid {
      grid-template-columns: minmax(0, 1fr);
    }
    .pw {
      font-size: 34px;
    }
  }
</style>
